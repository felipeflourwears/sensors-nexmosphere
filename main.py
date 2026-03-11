import cv2
import serial
import serial.tools.list_ports
import threading
import sys
import time

# ---------- Configuración serial ----------
baudrate = 115200

# ---------- Videos ----------
video_loop = "lala/loop.mp4"
video_rfid_1 = "lala/rfid-1.mp4"
video_rfid_2 = "lala/rfid-2.mp4"
video_rfid_1_2 = "lala/rfid-1-2.mp4"
video_rfid_2_1 = "lala/rfid-1-2.mp4"
video_magnetic_sensor = "lala/magnetic-sensor.mp4"
video_push_button1 = "lala/push-button1.mp4"
video_push_button2 = "lala/push-button2.mp4"
video_close = "videos/close.mp4"
video_far = "videos/far.mp4"
video_right = "videos/right.mp4"
video_left = "videos/left.mp4"
video_presence_sensor = "videos/presence_sensor.mp4"

# Evento para detener hilos
stop_event = threading.Event()

# Variable compartida para indicar qué video reproducir
video_to_play = video_loop
video_lock = threading.Lock()


def find_prolific_port():
    """Detecta automáticamente el puerto COM con 'Prolific' en la descripción."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = (port.description or "").lower()
        mfr  = (port.manufacturer or "").lower()
        if "prolific" in desc or "prolific" in mfr:
            print(f"Puerto Prolific encontrado: {port.device} — {port.description}")
            return port.device
    return None


def read_serial(puerto, baudrate):
    global video_to_play
    try:
        ser = serial.Serial(puerto, baudrate, timeout=1)
        print(f"Escuchando en {puerto} a {baudrate} baudios...\n")
        previous_line = None
        while not stop_event.is_set():
            try:
                linea = ser.readline().decode(errors='ignore').strip()
            except serial.SerialException:
                break

            if not linea:
                continue

            if linea.startswith("XR"):
                print(">>", linea)
                with video_lock:
                    if previous_line == "XR[PU001]" and linea == "XR[PU002]":
                        print("Coca-Sprite")
                        video_to_play = video_rfid_1_2
                    elif previous_line == "XR[PU002]" and linea == "XR[PU001]":
                        print("Sprite-Coca")
                        video_to_play = video_rfid_2_1
                    elif linea == "XR[PU001]":
                        video_to_play = video_rfid_1
                    elif linea == "XR[PU002]":
                        video_to_play = video_rfid_2
                previous_line = linea

            if linea.startswith("X003A") and not linea.startswith("X003A[4]"):
                if linea == "X003A[3]":
                    video_to_play = video_magnetic_sensor

            if linea.startswith("X001A"):
                if linea == "X001A[17]":
                    video_to_play = video_push_button1
                elif linea == "X001A[3]":
                    video_to_play = video_push_button2
                print(">>", linea)

            if linea.startswith("X002B"):
                print(">>", linea)
                print("Rotary Button")
                try:
                    rotary_button = int(linea.split("Dr=")[1].rstrip("]"))
                    if 1 <= rotary_button <= 10:
                        video_to_play = video_left
                    elif 11 <= rotary_button <= 20:
                        video_to_play = video_right
                except (IndexError, ValueError):
                    pass

            if linea.startswith("X004B"):
                if linea == "X004B[Bs=FAR]":
                    video_to_play = video_far
                elif linea == "X004B[Bs=NEAR]":
                    video_to_play = video_close

            if linea.startswith("X005B"):
                if linea == "X005B[Dz=AB]":
                    video_to_play = video_presence_sensor

    except serial.SerialException as e:
        print(f"Error al abrir el puerto: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Puerto serial cerrado.")


def play_videos():
    global video_to_play
    cap = cv2.VideoCapture(video_loop)
    if not cap.isOpened():
        print("Error al abrir el video")
        stop_event.set()
        return

    # WINDOW_GUI_NORMAL elimina los controles de la ventana que causan la "cruz"
    cv2.namedWindow("Video", cv2.WINDOW_GUI_NORMAL)
    cv2.setWindowProperty("Video", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    current_video = video_loop

    while not stop_event.is_set():
        with video_lock:
            if video_to_play != current_video:
                current_video = video_to_play
                cap.release()
                cap = cv2.VideoCapture(current_video)

        ret, frame = cap.read()
        if not ret:
            if current_video != video_loop:
                with video_lock:
                    video_to_play = video_loop
                current_video = video_loop
                cap.release()
                cap = cv2.VideoCapture(video_loop)
                continue
            else:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

        cv2.imshow("Video", frame)

        key = cv2.waitKey(25) & 0xFF
        if key == ord('q') or key == 27:  # q o Escape
            stop_event.set()
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    puerto = find_prolific_port()
    if puerto is None:
        print("ERROR: No se encontró ningún puerto COM con 'Prolific' en la descripción.")
        print("Puertos disponibles:")
        for p in serial.tools.list_ports.comports():
            print(f"  {p.device}: {p.description}")
        sys.exit(1)

    serial_thread = threading.Thread(target=read_serial, args=(puerto, baudrate), daemon=True)
    video_thread  = threading.Thread(target=play_videos, daemon=True)

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
    print("Programa cerrado.")
