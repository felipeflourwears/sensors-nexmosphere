"""Reproductor de video controlado por sensores Nexmosphere.

Escucha los mensajes de la API serial del controlador Xperience y reproduce el
video correspondiente en pantalla completa (modo kiosko).

La configuración de videos y sensores está en ModelVideos.py.

Uso:
    python main.py                # autodetecta el puerto
    python main.py /dev/ttyUSB0   # fuerza un puerto concreto
    python main.py COM3           # ídem en Windows

Salir: tecla 'q' o Escape.
"""

import os
import re
import subprocess
import sys
import threading
import time

# OpenCV dibuja la ventana con Qt. Bajo Wayland nativo, Qt no permite que la
# aplicación se coloque en un monitor concreto ni hace fullscreen de forma
# fiable (la ventana sale con tamaño incorrecto). Forzamos el backend X11, que
# funciona sobre XWayland. Tiene que hacerse ANTES de importar cv2.
# Se puede sobreescribir desde fuera: QT_QPA_PLATFORM=wayland python main.py
if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import cv2  # noqa: E402  (debe importarse después de fijar QT_QPA_PLATFORM)
import numpy as np  # noqa: E402
import serial  # noqa: E402
import serial.tools.list_ports  # noqa: E402

import ModelVideos as cfg  # noqa: E402

ES_WINDOWS = sys.platform.startswith("win")
ES_MAC = sys.platform == "darwin"

VENTANA = "Video"

# ---------- Mensajes de la API Nexmosphere ----------
# Par RFID: XR[PUxxx] / XR[PBxxx] seguido de X***A[1] / X***A[0]
RE_RFID = re.compile(r"^XR\[(PU|PB)(\d{1,3})\]$")
RE_XTALK = re.compile(r"^X(\d{3})([A-Z])\[(.*)\]$")

# ---------- Estado compartido entre hilos ----------
stop_event = threading.Event()
video_lock = threading.Lock()
video_to_play = cfg.LOOP
video_request = 0  # se incrementa en cada trigger para forzar el reinicio del video


def solicitar_video(path, motivo=""):
    """Pide reproducir un video. Thread-safe y siempre reinicia desde el frame 0."""
    global video_to_play, video_request
    with video_lock:
        video_to_play = path
        video_request += 1
    if motivo:
        print(f"   -> {motivo}: {os.path.basename(path)}")


def validar_videos():
    """Avisa de los videos configurados que no existen en disco."""
    faltantes = sorted({p for p in cfg.todos_los_videos() if not os.path.isfile(p)})
    for path in faltantes:
        print(f"ADVERTENCIA: no existe el video '{path}'")
    return faltantes


# ---------------------------------------------------------------------------
# Puerto serie
# ---------------------------------------------------------------------------
# Chips habituales de conversores USB-serial, en orden de preferencia. Funciona
# igual en Windows y Linux: pyserial rellena estos campos en ambos sistemas.
CHIPS_USB_SERIAL = (
    ("prolific", 0),
    ("pl2303", 0),
    ("ftdi", 1),
    ("ft232", 1),
    ("ch340", 1),
    ("ch341", 1),
    ("qinheng", 1),
    ("cp210", 1),
    ("silicon labs", 1),
    ("usb-serial", 2),
    ("usb serial", 2),
)


def listar_candidatos():
    """Puertos que parecen un conversor USB-serial, el más probable primero."""
    candidatos = []
    for port in serial.tools.list_ports.comports():
        texto = " ".join(
            filter(None, (port.description, port.manufacturer, port.product))
        ).lower()

        prioridad = None
        for chip, p in CHIPS_USB_SERIAL:
            if chip in texto:
                prioridad = p if prioridad is None else min(prioridad, p)
        if prioridad is None and port.vid is not None:
            prioridad = 3  # dispositivo USB sin chip reconocido: aún es candidato
        if prioridad is None:
            continue  # puerto integrado (ttyS0, LPT...): lo ignoramos

        candidatos.append((prioridad, port.device, port))

    candidatos.sort(key=lambda c: (c[0], c[1]))
    return [c[2] for c in candidatos]


