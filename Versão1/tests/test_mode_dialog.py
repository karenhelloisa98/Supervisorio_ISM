from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLabel,
    QPushButton, QMessageBox, QFormLayout, QDoubleSpinBox, QLineEdit
)
from PyQt5.QtCore import Qt
import numpy as np

from calc import bulk_volume_cylinder, porosity_from_p1_p2, estimate_alpha_from_decay, permeability_pulse_decay


def bar_to_pa(bar: float) -> float:
    return bar * 1e5


class TestModeDialog(QDialog):
    """
    Modo Teste:
      - Aba 1: Verificação rápida dos sensores (leituras atuais)
      - Aba 2: Teste de Porosidade (simulado: P1/P2)
      - Aba 3: Teste de Permeabilidade (simulado: gera decay e calcula k)
    """
    def __init__(self, parent, get_raw_by_name, get_corr_by_name, channel_names):
        super().__init__(parent)
        self.setWindowTitle("Modo Teste")
        self.resize(760, 520)
        self.setModal(True)

        self.get_raw_by_name = get_raw_by_name
        self.get_corr_by_name = get_corr_by_name
        self.channel_names = channel_names

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        # ===== Aba 1: Sensores (Live Snapshot) =====
        tab1 = QWidget()
        tabs.addTab(tab1, "Sensores")
        v1 = QVBoxLayout(tab1)

        self.lbl_live = QLabel("Clique em 'Snapshot' para ver leituras atuais.")
        self.lbl_live.setWordWrap(True)

        self.btn_snap = QPushButton("Snapshot (RAW e Corrigido)")
        self.btn_snap.clicked.connect(self.snapshot)

        v1.addWidget(self.lbl_live)
        v1.addSpacing(8)
        v1.addWidget(self.btn_snap)
        v1.addStretch(1)

        # ===== Aba 2: Porosidade (simulado) =====
        tab2 = QWidget()
        tabs.addTab(tab2, "Porosidade (Simulado)")
        f2 = QFormLayout(tab2)

        self.d_mm = QDoubleSpinBox(); self.d_mm.setRange(0.1, 500.0); self.d_mm.setDecimals(3); self.d_mm.setValue(25.4)
        self.L_mm = QDoubleSpinBox(); self.L_mm.setRange(0.1, 1000.0); self.L_mm.setDecimals(3); self.L_mm.setValue(50.0)

        self.vref_cm3 = QDoubleSpinBox(); self.vref_cm3.setRange(0.001, 1e9); self.vref_cm3.setDecimals(3); self.vref_cm3.setValue(10.0)
        self.vcell_cm3 = QDoubleSpinBox(); self.vcell_cm3.setRange(0.001, 1e9); self.vcell_cm3.setDecimals(3); self.vcell_cm3.setValue(20.0)

        self.p1_bar = QDoubleSpinBox(); self.p1_bar.setRange(0.0, 20000.0); self.p1_bar.setDecimals(4); self.p1_bar.setValue(50.0)
        self.p2_bar = QDoubleSpinBox(); self.p2_bar.setRange(0.0, 20000.0); self.p2_bar.setDecimals(4); self.p2_bar.setValue(30.0)

        self.btn_phi = QPushButton("Calcular Porosidade (Simulado)")
        self.btn_phi.clicked.connect(self.calc_phi_sim)

        self.lbl_phi = QLabel("Resultado: --")
        self.lbl_phi.setStyleSheet("font-weight: 800; font-size: 14px;")

        f2.addRow("Diâmetro (mm):", self.d_mm)
        f2.addRow("Comprimento (mm):", self.L_mm)
        f2.addRow("Vref (cm³):", self.vref_cm3)
        f2.addRow("Vcell vazio (cm³):", self.vcell_cm3)
        f2.addRow("P1 (bar):", self.p1_bar)
        f2.addRow("P2 (bar):", self.p2_bar)
        f2.addRow(self.btn_phi)
        f2.addRow(self.lbl_phi)

        # ===== Aba 3: Permeabilidade (simulado) =====
        tab3 = QWidget()
        tabs.addTab(tab3, "Permeabilidade (Simulado)")
        f3 = QFormLayout(tab3)

        self.mu = QLineEdit("1.78e-5")  # Pa.s N2 ~25C
        self.vu_cm3 = QDoubleSpinBox(); self.vu_cm3.setRange(0.001, 1e9); self.vu_cm3.setDecimals(3); self.vu_cm3.setValue(10.0)
        self.vd_cm3 = QDoubleSpinBox(); self.vd_cm3.setRange(0.001, 1e9); self.vd_cm3.setDecimals(3); self.vd_cm3.setValue(10.0)

        self.Pm_bar = QDoubleSpinBox(); self.Pm_bar.setRange(0.01, 20000.0); self.Pm_bar.setDecimals(4); self.Pm_bar.setValue(20.0)

        self.decay_seconds = QDoubleSpinBox(); self.decay_seconds.setRange(2.0, 300.0); self.decay_seconds.setDecimals(1); self.decay_seconds.setValue(30.0)
        self.fs = QDoubleSpinBox(); self.fs.setRange(1.0, 50.0); self.fs.setDecimals(1); self.fs.setValue(10.0)

        self.dP0_bar = QDoubleSpinBox(); self.dP0_bar.setRange(0.001, 20000.0); self.dP0_bar.setDecimals(4); self.dP0_bar.setValue(5.0)
        self.alpha = QDoubleSpinBox(); self.alpha.setRange(1e-5, 10.0); self.alpha.setDecimals(6); self.alpha.setValue(0.05)

        self.btn_k = QPushButton("Gerar Decay e Calcular k")
        self.btn_k.clicked.connect(self.calc_k_sim)

        self.lbl_k = QLabel("Resultado: --")
        self.lbl_k.setStyleSheet("font-weight: 800; font-size: 14px;")

        f3.addRow("μ N₂ (Pa·s):", self.mu)
        f3.addRow("Vu (cm³):", self.vu_cm3)
        f3.addRow("Vd (cm³):", self.vd_cm3)
        f3.addRow("Pressão média Pm (bar):", self.Pm_bar)
        f3.addRow("Tempo do decay (s):", self.decay_seconds)
        f3.addRow("Taxa (Hz):", self.fs)
        f3.addRow("ΔP0 (bar):", self.dP0_bar)
        f3.addRow("α real (1/s):", self.alpha)
        f3.addRow(self.btn_k)
        f3.addRow(self.lbl_k)

        # Footer
        foot = QHBoxLayout()
        self.btn_close = QPushButton("Fechar")
        self.btn_close.clicked.connect(self.accept)
        foot.addStretch(1)
        foot.addWidget(self.btn_close)
        root.addLayout(foot)

    def snapshot(self):
        lines = []
        for n in self.channel_names:
            raw = self.get_raw_by_name(n)
            corr = self.get_corr_by_name(n)
            lines.append(f"{n}: RAW={('--' if raw is None else f'{raw:.4f}')}  |  Corr={('--' if corr is None else f'{corr:.4f}')}")
        QMessageBox.information(self, "Snapshot", "\n".join(lines))

    def _cm3_to_m3(self, cm3: float) -> float:
        return cm3 * 1e-6

    def _mm_to_m(self, mm: float) -> float:
        return mm / 1000.0

    def calc_phi_sim(self):
        try:
            d = self._mm_to_m(self.d_mm.value())
            L = self._mm_to_m(self.L_mm.value())
            vbulk = bulk_volume_cylinder(d, L)
            vref = self._cm3_to_m3(self.vref_cm3.value())
            vcell = self._cm3_to_m3(self.vcell_cm3.value())
            p1 = bar_to_pa(self.p1_bar.value())
            p2 = bar_to_pa(self.p2_bar.value())

            out = porosity_from_p1_p2(p1, p2, vref, vcell, vbulk)
            self.lbl_phi.setText(
                f"Porosidade: {out['phi_percent']:.2f}% | Vgrain={out['Vgrain_m3']*1e6:.2f} cm³"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    def calc_k_sim(self):
        try:
            mu = float(self.mu.text().strip())
            Vu = self._cm3_to_m3(self.vu_cm3.value())
            Vd = self._cm3_to_m3(self.vd_cm3.value())
            Pm = bar_to_pa(self.Pm_bar.value())

            # geometria da amostra (reusa)
            d = self._mm_to_m(self.d_mm.value())
            L = self._mm_to_m(self.L_mm.value())
            A = np.pi * (d / 2.0) ** 2

            T = float(self.decay_seconds.value())
            fs = float(self.fs.value())
            N = int(T * fs)

            t = np.linspace(0, T, N)
            dP0 = bar_to_pa(self.dP0_bar.value())
            alpha_real = float(self.alpha.value())

            # gera dP(t)
            dP = dP0 * np.exp(-alpha_real * t)

            # estima alpha de volta
            alpha_est = estimate_alpha_from_decay(t, dP)

            out = permeability_pulse_decay(alpha_est, mu, L, A, Pm, Vu, Vd)
            self.lbl_k.setText(f"k ≈ {out['k_mD']:.2f} mD | alpha_est={alpha_est:.4f} 1/s")

        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))