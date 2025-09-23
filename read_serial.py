import serial

# Configuración del puerto serial
puerto = "COM3"       # En Windows sería COM3, COM4, etc.
baudrate = 115200     # Velocidad de transmisión

try:
    ser = serial.Serial(puerto, baudrate, timeout=1)
    print(f" Escuchando en {puerto} a {baudrate} baudios...\n")

    while True:
        if ser.in_waiting > 0:  # Si hay datos en el buffer
            linea = ser.readline().decode(errors='ignore').strip()
            if linea:
            #if linea.startswith("XR"):
                print(">>", linea)
            

except serial.SerialException as e:
    print(f"Error al abrir el puerto: {e}")
except KeyboardInterrupt:
    print("\nLectura detenida por el usuario.")
finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("Puerto cerrado.")
