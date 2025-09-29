# controller.py
import time
import threading
from serial_handler import SerialHandler
from xibo_client import XiboPlayerClient

# ----------------- CONFIG -----------------
PUERTO = "COM3"
BAUDRATE = 115200

# Ventana máxima (segundos) para que dos PU consecutivos sean considerada "secuencia"
SEQUENCE_WINDOW_SECONDS = 3.0

# Auto-return: si True, después de N segundos se envía TRG_LOOP para volver al loop.
AUTO_RETURN_TO_LOOP = True
RETURN_TO_LOOP_SECONDS = 8.0

# Trigger codes que debes crear en Xibo (Actions en LAY_LOOP)
TRG_RFID1     = "TRG_RFID1"
TRG_RFID2     = "TRG_RFID2"
TRG_RFID1_2   = "TRG_RFID1_2"
TRG_RFID2_1   = "TRG_RFID2_1"
TRG_LOOP      = "TRG_LOOP"
# ------------------------------------------

player = XiboPlayerClient(host='127.0.0.1', port=9696)

# Estado para detectar secuencias
_last_pu = None          # guarda "XR[PU001]" o "XR[PU002]" o None
_last_pu_time = 0.0
_return_timer = None
_lock = threading.Lock()


def _cancel_return_timer():
    global _return_timer
    if _return_timer is not None:
        try:
            _return_timer.cancel()
        except Exception:
            pass
        _return_timer = None


def _start_return_timer():
    global _return_timer
    _cancel_return_timer()
    if AUTO_RETURN_TO_LOOP:
        _return_timer = threading.Timer(RETURN_TO_LOOP_SECONDS, lambda: player.trigger(TRG_LOOP))
        _return_timer.daemon = True
        _return_timer.start()


def _send_trigger(trigger_code):
    """Envía trigger al Xibo Player y maneja retorno automático."""
    ok, resp = player.trigger(trigger_code)
    if not ok:
        print(f"[controller] Falló trigger {trigger_code}: {resp}")
    else:
        print(f"[controller] Trigger enviado: {trigger_code}")
    # iniciar timer para volver al loop (si está configurado)
    _start_return_timer()


def handle_serial(linea, previous_line):
    """
    Callback para SerialHandler.
    Solo procesa eventos 'PU' (levantado): XR[PU001], XR[PU002]
    Detecta secuencias (1->2 o 2->1) si ocurren dentro de SEQUENCE_WINDOW_SECONDS.
    """
    global _last_pu, _last_pu_time

    if not linea:
        return

    linea = linea.strip()
    now = time.time()

    # Filtrar solo PU (levantado). Usamos startswith para mayor tolerancia.
    if linea.startswith("XR[PU001]"):
        current = "XR[PU001]"
    elif linea.startswith("XR[PU002]"):
        current = "XR[PU002]"
    else:
        # Ignoramos otros eventos (según tu indicación)
        return

    with _lock:
        # ¿hay una PU previa dentro de la ventana?
        if _last_pu is not None and (now - _last_pu_time) <= SEQUENCE_WINDOW_SECONDS:
            # Detectar orden:
            if _last_pu == "XR[PU001]" and current == "XR[PU002]":
                # 1 -> 2
                print("[controller] Secuencia detectada: PU001 then PU002 -> TRG_RFID1_2")
                _send_trigger(TRG_RFID1_2)
                # resetear estado secuencia
                _last_pu = None
                _last_pu_time = 0.0
                return
            elif _last_pu == "XR[PU002]" and current == "XR[PU001]":
                # 2 -> 1
                print("[controller] Secuencia detectada: PU002 then PU001 -> TRG_RFID2_1")
                _send_trigger(TRG_RFID2_1)
                _last_pu = None
                _last_pu_time = 0.0
                return
            # si llegó aquí, la previa no forma secuencia relevante -> proceder como single

        # Si no hay secuencia válida, tratar como evento individual
        if current == "XR[PU001]":
            print("[controller] Evento individual: PU001 -> TRG_RFID1")
            _send_trigger(TRG_RFID1)
        elif current == "XR[PU002]":
            print("[controller] Evento individual: PU002 -> TRG_RFID2")
            _send_trigger(TRG_RFID2)

        # Guardar como posible inicio de secuencia
        _last_pu = current
        _last_pu_time = now


if __name__ == "__main__":
    serial_reader = SerialHandler(PUERTO, BAUDRATE, handle_serial)
    serial_reader.start()
    print("[controller] Iniciado. Escuchando serial en", PUERTO)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[controller] Saliendo...")
        _cancel_return_timer()
        serial_reader.stop()
