import sys
import os
import argparse
from PySide6.QtWidgets import QApplication
from engine.config_manager import ConfigManager
from engine.hardware import HardwareEngine, WallpaperSetter
from ui.main_window import MainWindow
from ui.components import FirstRunDialog

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def main():
    # Parse CLI arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="Apply wallpapers and exit")
    args = parser.parse_args()

    # Standard initialization
    app = QApplication(sys.argv)
    app.setApplicationName("PaperClipper")
    cfg = ConfigManager()

    # ... (Keep First-Run logic) ...

    cfg.ensure_config_exists()
    hw = HardwareEngine()
    monitors = hw.get_monitor_data()

    settings = cfg.load_settings()
    saved_clips = settings.get("clips", {})

    setter = WallpaperSetter()
    setter.apply_all_saved(monitors, saved_clips)

    # HEADLESS CHECK: If triggered by autostart, we stop here.
    if args.headless:
        print("Headless apply complete. Exiting.")
        sys.exit(0)

    # Otherwise, proceed to GUI
    window = MainWindow(monitors, cfg, setter)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)