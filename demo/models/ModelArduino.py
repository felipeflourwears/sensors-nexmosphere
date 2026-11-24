#!/usr/bin/env python3
import argparse
import sys
import time
import serial

import models.ModelSerial as model_serial

PORT = None

def main_cycle(stop_event, app_state):
    global PORT
    print ("Entering arduino cycle...")
    while not stop_event.is_set():
        if not app_state.get_updated_arduino():
            continue

        message = app_state.get_status_arduino()

        if not PORT:
            port = model_serial.get_port("CH340")
            if not port:
                stop_event.set()
                print("Could not find arduino!")
                return
            PORT = port

        ap = argparse.ArgumentParser(description="Envía un mensaje al Arduino listener")
        ap.add_argument("message", nargs="?", default=message, help="mensaje a enviar (default: hola)")
        ap.add_argument("--port", default=PORT)
        ap.add_argument("--baud", type=int, default=9600)
        ap.add_argument("--wait", type=float, default=2.5,
                        help="segundos de espera (reinicio de la placa y parpadeo)")
        args = ap.parse_args()

        try:
            s = serial.Serial(args.port, args.baud, timeout=1)
        except serial.SerialException as e:
            sys.exit(f"No pude abrir {args.port}: {e}\n(¿Monitor Serie abierto o placa desconectada?)")
            stop_event.set()

        with s:
            time.sleep(args.wait)            # la placa se reinicia al abrir el puerto
            s.reset_input_buffer()
            s.write((args.message + "\n").encode())
            time.sleep(args.wait)
            print(s.read(500).decode(errors="replace").strip() or "(sin respuesta)")
