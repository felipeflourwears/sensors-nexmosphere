import os
import time
import cv2
import re
import models.ModelVideos as cfg
import sys
import threading
import subprocess
import numpy as np

video_lock = threading.Lock()
video_to_play = cfg.LOOP
video_request = 0

import constants as cts

current_sensor = cts.NONE
current_id = None

current_rotation = None
current_video = None

current_rfid_stack = []

# Grosor (px) de la franja del video que se muestrea para COLOR_FONDO = "auto".
MUESTRA_BORDE = 8

EXTENSIONES_IMAGEN = (".png", ".jpg", ".jpeg")
TIEMPO_INACTIVIDAD_IMAGEN = 2.0  # segundos antes de volver a cfg.LOOP

ES_WINDOWS = sys.platform.startswith("win")
ES_MAC = sys.platform == "darwin"

VENTANA = "Video"


# ---------------------------------------------------------------------------
# Reproducción en modo kiosko
# ---------------------------------------------------------------------------
def ocultar_cursor():
    """Oculta el puntero del ratón. Solo en Linux/X11, y si 'unclutter' existe."""
    if not cfg.OCULTAR_CURSOR or ES_WINDOWS or ES_MAC:
        return None
    try:
        return subprocess.Popen(
            ["unclutter", "-idle", "0", "-root"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError):
        return None


# " 0: +*DP-1 2560/800x1080/340+1920+0  DP-1"
RE_MONITOR = re.compile(
    r"^\s*(\d+):\s+\+(\*?)(\S+)\s+(\d+)/\d+x(\d+)/\d+\+(-?\d+)\+(-?\d+)"
)


def detectar_monitores():
    """Lista de monitores vía xrandr. Vacía si no está disponible (Windows/Wayland puro)."""
    try:
        salida = subprocess.run(
            ["xrandr", "--listmonitors"],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return []

    monitores = []
    for linea in salida.splitlines():
        m = RE_MONITOR.match(linea)
        if m:
            monitores.append({
                "indice": int(m.group(1)),
                "primario": m.group(2) == "*",
                "nombre": m.group(3),
                "ancho": int(m.group(4)),
                "alto": int(m.group(5)),
                "x": int(m.group(6)),
                "y": int(m.group(7)),
            })
    return monitores


def elegir_monitor(preferencia):
    """Resuelve cfg.MONITOR a un monitor concreto, o None si no se puede."""
    monitores = detectar_monitores()
    if not monitores:
        return None

    print("Monitores detectados:")
    for m in monitores:
        marca = " (primario)" if m["primario"] else ""
        print(f"  [{m['indice']}] {m['nombre']}: {m['ancho']}x{m['alto']} "
              f"en +{m['x']}+{m['y']}{marca}")

    elegido = None
    if isinstance(preferencia, int) and not isinstance(preferencia, bool):
        for m in monitores:
            if m["indice"] == preferencia:
                elegido = m
    elif isinstance(preferencia, str) and preferencia.lower() not in ("auto", "primary"):
        for m in monitores:
            if m["nombre"].lower() == preferencia.lower():
                elegido = m
        if elegido is None:
            print(f"AVISO: no existe el monitor '{preferencia}', uso el primario.")

    if elegido is None:
        elegido = next((m for m in monitores if m["primario"]), monitores[0])

    print(f"Kiosko en {elegido['nombre']} ({elegido['ancho']}x{elegido['alto']})")
    return elegido


def crear_ventana_kiosko(monitor):
    """Crea la ventana en fullscreen sin decoración, en el monitor indicado."""
    cv2.namedWindow(VENTANA, cv2.WINDOW_GUI_NORMAL | cv2.WINDOW_NORMAL)

    if monitor is not None:
        destino_x, destino_y = monitor["x"], monitor["y"]
        ancho, alto = monitor["ancho"], monitor["alto"]
    else:
        destino_x, destino_y = cfg.MONITOR_X, cfg.MONITOR_Y
        ancho, alto = 1920, 1080

    cv2.imshow(VENTANA, np.zeros((alto, ancho, 3), dtype=np.uint8))
    cv2.waitKey(1)

    if monitor is not None:
        cv2.resizeWindow(VENTANA, ancho, alto)

    cv2.moveWindow(VENTANA, destino_x, destino_y)
    cv2.waitKey(1)

    cv2.setWindowProperty(VENTANA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    for _ in range(5):
        cv2.waitKey(20)


def tamano_ventana():
    """Tamaño real del área de imagen de la ventana, o None si no se puede leer."""
    try:
        _, _, ancho, alto = cv2.getWindowImageRect(VENTANA)
    except cv2.error:
        return None
    if ancho and alto and ancho > 0 and alto > 0:
        return ancho, alto
    return None


def geometria_destino(monitor):
    """Resolución a la que hay que ajustar los frames."""
    real = tamano_ventana()
    if monitor is None:
        return real

    esperado = (monitor["ancho"], monitor["alto"])
    if real and real != esperado:
        print(f"AVISO: la ventana mide {real[0]}x{real[1]} pero "
              f"{monitor['nombre']} es {esperado[0]}x{esperado[1]}. Uso el tamaño real.")
        return real
    return esperado


def ventana_cerrada():
    """True si el usuario cerró la ventana por fuera (Alt+F4, etc.)."""
    try:
        return cv2.getWindowProperty(VENTANA, cv2.WND_PROP_VISIBLE) < 1
    except cv2.error:
        return True


def es_imagen(path):
    """True si la ruta corresponde a un archivo de imagen estática."""
    return isinstance(path, str) and path.lower().endswith(EXTENSIONES_IMAGEN)


def cargar_imagen(path):
    """Carga una imagen BGR desde disco o devuelve None si falla."""
    if not os.path.isfile(path):
        print(f"Error: no existe la imagen '{path}'")
        return None
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        print(f"Error al decodificar la imagen '{path}'")
        return None
    return img


def abrir_video(path):
    """Abre un video y devuelve (cap, delay_ms) o None si no se pudo abrir."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        cap.release()
        print(f"Error al abrir el video '{path}'")
        return None
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0 or fps > 240:
        fps = 25.0
    return cap, max(1, int(round(1000.0 / fps)))


class Lienzo:
    """Encaja cada frame en la pantalla según cfg.AJUSTE."""

    def __init__(self, pantalla, modo, color_fondo):
        self.pantalla = pantalla
        self.modo = modo
        self.color_fondo = color_fondo
        self.buffer = None

    def ajustar(self, frame):
        if self.pantalla is None:
            return frame

        ancho, alto = self.pantalla
        h, w = frame.shape[:2]
        if (w, h) == (ancho, alto):
            return frame

        if self.modo == "estirar":
            return cv2.resize(frame, (ancho, alto), interpolation=cv2.INTER_AREA)

        if self.modo == "cubrir":
            return self._cubrir(frame, ancho, alto)
        return self._contener(frame, ancho, alto)

    def _cubrir(self, frame, ancho, alto):
        """Llena la pantalla y recorta el excedente por el centro. Sin barras."""
        h, w = frame.shape[:2]
        escala = max(ancho / w, alto / h)
        nuevo_w = max(ancho, int(round(w * escala)))
        nuevo_h = max(alto, int(round(h * escala)))
        escalado = cv2.resize(frame, (nuevo_w, nuevo_h), interpolation=cv2.INTER_AREA)

        x0 = (nuevo_w - ancho) // 2
        y0 = (nuevo_h - alto) // 2
        return escalado[y0:y0 + alto, x0:x0 + ancho]

    def _contener(self, frame, ancho, alto):
        """Muestra el video completo y rellena el hueco restante."""
        h, w = frame.shape[:2]
        escala = min(ancho / w, alto / h)
        nuevo_w = max(1, min(ancho, int(round(w * escala))))
        nuevo_h = max(1, min(alto, int(round(h * escala))))
        escalado = cv2.resize(frame, (nuevo_w, nuevo_h), interpolation=cv2.INTER_AREA)

        if (nuevo_w, nuevo_h) == (ancho, alto):
            return escalado

        if self.buffer is None or self.buffer.shape[:2] != (alto, ancho):
            self.buffer = np.zeros((alto, ancho, 3), dtype=np.uint8)

        y0 = (alto - nuevo_h) // 2
        x0 = (ancho - nuevo_w) // 2

        if x0 > 0:
            izq, der = self._colores_laterales(escalado)
            self.buffer[:, :x0] = izq
            self.buffer[:, x0 + nuevo_w:] = der
        if y0 > 0:
            arriba, abajo = self._colores_verticales(escalado)
            self.buffer[:y0] = arriba
            self.buffer[y0 + nuevo_h:] = abajo

        self.buffer[y0:y0 + nuevo_h, x0:x0 + nuevo_w] = escalado
        return self.buffer

    def _colores_laterales(self, img):
        if self.color_fondo != "auto":
            return self.color_fondo, self.color_fondo
        borde = min(MUESTRA_BORDE, img.shape[1])
        return self._promedio(img[:, :borde]), self._promedio(img[:, -borde:])

    def _colores_verticales(self, img):
        if self.color_fondo != "auto":
            return self.color_fondo, self.color_fondo
        borde = min(MUESTRA_BORDE, img.shape[0])
        return self._promedio(img[:borde]), self._promedio(img[-borde:])

    @staticmethod
    def _promedio(muestra):
        """Color medio de una franja, como entero BGR."""
        return muestra.reshape(-1, 3).mean(axis=0).astype(np.uint8)


def solicitar_video(path):
    global video_to_play, video_request
    with video_lock:
        video_to_play = path
        video_request += 1


def elegir_video(sensor, value):
    sensor_clave = cfg.SENSORS.get(sensor) or {}
    global current_rotation
    global current_rfid_stack

    if sensor != cts.ROTARY_BUTTON:
        current_rotation = None

    match sensor:
        case cts.PUSH_BUTTON:
            return sensor_clave.get("videos", {}).get(str(value), "")

        case cts.ROTARY_BUTTON:
            value = int(value)
            if value == current_rotation:
                return ""
            current_rotation = value
            return sensor_clave.get("videos", {}).get(value, "")

        case cts.MAGNETIC_PICK_UP_SENSOR:
            return sensor_clave.get("videos", {}).get(value, "")

        case cts.AIR_BUTTON:
            return sensor_clave.get("videos", {}).get(value, "")

        case cts.PRESENCE_SENSOR:
            return sensor_clave.get("videos", {}).get(value, "")

        case cts.LIGHT_SENSOR:
            return ""

        case cts.RFID_TAG:
            len_rfids = len(value)

            if len_rfids == 0:
                return ("")
            videos_rfid = sensor_clave.get("videos", {})
            if len_rfids == 1:
                return (videos_rfid.get(value[0], ""))
            elif len_rfids == 2:
                return (videos_rfid.get(value[0], ""), videos_rfid.get(value[1], ""))
            elif len_rfids == 3:
                return (videos_rfid.get(value[1], ""), videos_rfid.get(value[2], ""))
            elif len_rfids == 4:
                return (videos_rfid.get(value[0], ""), videos_rfid.get(value[1], ""), videos_rfid.get(value[2], ""), videos_rfid.get(value[3], ""))
            else:
                return ("")


def play_videos(stop_event, app_state):
    global current_video, current_rotation

    monitor = elegir_monitor(cfg.MONITOR)
    crear_ventana_kiosko(monitor)

    pantalla = geometria_destino(monitor)
    if pantalla:
        print(f"Ajustando video a {pantalla[0]}x{pantalla[1]} (modo '{cfg.AJUSTE}')")
    lienzo = Lienzo(pantalla, cfg.AJUSTE, cfg.COLOR_FONDO)

    cap = None
    imagen_actual = None
    inicio_imagen = None
    cache_imagenes = {}
    current_video = None
    current_request = -1
    delay = 40
    fallos_loop = 0
    frames = 0

    try:
        while not stop_event.is_set():
            if app_state.get_updated():
                sensor, value = app_state.get_status()
                path = elegir_video(sensor, value)
                print("path: ", path)
                if path:
                    solicitar_video(path)
            elif app_state.get_updated_rfids():
                rfids = app_state.get_rfids()
                paths = elegir_video(cts.RFID_TAG, rfids)
                if paths[0] != "":
                    solicitar_video(paths) # TODO adapt the code to allow for multiple video split screen, 1, 2 and 4 sections.

            with video_lock:
                deseado, request = video_to_play, video_request

            # Cambio de medio (video o imagen)
            if deseado != current_video or request != current_request:
                if es_imagen(deseado):
                    img = cache_imagenes.get(deseado)
                    if img is None:
                        img = cargar_imagen(deseado)
                        if img is not None:
                            cache_imagenes[deseado] = img

                    if img is None:
                        if deseado != cfg.LOOP:
                            solicitar_video(cfg.LOOP)
                            continue
                        break

                    if cap is not None:
                        cap.release()
                        cap = None

                    imagen_actual = img
                    inicio_imagen = time.monotonic()
                    current_video, current_request = deseado, request
                    delay = 30  # refresco rápido para responder sin latencia al giro del rotary
                else:
                    nuevo = abrir_video(deseado)
                    if nuevo is None:
                        if deseado != cfg.LOOP:
                            solicitar_video(cfg.LOOP)
                            continue
                        print("No se pudo abrir el video de loop. Cerrando.")
                        break
                    if cap is not None:
                        cap.release()
                    cap, delay = nuevo
                    imagen_actual = None
                    inicio_imagen = None
                    current_video, current_request = deseado, request
                    fallos_loop = 0

            # Obtención del frame actual (imagen estática vs video)
            if imagen_actual is not None:
                if (time.monotonic() - inicio_imagen) >= TIEMPO_INACTIVIDAD_IMAGEN:
                    current_rotation = None
                    solicitar_video(cfg.LOOP)
                    continue
                frame = imagen_actual
            else:
                ret, frame = cap.read()
                if not ret:
                    if current_video != cfg.LOOP:
                        solicitar_video(cfg.LOOP)
                        continue
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        fallos_loop += 1
                        if fallos_loop >= 3:
                            print("No se pueden leer frames del video de loop. Cerrando.")
                            break
                        continue
                    fallos_loop = 0

            frames += 1
            if frames % 50 == 0:
                real = tamano_ventana()
                if real and real != lienzo.pantalla:
                    print(f"Pantalla cambió a {real[0]}x{real[1]}, reajustando.")
                    lienzo = Lienzo(real, cfg.AJUSTE, cfg.COLOR_FONDO)

            cv2.imshow(VENTANA, lienzo.ajustar(frame))

            key = cv2.waitKey(delay) & 0xFF
            if key == ord("q") or key == 27:
                break
            if ventana_cerrada():
                break
    finally:
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        stop_event.set()
