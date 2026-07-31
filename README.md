# Sensors Nexmosphere

Reproductor de video en modo kiosko controlado por sensores Nexmosphere.
Escucha los mensajes de la API serial del controlador Xperience y lanza el video
que corresponda a cada sensor.

- `main.py` — lógica: puerto serie, interpretación de mensajes y reproducción.
- `ModelVideos.py` — **configuración**: qué video dispara cada sensor, monitor,
  ajuste de pantalla. Es el único archivo que hay que editar para cambiar videos.
- `videos/` — los archivos `.mp4`.
- `docs/` — manuales y datasheets oficiales de Nexmosphere.

---

## Arranque rápido (un clic)

Lo único que necesitas es tener Python instalado.

- **Windows** → doble clic en **`iniciar.bat`**
- **Linux** → doble clic en **`iniciar.sh`** (o `./iniciar.sh` en la terminal)

La primera vez crea el entorno virtual e instala las dependencias solo; las
siguientes arranca directo. Si el entorno existe pero le faltan paquetes,
también los instala. Para forzar un puerto concreto:

```
iniciar.bat COM3            (Windows)
./iniciar.sh /dev/ttyUSB0   (Linux)
```

Si algo falla, la ventana **no se cierra**: deja el error en pantalla con las
causas más probables.

En Linux, si al hacer doble clic no arranca, marca el archivo como ejecutable
(clic derecho → Propiedades → Permisos → *Permitir ejecutar*) o desde terminal:
`chmod +x iniciar.sh`

El resto de esta sección es la instalación manual, por si la prefieres.

---

## Instalación manual

Requiere **Python 3.8 o superior** (probado en 3.12).

### Linux

```bash
# 1. Crear el entorno virtual
python3 -m venv venv

# 2. Activarlo
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

Si `python3 -m venv` falla, instala el paquete: `sudo apt install python3-venv`

**Permisos del puerto serie.** En Linux el puerto pertenece al grupo `dialout` y
hay que añadir tu usuario una sola vez:

```bash
sudo usermod -aG dialout $USER
```

El cambio no aplica hasta cerrar y volver a abrir sesión. Para probar de
inmediato sin reiniciar sesión, abre una terminal con el grupo ya activo:

```bash
newgrp dialout
```

Opcional, para ocultar el cursor del ratón en el kiosko:

```bash
sudo apt install unclutter
```

### Windows

```powershell
# 1. Crear el entorno virtual
python -m venv venv

# 2. Activarlo (PowerShell)
venv\Scripts\Activate.ps1

# 3. Instalar dependencias
pip install -r requirements.txt
```

En **CMD** en lugar de PowerShell, el paso 2 es `venv\Scripts\activate.bat`.

Si PowerShell bloquea el script de activación, permite los scripts locales una
sola vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

En Windows no hay que tocar permisos, pero sí necesitas el **driver del cable**
(Prolific PL2303, FTDI, CH340 — según el cable). Comprueba en el Administrador
de dispositivos que aparezca un puerto `COMx`.

### Desactivar el entorno

En ambos sistemas: `deactivate`

---

## Uso

Con el entorno activado:

```bash
python main.py                # autodetecta el puerto
python main.py /dev/ttyUSB0   # forzar puerto en Linux
python main.py COM3           # forzar puerto en Windows
```

Salir del kiosko: tecla **`q`** o **`Escape`**.

Al arrancar imprime los puertos candidatos, los monitores detectados y la
resolución a la que ajusta el video, además de avisar de cualquier video
configurado que no exista en disco.

> **Importante:** conecta los sensores al X-talk **antes** de alimentar el
> controlador Xperience. Si los enchufas después, el controlador no los reconoce
> y no emite ningún mensaje (sección 4.1 del manual XR Range).

---

## Configuración

Todo en `ModelVideos.py`:

| Ajuste | Para qué sirve |
|---|---|
| `RFID_POR_TAG` | Número de tag → video al levantar el producto |
| `RFID_POR_COMBO` | Dos tags en secuencia → video de combinación |
| `SENSORES` | `(dirección, canal)` → valor del mensaje → video |
| `ROTARY` | Rangos de posición del rotary → video |
| `MONITOR` | Monitor del kiosko: nombre (`"DP-3"`), índice (`0`) o `"auto"` |
| `AJUSTE` | `"cubrir"` (llena y recorta), `"contener"` (completo con relleno), `"estirar"` |
| `COLOR_FONDO` | Relleno en modo `"contener"`: `"auto"` o color BGR |
| `BAUDRATE` | 115200 por defecto |

Añadir un sensor nuevo es una entrada más en `SENSORES`, sin tocar `main.py`.

### Notas de pantalla

Los videos son 1920×1080. Si el monitor tiene otra resolución, `AJUSTE`
determina qué pasa; con `"cubrir"` nunca aparecen franjas.

En Linux con Wayland, el programa fuerza el backend X11 de Qt automáticamente,
porque Wayland nativo no permite que la aplicación se coloque en un monitor
concreto. Los nombres de monitor salen de `xrandr --listmonitors`.

---

## Referencia de la API serial

Baudrate **115200**. Cada línea es un mensaje.

### RFID (XR Range)

Cada evento manda **dos mensajes consecutivos**: primero el número de tag y
después la dirección X-talk de la antena donde ocurrió.

```
XR[PUxxx]   Pick-up: el tag se levantó de la antena
X***A[1]    ...seguido de la dirección de esa antena