def listar_puertos_disponibles():
    puertos = list(serial.tools.list_ports.comports())
    if not puertos:
        print("No hay ningún puerto serie visible en el sistema.")
        return
    print("Puertos disponibles:")
    for p in puertos:
        print(f"  {p.device}: {p.description}")


def ayuda_error_puerto(error):
    """Sugerencia según el sistema operativo y el tipo de error."""
    texto = str(error).lower()
    if ES_WINDOWS:
        if "access is denied" in texto or "permission" in texto:
            return (
                "El puerto está ocupado por otro programa. Cierra cualquier terminal\n"
                "serie (PuTTY, Arduino IDE, Nexmosphere tools) y vuelve a intentarlo."
            )
        return (
            "Revisa que el driver del cable esté instalado y que el puerto COM\n"
            "aparezca en el Administrador de dispositivos."
        )
    if "permission denied" in texto:
        grupo = "wheel" if ES_MAC else "dialout"
        return (
            f"Parece un problema de permisos. Añade tu usuario al grupo del puerto:\n"
            f"  sudo usermod -aG {grupo} $USER\n"
            f"y vuelve a iniciar sesión (o usa 'newgrp {grupo}' en esta terminal)."
        )
    if "busy" in texto or "in use" in texto:
        return "El puerto está ocupado por otro proceso. Ciérralo y reintenta."
    return "Revisa la conexión del cable y que el controlador esté alimentado."


def abrir_puerto(forzado=None):
    """Abre el puerto del controlador. Prueba cada candidato hasta que uno funcione."""
    if forzado:
        candidatos = [forzado]
    else:
        puertos = listar_candidatos()
        if not puertos:
            print("ERROR: No se encontró ningún conversor USB-serial conectado.")
            listar_puertos_disponibles()
            return None
        print("Puertos candidatos detectados:")
        for p in puertos:
            print(f"  {p.device} — {p.description}")
        candidatos = [p.device for p in puertos]

    ultimo_error = None
    for device in candidatos:
        try:
            ser = serial.Serial(device, cfg.BAUDRATE, timeout=1)
        except serial.SerialException as e:
            print(f"No se pudo abrir {device}: {e}")
            ultimo_error = e
            continue
        print(f"\nEscuchando en {device} a {cfg.BAUDRATE} baudios...\n")
        return ser

    if ultimo_error is not None:
        print(f"\n{ayuda_error_puerto(ultimo_error)}")
    return None


# ---------------------------------------------------------------------------
# Interpretación de los mensajes
# ---------------------------------------------------------------------------
def procesar_rfid_pickup(tag, estado):
    """Un tag fue levantado de la antena (XR[PUxxx])."""
    ahora = time.monotonic()
    anterior = estado.get("ultimo_pickup")

    if anterior is not None:
        tag_anterior, t_anterior = anterior
        combo = cfg.RFID_POR_COMBO.get((tag_anterior, tag))
        if combo and (ahora - t_anterior) <= cfg.RFID_COMBO_TIMEOUT:
            solicitar_video(combo, f"combo tag {tag_anterior:03d}+{tag:03d}")
            estado["ultimo_pickup"] = None
            return

    video = cfg.RFID_POR_TAG.get(tag)
    if video:
        solicitar_video(video, f"pick-up tag {tag:03d}")
    else:
        print(f"   pick-up tag {tag:03d} sin video asignado")
    estado["ultimo_pickup"] = (tag, ahora)


def procesar_rotary(valor):
    """X002B[Dr=1..20] -> video según el rango de la posición."""
    clave, _, bruto = valor.partition("=")
    if clave != cfg.ROTARY["clave"]:
        return
    try:
        posicion = int(bruto)
    except ValueError:
        print(f"   valor de rotary no numérico: {valor!r}")
        return
    for desde, hasta, video in cfg.ROTARY["rangos"]:
        if desde <= posicion <= hasta:
            solicitar_video(video, f"{cfg.ROTARY['nombre']} ({posicion})")
            return
    print(f"   posición de rotary sin video asignado: {posicion}")


