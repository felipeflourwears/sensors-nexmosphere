#!/usr/bin/env python3
"""
Nexmosphere XN-185 (DM-XN10) — Main controller
================================================
Hardware layout:
  X-talk 001 | XT-B4N6   Push button interface
  X-talk 002 | XDW-A50   Analog interface (Rotary encoder)
  X-talk 003 | XSW-X36   X-Snapper magnetic sensor
  X-talk 004 | XT-EF30   AirButton sensor
  X-talk 005 | XY-240    Presence & AirButton sensor
  X-talk 006 | XZ-L20    Light sensor
  X-talk 007 | XR-DR1    RFID sensor
  X-talk 008 | XW-L56    X-Wave LED (5 LEDs)
"""

import os
import sys
import queue
import logging
import threading
from typing import Callable, NamedTuple

import cv2
import serial
import serial.tools.list_ports

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Video paths
# ---------------------------------------------------------------------------
VIDEO_LOOP            = "lala/loop.mp4"
VIDEO_RFID_1          = "lala/rfid-1.mp4"
VIDEO_RFID_2          = "lala/rfid-2.mp4"
VIDEO_RFID_1_2        = "lala/rfid-1-2.mp4"
VIDEO_RFID_2_1        = "lala/rfid-1-2.mp4"
VIDEO_MAGNETIC_SENSOR = "lala/magnetic-sensor.mp4"
VIDEO_PUSH_BUTTON1    = "lala/push-button1.mp4"
VIDEO_PUSH_BUTTON2    = "lala/push-button2.mp4"
VIDEO_CLOSE           = "videos/close.mp4"
VIDEO_FAR             = "videos/far.mp4"
VIDEO_RIGHT           = "videos/right.mp4"
VIDEO_LEFT            = "videos/left.mp4"
VIDEO_PRESENCE_SENSOR = "videos/presence_sensor.mp4"

# ---------------------------------------------------------------------------
# Serial config
# ---------------------------------------------------------------------------
BAUD_RATE    = 115200
PORT_KEYWORD = "Prolific"   # Substring to match in the port description


# ===========================================================================
# LED color profile
# ===========================================================================
class LedProfile(NamedTuple):
    """
    Full definition of a sensor's LED appearance.

    label     : Hex char (0-F) — the custom color slot on the XW-L56.
                Each profile owns a unique slot; LedController.init_colors()
                programs the exact RGB into the device at startup.
    r, g, b   : Exact RGB target (0-255).  These are programmed once via
                the set_custom_color protocol command (X008B[1ARRGGBB]).
                After that, only the label is referenced in ramp/pulse/wave
                commands.  On power-cycle the device resets labels to its
                default palette; init_colors() must be called again.
    intensity : Final brightness 0-99 (99 = physical maximum).
    ramp_time : Transition time in units of 0.1 s (0-99).
    name      : Human-readable string used in console logs.
    """
    label:     str
    r:         int
    g:         int
    b:         int
    intensity: int
    ramp_time: int
    name:      str


