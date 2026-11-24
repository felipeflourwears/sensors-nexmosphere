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
video_to_play = (cfg.LOOP,)
video_request = 0

import constants as cts

current_sensor = cts.NONE
current_id = None

current_rotation = None
current_distance = None
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
def hide_cursor():
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


def liberar_caps(caps):
    """Libera una lista de objetos cv2.VideoCapture."""
    for cap in caps:
        if cap is not None:
            cap.release()


def abrir_videos(paths):
    """Abre de 1 a 4 videos simultáneos. Devuelve (caps, delay_ms) o None si falla."""
    caps = []
    min_delay = 40
    for path in paths[:4]:
        res = abrir_video(path)
        if res is None:
            liberar_caps(caps)
            return None
        cap, d = res
        caps.append(cap)
        min_delay = min(min_delay, d)
    return caps, min_delay


class Lienzo:
    """Encaja frames individuales o en cuadrícula (1, 2 o 4 secciones) según cfg.AJUSTE."""

    def __init__(self, pantalla, modo, color_fondo):
        self.pantalla = pantalla
        self.modo = modo
        self.color_fondo = color_fondo
        self.buffer = None
        self._sublienzos = {}

    def _sublienzo(self, ancho, alto):
        clave = (ancho, alto)
        sub = self._sublienzos.get(clave)
        if sub is None:
            sub = Lienzo(clave, self.modo, self.color_fondo)
            self._sublienzos[clave] = sub
        return sub

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

    def componer_mosaico(self, frames):
        """Compone 1, 2 (lado a lado) o 3-4 (cuadrícula 2x2) frames en un solo lienzo."""
        n = len(frames)
        if n == 0:
            return None
        if n == 1:
            return self.ajustar(frames[0])

        ancho, alto = self.pantalla if self.pantalla else (
            frames[0].shape[1], frames[0].shape[0]
        )

        if self.buffer is None or self.buffer.shape[:2] != (alto, ancho):
            self.buffer = np.zeros((alto, ancho, 3), dtype=np.uint8)
        else:
            self.buffer.fill(0)

        if n == 2:
            # División vertical en 2 secciones (izquierda / derecha)
            w_izq = ancho // 2
            w_der = ancho - w_izq
            self.buffer[:, :w_izq] = self._sublienzo(w_izq, alto).ajustar(frames[0])
            self.buffer[:, w_izq:] = self._sublienzo(w_der, alto).ajustar(frames[1])
            return self.buffer

        # División en 4 secciones (cuadrícula 2x2) para 3 o 4 videos
        w_izq = ancho // 2
        w_der = ancho - w_izq
        h_sup = alto // 2
        h_inf = alto - h_sup

        regiones = [
            (0, 0, w_izq, h_sup),          # arriba-izquierda
            (w_izq, 0, w_der, h_sup),      # arriba-derecha
            (0, h_sup, w_izq, h_inf),      # abajo-izquierda
            (w_izq, h_sup, w_der, h_inf),  # abajo-derecha
        ]

        for frame, (x, y, rw, rh) in zip(frames[:4], regiones):
            self.buffer[y:y + rh, x:x + rw] = self._sublienzo(rw, rh).ajustar(frame)

        return self.buffer

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


def normalizar_fuentes(paths):
    """Convierte str o secuencia de rutas en una tupla limpia de hasta 4 rutas."""
    if not paths:
        return ()
    if isinstance(paths, str):
        return (paths,) if paths else ()
    return tuple(p for p in paths if p)[:4]


def solicitar_video(paths):
    """Solicita reproducir 1, 2 o 4 videos (o una imagen). Thread-safe."""
    global video_to_play, video_request
    fuentes = normalizar_fuentes(paths)
    if not fuentes:
        return
    with video_lock:
        video_to_play = fuentes
        video_request += 1


def _buscar_video(diccionario, clave):
    """Busca clave en diccionario soportando tanto int como str."""
    if clave in diccionario:
        return diccionario[clave]
    try:
        clave_int = int(clave)
        if clave_int in diccionario:
            return diccionario[clave_int]
    except (TypeError, ValueError):
        pass
    return diccionario.get(str(clave), "")


def elegir_video(sensor, value):
    sensor_clave = cfg.SENSORS.get(sensor) or {}
    global current_rotation
    global current_distance
    global current_rfid_stack

    if sensor != cts.ROTARY_BUTTON:
        current_rotation = None
    if sensor != cts.PRESENCE_SENSOR:
        current_distance = None
    if sensor != cts.RFID_TAG:
        current_rfid_stack = []

    match sensor:
        case cts.PUSH_BUTTON:
            return ""

        case cts.ROTARY_BUTTON:
            try:
                idx = int(value)
            except (TypeError, ValueError):
                return ""
            if idx == current_rotation:
                return ""
            current_rotation = idx
            return _buscar_video(sensor_clave.get("videos", {}), idx)

        case cts.MAGNETIC_PICK_UP_SENSOR:
            return _buscar_video(sensor_clave.get("videos", {}), value)

        case cts.AIR_BUTTON:
            return _buscar_video(sensor_clave.get("videos", {}), value)

        case cts.PRESENCE_SENSOR:
            try:
                idx = int(value)
            except (TypeError, ValueError):
                return ""
            if idx == current_distance:
                return ""
            current_distance = idx
            return _buscar_video(sensor_clave.get("videos", {}), idx)

        case cts.LIGHT_SENSOR:
            return ""

        case cts.RFID_TAG:
            rfids = list(value)
            if rfids == current_rfid_stack:
                return ()
            current_rfid_stack = rfids

            len_rfids = len(rfids)
            if len_rfids == 0:
                return ()

            videos_rfid = sensor_clave.get("videos", {})

            routes = []

            for tag in rfids:
                route = _buscar_video(videos_rfid, tag)
                if route:
                    routes.append(route)
            if len(routes) == 3:
                routes.pop(0)

            return routes

    return ""


