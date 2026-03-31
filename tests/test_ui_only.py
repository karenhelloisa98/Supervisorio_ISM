import sys
import random
from datetime import datetime

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from ui_main import MainWidget
from splash import SplashWidget


def main():
    app = QApplication(sys.argv)

    # Splash
    splash = SplashWidget()
    splash.show()

    def open_main():
        splash.close()

        channel_names = ["P1", "P2", "P3", "P4", "DP"]
        w = MainWidget(channel_names)
        w.show()

        # Simulação 10 Hz (100 ms)
        timer = QTimer()
        timer.setInterval(100)

        def fake_update():
            # valores simulados (0–10000 bar)
            eng = [random.uniform(0, 10000) for _ in range(5)]
            mA = [4 + (v / 10000) * 16 for v in eng]
            status = ["OK"] * 5
            ts = datetime.now().isoformat(timespec="milliseconds")
            w.update_data(ts, mA, eng, status)

        timer.timeout.connect(fake_update)

        # Botões
        def on_start():
            if not timer.isActive():
                timer.start()
            w.set_running(True)

        def on_stop():
            if timer.isActive():
                timer.stop()
            w.set_running(False)

        w.btn_start.clicked.connect(on_start)
        w.btn_stop.clicked.connect(on_stop)

        # Começa parado
        w.set_running(False)

        # manter referências vivas
        app._main_window = w
        app._timer = timer

    # Mostra splash por 2 segundos
    QTimer.singleShot(2000, open_main)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()