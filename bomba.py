import sys
from PyQt5.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsItem
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap
from PyQt5.QtCore import QRectF, Qt

class BombaItem(QGraphicsItem):
    def __init__(self, nome="Bomba", imagem_path="Bomba_Vindum.png"):
        super().__init__()

        self.nome = nome
        self.ligada = False
        self.falha = False
        self.pressao = 0.0
        self.vazao = 0.0
        self.pixmap = QPixmap(imagem_path)
        self.img_largura = 140
        self.img_altura = 130

    def boundingRect(self):
        return QRectF(0, 0, 200, 300) 

    def set_dados(self, pressao, vazao):
        self.pressao = pressao
        self.vazao = vazao
        self.update()

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.pixmap.isNull():
            painter.drawPixmap(10, 30, self.img_largura, self.img_altura, self.pixmap)
        else:
            painter.setPen(QPen(Qt.black, 2))
            painter.setBrush(QBrush(QColor(200, 200, 200)))
            painter.drawRect(10, 30, self.img_largura, self.img_altura)
            painter.drawText(20, 100, "Imagem não encontrada")

        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255))) 

        # Caixa da pressão (posicionada abaixo da imagem)
        painter.drawRoundedRect(10, 200, 150, 30, 5, 5)
        painter.setPen(Qt.black)
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(20, 220, f"Pressão: {self.pressao:>6.2f} psi")

        # Caixa da vazão
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawRoundedRect(10, 235, 150, 30, 5, 5)
        painter.setPen(Qt.black)
        painter.drawText(20, 255, f"Vazão: {self.vazao:>6.2f} L/min")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    view.setWindowTitle("Bomba Vindum")
    view.setRenderHint(QPainter.Antialiasing)
    view.resize(400, 500)

    minha_bomba = BombaItem("BOMBA 01", "Bomba_Vindum.png")
    minha_bomba.set_dados(2050.0, 7.74)
    
    scene.addItem(minha_bomba)
    view.show()
    sys.exit(app.exec_())