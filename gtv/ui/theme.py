"""浅色主题：QPalette（关键）+ QSS。

用户系统可能是深色模式：Qt 会继承系统深色调色板（白色文字），
导致"白底白字"。所以除了 QSS，还必须给 QApplication 强制安装一套
浅色 QPalette（见 light_palette()），双保险。
"""
from __future__ import annotations

PALETTE = {
    "bg": "#F3F5F8",
    "panel": "#FFFFFF",
    "border": "#E2E5EA",
    "text": "#1F2430",
    "muted": "#6B7280",
    "accent": "#2F6FEB",
    "accent_soft": "#E8F0FE",
    "danger": "#D64545",
    "warn": "#B26B00",
    "ok": "#2E9E5B",
    "chip": "#EEF1F5",
    "hover": "#F0F3F8",
    "selected": "#E7EFFD",
}


def light_palette():
    """浅色 QPalette：覆盖系统深色模式继承，保证所有原生控件文字可见。"""
    from PySide6.QtGui import QColor, QPalette

    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(PALETTE["bg"]))
    p.setColor(QPalette.ColorRole.WindowText, QColor(PALETTE["text"]))
    p.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor("#FAFBFC"))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(PALETTE["text"]))
    p.setColor(QPalette.ColorRole.Text, QColor(PALETTE["text"]))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#9AA3AF"))
    p.setColor(QPalette.ColorRole.Button, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(PALETTE["text"]))
    p.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.Link, QColor(PALETTE["accent"]))
    p.setColor(QPalette.ColorRole.LinkVisited, QColor(PALETTE["accent"]))
    p.setColor(QPalette.ColorRole.Highlight, QColor(PALETTE["accent"]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))

    g = QPalette.ColorGroup.Disabled
    p.setColor(g, QPalette.ColorRole.WindowText, QColor("#A6ADB8"))
    p.setColor(g, QPalette.ColorRole.Text, QColor("#A6ADB8"))
    p.setColor(g, QPalette.ColorRole.ButtonText, QColor("#A6ADB8"))
    return p


QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {PALETTE['text']};
}}
QWidget#root, QMainWindow {{ background: {PALETTE['bg']}; color: {PALETTE['text']}; }}
QToolTip {{
    background:#FFFFFF; color:{PALETTE['text']};
    border:1px solid {PALETTE['border']}; padding:4px 8px;
}}

/* ---- 面板 ---- */
QFrame#panel {{
    background: {PALETTE['panel']};
    border: 1px solid {PALETTE['border']};
    border-radius: 12px;
}}

/* ---- 文字基线 ---- */
QLabel {{ color: {PALETTE['text']}; background: transparent; }}
QLabel#muted {{ color: {PALETTE['muted']}; font-size: 12px; }}
QLabel#section {{
    color: {PALETTE['muted']}; font-size: 12px; font-weight: 600;
    letter-spacing: 1px;
}}
QLabel#chip {{
    background: {PALETTE['chip']}; color: #46505F;
    border-radius: 10px; padding: 3px 9px; font-size: 12px;
}}
QLabel#statusOK  {{ color: {PALETTE['ok']};   font-size: 12px; font-weight: 600; }}
QLabel#statusOff {{ color: #9AA3AF; font-size: 12px; }}
QLabel#warnbox {{
    background:#FFF6E6; color:{PALETTE['warn']}; border:1px solid #F3DCA8;
    border-radius:10px; padding:8px 10px; font-size: 12px;
}}
QLabel#titleBig {{ font-size: 17px; font-weight: 700; color: {PALETTE['text']}; }}
QLabel#titleSub {{ color: {PALETTE['muted']}; font-size: 12px; }}

/* ---- 输入框：白底深字（修复深色系统下白字白底） ---- */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background: #FFFFFF;
    color: {PALETTE['text']};
    border: 1px solid {PALETTE['border']};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {PALETTE['accent']};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {PALETTE['accent']};
    border-width: 1px;
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    background: #F4F5F7; color: #A6ADB8;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #6B7280;
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: #FFFFFF; color: {PALETTE['text']};
    border: 1px solid {PALETTE['border']}; border-radius: 8px;
    selection-background-color: {PALETTE['accent_soft']};
    selection-color: {PALETTE['accent']};
    outline: none; padding: 4px;
}}
QComboBox QAbstractItemView::item {{ min-height: 28px; padding: 4px 8px; border-radius: 6px; }}

