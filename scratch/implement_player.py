import re
import sys

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add PyQt6.QtMultimedia imports
if 'from PyQt6.QtMultimedia import' not in content:
    content = content.replace('from PyQt6.QtCore import pyqtSignal, QObject, QPoint, QRect',
                              'from PyQt6.QtCore import pyqtSignal, QObject, QPoint, QRect, QUrl\nfrom PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink')

# 2. Modify ImageLabel to have app_ref and custom paintEvent
image_label_old = """class ImageLabel(QLabel):
    box_updated = pyqtSignal(int, int, int, int) # x, y, w, h theo %

    def __init__(self, parent=None):
        super().__init__(parent)
        self.origin = QPoint()
        self.end = QPoint()
        self.is_drawing = False
        self.rect = QRect()
        self.setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event):"""

image_label_new = """class ImageLabel(QLabel):
    box_updated = pyqtSignal(int, int, int, int) # x, y, w, h theo %

    def __init__(self, parent=None):
        super().__init__(parent)
        self.origin = QPoint()
        self.end = QPoint()
        self.is_drawing = False
        self.rect = QRect()
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.app_ref = None

    def set_app(self, app):
        self.app_ref = app

    def mousePressEvent(self, event):"""
content = content.replace(image_label_old, image_label_new)

# Modify ImageLabel.paintEvent
paint_event_old = """    def paintEvent(self, event):
        super().paintEvent(event)
        if self.is_drawing:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(255, 0, 0), 2, Qt.PenStyle.SolidLine))
            painter.setBrush(QBrush(QColor(255, 0, 0, 80)))
            painter.drawRect(QRect(self.origin, self.end).normalized())"""

paint_event_new = """    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        if self.is_drawing:
            painter.setPen(QPen(QColor(255, 0, 0), 2, Qt.PenStyle.SolidLine))
            painter.setBrush(QBrush(QColor(255, 0, 0, 80)))
            painter.drawRect(QRect(self.origin, self.end).normalized())
        elif self.app_ref and self.pixmap():
            # Tự động tính toán toạ độ từ slider và vẽ lại Box màu đỏ
            lbl_w = self.width()
            lbl_h = self.height()
            pix_w = self.pixmap().width()
            pix_h = self.pixmap().height()
            
            offset_x = (lbl_w - pix_w) / 2
            offset_y = (lbl_h - pix_h) / 2
            
            # Vẽ hộp blur
            if self.app_ref.chk_blur.isChecked() and hasattr(self.app_ref, 'slider_x'):
                x = (self.app_ref.slider_x.value() / 100.0) * pix_w + offset_x
                y = (self.app_ref.slider_y.value() / 100.0) * pix_h + offset_y
                w = (self.app_ref.slider_w.value() / 100.0) * pix_w
                h = (self.app_ref.slider_h.value() / 100.0) * pix_h
                
                painter.setPen(QPen(QColor(255, 0, 0), 3, Qt.PenStyle.SolidLine))
                painter.setBrush(QBrush(QColor(255, 0, 0, 50)))
                painter.drawRect(int(x), int(y), int(w), int(h))
                
            # Vẽ Text Subtitle Mô phỏng
            if hasattr(self.app_ref, 'spin_font_size'):
                from PyQt6.QtGui import QPainterPath, QFontMetrics
                
                color_map = {
                    "Trắng": "#FFFFFF", "Vàng": "#FFFF00", "Xanh Lơ": "#00FFFF", 
                    "Xanh Lá": "#00FF00", "Đỏ": "#FF0000", "Hồng": "#FF00FF", "Đen": "#000000"
                }
                font_color = color_map.get(self.app_ref.combo_font_color.currentText(), "#FFFF00")
                outline_color = color_map.get(self.app_ref.combo_outline_color.currentText(), "#000000")
                
                # Chuyển đổi font_size tương đối với frame thật sang tỷ lệ preview
                original_w = getattr(self.app_ref, 'current_video_width', 1920)
                original_h = getattr(self.app_ref, 'current_video_height', 1080)
                if original_w == 0 or original_h == 0:
                    original_w, original_h = 1920, 1080
                    
                scale_ratio = pix_h / original_h
                
                scaled_font_size = max(8, int(self.app_ref.spin_font_size.value() * scale_ratio))
                scaled_outline_width = max(1, int(self.app_ref.spin_outline.value() * scale_ratio))
                
                font = QFont("Arial", scaled_font_size)
                font.setBold(True)
                
                if hasattr(self.app_ref, 'subs_data') and self.app_ref.subs_data:
                    sample_text = self.app_ref.subs_data[0]['text']
                else:
                    sample_text = "Ví dụ Text Phụ đề"
                    
                fm = QPainterPath()
                
                # Tính toạ độ
                margin_px = int((self.app_ref.margin_slider.value() / 100.0) * pix_h)
                sub_y = pix_h - margin_px + offset_y
                
                metrics = QFontMetrics(font)
                text_width = metrics.horizontalAdvance(sample_text)
                text_x = (pix_w - text_width) / 2 + offset_x
                
                path = QPainterPath()
                # Qt drawText y is baseline, so we need to adjust
                path.addText(text_x, sub_y, font, sample_text)
                
                # Vẽ hộp nền mờ nếu có
                if self.app_ref.combo_border_style.currentText() == "Khung nền mờ (Opaque Box)":
                    box_padding = max(2, scaled_outline_width * 3)
                    bg_rect = path.boundingRect().adjusted(-box_padding, -box_padding, box_padding, box_padding)
                    
                    # Convert hex to RGBA
                    h_c = outline_color.lstrip('#')
                    r, g, b = tuple(int(h_c[i:i+2], 16) for i in (0, 2, 4))
                    painter.fillRect(bg_rect, QColor(r, g, b, 255))
                    
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(font_color))
                    painter.drawPath(path)
                else:
                    painter.setPen(QPen(QColor(outline_color), scaled_outline_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                    painter.setBrush(QColor(font_color))
                    painter.drawPath(path)
"""
content = content.replace(paint_event_old, paint_event_new)

