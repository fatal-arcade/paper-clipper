import os
from PySide6.QtCore     import Qt, QTimer
from PySide6.QtGui      import QBrush, QColor, QPen, QPainter, QPixmap, QAction
from PySide6.QtWidgets  import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QFileDialog, QMenu
)

class FirstRunDialog(QDialog):
    """Initial setup dialog to choose between Standard and Portable modes."""

    # ---- DUNDER / MAGIC METHODS ----

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

    # ---- PRIVATE METHODS ----

    # ---- PUBLIC METHODS ----

    def set_choice(self, mode):
        self.choice = mode
        self.accept()

class MonitorItem(QGraphicsRectItem):
    """Visual representation of a monitor (Live or Ghost)."""

    # ---- DUNDER / MAGIC METHODS ----

    def __init__(self, x, y, w, h, monitor_data, image_path=None, is_staged=False, is_ghost=False):
        super().__init__(x, y, w, h)
        self.monitor_data = monitor_data
        self.is_ghost = is_ghost

        # 1. Determine Styling
        if is_staged:
            border_color = QColor("#3a86ff")
            border_width = 3
            style = Qt.PenStyle.SolidLine
        elif is_ghost:
            border_color = QColor("#555555")
            border_width = 1
            style = Qt.PenStyle.DashLine
        else:
            border_color = QColor("#444444")
            border_width = 1
            style = Qt.PenStyle.SolidLine

        pen = QPen(border_color, border_width)
        pen.setStyle(style)
        self.setPen(pen)

        # 2. Handle Background Image with Desaturation
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)

            # If ghost, convert to grayscale
            if is_ghost:
                # Use QImage.Format instead of QPixmap.Format
                from PySide6.QtGui import QImage
                image = pixmap.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
                pixmap = QPixmap.fromImage(image)
                self.setOpacity(0.5)

            scaled_pixmap = pixmap.scaled(
                int(w), int(h),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setBrush(QBrush(scaled_pixmap))
        else:
            self.setBrush(QBrush(QColor("#1a1a1a")))

    # ---- PRIVATE METHODS ----

    # ---- PUBLIC METHODS ----

    def contextMenuEvent(self, event):
        # We use the attribute self.is_ghost which we set during __init__
        if not self.is_ghost:
            return

        menu = QMenu()
        # "Forget Device" is more fitting for our 'Inactive Displays' theme
        remove_action = QAction("Forget Device", menu)
        remove_action.triggered.connect(self.request_removal)
        menu.addAction(remove_action)

        menu.exec(event.screenPos())

    def mousePressEvent(self, event):
        if not self.is_ghost:
            self.scene().views()[0].monitor_clicked(self.monitor_data)
        event.accept()

    def request_removal(self):
        # Accessing the canvas to trigger the re-render flow
        # monitor_data['id'] is our consistent way of passing the EDID/ID
        canvas = self.scene().views()[0]
        canvas.remove_ghost_device(self.monitor_data['id'])

class MonitorCanvas(QGraphicsView):
    """The interactive topology map containing live and ghost monitors."""

    # ---- DUNDER / MAGIC METHODS ----

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QBrush(QColor("#1e1e1e")))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.pending_clips = {}

        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._perform_render)

    # ---- PRIVATE METHODS ----

    def _perform_render(self):
        active_hw = getattr(self, 'current_monitors', [])
        if not self.scene:
            return

        self.scene.clear()

        # 1. Pull the profile history from the config manager
        profile_data = self.window().cfg.get_active_profile_data()
        live_ids = {m['id'] for m in active_hw}

        render_list = []

        # --- Build Render List: Live Monitors ---
        for m in active_hw:
            saved_image = None
            for _, entry in profile_data.items():
                if entry.get('device_id') == m['id']:
                    saved_image = entry.get('image')
                    break

            render_list.append({
                **m,
                "is_ghost": False,
                "image": saved_image
            })

        # --- Build Render List: Inactive Monitors ---
        # Position shelf closer and make boxes smaller
        max_live_y = max((m['y'] + m['h']) for m in active_hw) if active_hw else 0
        shelf_y = max_live_y + 150  # Tightened further

        ghost_offset_x = min((m['x']) for m in active_hw) if active_hw else 0

        has_ghosts = False
        for idx, m_meta in profile_data.items():
            if m_meta.get('device_id') not in live_ids:
                has_ghosts = True
                render_list.append({
                    "id": m_meta.get('device_id'),
                    "port": m_meta.get('port', '???'),
                    "name": m_meta.get('device_name', 'Unknown Ghost'),
                    "w": 600, "h": 340,  # MINIATURE BOXES: Reduced from 1280x720
                    "x": ghost_offset_x, "y": shelf_y,
                    "is_ghost": True,
                    "image": m_meta.get('image')
                })
                ghost_offset_x += 450  # Tighter horizontal spacing for small boxes

        if not render_list:
            return

        # 2. Calculate Bounding Box and Scaling
        min_x = min(m['x'] for m in render_list)
        min_y = min(m['y'] for m in render_list)
        max_x = max(m['x'] + m['w'] for m in render_list)
        max_y = max(m['y'] + m['h'] for m in render_list)

        total_w = max_x - min_x
        total_h = max_y - min_y

        view_w, view_h = self.width() * 0.95, self.height() * 0.95
        fit_scale = min(view_w / total_w, view_h / total_h) if total_w > 0 else 0.1

        # 3. Add Section Headers and Dividers
        active_lbl = self.scene.addText("ACTIVE DISPLAYS")
        active_lbl.setHtml("<b style='font-size: 11px; color: #3a86ff; letter-spacing: 1px;'>ACTIVE DISPLAYS</b>")
        active_lbl.setPos(0, -35)

        if has_ghosts:
            line_y = (shelf_y - 75 - min_y) * fit_scale
            divider = self.scene.addLine(0, line_y, total_w * fit_scale, line_y)
            divider.setPen(QPen(QColor("#555555"), 2, Qt.PenStyle.SolidLine))

            ghost_lbl = self.scene.addText("INACTIVE DISPLAYS")
            ghost_lbl.setHtml("<b style='font-size: 11px; color: #aaaaaa; letter-spacing: 1px;'>INACTIVE DISPLAYS</b>")
            ghost_lbl.setPos(0, (shelf_y - 65 - min_y) * fit_scale)

        # 4. Draw Monitors
        for m in render_list:
            sx, sy = (m['x'] - min_x) * fit_scale, (m['y'] - min_y) * fit_scale
            sw, sh = m['w'] * fit_scale, m['h'] * fit_scale

            is_staged = m['id'] in self.pending_clips
            is_ghost = m.get('is_ghost', False)

            staged_path = self.pending_clips.get(m['id'])
            final_path = staged_path if staged_path else m.get('image')

            rect = MonitorItem(sx, sy, sw, sh, m,
                               image_path=final_path,
                               is_staged=is_staged,
                               is_ghost=is_ghost)
            self.scene.addItem(rect)

            # --- Simplified Info for Smaller Boxes ---
            port = m.get('port', '???')
            raw_name = m.get('name', 'Unknown')
            name = (raw_name[:12] + '..') if len(raw_name) > 12 else raw_name

            # For ghosts, resolution is fixed/miniaturized for UI,
            # so we just show Name/Port to keep it readable
            if is_ghost:
                info_text = f"[{port}] {name}"
                font_size = "9px"
            else:
                res = f"{m['w']}x{m['h']}"
                raw_file = os.path.basename(final_path) if final_path else "Empty"
                filename = (raw_file[:12] + '..') if len(raw_file) > 12 else raw_file
                info_text = f"[{port}] {name} | {res} | {filename}"
                font_size = "11px"

            txt = self.scene.addText("")
            txt.document().setDocumentMargin(0)
            txt.setTextWidth(sw)
            txt.setHtml(f"""
                <div style='background-color: rgba(0, 0, 0, 230); 
                            color: white; 
                            padding: 3px; 
                            font-family: monospace; 
                            font-size: {font_size};
                            border-top: 1px solid #333;'>
                    {info_text}
                </div>
            """)

            txt_height = txt.boundingRect().height()
            txt.setPos(sx, (sy + sh) - txt_height)

        self.setSceneRect(self.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50))
        self.centerOn(self.scene.itemsBoundingRect().center())

    # ---- PUBLIC METHODS ----

    def display_monitors(self, monitors):
        self.current_monitors = monitors
        self._perform_render()

    def monitor_clicked(self, data):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Wallpaper", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            self.pending_clips[data['id']] = file_path
            QTimer.singleShot(1, lambda: self.display_monitors(self.window().monitors))

    def remove_ghost_device(self, device_id):
        """Bridge between UI and Config for pruning the Inactive Shelf."""
        if self.window().cfg.remove_monitor_from_profile(device_id):
            # We call our existing render method to wipe the box from the scene
            self._perform_render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_timer.start(50)