from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer

from logger_csv import CsvLogger
from calibration_store import load_calibration, apply_channel_cal, ensure_channel


@dataclass
class ChannelCfg:
    name: str
    physical: str
    lrv: float
    urv: float
    unit: str = "bar"


def mA_to_eng(mA: float, lrv: float, urv: float) -> float:
    p = (mA - 4.0) / 16.0
    return lrv + p * (urv - lrv)


class DaqWorker(QObject):
    data = pyqtSignal(dict)
    error = pyqtSignal(str)
    started = pyqtSignal()
    stopped = pyqtSignal()

    def __init__(self, config_path: str, calibration_path: str = "calibration.json"):
        super().__init__()
        self.config_path = config_path
        self.calibration_path = calibration_path

        self._task = None
        self._reader = None
        self._timer: Optional[QTimer] = None
        self._logger: Optional[CsvLogger] = None

        self._cfg: Dict[str, Any] = {}
        self._channels: List[ChannelCfg] = []
        self._rate_hz: float = 10.0

        self._open_loop_low = 3.6
        self._overrange_high = 21.0

        self._cal: Dict[str, Any] = {}

    def _load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            self._cfg = json.load(f)

        self._rate_hz = float(self._cfg.get("sample_rate_hz", 10))

        limits = self._cfg.get("limits_mA", {})
        self._open_loop_low = float(limits.get("open_loop_low_mA", 3.6))
        self._overrange_high = float(limits.get("overrange_high_mA", 21.0))

        self._channels = []
        for ch in self._cfg["channels"]:
            self._channels.append(
                ChannelCfg(
                    name=ch["name"],
                    physical=ch["physical"],
                    lrv=float(ch["lrv"]),
                    urv=float(ch["urv"]),
                    unit=ch.get("unit", "bar")
                )
            )

    @pyqtSlot()
    def start(self):
        try:
            # IMPORT AQUI (melhor para PyInstaller)
            import nidaqmx
            from nidaqmx.constants import AcquisitionType
            from nidaqmx.stream_readers import AnalogMultiChannelReader

            self._load_config()

            # Calibração
            self._cal = load_calibration(self.calibration_path)
            for ch in self._channels:
                ensure_channel(self._cal, ch.name)

            # Task
            self._task = nidaqmx.Task(new_task_name="PressureSupervisor")
            for ch in self._channels:
                self._task.ai_channels.add_ai_current_chan(
                    physical_channel=ch.physical,
                    name_to_assign_to_channel=ch.name,
                    min_val=0.0,
                    max_val=0.02
                )

            self._task.timing.cfg_samp_clk_timing(
                rate=self._rate_hz,
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=int(max(self._rate_hz, 10))
            )

            self._reader = AnalogMultiChannelReader(self._task.in_stream)

            # Logger CSV (log corrigido)
            csv_cfg = self._cfg.get("csv", {})
            if bool(csv_cfg.get("enabled", True)):
                folder = csv_cfg.get("folder", "logs")
                prefix = csv_cfg.get("file_prefix", "pressao")
                self._logger = CsvLogger(folder, prefix, [c.name for c in self._channels])

            self._timer = QTimer()
            self._timer.setInterval(int(1000 / self._rate_hz))
            self._timer.timeout.connect(self._read_once)

            self._task.start()
            self._timer.start()
            self.started.emit()

        except Exception as e:
            self.error.emit(f"Falha ao iniciar DAQ: {e}")

    @pyqtSlot()
    def stop(self):
        try:
            if self._timer:
                self._timer.stop()
                self._timer = None

            if self._task:
                try:
                    self._task.stop()
                except Exception:
                    pass
                self._task.close()
                self._task = None

            if self._logger:
                self._logger.close()
                self._logger = None

            self.stopped.emit()

        except Exception as e:
            self.error.emit(f"Falha ao parar DAQ: {e}")

    def _read_once(self):
        if not self._reader or not self._task:
            return

        try:
            n_ch = len(self._channels)
            dataA = np.zeros((n_ch, 1), dtype=np.float64)

            self._reader.read_many_sample(
                data=dataA,
                number_of_samples_per_channel=1,
                timeout=0.3
            )

            currents_mA = (dataA[:, 0] * 1000.0).tolist()

            eng_raw = []
            eng_corr = []
            status = []

            for i, ch in enumerate(self._channels):
                mA = float(currents_mA[i])

                if mA < self._open_loop_low:
                    status.append("OPEN_LOOP")
                elif mA > self._overrange_high:
                    status.append("OVERRANGE")
                else:
                    status.append("OK")

                raw = float(mA_to_eng(mA, ch.lrv, ch.urv))
                corr = float(apply_channel_cal(self._cal, ch.name, raw))

                eng_raw.append(raw)
                eng_corr.append(corr)

            ts = datetime.now().isoformat(timespec="milliseconds")

            payload = {
                "ts": ts,
                "mA": currents_mA,
                "eng_raw": eng_raw,
                "eng": eng_corr,
                "status": status
            }

            if self._logger:
                self._logger.write_row(ts, currents_mA, eng_corr)

            self.data.emit(payload)

        except Exception as e:
            self.error.emit(f"Erro de leitura: {e}")