#!/usr/bin/env python3
import time
import serial
import models.ModelSerial as model_serial

def main_cycle(stop_event, app_state, baud=9600, reset_wait=2.5, idle_sleep=0.05):
    print("Entering microcontroller cycle...")
    port = model_serial.get_port("CH340")
    if not port:
        print("Could not find microcontroller!")
        return

    ser = None
    try:
        ser = serial.Serial(port, baud, timeout=0.2)
        time.sleep(reset_wait)
        ser.reset_input_buffer()

        while not stop_event.is_set():
            if not app_state.get_updated_micro():
                time.sleep(idle_sleep)
                continue

            message = app_state.get_status_micro()
            ser.write((message + "\n").encode("utf-8"))
            ser.flush()

            time.sleep(0.05)
            response = ser.read(500).decode(errors="replace").strip()
            print(response or "(sin respuesta)")

    except serial.SerialException as e:
        print(f"Serial error on {port}: {e}")
        stop_event.set()
    finally:
        if ser and ser.is_open:
            ser.close()
