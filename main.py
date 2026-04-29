import sys
import os
import subprocess

# Bỏ qua lỗi xung đột thư viện OpenMP (Hay gặp khi chạy AI trên Windows)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# --- BẢN VÁ LỖI NHÁY MÀN HÌNH CMD TRÊN WINDOWS ---
if sys.platform == "win32" and hasattr(sys, "frozen"):
    _original_init = subprocess.Popen.__init__
    def _patched_init(self, *args, **kwargs):
        if "creationflags" not in kwargs:
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        _original_init(self, *args, **kwargs)
    subprocess.Popen.__init__ = _patched_init
# --------------------------------------------------

import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QComboBox, QStackedWidget, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QProgressBar, 
                             QTextEdit, QSlider, QCheckBox, QFileDialog, QMessageBox, QGroupBox, QFormLayout, QSpinBox, QTabWidget, QDoubleSpinBox, QScrollArea, QMenu, QTextBrowser)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor
from PIL import Image, ImageDraw

from style import MODERN_QSS
from ui_workers import WorkerStep1, WorkerStep3
from core.video_processor import extract_preview_frame
import sys
from PyQt6.QtCore import pyqtSignal, QObject, QPoint, QRect, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor, QPainter, QPen, QBrush

class ImageLabel(QLabel):
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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.pos()
            self.end = self.origin
            self.is_drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            self.end = event.pos()
            self.is_drawing = False
            self.rect = QRect(self.origin, self.end).normalized()
            self.update()
            self.calculate_percentages()

    def calculate_percentages(self):
        if not self.pixmap() or self.rect.isNull(): return
        
        lbl_w = self.width()
        lbl_h = self.height()
        pix_w = self.pixmap().width()
        pix_h = self.pixmap().height()
        
        offset_x = (lbl_w - pix_w) / 2
        offset_y = (lbl_h - pix_h) / 2
        
        px = self.rect.x() - offset_x
        py = self.rect.y() - offset_y
        pw = self.rect.width()
        ph = self.rect.height()
        
        px = max(0, min(px, pix_w))
        py = max(0, min(py, pix_h))
        if px + pw > pix_w: pw = pix_w - px
        if py + ph > pix_h: ph = pix_h - py
        
        if pw <= 0 or ph <= 0: return

        x_pct = (px / pix_w) * 100
        y_pct = (py / pix_h) * 100
        w_pct = (pw / pix_w) * 100
        h_pct = (ph / pix_h) * 100
        
        self.box_updated.emit(int(x_pct), int(y_pct), int(w_pct), int(h_pct))

    def paintEvent(self, event):
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


class EmittingStream(QObject):
    textWritten = pyqtSignal(str)
    
    def write(self, text):
        if text.strip() or text.startswith('\r'):
            self.textWritten.emit(text)
            
    def flush(self):
        pass

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

CONFIG_FILE = "config.json"

class AutoVietsubApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Vietsub Pro - Desktop Edition 🎬")
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1100, 750)
        
        # Load Config
        self.config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except: pass
            
        # Data
        self.current_video = ""
        self.subs_data = []
        self.worker1 = None
        self.worker3 = None
        
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
        self.current_video_height = 1080
        
        # Redirect stdout an toàn qua QObject Signal
        self.stream = EmittingStream()
        self.stream.textWritten.connect(self.append_log)
        sys.stdout = self.stream
        
    def init_ui(self):
        # Central Widget
        central_widget = QWidget()
        central_widget.setObjectName("central")
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- SIDEBAR (Trái) ---
        sidebar_container = QWidget()
        sidebar_container.setObjectName("sidebar")
        sidebar_container.setFixedWidth(460)
        sidebar_main_layout = QVBoxLayout(sidebar_container)
        sidebar_main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 20, 20, 20)
        sidebar_layout.setSpacing(15)
        
        scroll.setWidget(sidebar)
        sidebar_main_layout.addWidget(scroll)
        
        title_lbl = QLabel("CÀI ĐẶT HỆ THỐNG")
        title_lbl.setObjectName("header")
        sidebar_layout.addWidget(title_lbl)
        
        # Group STT
        group_stt = QGroupBox("Nhận diện (STT)")
        stt_layout = QFormLayout(group_stt)
        
        self.device_cb = QComboBox()
        self.device_cb.addItems(["CPU", "GPU (Nvidia)"])
        self.device_cb.setCurrentText(self.config.get("device_type", "CPU"))
        
        stt_layout.addRow("Phần cứng:", self.device_cb)
        sidebar_layout.addWidget(group_stt)
        
        # Group Dịch
        group_trans = QGroupBox("Dịch thuật (AI)")
        trans_layout = QFormLayout(group_trans)
        
        self.model_cb = QComboBox()
        self.model_cb.addItems(["Gemini 2.0 Flash (Khuyên dùng)", "Gemini 2.5 Flash-Lite (Siêu nhanh)", "Groq (Llama 3.3 - Nhanh)", "Groq (Qwen 3 32B - Dịch Tiếng Trung Tốt)", "Google Translate (Miễn phí 100%)"])
        self.model_cb.setCurrentText(self.config.get("translation_model", "Gemini 2.0 Flash (Khuyên dùng)"))
        
        self.target_lang_cb = QComboBox()
        self.target_lang_cb.addItems(["Tiếng Việt", "Tiếng Anh", "Tiếng Trung", "Tiếng Hàn", "Tiếng Nhật", "Tiếng Thái"])
        self.target_lang_cb.setCurrentText(self.config.get("target_lang", "Tiếng Việt"))
        
        self.gemini_key = QLineEdit(self.config.get("gemini_api_key", ""))
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_backup = QLineEdit(self.config.get("gemini_api_key_backup", ""))
        self.gemini_key_backup.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key_backup.setPlaceholderText("API Key dự phòng (Nếu bị lỗi quota)")
        self.groq_key = QLineEdit(self.config.get("groq_api_key", ""))
        self.groq_key.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.prompt_input = QTextEdit(self.config.get("gemini_prompt", "Giọng điệu review phim, kịch tính, hấp dẫn"))
        self.prompt_input.setPlaceholderText("VD: Dịch nhí nhảnh, GenZ...")
        self.prompt_input.setMaximumHeight(60)
        
        trans_layout.addRow("Model:", self.model_cb)
        trans_layout.addRow("Ngôn ngữ đích:", self.target_lang_cb)
        trans_layout.addRow("Phong cách:", self.prompt_input)
        trans_layout.addRow("Gemini Key:", self.gemini_key)
        trans_layout.addRow("Gemini Key 2:", self.gemini_key_backup)
        trans_layout.addRow("Groq Key:", self.groq_key)
        sidebar_layout.addWidget(group_trans)
        
        # Group TTS
        group_tts = QGroupBox("Giọng đọc (TTS)")
        tts_layout = QFormLayout(group_tts)
        
        self.voice_cb = QComboBox()
        from core.tts_engine import VOICE_MAP
        self.voice_cb.addItems(list(VOICE_MAP.keys()))
        self.voice_cb.setCurrentText(self.config.get("voice", "Nữ CapCut (VN)"))
        
        self.tiktok_id = QLineEdit(self.config.get("tiktok_session_id", ""))
        self.tiktok_id.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.bg_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.bg_vol_slider.setRange(0, 100)
        self.bg_vol_slider.setValue(int(self.config.get("bg_volume", 0.1) * 100))
        
        self.spin_tts_threads = QSpinBox()
        self.spin_tts_threads.setRange(1, 20)
        self.spin_tts_threads.setValue(int(self.config.get("tts_threads", 10)))
        self.spin_tts_threads.setToolTip("Tăng số luồng để tải TTS nhanh hơn (Tối đa 20)")
        
        self.spin_tts_speed = QDoubleSpinBox()
        self.spin_tts_speed.setRange(0.5, 2.5)
        self.spin_tts_speed.setSingleStep(0.1)
        self.spin_tts_speed.setValue(float(self.config.get("tts_speed", 1.2)))
        self.spin_tts_speed.setToolTip("Yêu cầu AI dịch văn bản dài ra/ngắn đi tương ứng và làm tốc độ đọc cơ sở (VD: 1.2 = Dịch dài 120%, tốc độ nền 1.2x)")
        
        self.spin_max_tts_speed = QDoubleSpinBox()
        self.spin_max_tts_speed.setRange(1.0, 5.0)
        self.spin_max_tts_speed.setSingleStep(0.1)
        self.spin_max_tts_speed.setValue(float(self.config.get("max_tts_speed", 1.35)))
        self.spin_max_tts_speed.setToolTip("Giới hạn tua nhanh tối đa để khớp thời gian phụ đề (Khuyên dùng: 1.35 - 1.5)")
        
        h_voice = QHBoxLayout()
        h_voice.addWidget(self.voice_cb)
        self.btn_test_voice = QPushButton("▶️ Test")
        self.btn_test_voice.clicked.connect(self.play_demo_voice)
        h_voice.addWidget(self.btn_test_voice)
        tts_layout.addRow("Voice:", h_voice)
        tts_layout.addRow("TikTok ID:", self.tiktok_id)
        tts_layout.addRow("Âm lượng gốc:", self.bg_vol_slider)
        tts_layout.addRow("Số luồng (Speed):", self.spin_tts_threads)
        tts_layout.addRow("Tỉ lệ Dịch/Đọc gốc (x):", self.spin_tts_speed)
        tts_layout.addRow("Giới hạn tua ép (x):", self.spin_max_tts_speed)
        
        # Thêm lựa chọn tắt/bật Sub/Dub
        self.chk_enable_tts = QCheckBox("Bật Lồng tiếng (Đọc TTS)")
        self.chk_enable_tts.setChecked(self.config.get("enable_tts", True))
        self.chk_enable_sub = QCheckBox("Bật Phụ đề (Hiện chữ Hardsub)")
        self.chk_enable_sub.setChecked(self.config.get("enable_sub", True))
        tts_layout.addRow(self.chk_enable_tts)
        tts_layout.addRow(self.chk_enable_sub)
        
        sidebar_layout.addWidget(group_tts)
        
        sidebar_layout.addStretch()
        
        # Save btn
        btn_save = QPushButton("💾 Lưu Cài Đặt")
        btn_save.clicked.connect(self.save_config)
        sidebar_main_layout.addWidget(btn_save)
        
        main_layout.addWidget(sidebar_container)
        
        # --- NỘI DUNG CHÍNH (Phải) ---
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(20)
        
        # Header
        app_title = QLabel("🎬 AUTO VIETSUB PRO")
        app_title.setObjectName("title")
        content_layout.addWidget(app_title)
        
        # Tabs Chính của ứng dụng
        self.main_tabs = QTabWidget()
        self.main_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #45475A; border-radius: 8px; }
            QTabBar::tab { background: #313244; color: #CDD6F4; padding: 12px 24px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; font-weight: bold; font-size: 14px;}
            QTabBar::tab:selected { background: #89B4FA; color: #11111B; font-weight: bold; }
        """)
        content_layout.addWidget(self.main_tabs)

        # --- TAB TẢI VIDEO ---
        self.tab_download = QWidget()
        v_dl = QVBoxLayout(self.tab_download)
        v_dl.setContentsMargins(30, 30, 30, 30)
        v_dl.setSpacing(15)
        
        lbl_dl_title = QLabel("📥 TẢI VIDEO TỪ TIKTOK / DOUYIN / YOUTUBE")
        lbl_dl_title.setObjectName("header")
        v_dl.addWidget(lbl_dl_title)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Dán link video TikTok, Douyin, Youtube vào đây...")
        self.url_input.setStyleSheet("padding: 10px; font-size: 14px;")
        v_dl.addWidget(self.url_input)
        
        self.cookie_input = QLineEdit()
        self.cookie_input.setPlaceholderText("Tuỳ chọn: Dán Cookie (Dạng Text Netscape hoặc Raw) vào đây nếu tool không tự tải được...")
        self.cookie_input.setStyleSheet("padding: 10px; font-size: 14px; background-color: #1e1e2e; color: #A6E3A1;")
        v_dl.addWidget(self.cookie_input)
        
        h_dl_btn = QHBoxLayout()
        self.btn_download = QPushButton("⬇️ BẮT ĐẦU TẢI VIDEO")
        self.btn_download.setObjectName("btn_primary")
        self.btn_download.clicked.connect(self.start_download)
        
        self.btn_open_dl_folder = QPushButton("📂 Mở Thư Mục Tải Về")
        self.btn_open_dl_folder.setStyleSheet("background-color: #313244; color: #CDD6F4; font-weight: bold; padding: 12px; border-radius: 6px;")
        self.btn_open_dl_folder.clicked.connect(self.open_dl_folder)
        
        h_dl_btn.addWidget(self.btn_download)
        h_dl_btn.addWidget(self.btn_open_dl_folder)
        v_dl.addLayout(h_dl_btn)
        
        self.dl_progress = QProgressBar()
        self.dl_progress.setValue(0)
        v_dl.addWidget(self.dl_progress)
        
        self.dl_status = QLabel("Trạng thái: Đang chờ...")
        v_dl.addWidget(self.dl_status)
        
        self.dl_terminal = QTextEdit()
        self.dl_terminal.setReadOnly(True)
        self.dl_terminal.setStyleSheet("background-color: #11111B; color: #89B4FA; font-family: Consolas;")
        v_dl.addWidget(self.dl_terminal)
        
        self.main_tabs.addTab(self.tab_download, "📥 Tải Video Mạng")
        
        # --- TAB XỬ LÝ VIDEO (Chứa code cũ) ---
        self.tab_process = QWidget()
        v_process = QVBoxLayout(self.tab_process)
        v_process.setContentsMargins(0, 0, 0, 0)
        
        # Stacked Widget cho các bước
        self.stack = QStackedWidget()
        v_process.addWidget(self.stack)
        
        self.main_tabs.addTab(self.tab_process, "🎬 Xử lý Video (Sub/Dub)")
        
        # --- TAB XƯỞNG VIDEO AI ---
        self.tab_factory = QWidget()
        v_fac = QVBoxLayout(self.tab_factory)
        v_fac.setContentsMargins(30, 30, 30, 30)
        v_fac.setSpacing(15)
        
        lbl_fac_title = QLabel("🏭 XƯỞNG SẢN XUẤT VIDEO AI (MASHUP & SPIN)")
        lbl_fac_title.setObjectName("header")
        v_fac.addWidget(lbl_fac_title)
        
        fac_tabs = QTabWidget()
        v_fac.addWidget(fac_tabs)
        
        # Module 1: Mashup
        tab_mashup = QWidget()
        v_mashup = QVBoxLayout(tab_mashup)
        v_mashup.setSpacing(15)
        
        h_mashup_in = QHBoxLayout()
        self.fac_input_dir = QLineEdit()
        self.fac_input_dir.setPlaceholderText("Chọn thư mục chứa nhiều video mẫu để mix...")
        self.fac_input_dir.setReadOnly(True)
        btn_fac_browse = QPushButton("📁 Chọn Thư mục Raw")
        btn_fac_browse.clicked.connect(self.browse_fac_input)
        h_mashup_in.addWidget(self.fac_input_dir)
        h_mashup_in.addWidget(btn_fac_browse)
        v_mashup.addLayout(h_mashup_in)
        
        h_mashup_out = QHBoxLayout()
        self.fac_output_dir = QLineEdit()
        self.fac_output_dir.setPlaceholderText("Chọn thư mục lưu các video mới xuất ra...")
        self.fac_output_dir.setReadOnly(True)
        btn_fac_out = QPushButton("📁 Chọn Nơi Lưu")
        btn_fac_out.clicked.connect(self.browse_fac_output)
        btn_fac_open = QPushButton("📂 Mở Thư Mục")
        btn_fac_open.clicked.connect(self.open_fac_output)
        h_mashup_out.addWidget(self.fac_output_dir)
        h_mashup_out.addWidget(btn_fac_out)
        h_mashup_out.addWidget(btn_fac_open)
        v_mashup.addLayout(h_mashup_out)
        
        g_mashup_cfg = QGroupBox("Cấu hình Mix")
        f_mashup = QFormLayout(g_mashup_cfg)
        self.spin_num_videos = QSpinBox()
        self.spin_num_videos.setRange(1, 1000)
        self.spin_num_videos.setValue(10)
        f_mashup.addRow("Số lượng video muốn tạo:", self.spin_num_videos)
        
        self.spin_clip_dur = QSpinBox()
        self.spin_clip_dur.setRange(1, 10)
        self.spin_clip_dur.setValue(3)
        self.spin_clip_dur.setToolTip("Cắt video raw thành các đoạn ngắn mấy giây?")
        f_mashup.addRow("Độ dài mỗi nhát cắt (s):", self.spin_clip_dur)
        v_mashup.addWidget(g_mashup_cfg)
        
        self.btn_run_mashup = QPushButton("🔄 BẮT ĐẦU MIX VIDEO HÀNG LOẠT")
        self.btn_run_mashup.setObjectName("btn_primary")
        self.btn_run_mashup.clicked.connect(self.start_fac_mashup)
        v_mashup.addWidget(self.btn_run_mashup)
        v_mashup.addStretch()
        fac_tabs.addTab(tab_mashup, "🔀 Máy Trộn Video (Mashup)")
        
        # Module 2: Spin Script
        tab_spin = QWidget()
        v_spin = QVBoxLayout(tab_spin)
        
        h_spin_prod = QHBoxLayout()
        h_spin_prod.addWidget(QLabel("Tên sản phẩm (Tuỳ chọn):"))
        self.spin_product_name = QLineEdit()
        self.spin_product_name.setPlaceholderText("Nhập tên SP (VD: Loa Bluetooth) để AI xào kịch bản bám sát vào sản phẩm này...")
        h_spin_prod.addWidget(self.spin_product_name)
        v_spin.addLayout(h_spin_prod)
        
        self.spin_original_txt = QTextEdit()
        self.spin_original_txt.setPlaceholderText("Dán kịch bản mẫu/Sub gốc vào đây...")
        
        h_spin_lbl = QHBoxLayout()
        h_spin_lbl.addWidget(QLabel("Kịch bản gốc:"))
        
        btn_extract_vid = QPushButton("🎵 Trích Xuất Từ Video")
        btn_extract_vid.setStyleSheet("background-color: #89B4FA; color: #11111B; font-weight: bold; padding: 5px 15px; border-radius: 4px;")
        btn_extract_vid.clicked.connect(self.extract_script_from_video)
        
        btn_spin_example = QPushButton("💡 Nạp Kịch Bản Mẫu ▾")
        btn_spin_example.setStyleSheet("background-color: #313244; color: #A6E3A1; font-weight: bold; padding: 5px 15px; border-radius: 4px;")
        
        example_menu = QMenu(btn_spin_example)
        example_menu.setStyleSheet("QMenu { background-color: #1E1E2E; color: #CDD6F4; border: 1px solid #45475A; font-size: 14px; } QMenu::item:selected { background-color: #89B4FA; color: #11111B; }")
        
        script1 = "Trời ơi tin được không! Đang lướt top top thấy món này đang được sale sốc quá nên mình phải hốt ngay về cho mọi người xem đây. Phải công nhận là hàng cầm trên tay cực kỳ xịn xò, chất lượng vượt xa số tiền bỏ ra luôn ấy. Bác nào mà đang tìm một món đồ vừa ngon bổ rẻ thì chốt ngay em này không phải nghĩ. Đang có mã freeship với giảm giá sâu lắm, mọi người nhanh tay bấm vào giỏ hàng màu vàng góc trái màn hình nhé, kẻo hết hàng lại tiếc hùi hụi!"
        script2 = "Đây chắc chắn là món đồ mà ai cũng nên có ít nhất một cái trong nhà! Lúc mới đặt mua mình cũng bán tín bán nghi lắm, không ngờ lúc bóc ra dùng thử thì ta nói nó u mê thực sự. Hàng siêu chất lượng, giải quyết được bao nhiêu rắc rối trước giờ của mình. Dùng xong chỉ tiếc là không biết tới món này sớm hơn. Link mua hàng chuẩn mình để dưới góc trái video nha, anh em nhấp vào tham khảo nhé, đang được shop trợ giá hời lắm đó!"
        script3 = "Thấy dạo này trên mạng ai cũng rần rần săn lùng cái món này, nên mình cũng đu trend đặt về xem có thực sự thần thánh như lời đồn không. Và kết quả là... nó đỉnh thật sự các bác ạ! Đáng đồng tiền bát gạo luôn. Bác nào dạo trước muốn mua mà lỡ dịp thì tranh thủ đợt này shop vừa về lại hàng, rải cả voucher giảm giá nữa. Bấm ngay vào giỏ hàng góc trái để chốt đơn nha, muộn là hết đó!"
        
        action1 = example_menu.addAction("🔥 Mẫu Khan Hiếm (FOMO)")
        action1.triggered.connect(lambda _, text=script1: self.spin_original_txt.setText(text))
        
        action2 = example_menu.addAction("🔍 Mẫu Review Tò Mò")
        action2.triggered.connect(lambda _, text=script2: self.spin_original_txt.setText(text))
        
        action3 = example_menu.addAction("🌟 Mẫu Đu Trend")
        action3.triggered.connect(lambda _, text=script3: self.spin_original_txt.setText(text))
        
        btn_spin_example.setMenu(example_menu)        
        h_spin_lbl.addStretch()
        h_spin_lbl.addWidget(btn_extract_vid)
        h_spin_lbl.addWidget(btn_spin_example)
        
        v_spin.addLayout(h_spin_lbl)
        v_spin.addWidget(self.spin_original_txt)
        
        self.btn_run_spin = QPushButton("✍️ AI XÀO LẠI KỊCH BẢN NÀY")
        self.btn_run_spin.setStyleSheet("background-color: #F9E2AF; color: #11111B; font-weight: bold; padding: 10px; border-radius: 6px;")
        self.btn_run_spin.clicked.connect(self.start_fac_spin)
        v_spin.addWidget(self.btn_run_spin)
        
        self.spin_new_txt = QTextEdit()
        self.spin_new_txt.setReadOnly(True)
        self.spin_new_txt.setPlaceholderText("Kịch bản mới sẽ hiện ở đây...")
        v_spin.addWidget(QLabel("Kịch bản mới (Đã Spin):"))
        v_spin.addWidget(self.spin_new_txt)
        
        fac_tabs.addTab(tab_spin, "✍️ Máy Xào Kịch Bản (Auto-Spin)")
        
        # Module 3: Image to Video
        tab_img2vid = QWidget()
        v_img2vid = QVBoxLayout(tab_img2vid)
        v_img2vid.setSpacing(15)
        
        h_img_in = QHBoxLayout()
        self.fac_img_path = QLineEdit()
        self.fac_img_path.setPlaceholderText("Cách 1: Chọn 1 hình ảnh sản phẩm (.jpg, .png)...")
        self.fac_img_path.setReadOnly(True)
        btn_fac_img = QPushButton("🖼️ Chọn Hình Ảnh")
        btn_fac_img.clicked.connect(self.browse_fac_image)
        h_img_in.addWidget(self.fac_img_path)
        h_img_in.addWidget(btn_fac_img)
        v_img2vid.addLayout(h_img_in)
        
        h_img_kw = QHBoxLayout()
        self.fac_img_keyword = QLineEdit()
        self.fac_img_keyword.setPlaceholderText("Cách 2: Hoặc nhập tên sản phẩm (đỡ tốn Token AI phân tích ảnh)...")
        h_img_kw.addWidget(QLabel("Tên Sản Phẩm:"))
        h_img_kw.addWidget(self.fac_img_keyword)
        v_img2vid.addLayout(h_img_kw)
        
        self.chk_use_ai_spin = QCheckBox("Băm nhỏ & Trộn khung hình (Nên bật để Bán Hàng/Affiliate)")
        self.chk_use_ai_spin.setChecked(True)
        self.chk_use_ai_spin.setToolTip("Nếu TẮT: Video sẽ giữ nguyên âm thanh và độ dài gốc, chỉ tự động chạy bộ lọc chống Reup siêu ẩn (Dành cho Reup thuần túy).")
        v_img2vid.addWidget(self.chk_use_ai_spin)
        
        h_img_src = QHBoxLayout()
        h_img_src.addWidget(QLabel("Nguồn Video:"))
        self.fac_img_source = QComboBox()
        self.fac_img_source.addItems(["Nguồn Tổng Hợp (Tự động tải từ Youtube Shorts/Reels)"])
        h_img_src.addWidget(self.fac_img_source)
        v_img2vid.addLayout(h_img_src)
        
        h_img_out = QHBoxLayout()
        self.fac_img_out_dir = QLineEdit()
        self.fac_img_out_dir.setPlaceholderText("Chọn thư mục lưu video xuất ra...")
        self.fac_img_out_dir.setReadOnly(True)
        btn_img_out = QPushButton("📁 Chọn Nơi Lưu")
        btn_img_out.clicked.connect(self.browse_fac_img_output)
        h_img_out.addWidget(self.fac_img_out_dir)
        h_img_out.addWidget(btn_img_out)
        v_img2vid.addLayout(h_img_out)
        
        self.btn_run_img2vid = QPushButton("🚀 TẠO VIDEO TỰ ĐỘNG TỪ ẢNH NÀY")
        self.btn_run_img2vid.setObjectName("btn_primary")
        self.btn_run_img2vid.clicked.connect(self.start_fac_img2vid)
        v_img2vid.addWidget(self.btn_run_img2vid)
        v_img2vid.addStretch()
        
        fac_tabs.addTab(tab_img2vid, "🖼️ Ảnh -> Video Tự Động")
        
        # Terminal chung cho Xưởng AI
        self.fac_progress = QProgressBar()
        self.fac_progress.setValue(0)
        v_fac.addWidget(self.fac_progress)
        
        self.fac_status = QLabel("Trạng thái: Đang chờ...")
        v_fac.addWidget(self.fac_status)
        
        self.fac_terminal = QTextEdit()
        self.fac_terminal.setReadOnly(True)
        self.fac_terminal.setStyleSheet("background-color: #11111B; color: #F5C2E7; font-family: Consolas;")
        self.fac_terminal.setMaximumHeight(150)
        v_fac.addWidget(self.fac_terminal)
        
        self.main_tabs.addTab(self.tab_factory, "🏭 Xưởng Video AI")
        
        # --- TAB HƯỚNG DẪN SỬ DỤNG ---
        self.tab_guide = QWidget()
        v_guide = QVBoxLayout(self.tab_guide)
        v_guide.setContentsMargins(30, 30, 30, 30)
        v_guide.setSpacing(15)
        
        lbl_guide_title = QLabel("📖 HƯỚNG DẪN SỬ DỤNG & CÔNG THỨC LÊN XU HƯỚNG")
        lbl_guide_title.setObjectName("header")
        v_guide.addWidget(lbl_guide_title)
        
        guide_text = QTextBrowser()
        guide_text.setStyleSheet("background-color: #1E1E2E; color: #CDD6F4; font-size: 15px; padding: 25px; line-height: 1.6; border-radius: 8px;")
        guide_text.setOpenExternalLinks(True)
        guide_text.setHtml("""
            <h2>Chào mừng đến với Auto Vietsub Pro 🚀</h2>
            <p>Đây là cỗ máy tự động hóa sản xuất video Reup và Affiliate hạng nặng. Dưới đây là hướng dẫn chi tiết từng Module:</p>
            
            <h3>1. Cài Đặt Hệ Thống (Cột trái)</h3>
            <ul>
                <li><b>Gemini Key:</b> Bắt buộc phải có để AI phân tích hình ảnh và viết kịch bản. Đăng ký miễn phí tại <a href="https://aistudio.google.com/" style="color: #89B4FA;">Google AI Studio</a>.</li>
                <li><b>Groq Key:</b> Dùng để dịch thuật siêu tốc. Đăng ký tại <a href="https://console.groq.com/" style="color: #89B4FA;">Groq Console</a>.</li>
                <li><b>Phần cứng:</b> Nếu máy có Card màn hình Nvidia, hãy chọn GPU để tăng tốc độ nhận diện giọng nói (STT).</li>
            </ul>

            <hr style="border: 1px solid #45475A; margin: 15px 0;">

            <h3>2. 📥 Tab Tải Video Mạng</h3>
            <p>Dán link video từ Tiktok, Douyin, Youtube Shorts hoặc Reels vào đây. Tool sẽ tự động tải video gốc không logo (No Watermark) về máy tính.</p>

            <hr style="border: 1px solid #45475A; margin: 15px 0;">

            <h3>3. 🎬 Tab Xử lý Video (Làm Phụ đề / Lồng tiếng / Chống Reup)</h3>
            <p>Tính năng cốt lõi giúp biến video tiếng nước ngoài thành video Tiếng Việt.</p>
            <ul>
                <li><b>Bước 1:</b> Chọn video gốc. Tool sẽ bóc tách âm thanh và dùng AI nghe/chép lại thành văn bản gốc.</li>
                <li><b>Bước 2:</b> Dịch văn bản sang tiếng Việt và chỉnh sửa lại kịch bản nếu cần.</li>
                <li><b>Bước 3 (Chống Reup):</b> Vẽ một vùng mờ (Opaque Box) để che đi chữ tiếng Trung/Anh gốc. Bật thêm "Lớp phủ tàng hình (Noise/Overlay)" để đánh lừa thuật toán quét khung hình của nền tảng.</li>
                <li><b>Bước 4:</b> Tool dùng AI lồng tiếng Việt (TTS) và ghép phụ đề khớp hoàn toàn với miệng nhân vật (Auto-Sync).</li>
            </ul>

            <hr style="border: 1px solid #45475A; margin: 15px 0;">

            <h3>4. 🏭 Tab Xưởng Video AI (Sản xuất công nghiệp)</h3>
            <p>Bộ tính năng bá đạo nhất dành riêng cho dân làm Affiliate / Reup số lượng lớn (500+ video/ngày):</p>
            <ul>
                <li><b>Máy Trộn Video (Mashup):</b> Ném 1 folder chứa nhiều video nguyên liệu vào. Tool sẽ "băm nát" chúng thành các nhát cắt siêu ngắn (VD: 3 giây), sau đó xáo trộn vị trí khung hình ngẫu nhiên để xuất ra hàng trăm video câm hoàn toàn khác biệt nhau. <i>(Hãy mang các video câm này sang Tab 2 để lồng kịch bản lồng tiếng vào)</i>.</li>
                <br>
                <li><b>Máy Xào Kịch Bản:</b> Ném 1 kịch bản bán hàng mẫu vào, AI sẽ viết lại thành hàng chục phiên bản khác nhau (cùng ý nghĩa, khác câu từ) để lồng vào video mà không bị quét trùng lặp âm thanh.</li>
                <br>
                <li><b>Ảnh -> Video Tự Động:</b> Tự động hoá từ A-Z. Chỉ cần gõ Tên Sản Phẩm hoặc tải Ảnh lên. Mọi thứ từ tìm video, tải video, băm trộn đến viết kịch bản chốt sale sẽ được máy tự làm hết.
                <br><br><i>* Mẹo Lên Xu Hướng: Hãy tắt ô "Băm nhỏ & Trộn khung hình" nếu anh chỉ muốn Reup nguyên si video giải trí trên mạng. Máy sẽ bỏ qua bước cắt ghép, giữ nguyên âm thanh gốc, và ngầm tự động ép 7 LỚP GIÁP LÁCH BẢN QUYỀN (Đổi Metadata/EXIF thành iPhone, Lật ngang, Phóng to, Đổi Tone giọng, Tốc độ, Nhiễu, Màu) để qua mặt thuật toán Tiktok/Youtube 100%.</i>
                </li>
            </ul>
        """)
        v_guide.addWidget(guide_text)
        self.main_tabs.addTab(self.tab_guide, "📖 Hướng Dẫn Sử Dụng")
        
        self.main_tabs.setCurrentIndex(1) # Mặc định mở tab Xử lý Video
        
        # --- BƯỚC 1: NẠP VIDEO & XỬ LÝ AI ---
        step1 = QWidget()
        v1 = QVBoxLayout(step1)
        
        lbl_step1 = QLabel("BƯỚC 1: CHỌN NGUỒN & CHẾ ĐỘ XỬ LÝ")
        lbl_step1.setObjectName("header")
        v1.addWidget(lbl_step1)
        
        # Chọn chế độ
        h_mode = QHBoxLayout()
        h_mode.addWidget(QLabel("Chế độ hoạt động:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Chế độ Đơn lẻ (1 Video)", "Chế độ Hàng loạt (Batch Folder)"])
        self.combo_mode.currentIndexChanged.connect(self.toggle_app_mode)
        h_mode.addWidget(self.combo_mode)
        h_mode.addStretch()
        v1.addLayout(h_mode)
        
        # Input/Output
        self.lbl_input_title = QLabel("Thư mục/File đầu vào:")
        v1.addWidget(self.lbl_input_title)
        
        h1_input = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Đường dẫn file video...")
        self.file_input.setReadOnly(True)
        
        self.btn_browse = QPushButton("📂 Chọn File")
        self.btn_browse.clicked.connect(self.browse_file)
        
        h1_input.addWidget(self.file_input)
        h1_input.addWidget(self.btn_browse)
        v1.addLayout(h1_input)
        
        # Batch Output (ẩn mặc định)
        self.h_batch_out = QHBoxLayout()
        self.batch_out_input = QLineEdit()
        self.batch_out_input.setPlaceholderText("Thư mục chứa video đã xuất...")
        self.batch_out_input.setReadOnly(True)
        self.btn_browse_out = QPushButton("📁 Chọn Output")
        self.btn_browse_out.clicked.connect(self.browse_batch_out_dir)
        self.h_batch_out.addWidget(self.batch_out_input)
        self.h_batch_out.addWidget(self.btn_browse_out)
        
        # Batch Config Button (ẩn mặc định)
        self.btn_batch_config = QPushButton("⚙️ Cài đặt Cấu hình & Blur (Áp dụng chung)")
        self.btn_batch_config.setStyleSheet("background-color: #89B4FA; color: #11111B; font-weight: bold;")
        self.btn_batch_config.clicked.connect(self.open_batch_config)
        self.btn_batch_config.hide()
        
        v1.addLayout(self.h_batch_out)
        v1.addWidget(self.btn_batch_config)
        
        # Ban đầu ẩn Output
        for i in range(self.h_batch_out.count()):
            self.h_batch_out.itemAt(i).widget().hide()
        
        self.chk_overwrite = QCheckBox("🗑️ Xóa cache và chạy lại từ đầu (Bỏ qua dữ liệu cũ)")
        self.chk_overwrite.setChecked(False)
        v1.addWidget(self.chk_overwrite)
        
        # Nhóm Cắt Video
        g_trim = QGroupBox("✂️ Cắt Video (Tùy chọn)")
        g_trim.setStyleSheet("QGroupBox { border: 1px solid #45475A; border-radius: 6px; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; color: #CDD6F4; }")
        h_trim = QHBoxLayout(g_trim)
        self.chk_trim = QCheckBox("Cắt Video trước khi làm phụ đề")
        self.chk_trim.setChecked(self.config.get("trim_en", False))
        h_trim.addWidget(self.chk_trim)
        
        h_trim.addWidget(QLabel("Từ (giây):"))
        self.spin_trim_start = QSpinBox()
        self.spin_trim_start.setRange(0, 36000)
        self.spin_trim_start.setValue(self.config.get("trim_start", 0))
        h_trim.addWidget(self.spin_trim_start)
        
        h_trim.addWidget(QLabel("Đến (giây):"))
        self.spin_trim_end = QSpinBox()
        self.spin_trim_end.setRange(0, 36000)
        self.spin_trim_end.setValue(self.config.get("trim_end", 0))
        self.spin_trim_end.setToolTip("Nhập 0 để cắt đến hết video")
        h_trim.addWidget(self.spin_trim_end)
        
        h_trim.addStretch()
        v1.addWidget(g_trim)
        
        h_run = QHBoxLayout()
        self.btn_run_step1 = QPushButton("🚀 BẮT ĐẦU XỬ LÝ (BƯỚC 1)")
        self.btn_run_step1.setObjectName("btn_primary")
        self.btn_run_step1.clicked.connect(self.start_processing)
        
        self.btn_skip_step1 = QPushButton("⏩ Đi thẳng tới Bước 2 (Nhập SRT)")
        self.btn_skip_step1.setStyleSheet("background-color: #313244; color: #CDD6F4; font-weight: bold; padding: 12px; border-radius: 6px;")
        self.btn_skip_step1.clicked.connect(self.skip_step1)
        
        self.btn_stop_step1 = QPushButton("🛑 DỪNG TIẾN TRÌNH")
        self.btn_stop_step1.setStyleSheet("background-color: #F38BA8; color: #F38BA8; font-weight: bold; padding: 12px; border-radius: 6px;")
        self.btn_stop_step1.clicked.connect(self.stop_processing)
        self.btn_stop_step1.hide()
        
        h_run.addWidget(self.btn_run_step1)
        h_run.addWidget(self.btn_skip_step1)
        h_run.addWidget(self.btn_stop_step1)
        v1.addLayout(h_run)
        
        # Bảng hiển thị tiến trình Batch (ẩn mặc định)
        self.batch_table = QTableWidget(0, 4)
        self.batch_table.setHorizontalHeaderLabels(["STT", "Tên Video", "Trạng thái", "Ghi chú"])
        self.batch_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.batch_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.batch_table.hide()
        v1.addWidget(self.batch_table)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        v1.addWidget(self.progress_bar)
        
        self.lbl_status = QLabel("Trạng thái: Đang chờ...")
        v1.addWidget(self.lbl_status)
        
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setPlaceholderText("Log hệ thống sẽ hiển thị ở đây...")
        self.terminal.setStyleSheet("background-color: #11111B; color: #A6E3A1; font-family: Consolas;")
        v1.addWidget(self.terminal)
        
        self.stack.addWidget(step1)
        
        # --- BƯỚC 2: TRẠM KIỂM DUYỆT ---
        step2 = QWidget()
        v2 = QVBoxLayout(step2)
        
        lbl_step2 = QLabel("BƯỚC 2: TRẠM KIỂM DUYỆT SUBTITLE & BLUR")
        lbl_step2.setObjectName("header")
        v2.addWidget(lbl_step2)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #45475A; border-radius: 8px; }
            QTabBar::tab { background: #313244; color: #CDD6F4; padding: 10px 20px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #89B4FA; color: #11111B; font-weight: bold; }
        """)
        v2.addWidget(self.tabs)
        
        # --- TAB 1: PHỤ ĐỀ ---
        tab_sub = QWidget()
        v_sub = QVBoxLayout(tab_sub)
        
        # Thêm các nút chức năng Xuất/Nhập/Dịch SRT
        h_sub_btns = QHBoxLayout()
        self.btn_import_srt = QPushButton("📥 Nhập SRT")
        self.btn_paste_srt = QPushButton("📋 Dán SRT")
        self.btn_export_srt = QPushButton("📤 Xuất SRT")
        self.btn_translate_srt = QPushButton("🔄 Dịch Phụ Đề")
        
        self.btn_import_srt.clicked.connect(self.import_srt)
        self.btn_paste_srt.clicked.connect(self.paste_srt)
        self.btn_export_srt.clicked.connect(self.export_srt)
        self.btn_translate_srt.clicked.connect(self.translate_srt_manual)
        
        self.btn_import_srt.setStyleSheet("background-color: #313244; color: #89B4FA; font-weight: bold; padding: 5px;")
        self.btn_paste_srt.setStyleSheet("background-color: #313244; color: #F5E0DC; font-weight: bold; padding: 5px;")
        self.btn_export_srt.setStyleSheet("background-color: #313244; color: #A6E3A1; font-weight: bold; padding: 5px;")
        self.btn_translate_srt.setStyleSheet("background-color: #F9E2AF; color: #11111B; font-weight: bold; padding: 5px;")
        
        h_sub_btns.addWidget(self.btn_import_srt)
        h_sub_btns.addWidget(self.btn_paste_srt)
        h_sub_btns.addWidget(self.btn_translate_srt)
        h_sub_btns.addWidget(self.btn_export_srt)
        h_sub_btns.addStretch()
        
        v_sub.addLayout(h_sub_btns)
        
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Timestamp (Giữ nguyên)", "Nội dung Subtitle (Được sửa)"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_srt_context_menu)
        v_sub.addWidget(self.table)
        
        self.tabs.addTab(tab_sub, "✍️ Chỉnh sửa Phụ đề")
        
        # --- TAB 2: BLUR & VỊ TRÍ ---
        tab_blur = QWidget()
        tab_blur_layout = QVBoxLayout(tab_blur)
        
        scroll_blur = QScrollArea()
        scroll_blur.setWidgetResizable(True)
        scroll_blur.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll_blur.setStyleSheet("QScrollArea { border: none; }")
        scroll_blur_content = QWidget()
        v_blur = QVBoxLayout(scroll_blur_content)
        
        scroll_blur.setWidget(scroll_blur_content)
        tab_blur_layout.addWidget(scroll_blur)
        
        h2_settings = QHBoxLayout()
        self.chk_blur = QCheckBox("Bật làm mờ (Blur)")
        self.chk_blur.setChecked(True)
        
        h2_settings.addWidget(self.chk_blur)
        h2_settings.addWidget(self.chk_blur)
        v_blur.addLayout(h2_settings)
        
        # Sliders cho Blur
        grid_blur = QFormLayout()
        
        self.slider_x = QSlider(Qt.Orientation.Horizontal)
        self.slider_x.setRange(0, 100); self.slider_x.setValue(0)
        grid_blur.addRow("X (%):", self.slider_x)
        
        self.slider_y = QSlider(Qt.Orientation.Horizontal)
        self.slider_y.setRange(0, 100); self.slider_y.setValue(70)
        grid_blur.addRow("Y (%):", self.slider_y)
        
        self.slider_w = QSlider(Qt.Orientation.Horizontal)
        self.slider_w.setRange(0, 100); self.slider_w.setValue(100)
        grid_blur.addRow("Rộng (%):", self.slider_w)
        
        self.slider_h = QSlider(Qt.Orientation.Horizontal)
        self.slider_h.setRange(0, 100); self.slider_h.setValue(30)
        grid_blur.addRow("Cao (%):", self.slider_h)
        
        self.sliders_widget = QWidget()
        self.sliders_widget.setLayout(grid_blur)
        self.sliders_widget.hide()
        v_blur.addWidget(self.sliders_widget)
        
        # Tự động cập nhật ảnh khi đổi số
        self.slider_x.valueChanged.connect(self.update_preview)
        self.slider_y.valueChanged.connect(self.update_preview)
        self.slider_w.valueChanged.connect(self.update_preview)
        self.slider_h.valueChanged.connect(self.update_preview)
        self.chk_blur.stateChanged.connect(self.update_preview)
        
        # Hàng riêng cho Margin Slider (Tính theo %)
        h2_margin = QHBoxLayout()
        lbl_margin = QLabel("Đẩy Sub lên cao (%):")
        self.margin_slider = QSlider(Qt.Orientation.Horizontal)
        self.margin_slider.setRange(0, 100) # Phần trăm chiều cao video
        self.margin_slider.setValue(2) # Mặc định đẩy lên 2%
        self.margin_slider.valueChanged.connect(self.update_preview)
        
        h2_margin.addWidget(lbl_margin)
        h2_margin.addWidget(self.margin_slider)
        v_blur.addLayout(h2_margin)
        
        # Hàng cho Format Subtitle
        h_format = QHBoxLayout()
        h_format.addWidget(QLabel("Cỡ chữ:"))
        self.spin_font_size = QSpinBox(); self.spin_font_size.setRange(10, 150); self.spin_font_size.setValue(45)
        h_format.addWidget(self.spin_font_size)
        
        h_format.addWidget(QLabel("Màu chữ:"))
        self.combo_font_color = QComboBox()
        self.combo_font_color.addItems(["Trắng", "Vàng", "Xanh Lơ", "Xanh Lá", "Đỏ", "Hồng", "Đen"])
        self.combo_font_color.setCurrentText("Vàng")
        h_format.addWidget(self.combo_font_color)
        
        h_format.addWidget(QLabel("Màu viền:"))
        self.combo_outline_color = QComboBox()
        self.combo_outline_color.addItems(["Đen", "Trắng"])
        self.combo_outline_color.setCurrentText("Đen")
        h_format.addWidget(self.combo_outline_color)
        
        h_format.addWidget(QLabel("Độ dày viền:"))
        self.spin_outline = QSpinBox(); self.spin_outline.setRange(0, 10); self.spin_outline.setValue(2)
        h_format.addWidget(self.spin_outline)
        
        h_format.addWidget(QLabel("Kiểu viền:"))
        self.combo_border_style = QComboBox()
        self.combo_border_style.addItems(["Viền chữ (Outline)", "Khung nền mờ (Opaque Box)"])
        h_format.addWidget(self.combo_border_style)
        
        v_blur.addLayout(h_format)
        
        # Connect tín hiệu
        self.spin_font_size.valueChanged.connect(self.update_preview)
        self.combo_font_color.currentIndexChanged.connect(self.update_preview)
        self.combo_outline_color.currentIndexChanged.connect(self.update_preview)
        self.spin_outline.valueChanged.connect(self.update_preview)
        self.combo_border_style.currentIndexChanged.connect(self.update_preview)
        
        # Thêm khu vực Preview Blur
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
        v_blur.addLayout(h2_preview)
        
        self.tabs.addTab(tab_blur, "🌫️ Cài đặt Blur & Vị trí Sub")
        
        # --- TAB 3: NÂNG CAO ---
        tab_adv = QWidget()
        v_adv = QVBoxLayout(tab_adv)
        
        # --- PRESET SELECTOR ---
        h_preset = QHBoxLayout()
        h_preset.addWidget(QLabel("🔥 Bộ cài đặt (Preset):"))
        self.combo_preset = QComboBox()
        self.combo_preset.addItems([
            "Tuỳ chỉnh (Custom)",
            "Mặc định (Giữ nguyên bản)",
            "Cấu hình Vàng (Bypass nhẹ - Có viền chữ)",
            "Cấu hình Kim Cương (Bypass siêu bạo lực - Lật Video)"
        ])
        h_preset.addWidget(self.combo_preset)
        self.combo_preset.currentIndexChanged.connect(self.apply_preset)
        v_adv.addLayout(h_preset)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # --- Group 1: Cơ bản ---
        g_basic = QGroupBox("Cơ bản")
        v_basic = QVBoxLayout(g_basic)
        self.chk_enable_sub = QCheckBox("Gắn Phụ đề (Subtitle) vào video")
        self.chk_enable_sub.setChecked(True)
        v_basic.addWidget(self.chk_enable_sub)
        scroll_layout.addWidget(g_basic)
        
        # --- Group 2: Màu sắc & Lớp phủ ---
        g_color = QGroupBox("Màu sắc & Lớp phủ (Chống quét MD5)")
        v_color = QFormLayout(g_color)
        
        self.slider_bright = QSlider(Qt.Orientation.Horizontal)
        self.slider_bright.setRange(-100, 100); self.slider_bright.setValue(0)
        v_color.addRow("Độ sáng:", self.slider_bright)
        
        self.slider_contrast = QSlider(Qt.Orientation.Horizontal)
        self.slider_contrast.setRange(-100, 100); self.slider_contrast.setValue(0)
        v_color.addRow("Tương phản:", self.slider_contrast)
        
        self.slider_saturation = QSlider(Qt.Orientation.Horizontal)
        self.slider_saturation.setRange(0, 200); self.slider_saturation.setValue(100)
        v_color.addRow("Bão hoà màu:", self.slider_saturation)
        
        h_overlay = QHBoxLayout()
        self.chk_overlay = QCheckBox("Lớp phủ (Ảnh nhiễu/Màu)")
        self.btn_overlay = QPushButton("Chọn Ảnh")
        self.lbl_overlay_path = QLabel("Chưa chọn")
        h_overlay.addWidget(self.chk_overlay)
        h_overlay.addWidget(self.btn_overlay)
        h_overlay.addWidget(self.lbl_overlay_path)
        v_color.addRow("", h_overlay)
        
        self.slider_overlay_op = QSlider(Qt.Orientation.Horizontal)
        self.slider_overlay_op.setRange(1, 100); self.slider_overlay_op.setValue(10)
        v_color.addRow("Độ rõ lớp phủ:", self.slider_overlay_op)
        
        scroll_layout.addWidget(g_color)
        
        # --- Group 3: Hiệu ứng hình ảnh ---
        g_fx = QGroupBox("Hiệu ứng Video (Reup)")
        v_fx = QFormLayout(g_fx)
        
        self.combo_aspect_ratio = QComboBox()
        self.combo_aspect_ratio.addItems(["Giữ nguyên (Original)", "9:16 (TikTok/Reels) - Viền mờ", "9:16 (TikTok/Reels) - Cắt giữa", "1:1 (Vuông) - Viền mờ", "16:9 (Ngang) - Viền mờ"])
        v_fx.addRow("Khung hình:", self.combo_aspect_ratio)
        
        h_speed = QHBoxLayout()
        self.chk_speed = QCheckBox("Tăng tốc")
        self.spin_speed = QDoubleSpinBox(); self.spin_speed.setRange(1.0, 3.0); self.spin_speed.setSingleStep(0.05); self.spin_speed.setValue(1.1)
        h_speed.addWidget(self.chk_speed); h_speed.addWidget(self.spin_speed)
        v_fx.addRow("Tốc độ (x):", h_speed)
        
        self.chk_flip = QCheckBox("Bật Lật ngang Video")
        v_fx.addRow("Lật Video:", self.chk_flip)
        
        h_noise = QHBoxLayout()
        self.chk_noise = QCheckBox("Bật Nhiễu hạt (Noise)")
        self.chk_noise.setChecked(True)
        self.spin_noise = QSpinBox(); self.spin_noise.setRange(1, 20); self.spin_noise.setValue(3)
        h_noise.addWidget(self.chk_noise); h_noise.addWidget(QLabel("Cường độ:")); h_noise.addWidget(self.spin_noise)
        v_fx.addRow("Chống MD5:", h_noise)
        
        self.chk_fake_iphone = QCheckBox("Bơm Fake Metadata (Apple iPhone 15 Pro Max)")
        self.chk_fake_iphone.setChecked(True)
        v_fx.addRow("Siêu dữ liệu:", self.chk_fake_iphone)
        
        h_round = QHBoxLayout()
        self.chk_round = QCheckBox("Bo tròn góc video")
        self.spin_round = QSpinBox(); self.spin_round.setRange(10, 150); self.spin_round.setValue(60)
        h_round.addWidget(self.chk_round); h_round.addWidget(QLabel("Bán kính:")); h_round.addWidget(self.spin_round)
        v_fx.addRow("Khung hình:", h_round)
        
        h_zoom = QHBoxLayout()
        self.chk_zoom = QCheckBox("Zoom")
        self.combo_zoom_mode = QComboBox()
        self.combo_zoom_mode.addItems(["Tĩnh (Cắt viền cố định)", "Động (Auto Zoom)"])
        self.spin_zoom = QSpinBox(); self.spin_zoom.setRange(1, 50); self.spin_zoom.setValue(15)
        h_zoom.addWidget(self.chk_zoom); h_zoom.addWidget(self.combo_zoom_mode); h_zoom.addWidget(QLabel("Tỷ lệ:"))
        h_zoom.addWidget(self.spin_zoom); h_zoom.addWidget(QLabel("%"))
        v_fx.addRow("Zoom hình:", h_zoom)
        
        self.h_zoom_dyn = QHBoxLayout()
        self.spin_zoom_static = QDoubleSpinBox()
        self.spin_zoom_static.setRange(0.1, 10.0)
        self.spin_zoom_static.setValue(2.0)
        self.spin_zoom_dyn = QDoubleSpinBox()
        self.spin_zoom_dyn.setRange(0.1, 10.0)
        self.spin_zoom_dyn.setValue(1.0)
        
        self.h_zoom_dyn.addWidget(QLabel("Giây đứng im:"))
        self.h_zoom_dyn.addWidget(self.spin_zoom_static)
        self.h_zoom_dyn.addWidget(QLabel("Giây zoom:"))
        self.h_zoom_dyn.addWidget(self.spin_zoom_dyn)
        self.h_zoom_dyn.addStretch()
        v_fx.addRow("Chu kỳ (Zoom Động):", self.h_zoom_dyn)
        
        def _toggle_zoom_dyn():
            is_dyn = self.combo_zoom_mode.currentText() == "Động (Auto Zoom)"
            self.spin_zoom_static.setEnabled(is_dyn)
            self.spin_zoom_dyn.setEnabled(is_dyn)
        self.combo_zoom_mode.currentIndexChanged.connect(_toggle_zoom_dyn)
        _toggle_zoom_dyn()
        
        scroll_layout.addWidget(g_fx)
        
        # --- Group 4: Logo & Nhạc Nền ---
        g_logo = QGroupBox("Chèn Logo & Nhạc")
        v_logo = QFormLayout(g_logo)
        
        h_logo = QHBoxLayout()
        self.chk_logo = QCheckBox("Chèn Logo")
        self.btn_logo = QPushButton("Chọn Logo")
        self.lbl_logo_path = QLabel("Chưa chọn")
        h_logo.addWidget(self.chk_logo); h_logo.addWidget(self.btn_logo); h_logo.addWidget(self.lbl_logo_path)
        v_logo.addRow("", h_logo)
        
        self.combo_logo_pos = QComboBox()
        self.combo_logo_pos.addItems(["Góc trên Trái", "Góc trên Phải", "Góc dưới Trái", "Góc dưới Phải", "Chính giữa"])
        v_logo.addRow("Vị trí Logo:", self.combo_logo_pos)
        
        self.combo_logo_move = QComboBox()
        self.combo_logo_move.addItems(["Đứng yên", "Trôi nổi (Lissajous)", "Nảy (DVD Bounce)"])
        self.combo_logo_move.hide()
        
        h_logo_sz = QHBoxLayout()
        self.slider_logo_scale = QSlider(Qt.Orientation.Horizontal)
        self.slider_logo_scale.setRange(5, 100); self.slider_logo_scale.setValue(20) # 20% width video
        h_logo_sz.addWidget(self.slider_logo_scale)
        v_logo.addRow("Kích thước Logo:", h_logo_sz)
        
        h_logo_op = QHBoxLayout()
        self.slider_logo_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_logo_opacity.setRange(1, 100); self.slider_logo_opacity.setValue(10)
        self.slider_logo_opacity.hide()
        
        h_bgm = QHBoxLayout()
        self.chk_bgm = QCheckBox("Nhạc Nền")
        self.btn_bgm = QPushButton("Chọn Nhạc")
        self.lbl_bgm_path = QLabel("Chưa chọn")
        h_bgm.addWidget(self.chk_bgm); h_bgm.addWidget(self.btn_bgm); h_bgm.addWidget(self.lbl_bgm_path)
        v_logo.addRow("", h_bgm)
        
        self.slider_bgm_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_bgm_vol.setRange(1, 100); self.slider_bgm_vol.setValue(10)
        v_logo.addRow("Âm lượng Nhạc:", self.slider_bgm_vol)
        
        scroll_layout.addWidget(g_logo)
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        v_adv.addWidget(scroll)
        
        self.tabs.addTab(tab_adv, "🚀 Nâng cao")
        
        # Kết nối sự kiện Logo và BGM
        self.logo_path = self.config.get("adv_logo_path", "")
        self.bgm_path = self.config.get("adv_bgm_path", "")
        self.overlay_path = self.config.get("adv_overlay_path", "")
        if self.logo_path: self.lbl_logo_path.setText(os.path.basename(self.logo_path))
        if self.bgm_path: self.lbl_bgm_path.setText(os.path.basename(self.bgm_path))
        if self.overlay_path: self.lbl_overlay_path.setText(os.path.basename(self.overlay_path))
        
        self.btn_logo.clicked.connect(self.browse_logo)
        self.btn_bgm.clicked.connect(self.browse_bgm)
        self.btn_overlay.clicked.connect(self.browse_overlay)
        
        # Phục hồi dữ liệu cài đặt cho Tab 2 & 3
        self.spin_font_size.setValue(self.config.get("sub_font_size", 45))
        self.combo_font_color.setCurrentText(self.config.get("sub_font_color", "Vàng"))
        self.combo_outline_color.setCurrentText(self.config.get("sub_outline_color", "Đen"))
        self.spin_outline.setValue(self.config.get("sub_outline_width", 2))
        if hasattr(self, 'combo_border_style'):
            self.combo_border_style.setCurrentText(self.config.get("sub_border_style", "Viền chữ (Outline)"))
        self.margin_slider.setValue(self.config.get("sub_margin_v", 10))
        self.chk_blur.setChecked(self.config.get("blur_enabled", True))
        self.slider_x.setValue(self.config.get("blur_x", 0))
        self.slider_y.setValue(self.config.get("blur_y", 70))
        self.slider_w.setValue(self.config.get("blur_w", 100))
        self.slider_h.setValue(self.config.get("blur_h", 30))
        
        self.chk_enable_sub.setChecked(self.config.get("adv_enable_sub", True))
        self.slider_bright.setValue(self.config.get("adv_bright", 0))
        self.slider_contrast.setValue(self.config.get("adv_contrast", 0))
        self.slider_saturation.setValue(self.config.get("adv_sat", 100))
        self.chk_overlay.setChecked(self.config.get("adv_overlay_en", False))
        self.slider_overlay_op.setValue(self.config.get("adv_overlay_op", 10))
        self.combo_aspect_ratio.setCurrentText(self.config.get("adv_aspect_ratio", "Giữ nguyên (Original)"))
        self.chk_speed.setChecked(self.config.get("adv_speed_en", False))
        self.spin_speed.setValue(self.config.get("adv_speed_val", 1.1))
        self.chk_flip.setChecked(self.config.get("flip", False))
        self.chk_noise.setChecked(self.config.get("noise", True))
        self.spin_noise.setValue(self.config.get("noise_strength", 3))
        self.chk_fake_iphone.setChecked(self.config.get("fake_iphone", True))
        self.chk_round.setChecked(self.config.get("round_enabled", False))
        self.spin_round.setValue(self.config.get("round_radius", 60))
        self.combo_preset.setCurrentText(self.config.get("preset_mode", "Tuỳ chỉnh (Custom)"))
        self.chk_zoom.setChecked(self.config.get("adv_zoom_en", False))
        self.spin_zoom.setValue(self.config.get("adv_zoom_val", 15))
        self.combo_zoom_mode.setCurrentText(self.config.get("adv_zoom_mode", "Tĩnh (Cắt viền cố định)"))
        self.spin_zoom_static.setValue(self.config.get("adv_zoom_static", 2.0))
        self.spin_zoom_dyn.setValue(self.config.get("adv_zoom_dyn", 1.0))
        _toggle_zoom_dyn()
        
        self.chk_logo.setChecked(self.config.get("adv_logo_en", False))
        self.combo_logo_pos.setCurrentText(self.config.get("adv_logo_pos", "Góc trên Trái"))
        self.combo_logo_move.setCurrentText(self.config.get("adv_logo_move", "Đứng yên"))
        self.slider_logo_scale.setValue(self.config.get("adv_logo_scale", 20))
        self.slider_logo_opacity.setValue(self.config.get("adv_logo_op", 80))
        self.chk_bgm.setChecked(self.config.get("adv_bgm_en", False))
        self.slider_bgm_vol.setValue(self.config.get("adv_bgm_vol", 10))
        
        h_hw = QHBoxLayout()
        h_hw.addWidget(QLabel("Thiết bị Xuất Video:"))
        self.combo_render_hw = QComboBox()
        self.combo_render_hw.addItems(["Tự động quét GPU (Khuyên dùng)", "Chỉ dùng CPU (Chậm hơn)"])
        self.combo_render_hw.setCurrentText(self.config.get("render_hw", "Tự động quét GPU (Khuyên dùng)"))
        h_hw.addWidget(self.combo_render_hw)
        h_hw.addStretch()
        v2.addLayout(h_hw)
        
        h_out = QHBoxLayout()
        self.out_dir_input = QLineEdit()
        self.out_dir_input.setPlaceholderText("Thư mục lưu video (Mặc định: Cùng thư mục video gốc)")
        self.out_dir_input.setReadOnly(True)
        btn_out_dir = QPushButton("📁 Chọn Nơi Lưu")
        btn_out_dir.clicked.connect(self.browse_out_dir)
        btn_open_dir = QPushButton("📂 Mở Thư Mục")
        btn_open_dir.clicked.connect(self.open_out_dir)
        h_out.addWidget(self.out_dir_input)
        h_out.addWidget(btn_out_dir)
        h_out.addWidget(btn_open_dir)
        v2.addLayout(h_out)
        
        h2_btns = QHBoxLayout()
        btn_back = QPushButton("⬅️ Quay lại")
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_render = QPushButton("🎥 Render Video Cuối (Bước 3)")
        self.btn_render.setObjectName("btn_primary")
        self.btn_render.clicked.connect(self.start_step3)
        
        self.btn_stop_step3 = QPushButton("🛑 DỪNG TIẾN TRÌNH")
        self.btn_stop_step3.setStyleSheet("background-color: #F38BA8; color: #11111B; font-weight: bold; padding: 12px; border-radius: 6px;")
        self.btn_stop_step3.clicked.connect(self.stop_processing)
        self.btn_stop_step3.hide()
        
        h2_btns.addWidget(btn_back)
        h2_btns.addStretch()
        h2_btns.addWidget(self.btn_render)
        h2_btns.addWidget(self.btn_stop_step3)
        v2.addLayout(h2_btns)
        
        self.stack.addWidget(step2)
        
        # Thêm content vào main layout
        main_layout.addWidget(content_widget)

    def apply_preset(self):
        text = self.combo_preset.currentText()
        if "Tuỳ chỉnh" in text: return
        
        self.blockSignals(True)
        if "Mặc định" in text:
            self.chk_noise.setChecked(False)
            if hasattr(self, 'chk_fake_iphone'): self.chk_fake_iphone.setChecked(False)
            if hasattr(self, 'chk_round'): self.chk_round.setChecked(False)
            self.chk_speed.setChecked(False)
            self.chk_zoom.setChecked(False)
            self.chk_flip.setChecked(False)
            self.slider_bright.setValue(0)
            self.slider_contrast.setValue(0)
            self.slider_saturation.setValue(100)
            if hasattr(self, 'combo_border_style'):
                self.combo_border_style.setCurrentText("Viền chữ (Outline)")
        elif "Vàng" in text:
            self.chk_noise.setChecked(True)
            self.spin_noise.setValue(1)
            if hasattr(self, 'chk_fake_iphone'): self.chk_fake_iphone.setChecked(True)
            if hasattr(self, 'chk_round'): self.chk_round.setChecked(True); self.spin_round.setValue(40)
            self.chk_speed.setChecked(True)
            self.spin_speed.setValue(1.05)
            self.chk_zoom.setChecked(True)
            self.spin_zoom.setValue(3)
            self.combo_zoom_mode.setCurrentText("Tĩnh (Cắt viền cố định)")
            self.chk_flip.setChecked(False)
            self.slider_bright.setValue(1)
            self.slider_contrast.setValue(1)
            self.slider_saturation.setValue(105)
            if hasattr(self, 'combo_border_style'):
                self.combo_border_style.setCurrentText("Khung nền mờ (Opaque Box)")
        elif "Kim Cương" in text:
            self.chk_noise.setChecked(True)
            self.spin_noise.setValue(3)
            if hasattr(self, 'chk_fake_iphone'): self.chk_fake_iphone.setChecked(True)
            if hasattr(self, 'chk_round'): self.chk_round.setChecked(True); self.spin_round.setValue(60)
            self.chk_speed.setChecked(True)
            self.spin_zoom.setValue(5)
            self.combo_zoom_mode.setCurrentText("Động (Auto Zoom)")
            self.chk_flip.setChecked(True)
            self.slider_bright.setValue(2)
            self.slider_contrast.setValue(2)
            self.slider_saturation.setValue(110)
            if hasattr(self, 'combo_border_style'):
                self.combo_border_style.setCurrentText("Khung nền mờ (Opaque Box)")
        self.blockSignals(False)

    def save_config(self, silent=False):
        self.config["device_type"] = self.device_cb.currentText()

        self.config["translation_model"] = self.model_cb.currentText()
        self.config["target_lang"] = self.target_lang_cb.currentText()
        self.config["gemini_prompt"] = self.prompt_input.toPlainText()
        self.config["gemini_api_key"] = self.gemini_key.text()
        self.config["gemini_api_key_backup"] = self.gemini_key_backup.text()
        self.config["groq_api_key"] = self.groq_key.text()
        self.config["voice"] = self.voice_cb.currentText()
        self.config["tiktok_session_id"] = self.tiktok_id.text()
        self.config["tts_threads"] = self.spin_tts_threads.value()
        self.config["tts_speed"] = self.spin_tts_speed.value()
        self.config["max_tts_speed"] = self.spin_max_tts_speed.value()
        self.config["bg_volume"] = self.bg_vol_slider.value() / 100.0
        
        if hasattr(self, 'chk_enable_tts'):
            self.config["enable_tts"] = self.chk_enable_tts.isChecked()
            self.config["enable_sub"] = self.chk_enable_sub.isChecked()
        
        if hasattr(self, 'chk_trim'):
            self.config["trim_en"] = self.chk_trim.isChecked()
            self.config["trim_start"] = self.spin_trim_start.value()
            self.config["trim_end"] = self.spin_trim_end.value()
            
        if hasattr(self, 'combo_render_hw'):
            self.config["render_hw"] = self.combo_render_hw.currentText()
        
        try:
            # Lưu cài đặt Tab 2 & 3 (Dùng try-except để tránh lỗi khi các widget chưa khởi tạo xong)
            self.config["sub_font_size"] = self.spin_font_size.value()
            self.config["sub_font_color"] = self.combo_font_color.currentText()
            self.config["sub_outline_color"] = self.combo_outline_color.currentText()
            self.config["sub_outline_width"] = self.spin_outline.value()
            if hasattr(self, 'combo_border_style'):
                self.config["sub_border_style"] = self.combo_border_style.currentText()
            self.config["sub_margin_v"] = self.margin_slider.value()
            
            self.config["blur_enabled"] = self.chk_blur.isChecked()
            self.config["blur_x"] = self.slider_x.value()
            self.config["blur_y"] = self.slider_y.value()
            self.config["blur_w"] = self.slider_w.value()
            self.config["blur_h"] = self.slider_h.value()
            
            self.config["adv_enable_sub"] = self.chk_enable_sub.isChecked()
            self.config["adv_bright"] = self.slider_bright.value()
            self.config["adv_contrast"] = self.slider_contrast.value()
            self.config["adv_sat"] = self.slider_saturation.value()
            self.config["adv_overlay_en"] = self.chk_overlay.isChecked()
            self.config["adv_overlay_path"] = getattr(self, "overlay_path", "")
            self.config["adv_overlay_op"] = self.slider_overlay_op.value()
            self.config["adv_aspect_ratio"] = self.combo_aspect_ratio.currentText()
            self.config["adv_speed_en"] = self.chk_speed.isChecked()
            self.config["speed_value"] = self.spin_speed.value()
            self.config["flip"] = self.chk_flip.isChecked()
            self.config["noise"] = self.chk_noise.isChecked()
            self.config["noise_strength"] = self.spin_noise.value()
            self.config["fake_iphone"] = self.chk_fake_iphone.isChecked()
            self.config["round_enabled"] = self.chk_round.isChecked()
            self.config["round_radius"] = self.spin_round.value()
            self.config["preset_mode"] = self.combo_preset.currentText()
            self.config["adv_zoom_en"] = self.chk_zoom.isChecked()
            self.config["adv_zoom_val"] = self.spin_zoom.value()
            self.config["adv_zoom_mode"] = self.combo_zoom_mode.currentText()
            self.config["adv_zoom_static"] = self.spin_zoom_static.value()
            self.config["adv_zoom_dyn"] = self.spin_zoom_dyn.value()
            self.config["adv_logo_en"] = self.chk_logo.isChecked()
            self.config["adv_logo_path"] = getattr(self, "logo_path", "")
            self.config["adv_logo_pos"] = self.combo_logo_pos.currentText()
            self.config["adv_logo_move"] = self.combo_logo_move.currentText()
            self.config["adv_logo_scale"] = self.slider_logo_scale.value()
            self.config["adv_logo_op"] = self.slider_logo_opacity.value()
            self.config["adv_bgm_en"] = self.chk_bgm.isChecked()
            self.config["adv_bgm_path"] = getattr(self, "bgm_path", "")
            self.config["adv_bgm_vol"] = self.slider_bgm_vol.value()
        except AttributeError:
            pass # Các UI tab2,3 chưa load xong
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)
            
        if not silent:
            QMessageBox.information(self, "Thành công", "Đã lưu cài đặt!")
        
    def append_log(self, text):
        from PyQt6.QtGui import QTextCursor
        if text.startswith('\r'):
            cursor = self.terminal.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            self.terminal.append(text.replace('\r', ''))
        else:
            self.terminal.append(text.strip('\n')) # Tránh dư dòng trống khi print
            
        # Scroll to bottom
        sb = self.terminal.verticalScrollBar()
        sb.setValue(sb.maximum())
        
    def append_dl_log(self, text):
        from PyQt6.QtGui import QTextCursor
        if text.startswith('\r'):
            cursor = self.dl_terminal.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            self.dl_terminal.append(text.replace('\r', ''))
        else:
            self.dl_terminal.append(text.strip('\n'))
        sb = self.dl_terminal.verticalScrollBar()
        sb.setValue(sb.maximum())

    def open_dl_folder(self):
        import os, subprocess, sys
        out_dir = os.path.join(os.getcwd(), "downloads")
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        try:
            if sys.platform == "win32":
                os.startfile(out_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", out_dir])
            else:
                subprocess.Popen(["xdg-open", out_dir])
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể mở thư mục: {e}")

    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập đường dẫn video!")
            return
            
        cookie_text = self.cookie_input.text().strip()
            
        self.btn_download.setEnabled(False)
        self.dl_terminal.clear()
        self.dl_progress.setValue(0)
        self.dl_status.setText("Trạng thái: Đang chuẩn bị tải...")
        
        import os
        out_dir = os.path.join(os.getcwd(), "downloads")
        
        from ui_workers import WorkerDownloadVideo
        self.worker_dl = WorkerDownloadVideo(url, out_dir, cookie_string=cookie_text)
        self.worker_dl.progress.connect(self.update_dl_progress)
        self.worker_dl.log.connect(self.append_dl_log)
        self.worker_dl.work_done.connect(self.download_done)
        self.worker_dl.start()

    def update_dl_progress(self, val, msg):
        self.dl_progress.setValue(val)
        self.dl_status.setText(f"Trạng thái: {msg}")

    def download_done(self, success, file_path):
        self.btn_download.setEnabled(True)
        if success:
            QMessageBox.information(self, "Thành công", f"Đã tải xong:\n{file_path}")
            # Chuyển file sang tab 1 nếu muốn xử lý luôn
            reply = QMessageBox.question(self, "Xử lý Video", "Bạn có muốn chuyển video này sang Tab Xử lý (Bước 1) ngay không?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.main_tabs.setCurrentIndex(1)
                self.stack.setCurrentIndex(0)
                self.file_input.setText(file_path)
        else:
            QMessageBox.critical(self, "Thất bại", "Quá trình tải video gặp lỗi, vui lòng xem log.")

    def extract_script_from_video(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn Video/Audio chứa kịch bản", "", "Media Files (*.mp4 *.mkv *.avi *.mp3 *.wav)")
        if not file_path: return
        
        self.spin_original_txt.setPlaceholderText("Đang dùng AI nghe và chép kịch bản từ video... Vui lòng đợi trong giây lát!")
        self.spin_original_txt.clear()
        
        from ui_workers import WorkerExtractScript
        self.worker_ext_script = WorkerExtractScript(file_path, self.config)
        self.worker_ext_script.progress.connect(lambda val, msg: self.fac_status.setText(f"Trạng thái: {msg}"))
        self.worker_ext_script.log.connect(self.append_fac_log)
        self.worker_ext_script.work_done.connect(self.extract_script_done)
        self.worker_ext_script.start()
        
    def extract_script_done(self, success, result):
        if success:
            self.spin_original_txt.setText(result)
            QMessageBox.information(self, "Thành công", "Đã bóc tách kịch bản thành công!")
        else:
            self.spin_original_txt.setPlaceholderText("Lỗi bóc tách kịch bản...")
            QMessageBox.critical(self, "Lỗi", f"Không thể trích xuất kịch bản: {result}")

    def browse_fac_input(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa video mẫu")
        if dir_path:
            self.fac_input_dir.setText(dir_path)

    def browse_fac_output(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu video đã mix")
        if dir_path:
            self.fac_output_dir.setText(dir_path)

    def open_fac_output(self):
        import os, subprocess, sys
        out_dir = self.fac_output_dir.text().strip()
        if not out_dir or not os.path.exists(out_dir):
            QMessageBox.warning(self, "Lỗi", "Thư mục chưa tồn tại!")
            return
        try:
            if sys.platform == "win32":
                os.startfile(out_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", out_dir])
            else:
                subprocess.Popen(["xdg-open", out_dir])
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể mở thư mục: {e}")

    def append_fac_log(self, text):
        from PyQt6.QtGui import QTextCursor
        if text.startswith('\r'):
            cursor = self.fac_terminal.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            self.fac_terminal.append(text.replace('\r', ''))
        else:
            self.fac_terminal.append(text.strip('\n'))
        sb = self.fac_terminal.verticalScrollBar()
        sb.setValue(sb.maximum())

    def update_fac_progress(self, val, msg):
        self.fac_progress.setValue(val)
        self.fac_status.setText(f"Trạng thái: {msg}")

    def set_fac_buttons_enabled(self, enabled):
        self.btn_run_mashup.setEnabled(enabled)
        self.btn_run_spin.setEnabled(enabled)
        self.btn_run_img2vid.setEnabled(enabled)

    def start_fac_mashup(self):
        in_dir = self.fac_input_dir.text().strip()
        out_dir = self.fac_output_dir.text().strip()
        if not in_dir or not out_dir:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn cả thư mục Input và Output!")
            return
            
        self.set_fac_buttons_enabled(False)
        self.fac_terminal.clear()
        
        from ui_workers import WorkerAIFactory
        self.worker_fac = WorkerAIFactory(
            mode="mashup",
            input_dir=in_dir,
            output_dir=out_dir,
            num_videos=self.spin_num_videos.value(),
            clip_duration=self.spin_clip_dur.value(),
            config=self.config
        )
        self.worker_fac.progress.connect(self.update_fac_progress)
        self.worker_fac.log.connect(self.append_fac_log)
        self.worker_fac.work_done.connect(self.fac_mashup_done)
        self.worker_fac.start()

    def fac_mashup_done(self, success, out_dir):
        self.set_fac_buttons_enabled(True)
        if success:
            QMessageBox.information(self, "Thành công", "Đã mix xong toàn bộ video!")
        else:
            QMessageBox.critical(self, "Lỗi", "Quá trình mix gặp lỗi, vui lòng xem log.")

    def start_fac_spin(self):
        text = self.spin_original_txt.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Lỗi", "Vui lòng dán kịch bản gốc vào!")
            return
            
        prod_name = getattr(self, "spin_product_name", QLineEdit()).text().strip()
        if prod_name:
            text = f"[SẢN PHẨM CẦN BÁN: {prod_name}]\n\nHãy xào lại kịch bản dưới đây và thay thế linh hoạt để bám sát vào sản phẩm này nhé:\n{text}"
            
        self.set_fac_buttons_enabled(False)
        self.fac_terminal.clear()
        
        from ui_workers import WorkerAIFactory
        self.worker_fac_spin = WorkerAIFactory(
            mode="spin",
            input_dir="",
            output_dir="",
            num_videos=0,
            clip_duration=0,
            config=self.config,
            original_script=text
        )
        self.worker_fac_spin.progress.connect(self.update_fac_progress)
        self.worker_fac_spin.log.connect(self.append_fac_log)
        self.worker_fac_spin.work_done.connect(self.fac_spin_done)
        self.worker_fac_spin.start()

    def fac_spin_done(self, success, new_text):
        self.set_fac_buttons_enabled(True)
        if success:
            self.spin_new_txt.setText(new_text)
            QMessageBox.information(self, "Thành công", "Đã xào xong kịch bản!")
        else:
            QMessageBox.critical(self, "Lỗi", "Quá trình xào kịch bản gặp lỗi, xem log.")

    def browse_fac_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn hình ảnh sản phẩm", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            self.fac_img_path.setText(file_path)

    def browse_fac_img_output(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu video")
        if dir_path:
            self.fac_img_out_dir.setText(dir_path)

    def start_fac_img2vid(self):
        img_path = self.fac_img_path.text().strip()
        keyword = self.fac_img_keyword.text().strip()
        out_dir = self.fac_img_out_dir.text().strip()
        use_ai_spin = self.chk_use_ai_spin.isChecked()
        
        if not out_dir:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục lưu!")
            return
            
        if not img_path and not keyword:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn hình ảnh HOẶC nhập tên sản phẩm!")
            return
            
        source_type = "youtube"
            
        self.set_fac_buttons_enabled(False)
        self.fac_terminal.clear()
        
        from ui_workers import WorkerAIFactory
        self.worker_fac_img = WorkerAIFactory(
            mode="img2vid",
            input_dir="",
            output_dir=out_dir,
            num_videos=self.spin_num_videos.value(),
            clip_duration=self.spin_clip_dur.value(),
            config=self.config,
            image_path=img_path,
            keyword=keyword,
            source_type=source_type,
            use_ai_spin=use_ai_spin
        )
        self.worker_fac_img.progress.connect(self.update_fac_progress)
        self.worker_fac_img.log.connect(self.append_fac_log)
        self.worker_fac_img.work_done.connect(self.fac_img2vid_done)
        self.worker_fac_img.start()

    def fac_img2vid_done(self, success, result_data):
        self.set_fac_buttons_enabled(True)
        if success and result_data:
            out_dir = result_data.get("out_dir", "")
            script = result_data.get("script", "")
            
            # Ghi kịch bản ra file text trong thư mục output
            if out_dir and script:
                import os
                try:
                    with open(os.path.join(out_dir, "kich_ban_ai.txt"), "w", encoding="utf-8") as f:
                        f.write(script)
                except:
                    pass
            
            msg = "Đã tự động tải và mix video thành công!\nKịch bản mẫu đã được lưu trong thư mục."
            QMessageBox.information(self, "Thành công", msg)
            
            # Hiển thị luôn kịch bản lên tab Auto-Spin để tiện dùng
            self.spin_new_txt.setText(script)
        else:
            QMessageBox.critical(self, "Lỗi", "Quá trình tạo video từ ảnh gặp lỗi, xem log.")

    def update_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.lbl_status.setText(f"Trạng thái: {msg}")
        
    def toggle_app_mode(self):
        idx = self.combo_mode.currentIndex()
        if idx == 1: # Batch Mode
            self.lbl_input_title.setText("Thư mục Video đầu vào:")
            self.btn_browse.setText("📁 Chọn Thư mục")
            self.file_input.clear()
            self.file_input.setPlaceholderText("Đường dẫn đến thư mục chứa các video...")
            for i in range(self.h_batch_out.count()):
                self.h_batch_out.itemAt(i).widget().show()
            self.btn_batch_config.show()
            self.btn_run_step1.setText("🚀 BẮT ĐẦU XỬ LÝ HÀNG LOẠT (TỰ ĐỘNG A-Z)")
            self.batch_table.show()
            self.btn_skip_step1.hide()
            
            # Disable Tab Phụ đề (Step 2)
            self.tabs.setTabEnabled(0, False)
            self.tabs.setCurrentIndex(1)
            self.btn_render.setText("Lưu Cài Đặt Khung Hình & Quay Lại")
        else: # Single Mode
            self.lbl_input_title.setText("Thư mục/File đầu vào:")
            self.btn_browse.setText("📂 Chọn File")
            self.file_input.clear()
            self.file_input.setPlaceholderText("Đường dẫn file video...")
            for i in range(self.h_batch_out.count()):
                self.h_batch_out.itemAt(i).widget().hide()
            self.btn_batch_config.hide()
            self.btn_run_step1.setText("🚀 BẮT ĐẦU XỬ LÝ (BƯỚC 1)")
            self.batch_table.hide()
            self.btn_skip_step1.show()
            
            self.tabs.setTabEnabled(0, True)
            self.tabs.setCurrentIndex(0)
            self.btn_render.setText("🎥 Render Video Cuối (Bước 3)")
            
    def browse_batch_out_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu hàng loạt")
        if dir_path:
            self.batch_out_input.setText(dir_path)
            
    def open_batch_config(self):
        # Lấy video đầu tiên trong thư mục làm preview
        folder = self.file_input.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn Thư mục Video hợp lệ trước!")
            return
            
        videos = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))]
        if not videos:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy video nào trong thư mục!")
            return
            
        self.current_video = videos[0]
        self.update_preview()
        self.stack.setCurrentIndex(1)
        
    def start_processing(self):
        idx = self.combo_mode.currentIndex()
        if idx == 1:
            self.start_batch()
        else:
            self.start_step1()

    def browse_file(self):
        if self.combo_mode.currentIndex() == 1:
            val = QFileDialog.getExistingDirectory(self, "Chọn Thư mục chứa Video")
        else:
            val, _ = QFileDialog.getOpenFileName(self, "Chọn Video", "", "Video Files (*.mp4 *.mkv *.avi *.mov)")
        if val:
            self.file_input.setText(val)
            
    def browse_out_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu Video")
        if dir_path:
            self.out_dir_input.setText(dir_path)
            
    def open_out_dir(self):
        path = self.out_dir_input.text().strip()
        if not path or not os.path.exists(path):
            path = os.getcwd()
            
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể mở thư mục: {e}")
            
    def start_step1(self):
        self.save_config(silent=True)
        
        file_val = self.file_input.text().strip()
        
        if not file_val:
            QMessageBox.warning(self, "Lỗi", "Vui lòng Chọn File Video!")
            return
            
        mode = "file"
        val = file_val
            
        self.terminal.clear()
        self.progress_bar.setValue(0)
        self.btn_run_step1.setEnabled(False)
        self.btn_stop_step1.show()

        self.worker1 = WorkerStep1(mode, val, self.config, overwrite=self.chk_overwrite.isChecked())
        self.worker1.progress.connect(self.update_progress)
        self.worker1.log.connect(self.append_log)
        self.worker1.work_done.connect(self.step1_done)
        self.worker1.start()
        
    def skip_step1(self):
        video_path = self.file_input.text()
        if not video_path or not os.path.exists(video_path):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn Video ở Bước 1 trước khi chuyển sang Bước 2!")
            return
            
        self.current_video = video_path
        self.stack.setCurrentIndex(1)
        self.append_log("Đã bỏ qua Bước 1. Vui lòng nhập file SRT ở Bước 2.")

    def translate_srt_manual(self):
        if self.table.rowCount() == 0:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Lỗi", "Bảng phụ đề đang trống. Vui lòng nạp SRT trước!")
            return
            
        self.btn_translate_srt.setEnabled(False)
        self.btn_import_srt.setEnabled(False)
        self.append_log("Đang bắt đầu tiến trình dịch SRT thủ công...")
        self.save_config(silent=True)
        
        # Sửa lỗi: Tạo chuỗi SRT thay vì truyền List
        srt_content = ""
        for row in range(self.table.rowCount()):
            idx_item = self.table.item(row, 0)
            ts_item = self.table.item(row, 1)
            txt_item = self.table.item(row, 2)
            
            idx = idx_item.text() if idx_item else str(row + 1)
            ts = ts_item.text() if ts_item else ""
            txt = txt_item.text() if txt_item else ""
            
            # Khôi phục timestamp sạch nếu nó bị gộp với text
            import re
            ts_match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})', ts)
            if ts_match:
                clean_ts = ts_match.group(1)
                extra = ts[ts_match.end():].strip()
                if extra and not txt:
                    txt = extra
                ts = clean_ts
                # Cập nhật lại UI cho sạch đẹp
                self.table.item(row, 1).setText(ts)
                self.table.item(row, 2).setText(txt)
            srt_content += f"{idx}\n{ts}\n{txt}\n\n"
        
        from ui_workers import WorkerTranslateSRT
        self.worker_trans = WorkerTranslateSRT(srt_content, self.config)
        self.worker_trans.progress.connect(self.update_progress)
        self.worker_trans.log.connect(self.append_log)
        self.worker_trans.work_done.connect(self.translate_srt_done)
        self.worker_trans.start()
        
    def translate_srt_done(self, success, out_srt, new_subs_data):
        self.btn_translate_srt.setEnabled(True)
        self.btn_import_srt.setEnabled(True)
        if success and isinstance(new_subs_data, list) and len(new_subs_data) > 0:
            self.subs_data = new_subs_data
            self.table.setRowCount(0)
            def format_time(seconds):
                h = int(seconds // 3600)
                m = int((seconds % 3600) // 60)
                s = int(seconds % 60)
                ms = int((seconds - int(seconds)) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            for i, sub in enumerate(self.subs_data):
                self.table.insertRow(i)
                from PyQt6.QtWidgets import QTableWidgetItem
                self.table.setItem(i, 0, QTableWidgetItem(str(i+1)))
                self.table.setItem(i, 1, QTableWidgetItem(sub['timestamp']))
                self.table.setItem(i, 2, QTableWidgetItem(sub['text']))
            self.append_log("Đã cập nhật bảng với phụ đề đã dịch!")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Thành công", "Đã dịch phụ đề xong!")
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Lỗi", "Quá trình dịch thất bại, xem log để biết thêm chi tiết.")

    def step1_done(self, success, video_path, subs_data, bgm_path=""):
        self.btn_run_step1.setEnabled(True)
        self.btn_stop_step1.hide()

        if success:
            self.current_video = video_path
            self.subs_data = subs_data
            self.current_bgm_path = bgm_path
            
            # Load data vào bảng
            self.table.setRowCount(0)
            for i, sub in enumerate(subs_data):
                self.table.insertRow(i)
                self.table.setItem(i, 0, QTableWidgetItem(str(sub['index'])))
                self.table.setItem(i, 1, QTableWidgetItem(sub['timestamp']))
                self.table.setItem(i, 2, QTableWidgetItem(sub['text']))
                
                # Cột 0 và 1 không cho sửa
                self.table.item(i, 0).setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.table.item(i, 1).setFlags(Qt.ItemFlag.ItemIsEnabled)
                
            self.update_preview()
            self.stack.setCurrentIndex(1) # Chuyển sang Bước 2
        else:
            QMessageBox.critical(self, "Lỗi", "Quá trình Bước 1 thất bại! Xem log.")
            
    def start_batch(self):
        self.save_config(silent=True)
        folder = self.file_input.text().strip()
        out_folder = self.batch_out_input.text().strip()
        
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "Lỗi", "Vui lòng Chọn Thư mục Video Đầu vào hợp lệ!")
            return
        if not out_folder:
            QMessageBox.warning(self, "Lỗi", "Vui lòng Chọn Thư mục Lưu Output (Bắt buộc cho Batch Mode)!")
            return
            
        videos = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))]
        if not videos:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy video nào trong thư mục!")
            return
            
        self.terminal.clear()
        self.progress_bar.setValue(0)
        self.btn_run_step1.setEnabled(False)
        self.btn_stop_step1.show()

        self.btn_batch_config.setEnabled(False)
        self.batch_table.setRowCount(0)
        
        # Load danh sách vào table
        for i, v in enumerate(videos):
            self.batch_table.insertRow(i)
            self.batch_table.setItem(i, 0, QTableWidgetItem(str(i+1)))
            self.batch_table.setItem(i, 1, QTableWidgetItem(os.path.basename(v)))
            self.batch_table.setItem(i, 2, QTableWidgetItem("Đang chờ"))
            self.batch_table.setItem(i, 3, QTableWidgetItem(""))
            
        from ui_workers import WorkerBatch
        
        # Setup advanced configs map
        adv_config = {
            "sub_border_style": 3 if getattr(self, 'combo_border_style', None) and self.combo_border_style.currentText() == "Khung nền mờ (Opaque Box)" else 1,
            "aspect_ratio": self.combo_aspect_ratio.currentText(),
            "render_hw": self.combo_render_hw.currentText() if hasattr(self, 'combo_render_hw') else "Tự động quét GPU (Khuyên dùng)",
            "speed": self.spin_speed.value() if self.chk_speed.isChecked() else 1.0,
            "flip": self.chk_flip.isChecked(),
            "noise": {
                "enabled": self.chk_noise.isChecked(),
                "strength": self.spin_noise.value()
            },
            "fake_iphone": self.chk_fake_iphone.isChecked(),
            "round": {
                "enabled": self.chk_round.isChecked(),
                "radius": self.spin_round.value()
            },
            "zoom": {
                "enabled": self.chk_zoom.isChecked(),
                "val": self.spin_zoom.value(),
                "mode": self.combo_zoom_mode.currentText(),
                "static_time": self.spin_zoom_static.value(),
                "dyn_time": self.spin_zoom_dyn.value()
            },
            "logo": {
                "path": self.logo_path if self.chk_logo.isChecked() else "",
                "pos": self.combo_logo_pos.currentText(),
                "opacity": self.slider_logo_opacity.value() / 100.0,
                "scale": self.slider_logo_scale.value() / 100.0,
                "move": self.combo_logo_move.currentText()
            },
            "bgm": {
                "path": self.bgm_path if self.chk_bgm.isChecked() else "",
                "vol": self.slider_bgm_vol.value() / 100.0
            },
            "enable_sub": self.chk_enable_sub.isChecked(),
            "color_eq": {
                "brightness": self.slider_bright.value() / 100.0,
                "contrast": 1.0 + (self.slider_contrast.value() / 100.0),
                "saturation": 1.0 + (self.slider_saturation.value() / 100.0)
            },
            "overlay": {
                "enabled": self.chk_overlay.isChecked(),
                "path": self.overlay_path,
                "opacity": self.slider_overlay_op.value() / 100.0
            }
        }
        
        self.worker_batch = WorkerBatch(
            video_paths=videos,
            config=self.config,
            sub_margin_v=self.margin_slider.value(),
            use_blur=self.chk_blur.isChecked(),
            blur_box={
                "x_pct": self.slider_x.value() / 100.0,
                "y_pct": self.slider_y.value() / 100.0,
                "w_pct": self.slider_w.value() / 100.0,
                "h_pct": self.slider_h.value() / 100.0
            },
            out_dir=out_folder,
            font_size=self.spin_font_size.value(),
            font_color=self.combo_font_color.currentText(),
            outline_color=self.combo_outline_color.currentText(),
            outline_width=self.spin_outline.value(),
            adv_config=adv_config
        )
        
        self.worker_batch.progress.connect(self.update_progress)
        self.worker_batch.log.connect(self.append_log)
        self.worker_batch.video_status.connect(self.update_batch_status)
        self.worker_batch.batch_done.connect(self.batch_finished)
        self.worker_batch.start()
        
    def update_batch_status(self, path, status, note):
        for row in range(self.batch_table.rowCount()):
            if self.batch_table.item(row, 1).text() == os.path.basename(path):
                self.batch_table.setItem(row, 2, QTableWidgetItem(status))
                self.batch_table.setItem(row, 3, QTableWidgetItem(note))
                
                # Màu sắc
                color = "#CDD6F4"
                if status == "Thành công": color = "#A6E3A1"
                elif status == "Lỗi": color = "#F38BA8"
                elif status == "Đang xử lý": color = "#F9E2AF"
                
                self.batch_table.item(row, 2).setForeground(QColor(color))
                break
                
    def batch_finished(self, success):
        self.btn_run_step1.setEnabled(True)
        self.btn_stop_step1.hide()

        self.btn_batch_config.setEnabled(True)
        if success:
            msg = QMessageBox(self)
            msg.setWindowTitle("Hoàn tất!")
            msg.setText("Đã xử lý xong toàn bộ danh sách Batch!")
            msg.setIcon(QMessageBox.Icon.Information)
            
            btn_open_dir = msg.addButton("📁 Mở Thư Mục Output", QMessageBox.ButtonRole.ActionRole)
            btn_ok = msg.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            
            msg.exec()
            if msg.clickedButton() == btn_open_dir:
                out_dir = self.batch_out_input.text().strip()
                if out_dir and os.path.exists(out_dir):
                    os.startfile(out_dir)
            
    def on_demucs_changed(self, state):
        if state == 2: # Checked
            if hasattr(self, 'bg_vol_slider') and self.bg_vol_slider.value() < 30:
                self.bg_vol_slider.setValue(60)
                self.append_log("💡 Đã tự động tăng [Âm lượng gốc] lên 60% để nghe rõ nhạc nền Demucs.")
                
    def play_demo_voice(self):
        self.save_config(silent=True)
        self.btn_test_voice.setText("Đang tải...")
        self.btn_test_voice.setEnabled(False)
        QApplication.processEvents() # Cập nhật UI
        
        try:
            from core.tts_engine import generate_demo_voice, VOICE_MAP
            voice_display = self.voice_cb.currentText()
            voice = VOICE_MAP.get(voice_display, "tiktok:BV074_streaming")
            tiktok_id = self.tiktok_id.text()
            current_speed = self.spin_tts_speed.value()
            
            demo_file = generate_demo_voice(voice, speed_rate=current_speed, tiktok_session_id=tiktok_id)
            if demo_file and os.path.exists(demo_file):
                import winsound
                # winsound.PlaySound only works with .wav, but edge-tts saves as mp3 usually.
                # Since edge-tts defaults to mp3, we might need to convert or just use os.startfile
                if demo_file.endswith(".wav"):
                    winsound.PlaySound(demo_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
                else:
                    # os.startfile sẽ mở bằng trình phát nhạc mặc định của Windows (nhanh nhất)
                    os.startfile(os.path.abspath(demo_file))
            else:
                QMessageBox.warning(self, "Lỗi", "Không thể tạo giọng đọc mẫu. Hãy kiểm tra API Key hoặc mạng.")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Lỗi khi phát thử giọng: {str(e)}")
        finally:
            self.btn_test_voice.setText("🔊 Nghe thử")
            self.btn_test_voice.setEnabled(True)

    def browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Logo", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.logo_path = path
            self.lbl_logo_path.setText(os.path.basename(path))
            self.chk_logo.setChecked(True)
            
    def browse_bgm(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Nhạc Nền", "", "Audio (*.mp3 *.wav *.m4a)")
        if path:
            self.bgm_path = path
            self.lbl_bgm_path.setText(os.path.basename(path))
            self.chk_bgm.setChecked(True)

    def browse_overlay(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn Lớp Phủ", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.overlay_path = path
            self.lbl_overlay_path.setText(os.path.basename(path))
            self.chk_overlay.setChecked(True)

    def export_srt(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Trống", "Không có dữ liệu phụ đề để xuất!")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Xuất file SRT", "", "Phụ đề (*.srt)")
        if path:
            try:
                with open(path, "w", encoding="utf-8-sig") as f:
                    for row in range(self.table.rowCount()):
                        idx = self.table.item(row, 0).text()
                        ts = self.table.item(row, 1).text()
                        txt = self.table.item(row, 2).text()
                        f.write(f"{idx}\n{ts}\n{txt}\n\n")
                QMessageBox.information(self, "Thành công", f"Đã xuất phụ đề ra:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Lỗi khi xuất: {str(e)}")

    def import_srt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file SRT", "", "Phụ đề (*.srt)")
        if path:
            try:
                from core.translator import parse_srt
                subs = parse_srt(path)
                
                # --- AUTO-TRIM DURATION (CHỐNG DÔI PHỤ ĐỀ) ---
                for sub in subs:
                    ts = sub['timestamp']
                    txt = sub['text']
                    import re
                    ts_match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', ts)
                    if ts_match:
                        start_str, end_str = ts_match.groups()
                        
                        def parse_time(ts_str):
                            h, m, s_ms = ts_str.split(':')
                            s, ms = s_ms.replace('.', ',').split(',')
                            return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0
                            
                        def format_time(seconds):
                            h = int(seconds // 3600)
                            m = int((seconds % 3600) // 60)
                            s = int(seconds % 60)
                            ms = int((seconds - int(seconds)) * 1000)
                            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
                            
                        start_sec = parse_time(start_str)
                        end_sec = parse_time(end_str)
                        duration = end_sec - start_sec
                        
                        # Ước lượng thời gian tối đa dựa trên độ dài (ký tự Trung hoặc số từ Anh/Việt)
                        is_asian = any('\u4e00' <= c <= '\u9fff' for c in txt)
                        length = len(txt) if is_asian else len(txt.split())
                        
                        # Cho phép tối đa 0.4s mỗi chữ + 2s dư dả (Max 7 giây cho 1 câu thông thường)
                        max_allowed = min(7.5, length * 0.4 + 2.0)
                        
                        # Cắt bớt phần đuôi dôi ra nếu dài bất thường
                        if duration > max_allowed and duration > 3.0:
                            new_end_sec = start_sec + max_allowed
                            sub['timestamp'] = f"{format_time(start_sec)} --> {format_time(new_end_sec)}"

                self.table.setRowCount(0)
                for i, sub in enumerate(subs):
                    self.table.insertRow(i)
                    self.table.setItem(i, 0, QTableWidgetItem(str(sub['index'])))
                    self.table.setItem(i, 1, QTableWidgetItem(sub['timestamp']))
                    self.table.setItem(i, 2, QTableWidgetItem(sub['text']))
                    
                    self.table.item(i, 0).setFlags(Qt.ItemFlag.ItemIsEnabled)
                QMessageBox.information(self, "Thành công", f"Đã nạp {len(subs)} dòng phụ đề!\n(Đã tự động cắt bớt các khoảng thời gian bị kéo dài bất thường)")
                self.update_preview()
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Lỗi nạp file: {str(e)}")

    def paste_srt(self):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        
        if not text or "-->" not in text:
            QMessageBox.warning(self, "Lỗi", "Dữ liệu trong Clipboard không phải là định dạng SRT hợp lệ (thiếu '-->')!")
            return
            
        try:
            import re
            content = text.replace('\r\n', '\n')
            blocks = re.split(r'\n{2,}', content.strip())
            subs = []
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 2:
                    index = lines[0].strip()
                    ts_line = lines[1].strip()
                    ts_match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})', ts_line)
                    if ts_match:
                        timestamp = ts_match.group(1)
                        extra_text = ts_line[ts_match.end():].strip()
                        text_parts = []
                        if extra_text:
                            text_parts.append(extra_text)
                        if len(lines) > 2:
                            text_parts.append(" ".join(lines[2:]).strip())
                        sub_text = " ".join(text_parts).strip()
                        sub_text = re.sub(r"\s+", " ", sub_text)
                        subs.append({'index': index, 'timestamp': timestamp, 'text': sub_text})
                    
            if len(subs) == 0:
                QMessageBox.warning(self, "Lỗi", "Không thể đọc được phụ đề từ Clipboard!")
                return
                
            # --- AUTO-TRIM DURATION (CHỐNG DÔI PHỤ ĐỀ) ---
            for sub in subs:
                ts = sub['timestamp']
                txt = sub['text']
                ts_match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', ts)
                if ts_match:
                    start_str, end_str = ts_match.groups()
                    def parse_time(ts_str):
                        h, m, s_ms = ts_str.split(':')
                        s, ms = s_ms.replace('.', ',').split(',')
                        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0
                    def format_time(seconds):
                        h = int(seconds // 3600)
                        m = int((seconds % 3600) // 60)
                        s = int(seconds % 60)
                        ms = int((seconds - int(seconds)) * 1000)
                        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
                        
                    start_sec = parse_time(start_str)
                    end_sec = parse_time(end_str)
                    duration = end_sec - start_sec
                    
                    is_asian = any('\u4e00' <= c <= '\u9fff' for c in txt)
                    length = len(txt) if is_asian else len(txt.split())
                    max_allowed = min(7.5, length * 0.4 + 2.0)
                    
                    if duration > max_allowed and duration > 3.0:
                        new_end_sec = start_sec + max_allowed
                        sub['timestamp'] = f"{format_time(start_sec)} --> {format_time(new_end_sec)}"
                
            self.table.setRowCount(0)
            for i, sub in enumerate(subs):
                self.table.insertRow(i)
                from PyQt6.QtWidgets import QTableWidgetItem
                self.table.setItem(i, 0, QTableWidgetItem(str(sub['index'])))
                self.table.setItem(i, 1, QTableWidgetItem(sub['timestamp']))
                self.table.setItem(i, 2, QTableWidgetItem(sub['text']))
                
                self.table.item(i, 0).setFlags(Qt.ItemFlag.ItemIsEnabled)
            QMessageBox.information(self, "Thành công", f"Đã dán {len(subs)} dòng phụ đề từ Clipboard!\n(Đã tự động cắt bớt các khoảng thời gian bị kéo dài bất thường)")
            self.update_preview()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi dán SRT: {str(e)}")

    def show_srt_context_menu(self, pos):
        menu = QMenu(self.table)
        action_delete = menu.addAction("🗑️ Xoá các dòng đã chọn")
        action_clear_text = menu.addAction("🧹 Xoá trống nội dung (Giữ thời gian)")
        
        action = menu.exec(self.table.mapToGlobal(pos))
        
        if action == action_delete:
            self.delete_selected_srt_rows()
        elif action == action_clear_text:
            self.clear_selected_srt_text()

    def delete_selected_srt_rows(self):
        rows = sorted(list(set([idx.row() for idx in self.table.selectedIndexes()])), reverse=True)
        if not rows:
            return
        # Hỏi xác nhận
        reply = QMessageBox.question(self, "Xác nhận xoá", f"Bạn có chắc muốn xoá {len(rows)} dòng phụ đề này?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for row in rows:
                self.table.removeRow(row)
            self.update_preview()

    def clear_selected_srt_text(self):
        rows = list(set([idx.row() for idx in self.table.selectedIndexes()]))
        for row in rows:
            self.table.setItem(row, 2, QTableWidgetItem("(không dịch)"))
        self.update_preview()

    def start_step3(self):
        # Nếu đang ở chế độ Batch, nút này chỉ có chức năng lưu và quay lại Bước 1
        if self.combo_mode.currentIndex() == 1:
            self.save_config(silent=True)
            self.stack.setCurrentIndex(0)
            return
            
        self.save_config(silent=True)
        self.btn_render.setEnabled(False)
        self.btn_stop_step3.show()
        
        # Lưu lại bảng ra file temp\xxx_translated.srt
        srt_path = os.path.splitext(self.current_video)[0] + "_translated.srt"
        with open(srt_path, "w", encoding="utf-8-sig") as f:
            for row in range(self.table.rowCount()):
                idx = self.table.item(row, 0).text()
                ts = self.table.item(row, 1).text()
                txt = self.table.item(row, 2).text()
                f.write(f"{idx}\n{ts}\n{txt}\n\n")
                
        self.stack.setCurrentIndex(0) # Quay lại màn hình 1 để xem log
        self.terminal.clear()
        
        vid_w = getattr(self, 'current_video_width', 1080)
        vid_h = getattr(self, 'current_video_height', 1920)
        
        blur_box_dict = {
            "x": int((self.slider_x.value() / 100.0) * vid_w),
            "y": int((self.slider_y.value() / 100.0) * vid_h),
            "w": int((self.slider_w.value() / 100.0) * vid_w),
            "h": int((self.slider_h.value() / 100.0) * vid_h)
        }
        
        # Đóng gói cấu hình Nâng cao
        adv_config = {
            "enable_sub": self.chk_enable_sub.isChecked(),
            "render_hw": self.combo_render_hw.currentText() if hasattr(self, 'combo_render_hw') else "Tự động quét GPU (Khuyên dùng)",
            "color_eq": {
                "brightness": self.slider_bright.value() / 100.0,
                "contrast": 1.0 + (self.slider_contrast.value() / 100.0),
                "saturation": 1.0 + (self.slider_saturation.value() / 100.0)
            },
            "overlay": {
                "path": self.overlay_path if self.chk_overlay.isChecked() else "",
                "opacity": self.slider_overlay_op.value() / 100.0
            },
            "aspect_ratio": self.combo_aspect_ratio.currentText(),
            "speed": self.spin_speed.value() if self.chk_speed.isChecked() else 1.0,
            "flip": self.chk_flip.isChecked(),
            "noise": {
                "enabled": self.chk_noise.isChecked(),
                "strength": self.spin_noise.value()
            },
            "fake_iphone": self.chk_fake_iphone.isChecked(),
            "round": {
                "enabled": self.chk_round.isChecked(),
                "radius": self.spin_round.value()
            },
            "sub_border_style": 3 if getattr(self, 'combo_border_style', None) and self.combo_border_style.currentText() == "Khung nền mờ (Opaque Box)" else 1,
            "zoom": {
                "percent": self.spin_zoom.value() if self.chk_zoom.isChecked() else 0,
                "mode": self.combo_zoom_mode.currentText(),
                "static_time": self.spin_zoom_static.value(),
                "dyn_time": self.spin_zoom_dyn.value()
            },
            "logo": {
                "path": self.logo_path if self.chk_logo.isChecked() else "",
                "pos": self.combo_logo_pos.currentText(),
                "opacity": self.slider_logo_opacity.value() / 100.0,
                "scale": self.slider_logo_scale.value() / 100.0,
                "move": self.combo_logo_move.currentText()
            },
            "bgm": {
                "path": self.bgm_path if self.chk_bgm.isChecked() else "",
                "vol": self.slider_bgm_vol.value() / 100.0
            }
        }
        
        # Chuyển đổi phần trăm sang Pixel thực tế dựa trên chiều cao video
        margin_px = int((self.margin_slider.value() / 100.0) * getattr(self, 'current_video_height', 1920))
        
        self.worker3 = WorkerStep3(
            srt_path=srt_path,
            video_path=self.current_video,
            config=self.config,
            sub_margin_v=margin_px,
            use_blur=self.chk_blur.isChecked(),
            blur_box=blur_box_dict,
            overwrite=self.chk_overwrite.isChecked(),
            out_dir=self.out_dir_input.text(),
            font_size=self.spin_font_size.value(),
            font_color=self.combo_font_color.currentText(),
            outline_color=self.combo_outline_color.currentText(),
            outline_width=self.spin_outline.value(),
            adv_config=adv_config,
            base_audio_path=getattr(self, "current_bgm_path", "")
        )
        self.worker3.progress.connect(self.update_progress)
        self.worker3.log.connect(self.append_log)
        self.worker3.work_done.connect(self.step3_done)
        self.worker3.start()
        
    def stop_processing(self):
        self.append_log("🛑 Đang dọn dẹp và ép dừng tiến trình...")
        if hasattr(self, 'worker1') and self.worker1 and self.worker1.isRunning():
            self.worker1.terminate()
            self.worker1.wait()
        if hasattr(self, 'worker_batch') and self.worker_batch and self.worker_batch.isRunning():
            self.worker_batch.terminate()
            self.worker_batch.wait()
        if hasattr(self, 'worker3') and self.worker3 and self.worker3.isRunning():
            self.worker3.terminate()
            self.worker3.wait()
            
        try:
            # Ép tắt các process con đang chạy ngầm (ffmpeg, demucs)
            os.system("taskkill /F /IM ffmpeg.exe /T >nul 2>&1")
        except:
            pass
            
        self.append_log("✅ Đã dừng thành công!")
        self.btn_run_step1.setEnabled(True)
        self.btn_stop_step1.hide()
        self.btn_render.setEnabled(True)
        self.btn_stop_step3.hide()
        if self.combo_mode.currentIndex() == 1:
            self.btn_batch_config.setEnabled(True)
            


        
    def closeEvent(self, event):
        reply = QMessageBox.question(self, "Xác nhận Thoát", "Bạn có chắc chắn muốn thoát ứng dụng?\n(Mọi tiến trình đang chạy sẽ bị huỷ)", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.stop_processing()
            os._exit(0)
        else:
            event.ignore()
        
    def step3_done(self, success, out_path):
        self.btn_render.setEnabled(True)
        self.btn_stop_step3.hide()
        if success:
            msg = QMessageBox(self)
            msg.setWindowTitle("Hoàn tất!")
            msg.setText(f"Video đã xuất thành công ra:\n{out_path}")
            msg.setIcon(QMessageBox.Icon.Information)
            
            btn_open_vid = msg.addButton("▶️ Mở Video", QMessageBox.ButtonRole.ActionRole)
            btn_open_dir = msg.addButton("📁 Mở Thư Mục", QMessageBox.ButtonRole.ActionRole)
            btn_ok = msg.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
            
            msg.exec()
            
            if msg.clickedButton() == btn_open_vid:
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(out_path)))
            elif msg.clickedButton() == btn_open_dir:
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(os.path.abspath(out_path))))
        else:
            QMessageBox.critical(self, "Lỗi", "Render Bước 3 thất bại!")
            
    def on_video_frame_changed(self, frame):
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

    def on_box_drawn(self, x, y, w, h):
        """Được gọi khi người dùng vẽ xong hộp trên ImageLabel"""
        self.slider_x.blockSignals(True)
        self.slider_y.blockSignals(True)
        self.slider_w.blockSignals(True)
        self.slider_h.blockSignals(True)
        
        self.slider_x.setValue(x)
        self.slider_y.setValue(y)
        self.slider_w.setValue(w)
        self.slider_h.setValue(h)
        
        self.slider_x.blockSignals(False)
        self.slider_y.blockSignals(False)
        self.slider_w.blockSignals(False)
        self.slider_h.blockSignals(False)
        
        self.update_preview()

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = 'autovietsub.pro.desktop.v1'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
            
    app = QApplication(sys.argv)
    icon_path = resource_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = AutoVietsubApp()
    window.show()
    sys.exit(app.exec())
