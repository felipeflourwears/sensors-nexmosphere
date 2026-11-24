@echo off
REM ===========================================================================
REM  Sensors Nexmosphere - lanzador para Windows
REM
REM  Doble clic y listo:
REM    - La primera vez crea el entorno virtual e instala las dependencias.
REM    - Las siguientes veces arranca directo.
REM
REM  Para forzar un puerto:  iniciar.bat COM3
REM ===========================================================================

setlocal
REM Trabajar siempre en la carpeta del script, no en la del acceso directo.
cd /d "%~dp0"

set VENV_PY=venv\Scripts\python.exe

REM --- Buscar Python en el sistema ---------------------------------------
REM 'py' es el lanzador oficial y es el mas fiable; si no esta, probamos python.
set PY=
where py >nul 2>&1 && set PY=py
if not defined PY (
    where python >nul 2>&1 && set PY=python
)
if not defined PY goto sin_python

REM --- Crear el entorno virtual si no existe -----------------------------
if not exist "%VENV_PY%" (
    echo.
    echo Creando entorno virtual... esto solo pasa la primera vez.
    %PY% -m venv venv
    if errorlevel 1 goto error_venv
)

REM --- Instalar dependencias si faltan -----------------------------------
REM Comprobamos importando: cubre el caso de un venv a medio instalar.
"%VENV_PY%" -c "import cv2, numpy, serial" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Instalando dependencias... puede tardar un par de minutos.
    "%VENV_PY%" -m pip install --upgrade pip
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 goto error_pip
    echo.
    echo Dependencias instaladas.
)

REM --- Arrancar ----------------------------------------------------------
echo.
echo Iniciando... pulsa 'q' o Escape sobre el video para salir.
echo.
"%VENV_PY%" main.py %*
if errorlevel 1 goto error_run

endlocal
exit /b 0


REM ===========================================================================
:sin_python
echo.
echo ERROR: no se encontro Python en este equipo.
echo.
echo Instalalo desde https://www.python.org/downloads/
echo IMPORTANTE: marca la casilla "Add Python to PATH" durante la instalacion.
echo.
pause
exit /b 1

:error_venv
echo.
echo ERROR: no se pudo crear el entorno virtual.
echo Comprueba que Python este bien instalado ejecutando:  py --version
echo.
pause
exit /b 1

:error_pip
echo.
echo ERROR: fallo la instalacion de dependencias.
echo Revisa que haya conexion a internet y vuelve a ejecutar este archivo.
echo.
pause
exit /b 1

:error_run
echo.
echo El programa termino con error. Revisa los mensajes de arriba.
echo.
echo Causas mas frecuentes:
echo   - No se encontro el cable: falta el driver (Prolific / FTDI / CH340).
echo   - Puerto ocupado: cierra PuTTY, Arduino IDE u otra terminal serie.
echo   - Falta algun video en la carpeta videos\.
echo.
pause
exit /b 1
