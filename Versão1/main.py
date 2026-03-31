import sys 
import json 
import os 
import traceback 

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QThread, QTimer

from ui_main import MainWidget 
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
    QMessageBox.critical(None, "Erro", msg)

def main():
    app = QApplication(sys.argv) 
    app.setQuitOnLastWindowClosed(False) 
    def open_main(): 
        try: 
            config_path = resource_path("config.json") 
            channel_names = load_channel_names(config_path) 

            w = MainWidget(channel_names) 
            w.show() 

            # ===== DAQ =====
            thread = QThread() 
            worker = DaqWorker(config_path) 
            worker.moveToThread(thread) 

            def on_start():
                if not thread.isRunning():
                    thread.start()
                w.set_running(True)

            def on_stop():
                worker.stop()
                w.set_running(False)

            #CONECTAR SINAIS E SLOTS
            w.btn_start.clicked.connect(on_start) 
            w.btn_stop.clicked.connect(on_stop)   

            #CONECTAR EVENTOS DA THREAD/WORKER
            thread.started.connect(worker.start) 
            worker.started.connect(lambda: w.set_running(True)) 
            worker.stopped.connect(lambda: w.set_running(False)) 
            worker.stopped.connect(thread.quit) 

            #CONECTAR DADOS E ERROS
            worker.data.connect(w.update_data) 
            worker.error.connect(w.show_error) 
            worker.error.connect(lambda _: w.set_running(False)) 
            worker.error.connect(thread.quit) 

            #FECHAMENTO AO SAIR DO APP
            app.aboutToQuit.connect(worker.stop) 
            app.aboutToQuit.connect(thread.quit) 

            # ===== BOMBA =====
            #Atualiza a tela quando a bomba enviar informações de vazão, dado bruto, status, erro
            pump = PumpWorker(port="COM5", baudrate=9600) 
            pump.flow_received.connect(w.update_pump_flow)
            pump.raw_received.connect(w.update_pump_raw)
            pump.status.connect(w.update_pump_status)
            pump.error.connect(w.update_pump_error)

            w.btn_pump_connect.clicked.connect(pump.start) 
            w.btn_pump_disconnect.clicked.connect(pump.stop) 
            app.aboutToQuit.connect(pump.stop) 

            # ===== ESTUFA =====
            #Atualiza a tela quando a estufa enviar informações de temperatura, dado bruto, status, erro
            oven = OvenWorker(port="COM6", baudrate=9600) 
            oven.temp_received.connect(w.update_oven_temp)
            oven.raw_received.connect(w.update_oven_raw)
            oven.status.connect(w.update_oven_status)
            oven.error.connect(w.update_oven_error)

            w.btn_oven_connect.clicked.connect(oven.start) 
            w.btn_oven_disconnect.clicked.connect(oven.stop) 

            app.aboutToQuit.connect(oven.stop) 

            w.set_running(False) 

            # mantém referências vivas -> "esses objetos precisam continuar existindo enquanto o app estiver aberto"
            app._w = w
            app._thread = thread
            app._worker = worker
            app._pump = pump
            app._oven = oven
            app.setQuitOnLastWindowClosed(True) 
        except Exception as e:
            show_fatal_error("Falha ao abrir a tela principal.", e)

    QTimer.singleShot(100, open_main)
    sys.exit(app.exec_()) 
    
if __name__ == "__main__": 
    main()