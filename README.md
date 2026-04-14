# PaperClipper
![PaperClipper Logo](https://www.github.com/fatal-arcade/paper-clipper/PaperClipper.png)
**A casual, hardware-aware wallpaper manager for Linux.**

PaperClipper is a utility born out of a simple frustration: the way many Linux systems "forget" which wallpaper goes on which screen the moment you swap a cable or reboot with a different display configuration. 

The goal of this project is to make multi-display wallpaper assignment persistent and logical, regardless of whether you're on Mint, Fedora, Arch, or any other distro.

### Persistence That Makes Sense
Instead of relying on volatile port indices, PaperClipper lets you choose how your desktop is remembered:

* **The Hardware ID (EDID):** Wallpapers are "clipped" to the unique serial number of your monitor. If you move the monitor to a different port, the wallpaper follows it.
* **The Physical Port:** Alternatively, you can tie wallpapers to a specific spot in your device's I/O—useful for docking stations where the hardware might change but the desk layout stays the same.

### Profiles & Scheduling
* **Seasonal Profiles:** Save entire multi-monitor configurations as profiles. Switch between "Work," "Nightly," or "Holiday" themes without manually reassigning every screen.
* **The Scheduler:** Includes a built-in timer to rotate your wallpapers or switch profiles on a specific schedule, keeping your workspace fresh.

### Under the Hood
* **Language:** Python
* **Interface:** Qt (via PySide6)
* **License:** GPL v3 (FOSS)

---
*I'm just fixing a personal annoyance—hopefully, it makes your Linux experience a little smoother, too.*
