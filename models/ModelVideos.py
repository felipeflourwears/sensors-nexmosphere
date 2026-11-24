import os
import constants as cts
import config as cfg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(BASE_DIR, "media")

OCULTAR_CURSOR = True
MONITOR = "DP-3"

MONITOR_X = 0
MONITOR_Y = 0

AJUSTE = "cubrir"
COLOR_FONDO = "auto"


def v(name):
    return os.path.join(VIDEO_DIR, name)

LOOP = v(cfg.LOOP_VIDEO)

SENSORS = {
    (cts.RFID_TAG): {
        "name": "RFID tags",
        "videos": {
            cts.RFID_TAG_ID_1: v(cfg.RFID_1_VIDEO),
            cts.RFID_TAG_ID_2: v(cfg.RFID_2_VIDEO),
            cts.RFID_TAG_ID_3: v(cfg.RFID_3_VIDEO),
            cts.RFID_TAG_ID_4: v(cfg.RFID_4_VIDEO),
        },
    },
    (cts.MAGNETIC_PICK_UP_SENSOR): {
        "name": "Sensor magnético",
        "videos": {
            cts.MAGNETIC_PICK_UP_SENSOR: v(cfg.MAGNETIC_VIDEO),
        },
    },
    (cts.PRESENCE_SENSOR): {
        "name": "Sensor de presencia",
        "videos": {
            0:  v("presence/" + cfg.PRESENCE_SENSOR_0),
            1:  v("presence/" + cfg.PRESENCE_SENSOR_1),
            2:  v("presence/" + cfg.PRESENCE_SENSOR_2),
            3:  v("presence/" + cfg.PRESENCE_SENSOR_3),
            4:  v("presence/" + cfg.PRESENCE_SENSOR_4),
            5:  v("presence/" + cfg.PRESENCE_SENSOR_5),
            6:  v("presence/" + cfg.PRESENCE_SENSOR_6),
            7:  v("presence/" + cfg.PRESENCE_SENSOR_7),
            8:  v("presence/" + cfg.PRESENCE_SENSOR_8),
            9:  v("presence/" + cfg.PRESENCE_SENSOR_9),
            10: v("presence/" + cfg.PRESENCE_SENSOR_10)
        }
    },
    cts.ROTARY_BUTTON: {
        "name": "Rotary Button",
        "videos": {
            0:  v("rotary/" + cfg.ROTARY_SENSOR_0),
            1:  v("rotary/" + cfg.ROTARY_SENSOR_1),
            2:  v("rotary/" + cfg.ROTARY_SENSOR_2),
            3:  v("rotary/" + cfg.ROTARY_SENSOR_3),
            4:  v("rotary/" + cfg.ROTARY_SENSOR_4),
            5:  v("rotary/" + cfg.ROTARY_SENSOR_5),
            6:  v("rotary/" + cfg.ROTARY_SENSOR_6),
            7:  v("rotary/" + cfg.ROTARY_SENSOR_7),
            8:  v("rotary/" + cfg.ROTARY_SENSOR_8),
            9:  v("rotary/" + cfg.ROTARY_SENSOR_9),
            10: v("rotary/" + cfg.ROTARY_SENSOR_10),
            11: v("rotary/" + cfg.ROTARY_SENSOR_11),
            12: v("rotary/" + cfg.ROTARY_SENSOR_12),
            13: v("rotary/" + cfg.ROTARY_SENSOR_13),
            14: v("rotary/" + cfg.ROTARY_SENSOR_14),
            15: v("rotary/" + cfg.ROTARY_SENSOR_15),
            16: v("rotary/" + cfg.ROTARY_SENSOR_16),
            17: v("rotary/" + cfg.ROTARY_SENSOR_17),
            18: v("rotary/" + cfg.ROTARY_SENSOR_18),
            19: v("rotary/" + cfg.ROTARY_SENSOR_19),
            20: v("rotary/" + cfg.ROTARY_SENSOR_20),
        }
    }
}

def all_media_files():
    rutas = [LOOP]
    for sensor in SENSORS.values():
        rutas += list(sensor["videos"].values())
    return rutas
