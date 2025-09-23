import cv2
import serial
import threading

# ---------- Configuración serial ----------
puerto = "COM3"
baudrate = 115200

# ---------- Videos ----------
video_loop = "videos/loop.mp4"
video_coca = "videos/cocacola.mp4"
video_sprite = "videos/sprite.mp4"
video_coca_sprite = "videos/coca-sprite.mp4"
video_sprite_coca = "videos/sprite-coca.mp4"
video_iphone = "videos/iphone17promax.mp4"
video_fanta = "videos/fanta.mp4"
video_delvalle = "videos/delvalle.mp4"
video_close = "videos/close.mp4"
video_far = "videos/far.mp4"
video_right = "videos/right.mp4"
video_left = "videos/left.mp4"

# Evento para detener hilos
stop_event = threading.Event()

# Variable compartida para indicar qué video reproducir
video_to_play = video_loop
video_lock = threading.Lock()


def read_serial(puerto, baudrate):
    global video_to_play
    try:
        ser = serial.Serial(puerto, baudrate, timeout=1)
        print(f"Escuchando en {puerto} a {baudrate} baudios...\n")
        previous_line = None
        while not stop_event.is_set():
            if ser.in_waiting > 0:
                linea = ser.readline().decode(errors='ignore').strip()
                if linea.startswith("XR"):
                    print(">>", linea)
                    with video_lock:
                        # Detectar transición PU001 → PU002
                        if previous_line == "XR[PU001]" and linea == "XR[PU002]":
                            print("Coca-Sprite")
                            video_to_play = video_coca_sprite
                        # Detectar transición PU002 → PU001
                        elif previous_line == "XR[PU002]" and linea == "XR[PU001]":
                            print("Sprite-Coca")
                            video_to_play = video_sprite_coca
                        # Video normal individual
                        elif linea == "XR[PU001]":
                            video_to_play = video_coca
                        elif linea == "XR[PU002]":
                            video_to_play = video_sprite
                    previous_line = linea
                if linea.startswith("X003A") and not linea.startswith("X003A[4]"):
                    if linea == "X003A[3]":
                        video_to_play = video_iphone
                if linea.startswith("X001A"):
                    if linea == "X001A[17]":
                        video_to_play = video_fanta
                    elif linea == "X001A[3]":
                        video_to_play = video_delvalle
                    print(">>", linea)
                if linea.startswith("X002B"):
                    print(">>", linea)
                    print("Rotary Button")
                if linea.startswith("X004B"):   
                    if linea == "X004B[Bs=FAR]":
                        video_to_play = video_far
                    elif linea == "X004B[Bs=NEAR]":
                        video_to_play = video_close
                if linea.startswith("X002B"):
                    rotary_button = int(linea.split("Dr=")[1].rstrip("]")) 
                    if 1 <= rotary_button <= 10:
                        video_to_play = video_left
                    elif 11 <= rotary_button <= 20:
                        video_to_play = video_right             


    except serial.SerialException as e:
        print(f"Error al abrir el puerto: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Puerto cerrado.")


def play_videos():
    global video_to_play
    cap = cv2.VideoCapture(video_loop)
    if not cap.isOpened():
        print("Error al abrir el video")
        return

    cv2.namedWindow("Video", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Video", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    current_video = video_loop

    while not stop_event.is_set():
        with video_lock:
            # Si cambió el video a reproducir, reiniciar captura
            if video_to_play != current_video:
                current_video = video_to_play
                cap.release()
                cap = cv2.VideoCapture(current_video)

        ret, frame = cap.read()
        if not ret:
            # Si es video especial (Coca/Sprite), volver al loop
            if current_video != video_loop:
                with video_lock:
                    video_to_play = video_loop
                current_video = video_loop
                cap.release()
                cap = cv2.VideoCapture(video_loop)
                continue
            else:
                # Loop del video principal
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

        cv2.imshow("Video", frame)

        if cv2.waitKey(25) & 0xFF == ord('q'):
            stop_event.set()
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    serial_thread = threading.Thread(target=read_serial, args=(puerto, baudrate))
    video_thread = threading.Thread(target=play_videos)

    serial_thread.start()
    video_thread.start()

    serial_thread.join()
    video_thread.join()