XR[PBxxx]   Place-back: el tag se colocó en la antena
X***A[0]    ...seguido de la dirección de esa antena
```

`xxx` es el número de tag, de **001 a 250**. Cada tag de la instalación debe
tener un número distinto. Ejemplo real de levantar el tag 4 en la antena 001:

```
XR[PU004]
X001A[1]
```

Una antena detecta hasta **4 tags simultáneos**, con 10 mm de separación mínima
entre ellos.

### Sensor magnético (pick-up)

```
X003A[3]   Stand by
X003A[0]   Pick up
```

> La configuración actual dispara el video en `[3]`. Si debe salir al levantar
> el producto, cambia la clave a `"0"` en `ModelVideos.py`.

### Air Button

```
X004B[Bs=NEAR]   Cerca
X004B[Bs=FAR]    Lejos
X004B[Bs=IDLE]   Fuera del área
```

### Rotary Button

```
X002B[Dr=1] ... X002B[Dr=20]
```

### Push Buttons

```
X001A[17]   Botón 1 pulsado
X001A[3]    Botón 2 pulsado
X001A[0]    Botón soltado (ambos casos)
```

### Sensor de presencia

```
X005B[Dz=AB]   Presencia detectada
```

---

## Ajustes del driver RFID (XR-DR1)

Se envían por serial al controlador. **Se pierden al cortar la alimentación**,
hay que reenviarlos en cada arranque.

```
X001S[6:X]   Filtro de "ghost pick-ups", X entre 1 y 20 (por defecto 2)
X001S[4:3]   Ganancia de antena: 38dB, el valor por defecto
X001S[5:1]   LED rojo: mostrar interferencia de nivel 3
```

Si aparecen disparos de video espurios (sin que nadie toque nada), la causa
suele ser interferencia. La solución documentada es **subir el filtro** con
`X001S[6:4]` o `[6:6]` antes de tocar el código: sube a costa de un poco de
respuesta. La ganancia mejor no cambiarla — todo el XR Range está calibrado
para 38 dB, y subirla aumenta la interferencia entre antenas.

Más detalle en `docs/Product+Manual+-+XR+Range+RFID.pdf`, secciones 4.2 y 5.

---

## Problemas frecuentes

| Síntoma | Causa probable |
|---|---|
| `Permission denied: '/dev/ttyUSB0'` | Falta el grupo `dialout` (ver Instalación) |
| `Access is denied` en `COMx` | Otro programa tiene el puerto abierto (PuTTY, Arduino IDE) |
| No encuentra ningún puerto | Falta el driver del cable, o no está conectado |
| No llega ningún mensaje | Los sensores se conectaron después de alimentar el controlador |
| El kiosko abre en el monitor equivocado | Ajusta `MONITOR` en `ModelVideos.py` |
| Franjas en los bordes del video | Pon `AJUSTE = "cubrir"` |
| Disparos de video sin tocar nada | Ghost triggers: sube el filtro con `X001S[6:X]` |
| El cursor se ve sobre el video | Instala `unclutter` (solo Linux) |
