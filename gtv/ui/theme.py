"""浅色 QSS 主题与调色板。"""
from __future__ import annotations

PALETTE = {
    "bg": "#F5F6F8",
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

QSS = f"""
* {{ font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif; }}
QWidget#root, QMainWindow {{ background: {PALETTE['bg']}; color: {PALETTE['text']}; }}
QToolTip {{ background:#FFFFFF; color:{PALETTE['text']}; border:1px solid {PALETTE['border']}; padding:4px 8px; }}

/* ---- 面板 ---- */
QFrame#panel {{
    background: {PALETTE['panel']};
    border: 1px solid {PALETTE['border']};
    border-radius: 12px;
}}
QFrame#side {{
    background: {PALETTE['panel']};
    border-right: 1px solid {PALETTE['border']};
}}

/* ---- 输入 ---- */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
    background: #FFFFFF;
    border: 1px solid {PALETTE['border']};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {PALETTE['accent_soft']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border-color: {PALETTE['accent']};
}}
QComboBox QAbstractItemView {{
    border:1px solid {PALETTE['border']}; border-radius:8px; background:#fff;
    selection-background-color:{PALETTE['accent_soft']};
}}

/* ---- 按钮 ---- */
QPushButton {{
    background: #FFFFFF; color:{PALETTE['text']};
    border: 1px solid {PALETTE['border']};
    border-radius: 8px; padding: 7px 14px;
}}
QPushButton:hover {{ background:{PALETTE['hover']}; border-color:#CBD2DC; }}
QPushButton:pressed {{ background:#E7EBF2; }}
QPushButton:disabled {{ color:#A6ADB8; background:#F4F5F7; }}
QPushButton#primary {{
    background:{PALETTE['accent']}; color:#fff; border:1px solid {PALETTE['accent']}; font-weight:600;
}}
QPushButton#primary:hover {{ background:#275ED4; }}
QPushButton#danger {{ color:{PALETTE['danger']}; border-color:#F0BEBE; }}
QPushButton#danger:hover {{ background:#FDF1F1; }}
QPushButton#ghost {{ border:1px solid transparent; background:transparent; padding:4px 8px; }}
QPushButton#ghost:hover {{ background:{PALETTE['hover']}; }}

/* ---- 列表 ---- */
QListWidget {{ background:transparent; border:none; outline:none; }}
QListWidget::item {{ padding:8px 12px; border-radius:8px; margin:1px 6px; }}
QListWidget::item:hover {{ background:{PALETTE['hover']}; }}
QListWidget::item:selected {{ background:{PALETTE['selected']}; color:{PALETTE['accent']}; font-weight:600; }}

/* ---- 表格 ---- */
QTableWidget, QTableView {{
    background:#fff; alternate-background-color:#FAFBFC;
    border:1px solid {PALETTE['border']}; border-radius:10px;
    gridline-color:{PALETTE['border']}; outline:none;
}}
QHeaderView::section {{
    background:#F7F8FA; border:none; border-right:1px solid {PALETTE['border']};
    border-bottom:1px solid {PALETTE['border']}; padding:7px 8px; font-weight:600;
}}

/* ---- 滚动条 ---- */
QScrollArea, QScrollArea > QWidget > QWidget {{ background:transparent; border:none; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:0; }}
QScrollBar::handle:vertical {{ background:#D3D8E0; border-radius:5px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:#BCC3CE; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; }}
QScrollBar:horizontal {{ background:transparent; height:10px; }}
QScrollBar::handle:horizontal {{ background:#D3D8E0; border-radius:5px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}

/* ---- 分割 / 状态 ---- */
QSplitter::handle {{ background:{PALETTE['border']}; }}
QSplitter::handle:horizontal {{ width:1px; }}
QStatusBar {{ background:{PALETTE['panel']}; border-top:1px solid {PALETTE['border']}; color:{PALETTE['muted']}; }}
QTabWidget::pane {{ border:1px solid {PALETTE['border']}; border-radius:10px; background:#fff; top:-1px; }}
QTabBar::tab {{ padding:8px 16px; margin-right:4px; border:none; background:transparent; }}
QTabBar::tab:selected {{ background:{PALETTE['accent_soft']}; border-radius:8px; color:{PALETTE['accent']}; font-weight:600; }}
QProgressBar {{ border:1px solid {PALETTE['border']}; border-radius:8px; background:#fff; height:18px; text-align:center; }}
QProgressBar::chunk {{ background:{PALETTE['accent']}; border-radius:7px; }}
QCheckBox::indicator {{ width:16px; height:16px; border-radius:4px; border:1px solid {PALETTE['border']}; background:#fff; }}
QCheckBox::indicator:checked {{ background:{PALETTE['accent']}; border-color:{PALETTE['accent']}; }}
QMenu {{ background:#fff; border:1px solid {PALETTE['border']}; border-radius:10px; padding:6px; }}
QMenu::item {{ padding:7px 22px; border-radius:6px; }}
QMenu::item:selected {{ background:{PALETTE['accent_soft']}; color:{PALETTE['accent']}; }}
QLabel#muted {{ color:{PALETTE['muted']}; }}
QLabel#chip {{
    background:{PALETTE['chip']}; color:#46505F; border-radius:10px; padding:3px 9px;
}}
QLabel#warnbox {{
    background:#FFF6E6; color:{PALETTE['warn']}; border:1px solid #F3DCA8;
    border-radius:10px; padding:8px 10px;
}}
"""


def style_sheet() -> str:
    return QSS
