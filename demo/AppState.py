import threading

import constants as cts

class AppState:
    def __init__(self):
        self._lock = threading.Lock()

        self.sensor = cts.NONE
        self.value = None
        self.updated = False

        self.rfids = []
        self.updated_rfids = False

        self.updated_arduino = False
        self.message = ""

    # sensors

    def get_updated(self) -> bool:
        with self._lock:
            return self.updated

    def get_status(self) -> str:
        with self._lock:
            self.updated = False
            return self.sensor, self.value

    def set_status(self, new_sensor: int, new_value: int):
        with self._lock:
            print(new_value)
            self.sensor = new_sensor
            self.value = new_value
            self.updated = True
            self.updated_rfids = False


    # rfids

    def get_updated_rfids(self) -> bool:
        with self._lock:
            return self.updated_rfids

    def get_rfids(self):
        with self._lock:
            self.updated_rfids = False
            return self.rfids

    def push_rfid(self, value):
        with self._lock:
            if value not in self.rfids:
                self.rfids.append(value)
                self.updated_rfids = True
                self.updated = False

    def pop_rfid(self, value):
        with self._lock:
            if value in self.rfids:
                self.rfids.remove(value)
                self.updated_rfids = True
                self.updated = False

    # get arduino

    def get_updated_arduino(self) -> bool:
            with self._lock:
                return self.updated_arduino

    def get_status_arduino(self) -> str:
        with self._lock:
            self.updated_arduino = False
            return self.message

    def set_status_arduino(self, new_value: int):
        with self._lock:
            self.message = new_value
            self.updated_arduino = True
