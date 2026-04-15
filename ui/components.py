import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton,
                               QHBoxLayout, QGraphicsView, QGraphicsScene,
                               QGraphicsRectItem, QFrame, QFileDialog)
from PySide6.QtGui import QBrush, QColor, QPen, QPainter, QPixmap
from PySide6.QtCore import Qt, QTimer


class FirstRunDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PaperClipper Setup")
        self.setFixedSize(400, 250)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Welcome to PaperClipper</b>"))
        layout.addWidget(QLabel("Choose your settings storage mode:"))

        btn_layout = QHBoxLayout()
        self.btn_std = QPushButton("Standard (~/.config)")
        self.btn_port = QPushButton("Portable (Local Folder)")
        btn_layout.addWidget(self.btn_std)
        btn_layout.addWidget(self.btn_port)
        layout.addLayout(btn_layout)

        self.choice = None
        self.btn_std.clicked.connect(lambda: self.set_choice("STANDARD"))
        self.btn_port.clicked.connect(lambda: self.set_choice("PORTABLE"))

    def set_choice(self, mode):
        self.choice = mode
        self.accept()


class MonitorItem(QGraphicsRectItem):
    def __init__(self, x, y, w, h, monitor_data, image_path=None, is_staged=False):
        super().__init__(x, y, w, h)
        self.monitor_data = monitor_data

        # 1. Determine Styling
        border_color = QColor("#3a86ff") if is_staged else QColor("#444444")
        border_width = 3 if is_staged else 1
        self.setPen(QPen(border_color, border_width))

        # 2. Handle Background Image
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            # Scale pixmap to fill the box while maintaining smoothness
            scaled_pixmap = pixmap.scaled(
                int(w), int(h),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setBrush(QBrush(scaled_pixmap))
        else:
            # Fallback to dark grey if no path is found/provided
            self.setBrush(QBrush(QColor("#1a1a1a")))

    def mousePressEvent(self, event):
        # We handle the click but DON'T call super() at the end
        # to prevent it from trying to access a deleted object.
        self.scene().views()[0].monitor_clicked(self.monitor_data)
        event.accept()


class MonitorCanvas(QGraphicsView):

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QBrush(QColor("#1e1e1e")))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.pending_clips = {}

        # NEW: Debounce timer for smooth resizing on low-end hardware
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._perform_render)

    def monitor_clicked(self, data):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Wallpaper", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            self.pending_clips[data['id']] = file_path
            # FIX: trigger refresh after event loop finishes
            QTimer.singleShot(1, lambda: self.display_monitors(self.window().monitors))

    def display_monitors(self, monitors):
        """Public method to trigger a redraw."""
        # Store monitors for the timer-based render
        self.current_monitors = monitors
        self._perform_render()

    def _perform_render(self):
        """The actual heavy-lifting render logic."""
        monitors = getattr(self, 'current_monitors', None)
        if not self.scene or not monitors:
            return

        self.scene.clear()

        # 1. Calculate the total bounding box of all monitors in raw pixels
        min_x = min(m['x'] for m in monitors)
        min_y = min(m['y'] for m in monitors)
        max_x = max(m['x'] + m['w'] for m in monitors)
        max_y = max(m['y'] + m['h'] for m in monitors)

        total_w = max_x - min_x
        total_h = max_y - min_y

        # 2. Calculate scale factor to fit within view (90% of available space)
        view_w, view_h = self.width() * 0.9, self.height() * 0.9
        fit_scale = min(view_w / total_w, view_h / total_h) if total_w > 0 else 0.1

        active_settings = self.window().cfg.load_settings()
        active_clips = active_settings.get("clips", {})

        # 3. Draw Monitors and Panels
        for m in monitors:
            # Map raw coordinates to scaled UI coordinates
            sx, sy = (m['x'] - min_x) * fit_scale, (m['y'] - min_y) * fit_scale
            sw, sh = m['w'] * fit_scale, m['h'] * fit_scale

            # Determine image path priority: Staged > Active > None
            staged_path = self.pending_clips.get(m['id'])
            active_path = active_clips.get(m['id'])
            final_path = staged_path if staged_path else active_path
            is_staged = m['id'] in self.pending_clips

            # Create the monitor background box
            rect = MonitorItem(sx, sy, sw, sh, m, image_path=final_path, is_staged=is_staged)
            self.scene.addItem(rect)

            # --- FLUSH-MOUNT PANEL LOGIC ---
            display_id = m['port']
            status_text = "ACTIVE"
            filename = ""

            if is_staged:
                status_text = "STAGED"
                filename = os.path.basename(staged_path)
            elif active_path:
                filename = os.path.basename(active_path)
            else:
                status_text = "EMPTY"

            # Truncate filename for panel cleanliness
            if len(filename) > 20:
                filename = filename[:17] + "..."

            # Construct the single-line panel string
            panel_info = f"<b>{display_id}</b> {m['w']}x{m['h']} | "
            panel_info += f"{status_text}: {filename}" if filename else f"{status_text}"

            txt = self.scene.addText("")
            # Strip default Qt margins for a flush fit
            txt.document().setDocumentMargin(0)

            txt.setTextWidth(sw)
            # Stretch HTML background to 100% width of the scaled box
            txt.setHtml(f"""
                <div style='background-color: rgba(0, 0, 0, 235); 
                            color: white; 
                            width: 100%; 
                            padding: 4px; 
                            font-family: monospace; 
                            font-size: 10px;
                            border-top: 1px solid #333;'>
                    {panel_info}
                </div>
            """)

            # Anchor precisely to the bottom-left of the monitor rectangle
            txt_height = txt.boundingRect().height()
            txt.setPos(sx, (sy + sh) - txt_height)
            # --------------------------------

        # 4. Finalize scene centering and bounds
        self.setSceneRect(self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20))
        self.centerOn(self.scene.itemsBoundingRect().center())

    def resizeEvent(self, event):
        """Debounced resize handler."""
        super().resizeEvent(event)
        # 50ms is fast enough to feel responsive,
        # but slow enough to skip unnecessary intermediate frames.
        self.resize_timer.start(50)