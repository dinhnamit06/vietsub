# Tệp chứa chuỗi Style (CSS dành cho Qt)
MODERN_QSS = """
/* Tổng quan cửa sổ */
QWidget {
    background-color: #1E1E2E; /* Nền tối hiện đại (Catppuccin Mocha) */
    color: #CDD6F4;
}

/* Sidebar bên trái */
QWidget#sidebar {
    background-color: #181825;
}

/* Khu vực trung tâm */
QWidget#central {
    background-color: #1E1E2E;
}

/* Label (Chữ) */
QLabel {
    color: #CDD6F4;
    font-family: 'Segoe UI', 'Roboto', sans-serif;
    font-size: 14px;
}
QLabel#title {
    font-size: 24px;
    font-weight: bold;
    color: #89B4FA; /* Xanh ngọc nổi bật */
    margin-bottom: 10px;
}
QLabel#header {
    font-size: 16px;
    font-weight: bold;
    color: #A6E3A1; /* Xanh lá */
    margin-top: 15px;
    margin-bottom: 5px;
}

/* Nút bấm (Button) */
QPushButton {
    background-color: #89B4FA;
    color: #11111B;
    border: none;
    border-radius: 8px;
    padding: 10px 15px;
    font-weight: bold;
    font-size: 14px;
}
QPushButton:hover {
    background-color: #74C7EC;
}
QPushButton:pressed {
    background-color: #89DCEB;
}
QPushButton#btn_primary {
    background-color: #F38BA8; /* Màu đỏ hồng nổi bật cho nút chính */
    color: #11111B;
    font-size: 16px;
    padding: 12px;
}
QPushButton#btn_primary:hover {
    background-color: #EBA0AC;
}

/* Ô nhập liệu (Input) */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 6px;
    padding: 8px;
    font-size: 14px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #89B4FA;
}

/* GroupBox */
QGroupBox {
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 15px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: #89B4FA;
    font-weight: bold;
    left: 10px;
}

/* Bảng (Table) */
QTableWidget {
    background-color: #181825;
    color: #CDD6F4;
    border: 1px solid #313244;
    gridline-color: #313244;
    border-radius: 8px;
    selection-background-color: #45475A;
}
QHeaderView::section {
    background-color: #313244;
    color: #CDD6F4;
    padding: 6px;
    border: none;
    font-weight: bold;
}

/* Thanh tiến trình (Progress Bar) */
QProgressBar {
    background-color: #313244;
    color: transparent;
    border: none;
    border-radius: 8px;
    text-align: center;
    height: 16px;
}
QProgressBar::chunk {
    background-color: #A6E3A1;
    border-radius: 8px;
}

/* Scrollbar */
QScrollBar:vertical {
    background-color: transparent;
    width: 6px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #45475A;
    border-radius: 6px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #585B70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Combobox (Dropdown) */
QComboBox {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 6px;
    padding: 8px;
}
QComboBox:hover {
    border: 1px solid #89B4FA;
}
QComboBox::drop-down {
    border: none;
}
"""
