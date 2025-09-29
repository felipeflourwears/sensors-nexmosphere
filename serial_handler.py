# serial_handler.py
import serial
import threading

class SerialHandler:
    def __init__(self, puerto, baudrate, callback):
        self.puerto = puerto
        self.baudrate = baudrate
        self.callback = callback
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.read_serial, daemon=True)
        self.thread.start()

    def read_serial(self):
        try:
            ser = serial.Serial(self.puerto, self.baudrate, timeout=1)
            print(f"Escuchando en {self.puerto} a {self.baudrate} baudios...")
            previous_line = None
            while not self.stop_event.is_set():
                if ser.in_waiting > 0:
                    linea = ser.readline().decode(errors='ignore').strip()
                    if linea:
                        # callback recibe (linea, previous_line)
                        self.callback(linea, previous_line)
                        previous_line = linea
        except serial.SerialException as e:
            print(f"[SerialHandler] Error al abrir el puerto: {e}")
        finally:
            try:
                if 'ser' in locals() and ser.is_open:
                    ser.close()
                    print("[SerialHandler] Puerto cerrado.")
            except Exception:
                pass

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
