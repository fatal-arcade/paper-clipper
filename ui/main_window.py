import os
from ui.components      import MonitorCanvas
from PySide6.QtGui      import QIcon, QAction, QGuiApplication
from PySide6.QtCore     import Qt
from PySide6.QtWidgets  import (
    QMainWindow, QHBoxLayout, QVBoxLayout,
    QWidget, QFrame, QLabel, QApplication,
    QCheckBox, QPushButton, QSystemTrayIcon,
    QMenu, QComboBox
)

class MainWindow(QMainWindow):

    # ---- DUNDER / MAGIC METHODS ----

    def __init__(self, monitors, config_manager, setter, engine):
        super().__init__()
        self.monitors = monitors
        self.cfg = config_manager
        self.setter = setter
        self.engine = engine
        self.setWindowTitle("PaperClipper")
        self.resize(1100, 700) # Slightly larger to accommodate the shelf

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Sidebar ---
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(220)
        self.sidebar.setStyleSheet("background-color: #252526; border-right: 1px solid #333;")
        side_layout = QVBoxLayout(self.sidebar)

        # Settings: Link Preference
        lbl_pref = QLabel("LINK PREFERENCE")
        lbl_pref.setStyleSheet("color: #555; font-weight: bold; font-size: 10px; margin-top: 10px;")
        side_layout.addWidget(lbl_pref)

        self.pref_combo = QComboBox()
        self.pref_combo.addItems(["Device-Centric", "Port-Centric"])
        current_pref = self.cfg.get_setting("link_preference", "device")
        self.pref_combo.setCurrentText("Device-Centric" if current_pref == "device" else "Port-Centric")
        self.pref_combo.currentTextChanged.connect(self._handle_pref_change)
        side_layout.addWidget(self.pref_combo)

        # Settings: Autostart
        self.auto_cb = QCheckBox("Start on Boot")
        self.auto_cb.setStyleSheet("color: #ccc; margin-top: 10px;")
        self.auto_cb.setChecked(self.cfg.is_autostart_enabled())
        self.auto_cb.stateChanged.connect(self.toggle_boot)
        side_layout.addWidget(self.auto_cb)

        side_layout.addSpacing(20)

        # Actions
        self.apply_btn = QPushButton("Commit Changes")
        self.apply_btn.setStyleSheet("""
            QPushButton { background-color: #0e639c; color: white; border: none; padding: 8px; border-radius: 2px; }
            QPushButton:hover { background-color: #1177bb; }
        """)
        self.apply_btn.clicked.connect(self.commit_changes)
        side_layout.addWidget(self.apply_btn)

        self.refresh_btn = QPushButton("Scan Hardware")
        self.refresh_btn.clicked.connect(self._handle_hardware_change)
        side_layout.addWidget(self.refresh_btn)

        side_layout.addStretch()

        # --- Canvas ---
        self.canvas = MonitorCanvas()
        layout.addWidget(self.sidebar)
        layout.addWidget(self.canvas)

        self.canvas.display_monitors(monitors)
        self._setup_hardware_listener()
        self.set_application_icon()
        self._setup_tray()

    # ---- PRIVATE METHODS ----

    def _handle_hardware_change(self, *args):
        """Re-scans hardware and updates the UI automatically."""
        print("DEBUG: Hardware/Topology refresh triggered.")

        # 1. Re-scan using the stored engine
        self.monitors = self.engine.get_monitor_data()

        # 2. Update the topology canvas
        if hasattr(self, 'canvas'):
            self.canvas.display_monitors(self.monitors)

        # 3. Re-connect geometry listeners for the (potentially new) screen set
        for screen in QGuiApplication.screens():
            try:
                screen.geometryChanged.disconnect(self._handle_hardware_change)
            except (RuntimeError, TypeError):
                pass  # Safe to ignore if not connected
            screen.geometryChanged.connect(self._handle_hardware_change)

        print(f"DEBUG: Refresh complete. {len(self.monitors)} displays detected.")

    def _handle_pref_change(self, text):
        pref = "device" if "Device" in text else "port"
        self.cfg.set_setting("link_preference", pref)
        print(f"Logic Pivot: Matching now set to {pref}")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()

    def _setup_hardware_listener(self):
        """Connects OS-level display signals to the UI refresh logic."""
        # Get the running application instance
        app_instance = QGuiApplication.instance()

        if not app_instance:
            return

        # Detects when a monitor is plugged in
        app_instance.screenAdded.connect(self._handle_hardware_change)

        # Detects when a monitor is unplugged
        app_instance.screenRemoved.connect(self._handle_hardware_change)

        # Detects resolution or orientation changes for existing screens
        for screen in QGuiApplication.screens():
            screen.geometryChanged.connect(self._handle_hardware_change)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        icon_path = self.cfg.root_dir / "assets" / "icons" / "pc-logo.png"

        if icon_path.exists():
            self.tray.setIcon(QIcon(str(icon_path)))

        # Tray Menu
        self.tray_menu = QMenu()

        show_action = QAction("Open PaperClipper", self)
        show_action.triggered.connect(self.showNormal)

        apply_action = QAction("Apply Saved Wallpapers", self)
        apply_action.triggered.connect(self.apply_all_current)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        refresh_action = QAction("Refresh Hardware", self)
        refresh_action.triggered.connect(self._handle_hardware_change)

        self.tray_menu.addAction(show_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(refresh_action)
        self.tray_menu.addAction(apply_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(quit_action)

        self.tray.setContextMenu(self.tray_menu)
        self.tray.show()

        # Handle double click on tray icon
        self.tray.activated.connect(self._on_tray_activated)

    # ---- PUBLIC METHODS ----

    def apply_all_current(self):
        """Passes the rich profile data and preference to the setter."""
        profile_data = self.cfg.get_active_profile_data()
        pref = self.cfg.get_setting("link_preference", "device")

        # The setter now handles the dictionary-to-list matching logic internally
        self.setter.apply_all_saved(self.monitors, profile_data, pref)

    def closeEvent(self, event):
        """Override close to minimize to tray instead of exiting."""
        if self.tray.isVisible():
            self.hide()
            event.ignore()
            # Optional: Add a 'toast' notification for first-time users
            # self.tray.showMessage("PaperClipper", "Running in tray")

    def commit_changes(self):
        """Saves staged metadata to profiles.json and applies wallpapers."""
        if not self.canvas.pending_clips:
            return

        # 1. Update the profile with new assignments
        for m_id, path in self.canvas.pending_clips.items():
            # Find the monitor object in current hardware to get its metadata
            m_obj = next((m for m in self.monitors if m['id'] == m_id), None)
            if m_obj:
                info = {
                    "image": path,
                    "device_id": m_id,
                    "device_name": m_obj['name'],
                    "port": m_obj['port'],
                    "is_active": True
                }
                # We use the list index for the profiles.json slot
                idx = self.monitors.index(m_obj)
                self.cfg.save_to_profile(idx, info)

        self.canvas.pending_clips = {}

        # 2. Re-apply wallpapers based on updated profile
        self.apply_all_current()
        self.canvas.display_monitors(self.monitors)

    def handle_wallpaper_selection(self, monitor_id, image_path):
        """Saves the clip and refreshes the entire desktop state."""
        # 1. Save the new clip
        self.cfg.save_clip(monitor_id, image_path)

        # 2. Get the updated clips list
        settings = self.cfg.load_settings()
        clips = settings.get("clips", {})

        # 3. Apply everything to prevent mirroring
        self.setter.apply_all_saved(self.monitors, clips)

    def set_application_icon(self):
        # Use the root_dir from our config manager to build a rock-solid path
        icon_path = self.cfg.root_dir / "assets" / "icons" / "pc-logo.png"

        if icon_path.exists():
            icon = QIcon(str(icon_path))
            self.setWindowIcon(icon)
            # This ensures the icon shows up in the taskbar/dock on GNOME/KDE/Mint
            QApplication.setWindowIcon(icon)
        else:
            print(f"DEBUG: Icon not found at {icon_path}")

    def toggle_boot(self, state):
        # In PySide6, state can be an integer or a CheckState enum
        # 2 is Checked, 0 is Unchecked
        is_checked = (state == 2 or state == Qt.CheckState.Checked)
        self.cfg.toggle_autostart(is_checked)
        print(f"Autostart enabled: {is_checked}")