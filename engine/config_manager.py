import json
import sys
import os
from pathlib    import Path
from datetime   import datetime

class ConfigManager:

    # ---- DUNDER / MAGIC METHODS ----

    def __init__(self):
        self.root_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.portable_flag = self.root_dir / "portable.mode"
        self.config_dir = self._resolve_config_path()

        # The Two-File Architecture
        self.settings_file = self.config_dir / "settings.json"
        self.profiles_file = self.config_dir / "profiles.json"

        self.ensure_config_exists()

    # ---- PRIVATE METHODS ----

    def _load_json(self, file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _resolve_config_path(self):
        if self.portable_flag.exists():
            return self.root_dir / "config"
        return Path(os.path.expanduser("~/.config/paper-clipper"))

    def _save_json(self, file_path, data):
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)

    # ---- PUBLIC METHODS ----

    def ensure_config_exists(self):
        """Initializes both files with their distinct default structures."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.settings_file.exists():
            self._save_json(self.settings_file, {
                "active_profile": "default_profile",
                "link_preference": "device",
                "autostart": False
            })

        if not self.profiles_file.exists():
            self._save_json(self.profiles_file, {
                "profiles": {
                    "default_profile": {}
                }
            })

    def get_active_profile_data(self):
        """Retrieves the hardware dictionary for the currently selected profile."""
        active_name = self.get_setting("active_profile", "default_profile")
        profiles_data = self._load_json(self.profiles_file).get("profiles", {})
        return profiles_data.get(active_name, {})

    def get_profile(self, key, default=None):
        json = self._load_json(self.profiles_file)
        json = json.get("profiles")
        json = json.get(key, default)
        return json

    def get_setting(self, key, default=None):
        return self._load_json(self.settings_file).get(key, default)

    def is_autostart_enabled(self):
        """Checks the setting in settings.json to see if autostart should be active."""
        return self.get_setting("autostart", False)

    def remove_monitor_from_profile(self, device_id):
        """
        Removes a monitor entry from the active profile and re-indexes.
        """
        # 1. Identify the active profile name
        active_name = self.get_setting("active_profile", "default_profile")

        # 2. Access the profile dictionary from the profiles object
        if not hasattr(self, 'profiles_file') or not self.get_profile(active_name, False):
            return False

        profile_content = self.get_profile(active_name)

        # 3. Find the key to delete
        target_key = None

        for key, entry in profile_content.items():
            if entry.get('device_id') == device_id:
                target_key = key
                break

        if target_key is not None:
            del profile_content[target_key]
            profiles = self._load_json(self.profiles_file)
            profiles["profiles"][active_name] = profile_content
            self._save_json(self.profiles_file, profiles)

        return

    def save_to_profile(self, index, monitor_info):
        """
        Saves a rich metadata block to the active profile in profiles.json.
        monitor_info: {image, device_id, device_name, port, is_active}
        """
        active_name = self.get_setting("active_profile", False)
        if not active_name: return

        full_data = self._load_json(self.profiles_file)

        if "profiles" not in full_data:
            full_data["profiles"] = {}

        if active_name not in full_data["profiles"]:
            full_data["profiles"][active_name] = {}

        # Inject current timestamp before saving
        monitor_info["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_data["profiles"][active_name][str(index)] = monitor_info

        self._save_json(self.profiles_file, full_data)

    def set_setting(self, key, value):
        data = self._load_json(self.settings_file)
        data[key] = value
        self._save_json(self.settings_file, data)

    def toggle_autostart(self, enabled=True):
        """Creates or removes a .desktop file and updates settings.json."""
        self.set_setting("autostart", enabled)

        autostart_dir = Path(os.path.expanduser("~/.config/autostart"))
        desktop_file = autostart_dir / "paper-clipper.desktop"

        if enabled:
            autostart_dir.mkdir(parents=True, exist_ok=True)
            python_exe = sys.executable
            # Ensure the path to main.py is absolute
            script_path = self.root_dir / "main.py"
            icon_path = self.root_dir / "assets" / "icons" / "pc-logo.png"

            content = f"""[Desktop Entry]
Type=Application
Name=PaperClipper
Exec={python_exe} {script_path} --headless
Icon={icon_path}
Comment=Hardware-aware Wallpaper Manager
Terminal=false
"""
            with open(desktop_file, "w") as f:
                f.write(content)
        else:
            if desktop_file.exists():
                desktop_file.unlink()