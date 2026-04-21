import os
import re
import shutil
import hashlib
import subprocess
from pathlib import Path

class HardwareEngine:

    def __init__(self):
        self.drm_path = Path("/sys/class/drm")

    def _get_device_name_from_edid(self, edid_data):
        """
        Extracts the human-readable monitor name from EDID binary data.
        Searches for the ASCII descriptor block (type 0xFC).
        """
        try:
            # The EDID monitor name block usually starts with 00 00 00 FC 00
            pattern = b'\x00\x00\x00\xfc\x00'
            idx = edid_data.find(pattern)
            if idx != -1:
                name_bytes = edid_data[idx + 5: idx + 18]
                return name_bytes.decode('ascii').strip()
        except:
            pass
        return "Unknown Display"

    def get_monitor_data(self):
        """
        Returns a list of rich metadata dictionaries for currently connected monitors.
        """
        hw_info = {}  # Maps port names to {id, name}

        if self.drm_path.exists():
            connectors = sorted([c for c in self.drm_path.iterdir() if "-" in c.name])
            for connector in connectors:
                edid_file = connector / "edid"
                status_file = connector / "status"

                if status_file.exists():
                    with open(status_file, "r") as f:
                        if f.read().strip() == "connected" and edid_file.exists():
                            with open(edid_file, "rb") as ef:
                                edid_data = ef.read()
                                f_print = hashlib.md5(edid_data).hexdigest()
                                name = self._get_device_name_from_edid(edid_data)

                                # xrandr uses 'HDMI-1', sysfs uses 'card0-HDMI-A-1'
                                # We strip the 'card0-' prefix for easier matching
                                raw_port = connector.name.split("-", 1)[1]
                                hw_info[raw_port] = {"id": f_print, "name": name}

        monitors = []
        try:
            output = subprocess.check_output(["xrandr", "--query"]).decode()
            # Matches port, width, height, x-offset, y-offset
            pattern = r"(\S+) connected (?:primary )?(\d+)x(\d+)\+(\d+)\+(\d+)"
            matches = re.findall(pattern, output)

            for i, (port, w, h, x, y) in enumerate(matches):
                # Match xrandr port to sysfs metadata
                meta = hw_info.get(port, {"id": f"unknown-{i}", "name": "Generic Monitor"})

                # If direct match fails, try a fuzzy match (e.g., HDMI-1 vs HDMI-A-1)
                if meta["id"].startswith("unknown"):
                    clean_port = port.replace("-", "").upper()
                    for hw_port, data in hw_info.items():
                        if clean_port in hw_port.replace("-", "").upper():
                            meta = data
                            break

                monitors.append({
                    "port": port,
                    "id": meta["id"],
                    "name": meta["name"],
                    "w": int(w), "h": int(h), "x": int(x), "y": int(y)
                })
        except Exception as e:
            print(f"Hardware Engine Error: {e}")

        return monitors

