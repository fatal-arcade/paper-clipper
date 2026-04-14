from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                               QHBoxLayout, QGraphicsView, QGraphicsScene,
                               QGraphicsRectItem, QFrame, QFileDialog)
from PySide6.QtGui import QBrush, QColor, QPen, QPainter
from PySide6.QtCore import Qt


class FirstRunDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PaperClipper Setup")
        self.setFixedSize(400, 250)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Welcome to PaperClipper</b>"))
        layout.addWidget(QLabel("Choose your settings storage mode:"))

        btn_layout = QHBoxLayout()
        self.btn_std = QPushButton("Standard (~/.config)")
        self.btn_port = QPushButton("Portable (Local Folder)")
        btn_layout.addWidget(self.btn_std)
        btn_layout.addWidget(self.btn_port)
        layout.addLayout(btn_layout)

        self.choice = None
        self.btn_std.clicked.connect(lambda: self.set_choice("STANDARD"))
        self.btn_port.clicked.connect(lambda: self.set_choice("PORTABLE"))

    def set_choice(self, mode):
        self.choice = mode
        self.accept()


class MonitorItem(QGraphicsRectItem):
    def __init__(self, x, y, w, h, monitor_data):
        super().__init__(x, y, w, h)
        self.monitor_data = monitor_data
        self.setBrush(QBrush(QColor("#708090")))
        self.setPen(QPen(QColor("#ffffff"), 2))

    def mousePressEvent(self, event):
        self.scene().views()[0].monitor_clicked(self.monitor_data)
        super().mousePressEvent(event)


class MonitorCanvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QBrush(QColor("#1e1e1e")))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scale_factor = 0.1

    def monitor_clicked(self, data):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Wallpaper", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            self.window().handle_wallpaper_selection(data['id'], file_path)

    def display_monitors(self, monitors):
        self.scene.clear()
        for m in monitors:
            rect = MonitorItem(m['x'] * self.scale_factor, m['y'] * self.scale_factor,
                               m['w'] * self.scale_factor, m['h'] * self.scale_factor, m)
            self.scene.addItem(rect)
            txt = self.scene.addText(f"{m['port']}\n{m['w']}x{m['h']}")
            txt.setDefaultTextColor(Qt.white)
            txt.setPos(m['x'] * self.scale_factor + 5, m['y'] * self.scale_factor + 5)
        self.setSceneRect(self.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50))