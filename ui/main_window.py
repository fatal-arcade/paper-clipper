import os
from PySide6.QtWidgets import QMainWindow, QHBoxLayout, QVBoxLayout, QWidget, QFrame, QLabel, QApplication, QCheckBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt
from ui.components import MonitorCanvas
from engine.hardware import WallpaperSetter # New Import

class MainWindow(QMainWindow):

    def __init__(self, monitors, config_manager, setter):
        super().__init__()
        self.monitors = monitors
        self.cfg = config_manager
        self.setter = setter  # Initialize the setter
        self.setWindowTitle("PaperClipper")
        self.resize(1000, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("background-color: #252526; border-right: 1px solid #333;")
        side_layout = QVBoxLayout(self.sidebar)

        lbl_sidebar = QLabel("SETTINGS")
        lbl_sidebar.setStyleSheet("color: #aaa; font-weight: bold; font-size: 10px; margin-bottom: 10px;")
        side_layout.addWidget(lbl_sidebar)

        # Autostart Checkbox
        self.auto_cb = QCheckBox("Start on Boot")
        self.auto_cb.setStyleSheet("color: #ccc; font-size: 12px;")

        # NEW: Check actual system state and set the checkbox
        if self.cfg.is_autostart_enabled():
            self.auto_cb.setChecked(True)

        # Check current status (you could store this in settings.json)
        side_layout.addWidget(self.auto_cb)
        self.auto_cb.stateChanged.connect(self.toggle_boot)

        side_layout.addStretch()

        # Canvas
        self.canvas = MonitorCanvas()
        layout.addWidget(self.sidebar)
        layout.addWidget(self.canvas)



        self.canvas.display_monitors(monitors)
        self.set_application_icon()

    def set_application_icon(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "PaperClipper.png")
        if os.path.exists(path):
            icon = QIcon(path)
            self.setWindowIcon(icon)
            QApplication.setWindowIcon(icon)

    def handle_wallpaper_selection(self, monitor_id, image_path):
        """Saves the clip and refreshes the entire desktop state."""
        # 1. Save the new clip
        self.cfg.save_clip(monitor_id, image_path)

        # 2. Get the updated clips list
        settings = self.cfg.load_settings()
        clips = settings.get("clips", {})

        # 3. Apply everything to prevent mirroring
        self.setter.apply_all_saved(self.monitors, clips)

    def toggle_boot(self, state):
        # In PySide6, state can be an integer or a CheckState enum
        # 2 is Checked, 0 is Unchecked
        is_checked = (state == 2 or state == Qt.CheckState.Checked)
        self.cfg.toggle_autostart(is_checked)
        print(f"Autostart enabled: {is_checked}")