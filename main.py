import sys
from PySide6.QtWidgets      import QApplication
from engine.config_manager  import ConfigManager
from engine.hardware        import HardwareEngine, WallpaperSetter
from ui.main_window         import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 1. Initialize Config
    cfg = ConfigManager()

    # (First-run / Portable logic remains here...)
    if not cfg.settings_file.exists():
        # ... [Existing FirstRunDialog Logic] ...
        pass

    cfg.ensure_config_exists()

    # 2. Initialize Engines
    engine = HardwareEngine()
    monitors = engine.get_monitor_data()
    setter = WallpaperSetter()

    # 3. Smart Startup Logic
    # We always pull the data so the UI knows what is "saved"
    profile_data = cfg.get_active_profile_data()
    pref = cfg.get_setting("link_preference", "device")

    # CHECK: Should we actually push these to the OS?
    # This assumes your setting key is 'autostart' or similar in settings.json
    should_auto_apply = cfg.get_setting("autostart", False)

    if should_auto_apply:
        # Pushes saved profile images to the actual desktop
        setter.apply_all_saved(monitors, profile_data, pref)
    else:
        # We do NOT call the setter's apply method.
        # The desktop remains exactly as the user left it.
        print("Autostart is OFF: Monitoring hardware without overriding wallpapers.")

    # 4. Launch GUI
    # The MainWindow still gets the 'monitors' and 'profile_data',
    # so the Canvas will correctly show the images, but the OS is untouched.
    window = MainWindow(monitors, cfg, setter, engine)

    if "--headless" not in sys.argv:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()