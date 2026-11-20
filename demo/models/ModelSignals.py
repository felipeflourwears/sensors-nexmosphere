import re
import constants as cts

RE_RFID = re.compile(r"^XR\[(PU|PB)(\d{1,3})\]$")
RE_XTALK = re.compile(r"^X(\d{3})([A-Z])\[(.*)\]$")

# ---------------------------------------------------------------------------
# Interpretación de los mensajes
# ---------------------------------------------------------------------------

def process_line(line, app_state):

    # --- RFID: primer mensaje del par ---
    m = RE_RFID.match(line)
    if m:
        evento, tag = m.group(1), int(m.group(2))
        if evento == "PU":
            print(f"LEVANTADO {tag}")
            app_state.push_rfid(tag)
        else:
            print(f"COLOCADO {tag}")
            app_state.pop_rfid(tag)
        return

    m = RE_XTALK.match(line)
    if not m:
        return
    addr, canal, valor = m.group(1), m.group(2), m.group(3)

    match addr:
        case "001":
            if valor == "0":
                return
            app_state.set_status(cts.PUSH_BUTTON, int(valor))
            print("Push buttons")
        case "002":
            converted_valor = valor.split("=")[1]
            app_state.set_status(cts.ROTARY_BUTTON, int(converted_valor))
            print("Rotary button")
        case "003":
            if valor == "0" or valor == "4":
                return
            app_state.set_status(cts.MAGNETIC_PICK_UP_SENSOR, int(valor))
            print("Magnetic pick up sensor")
        case "004":
            return
            match valor:
                case "Bs=NEAR":
                    app_state.set_status(cts.AIR_BUTTON, cts.AIR_BUTTON_NEAR)
                case "Bs=FAR":
                    app_state.set_status(cts.AIR_BUTTON, cts.AIR_BUTTON_FAR)
            print("Air Button")
        case "005":
            converted_valor = valor.split("=")[1]
            print("Presence sensor")
            match converted_valor:
                case "XX":
                    return
                case "AB":
                    app_state.set_status(cts.PRESENCE_SENSOR, cts.PRESENCE_SENSOR_CLOSE)
                    return
                case "10":
                    app_state.set_status(cts.PRESENCE_SENSOR, 10)
                    return
            app_state.set_status(cts.AIR_BUTTON, int(converted_valor.strip("0")))
        case "006":
            app_state.set_status(cts.LIGHT_SENSOR, int(valor))
            print("Light sensor")
        case "007":
            return
