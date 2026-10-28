import cv2
import serial
import threading

# ---------- VARS ----------
PORT = "COM3"
PORT = "/dev/ttyUSB0"
BAUDRATE = 115200
PATH="videos/"

# ---------- Videos ---------- Examples
video_loop = PATH + "loop.mp4"
video_rfid_1 = PATH + "rfid-1.mp4"
video_rfid_2 = PATH + "rfid-2.mp4"
video_rfid_1_2 = PATH + "rfid-1-2.mp4"
video_rfid_2_1 = PATH + "rfid-2-1.mp4"
video_magnetic_sensor = PATH + "magnetic-sensor.mp4"
video_push_button1 = PATH + "push-button1.mp4"
video_push_button2 = PATH + "push-button2.mp4"
video_close = PATH + "close.mp4"
video_far = PATH + "far.mp4"
video_right = PATH + "right.mp4"
video_left = PATH + "left.mp4"
video_presence_sensor = PATH + "presence_sensor.mp4"


stop_event = threading.Event()
video_to_play = video_loop
video_lock = threading.Lock()



def read_serial(puerto, baudrate):
    try:
        with serial.Serial(puerto, baudrate, timeout=1) as ser:
            print(f"Escuchando en {puerto} a {baudrate} baudios...\n")

            while not stop_event.is_set():
                if ser.in_waiting > 0:
                    linea = ser.readline().decode(
                        "utf-8", errors="ignore"
                    ).strip()

                    if linea:
                        print(f">> {linea}", flush=True)

    except serial.SerialException as e:
        print(f"Error comunication Serial: {e}")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        print("Final Reading...")


def play_videos():
    global video_to_play

    window_name = "Video"
    current_video = video_loop

    screen_width = 1920
    screen_height = 1080

    cap = cv2.VideoCapture(current_video)

    if not cap.isOpened():
        print("Error to open the main video")
        stop_event.set()
        return

    # No controls
    cv2.namedWindow(
        window_name,
        cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL
    )

    cv2.resizeWindow(
        window_name,
        screen_width,
        screen_height
    )

    fullscreen_enabled = False

    try:
        while not stop_event.is_set():

            ret, frame = cap.read()

            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            frame = cv2.resize(
                frame,
                (screen_width, screen_height),
                interpolation=cv2.INTER_LINEAR
            )

            cv2.imshow(window_name, frame)

            if not fullscreen_enabled:
                cv2.setWindowProperty(
                    window_name,
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN
                )
                fullscreen_enabled = True

            # Salir con Q
            if cv2.waitKey(25) & 0xFF == ord("q"):
                stop_event.set()
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        stop_event.set()


if __name__ == "__main__":
    serial_thread = threading.Thread(target=read_serial, args=(PORT, BAUDRATE))
    video_thread = threading.Thread(target=play_videos)

    serial_thread.start()
    video_thread.start()

    serial_thread.join()
    video_thread.join()
