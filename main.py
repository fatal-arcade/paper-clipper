import sys
from PySide6.QtWidgets      import QApplication
from engine.config_manager  import ConfigManager
from engine.hardware        import HardwareEngine, WallpaperSetter
from ui.main_window         import MainWindow


def main():
    app = QApplication(sys.argv)

    # 1. Initialize Config & Handle First Run
    cfg = ConfigManager()

    # If settings.json doesn't exist, it's a fresh install or new location
    if not cfg.settings_file.exists():
        from ui.components import FirstRunDialog
        dr = FirstRunDialog()
        if dr.exec():
            if dr.choice == "PORTABLE":
                # Create the flag file to force portable mode on next init
                with open(cfg.root_dir / "portable.mode", "w") as f:
                    f.write("")
                # Re-initialize to update internal paths to the local /config folder
                cfg = ConfigManager()

    # Ensure directories and default files are actually on disk
    cfg.ensure_config_exists()

    # 2. Initialize Engines
    engine = HardwareEngine()
    monitors = engine.get_monitor_data()
    setter = WallpaperSetter()

    # 3. Initial Wallpaper Application (Startup/Headless Logic)
    # Pull rich profile data and user preference
    profile_data = cfg.get_active_profile_data()
    pref = cfg.get_setting("link_preference", "device")

    # The setter now handles the matching logic internally using the rich data
    setter.apply_all_saved(monitors, profile_data, pref)

    # 4. Headless Check
    if "--headless" in sys.argv:
        # In a future update, we can keep the loop alive here for a tray-only mode
        # For now, headless just applies and exits
        return

    # 5. Launch GUI
    window = MainWindow(monitors, cfg, setter, engine)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()