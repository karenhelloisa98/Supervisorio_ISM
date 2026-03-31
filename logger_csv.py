import csv
import os
from datetime import datetime

class CsvLogger:
    def __init__(self, folder: str, file_prefix: str, channel_names: list[str]):
        os.makedirs(folder, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = os.path.join(folder, f"{file_prefix}_{ts}.csv")

        self.file = open(self.path, "w", newline="", encoding="utf-8")
        self.writer = csv.writer(self.file)

        header = ["timestamp_iso"] + [f"{n}_mA" for n in channel_names] + [f"{n}_eng" for n in channel_names]
        self.writer.writerow(header)
        self.file.flush()

    def write_row(self, timestamp_iso: str, currents_mA: list[float], eng_values: list[float]):
        self.writer.writerow([timestamp_iso] + currents_mA + eng_values)
        self.file.flush()

    def close(self):
        try:
            self.file.close()
        except Exception:
            pass