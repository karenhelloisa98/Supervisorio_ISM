from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class SplashWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Iniciando...")
        self.setFixedSize(560, 280)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        self.setStyleSheet("""
            QWidget {
                background: #0b1220;
                border-radius: 14px;
            }
            QLabel { color: #e8eefc; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        title = QLabel("Desenvolvido por ISM - Engenharia")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 15, QFont.Bold))

        sub = QLabel("Engenheiro Responsável: Rafael Cabral")
        sub.setAlignment(Qt.AlignCenter)
        sub.setFont(QFont("Segoe UI", 11, QFont.Normal))
        sub.setStyleSheet("color: #b8c6e6;")

        hint = QLabel("Carregando supervisório...")
        hint.setAlignment(Qt.AlignCenter)
        hint.setFont(QFont("Segoe UI", 10))
        hint.setStyleSheet("color: #93a6cf; margin-top: 14px;")

        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addWidget(hint)
        layout.addStretch(1)