# 3. Setup QMediaPlayer in AutoVietsubApp.__init__
init_old = """        self.worker3 = None
        
        self.init_ui()
        self.setStyleSheet(MODERN_QSS)"""

init_new = """        self.worker3 = None
        
        self.init_ui()
        self.setStyleSheet(MODERN_QSS)
        
        # Setup Video Player
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.video_sink = QVideoSink()
        self.media_player.setVideoOutput(self.video_sink)
        
        self.video_sink.videoFrameChanged.connect(self.on_video_frame_changed)
        self.media_player.positionChanged.connect(self.on_video_position_changed)
        self.media_player.durationChanged.connect(self.on_video_duration_changed)
        
        self.preview_lbl.set_app(self)
        self.current_video_width = 1920
        self.current_video_height = 1080"""
content = content.replace(init_old, init_new)

# 4. Modify Preview Area UI
ui_old = """        # Thêm khu vực Preview Blur
        h2_preview = QVBoxLayout()
        self.btn_preview = QPushButton("🖼️ Nạp ảnh xem trước (Sau đó hãy kéo chuột trên ảnh để vẽ)")
        self.btn_preview.clicked.connect(self.update_preview)
        self.preview_lbl = ImageLabel()
        self.preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_lbl.setStyleSheet("border: 1px dashed #45475A;")
        self.preview_lbl.setMinimumHeight(200)
        self.preview_lbl.box_updated.connect(self.on_box_drawn)
        h2_preview.addWidget(self.btn_preview)
        h2_preview.addWidget(self.preview_lbl)
        v_blur.addLayout(h2_preview)"""

ui_new = """        # Thêm khu vực Preview Blur
        h2_preview = QVBoxLayout()
        self.btn_preview = QPushButton("▶️ Nạp Video Xem Trước (Sau đó kéo chuột trên hình để vẽ)")
        self.btn_preview.clicked.connect(self.update_preview)
        self.preview_lbl = ImageLabel()
        self.preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_lbl.setStyleSheet("border: 1px dashed #45475A; background-color: #1e1e2e;")
        self.preview_lbl.setMinimumHeight(250)
        self.preview_lbl.box_updated.connect(self.on_box_drawn)
        
        h_video_controls = QHBoxLayout()
        self.btn_play_pause = QPushButton("⏸️")
        self.btn_play_pause.setFixedWidth(50)
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        
        self.video_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_slider.setRange(0, 0)
        self.video_slider.sliderMoved.connect(self.set_video_position)
        
        self.lbl_video_time = QLabel("00:00 / 00:00")
        
        h_video_controls.addWidget(self.btn_play_pause)
        h_video_controls.addWidget(self.video_slider)
        h_video_controls.addWidget(self.lbl_video_time)
        
        h2_preview.addWidget(self.btn_preview)
        h2_preview.addWidget(self.preview_lbl)
        h2_preview.addLayout(h_video_controls)
        v_blur.addLayout(h2_preview)"""
content = content.replace(ui_old, ui_new)

# 5. Add Player methods and rewrite update_preview
update_preview_regex = re.compile(r'    def update_preview\(self\):.*?    def on_box_drawn\(self, x, y, w, h\):', re.DOTALL)

methods_new = """    def on_video_frame_changed(self, frame):
        image = frame.toImage()
        if not image.isNull():
            pixmap = QPixmap.fromImage(image)
            scaled = pixmap.scaled(self.preview_lbl.width(), self.preview_lbl.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.preview_lbl.setPixmap(scaled)
            
            self.current_video_width = image.width()
            self.current_video_height = image.height()

    def toggle_play_pause(self):
        from PyQt6.QtMultimedia import QMediaPlayer
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.btn_play_pause.setText("▶️")
        else:
            self.media_player.play()
            self.btn_play_pause.setText("⏸️")

    def set_video_position(self, position):
        self.media_player.setPosition(position)

    def on_video_position_changed(self, position):
        if not self.video_slider.isSliderDown():
            self.video_slider.setValue(position)
        self.update_video_time_label()

    def on_video_duration_changed(self, duration):
        self.video_slider.setRange(0, duration)
        self.update_video_time_label()
        
    def update_video_time_label(self):
        pos = self.media_player.position() // 1000
        dur = self.media_player.duration() // 1000
        self.lbl_video_time.setText(f"{pos//60:02d}:{pos%60:02d} / {dur//60:02d}:{dur%60:02d}")

    def update_preview(self):
        if not hasattr(self, 'current_video') or not self.current_video or not os.path.exists(self.current_video):
            if self.sender() == getattr(self, 'btn_preview', None):
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn Video ở Bước 1 trước khi tải ảnh xem trước!")
            return
            
        if self.sender() == getattr(self, 'btn_preview', None):
            self.media_player.setSource(QUrl.fromLocalFile(self.current_video))
            self.media_player.play()
            self.btn_play_pause.setText("⏸️")
            self.preview_lbl.setText("Đang nạp video...")
        else:
            self.preview_lbl.update()

    def on_box_drawn(self, x, y, w, h):"""

content = update_preview_regex.sub(methods_new, content)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done writing modifications!")