class WallpaperSetter:

    def __init__(self):
        self.desktop_env = self._get_desktop_environment()

    def _dispatch_batch(self, image_paths, monitors):
        """Determines the best command to set multiple backgrounds at once."""
        # Filter out empty paths for tools that don't like gaps
        valid_paths = [p for p in image_paths if p]
        if not valid_paths:
            return

        if "KDE" in self.desktop_env:
            # KDE specific: Iterate monitors and apply individually
            for i, path in enumerate(image_paths):
                if path:
                    self.apply(path, port=monitors[i]['port'])

        elif "XFCE" in self.desktop_env:
            for i, path in enumerate(image_paths):
                if path:
                    self.apply(path, port=monitors[i]['port'])

        else:
            # UNIVERSAL: feh handles multiple monitors by taking multiple arguments
            # syntax: feh --bg-fill /path/to/img1.jpg /path/to/img2.jpg
            if self.is_tool_installed("feh"):
                # We filter to ensure we aren't passing empty strings to the shell
                subprocess.run(["feh", "--bg-fill"] + [p for p in image_paths if p])

            elif "GNOME" in self.desktop_env:
                # GNOME remains the 'odd one out'—it natively mirrors unless
                # the image itself is a pre-stitched 'super-image'.
                # For now, we apply the first valid clip found.
                subprocess.run(
                    ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{valid_paths[0]}"])

    def _execute_set_command(self, monitors, paths):
        """The actual shell execution logic you had previously."""
        # Ensure we only try to set paths that actually exist
        cmd = ["feh", "--bg-fill"]
        valid = False
        for path in paths:
            if path and os.path.exists(path):
                cmd.append(path)
                valid = True
            else:
                # Fallback for empty slots to prevent feh from shifting images
                cmd.append("/usr/share/backgrounds/default.png")

        if valid:
            subprocess.Popen(cmd)

    def _get_desktop_environment(self):
        """Detects the current Linux Desktop Environment."""
        de = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
        if not de:
            de = os.environ.get("DESKTOP_SESSION", "").upper()
        return de

    def apply(self, image_path, port=None):
        """Runs the system command to set the wallpaper for a specific port."""
        path = os.path.abspath(image_path)

        try:
            if "KDE" in self.desktop_env:
                # KDE allows targeting specific screens via indices
                # We'll use a script that attempts to match the screen name
                script = f"""
                var allDesktops = desktops();
                for (var i = 0; i < allDesktops.length; i++) {{
                    if (allDesktops[i].name == "{port}" || allDesktops.length > 1) {{
                        allDesktops[i].wallpaperPlugin = "org.kde.image";
                        allDesktops[i].currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");
                        allDesktops[i].writeConfig("Image", "file://{path}");
                    }}
                }}
                """
                subprocess.run(
                    ["qdbus", "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript", script])

            elif "XFCE" in self.desktop_env:
                # XFCE is great for this; we just need to find the right monitor index
                # This assumes monitor0, monitor1, etc. mapping
                mon_index = port[-1] if port[-1].isdigit() else "0"
                subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-p",
                                f"/backdrop/screen0/monitor{mon_index}/workspace0/last-image", "-s", path])

            else:
                # UNIVERSAL FIX: Use 'feh' with the --display or specific geometry
                # Since we know the port from xrandr, we use --bg-fill specifically
                # For many WMs, feh manages multiple monitors by receiving a list of files
                # in the order they appear in xrandr.

                # To do this per-monitor, we actually need to pass ALL wallpapers at once
                # Let's use the 'feh' per-monitor syntax if possible:
                if self.is_tool_installed("feh"):
                    # This is the "Zero-Jank" way for feh: feh --bg-fill img1.jpg img2.jpg
                    # But we need to know the order. For now, let's use the simplest per-port command:
                    subprocess.run(["feh", "--bg-fill", path])
                    # Note: If feh is setting both, we will refine this to a "Batch Apply" in the next step.

                elif "GNOME" in self.desktop_env:
                    # GNOME limitation: Native GNOME doesn't support different wallpapers
                    # per monitor without extensions like 'Multi-monitors Add-on'.
                    # We will set it globally for now, but log the limitation.
                    subprocess.run(
                        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{path}"])

        except Exception as e:
            print(f"Failed to set wallpaper: {e}")

    def apply_all_saved(self, monitors, profile_data, link_pref="device"):
        """Matches current hardware against the profile registry."""
        final_paths = []

        for m in monitors:
            matched_path = ""

            # Use .values() because profile_data is { "0": {...}, "1": {...} }
            entries = profile_data.values() if isinstance(profile_data, dict) else []

            # 1. Try Preferred Match
            for entry in entries:
                if not isinstance(entry, dict): continue  # Safety check

                if link_pref == "device" and entry.get('device_id') == m['id']:
                    matched_path = entry.get('image')
                    break
                elif link_pref == "port" and entry.get('port') == m['port']:
                    matched_path = entry.get('image')
                    break

            # 2. Fallback to Secondary Match
            if not matched_path:
                for entry in entries:
                    if not isinstance(entry, dict): continue

                    if link_pref == "device" and entry.get('port') == m['port']:
                        matched_path = entry.get('image')
                        break
                    elif link_pref == "port" and entry.get('device_id') == m['id']:
                        matched_path = entry.get('image')
                        break

            final_paths.append(matched_path)

        self._execute_set_command(monitors, final_paths)

    def is_tool_installed(self, name):
        """Checks if a command-line tool exists on the system."""
        return shutil.which(name) is not None




