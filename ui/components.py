import os
from PySide6.QtCore     import Qt, QTimer
from PySide6.QtGui      import QBrush, QColor, QPen, QPainter, QPixmap
from PySide6.QtWidgets  import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QFileDialog
)

class FirstRunDialog(QDialog):
    """Initial setup dialog to choose between Standard and Portable modes."""
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
    """Visual representation of a monitor (Live or Ghost)."""

    def __init__(self, x, y, w, h, monitor_data, image_path=None, is_staged=False, is_ghost=False):
        super().__init__(x, y, w, h)
        self.monitor_data = monitor_data
        self.is_ghost = is_ghost

        # 1. Determine Styling based on state
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

        # 2. Handle Background Image
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            scaled_pixmap = pixmap.scaled(
                int(w), int(h),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setBrush(QBrush(scaled_pixmap))

            if is_ghost:
                self.setOpacity(0.4)
        else:
            self.setBrush(QBrush(QColor("#1a1a1a")))

    def mousePressEvent(self, event):
        if not self.is_ghost:
            self.scene().views()[0].monitor_clicked(self.monitor_data)
        event.accept()

class MonitorCanvas(QGraphicsView):
    """The interactive topology map containing live and ghost monitors."""

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

    def monitor_clicked(self, data):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Wallpaper", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            self.pending_clips[data['id']] = file_path
            QTimer.singleShot(1, lambda: self.display_monitors(self.window().monitors))

    def display_monitors(self, monitors):
        self.current_monitors = monitors
        self._perform_render()

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
            # Look for a saved image in the profile for this specific hardware ID
            saved_image = None
            for _, entry in profile_data.items():
                if entry.get('device_id') == m['id']:
                    saved_image = entry.get('image')
                    break

            # Create a copy with the saved image attached for rendering
            render_list.append({
                **m,
                "is_ghost": False,
                "image": saved_image
            })

        # --- Build Render List: Ghost Monitors ---
        # Calculate the max-y of live monitors to place the shelf below them
        max_live_y = max((m['y'] + m['h']) for m in active_hw) if active_hw else 0
        shelf_y = max_live_y + 500

        # Start the ghost shelf aligned with the leftmost active monitor
        ghost_offset_x = min((m['x']) for m in active_hw) if active_hw else 0

        for idx, m_meta in profile_data.items():
            if m_meta.get('device_id') not in live_ids:
                render_list.append({
                    "id": m_meta.get('device_id'),
                    "port": m_meta.get('port', '???'),
                    "name": m_meta.get('device_name', 'Unknown Ghost'),
                    "w": 1280, "h": 720,
                    "x": ghost_offset_x, "y": shelf_y,
                    "is_ghost": True,
                    "image": m_meta.get('image')
                })
                ghost_offset_x += 1400

        if not render_list:
            return

        # 2. Calculate Bounding Box and Scaling
        min_x = min(m['x'] for m in render_list)
        min_y = min(m['y'] for m in render_list)
        max_x = max(m['x'] + m['w'] for m in render_list)
        max_y = max(m['y'] + m['h'] for m in render_list)

        total_w = max_x - min_x
        total_h = max_y - min_y

        view_w, view_h = self.width() * 0.9, self.height() * 0.9
        fit_scale = min(view_w / total_w, view_h / total_h) if total_w > 0 else 0.1

        # 3. Draw Items to Scene
        for m in render_list:
            sx, sy = (m['x'] - min_x) * fit_scale, (m['y'] - min_y) * fit_scale
            sw, sh = m['w'] * fit_scale, m['h'] * fit_scale

            is_staged = m['id'] in self.pending_clips
            is_ghost = m.get('is_ghost', False)

            # PRIORITY: Staged UI selection > Saved Profile Image > None
            staged_path = self.pending_clips.get(m['id'])
            final_path = staged_path if staged_path else m.get('image')

            rect = MonitorItem(sx, sy, sw, sh, m,
                               image_path=final_path,
                               is_staged=is_staged,
                               is_ghost=is_ghost)
            self.scene.addItem(rect)

            # --- Rich Panel Text Logic ---
            status_label = "GHOST" if is_ghost else ("STAGED" if is_staged else "ACTIVE")
            display_name = m.get('name', m['port'])
            filename = os.path.basename(final_path) if final_path else "No Wallpaper"

            panel_info = f"<b>{display_name}</b> <small>[{m['port']}]</small> | {status_label}"
            if final_path:
                panel_info += f"<br/>{filename[:25]}..."

            txt = self.scene.addText("")
            txt.document().setDocumentMargin(0)
            txt.setTextWidth(sw)
            txt.setHtml(f"""
                <div style='background-color: rgba(0, 0, 0, 220); 
                            color: white; 
                            width: 100%; 
                            padding: 4px; 
                            font-family: monospace; 
                            font-size: 9px;
                            border-top: 1px solid #333;'>
                    {panel_info}
                </div>
            """)

            txt_height = txt.boundingRect().height()
            txt.setPos(sx, (sy + sh) - txt_height)

        # 4. Final Scene Formatting
        self.setSceneRect(self.scene.itemsBoundingRect().adjusted(-50, -50, 50, 50))
        self.centerOn(self.scene.itemsBoundingRect().center())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_timer.start(50)