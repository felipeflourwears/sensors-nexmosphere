import time
import re

RE_RFID = re.compile(r"^XR\[(PU|PB)(\d{1,3})\]$")
RE_XTALK = re.compile(r"^X(\d{3})([A-Z])\[(.*)\]$")

# ---------------------------------------------------------------------------
# Interpretación de los mensajes
# ---------------------------------------------------------------------------
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


def process_line(line, state, app_state):
    
    # --- RFID: primer mensaje del par ---
    m = RE_RFID.match(line)
    if m:
        
        print(">>", line)
        evento, tag = m.group(1), int(m.group(2))
        print(evento)
        print(tag)
        return
        if evento == "PU":
            procesar_rfid_pickup(tag, state)
        else:
            # Place-back: no dispara video, y NO debe romper la lógica de combos.
            print(f"   place-back tag {tag:03d}")
        return

    m = RE_XTALK.match(line)
    if not m:
        return
    addr, canal, valor = m.group(1), m.group(2), m.group(3)
    #print("address ", addr)
    #print("canal ", canal)
    #print("valor ", valor)
    match addr:
        case "001":
            if valor == "0":
                return
            app_state.set_status("PUSH", valor)
            print("Push buttons")
        case "002":
            app_state.set_status("PUSH", valor)
            print("Rotary button")
        case "003":
            app_state.set_status("PUSH", valor)
            print("Magnetic pick up sensor")
        case "004":
            print("Air Button")
        case "005":
            print("Presence sensor")
        case "006":
            print("Light sensor")
        case "007":
            return
            
    clave = (addr, canal)
    #print(">>", line)
    return

    if clave == tuple(cfg.ROTARY["direccion"]):
        procesar_rotary(valor)
        return

    sensor = cfg.SENSORES.get(clave)
    if sensor is None:
        return

    video = sensor["videos"].get(valor)
    if video:
        solicitar_video(video, sensor["nombre"])