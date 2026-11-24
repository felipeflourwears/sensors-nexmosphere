import os
import constants as cts
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(BASE_DIR, "videos")

OCULTAR_CURSOR = True
MONITOR = "DP-3"

MONITOR_X = 0
MONITOR_Y = 0

AJUSTE = "cubrir"
COLOR_FONDO = "auto"


def v(name):
    return os.path.join(VIDEO_DIR, name)

# Se reproduce en bucle mientras no haya ningún sensor activado, y es al que se
# vuelve cuando termina el video de un trigger.
LOOP = v("loop.mp4")

SENSORS = {
    (cts.RFID_TAG): {
        "name": "RFID tags",
        "videos": {
            cts.RFID_TAG_ID_1: v("fanta.mp4"),
            cts.RFID_TAG_ID_2: v("santa_clara.mp4"),
            cts.RFID_TAG_ID_3: v("iphone17promax.mp4"),
            cts.RFID_TAG_ID_4: v("delvalle.mp4"),
        },
    },
    (cts.PUSH_BUTTON): {
        "name": "Push buttons",
        "videos": {
            "17": v("sprite.mp4"),
            "3": v("santa_clara.mp4"),
        },
    },
    (cts.MAGNETIC_PICK_UP_SENSOR): {
        "name": "Sensor magnético",
        "videos": {
            cts.MAGNETIC_PICK_UP_SENSOR: v("delvalle.mp4"),
        },
    },
    (cts.AIR_BUTTON): {
        "name": "Air button",
        "videos": {
            cts.AIR_BUTTON_NEAR: v("close.mp4"),
            cts.AIR_BUTTON_FAR: v("far.mp4"),
        },
    },
    (cts.PRESENCE_SENSOR): {
        "name": "Sensor de presencia",
        "videos": {
            0:  v("presence/0.jpeg"),
            1:  v("presence/1.jpeg"),
            2:  v("presence/2.jpeg"),
            3:  v("presence/3.jpeg"),
            4:  v("presence/4.jpeg"),
            5:  v("presence/5.jpeg"),
            6:  v("presence/6.jpeg"),
            7:  v("presence/7.jpeg"),
            8:  v("presence/8.jpeg"),
            9:  v("presence/9.jpeg"),
            10: v("presence/10.jpeg")
        }
    },
    cts.ROTARY_BUTTON: {
        "name": "Rotary Button",
        "videos": {
            0:  v("rotary/Frame0.jpg"),
            1:  v("rotary/Frame1.jpg"),
            2:  v("rotary/Frame2.jpg"),
            3:  v("rotary/Frame3.jpg"),
            4:  v("rotary/Frame4.jpg"),
            5:  v("rotary/Frame5.jpg"),
            6:  v("rotary/Frame6.jpg"),
            7:  v("rotary/Frame7.jpg"),
            8:  v("rotary/Frame8.jpg"),
            9:  v("rotary/Frame9.jpg"),
            10: v("rotary/Frame10.jpg"),
            11: v("rotary/Frame11.jpg"),
            12: v("rotary/Frame12.jpg"),
            13: v("rotary/Frame13.jpg"),
            14: v("rotary/Frame14.jpg"),
            15: v("rotary/Frame15.jpg"),
            16: v("rotary/Frame16.jpg"),
            17: v("rotary/Frame17.jpg"),
            18: v("rotary/Frame18.jpg"),
            19: v("rotary/Frame19.jpg"),
            20: v("rotary/Frame20.jpg"),
        }
    }
}

# ---------------------------------------------------------------------------
# Rotary button: se trata aparte porque manda un rango de posiciones
# ---------------------------------------------------------------------------
# Mensajes tipo X002B[Dr=1] ... X002B[Dr=20]
ROTARY = {
    "direccion": ("002", "B"),
    "nombre": "Rotary button",
    "clave": "Dr",
    # (desde, hasta, video) — ambos extremos incluidos
    "rangos": [
        (0, 10, v("left.mp4")),
        (11, 20, v("right.mp4")),
    ],
}

def todos_los_videos():
    """Todas las rutas de video configuradas (para validarlas al arrancar)."""
    rutas = [LOOP]
    for sensor in SENSORS.values():
        rutas += list(sensor["videos"].values())
    rutas += [video for _, _, video in ROTARY["rangos"]]
    return rutas
