#!/usr/bin/env bash
# ===========================================================================
#  Sensors Nexmosphere - lanzador para Linux
#
#  Doble clic (o ./iniciar.sh) y listo:
#    - La primera vez crea el entorno virtual e instala las dependencias.
#    - Las siguientes veces arranca directo.
#
#  Para forzar un puerto:  ./iniciar.sh /dev/ttyUSB0
# ===========================================================================
set -euo pipefail

# Trabajar siempre en la carpeta del script, no en la del acceso directo.
cd "$(dirname "$(readlink -f "$0")")"

VENV_PY="venv/bin/python"

error() {
    echo
    echo "ERROR: $1"
    echo
    # Si se lanzó con doble clic, la ventana se cerraría sin dejar leer nada.
    [ -t 0 ] || read -rp "Pulsa Enter para cerrar..."
    exit 1
}

command -v python3 >/dev/null 2>&1 || error "no se encontró python3. Instálalo con: sudo apt install python3"

# --- Crear el entorno virtual si no existe ---------------------------------
if [ ! -x "$VENV_PY" ]; then
    echo
    echo "Creando entorno virtual... esto solo pasa la primera vez."
    python3 -m venv venv || error "no se pudo crear el entorno virtual. Prueba: sudo apt install python3-venv"
fi

# --- Instalar dependencias si faltan ---------------------------------------
# Comprobamos importando: cubre el caso de un venv a medio instalar.
if ! "$VENV_PY" -c "import cv2, numpy, serial" >/dev/null 2>&1; then
    echo
    echo "Instalando dependencias... puede tardar un par de minutos."
    "$VENV_PY" -m pip install --upgrade pip
    "$VENV_PY" -m pip install -r requirements.txt || error "falló la instalación de dependencias. Revisa la conexión a internet."
    echo
    echo "Dependencias instaladas."
fi

# --- Avisar de permisos del puerto antes de arrancar -----------------------
if ! id -nG | tr ' ' '\n' | grep -qx dialout; then
    echo
    echo "AVISO: tu usuario no está en el grupo 'dialout' y puede que no pueda"
    echo "abrir el puerto serie. Para arreglarlo de forma permanente:"
    echo "  sudo usermod -aG dialout \$USER    (y volver a iniciar sesión)"
fi

# --- Arrancar --------------------------------------------------------------
echo
echo "Iniciando... pulsa 'q' o Escape sobre el video para salir."
echo
exec "$VENV_PY" main.py "$@"
