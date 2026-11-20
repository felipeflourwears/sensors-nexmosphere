import time
import re
import constants as cts

RE_RFID = re.compile(r"^XR\[(PU|PB)(\d{1,3})\]$")
RE_XTALK = re.compile(r"^X(\d{3})([A-Z])\[(.*)\]$")

# ---------------------------------------------------------------------------
# Interpretación de los mensajes
# ---------------------------------------------------------------------------

def process_push_button(valor):
    print(valor)

def process_rfid_pickup(tag, estado):
    """Un tag fue levantado de la antena (XR[PUxxx])."""
    ahora = time.monotonic()
    anterior = estado.get("ultimo_pickup")

    if anterior is not None:
        tag_anterior, t_anterior = anterior
        combo = cfg.RFID_POR_COMBO.get((tag_anterior, tag))
        if combo and (ahora - t_anterior) <= cfg.RFID_COMBO_TIMEOUT:
            solicitar_video(combo, f"combo tag {tag_anterior:03d}+{tag:03d}")
            estado["ultimo_pickup"] = None
            return

    video = cfg.RFID_POR_TAG.get(tag)
    if video:
        solicitar_video(video, f"pick-up tag {tag:03d}")
    else:
        print(f"   pick-up tag {tag:03d} sin video asignado")
    estado["ultimo_pickup"] = (tag, ahora)


def procesar_rotary(valor):
    """X002B[Dr=1..20] -> video según el rango de la posición."""
    clave, _, bruto = valor.partition("=")
    if clave != cfg.ROTARY["clave"]:
        return
    try:
        posicion = int(bruto)
    except ValueError:
        print(f"   valor de rotary no numérico: {valor!r}")
        return
    for desde, hasta, video in cfg.ROTARY["rangos"]:
        if desde <= posicion <= hasta:
            solicitar_video(video, f"{cfg.ROTARY['nombre']} ({posicion})")
            return
    print(f"   posición de rotary sin video asignado: {posicion}")


def process_line(line, app_state):

    # --- RFID: primer mensaje del par ---
    m = RE_RFID.match(line)
    if m:
        #print(">>", line)
        evento, tag = m.group(1), int(m.group(2))
        #print(evento)
        #print(tag)
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
