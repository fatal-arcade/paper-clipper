import json
import sys
import os
from pathlib import Path

class ConfigManager:
    def __init__(self):
        self.root_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.portable_flag = self.root_dir / "portable.mode"
        self.config_dir = self._resolve_config_path()

    def _resolve_config_path(self):
        if self.portable_flag.exists():
            return self.root_dir / "config"
        return Path(os.path.expanduser("~/.config/paper-clipper"))

    def ensure_config_exists(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        return self.config_dir

    def get_settings_file(self):
        return self.config_dir / "settings.json"

    def is_autostart_enabled(self):
        """Checks if the .desktop file exists in the autostart directory."""
        desktop_file = Path(os.path.expanduser("~/.config/autostart/paper-clipper.desktop"))
        return desktop_file.exists()

    def save_clip(self, monitor_id, image_path):
        data = self.load_settings()
        if "clips" not in data:
            data["clips"] = {}
        data["clips"][monitor_id] = image_path
        with open(self.get_settings_file(), "w") as f:
            json.dump(data, f, indent=4)

    def load_settings(self):
        settings_file = self.get_settings_file()
        if not settings_file.exists():
            return {"clips": {}}
        try:
            with open(settings_file, "r") as f:
                return json.load(f)
        except:
            return {"clips": {}}

    def toggle_autostart(self, enabled=True):
        """Creates or removes a .desktop file in ~/.config/autostart/"""
        autostart_dir = Path(os.path.expanduser("~/.config/autostart"))
        autostart_dir.mkdir(parents=True, exist_ok=True)
        desktop_file = autostart_dir / "paper-clipper.desktop"

        if enabled:
            # Get path to current python executable and main.py
            python_exe = sys.executable
            script_path = os.path.join(self.root_dir, "main.py")

            content = f"""[Desktop Entry]

Type=Application
Name=PaperClipper
Exec={python_exe} {script_path} --headless
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=Hardware-aware Wallpaper Manager
            """
            with open(desktop_file, "w") as f:
                f.write(content)
        else:
            if desktop_file.exists():
                desktop_file.unlink()