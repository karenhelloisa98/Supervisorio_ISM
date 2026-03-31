import sys 
import json 
import os 
import traceback 

from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog
from PyQt5.QtCore import QThread

from tela_login import Login
from mainwindow import TelaPrincipal 
from daq_worker import DaqWorker 
from pump_worker import PumpWorker 
from oven_worker import OvenWorker 

def resource_path(relative_path: str) -> str: 
    base = getattr(sys, "_MEIPASS", os.path.abspath(".")) 
    return os.path.join(base, relative_path)

def load_channel_names(config_path: str):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return [c["name"] for c in cfg["channels"]]

def show_fatal_error(title: str, err: Exception): 
    msg = f"{title}\n\n{err}\n\n{traceback.format_exc()}"
    QMessageBox.critical(None, "Erro Crítico", msg)

def main():
    app = QApplication(sys.argv) 
    app.setQuitOnLastWindowClosed(False) 

    tela_login = Login()
    
    if tela_login.exec_() == QDialog.Accepted:
        try: 
            config_path = resource_path("config.json") 
            channel_names = load_channel_names(config_path) 

            w = TelaPrincipal(channel_names) 

            # ===== CONFIGURAÇÃO DO DAQ (Thread) =====
            thread_daq = QThread() 
            worker_daq = DaqWorker(config_path) 
            worker_daq.moveToThread(thread_daq) 

            def on_start():
                if not thread_daq.isRunning():
                    thread_daq.start()
                w.set_running(True)

            def on_stop():
                worker_daq.stop()
                w.set_running(False)

            # Conexões da Interface
            w.btn_start.clicked.connect(on_start) 
            w.btn_stop.clicked.connect(on_stop)   

            # Eventos do Worker/Thread
            thread_daq.started.connect(worker_daq.start) 
            worker_daq.started.connect(lambda: w.set_running(True)) 
            worker_daq.stopped.connect(lambda: w.set_running(False)) 
            worker_daq.stopped.connect(thread_daq.quit) 

            # Dados e Erros
            worker_daq.data.connect(w.update_data) 
            worker_daq.error.connect(w.show_error) 
            worker_daq.error.connect(lambda _: w.set_running(False)) 
            worker_daq.error.connect(thread_daq.quit) 

            # ===== CONFIGURAÇÃO DA BOMBA =====
            pump = PumpWorker(port="COM5", baudrate=9600) 
            pump.flow_received.connect(w.update_pump_flow)
            pump.raw_received.connect(w.update_pump_raw)
            pump.status.connect(w.update_pump_status)
            pump.error.connect(w.update_pump_error)

            w.btn_pump_connect.clicked.connect(pump.start) 
            w.btn_pump_disconnect.clicked.connect(pump.stop) 

            # ===== CONFIGURAÇÃO DA ESTUFA =====
            oven = OvenWorker(port="COM6", baudrate=9600) 
            oven.temp_received.connect(w.update_oven_temp)
            oven.raw_received.connect(w.update_oven_raw)
            oven.status.connect(w.update_oven_status)
            oven.error.connect(w.update_oven_error)

            w.btn_oven_connect.clicked.connect(oven.start) 
            w.btn_oven_disconnect.clicked.connect(oven.stop) 

            # ===== GERENCIAMENTO DE FECHAMENTO =====
            def shutdown():
                worker_daq.stop()
                thread_daq.quit()
                thread_daq.wait()
                pump.stop()
                oven.stop()

            app.aboutToQuit.connect(shutdown) 

            w.set_running(False) 
            w.show()

            app._w = w
            app._daq = thread_daq
            app._worker = worker_daq
            app._pump = pump
            app._oven = oven

            app.setQuitOnLastWindowClosed(True) 
            sys.exit(app.exec_())

        except Exception as e:
            show_fatal_error("Erro ao carregar o sistema principal", e)
            sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__": 
    main()