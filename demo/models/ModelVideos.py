import os
import constants as cts
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(BASE_DIR, "videos")

def v(name):
    return os.path.join(VIDEO_DIR, name)


# Se reproduce en bucle mientras no haya ningún sensor activado, y es al que se
# vuelve cuando termina el video de un trigger.
LOOP = v("loop.mp4")

# Segundos máximos entre dos pick-ups para considerarlos una combinación.
RFID_COMBO_TIMEOUT = 3.0


# ---------------------------------------------------------------------------
# Resto de sensores: (dirección, canal) -> valor del mensaje -> video
# ---------------------------------------------------------------------------
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
    #(cts.ROTARY_BUTTON): {
    #    "name": "Botón de rotación",
    #    "videos": {
    #        cts.ROTARY_BUTTON_LEFT: v("left.mp4"),
    #        cts.ROTARY_BUTTON_RIGHT: v("right.mp4"),
    #    },
    #}
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

# ---------------------------------------------------------------------------
# Pantalla (modo kiosko)
# ---------------------------------------------------------------------------
# Cómo encaja el video cuando su proporción NO coincide con la de la pantalla:
#
#   "cubrir"   -> llena toda la pantalla y recorta lo que sobra.
#                 Sin barras. Es la mejor opción para kiosko.
#   "contener" -> muestra el video completo y rellena el hueco con COLOR_FONDO.
#   "estirar"  -> deforma el video hasta llenar la pantalla.
#
# Si el video y la pantalla tienen la misma resolución, esto no se aplica: el
# frame se muestra tal cual.
AJUSTE = "cubrir"

# Relleno cuando AJUSTE = "contener".
#   "auto" -> copia el color del borde del propio video, así se mezcla con
#             fondos claros u oscuros sin que se note el corte.
#   (B, G, R) -> color fijo. Ojo: OpenCV usa BGR, no RGB.
#                (255, 255, 255) blanco · (0, 0, 0) negro
COLOR_FONDO = "auto"

# Monitor en el que se abre el kiosko. Opciones:
#   "DP-3"    -> por nombre (el programa los lista al arrancar)
#   0, 1, 2   -> por índice
#   "auto"    -> el monitor primario del sistema
#
# En este equipo:
#   "DP-3" -> 1920x1080, el monitor pequeño (coincide exacto con los videos)
#   "DP-1" -> 2560x1080 ultrawide, es el primario
MONITOR = "DP-3"

# Posición manual, solo se usa si no se puede consultar la lista de monitores
# (por ejemplo en Windows, donde no existe xrandr).
MONITOR_X = 0
MONITOR_Y = 0

# Oculta el cursor del ratón sobre el video (útil en kiosko con pantalla táctil).
OCULTAR_CURSOR = True


def todos_los_videos():
    """Todas las rutas de video configuradas (para validarlas al arrancar)."""
    rutas = [LOOP]
    for sensor in SENSORS.values():
        rutas += list(sensor["videos"].values())
    rutas += [video for _, _, video in ROTARY["rangos"]]
    return rutas
