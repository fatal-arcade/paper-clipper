import os
from PySide6.QtWidgets import QMainWindow, QHBoxLayout, QVBoxLayout, QWidget, QFrame, QLabel, QApplication, QCheckBox, QPushButton
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

        #Central
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("background-color: #252526; border-right: 1px solid #333;")
        side_layout = QVBoxLayout(self.sidebar)

        # --- Settings Section ---
        lbl_settings = QLabel("SETTINGS")
        lbl_settings.setStyleSheet("color: #555; font-weight: bold; font-size: 10px;")
        side_layout.addWidget(lbl_settings)

        # Autostart Checkbox
        self.auto_cb = QCheckBox("Start on Boot")
        self.auto_cb.setStyleSheet("color: #ccc;")
        if self.cfg.is_autostart_enabled():
            self.auto_cb.setChecked(True)
        side_layout.addWidget(self.auto_cb)
        self.auto_cb.stateChanged.connect(self.toggle_boot)

        side_layout.addSpacing(20)

        # --- Actions Section ---
        lbl_actions = QLabel("ACTIONS")
        lbl_actions.setStyleSheet("color: #555; font-weight: bold; font-size: 10px;")
        side_layout.addWidget(lbl_actions)

        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.setStyleSheet("""
                    QPushButton { 
                        background-color: #0e639c; color: white; border: none; padding: 8px; border-radius: 2px;
                    }
                    QPushButton:hover { background-color: #1177bb; }
                    QPushButton:pressed { background-color: #06436c; }
                """)
        self.apply_btn.clicked.connect(self.commit_changes)
        side_layout.addWidget(self.apply_btn)

        side_layout.addStretch()

        # Canvas
        self.canvas = MonitorCanvas()
        layout.addWidget(self.sidebar)
        layout.addWidget(self.canvas)

        self.canvas.display_monitors(monitors)

        # Call the icon loader at the end of init
        self.set_application_icon()

    def commit_changes(self):
        """Finalizes all staged wallpapers at once."""
        if not self.canvas.pending_clips:
            print("Nothing to apply.")
            return

        # 1. Save all pending items to the JSON config
        for m_id, path in self.canvas.pending_clips.items():
            self.cfg.save_clip(m_id, path)

        # 2. Clear the staging area NOW that they are saved
        self.canvas.pending_clips = {}

        # 3. Pull the full current state from config and push to hardware
        settings = self.cfg.load_settings()
        clips = settings.get("clips", {})
        self.setter.apply_all_saved(self.monitors, clips)

        # 4. Refresh the UI to show the 'staged' highlights are gone
        self.canvas.display_monitors(self.monitors)
        print("Hardware state synchronized.")

    def set_application_icon(self):
        # Use the root_dir from our config manager to build a rock-solid path
        icon_path = self.cfg.root_dir / "assets" / "icons" / "PaperClipper.png"

        if icon_path.exists():
            icon = QIcon(str(icon_path))
            self.setWindowIcon(icon)
            # This ensures the icon shows up in the taskbar/dock on GNOME/KDE/Mint
            QApplication.setWindowIcon(icon)
        else:
            print(f"DEBUG: Icon not found at {icon_path}")

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