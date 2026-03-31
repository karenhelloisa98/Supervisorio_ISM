from __future__ import annotations
import os
import sys
from collections import deque
from typing import List, Dict, Optional
from datetime import datetime
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QMessageBox, QFrame, QDoubleSpinBox, QComboBox,
    QScrollArea, QStackedWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap


def resource_path(relative_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, relative_path)

class MainWidget(QWidget):
    def __init__(self, channel_names: List[str]):
        super().__init__()

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

        # ===== Janela =====
        self.setWindowTitle("Supervisório de Pressão - ISM")
        self.resize(1200, 900)

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

        # ===== Layout principal =====
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(12)

        # ===== Header Fixo =====
        self.header = QFrame()
        self.header.setObjectName("Header")
        self.header.setFixedHeight(80)

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 12, 20, 12)
        header_layout.setSpacing(14)

        self.logo1 = QLabel()
        self.logo1.setObjectName("Logo1")
        self.logo1.setFixedSize(50, 50)
        self.logo1.setAlignment(Qt.AlignCenter)

        logo1_path = resource_path("logo_ism.png")
        if os.path.exists(logo1_path):
            pix = QPixmap(logo1_path)
            self.logo1.setPixmap(pix.scaledToHeight(50, Qt.SmoothTransformation))
        else:
            self.logo1.setText("LOGO")
            self.logo1.setAlignment(Qt.AlignCenter)

        self.logo2 = QLabel()
        self.logo2.setObjectName("Logo2")
        self.logo2.setFixedSize(50, 50)
        self.logo2.setAlignment(Qt.AlignCenter)

        logo2_path = resource_path("logo_on.jpg")
        if os.path.exists(logo2_path):
            pix = QPixmap(logo2_path)
            self.logo2.setPixmap(pix.scaledToHeight(50, Qt.SmoothTransformation))
        else:
            self.logo2.setText("LOGO")
            self.logo2.setAlignment(Qt.AlignCenter)

        logos_layout = QHBoxLayout()
        logos_layout.setSpacing(8)
        logos_layout.setContentsMargins(0, 0, 0, 0)
        logos_layout.addWidget(self.logo1)
        logos_layout.addWidget(self.logo2)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Sistema Coreflooding - Observatório Nacional")
        title.setObjectName("HeaderTitle")

        subtitle = QLabel("ISM - Engenharia")
        subtitle.setObjectName("HeaderSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        self.status_pill = QLabel("PARADO")
        self.status_pill.setObjectName("StatusPill")
        self.status_pill.setAlignment(Qt.AlignCenter)
        self.status_pill.setFixedSize(140, 48)

        header_layout.addLayout(logos_layout)
        header_layout.addLayout(title_box)
        header_layout.addStretch(1)
        header_layout.addWidget(self.status_pill)

        self.main_layout.addWidget(self.header)

        # ===== Menu de navegação =====
        self.nav_frame = QFrame()
        self.nav_frame.setObjectName("NavFrame")
        nav_layout = QHBoxLayout(self.nav_frame)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(10)

        self.btn_operacao = QPushButton("OPERAÇÃO E CONTROLE")
        self.btn_operacao.setObjectName("NavButton")
        self.btn_operacao.setCheckable(True)

        self.btn_graficos = QPushButton("ANÁLISE DE GRÁFICOS")
        self.btn_graficos.setObjectName("NavButton")
        self.btn_graficos.setCheckable(True)

        self.btn_operacao.setChecked(True)
        self.btn_graficos.setChecked(False)

        nav_layout.addWidget(self.btn_operacao)
        nav_layout.addWidget(self.btn_graficos)
        nav_layout.addStretch()

        self.main_layout.addWidget(self.nav_frame)

        # ===== Stack de telas =====
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack, 1)

        # ===== Criação das telas =====
        self.setup_tela_operacao()
        self.setup_tela_graficos()

        self.stack.addWidget(self.scroll_operacao)
        self.stack.addWidget(self.container_graficos)

        # ===== Conexões =====
        self.btn_operacao.clicked.connect(self.mostrar_operacao)
        self.btn_graficos.clicked.connect(self.mostrar_graficos)

        # ===== Estilo =====
        self.apply_initial_stylesheet()

        # ===== Estado inicial =====
        self.set_running(False)

    def mostrar_operacao(self):
        self.stack.setCurrentIndex(0)
        self.btn_operacao.setChecked(True)
        self.btn_graficos.setChecked(False)

    def mostrar_graficos(self):
        self.stack.setCurrentIndex(1)
        self.btn_operacao.setChecked(False)
        self.btn_graficos.setChecked(True)

    # =========================================================
    # TELA 1 - OPERAÇÃO
    # =========================================================
    def setup_tela_operacao(self):
        self.scroll_operacao = QScrollArea()
        self.scroll_operacao.setWidgetResizable(True)
        self.scroll_operacao.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        self.scroll_operacao.setWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # ===== Controls =====
        controls = QFrame()
        controls.setObjectName("Controls")

        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(12, 10, 12, 10)
        controls_layout.setSpacing(10)

        self.lbl_conn = QLabel("Status do sistema: PARADO")
        self.lbl_conn.setObjectName("ConnLabel")

        self.btn_start = QPushButton("Iniciar DAQ")
        self.btn_start.setObjectName("BtnStart")

        self.btn_stop = QPushButton("Parar DAQ")
        self.btn_stop.setObjectName("BtnStop")
        self.btn_stop.setEnabled(False)

        controls_layout.addWidget(self.lbl_conn)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.btn_start)
        controls_layout.addWidget(self.btn_stop)

        root.addWidget(controls)

        # ===== Cards principais dos canais =====
        grid_frame = QFrame()
        grid_frame.setObjectName("CardsArea")

        grid = QGridLayout(grid_frame)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.value_labels = []
        self.status_labels = []

        for i, name in enumerate(self.channel_names):
            card = QFrame()
            card.setObjectName("Card")

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(6)
            card.setMaximumWidth(140)
            card.setMaximumHeight(70)

            top_row = QHBoxLayout()

            title = QLabel(name)
            title.setObjectName("CardTitle")

            st = QLabel("OK")
            st.setObjectName("TagOK")
            st.setAlignment(Qt.AlignCenter)

            top_row.addWidget(title)
            top_row.addStretch(1)
            top_row.addWidget(st)

            val = QLabel("--")
            val.setObjectName("CardValue")
            val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            unit = QLabel("psi")
            unit.setObjectName("CardUnit")

            card_layout.addLayout(top_row)
            card_layout.addWidget(val)
            card_layout.addWidget(unit)

            self.value_labels.append(val)
            self.status_labels.append(st)

            row = i // 8
            col = i % 8
            grid.addWidget(card, row, col)

        # ===== Métricas adicionais =====
        self.card_phi = QLabel("-- %")
        self.card_phi.setObjectName("CardValue")

        self.card_k = QLabel("-- mD")
        self.card_k.setObjectName("CardValue")

        self.card_dpcalc = QLabel("-- psi")
        self.card_dpcalc.setObjectName("CardValue")

        self.card_pmean = QLabel("-- psi")
        self.card_pmean.setObjectName("CardValue")

        self.card_sigma_eff = QLabel("-- psi")
        self.card_sigma_eff.setObjectName("CardValue")

        self.card_temp = QLabel("-- °C")
        self.card_temp.setObjectName("CardValue")

        def add_metric_card(title_txt: str, value_label: QLabel, row: int, col: int):
            card = QFrame()
            card.setObjectName("Card")

            lay = QVBoxLayout(card)
            lay.setContentsMargins(12, 10, 12, 10)
            lay.setSpacing(6)

            t = QLabel(title_txt)
            t.setObjectName("CardTitle")

            u = QLabel("")
            u.setObjectName("CardUnit")

            lay.addWidget(t)
            lay.addWidget(value_label)
            lay.addWidget(u)

            grid.addWidget(card, row, col)

        last_row = (len(self.channel_names) - 1) // 6 + 1

        add_metric_card("Porosidade", self.card_phi, last_row, 0)
        add_metric_card("Permeabilidade", self.card_k, last_row, 1)
        add_metric_card("ΔP (calc)", self.card_dpcalc, last_row + 1, 0)
        add_metric_card("Pmean", self.card_pmean, last_row + 1, 1)
        add_metric_card("σ' = Pc - Pmean", self.card_sigma_eff, last_row + 2, 0)
        add_metric_card("Temperatura", self.card_temp, last_row + 2, 1)

        root.addWidget(grid_frame)

        # ===== Porosidade =====
        porosity_frame = QFrame()
        porosity_frame.setObjectName("PlotFrame")

        porosity_layout = QVBoxLayout(porosity_frame)
        porosity_layout.setContentsMargins(12, 12, 12, 12)
        porosity_layout.setSpacing(8)

        porosity_title = QLabel("Cálculo de Porosidade")
        porosity_title.setObjectName("PlotTitle")
        porosity_layout.addWidget(porosity_title)

        porosity_inputs = QHBoxLayout()

        self.input_v1 = QDoubleSpinBox()
        self.input_v1.setRange(0.000001, 1e12)
        self.input_v1.setDecimals(6)
        self.input_v1.setValue(1.0)

        self.input_vb = QDoubleSpinBox()
        self.input_vb.setRange(0.000001, 1e12)
        self.input_vb.setDecimals(6)
        self.input_vb.setValue(1.0)

        self.btn_calc_phi = QPushButton("Calcular Porosidade")
        self.btn_calc_phi.setObjectName("BtnStop")
        self.btn_calc_phi.clicked.connect(self.calculate_porosity)

        porosity_inputs.addWidget(QLabel("V1:"))
        porosity_inputs.addWidget(self.input_v1)
        porosity_inputs.addSpacing(20)
        porosity_inputs.addWidget(QLabel("VB:"))
        porosity_inputs.addWidget(self.input_vb)
        porosity_inputs.addSpacing(20)
        porosity_inputs.addWidget(self.btn_calc_phi)
        porosity_inputs.addStretch(1)

        porosity_layout.addLayout(porosity_inputs)
        root.addWidget(porosity_frame)

        # ===== Estufa / Temperatura =====
        oven_frame = QFrame()
        oven_frame.setObjectName("PlotFrame")

        oven_layout = QVBoxLayout(oven_frame)
        oven_layout.setContentsMargins(12, 12, 12, 12)
        oven_layout.setSpacing(8)

        oven_title = QLabel("Temperatura da Estufa")
        oven_title.setObjectName("PlotTitle")
        oven_layout.addWidget(oven_title)

        oven_row1 = QHBoxLayout()

        self.btn_oven_connect = QPushButton("Conectar estufa")
        self.btn_oven_connect.setObjectName("BtnStop")

        self.btn_oven_disconnect = QPushButton("Desconectar estufa")
        self.btn_oven_disconnect.setObjectName("BtnStop")

        self.lbl_oven_status = QLabel("Status: Desconectada")
        self.lbl_oven_status.setObjectName("CardTitle")

        oven_row1.addWidget(self.btn_oven_connect)
        oven_row1.addWidget(self.btn_oven_disconnect)
        oven_row1.addSpacing(20)
        oven_row1.addWidget(self.lbl_oven_status)
        oven_row1.addStretch(1)

        oven_row2 = QHBoxLayout()

        self.temp_source = QComboBox()
        self.temp_source.addItems(["Temperatura manual", "Usar estufa"])

        self.input_temp_manual = QDoubleSpinBox()
        self.input_temp_manual.setRange(-100.0, 500.0)
        self.input_temp_manual.setDecimals(2)
        self.input_temp_manual.setValue(25.0)

        oven_row2.addWidget(QLabel("Fonte de temperatura:"))
        oven_row2.addWidget(self.temp_source)
        oven_row2.addSpacing(20)
        oven_row2.addWidget(QLabel("T manual (°C):"))
        oven_row2.addWidget(self.input_temp_manual)
        oven_row2.addStretch(1)

        self.lbl_oven_raw = QLabel("Última mensagem: -")
        self.lbl_oven_raw.setObjectName("CardUnit")

        oven_layout.addLayout(oven_row1)
        oven_layout.addLayout(oven_row2)
        oven_layout.addWidget(self.lbl_oven_raw)

        root.addWidget(oven_frame)

        # ===== Bomba =====
        pump_frame = QFrame()
        pump_frame.setObjectName("PlotFrame")

        pump_layout = QVBoxLayout(pump_frame)
        pump_layout.setContentsMargins(12, 12, 12, 12)
        pump_layout.setSpacing(8)

        pump_title = QLabel("Integração da Bomba")
        pump_title.setObjectName("PlotTitle")
        pump_layout.addWidget(pump_title)

        pump_row1 = QHBoxLayout()

        self.btn_pump_connect = QPushButton("Conectar bomba")
        self.btn_pump_connect.setObjectName("BtnStop")

        self.btn_pump_disconnect = QPushButton("Desconectar bomba")
        self.btn_pump_disconnect.setObjectName("BtnStop")

        self.lbl_pump_status = QLabel("Status: Desconectada")
        self.lbl_pump_status.setObjectName("CardTitle")

        pump_row1.addWidget(self.btn_pump_connect)
        pump_row1.addWidget(self.btn_pump_disconnect)
        pump_row1.addSpacing(20)
        pump_row1.addWidget(self.lbl_pump_status)
        pump_row1.addStretch(1)

        pump_row2 = QHBoxLayout()

        self.lbl_pump_raw = QLabel("Última mensagem: -")
        self.lbl_pump_raw.setObjectName("CardUnit")

        pump_row2.addWidget(self.lbl_pump_raw)

        pump_layout.addLayout(pump_row1)
        pump_layout.addLayout(pump_row2)

        root.addWidget(pump_frame)

        # ===== Permeabilidade =====
        perm_frame = QFrame()
        perm_frame.setObjectName("PlotFrame")

        perm_layout = QVBoxLayout(perm_frame)
        perm_layout.setContentsMargins(12, 12, 12, 12)
        perm_layout.setSpacing(8)

        perm_title = QLabel("Permeabilidade em Tempo Real (Lei de Darcy)")
        perm_title.setObjectName("PlotTitle")
        perm_layout.addWidget(perm_title)

        row1 = QHBoxLayout()
        row2 = QHBoxLayout()

        def make_spin(min_v, max_v, decimals, value):
            s = QDoubleSpinBox()
            s.setRange(min_v, max_v)
            s.setDecimals(decimals)
            s.setValue(value)
            return s

        self.input_q = make_spin(0.0, 1e9, 9, 0.0)
        self.input_mu = make_spin(1e-9, 10.0, 9, 1.8e-5)
        self.input_L = make_spin(1e-6, 1e9, 6, 0.05)
        self.input_d = make_spin(1e-6, 1e9, 6, 0.0254)

        self.flow_source = QComboBox()
        self.flow_source.addItems(["Vazão manual", "Usar bomba"])

        self.dp_source = QComboBox()
        self.dp_source.addItems(["Usar DP medido", "Usar Pu - Pd"])

        row1.addWidget(QLabel("Fonte de vazão:"))
        row1.addWidget(self.flow_source)
        row1.addSpacing(12)

        row1.addWidget(QLabel("Q manual (m³/s):"))
        row1.addWidget(self.input_q)
        row1.addSpacing(12)

        row1.addWidget(QLabel("μ (Pa·s):"))
        row1.addWidget(self.input_mu)
        row1.addStretch(1)

        row2.addWidget(QLabel("L (m):"))
        row2.addWidget(self.input_L)
        row2.addSpacing(12)

        row2.addWidget(QLabel("d (m):"))
        row2.addWidget(self.input_d)
        row2.addSpacing(12)

        row2.addWidget(QLabel("Fonte de ΔP:"))
        row2.addWidget(self.dp_source)
        row2.addStretch(1)

        perm_layout.addLayout(row1)
        perm_layout.addLayout(row2)

        root.addWidget(perm_frame)
        root.addStretch(1)

    # =========================================================
    # TELA 2 - GRÁFICOS
    # =========================================================
    def setup_tela_graficos(self):
        self.container_graficos = QFrame()

        layout = QVBoxLayout(self.container_graficos)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ===== Plot de pressões =====
        plot_frame = QFrame()
        plot_frame.setObjectName("PlotFrame")

        plot_layout = QVBoxLayout(plot_frame)
        plot_layout.setContentsMargins(12, 12, 12, 12)
        plot_layout.setSpacing(8)

        plot_title = QLabel("Pressões (tempo real)")
        plot_title.setObjectName("PlotTitle")
        plot_layout.addWidget(plot_title)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        self.plot.setMinimumHeight(300)
        self.plot.setMouseEnabled(x=True, y=False)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("left", "Pressão", units="psi")
        self.plot.setLabel("bottom", "Amostras")
        self.plot.addLegend(offset=(10, 10))

        self.curves = []
        for name in self.channel_names:
            curve = self.plot.plot([], [], name=name, pen=pg.mkPen(width=2))
            self.curves.append(curve)

        plot_layout.addWidget(self.plot, 1)
        layout.addWidget(plot_frame, 2)

        # ===== Permeabilidade e Temperatura lado a lado =====
        h_row = QHBoxLayout()
        h_row.setSpacing(12)

        # ----- Permeabilidade -----
        k_plot_frame = QFrame()
        k_plot_frame.setObjectName("PlotFrame")

        k_plot_layout = QVBoxLayout(k_plot_frame)
        k_plot_layout.setContentsMargins(12, 12, 12, 12)
        k_plot_layout.setSpacing(8)

        k_plot_title = QLabel("Permeabilidade (tempo real)")
        k_plot_title.setObjectName("PlotTitle")
        k_plot_layout.addWidget(k_plot_title)

        self.k_plot = pg.PlotWidget()
        self.k_plot.setBackground("w")
        self.k_plot.setMinimumHeight(240)
        self.k_plot.setMouseEnabled(x=True, y=False)
        self.k_plot.showGrid(x=True, y=True, alpha=0.25)
        self.k_plot.setLabel("left", "Permeabilidade", units="mD")
        self.k_plot.setLabel("bottom", "Amostras")
        self.k_plot.addLegend(offset=(10, 10))

        self.k_curve = self.k_plot.plot([], [], name="k", pen=pg.mkPen(width=2))
        k_plot_layout.addWidget(self.k_plot, 1)

        # ----- Temperatura -----
        temp_plot_frame = QFrame()
        temp_plot_frame.setObjectName("PlotFrame")

        temp_plot_layout = QVBoxLayout(temp_plot_frame)
        temp_plot_layout.setContentsMargins(12, 12, 12, 12)
        temp_plot_layout.setSpacing(8)

        temp_plot_title = QLabel("Temperatura (tempo real)")
        temp_plot_title.setObjectName("PlotTitle")
        temp_plot_layout.addWidget(temp_plot_title)

        self.temp_plot = pg.PlotWidget()
        self.temp_plot.setBackground("w")
        self.temp_plot.setMinimumHeight(240)
        self.temp_plot.setMouseEnabled(x=True, y=False)
        self.temp_plot.showGrid(x=True, y=True, alpha=0.25)
        self.temp_plot.setLabel("left", "Temperatura", units="°C")
        self.temp_plot.setLabel("bottom", "Amostras")
        self.temp_plot.addLegend(offset=(10, 10))

        self.temp_curve = self.temp_plot.plot([], [], name="T", pen=pg.mkPen(width=2))
        temp_plot_layout.addWidget(self.temp_plot, 1)

        h_row.addWidget(k_plot_frame, 1)
        h_row.addWidget(temp_plot_frame, 1)

        layout.addLayout(h_row, 1)

    # =========================================================
    # ESTILO
    # =========================================================
    def apply_initial_stylesheet(self):
        self.setStyleSheet("""
            QWidget {
                font-family: "Segoe UI";
                background: #f3f5fb;
            }

            #Header {
                background-color: #082C5C;
                border-radius: 14px;
            }

            #Logo1, #Logo2 {
                background: transparent;
            }

            #HeaderTitle {
                background: transparent;
                color: #ffffff;
                font-size: 20px;
                font-weight: 800;
            }

            #HeaderSubtitle {
                background: transparent;
                color: #ffffff;
                font-size: 12px;
                font-weight: 600;
            }

            #StatusPill {
                min-width: 110px;
                height: 30px;
                border-radius: 15px;
                padding: 0 14px;
                font-weight: 800;
                background: #d7dbe6;
                color: #0b1220;
            }

            #NavFrame {
                background: transparent;
            }

            QPushButton#NavButton {
                height: 38px;
                padding: 0 16px;
                border-radius: 10px;
                font-weight: 800;
                border: 1px solid #cfd6ea;
                background: #ffffff;
                color: #0b1220;
            }

            QPushButton#NavButton:checked {
                background: #0b1220;
                color: #ffffff;
                border: 1px solid #0b1220;
            }

            #Controls {
                background: #ffffff;
                border-radius: 12px;
                border: 1px solid #e4e8f2;
            }

            #ConnLabel {
                color: #0b1220;
                font-weight: 700;
            }

            QPushButton {
                height: 36px;
                padding: 0 16px;
                border-radius: 10px;
                font-weight: 800;
                border: none;
            }

            QPushButton#BtnStart:enabled {
                background: #0b1220;
                color: white;
            }

            QPushButton#BtnStop:enabled {
                background: #ffffff;
                color: #0b1220;
                border: 1px solid #cfd6ea;
            }

            QPushButton:disabled {
                background: #d7dbe6;
                color: #7a849a;
            }

            #Card {
                background: #ffffff;
                border-radius: 12px;
                border: 1px solid #e4e8f2;
            }

            #CardTitle {
                color: #0b1220;
                font-size: 13px;
                font-weight: 800;
                background: transparent;
            }

            #CardValue {
                color: #0b1220;
                font-size: 24px;
                font-weight: 900;
                background: transparent;
            }

            #CardUnit {
                color: #6b7896;
                font-size: 12px;
                font-weight: 700;
                background: transparent;
            }

            QLabel#TagOK {
                min-width: 88px;
                height: 22px;
                border-radius: 11px;
                padding: 0 10px;
                background: #c7f7c7;
                color: #0b1220;
                font-weight: 800;
                font-size: 11px;
            }

            QLabel#TagWarn {
                min-width: 88px;
                height: 22px;
                border-radius: 11px;
                padding: 0 10px;
                background: #ffd6a6;
                color: #0b1220;
                font-weight: 800;
                font-size: 11px;
            }

            QLabel#TagBad {
                min-width: 88px;
                height: 22px;
                border-radius: 11px;
                padding: 0 10px;
                background: #ffb3b3;
                color: #0b1220;
                font-weight: 800;
                font-size: 11px;
            }

            #PlotFrame {
                background: #ffffff;
                border-radius: 12px;
                border: 1px solid #e4e8f2;
            }

            #PlotTitle {
                color: #0b1220;
                font-size: 13px;
                font-weight: 800;
                background: transparent;
            }
        """)

    # =========================================================
    # STATUS DO SISTEMA
    # =========================================================
    def set_running(self, running: bool):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)

        if running:
            self.lbl_conn.setText("Status do sistema: RODANDO")
            self.status_pill.setText("RODANDO")
            self.status_pill.setStyleSheet("""
                min-width: 110px;
                height: 30px;
                border-radius: 15px;
                padding: 0 14px;
                font-weight: 800;
                color: #ffffff;
                background: #28a745;
            """)
        else:
            self.lbl_conn.setText("Status do sistema: PARADO")
            self.status_pill.setText("PARADO")
            self.status_pill.setStyleSheet("""
                min-width: 110px;
                height: 30px;
                border-radius: 15px;
                padding: 0 14px;
                font-weight: 800;
                color: #ffffff;
                background: #000000;
            """)

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
            self.card_temp.setText(f"{value_c:.2f} °C")

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
    # CÁLCULO DE POROSIDADE
    # =========================================================
    def calculate_porosity(self):
        try:
            v1 = float(self.input_v1.value())
            vb = float(self.input_vb.value())

            if vb <= 0:
                raise ValueError("VB deve ser maior que zero.")
            if v1 <= 0:
                raise ValueError("V1 deve ser maior que zero.")

            p1 = self.latest_eng_corr.get("Pu")
            p2 = self.latest_eng_corr.get("Pd")

            if p1 is None or p2 is None:
                p1 = self.latest_eng_corr.get("P1")
                p2 = self.latest_eng_corr.get("P2")

            if p1 is None or p2 is None:
                raise ValueError("Não foi possível encontrar P1/P2 ou Pu/Pd nas leituras.")
            if p2 <= 0:
                raise ValueError("P2 deve ser maior que zero.")

            vp = v1 * ((p1 / p2) - 1.0)
            phi = (vp / vb) * 100.0

            self.card_phi.setText(f"{phi:.2f} %")

        except Exception as e:
            QMessageBox.critical(self, "Erro no cálculo", str(e))

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
                self.card_k.setText("-- mD")
                return None

            if min(mu, L, d) <= 0:
                self.card_k.setText("-- mD")
                return None

            pu = self.latest_eng_corr.get("Pu")
            pd = self.latest_eng_corr.get("Pd")

            if pu is None or pd is None:
                self.card_k.setText("-- mD")
                return None

            if self.dp_source.currentIndex() == 0:
                dp = self.latest_eng_corr.get("DP")
                if dp is None:
                    self.card_k.setText("-- mD")
                    return None
            else:
                dp = pu - pd

            if dp is None or dp <= 0:
                self.card_k.setText("-- mD")
                return None

            dp_pa = dp * 6894.75729
            A = np.pi * (d / 2.0) ** 2

            if A <= 0:
                self.card_k.setText("-- mD")
                return None

            k_m2 = (q * mu * L) / (A * dp_pa)
            k_mD = k_m2 / 9.869233e-16

            if np.isfinite(k_mD) and k_mD >= 0:
                self.card_k.setText(f"{k_mD:.2f} mD")
                return float(k_mD)

            self.card_k.setText("-- mD")
            return None

        except Exception:
            self.card_k.setText("-- mD")
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
        Pc = self.latest_eng_corr.get("Pc")
        Pu = self.latest_eng_corr.get("Pu")
        Pd = self.latest_eng_corr.get("Pd")

        if Pc is not None and Pu is not None and Pd is not None:
            dpcalc = Pu - Pd
            pmean = (Pu + Pd) / 2.0
            sigma_eff = Pc - pmean

            self.card_dpcalc.setText(f"{dpcalc:.2f} psi")
            self.card_pmean.setText(f"{pmean:.2f} psi")
            self.card_sigma_eff.setText(f"{sigma_eff:.2f} psi")
        else:
            self.card_dpcalc.setText("-- psi")
            self.card_pmean.setText("-- psi")
            self.card_sigma_eff.setText("-- psi")

        # ===== Temperatura =====
        temp_value = self.get_current_temperature()
        if temp_value is not None:
            self.card_temp.setText(f"{temp_value:.2f} °C")
            self.temp_t.append(idx)
            self.temp_y.append(temp_value)

            if hasattr(self, "temp_curve"):
                self.temp_curve.setData(list(self.temp_t), list(self.temp_y))

        # ===== Permeabilidade =====
        k_value = self.calculate_permeability_realtime()
        if k_value is not None:
            self.k_t.append(idx)
            self.k_y.append(k_value)

            if hasattr(self, "k_curve"):
                self.k_curve.setData(list(self.k_t), list(self.k_y))

        # ===== Histórico de pressões =====
        for i in range(self.n):
            val = eng_corr[i] if i < len(eng_corr) and eng_corr[i] is not None else 0.0
            self.y[i].append(val)

        x = list(self.t)

        if hasattr(self, "curves"):
            for i in range(self.n):
                self.curves[i].setData(x, list(self.y[i]))