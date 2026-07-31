"""Configuración de la instalación: qué video dispara cada sensor.

Este es el ÚNICO archivo que necesitas editar para cambiar videos o sensores.
No hace falta tocar main.py.

Cómo funciona:
  - Pon los archivos .mp4 dentro de la carpeta 'videos/'.
  - Usa v("nombre.mp4") para referenciarlos.
  - Cada sensor se identifica por su dirección X-talk y su canal (la letra que
    aparece en el mensaje). Por ejemplo, en X003A[3] la dirección es "003",
    el canal es "A" y el valor es "3".
"""

import os

# Rutas relativas a este archivo, no al directorio desde el que se lanza el
# programa. Así funciona igual con doble clic, systemd o autostart de kiosko.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = os.path.join(BASE_DIR, "videos")


def v(nombre):
    """Ruta completa de un video dentro de la carpeta 'videos'."""
    return os.path.join(VIDEO_DIR, nombre)


# ---------------------------------------------------------------------------
# Video en bucle
# ---------------------------------------------------------------------------
# Se reproduce en bucle mientras no haya ningún sensor activado, y es al que se
# vuelve cuando termina el video de un trigger.
LOOP = v("loop.mp4")


# ---------------------------------------------------------------------------
# RFID (mensajes XR[PUxxx] / XR[PBxxx])
# ---------------------------------------------------------------------------
# Número de tag -> video que se reproduce al LEVANTAR el producto.
RFID_POR_TAG = {
    1: v("cocacola.mp4"),
    2: v("sprite.mp4"),
}

# Dos tags levantados en secuencia -> video de combinación.
# La clave es (primer tag, segundo tag), así que el orden importa.
RFID_POR_COMBO = {
    (1, 2): v("coca-sprite.mp4"),
    (2, 1): v("sprite-coca.mp4"),
}

# Segundos máximos entre dos pick-ups para considerarlos una combinación.
RFID_COMBO_TIMEOUT = 3.0


# ---------------------------------------------------------------------------
# Resto de sensores: (dirección, canal) -> valor del mensaje -> video
# ---------------------------------------------------------------------------
SENSORES = {
    ("001", "A"): {
        "nombre": "Push buttons",
        "videos": {
            "17": v("fanta.mp4"),           # X001A[17] -> botón 1
            "3": v("santa_clara.mp4"),   # X001A[3]  -> botón 2
            # X001A[0] es "soltar el botón": sin video, no hace nada.
        },
    },
    ("003", "A"): {
        "nombre": "Sensor magnético",
        "videos": {
            "3": v("delvalle.mp4"),
            # Según el manual, X003A[0] es el pick-up y [3] el stand-by.
            # Si el video debe salir al levantar el producto, cambia "3" por "0".
        },
    },
    ("004", "B"): {
        "nombre": "Air button",
        "videos": {
            "Bs=NEAR": v("close.mp4"),
            "Bs=FAR": v("far.mp4"),
            # Bs=IDLE (fuera del área): sin video.
        },
    },
    ("005", "B"): {
        "nombre": "Sensor de presencia",
        "videos": {
            "Dz=AB": v("presence_sensor.mp4"),
        },
    },
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
        (1, 10, v("left.mp4")),
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


# ---------------------------------------------------------------------------
# Puerto serie
# ---------------------------------------------------------------------------
BAUDRATE = 115200

# Deja None para autodetectar. Si quieres fijarlo: "/dev/ttyUSB0" o "COM3".
PUERTO_FIJO = None


def todos_los_videos():
    """Todas las rutas de video configuradas (para validarlas al arrancar)."""
    rutas = [LOOP]
    rutas += list(RFID_POR_TAG.values())
    rutas += list(RFID_POR_COMBO.values())
    for sensor in SENSORES.values():
        rutas += list(sensor["videos"].values())
    rutas += [video for _, _, video in ROTARY["rangos"]]
    return rutas
