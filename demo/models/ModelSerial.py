
import sys
import serial

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

import demo.models.ModelSignals as modelSignals

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

BAUDRATE = 115200
FIXED_PORT = None


def list_candidates():
    """Puertos que parecen un conversor USB-serial, el más probable primero."""
    candidates = []
    for port in serial.tools.list_ports.comports():
        text = " ".join(
            filter(None, (port.description, port.manufacturer, port.product))
        ).lower()

        priority = None
        for chip, p in CHIPS_USB_SERIAL:
            if chip in text:
                priority = p if priority is None else min(priority, p)
        if priority is None and port.vid is not None:
            priority = 3  # dispositivo USB sin chip reconocido: aún es candidato
        if priority is None:
            continue  # puerto integrado (ttyS0, LPT...): lo ignoramos

        candidates.append((priority, port.device, port))

    candidates.sort(key=lambda c: (c[0], c[1]))
    return [c[2] for c in candidates]


def list_available_ports():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No hay ningún puerto serie visible en el sistema.")
        return
    print("Puertos disponibles:")
    for p in ports:
        print(f"  {p.device}: {p.description}")


def help_error_port(error):
    """Sugerencia según el sistema operativo y el tipo de error."""
    text = str(error).lower()
    if IS_WINDOWS:
        if "access is denied" in text or "permission" in text:
            return (
                "El puerto está ocupado por otro programa. Cierra cualquier terminal\n"
                "serie (PuTTY, Arduino IDE, Nexmosphere tools) y vuelve a intentarlo."
            )
        return (
            "Revisa que el driver del cable esté instalado y que el puerto COM\n"
            "aparezca en el Administrador de dispositivos."
        )
    if "permission denied" in text:
        grupo = "wheel" if IS_MAC else "dialout"
        return (
            f"Parece un problema de permisos. Añade tu usuario al grupo del puerto:\n"
            f"  sudo usermod -aG {grupo} $USER\n"
            f"y vuelve a iniciar sesión (o usa 'newgrp {grupo}' en esta terminal)."
        )
    if "busy" in text or "in use" in text:
        return "El puerto está ocupado por otro proceso. Ciérralo y reintenta."
    return "Revisa la conexión del cable y que el controlador esté alimentado."


def open_port(forced=None):
    """Abre el puerto del controlador. Prueba cada candidato hasta que uno funcione."""
    if forced:
        candidates = [forced]
    else:
        ports = list_candidates()
        if not ports:
            print("ERROR: No se encontró ningún conversor USB-serial conectado.")
            list_available_ports()
            return None
        print("Puertos candidatos detectados:")
        for p in ports:
            print(f"  {p.device} — {p.description}")
        candidates = [p.device for p in ports]

    last_error = None
    for device in candidates:
        try:
            ser = serial.Serial(device, BAUDRATE, timeout=1)
        except serial.SerialException as e:
            print(f"No se pudo abrir {device}: {e}")
            last_error = e
            continue
        print(f"\nEscuchando en {device} a {BAUDRATE} baudios...\n")
        return ser

    if last_error is not None:
        print(f"\n{help_error_port(last_error)}")
    return None


def read_serial(ser, stop_event, app_state):
    state = {"ultimo_pickup": None, "rfid_pendiente": False}
    try:
        while not stop_event.is_set():
            try:
                line = ser.readline().decode(errors="ignore").strip()
            except serial.SerialException as e:
                print(f"Lost serial connection: {e}")
                break
            if line:
                modelSignals.process_line(line, state, app_state)
    finally:
        if ser.is_open:
            ser.close()
            print("Serial port closed...")

def initiate():
    print("Initializing serial handler...")
    forced = sys.argv[1] if len(sys.argv) > 1 else FIXED_PORT
    
    ser = open_port(forced)
    if ser is None:
        sys.exit(1)
    return ser
