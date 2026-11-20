import os
import constants as cts
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(BASE_DIR, "videos")

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
            "17": v("fanta.mp4"),
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
            cts.PRESENCE_SENSOR_CLOSE: v("presence_sensor.mp4"),
        },
    },
    cts.ROTARY_BUTTON: {
        "name": "Rotary Button",
        "videos": {
            0:  v("rotary/0.png"),
            1:  v("rotary/1.png"),
            2:  v("rotary/2.png"),
            3:  v("rotary/3.png"),
            4:  v("rotary/4.png"),
            5:  v("rotary/5.png"),
            6:  v("rotary/6.png"),
            7:  v("rotary/7.png"),
            8:  v("rotary/8.png"),
            9:  v("rotary/9.png"),
            10: v("rotary/10.png"),
            11: v("rotary/11.png"),
            12: v("rotary/12.png"),
            13: v("rotary/13.png"),
            14: v("rotary/14.png"),
            15: v("rotary/15.png"),
            16: v("rotary/16.png"),
            17: v("rotary/17.png"),
            18: v("rotary/18.png"),
            19: v("rotary/19.png"),
            20: v("rotary/20.png"),
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
