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
                             QTextEdit, QSlider, QCheckBox, QFileDialog, QMessageBox, QGroupBox, QFormLayout, QSpinBox, QTabWidget, QDoubleSpinBox, QScrollArea)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor
from PIL import Image, ImageDraw

from style import MODERN_QSS
from ui_workers import WorkerStep1, WorkerStep3
from core.video_processor import extract_preview_frame
import sys
from PyQt6.QtCore import pyqtSignal, QObject

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
        
        # Fixed device to CPU
        self.device_type = "cpu"
        
        stt_layout.addRow("Phần cứng:", QLabel("CPU (Đã tối ưu)"))
        sidebar_layout.addWidget(group_stt)
        
        # Group Dịch
        group_trans = QGroupBox("Dịch thuật (AI)")
        trans_layout = QFormLayout(group_trans)
        
        self.model_cb = QComboBox()
        self.model_cb.addItems(["Gemini 2.0 Flash (Khuyên dùng)", "Groq (Llama 3.3 - Nhanh)", "Groq (Qwen 3 32B - Dịch Tiếng Trung Tốt)"])
        self.model_cb.setCurrentText(self.config.get("translation_model", "Gemini 2.0 Flash (Khuyên dùng)"))
        
        self.target_lang_cb = QComboBox()
        self.target_lang_cb.addItems(["Tiếng Việt", "Tiếng Anh", "Tiếng Trung", "Tiếng Hàn", "Tiếng Nhật", "Tiếng Thái"])
        self.target_lang_cb.setCurrentText(self.config.get("target_lang", "Tiếng Việt"))
        
        self.gemini_key = QLineEdit(self.config.get("gemini_api_key", ""))
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.groq_key = QLineEdit(self.config.get("groq_api_key", ""))
        self.groq_key.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.prompt_input = QTextEdit(self.config.get("gemini_prompt", "Giọng điệu review phim, kịch tính, hấp dẫn"))
        self.prompt_input.setPlaceholderText("VD: Dịch nhí nhảnh, GenZ...")
        self.prompt_input.setMaximumHeight(60)
        
        trans_layout.addRow("Model:", self.model_cb)
        trans_layout.addRow("Ngôn ngữ đích:", self.target_lang_cb)
        trans_layout.addRow("Phong cách:", self.prompt_input)
        trans_layout.addRow("Gemini Key:", self.gemini_key)
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
        self.spin_tts_threads.setRange(1, 5)
        self.spin_tts_threads.setValue(int(self.config.get("tts_threads", 2)))
        self.spin_tts_threads.setToolTip("Tăng số luồng để tải TTS nhanh hơn (Tối đa 5)")
        
        h_voice = QHBoxLayout()
        h_voice.addWidget(self.voice_cb)
        self.btn_test_voice = QPushButton("▶️ Test")
        self.btn_test_voice.clicked.connect(self.play_demo_voice)
        h_voice.addWidget(self.btn_test_voice)
        tts_layout.addRow("Voice:", h_voice)
        tts_layout.addRow("TikTok ID:", self.tiktok_id)
        tts_layout.addRow("Âm lượng gốc:", self.bg_vol_slider)
        tts_layout.addRow("Số luồng (Speed):", self.spin_tts_threads)
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
        
        # Stacked Widget cho các bước
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        
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
        
        h_run = QHBoxLayout()
        self.btn_run_step1 = QPushButton("🚀 BẮT ĐẦU XỬ LÝ (BƯỚC 1)")
        self.btn_run_step1.setObjectName("btn_primary")
        self.btn_run_step1.clicked.connect(self.start_processing)
        
        h_run.addWidget(self.btn_run_step1)
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
        
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Timestamp (Giữ nguyên)", "Nội dung Subtitle (Được sửa)"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        v_sub.addWidget(self.table)
        
        self.tabs.addTab(tab_sub, "✍️ Chỉnh sửa Phụ đề")
        
        # --- TAB 2: BLUR & VỊ TRÍ ---
        tab_blur = QWidget()
        v_blur = QVBoxLayout(tab_blur)
        
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
        
        v_blur.addLayout(grid_blur)
        
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
        
        v_blur.addLayout(h_format)
        
        # Connect tín hiệu
        self.spin_font_size.valueChanged.connect(self.update_preview)
        self.combo_font_color.currentTextChanged.connect(self.update_preview)
        self.combo_outline_color.currentTextChanged.connect(self.update_preview)
        self.spin_outline.valueChanged.connect(self.update_preview)
        
        # Thêm khu vực Preview Blur
        h2_preview = QHBoxLayout()
        self.btn_preview = QPushButton("🖼️ Xem trước khung che mờ")
        self.btn_preview.clicked.connect(self.update_preview)
        self.preview_lbl = QLabel("Khung Preview sẽ hiển thị tại đây")
        self.preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_lbl.setStyleSheet("border: 1px dashed #45475A;")
        h2_preview.addWidget(self.btn_preview)
        h2_preview.addWidget(self.preview_lbl)
        v_blur.addLayout(h2_preview)
        
        self.tabs.addTab(tab_blur, "🌫️ Cài đặt Blur & Vị trí Sub")
        
        # --- TAB 3: NÂNG CAO ---
        tab_adv = QWidget()
        v_adv = QVBoxLayout(tab_adv)
        
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
        
        h_speed = QHBoxLayout()
        self.chk_speed = QCheckBox("Tăng tốc")
        self.spin_speed = QDoubleSpinBox(); self.spin_speed.setRange(1.0, 3.0); self.spin_speed.setSingleStep(0.05); self.spin_speed.setValue(1.1)
        h_speed.addWidget(self.chk_speed); h_speed.addWidget(self.spin_speed)
        v_fx.addRow("Tốc độ (x):", h_speed)
        
        self.chk_flip = QCheckBox("Bật Lật ngang Video")
        v_fx.addRow("Lật Video:", self.chk_flip)
        
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
        v_logo.addRow("Hiệu ứng Logo:", self.combo_logo_move)
        
        h_logo_sz = QHBoxLayout()
        self.slider_logo_scale = QSlider(Qt.Orientation.Horizontal)
        self.slider_logo_scale.setRange(5, 100); self.slider_logo_scale.setValue(20) # 20% width video
        h_logo_sz.addWidget(self.slider_logo_scale)
        v_logo.addRow("Kích thước Logo:", h_logo_sz)
        
        h_logo_op = QHBoxLayout()
        self.slider_logo_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_logo_opacity.setRange(1, 100); self.slider_logo_opacity.setValue(80)
        h_logo_op.addWidget(self.slider_logo_opacity)
        v_logo.addRow("Độ rõ Logo:", h_logo_op)
        
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
        self.chk_speed.setChecked(self.config.get("adv_speed_en", False))
        self.spin_speed.setValue(self.config.get("adv_speed_val", 1.1))
        self.chk_flip.setChecked(self.config.get("adv_flip", False))
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
        
        h_out = QHBoxLayout()
        self.out_dir_input = QLineEdit()
        self.out_dir_input.setPlaceholderText("Thư mục lưu video (Mặc định: Cùng thư mục video gốc)")
        self.out_dir_input.setReadOnly(True)
        btn_out_dir = QPushButton("📁 Chọn Nơi Lưu")
        btn_out_dir.clicked.connect(self.browse_out_dir)
        h_out.addWidget(self.out_dir_input)
        h_out.addWidget(btn_out_dir)
        v2.addLayout(h_out)
        
        h2_btns = QHBoxLayout()
        btn_back = QPushButton("⬅️ Quay lại")
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_render = QPushButton("🎥 Render Video Cuối (Bước 3)")
        self.btn_render.setObjectName("btn_primary")
        self.btn_render.clicked.connect(self.start_step3)
        h2_btns.addWidget(btn_back)
        h2_btns.addStretch()
        h2_btns.addWidget(self.btn_render)
        v2.addLayout(h2_btns)
        
        self.stack.addWidget(step2)
        
        # Thêm content vào main layout
        main_layout.addWidget(content_widget)

    def save_config(self, silent=False):
        self.config["device_type"] = self.device_type

        self.config["translation_model"] = self.model_cb.currentText()
        self.config["target_lang"] = self.target_lang_cb.currentText()
        self.config["gemini_prompt"] = self.prompt_input.toPlainText()
        self.config["gemini_api_key"] = self.gemini_key.text()
        self.config["groq_api_key"] = self.groq_key.text()
        self.config["voice"] = self.voice_cb.currentText()
        self.config["tiktok_session_id"] = self.tiktok_id.text()
        self.config["tts_threads"] = self.spin_tts_threads.value()
        self.config["bg_volume"] = self.bg_vol_slider.value() / 100.0
        
        try:
            # Lưu cài đặt Tab 2 & 3 (Dùng try-except để tránh lỗi khi các widget chưa khởi tạo xong)
            self.config["sub_font_size"] = self.spin_font_size.value()
            self.config["sub_font_color"] = self.combo_font_color.currentText()
            self.config["sub_outline_color"] = self.combo_outline_color.currentText()
            self.config["sub_outline_width"] = self.spin_outline.value()
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
            self.config["adv_speed_en"] = self.chk_speed.isChecked()
            self.config["adv_speed_val"] = self.spin_speed.value()
            self.config["adv_flip"] = self.chk_flip.isChecked()
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
            
            # Disable Tab Phụ đề (Step 2)
            self.tabs.setTabEnabled(0, False)
            self.tabs.setCurrentIndex(1)
            self.btn_render.setText("Lưu Cài Đặt Khung Hình & Quay Lại")
        else:
            self.lbl_input_title.setText("Thư mục/File đầu vào:")
            self.btn_browse.setText("📂 Chọn File")
            self.file_input.clear()
            self.file_input.setPlaceholderText("Đường dẫn file video...")
            for i in range(self.h_batch_out.count()):
                self.h_batch_out.itemAt(i).widget().hide()
            self.btn_batch_config.hide()
            self.btn_run_step1.setText("🚀 BẮT ĐẦU XỬ LÝ (BƯỚC 1)")
            self.batch_table.hide()
            
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

        self.worker1 = WorkerStep1(mode, val, self.config, overwrite=self.chk_overwrite.isChecked())
        self.worker1.progress.connect(self.update_progress)
        self.worker1.log.connect(self.append_log)
        self.worker1.work_done.connect(self.step1_done)
        self.worker1.start()
        
    def step1_done(self, success, video_path, subs_data, bgm_path=""):
        self.btn_run_step1.setEnabled(True)

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
            "speed": self.spin_speed.value() if self.chk_speed.isChecked() else 1.0,
            "flip": self.chk_flip.isChecked(),
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

        self.btn_batch_config.setEnabled(True)
        if success:
            QMessageBox.information(self, "Hoàn tất", "Đã xử lý xong toàn bộ danh sách Batch!")
            
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
            
            demo_file = generate_demo_voice(voice, tiktok_session_id=tiktok_id)
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

    def start_step3(self):
        # Nếu đang ở chế độ Batch, nút này chỉ có chức năng lưu và quay lại Bước 1
        if self.combo_mode.currentIndex() == 1:
            self.save_config(silent=True)
            self.stack.setCurrentIndex(0)
            return
            
        self.save_config(silent=True)
        self.btn_render.setEnabled(False)
        
        # Lưu lại bảng ra file temp\xxx_translated.srt
        srt_path = self.current_video.replace(".mp4", "_translated.srt")
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
            "color_eq": {
                "brightness": self.slider_bright.value() / 100.0,
                "contrast": 1.0 + (self.slider_contrast.value() / 100.0),
                "saturation": 1.0 + (self.slider_saturation.value() / 100.0)
            },
            "overlay": {
                "path": self.overlay_path if self.chk_overlay.isChecked() else "",
                "opacity": self.slider_overlay_op.value() / 100.0
            },
            "speed": self.spin_speed.value() if self.chk_speed.isChecked() else 1.0,
            "flip": self.chk_flip.isChecked(),
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
        self.append_log("🛑 Đang dọn dẹp và thoát ứng dụng...")
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
            


        
    def closeEvent(self, event):
        reply = QMessageBox.question(self, "Xác nhận Thoát", "Bạn có chắc chắn muốn thoát ứng dụng?\n(Mọi tiến trình đang chạy sẽ bị huỷ)", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.stop_processing()
            os._exit(0)
        else:
            event.ignore()
        
    def step3_done(self, success, out_path):
        self.btn_render.setEnabled(True)
        if success:
            QMessageBox.information(self, "Hoàn tất!", f"Video đã xuất thành công ra:\n{out_path}")
            os.startfile(os.path.dirname(os.path.abspath(out_path)))
        else:
            QMessageBox.critical(self, "Lỗi", "Render Bước 3 thất bại!")
            
    def update_preview(self):
        if not self.current_video: return
        self.preview_lbl.setText("Đang trích xuất ảnh...")
        
        try:
            preview_path = extract_preview_frame(self.current_video, output_dir="temp")
            if os.path.exists(preview_path):
                img = Image.open(preview_path)
                draw = ImageDraw.Draw(img)
                img_width, img_height = img.size
                self.current_video_width = img_width
                self.current_video_height = img_height # Lưu cho bước 3
                
                if self.chk_blur.isChecked():
                    x = int((self.slider_x.value() / 100.0) * img_width)
                    y = int((self.slider_y.value() / 100.0) * img_height)
                    w = int((self.slider_w.value() / 100.0) * img_width)
                    h = int((self.slider_h.value() / 100.0) * img_height)
                    draw.rectangle([x, y, x+w, y+h], outline="red", width=8)
                    
                # Lấy màu từ combo box
                color_map = {
                    "Trắng": "#FFFFFF", "Vàng": "#FFFF00", "Xanh Lơ": "#00FFFF", 
                    "Xanh Lá": "#00FF00", "Đỏ": "#FF0000", "Hồng": "#FF00FF", "Đen": "#000000"
                }
                font_color = color_map.get(self.combo_font_color.currentText(), "#FFFF00")
                outline_color = color_map.get(self.combo_outline_color.currentText(), "#000000")
                font_size = self.spin_font_size.value()
                outline_width = self.spin_outline.value()
                
                # Vẽ mô phỏng Subtitle bằng Text thật
                margin_px = int((self.margin_slider.value() / 100.0) * img_height)
                sub_y = img_height - margin_px - font_size
                if sub_y < 0: sub_y = 0
                
                try:
                    from PIL import ImageFont
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
                    
                sample_text = "Ăn núi thì núi, ăn biển thì biển"
                # Tính toạ độ X để căn giữa chữ
                try:
                    text_bbox = draw.textbbox((0, 0), sample_text, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                except:
                    text_width = font_size * 10 # Fallback
                
                text_x = (img_width - text_width) / 2
                
                draw.text(
                    (text_x, sub_y), 
                    sample_text, 
                    font=font, 
                    fill=font_color, 
                    stroke_width=outline_width, 
                    stroke_fill=outline_color
                )
                
                # Lưu tạm để QPixmap nạp
                temp_preview = os.path.join("temp", "preview_with_box.jpg")
                img.save(temp_preview)
                pixmap = QPixmap(temp_preview)
                    
                # Tính toán kích thước để hiển thị to hơn trên màn hình
                pixmap = pixmap.scaled(600, 500, Qt.AspectRatioMode.KeepAspectRatio)
                self.preview_lbl.setPixmap(pixmap)
        except Exception as e:
            self.preview_lbl.setText(f"Lỗi Preview: {e}")

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