# ===========================================================================
# LedController — XW-L56 X-Wave LED  (X-talk 008)
# ===========================================================================
class LedController:
    """
    Builds and sends X-Wave LED commands to the XW-L56 module
    on X-talk interface 008.

    Protocol: "Manual – Controlling X-Wave LEDs (API)" v1.0
    Commands are sent over the shared serial port.

    ┌─────────────────────────────────────────────────────────────────────┐
    │  Custom color : X008B[1ARRGGBB]                                     │
    │    A  = color label  0-F                                            │
    │    RR = Red   00-FF   GG = Green 00-FF   BB = Blue 00-FF            │
    │                                                                     │
    │  Single ramp  : X008B[2IICTT]                                       │
    │    II = intensity 00-99   C = color label   TT = ramp × 0.1 s       │
    │                                                                     │
    │  Pulse        : X008B[3IICTTPPOIICTTRRTT]                           │
    │    State1: II C TT   PP=01 (fixed)  O=0 (fixed)                     │
    │    State2: II C TT   RR = repeats (00=∞)   TT = ramp time           │
    │                                                                     │
    │  Wave         : X008B[4IICDDPPOIICUULL]                             │
    │    State1: II C   DD = duration   PP = program   O = direction      │
    │    State2: II C   UU = reserved (00)   LL = LEDs for animation      │
    │    Programs: 00=sym-sine  01=asym-sine  51-59=discrete              │
    │    Direction: 1=left  2=right  3=outward  4=inward                  │
    └─────────────────────────────────────────────────────────────────────┘

    Color strategy
    ──────────────
    Each sensor gets a dedicated label slot (0-A).  On startup, init_colors()
    programs each slot with an exact saturated RGB value via set_custom_color.
    Subsequent ramp commands reference only the label, keeping the bus lean.
    set_sensor_color() deduplicates: repeated calls with the same key are
    silently ignored to avoid flooding the serial bus.
    """

    LED_ADDRESS = "008"

    # ------------------------------------------------------------------
    # Sensor → LED color mapping
    # Labels 0-A are assigned exclusively to the keys below.
    # Vivid, saturated RGB values are used so every sensor is visually
    # unambiguous on the physical strip.
    # ------------------------------------------------------------------
    SENSOR_LED_MAP: dict[str, LedProfile] = {
        #                label   R    G    B   int  ramp  display name
        "RFID_1":         LedProfile("0", 255,   0,   0,  99,  5, "Rojo Puro"),
        "RFID_2":         LedProfile("1",   0,   0, 255,  99,  5, "Azul Eléctrico"),
        "PUSH_BTN_1":     LedProfile("2",   0, 255,   0,  99,  5, "Verde Neón"),
        "PUSH_BTN_2":     LedProfile("3", 255, 255,   0,  99,  5, "Amarillo Intenso"),
        "MAGNETIC":       LedProfile("4", 180,   0, 255,  99,  5, "Morado Fuerte"),
        "ROTARY_LEFT":    LedProfile("5", 255,  80,   0,  99,  3, "Naranja Fuerte"),
        "ROTARY_RIGHT":   LedProfile("6",   0, 255, 255,  99,  3, "Cyan Brillante"),
        "PRESENCE":       LedProfile("7", 255, 255, 255,  99,  5, "Blanco Full"),
        "AIRBUTTON_FAR":  LedProfile("8", 255,   0, 150,  99,  5, "Rosa Fuerte"),
        "AIRBUTTON_NEAR": LedProfile("9",   0, 255, 180,  99,  5, "Turquesa Fuerte"),
        "IDLE":           LedProfile("A",   0,  30, 100,  20, 10, "Azul Tenue"),
    }

    def __init__(self) -> None:
        # Injected by SerialController once the port is open
        self._ser: serial.Serial | None = None
        # Active sensor key — used for deduplication in set_sensor_color()
        self._current_key: str | None = None

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def init_colors(self) -> None:
        """
        Program every custom RGB color into the XW-L56 at startup.

        Must be called once after the serial port is open.  The device
        resets all label slots to its default palette on power-cycle, so
        this method must run again on each application start.
        """
        log.info("LED: programando colores personalizados en el dispositivo...")
        for key, p in self.SENSOR_LED_MAP.items():
            self.set_custom_color(p.label, p.r, p.g, p.b)
            log.info(
                f"  Slot {p.label} ← {key:16s} RGB({p.r:3d},{p.g:3d},{p.b:3d})  [{p.name}]"
            )
        log.info("LED: colores listos.")

    # ------------------------------------------------------------------
    # Internal: low-level serial write
    # ------------------------------------------------------------------

    def _send(self, payload: str) -> None:
        """Wrap payload in X008B[...] and write to serial."""
        if self._ser is None or not self._ser.is_open:
            log.warning("LED: serial no disponible, comando descartado.")
            return
        cmd = f"X{self.LED_ADDRESS}B[{payload}]\r\n"
        log.info(f"LED << {cmd.strip()}")
        self._ser.write(cmd.encode())

    # ------------------------------------------------------------------
    # Low-level command builders  (protocol layer)
    # ------------------------------------------------------------------

    def set_custom_color(self, label: str, r: int, g: int, b: int) -> None:
        """
        Program an exact RGB color into a label slot (0-F).

        Does NOT change the current LED output — a ramp/pulse/wave command
        that references this label must be sent afterwards.
        Slots revert to device defaults after a power cycle.
        """
        self._send(f"1{label}{r:02X}{g:02X}{b:02X}")

    def set_single_ramp(
        self,
        intensity:   int,
        color_label: str = "0",
        ramp_time:   int = 5,
    ) -> None:
        """
        Set all LEDs to one color/brightness with a smooth ramp transition.

        Args:
            intensity:   0-99  (99 = maximum brightness)
            color_label: Hex char 0-F
            ramp_time:   0-99  in units of 0.1 s
        """
        intensity = max(0, min(99, intensity))
        ramp_time = max(0, min(99, ramp_time))
        self._send(f"2{intensity:02d}{color_label}{ramp_time:02d}")

    def set_pulse(
        self,
        intensity1: int,
        color1:     str,
        time1:      int,
        intensity2: int,
        color2:     str,
        time2:      int,
        repeats:    int = 0,
        ramp_time:  int = 10,
    ) -> None:
        """
        Pulsing fade-in / fade-out between two states.

        Args:
            intensity1/2: 0-99
            color1/2:     Hex char 0-F
            time1/2:      02-99 × 0.1 s (includes ramp time)
            repeats:      00 = infinite
            ramp_time:    02-99 × 0.1 s  (must be ≤ time1 and time2)
        """
        payload = (
            f"3{intensity1:02d}{color1}{time1:02d}"
            f"010"                             # PP=01 fixed, O=0 fixed
            f"{intensity2:02d}{color2}{time2:02d}"
            f"{repeats:02d}{ramp_time:02d}"
        )
        self._send(payload)

    def set_wave(
        self,
        intensity1: int,
        color1:     str,
        duration:   int,
        program:    str,
        direction:  int,
        intensity2: int,
        color2:     str,
        leds:       int = 5,
    ) -> None:
        """
        Animated wave pattern.

        Args:
            intensity1/2: 0-99
            color1/2:     Hex char 0-F
            duration:     02-99 × 0.1 s
            program:      "00"=sym-sine / "01"=asym-sine / "51"-"59"=discrete
            direction:    1=left  2=right  3=outward  4=inward
            leds:         02-99 (minimum 02 for XW-L5)
        """
        payload = (
            f"4{intensity1:02d}{color1}{duration:02d}"
            f"{program}{direction}"
            f"{intensity2:02d}{color2}"
            f"00{leds:02d}"                   # UU=00 reserved
        )
        self._send(payload)

    # ------------------------------------------------------------------
    # Application-level helpers  (sensor layer)
    # ------------------------------------------------------------------

    def set_sensor_color(self, sensor_key: str) -> None:
        """
        Activate the pre-defined LED color for a sensor event.

        Looks up sensor_key in SENSOR_LED_MAP and sends a single-ramp
        command using the pre-programmed color slot.
        Repeated calls with the same key are silently ignored.
        """
        if sensor_key == self._current_key:
            return  # Already active — skip to avoid flooding the bus

        profile = self.SENSOR_LED_MAP.get(sensor_key)
        if profile is None:
            log.warning(f"LED: sensor key desconocido '{sensor_key}'")
            return

        log.info(f"LED → {sensor_key} → {profile.name}")
        self.set_single_ramp(profile.intensity, profile.label, profile.ramp_time)
        self._current_key = sensor_key

    def set_idle(self) -> None:
        """Return LED to soft idle state (shown during the loop video)."""
        self.set_sensor_color("IDLE")

    def apply_rotary(self, value: int) -> None:
        """
        Rotary encoder: fixed color per range with dynamic brightness.

        The COLOR is determined by the encoder range (naranja / cyan),
        the BRIGHTNESS is scaled linearly across the position within
        each range.  Every position change sends a new command (no
        deduplication), because each position is a distinct light level.

        Range  1-10  → Naranja Fuerte (slot 5), brightness 10 → 99
        Range 11-20  → Cyan Brillante (slot 6), brightness 10 → 99
        """
        if 1 <= value <= 10:
            key       = "ROTARY_LEFT"
            intensity = int(10 + (value - 1) * (89 / 9))
        elif 11 <= value <= 20:
            key       = "ROTARY_RIGHT"
            intensity = int(10 + (value - 11) * (89 / 9))
        else:
            return

        profile = self.SENSOR_LED_MAP[key]
        log.info(
            f"LED → {key} → {profile.name}  "
            f"(pos={value}, intensidad={intensity:02d})"
        )
        self.set_single_ramp(intensity, profile.label, profile.ramp_time)
        self._current_key = key   # keep dedup context updated


