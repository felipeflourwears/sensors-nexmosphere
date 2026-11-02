import threading

class AppState:
    def __init__(self):
        self._lock = threading.Lock()
        self._sensor = "NONE"
        self.value = None

    def set_status(self, new_sensor: str, new_value: int):
        with self._lock:
            self._sensor = new_sensor
            self.value = new_value

    def get_status(self) -> str:
        with self._lock:
            return self._sensor, self.value
