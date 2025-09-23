import cv2

# Variable que controla el video
play_video = 0  # Cambia a 0 para no reproducir

# Rutas de tus videos
video_coca = "videos/cocacola.mp4"
video_sprite = "videos/sprite.mp4"

# Elegir video según la variable
video_path = video1_path if play_video == 1 else video0_path

# Abrir el video
cap = cv2.VideoCapture(video_path)
if not cap.isOpened():
    print("Error al abrir el video")
    exit()

# Crear ventana sin bordes en modo fullscreen
cv2.namedWindow("Video", cv2.WINDOW_NORMAL)
cv2.setWindowProperty("Video", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    cv2.imshow("Video", frame)
    
    # Salir si se presiona 'q'
    if cv2.waitKey(25) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()