def play_videos(stop_event, app_state):
    global current_video, current_rotation, current_distance, current_rfid_stack

    monitor = elegir_monitor(cfg.MONITOR)
    crear_ventana_kiosko(monitor)

    pantalla = geometria_destino(monitor)
    if pantalla:
        print(f"Ajustando video a {pantalla[0]}x{pantalla[1]} (modo '{cfg.AJUSTE}')")
    lienzo = Lienzo(pantalla, cfg.AJUSTE, cfg.COLOR_FONDO)

    caps = []
    imagen_actual = None
    inicio_imagen = None
    cache_imagenes = {}
    current_video = None
    current_request = -1
    delay = 40
    fallos_loop = 0
    frames = 0
    loop_fuentes = normalizar_fuentes(cfg.LOOP)

    try:
        while not stop_event.is_set():
            if app_state.get_updated():
                sensor, value = app_state.get_status()
                path = elegir_video(sensor, value)
                if path:
                    solicitar_video(path)
            elif app_state.get_updated_rfids():
                rfids = app_state.get_rfids()
                paths = elegir_video(cts.RFID_TAG, rfids)
                if paths:
                    solicitar_video(paths)

            with video_lock:
                deseado, request = video_to_play, video_request

            # Cambio de medio (imagen única o 1/2/4 videos)
            if deseado != current_video or request != current_request:
                if len(deseado) == 1 and es_imagen(deseado[0]):
                    ruta_img = deseado[0]
                    img = cache_imagenes.get(ruta_img)
                    if img is None:
                        img = cargar_imagen(ruta_img)
                        if img is not None:
                            cache_imagenes[ruta_img] = img

                    if img is None:
                        if deseado != loop_fuentes:
                            solicitar_video(cfg.LOOP)
                            continue
                        break

                    liberar_caps(caps)
                    caps = []

                    imagen_actual = img
                    inicio_imagen = time.monotonic()
                    current_video, current_request = deseado, request
                    delay = 30
                else:
                    nuevo = abrir_videos(deseado)
                    if nuevo is None:
                        if deseado != loop_fuentes:
                            solicitar_video(cfg.LOOP)
                            continue
                        print("No se pudo abrir el video de loop. Cerrando.")
                        break
                    liberar_caps(caps)
                    caps, delay = nuevo
                    imagen_actual = None
                    inicio_imagen = None
                    current_video, current_request = deseado, request
                    fallos_loop = 0

            # Obtención y composición del frame actual
            if imagen_actual is not None:
                if (time.monotonic() - inicio_imagen) >= TIEMPO_INACTIVIDAD_IMAGEN:
                    current_rotation = None
                    current_distance = None
                    solicitar_video(cfg.LOOP)
                    continue
                frame_salida = lienzo.ajustar(imagen_actual)
            else:
                es_loop = (current_video == loop_fuentes)
                frames_leidos = []
                alguno_termino = False

                for cap in caps:
                    ret, f = cap.read()
                    if not ret:
                        if not es_loop:
                            alguno_termino = True
                            break
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, f = cap.read()
                        if not ret:
                            alguno_termino = True
                            break
                    frames_leidos.append(f)

                if alguno_termino:
                    if not es_loop:
                        current_rfid_stack = []
                        solicitar_video(cfg.LOOP)
                        continue
                    fallos_loop += 1
                    if fallos_loop >= 3:
                        print("No se pueden leer frames del video de loop. Cerrando.")
                        break
                    continue

                fallos_loop = 0
                frame_salida = lienzo.componer_mosaico(frames_leidos)

            frames += 1
            if frames % 50 == 0:
                real = tamano_ventana()
                if real and real != lienzo.pantalla:
                    print(f"Pantalla cambió a {real[0]}x{real[1]}, reajustando.")
                    lienzo = Lienzo(real, cfg.AJUSTE, cfg.COLOR_FONDO)

            if frame_salida is not None:
                cv2.imshow(VENTANA, frame_salida)

            key = cv2.waitKey(delay) & 0xFF
            if key == ord("q") or key == 27:
                break
            if ventana_cerrada():
                break
    finally:
        liberar_caps(caps)
        cv2.destroyAllWindows()
        stop_event.set()
