import subprocess
import re
import os
import shutil
import hashlib
from pathlib import Path


class HardwareEngine:

    def __init__(self):
        self.drm_path = Path("/sys/class/drm")

    def get_monitor_data(self):
        hw_fingerprints = {}
        fingerprint_list = []

        if self.drm_path.exists():
            connectors = sorted([c for c in self.drm_path.iterdir() if "-" in c.name])
            for connector in connectors:
                edid_file = connector / "edid"
                status_file = connector / "status"
                if status_file.exists():
                    with open(status_file, "r") as f:
                        if f.read().strip() == "connected" and edid_file.exists():
                            with open(edid_file, "rb") as ef:
                                # FIX: Use hashlib for a persistent ID
                                edid_data = ef.read()
                                f_print = hashlib.md5(edid_data).hexdigest()

                                raw_name = connector.name.split("-", 1)[1]
                                hw_fingerprints[raw_name] = f_print
                                fingerprint_list.append(f_print)

        monitors = []
        try:
            output = subprocess.check_output(["xrandr", "--query"]).decode()
            pattern = r"(\S+) connected (?:primary )?(\d+)x(\d+)\+(\d+)\+(\d+)"
            matches = re.findall(pattern, output)

            for i, (port, w, h, x, y) in enumerate(matches):
                final_id = "unknown"
                if port in hw_fingerprints:
                    final_id = hw_fingerprints[port]
                else:
                    clean_port = port.replace("-", "").upper()
                    for hw_port, f_print in hw_fingerprints.items():
                        if clean_port in hw_port.replace("-", "").upper():
                            final_id = f_print
                            break

                if final_id == "unknown" and i < len(fingerprint_list):
                    final_id = fingerprint_list[i]

                monitors.append({
                    "port": port, "id": final_id,
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

    def _get_desktop_environment(self):
        """Detects the current Linux Desktop Environment."""
        de = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
        if not de:
            de = os.environ.get("DESKTOP_SESSION", "").upper()
        return de

    def is_tool_installed(self, name):
        """Checks if a command-line tool exists on the system."""
        return shutil.which(name) is not None

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

    def apply_all_saved(self, monitors, clips):
        """
        Gathers all images and applies them in one command
        to prevent mirroring/overwriting.
        """
        image_paths = []
        for m in monitors:
            m_id = m['id']
            # Get the path if it exists, otherwise use a fallback/empty string
            path = clips.get(m_id, "")
            if path and os.path.exists(path):
                image_paths.append(os.path.abspath(path))
            else:
                # If no clip is saved, we don't want to shift the order,
                # so we skip or use a default. For now, we only apply
                # if we have a full set or the setter supports individual ports.
                image_paths.append("")

        self._dispatch_batch(image_paths, monitors)