def procesar_linea(linea, estado):
    """Interpreta una línea de la API Nexmosphere y dispara el video que toque."""
    # --- RFID: primer mensaje del par ---
    m = RE_RFID.match(linea)
    if m:
        print(">>", linea)
        evento, tag = m.group(1), int(m.group(2))
        estado["rfid_pendiente"] = True
        if evento == "PU":
            procesar_rfid_pickup(tag, estado)
        else:
            # Place-back: no dispara video, y NO debe romper la lógica de combos.
            print(f"   place-back tag {tag:03d}")
        return

    m = RE_XTALK.match(linea)
    if not m:
        return
    addr, canal, valor = m.group(1), m.group(2), m.group(3)

    # --- RFID: segundo mensaje del par (X***A[1] pick-up / X***A[0] place-back) ---
    # El manual garantiza que llega justo después de XR[PU/PBxxx]. Se consume aquí
    # para que no se confunda con los push buttons de esa misma dirección.
    if estado.get("rfid_pendiente") and canal == "A" and valor in ("0", "1"):
        print(f">> {linea}   (antena RFID en dirección {addr})")
        estado["rfid_pendiente"] = False
        return
    estado["rfid_pendiente"] = False

    clave = (addr, canal)
    print(">>", linea)

    if clave == tuple(cfg.ROTARY["direccion"]):
        procesar_rotary(valor)
        return

    sensor = cfg.SENSORES.get(clave)
    if sensor is None:
        return

    video = sensor["videos"].get(valor)
    if video:
        solicitar_video(video, sensor["nombre"])


