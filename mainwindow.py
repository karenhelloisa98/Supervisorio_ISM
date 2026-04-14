import os
import sys
import pyqtgraph as pg
import numpy as np
from collections import deque
from typing import List, Dict, Optional
from datetime import datetime
from PyQt5 import uic
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import Qt, QTimer, QTime, QDate
from PyQt5.QtWidgets import (QMessageBox)
from logger_csv import CsvLogger

def resource_path(relative_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, relative_path)

class TelaPrincipal(QMainWindow):
    def __init__(self, channel_names: List[str]):
        super().__init__()
        
        caminho_ui = os.path.join(os.path.dirname(__file__), "mainwindow.ui")
        try:
            uic.loadUi(caminho_ui, self)
            print("Sucesso: Interface do Supervisório carregada!")
        except Exception as e:
            print(f"ERRO CRÍTICO ao carregar o UI: {e}")
            raise

        self.set_running(False)
        self.setWindowTitle("Sistema Coreflooding - Supervisório")
        nome_logo = "Imagens/logo_ism_transp.png"
        caminho_logo = resource_path(nome_logo)
        if os.path.exists(caminho_logo):
            self.setWindowIcon(QIcon(caminho_logo))
        else:
            print(f"Aviso: Arquivo de logo não encontrado em {caminho_logo}")
        self.Paginas.setCurrentIndex(0)

        self.timer_relogio = QTimer(self)
        self.timer_relogio.timeout.connect(self.atualizar_data_hora)
        self.timer_relogio.start(1000)
        self.atualizar_data_hora()

        # ===== Canais =====
        self.channel_names = channel_names
        self.name_to_index: Dict[str, int] = {n: i for i, n in enumerate(channel_names)}
        self.n = len(channel_names)

        # ===== Memória dos últimos dados DAQ =====
        self.latest_eng_corr: Dict[str, Optional[float]] = {}
        self.latest_eng_raw: Dict[str, Optional[float]] = {}
        self.latest_ts_ms: Optional[int] = None

        # ===== Estado da bomba =====
        self.current_pump_flow_m3s: Optional[float] = None
        self.current_pump_raw: str = "-" 
        self.current_pump_status: str = "Desconectada" 

        # ===== Estado da estufa =====
        self.current_oven_temp_c: Optional[float] = None
        self.current_oven_raw: str = "-" 
        self.current_oven_status: str = "Desconectada" 

        # ===== Históricos (5 min @ 10 Hz) =====
        self.max_points = 5 * 60 * 10

        # Pressões
        self.t = deque(maxlen=self.max_points)
        self.y = [deque(maxlen=self.max_points) for _ in range(self.n)]

        # Permeabilidade
        self.k_t = deque(maxlen=self.max_points)
        self.k_y = deque(maxlen=self.max_points)

        # Temperatura
        self.temp_t = deque(maxlen=self.max_points)
        self.temp_y = deque(maxlen=self.max_points)

        # CONFIGURAÇÃO DOS GRÁFICOS 
        self.configurar_estilo_graficos()
        self.x_data = [] #eixo do tempo (amostras)
        self.p1_data = []
        self.p2_data = []
        self.p3_data = []
        self.p4_data = []
        self.dp_data = []
        self.temp_data = []
        self.k_data = []
        self.amostra_atual = 0

        # CONEXÕES DE BOTÕES
        self.btn_operacao.clicked.connect(self.ir_para_operacao)
        self.btn_graficos.clicked.connect(self.ir_para_graficos)
        self.btn_start.clicked.connect(self.iniciar_daq)
        self.btn_stop.clicked.connect(self.parar_daq)

    def atualizar_data_hora(self):
        data_atual = QDate.currentDate().toString("dd/MM/yyyy")
        hora_atual = QTime.currentTime().toString("HH:mm:ss")
        self.lbl_data.setText(data_atual)
        self.lbl_hora.setText(hora_atual)

    def configurar_estilo_graficos(self):
        pen_p1 = pg.mkPen(color='b', width=2)
        pen_p2 = pg.mkPen(color='r', width=2)
        pen_p3 = pg.mkPen(color='g', width=2)
        pen_p4 = pg.mkPen(color='m', width=2)
        pen_dp = pg.mkPen(color='k', width=2)   
        pen_temp = pg.mkPen(color='k', width=2) 
        pen_k = pg.mkPen(color='k', width=2)    

        # Gráfico de Pressões (Superior Esquerda)
        self.widget_plot_pressao.setBackground('w')
        self.widget_plot_pressao.showGrid(x=True, y=True, alpha=0.3)
        self.widget_plot_pressao.setLabel('left', 'Pressão', units='psi')
        self.widget_plot_pressao.setLabel('bottom','Amostras')
        self.widget_plot_pressao.addLegend(offset=(10,10))

        self.curva_p1 = self.widget_plot_pressao.plot([], [], pen=pen_p1, name="P1")
        self.curva_p2 = self.widget_plot_pressao.plot([], [], pen=pen_p2, name="P2")
        self.curva_p3 = self.widget_plot_pressao.plot([], [], pen=pen_p3, name="P3")
        self.curva_p4 = self.widget_plot_pressao.plot([], [], pen=pen_p4, name="P4")

        self.curves = [self.curva_p1, self.curva_p2, self.curva_p3, self.curva_p4]
        
        #Gráfico de Pressão Diferencial (Superior Direta)
        self.widget_plot_pressao_dp.setBackground('w')
        self.widget_plot_pressao_dp.showGrid(x=True, y=True, alpha=0.3)
        self.widget_plot_pressao_dp.setLabel('left', 'Pressão Diferencial', units='psi')
        self.widget_plot_pressao_dp.setLabel('bottom','Amostras')
        self.widget_plot_pressao_dp.addLegend(offset=(10,10))
        self.curva_dp = self.widget_plot_pressao_dp.plot([], [], pen=pen_dp, name="DP")

        # Gráfico de Temperatura (Inferior Esquerda)
        self.widget_plot_temp.setBackground('w')
        self.widget_plot_temp.showGrid(x=True, y=True, alpha=0.3)
        self.widget_plot_temp.setLabel('left', 'Temperatura', units='°C')
        self.widget_plot_temp.setLabel('bottom', 'Amostras')
        self.curva_temp = self.widget_plot_temp.plot([], [], pen=pen_temp, name='temp')

        # Gráfico de Permeabilidade (Inferior Direita)
        self.widget_plot_k.setBackground('w')
        self.widget_plot_k.showGrid(x=True, y=True, alpha=0.3)
        self.widget_plot_k.setLabel('left', 'Permeabilidade', units='mD')
        self.widget_plot_k.setLabel('bottom', 'Amostras')
        self.curva_k = self.widget_plot_k.plot([], [], pen=pen_k)

    # ===== FUNÇÕES DE NAVEGAÇÃO E CONTROLE =====
    def ir_para_operacao(self):
        self.Paginas.setCurrentIndex(0)
        print("Página: Operação e Controle")

    def ir_para_graficos(self):
        self.Paginas.setCurrentIndex(1)
        print("Página: Análise de Gráficos")

    def set_running(self, running: bool):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)

        if running:
            self.lbl_conn.setText("Status: Rodando")
            self.lbl_conn.setStyleSheet("""
            color: #000; 
            font-weight: bold; 
            background-color: #0F0; 
            border-radius: 10px;
            padding: 2px;
            qproperty-alignment: 'AlignCenter';
            """)
        else:
            self.lbl_conn.setText("Status: Parado")
            self.lbl_conn.setStyleSheet("""
            color: white; 
            font-weight: bold; 
            background-color: black; 
            border-radius: 10px;
            padding: 2px;
            qproperty-alignment: 'AlignCenter';
            """)

    def iniciar_daq(self):
        self.timer_daq.start(200)
        self.set_running(True)
        print("Aquisicao de dados iniciada...")

    def parar_daq(self):
        self.timer_daq.stop()
        self.set_running(False)
        print("Aquisicao de dados parada...")

    # =========================================================
    # UTILIDADES
    # =========================================================
    def show_error(self, msg: str):
        QMessageBox.critical(self, "Erro", msg)

    # =========================================================
    # BOMBA
    # =========================================================
    def update_pump_flow(self, value_m3s: float):
        self.current_pump_flow_m3s = value_m3s
        if self.flow_source.currentIndex() == 1:
            self.input_q.setValue(value_m3s)

    def update_pump_raw(self, text: str):
        self.current_pump_raw = text
        self.lbl_pump_raw.setText(f"Última mensagem: {text}")

    def update_pump_status(self, text: str):
        self.current_pump_status = text
        self.lbl_pump_status.setText(f"Status: {text}")

    def update_pump_error(self, text: str):
        self.current_pump_status = f"Erro: {text}"
        self.lbl_pump_status.setText("Status: Erro")
        self.lbl_pump_raw.setText(f"Última mensagem: {text}")

    # =========================================================
    # ESTUFA
    # =========================================================
    def update_oven_temp(self, value_c: float):
        self.current_oven_temp_c = value_c
        if self.temp_source.currentIndex() == 1:
            self.lbl_temp.setText(f"{value_c:.2f} °C")

    def update_oven_raw(self, text: str):
        self.current_oven_raw = text
        self.lbl_oven_raw.setText(f"Última mensagem: {text}")

    def update_oven_status(self, text: str):
        self.current_oven_status = text
        self.lbl_oven_status.setText(f"Status: {text}")

    def update_oven_error(self, text: str):
        self.current_oven_status = f"Erro: {text}"
        self.lbl_oven_status.setText("Status: Erro")
        self.lbl_oven_raw.setText(f"Última mensagem: {text}")

    # =========================================================
    # FONTES ATUAIS
    # =========================================================
    def get_current_temperature(self):
        if self.temp_source.currentIndex() == 0:
            return float(self.input_temp_manual.value())
        return self.current_oven_temp_c

    def get_current_flow(self):
        if self.flow_source.currentIndex() == 0:
            return float(self.input_q.value())
        return self.current_pump_flow_m3s

    # =========================================================
    # CÁLCULO DE PERMEABILIDADE (tempo real)
    # =========================================================
    def calculate_permeability_realtime(self):
        try:
            q = self.get_current_flow()
            mu = float(self.input_mu.value())
            L = float(self.input_L.value())
            d = float(self.input_d.value())

            if q is None or q <= 0:
                self.lbl_k.setText("-- mD")
                return None

            if min(mu, L, d) <= 0:
                self.lbl_k.setText("-- mD")
                return None

            pu = self.latest_eng_corr.get("Pu")
            pd = self.latest_eng_corr.get("Pd")

            if pu is None or pd is None:
                self.lbl_k.setText("-- mD")
                return None

            if self.dp_source.currentIndex() == 0:
                dp = self.latest_eng_corr.get("DP")
                if dp is None:
                    self.lbl_k.setText("-- mD")
                    return None
            else:
                dp = pu - pd

            if dp is None or dp <= 0:
                self.lbl_k.setText("-- mD")
                return None

            dp_pa = dp * 6894.75729
            A = np.pi * (d / 2.0) ** 2

            if A <= 0:
                self.lbl_k.setText("-- mD")
                return None

            k_m2 = (q * mu * L) / (A * dp_pa)
            k_mD = k_m2 / 9.869233e-16

            if np.isfinite(k_mD) and k_mD >= 0:
                self.lbl_k.setText(f"{k_mD:.2f} mD")
                return float(k_mD)

            self.lbl_k.setText("-- mD")
            return None

        except Exception:
            self.lbl_k.setText("-- mD")
            return None

    # =========================================================
    # UPDATE GERAL DOS DADOS
    # =========================================================
    def update_data(self, payload):
        eng_corr = payload.get("eng", [])
        eng_raw = payload.get("eng_raw", eng_corr)
        status = payload.get("status", ["OK"] * len(eng_corr))

        # ===== Salva últimas leituras =====
        for i, name in enumerate(self.channel_names):
            raw_val = eng_raw[i] if i < len(eng_raw) else None
            corr_val = eng_corr[i] if i < len(eng_corr) else None

            self.latest_eng_raw[name] = float(raw_val) if raw_val is not None else None
            self.latest_eng_corr[name] = float(corr_val) if corr_val is not None else None

        self.latest_ts_ms = int(datetime.now().timestamp() * 1000)

        # ===== Índice temporal =====
        idx = self.t[-1] + 1 if len(self.t) else 0
        self.t.append(idx)

        # ===== Atualiza cards dos canais =====
        for i in range(self.n):
            val = eng_corr[i] if i < len(eng_corr) else None

            if val is None:
                self.value_labels[i].setText("OFFLINE")
            else:
                self.value_labels[i].setText(f"{val:.2f}")

            st = status[i] if i < len(status) else "OK"

            if st == "OK":
                self.status_labels[i].setObjectName("TagOK")
            elif st == "OPEN_LOOP":
                self.status_labels[i].setObjectName("TagWarn")
            else:
                self.status_labels[i].setObjectName("TagBad")

            self.status_labels[i].style().unpolish(self.status_labels[i])
            self.status_labels[i].style().polish(self.status_labels[i])
            self.status_labels[i].setText(st)

        # ===== Cálculos auxiliares =====
        P1 = self.latest_eng_corr.get("P1")
        P2 = self.latest_eng_corr.get("P2")
        DP1 = self.latest_eng_corr.get("DP1")

        x = list(self.t)

        if P1 is not None and P2 is not None and DP1 is not None:
            dpcalc = P2 - P1
            pmean = (P1 + P2) / 2.0
            sigma_eff = P2 - pmean

            self.lbl_dpcalc.setText(f"{dpcalc:.2f} psi")
            self.lbl_pmean.setText(f"{pmean:.2f} psi")
            self.lbl_sigma_eff.setText(f"{sigma_eff:.2f} psi")

            # Atualiza o gráfico de Pressão Diferencial
            if hasattr(self, "curva_dp"):
                self.dp_data.append(dpcalc) # Adiciona ao histórico de DP
                self.curva_dp.setData(x, list(self.dp_data))
        else:
            self.lbl_dpcalc.setText("-- psi")
            self.lbl_pmean.setText("-- psi")
            self.lbl_sigma_eff.setText("-- psi")

        # ===== Temperatura =====
        temp_value = self.get_current_temperature()
        if temp_value is not None:
            self.lbl_temp.setText(f"{temp_value:.2f} °C")
            self.temp_t.append(idx)
            self.temp_y.append(temp_value)

            if hasattr(self, "curva_temp"):
                self.curva_temp.setData(list(self.temp_t), list(self.temp_y))

        # ===== Permeabilidade =====
        k_value = self.calculate_permeability_realtime()
        if k_value is not None:
            self.k_t.append(idx)
            self.k_y.append(k_value)

            if hasattr(self, "curva_k"):
                self.curva_k.setData(list(self.k_t), list(self.k_y))

        # ===== Histórico de pressões =====
        for i in range(self.n):
            val = eng_corr[i] if i < len(eng_corr) and eng_corr[i] is not None else 0.0
            self.y[i].append(val)

        x = list(self.t)

        if hasattr(self, "curves"):
            for i in range(self.n):
                self.curves[i].setData(x, list(self.y[i]))
