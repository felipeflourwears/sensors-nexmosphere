# Sensors Nexmosphere

Reproductor multimedia en modo kiosko controlado por sensores Nexmosphere y comunicación serial con el microcontrolador. Escucha los mensajes de la API serial del controlador Xperience (115200 baudios), gestiona el estado de forma concurrente y lanza videos (individuales o en mosaico de hasta 4 pantallas) o imágenes estáticas según la interacción física.

---

## Arquitectura del Proyecto

El código está modularizado para separar la lectura de hardware, el estado concurrente y la renderización en pantalla:

- **`main.py`** — Punto de entrada y orquestación de hilos.
- **`AppState.py`** — Gestión de estado *thread-safe* (`threading.Lock`) entre los hilos de lectura serial, mirocontrolador y video.
- **`constants.py`** — Identificadores de sensores, constantes de tags RFID y banderas de control para el microcontrolador.
- **`models/ModelVideos.py`** — **Configuración principal**: mapeo de sensores a rutas de video/imagen, video en bucle (`LOOP`), selección de monitor, modo de ajuste y color de fondo. *Es el único archivo que necesitas editar para cambiar contenido.*
- **`models/ModelSerial.py`** — Detección automática y apertura del puerto USB-serial del controlador Nexmosphere (priorizando conversores Prolific a `115200` baudios).
- **`models/ModelSignals.py`** — Parser de mensajes `XR[...]` y `X***[...]` de Nexmosphere hacia acciones de video o comandos para el microcontrolador.
- **`models/ModelLedController.py`** — Hilo de comunicación serial (`9600` baudios) hacia un microcontrolador (chip `CH340`) para disparar acciones externas (ej. iluminación o actuadores) mediante banderas (`FLAG1`–`FLAG4`).
- **`models/ModelDisplay.py`** — Motor de reproducción en ventana kiosko sin bordes (`OpenCV`), composición en mosaico (1, 2 o 4 secciones) y renderizado de imágenes con retorno automático al loop.
- **`videos/`** — Archivos multimedia (`.mp4`, `.png`, `.jpg`, `.jpeg`).
- **`docs/`** — Manuales y datasheets oficiales de Nexmosphere.

---

## Arranque rápido (un clic)

Solo necesitas tener **Python 3.10 o superior** instalado (el código utiliza sentencias `match/case`):

- **Windows** → doble clic en **`iniciar.bat`**
- **Linux** → doble clic en **`iniciar.sh`** (o `./iniciar.sh` en la terminal)

La primera vez crea el entorno virtual (`venv`) e instala las dependencias automáticamente; en ejecuciones posteriores arranca directo. Para forzar un puerto específico en el controlador Nexmosphere:

```bash
iniciar.bat COM3            # Windows
./iniciar.sh /dev/ttyUSB0   # Linux
```

> **Nota en Linux:** Si al hacer doble clic no se ejecuta, dale permisos desde la terminal con `chmod +x iniciar.sh` o en *Propiedades → Permisos → Permitir ejecutar*.

**Nota en Windows:** Si el video o imagen seleccionado no es el correcto, cerrar programa y volver a abrir.
---

## Instalación manual

### Linux

```bash
# 1. Crear y activar el entorno virtual
python3 -m venv venv
source venv/bin/activate

# 2. Instalar dependencias (opencv-python, numpy, pyserial)
pip install -r requirements.txt
```

**Permisos del puerto serie:** Añade tu usuario al grupo `dialout` una sola vez y reinicia sesión (o usa `newgrp dialout` en la terminal actual):

```bash
sudo usermod -aG dialout $USER
```

**Ocultar cursor (opcional):** El sistema utiliza `unclutter` en Linux/X11 si `OCULTAR_CURSOR` está activo:

```bash
sudo apt install unclutter
```

### Windows

```powershell
# 1. Crear y activar el entorno virtual (PowerShell)
python -m venv venv
venv\Scripts\Activate.ps1

# 2. Instalar dependencias
pip install -r requirements.txt
```

*(Si PowerShell bloquea el script, ejecuta `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` una sola vez.)*

Asegúrate de tener instalados los drivers de los cables USB-Serial:
- **Nexmosphere:** Prolific (`PL2303`)
- **Microcontrolador (opcional):** `CH340` / `CH341`

---

## Uso y controles

Con el entorno virtual activado:

```bash
python main.py                # Autodetecta Nexmosphere (Prolific) y Microcontrolador (CH340)
```

- **Salir del modo kiosko:** Presiona **`q`** o **`Escape`** sobre la ventana de video.
- **Orden de encendido:** Conecta todos los sensores al bus X-talk **antes** de energizar el controlador Xperience; de lo contrario, no serán reconocidos.

---

## Configuración (`models/ModelVideos.py`)

Toda la personalización visual y de sensores se concentra en `models/ModelVideos.py`:

| Parámetro | Descripción |
| :--- | :--- |
| `LOOP` | Ruta (o tupla de rutas) del video base que se reproduce en bucle en reposo. |
| `SENSORS` | Diccionario indexado por constantes (`constants.py`) con el subdiccionario `"videos"` mapeando cada valor/tag a su archivo multimedia. |
| `MONITOR` | Monitor destino en X11: nombre (`"DP-1"`, `"HDMI-1"`), índice entero (`0`, `1`) o `"auto"` / `"primary"`. |
| `MONITOR_X` / `MONITOR_Y` | Coordenadas `(x, y)` de respaldo si no se detectan monitores vía `xrandr` (Windows/Wayland). |
| `AJUSTE` | `"cubrir"` (llena pantalla recortando bordes), `"contener"` (video completo con relleno), `"estirar"`. |
| `COLOR_FONDO` | Color BGR `(B, G, R)` para las bandas en modo `"contener"`, o `"auto"` para muestrear el color promedio de los bordes del video. |
| `OCULTAR_CURSOR` | `True` / `False` para ocultar el puntero del ratón en Linux/X11 mediante `unclutter`. |