def read_serial(ser):
    """Lee el puerto ya abierto y despacha cada mensaje."""
    estado = {"ultimo_pickup": None, "rfid_pendiente": False}
    try:
        while not stop_event.is_set():
            try:
                linea = ser.readline().decode(errors="ignore").strip()
            except serial.SerialException as e:
                print(f"Se perdió la conexión serial: {e}")
                break

            if linea:
                procesar_linea(linea, estado)
    finally:
        if ser.is_open:
            ser.close()
            print("Puerto serial cerrado.")
        # Sin sensor no tiene sentido seguir: cerramos la aplicación.
        stop_event.set()


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
        # unclutter no instalado: no es crítico, seguimos con el cursor visible.
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
    """Crea la ventana en fullscreen sin decoración, en el monitor indicado.

    WINDOW_GUI_NORMAL elimina la barra de herramientas, la barra de estado y el
    menú contextual de OpenCV. Al pasar a fullscreen el gestor de ventanas deja
    de dibujar la decoración, así que no hay botones de cerrar/minimizar/expandir.
    """
    cv2.namedWindow(VENTANA, cv2.WINDOW_GUI_NORMAL | cv2.WINDOW_NORMAL)

    if monitor is not None:
        destino_x, destino_y = monitor["x"], monitor["y"]
        ancho, alto = monitor["ancho"], monitor["alto"]
    else:
        destino_x, destino_y = cfg.MONITOR_X, cfg.MONITOR_Y
        ancho, alto = 1920, 1080

    # La ventana no existe para el gestor de ventanas hasta el primer imshow:
    # sin este frame previo, moveWindow se ignora y el kiosko acaba abriéndose
    # en el monitor primario. El frame debe tener la proporción del monitor,
    # porque Qt conserva la relación de aspecto de la imagen y getWindowImageRect
    # devuelve el área de la IMAGEN, no de la ventana.
    cv2.imshow(VENTANA, np.zeros((alto, ancho, 3), dtype=np.uint8))
    cv2.waitKey(1)

    if monitor is not None:
        cv2.resizeWindow(VENTANA, ancho, alto)

    # Colocamos la ventana dentro del monitor deseado ANTES del fullscreen: la
    # mayoría de gestores hacen fullscreen en el monitor que contiene la ventana.
    cv2.moveWindow(VENTANA, destino_x, destino_y)
    cv2.waitKey(1)

    cv2.setWindowProperty(VENTANA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    # Damos tiempo al gestor de ventanas a aplicar el cambio antes de medir.
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
        # El gestor de ventanas no hizo lo que pedimos: manda lo que hay en pantalla.
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


# Grosor (px) de la franja del video que se muestrea para COLOR_FONDO = "auto".
MUESTRA_BORDE = 8


class Lienzo:
    """Encaja cada frame en la pantalla según cfg.AJUSTE."""

    def __init__(self, pantalla, modo, color_fondo):
        self.pantalla = pantalla
        self.modo = modo
        self.color_fondo = color_fondo
        self.buffer = None

    def ajustar(self, frame):
        if self.pantalla is None:
            return frame  # sin tamaño conocido, que OpenCV haga lo que pueda

        ancho, alto = self.pantalla
        h, w = frame.shape[:2]
        if (w, h) == (ancho, alto):
            return frame  # coincidencia exacta: nada que hacer

        if self.modo == "estirar":
            # Deformamos nosotros hasta el tamaño exacto de la ventana. No vale
            # dejárselo a OpenCV: Qt conserva la proporción y añadiría barras.
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
        # El recorte es una vista de numpy, no copia datos.
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

        if x0 > 0:  # barras a los lados
            izq, der = self._colores_laterales(escalado)
            self.buffer[:, :x0] = izq
            self.buffer[:, x0 + nuevo_w:] = der
        if y0 > 0:  # barras arriba y abajo
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


def play_videos():
    monitor = elegir_monitor(cfg.MONITOR)
    crear_ventana_kiosko(monitor)

    pantalla = geometria_destino(monitor)
    if pantalla:
        print(f"Ajustando video a {pantalla[0]}x{pantalla[1]} (modo '{cfg.AJUSTE}')")
    lienzo = Lienzo(pantalla, cfg.AJUSTE, cfg.COLOR_FONDO)

    cap = None
    current_video = None
    current_request = -1
    delay = 40
    fallos_loop = 0
    frames = 0

    try:
        while not stop_event.is_set():
            with video_lock:
                deseado, request = video_to_play, video_request

            if cap is None or deseado != current_video or request != current_request:
                nuevo = abrir_video(deseado)
                if nuevo is None:
                    if deseado != cfg.LOOP:
                        solicitar_video(cfg.LOOP, "fallback")
                        continue
                    print("No se pudo abrir el video de loop. Cerrando.")
                    break
                if cap is not None:
                    cap.release()
                cap, delay = nuevo
                current_video, current_request = deseado, request
                fallos_loop = 0

            ret, frame = cap.read()
            if not ret:
                if current_video != cfg.LOOP:
                    # El video del trigger terminó: volvemos al loop.
                    solicitar_video(cfg.LOOP)
                    continue
                # El loop terminó: rebobinamos.
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    fallos_loop += 1
                    if fallos_loop >= 3:
                        print("No se pueden leer frames del video de loop. Cerrando.")
                        break
                    continue
                fallos_loop = 0

            # El gestor de ventanas puede tardar en aplicar el fullscreen, y el
            # monitor puede cambiar en caliente. Re-medimos de vez en cuando.
            frames += 1
            if frames % 50 == 0:
                real = tamano_ventana()
                if real and real != lienzo.pantalla:
                    print(f"Pantalla cambió a {real[0]}x{real[1]}, reajustando.")
                    lienzo = Lienzo(real, cfg.AJUSTE, cfg.COLOR_FONDO)

            cv2.imshow(VENTANA, lienzo.ajustar(frame))

            key = cv2.waitKey(delay) & 0xFF
            if key == ord("q") or key == 27:  # q o Escape
                break
            if ventana_cerrada():
                break
    finally:
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        stop_event.set()


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    forzado = sys.argv[1] if len(sys.argv) > 1 else cfg.PUERTO_FIJO

    validar_videos()

    ser = abrir_puerto(forzado)
    if ser is None:
        sys.exit(1)

    cursor = ocultar_cursor()

    serial_thread = threading.Thread(target=read_serial, args=(ser,), daemon=True)
    video_thread = threading.Thread(target=play_videos, daemon=True)

    serial_thread.start()
    video_thread.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nCerrando programa (Ctrl+C)...")
        stop_event.set()

    # Dar tiempo a los hilos para cerrar limpiamente
    serial_thread.join(timeout=3)
    video_thread.join(timeout=3)
    if cursor is not None:
        cursor.terminate()
    print("Programa cerrado.")
