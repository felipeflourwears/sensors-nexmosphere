import serial

# Configuración del puerto serial
#PORT = "COM3"       # En Windows sería COM3, COM4, etc.
PORT = "/dev/ttyUSB0"
baudrate = 115200     # Velocidad de transmisión

try:
    ser = serial.Serial(PORT, baudrate, timeout=1)
    print(f"Listening {PORT} at {baudrate} bauds...\n")

    while True:
        if ser.in_waiting > 0:
            linea = ser.readline().decode(errors='ignore').strip()
            if linea:
            #if linea.startswith("XR"):
                print(">>", linea)
            

except serial.SerialException as e:
    print(f"Error to open port {e}")
except KeyboardInterrupt:
    print("Exiting...")
finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("Port closed.")