# ===========================================================================
# VideoController
# ===========================================================================
class VideoController:
    """
    Full-screen OpenCV video playback — optimized for immediate response.

    Architecture
    ────────────
    - request() enqueues a path AND fires a wakeup Event.
    - The playback loop waits between frames using Event.wait(timeout)
      instead of cv2.waitKey(ms).  This means a new request interrupts
      the inter-frame sleep immediately (microsecond latency), rather than
      waiting up to one full frame interval (25-33 ms) before reacting.
    - cv2.waitKey(1) is still called every frame to pump the GUI event
      queue (required by OpenCV's window system).
    - Frame rate is derived from the video's own FPS metadata so every
      clip plays at its correct speed.

    Latency model
    ─────────────
    Old design  : up to waitKey(25) ms = ~25 ms per frame before reacting
    New design  : Event.wait() interrupted by wakeup.set() in < 1 ms
                  + cap.release() + VideoCapture() open time (~50-100 ms)
    """

    def __init__(
        self,
        stop_event:     threading.Event,
        on_loop_return: Callable[[], None] | None = None,
    ) -> None:
        self._stop           = stop_event
        self._on_loop_return = on_loop_return
        # Queue holds at most the latest pending path; older requests are
        # discarded — we only care about the most recent state.
        self._queue  = queue.Queue()
        # Wakeup event: set by request() to interrupt the inter-frame sleep
        # and force the loop to check for a new path immediately.
        self._wakeup = threading.Event()

    def request(self, path: str) -> None:
        """
        Request an immediate video switch (thread-safe, non-blocking).

        Drains any previous pending request so the video thread always
        picks up the latest state, never a stale intermediate value.
        Fires _wakeup to interrupt the current inter-frame sleep.
        """
        print(f"[VIDEO] request() → {path}")
        if not os.path.exists(path):
            print(f"[VIDEO] ADVERTENCIA: archivo no existe → {path}")

        # Drain stale pending requests
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        self._queue.put_nowait(path)
        self._wakeup.set()   # ← wake up video thread NOW

    def _get_pending(self) -> str | None:
        """Drain the queue and return the latest path, or None."""
        latest = None
        while True:
            try:
                latest = self._queue.get_nowait()
            except queue.Empty:
                break
        return latest

    def _open(self, path: str) -> tuple[cv2.VideoCapture, float]:
        """Open a VideoCapture and return (cap, frame_interval_seconds)."""
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print(f"[VIDEO] ERROR: no se pudo abrir → {path}")
            return cap, 1.0 / 30.0
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0
        return cap, 1.0 / fps

    def run(self) -> None:
        if not os.path.exists(VIDEO_LOOP):
            print(f"[VIDEO] ERROR CRITICO: loop no existe → {VIDEO_LOOP}")
            log.error(f"No se pudo abrir el video de loop: {VIDEO_LOOP}")
            self._stop.set()
            return

        cap, frame_interval = self._open(VIDEO_LOOP)
        if not cap.isOpened():
            log.error(f"No se pudo abrir el video de loop: {VIDEO_LOOP}")
            self._stop.set()
            return

        cv2.namedWindow("Video", cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("Video", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

        current = VIDEO_LOOP
        print(f"[VIDEO] Iniciando: {current}  ({1/frame_interval:.1f} fps)")

        while not self._stop.is_set():

            # ── PRIORIDAD 1: cambio de video inmediato ─────────────────
            # Wakeup was set by request() — check queue before anything else.
            next_path = self._get_pending()
            if next_path is not None and next_path != current:
                print(f"[VIDEO] CAMBIO INMEDIATO: {current} → {next_path}")
                log.info(f"Reproduciendo: {next_path}")
                cap.release()
                current = next_path
                cap, frame_interval = self._open(current)
                if not cap.isOpened():
                    current = VIDEO_LOOP
                    cap, frame_interval = self._open(VIDEO_LOOP)
                else:
                    print(f"[VIDEO] REPRODUCIENDO: {current}  ({1/frame_interval:.1f} fps)")

            # ── Leer frame ─────────────────────────────────────────────
            ret, frame = cap.read()

            if not ret:
                # End of clip — back to loop (or restart loop)
                if current != VIDEO_LOOP:
                    print(f"[VIDEO] Fin de clip → loop")
                    log.info("Fin de clip, volviendo al loop.")
                    cap.release()
                    current = VIDEO_LOOP
                    cap, frame_interval = self._open(VIDEO_LOOP)
                    if self._on_loop_return is not None:
                        self._on_loop_return()
                else:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            # ── Mostrar frame ──────────────────────────────────────────
            cv2.imshow("Video", frame)

            # cv2.waitKey(1): minimum call required to pump OpenCV's GUI
            # event queue (window display, keyboard detection).
            # Does NOT control frame rate — that is handled by Event.wait below.
            if cv2.waitKey(1) & 0xFF == ord("q"):
                self._stop.set()
                break

            # ── Control de FPS + espera interrumpible ──────────────────
            # Sleep for the remainder of the frame interval.
            # If request() fires during this sleep, _wakeup.set() wakes
            # us up immediately — no waiting for the next frame boundary.
            self._wakeup.clear()
            sleep_time = frame_interval - 0.001   # 1 ms headroom for overhead
            if sleep_time > 0:
                self._wakeup.wait(timeout=sleep_time)
            # If wakeup was set, _get_pending() at the top will pick up the
            # new request on the very next iteration.

        cap.release()
        cv2.destroyAllWindows()
        log.info("VideoController detenido.")


# ===========================================================================
# SerialController
# ===========================================================================
class SerialController:
    """
    Detects the serial port automatically, reads incoming X-talk frames,
    and dispatches sensor events to VideoController and LedController.

    RFID state machine
    ──────────────────
    Two boolean flags track the independent presence of each RFID tag:

        _rfid1  True while tag PU001 is detected on the reader
        _rfid2  True while tag PU002 is detected on the reader

    State transitions and their video/LED outcomes:

        IDLE  (both False)
          + XR[PU001]  →  ONLY1  → video_rfid_1,   LED Rojo
          + XR[PU002]  →  ONLY2  → video_rfid_2,   LED Azul

        ONLY1 (rfid1=True, rfid2=False)
          + XR[PU002]  →  BOTH   → video_rfid_1_2, LED Azul (nuevo)
          + removal    →  IDLE   → VIDEO_LOOP,      LED Idle

        ONLY2 (rfid1=False, rfid2=True)
          + XR[PU001]  →  BOTH   → video_rfid_2_1, LED Rojo (nuevo)
          + removal    →  IDLE   → VIDEO_LOOP,      LED Idle

        BOTH  (rfid1=True, rfid2=True)
          + removal 1  →  ONLY2  → video_rfid_2,   LED Azul
          + removal 2  →  ONLY1  → video_rfid_1,   LED Rojo
          + all gone   →  IDLE   → VIDEO_LOOP,      LED Idle

    Removal messages
    ─────────────────
    XR[P0000] is treated as "no tag present" and clears all active flags.
    With a single reader this is correct.  If the installation uses two
    separate readers (one per product), the removal message for each must
    be disambiguated here — adjust _handle_rfid() accordingly.
    """

    def __init__(
        self,
        stop_event:   threading.Event,
        video_ctrl:   VideoController,
        led_ctrl:     LedController,
        baud_rate:    int = BAUD_RATE,
        port_keyword: str = PORT_KEYWORD,
    ) -> None:
        self._stop    = stop_event
        self._video   = video_ctrl
        self._led     = led_ctrl
        self._baud    = baud_rate
        self._keyword = port_keyword
        self._ser: serial.Serial | None = None

        # RFID state machine — independent presence flags
        self._rfid1: bool = False
        self._rfid2: bool = False

    # ------------------------------------------------------------------
    # Port auto-detection
    # ------------------------------------------------------------------

    def _find_port(self) -> str | None:
        """Return the first port whose description contains PORT_KEYWORD."""
        for info in serial.tools.list_ports.comports():
            if self._keyword.lower() in info.description.lower():
                return info.device
        return None

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        port = self._find_port()
        if port is None:
            log.error(
                f"No se encontró ningún puerto cuya descripción contenga "
                f"'{self._keyword}'. "
                "Verifica que el adaptador USB-serial Prolific esté conectado."
            )
            self._stop.set()
            return

        log.info(f"Puerto detectado: {port}")
        try:
            self._ser = serial.Serial(port, self._baud, timeout=1)
            log.info(f"Escuchando en {port} a {self._baud} baudios...")

            # Inject serial into LED controller and program all custom colors
            self._led._ser = self._ser
            self._led.init_colors()

            while not self._stop.is_set():
                if self._ser.in_waiting > 0:
                    raw = self._ser.readline().decode(errors="ignore").strip()
                    if raw:
                        # Sanitize: remove all non-printable characters that
                        # strip() does not catch (e.g. \x00, \x01, etc.)
                        raw = "".join(c for c in raw if c.isprintable())
                        if raw:
                            self._dispatch(raw)

        except serial.SerialException as e:
            log.error(f"Error en puerto serial: {e}")
        finally:
            self._close()

    def _close(self) -> None:
        if self._ser and self._ser.is_open:
            self._ser.close()
            log.info("Puerto serial cerrado.")

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    def _dispatch(self, line: str) -> None:
        """Route an X-talk line to the appropriate sensor handler."""

        if line.startswith("XR"):
            # X-talk 007 — RFID (XR-DR1)
            log.info(f"RFID      >> {line}")
            self._handle_rfid(line)

        elif line.startswith("X001A"):
            # X-talk 001 — Push buttons (XT-B4N6)
            log.info(f"PushBtn   >> {line}")
            self._handle_push_button(line)

        elif line.startswith("X002B"):
            # X-talk 002 — Rotary encoder (XDW-A50)
            log.info(f"Rotary    >> {line}")
            self._handle_rotary(line)

        elif line.startswith("X003A"):
            # X-talk 003 — Magnetic sensor (XSW-X36)
            self._handle_magnetic(line)

        elif line.startswith("X004B"):
            # X-talk 004 — AirButton (XT-EF30)
            log.info(f"AirButton >> {line}")
            self._handle_airbutton(line)

        elif line.startswith("X005B"):
            # X-talk 005 — Presence sensor (XY-240)
            log.info(f"Presence  >> {line}")
            self._handle_presence(line)

    # ------------------------------------------------------------------
    # RFID state machine
    # ------------------------------------------------------------------

    def _handle_rfid(self, line: str) -> None:
        """
        Update RFID boolean flags based on the incoming message, then
        call _resolve_rfid_state() to apply the correct video and LED.

        Detection:
          XR[PU001] → rfid1 = True
          XR[PU002] → rfid2 = True

        Removal (single-reader setup):
          XR[P0000] → clear all flags
          (Adjust below for dual-reader installations)
        """
        # Extra safety: strip again and sanitize in case something slipped through
        line = line.strip()

        print(f"[RFID] _handle_rfid llamado con: repr={repr(line)}")

        prev1, prev2 = self._rfid1, self._rfid2

        if line == "XR[PU001]":
            print("[RFID] Match: XR[PU001] → rfid1 = True")
            self._rfid1 = True
        elif line == "XR[PU002]":
            print("[RFID] Match: XR[PU002] → rfid2 = True")
            self._rfid2 = True
        elif line == "XR[PB001]":
            # Tag 1 removed from reader
            print("[RFID] Match: XR[PB001] → rfid1 = False")
            self._rfid1 = False
        elif line == "XR[PB002]":
            # Tag 2 removed from reader
            print("[RFID] Match: XR[PB002] → rfid2 = False")
            self._rfid2 = False
        elif line == "XR[P0000]":
            # Fallback: clear all flags (single-reader removal)
            print("[RFID] Match: XR[P0000] → limpiando ambos flags")
            self._rfid1 = False
            self._rfid2 = False
        else:
            print(f"[RFID] NO MATCH para: repr={repr(line)} — ignorado")
            return  # Unrecognised RFID message — ignore

        print(f"[RFID] Estado anterior → rfid1: {prev1}, rfid2: {prev2}")
        print(f"[RFID] Estado nuevo    → rfid1: {self._rfid1}, rfid2: {self._rfid2}")

        # Skip resolution if state did not actually change
        if self._rfid1 == prev1 and self._rfid2 == prev2:
            print("[RFID] Estado sin cambio — omitiendo resolución")
            return

        self._resolve_rfid_state(prev1, prev2)

    def _resolve_rfid_state(self, prev1: bool, prev2: bool) -> None:
        """
        Determine the correct video and LED output based on the current
        RFID state and the previous state (to detect transition direction).

        Called only when the state has actually changed.
        """
        now1, now2 = self._rfid1, self._rfid2

        print(f"[RFID] _resolve_rfid_state → now1={now1}, now2={now2}, prev1={prev1}, prev2={prev2}")
        log.info(
            f"RFID estado: PU001={'ON ' if now1 else 'OFF'} | "
            f"PU002={'ON ' if now2 else 'OFF'}"
        )

        if now1 and now2:
            # ── BOTH active ──────────────────────────────────────────────
            if prev1 and not prev2:
                # Was ONLY1, PU002 just arrived → Coca+Sprite transition
                video_name = VIDEO_RFID_1_2
                print(f"[RFID] Transición PU001→PU001+PU002 | VIDEO CAMBIADO A: {video_name}")
                log.info("RFID transición: PU001 → PU001+PU002")
                self._video.request(video_name)
                self._led.set_sensor_color("RFID_2")   # color of arriving tag
            elif prev2 and not prev1:
                # Was ONLY2, PU001 just arrived → Sprite+Coca transition
                video_name = VIDEO_RFID_2_1
                print(f"[RFID] Transición PU002→PU001+PU002 | VIDEO CAMBIADO A: {video_name}")
                log.info("RFID transición: PU002 → PU001+PU002")
                self._video.request(video_name)
                self._led.set_sensor_color("RFID_1")   # color of arriving tag
            else:
                print("[RFID] Ya ambos activos — manteniendo video actual")
            # else: already BOTH — maintain current video, no change

        elif now1 and not now2:
            # ── Only PU001 ───────────────────────────────────────────────
            video_name = VIDEO_RFID_1
            print(f"[RFID] Solo PU001 activo | VIDEO CAMBIADO A: {video_name}")
            log.info("RFID: solo PU001 activo")
            self._video.request(video_name)
            self._led.set_sensor_color("RFID_1")

        elif now2 and not now1:
            # ── Only PU002 ───────────────────────────────────────────────
            video_name = VIDEO_RFID_2
            print(f"[RFID] Solo PU002 activo | VIDEO CAMBIADO A: {video_name}")
            log.info("RFID: solo PU002 activo")
            self._video.request(video_name)
            self._led.set_sensor_color("RFID_2")

        else:
            # ── Both inactive / IDLE ─────────────────────────────────────
            video_name = VIDEO_LOOP
            print(f"[RFID] Ninguno activo — volviendo al loop | VIDEO CAMBIADO A: {video_name}")
            log.info("RFID: ninguno activo — volviendo al loop")
            self._video.request(video_name)
            self._led.set_idle()

    # ------------------------------------------------------------------
    # Other sensor handlers
    # ------------------------------------------------------------------

    def _handle_push_button(self, line: str) -> None:
        if line == "X001A[17]":
            self._video.request(VIDEO_PUSH_BUTTON1)
            self._led.set_sensor_color("PUSH_BTN_1")
        elif line == "X001A[3]":
            self._video.request(VIDEO_PUSH_BUTTON2)
            self._led.set_sensor_color("PUSH_BTN_2")

    def _handle_rotary(self, line: str) -> None:
        """Parse Dr=XX, update video and LED (color + dynamic brightness)."""
        try:
            value = int(line.split("Dr=")[1].rstrip("]"))
        except (IndexError, ValueError):
            log.warning(f"Rotary: no se pudo parsear '{line}'")
            return

        if 1 <= value <= 10:
            self._video.request(VIDEO_LEFT)
        elif 11 <= value <= 20:
            self._video.request(VIDEO_RIGHT)

        self._led.apply_rotary(value)

    def _handle_magnetic(self, line: str) -> None:
        # X003A[3] = contact  |  X003A[4] = release — only react to contact
        if line == "X003A[3]":
            log.info(f"Magnetic  >> {line}")
            self._video.request(VIDEO_MAGNETIC_SENSOR)
            self._led.set_sensor_color("MAGNETIC")

    def _handle_airbutton(self, line: str) -> None:
        if line == "X004B[Bs=FAR]":
            self._video.request(VIDEO_FAR)
            self._led.set_sensor_color("AIRBUTTON_FAR")
        elif line == "X004B[Bs=NEAR]":
            self._video.request(VIDEO_CLOSE)
            self._led.set_sensor_color("AIRBUTTON_NEAR")

    def _handle_presence(self, line: str) -> None:
        if line == "X005B[Dz=AB]":
            self._video.request(VIDEO_PRESENCE_SENSOR)
            self._led.set_sensor_color("PRESENCE")


# ===========================================================================
# AppController — orchestrator
# ===========================================================================
class AppController:
    """Wires all sub-controllers together and manages thread lifecycle."""

    def __init__(self) -> None:
        self._stop  = threading.Event()
        self._led   = LedController()

        # Pass the LED idle callback so VideoController automatically
        # resets the LED whenever any sensor clip ends and the loop resumes.
        self._video = VideoController(
            stop_event=self._stop,
            on_loop_return=self._led.set_idle,
        )

        self._serial = SerialController(
            stop_event=self._stop,
            video_ctrl=self._video,
            led_ctrl=self._led,
        )

    def run(self) -> None:
        serial_thread = threading.Thread(
            target=self._serial.run,
            name="SerialThread",
            daemon=True,
        )
        video_thread = threading.Thread(
            target=self._video.run,
            name="VideoThread",
            daemon=True,
        )

        serial_thread.start()
        video_thread.start()

        try:
            # Keep main thread alive; Ctrl+C raises KeyboardInterrupt here
            while not self._stop.is_set():
                serial_thread.join(timeout=0.5)
                if not serial_thread.is_alive():
                    break
        except KeyboardInterrupt:
            log.info("Ctrl+C detectado — cerrando...")
            self._stop.set()
        finally:
            serial_thread.join(timeout=2)
            video_thread.join(timeout=2)
            log.info("Aplicación cerrada correctamente.")


# ===========================================================================
# Entry point
# ===========================================================================
if __name__ == "__main__":
    try:
        AppController().run()
    except KeyboardInterrupt:
        pass
    sys.exit(0)