### Modos de reproducción y mosaico

1. **Multi-video simultáneo (RFID):** Al levantar múltiples tags RFID (`PU`), el sistema apila los tags activos y compone dinámicamente la pantalla:
   - **1 tag:** Pantalla completa.
   - **2 tags:** Pantalla dividida verticalmente en 2 secciones (izquierda / derecha).
   - **3 o 4 tags:** Cuadrícula 2×2 (si hay 3 videos activos, descarta el más antiguo de la lista o acomoda hasta 4 fuentes simultáneas).
   - Al volver a colocar los tags (`PB`) o finalizar los videos que no son loop, regresa automáticamente a `cfg.LOOP`.
2. **Imágenes estáticas:** Si un sensor apunta a un archivo `.png`, `.jpg` o `.jpeg`, se muestra en pantalla durante **2.0 segundos** (`TIEMPO_INACTIVIDAD_IMAGEN`) y vuelve automáticamente a `cfg.LOOP`.

---

## Referencia de Hardware y API Serial

### Controlador Nexmosphere (`115200` baudios)

Mapeo implementado en `models/ModelSignals.py`:

| Sensor / Dispositivo | Dirección / Formato | Mensajes recibidos | Acción en el sistema |
| :--- | :--- | :--- | :--- |
| **Antena RFID (XR)** | `XR[PUxxx]` / `XR[PBxxx]` | `PU` (levantar) / `PB` (colocar) tag `001`–`250` | Añade/quita el tag de la pila activa (`RFID_TAG`) para reproducir 1, 2 o 4 videos en mosaico. |
| **Push Buttons** | `X001A[...]` | `[3]` (Botón 2) / `[17]` (Botón 1) / `[0]` (soltado) | Envía `FLAG1` (`"3"`) o `FLAG2` (`"17"`) al microcontrolador. |
| **Rotary Button** | `X002B[Dr=X]` | `Dr=1` a `Dr=20` | Reproduce el video asignado al índice de rotación (`ROTARY_BUTTON`). |
| **Sensor Magnético** | `X003A[X]` | Valores distintos de `0` y `4` disparan evento | Reproduce el video asociado (`MAGNETIC_PICK_UP_SENSOR`). |
| **Air Button** | `X004B[Bs=...]` | `Bs=NEAR` / `Bs=FAR` | Envía `FLAG3` (`NEAR`) o `FLAG4` (`FAR`) al microcontrolador. |
| **Sensor de Presencia** | `X005B[Dz=...]` | `Dz=AB` (0), `Dz=10` (10), o zonas numéricas (`PRESENCE_SENSOR`) | Reproduce el video correspondiente a la zona de distancia detectada. |
| **Sensor de Luz** | `X006A[X]` | Valor numérico entero | Actualiza estado interno `LIGHT_SENSOR`. |

### Comunicación con el microcontrolador (`9600` baudios)

`models/ModelLedController.py` busca automáticamente un dispositivo con descriptor **`CH340`**. Cuando un Push Button o Air Button se activa, envía la bandera correspondiente terminada en salto de línea (`\n`):

- `FLAG1\n` → Push Button valor `3`
- `FLAG2\n` → Push Button valor `17`
- `FLAG3\n` → Air Button `Bs=NEAR`
- `FLAG4\n` → Air Button `Bs=FAR`

### Ajustes del driver RFID (XR-DR1)

Si ocurren disparos fantasma (*ghost pick-ups*) por interferencia electromagnética, envía estos comandos al controlador Nexmosphere al iniciar (se pierden al desconectar la corriente):

```text
X001S[6:4]   # Sube el filtro de ghost pick-ups (rango 1-20, defecto 2)
X001S[4:3]   # Ganancia de antena calibrada a 38 dB (valor recomendado)
X001S[5:1]   # LED rojo indicador de interferencia nivel 3
```

*(Consulta `docs/Product+Manual+-+XR+Range+RFID.pdf`, secciones 4.2 y 5 para más detalles.)*

---

## Solución de problemas

| Síntoma | Causa probable y solución |
| :--- | :--- |
| `Permission denied: '/dev/ttyUSB0'` | Tu usuario no pertenece al grupo `dialout`. Ejecuta `sudo usermod -aG dialout $USER` y reinicia sesión. |
| `Access is denied` en `COMx` | El puerto está ocupado por PuTTY, Arduino IDE u otro monitor serie. Ciérralo antes de iniciar. |
| No detecta el controlador Nexmosphere | El código filtra automáticamente dispositivos con chip **Prolific**. Verifica el driver o pasa el puerto manualmente (`iniciar.bat COMx`). |
| `Could not find micro!` | No hay ningún conversor `CH340` conectado; el sistema continuará operando solo con los videos. |
| Los sensores no envían datos | Fueron conectados después de encender el controlador Xperience. Reinicia la alimentación del controlador. |
| El kiosko abre en el monitor incorrecto | Revisa los nombres impresos en consola al arrancar y ajusta `MONITOR` en `models/ModelVideos.py`. |
| Franjas negras a los lados del video | Cambia `AJUSTE = "cubrir"` o usa `AJUSTE = "contener"` con `COLOR_FONDO = "auto"`. |
