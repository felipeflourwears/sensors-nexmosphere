"""
Reproductor de video controlado por sensores Nexmosphere.

Escucha los mensajes de la API serial del controlador Xperience y reproduce el
video correspondiente en pantalla completa (modo kiosko)

Uso:
    python main.py                # autodetecta el puerto
    python main.py /dev/ttyUSB0   # fuerza un puerto concreto
    python main.py COM3           # ídem en Windows

Salir: tecla 'q' o Escape.
"""

import os
import sys
import threading
import time


if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import demo.models.ModelVideos as modelVideos  # noqa: E402
import demo.models.ModelSerial as modelSerial

# ---------- Estado compartido entre hilos ----------
stop_event = threading.Event()
video_lock = threading.Lock()
video_to_play = modelVideos.LOOP
video_request = 0  # se incrementa en cada trigger para forzar el reinicio del video


def validar_videos():
    """Avisa de los videos configurados que no existen en disco."""
    faltantes = sorted({p for p in modelVideos.todos_los_videos() if not os.path.isfile(p)})
    for path in faltantes:
        print(f"ADVERTENCIA: no existe el video '{path}'")
    return faltantes


def central():

    faltantes = validar_videos()
    if faltantes:
        print(f"Faltan los siguientes videos: {faltantes}")
        return
    
    ser = modelSerial.initiate()
    serial_thread = threading.Thread(target=modelSerial.read_serial, args=(ser, stop_event,), daemon=True)
    #video_thread = threading.Thread(target=play_videos, daemon=True)

    serial_thread.start()
    #video_thread.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nCerrando programa (Ctrl+C)...")
        stop_event.set()

    # Dar tiempo a los hilos para cerrar limpiamente
    serial_thread.join(timeout=3)
    #video_thread.join(timeout=3)
    #if cursor is not None:
    #    cursor.terminate()
    print("Programa cerrado.")