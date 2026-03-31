from PyQt5.QtCore import QThread, pyqtSignal

try:
    import serial
except Exception:
    serial = None


class PumpWorker(QThread):
    flow_received = pyqtSignal(float)   # vazão em m³/s
    raw_received = pyqtSignal(str)
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, port="COM5", baudrate=9600, parent=None):
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
            self.status.emit(f"Bomba conectada em {self.port}")
        except Exception as e:
            self.error.emit(f"Falha ao abrir porta da bomba ({self.port}): {e}")
            return

        while self._running:
            try:
                line = self._ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue

                self.raw_received.emit(line)

                flow_m3s = self.parse_flow(line)
                if flow_m3s is not None:
                    self.flow_received.emit(flow_m3s)

            except Exception as e:
                self.error.emit(f"Erro lendo bomba: {e}")
                break

        self._close_serial()
        self.status.emit("Bomba desconectada")

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
    def parse_flow(line: str):
        """
        Tenta extrair vazão da string e converter para m³/s.

        Exemplos aceitos:
        - FLOW: 1.23
        - FLOW: 1.23 ml/min
        - 1.23 ml/min
        - Q=0.5 mL/min
        """
        s = line.strip().lower().replace(",", ".")

        # procura primeiro por ml/min
        import re
        m = re.search(r'([-+]?\d*\.?\d+)\s*(ml/min|mlm|min)', s)
        if m:
            value_ml_min = float(m.group(1))
            return value_ml_min * 1e-6 / 60.0

        # tenta algo do tipo "flow: 1.23"
        m = re.search(r'flow\s*[:=]\s*([-+]?\d*\.?\d+)', s)
        if m:
            value_ml_min = float(m.group(1))
            return value_ml_min * 1e-6 / 60.0

        return None