/* ---- 按钮 ---- */
QPushButton {{
    background: #FFFFFF; color: {PALETTE['text']};
    border: 1px solid {PALETTE['border']};
    border-radius: 8px; padding: 7px 14px; font-size: 13px;
}}
QPushButton:hover {{ background:{PALETTE['hover']}; border-color:#CBD2DC; }}
QPushButton:pressed {{ background:#E7EBF2; }}
QPushButton:disabled {{ color:#A6ADB8; background:#F4F5F7; border-color:{PALETTE['border']}; }}
QPushButton#primary {{
    background:{PALETTE['accent']}; color:#FFFFFF;
    border:1px solid {PALETTE['accent']}; font-weight:600;
}}
QPushButton#primary:hover {{ background:#275ED4; }}
QPushButton#primary:disabled {{ background:#B9CDF5; color:#F2F6FF; border-color:#B9CDF5; }}
QPushButton#danger {{ color:{PALETTE['danger']}; border-color:#F0BEBE; }}
QPushButton#danger:hover {{ background:#FDF1F1; }}
QPushButton#ghost {{ border:1px solid transparent; background:transparent; padding:4px 8px; }}
QPushButton#ghost:hover {{ background:{PALETTE['hover']}; }}

/* ---- 单选 / 复选 ---- */
QRadioButton, QCheckBox {{ color: {PALETTE['text']}; spacing: 7px; background: transparent; }}
QRadioButton::indicator, QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid #C4CBD6; background: #FFFFFF;
}}
QRadioButton::indicator {{ border-radius: 8px; }}
QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
    background: {PALETTE['accent']}; border-color: {PALETTE['accent']};
}}
QRadioButton::indicator:checked {{
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 #FFFFFF, stop:0.45 #FFFFFF, stop:0.55 {PALETTE['accent']}, stop:1 {PALETTE['accent']});
}}
QCheckBox:disabled, QRadioButton:disabled {{ color: #A6ADB8; }}

/* ---- 列表 / 树 ---- */
QListWidget, QTreeWidget, QTreeView {{
    background: transparent; border: none; outline: none;
    color: {PALETTE['text']};
}}
QListWidget::item {{ padding:8px 12px; border-radius:8px; margin:1px 6px; color:{PALETTE['text']}; }}
QListWidget::item:hover {{ background:{PALETTE['hover']}; }}
QListWidget::item:selected {{ background:{PALETTE['selected']}; color:{PALETTE['accent']}; font-weight:600; }}
QTreeWidget::item {{ height: 26px; color: {PALETTE['text']}; }}
QTreeWidget::item:hover {{ background:{PALETTE['hover']}; border-radius:6px; }}
QTreeWidget::item:selected {{ background:{PALETTE['selected']}; color:{PALETTE['accent']}; border-radius:6px; }}
QTreeView::branch {{ background: transparent; }}

/* ---- 表格 ---- */
QTableWidget, QTableView {{
    background:#FFFFFF; color:{PALETTE['text']};
    alternate-background-color:#FAFBFC;
    border:1px solid {PALETTE['border']}; border-radius:10px;
    gridline-color:{PALETTE['border']}; outline:none;
}}
QTableWidget::item {{ padding: 4px 6px; color: {PALETTE['text']}; }}
QTableWidget::item:selected {{ background:{PALETTE['selected']}; color:{PALETTE['accent']}; }}
QHeaderView::section {{
    background:#F7F8FA; color:#46505F;
    border:none; border-right:1px solid {PALETTE['border']};
    border-bottom:1px solid {PALETTE['border']};
    padding:7px 8px; font-weight:600; font-size: 12px;
}}

/* ---- Tab ---- */
QTabWidget::pane {{ border:1px solid {PALETTE['border']}; border-radius:10px; background:#FFFFFF; top:-1px; }}
QTabBar::tab {{
    padding:8px 18px; margin-right:4px; border:none; background:transparent;
    color: {PALETTE['muted']}; font-size: 13px;
}}
QTabBar::tab:hover {{ color: {PALETTE['text']}; }}
QTabBar::tab:selected {{
    background:{PALETTE['accent_soft']}; border-radius:8px;
    color:{PALETTE['accent']}; font-weight:600;
}}

/* ---- 滚动条 ---- */
QScrollArea, QScrollArea > QWidget > QWidget {{ background:transparent; border:none; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:0; }}
QScrollBar::handle:vertical {{ background:#D3D8E0; border-radius:5px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:#BCC3CE; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ background:transparent; height:10px; }}
QScrollBar::handle:horizontal {{ background:#D3D8E0; border-radius:5px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}

/* ---- 其它 ---- */
QSplitter::handle {{ background:{PALETTE['border']}; }}
QSplitter::handle:horizontal {{ width:1px; }}
QStatusBar {{ background:{PALETTE['panel']}; border-top:1px solid {PALETTE['border']}; color:{PALETTE['muted']}; }}
QStatusBar QLabel {{ color: {PALETTE['muted']}; }}
QProgressBar {{ border:1px solid {PALETTE['border']}; border-radius:8px; background:#FFFFFF; height:18px; text-align:center; color:{PALETTE['text']}; }}
QProgressBar::chunk {{ background:{PALETTE['accent']}; border-radius:7px; }}
QMenu {{ background:#FFFFFF; color:{PALETTE['text']}; border:1px solid {PALETTE['border']}; border-radius:10px; padding:6px; }}
QMenu::item {{ padding:7px 22px; border-radius:6px; color:{PALETTE['text']}; }}
QMenu::item:selected {{ background:{PALETTE['accent_soft']}; color:{PALETTE['accent']}; }}
QMessageBox {{ background: #FFFFFF; }}
QMessageBox QLabel {{ color: {PALETTE['text']}; }}
QGroupBox {{
    border: 1px solid {PALETTE['border']}; border-radius: 10px;
    margin-top: 12px; color: {PALETTE['text']}; background: #FFFFFF;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {PALETTE['muted']}; }}
"""


def style_sheet() -> str:
    return QSS
