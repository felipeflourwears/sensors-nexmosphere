"""
Reproductor de video controlado por sensores Nexmosphere.

Escucha los mensajes de la API serial del controlador Xperience y reproduce el
video correspondiente en pantalla completa (modo kiosko)

Salir: tecla 'q' o Escape.
"""

import os
import sys
import threading
import time

if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import models.ModelVideos as modelVideos
import models.ModelSerial as modelSerial
import models.ModelDisplay as modelDisplay
import models.ModelArduino as modelArduino

import AppState

# ---------- Estado compartido entre hilos ----------
stop_event = threading.Event()
video_lock = threading.Lock()
video_to_play = modelVideos.LOOP

def validate_videos():
    """Avisa de los videos configurados que no existen en disco."""
    missing = sorted({p for p in modelVideos.all_media_files() if not os.path.isfile(p)})
    for path in missing:
        print(f"ADVERTENCIA: no existe el archivo '{path}'")
    return missing

def central():
    missing = validate_videos()
    if missing:
        print(f"Faltan los siguientes archivos: {missing}")
        return

    app_state = AppState.AppState()

    ser = modelSerial.initiate()
    cursor = modelDisplay.hide_cursor()

    serial_thread = threading.Thread(target=modelSerial.read_serial, args=(ser, stop_event, app_state,), daemon=True)
    video_thread = threading.Thread(target=modelDisplay.play_videos, args=(stop_event, app_state,), daemon=True)
    arduino_thread = threading.Thread(target=modelArduino.main_cycle, args=(stop_event, app_state,), daemon=True)

    serial_thread.start()
    video_thread.start()
    arduino_thread.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nCerrando programa (Ctrl+C)...")
        stop_event.set()

    serial_thread.join(timeout=3)
    video_thread.join(timeout=3)
    if cursor is not None:
        cursor.terminate()
    print("Programa cerrado.")

if __name__ == "__main__":
    central()
