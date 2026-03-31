from PyQt5.QtCore import QThread, pyqtSignal

try:
    import serial
except Exception:
    serial = None


class OvenWorker(QThread):
    temp_received = pyqtSignal(float)   # °C
    raw_received = pyqtSignal(str)
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, port="COM6", baudrate=9600, parent=None):
        super().__init__(parent)
        self.port = port
        self.baudrate = baudrate
        self._running = False
        self._ser = None

    def run(self):
        if serial is None:
            self.error.emit("pyserial não está instalado.")
            return

        self._running = True

        try:
            self._ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.status.emit(f"Estufa conectada em {self.port}")
        except Exception as e:
            self.error.emit(f"Falha ao abrir porta da estufa ({self.port}): {e}")
            return

        while self._running:
            try:
                line = self._ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue

                self.raw_received.emit(line)

                temp_c = self.parse_temp(line)
                if temp_c is not None:
                    self.temp_received.emit(temp_c)

            except Exception as e:
                self.error.emit(f"Erro lendo estufa: {e}")
                break

        self._close_serial()
        self.status.emit("Estufa desconectada")

    def stop(self):
        self._running = False
        self.wait(1500)
        self._close_serial()

    def _close_serial(self):
        try:
            if self._ser and self._ser.is_open:
                self._ser.close()
        except Exception:
            pass
        self._ser = None

    @staticmethod
    def parse_temp(line: str):
        """
        Exemplos aceitos:
        TEMP: 45.2
        TEMP=45.2
        45.2 C
        PV:45.2
        """
        import re

        s = line.strip().lower().replace(",", ".")

        patterns = [
            r'temp\s*[:=]\s*([-+]?\d*\.?\d+)',
            r'pv\s*[:=]\s*([-+]?\d*\.?\d+)',
            r'([-+]?\d*\.?\d+)\s*°?c'
        ]

        for p in patterns:
            m = re.search(p, s)
            if m:
                return float(m.group(1))

        return None