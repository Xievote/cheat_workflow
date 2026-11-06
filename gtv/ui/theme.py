"""深色毛玻璃主题（参考 wemod.com 风格）：深蓝渐变底 + 半透明面板 + 蓝色主调。

设计要点：
* 背景在 QMainWindow / QDialog 上画对角深蓝渐变，营造氛围光；
* 面板用 rgba 半透明白叠加在渐变上，形成"类毛玻璃"层次；
* QPalette 同步为深色，防止系统浅色模式下出现"黑底黑字"；
* QComboBox / QSpinBox / QDoubleSpinBox 的箭头用 QPainter 绘制的真实 PNG，
  不依赖系统图元（修复 Windows 下箭头渲染成小方块/残缺的问题）；
* 主按钮渐变两端对白字均满足 WCAG AA（≥4.5:1），键盘焦点统一用 2px 亮蓝环。
"""
from __future__ import annotations

# 实色（供 QPalette / QColor 使用，不能写 rgba）
PALETTE = {
    "bg": "#0B1120",
    "panel": "#151D33",
    "border": "#27324E",
    "text": "#E7EDF8",
    "muted": "#A8B4CC",        # 次级文字：玻璃面板最亮处仍有 5.5:1（原 #8C99B4 仅 4.05:1）
    # 主色按 WCAG AA 压暗：白字对比 4.63:1（原 #3E8BFF 仅 3.49:1）
    "accent": "#2F6FE6",
    "accent2": "#6A45E8",      # 渐变终点：白字 5.79:1
    # hover / pressed 只压暗不提亮（提亮会让白字掉到 4:1 以下）
    "accent_hover": "#2A64D6",
    "accent2_hover": "#5F3BDD",
    "accent_bright": "#6FA8FF",  # 深底上的强调文字/图标（7.9:1）
    "accent_soft": "#1B2C4F",
    "focus": "#7FB0FF",        # 键盘焦点环
    "danger": "#FF8B8B",       # 深底上 5.1:1（原 #F16A6A 仅 3.91:1）
    "warn": "#E8A33D",
    "ok": "#34D399",
    "chip": "#1D2740",
    "hover": "rgba(255, 255, 255, 26)",
    "selected": "#204487",
}

# 半透明叠加层（叠在深蓝渐变上产生毛玻璃感）
GLASS = {
    "panel": "rgba(255, 255, 255, 18)",
    "panel_hover": "rgba(255, 255, 255, 30)",
    "border": "rgba(255, 255, 255, 30)",
    "border_strong": "rgba(255, 255, 255, 62)",
    "input": "rgba(8, 14, 30, 150)",
    "field": "rgba(255, 255, 255, 22)",
}


def app_palette():
    """深色 QPalette：与 QSS 同步，兜底所有原生控件（菜单/滚动条/弹窗）。"""
    from PySide6.QtGui import QColor, QPalette

    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(PALETTE["bg"]))
    p.setColor(QPalette.ColorRole.WindowText, QColor(PALETTE["text"]))
    p.setColor(QPalette.ColorRole.Base, QColor("#0D1426"))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor("#121B33"))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(PALETTE["accent"]))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.Text, QColor(PALETTE["text"]))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8593B0"))
    p.setColor(QPalette.ColorRole.Button, QColor("#1A2340"))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(PALETTE["text"]))
    p.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.Link, QColor(PALETTE["accent"]))
    p.setColor(QPalette.ColorRole.LinkVisited, QColor(PALETTE["accent2"]))
    p.setColor(QPalette.ColorRole.Highlight, QColor(PALETTE["accent"]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))

    g = QPalette.ColorGroup.Disabled
    p.setColor(g, QPalette.ColorRole.WindowText, QColor("#57647F"))
    p.setColor(g, QPalette.ColorRole.Text, QColor("#57647F"))
    p.setColor(g, QPalette.ColorRole.ButtonText, QColor("#57647F"))
    return p


# 兼容旧脚本（tools/smoke_ui.py 等）
light_palette = app_palette


def _arrow_images() -> dict[str, str]:
    """生成下拉/数字框箭头的小 PNG（QPainter 画真三角）。

    Qt 的 QSS 不支持 CSS 三角边框技巧（会画成实心方块），
    所以箭头必须用真实图片。图片缓存到应用数据目录，只生成一次。
    返回 {名称: url()} 字符串，直接嵌入 QSS。
    """
    from pathlib import Path

    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
    from PySide6.QtCore import Qt as _Qt

    from ..core import config

    cache = config.APP_DIR / "cache" / "arrows"
    cache.mkdir(parents=True, exist_ok=True)

    def draw(name: str, w: int, h: int, direction: str, color: str) -> str:
        path = cache / name
        if not path.exists():
            pm = QPixmap(w * 2, h * 2)  # 2x 渲染防锯齿，QSS 里缩到逻辑尺寸
            pm.fill(_Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            poly = QPainterPath()
            if direction == "down":
                poly.moveTo(QPointF(0, 0))
                poly.lineTo(QPointF(w * 2, 0))
                poly.lineTo(QPointF(w, h * 2))
            elif direction == "up":
                poly.moveTo(QPointF(0, h * 2))
                poly.lineTo(QPointF(w * 2, h * 2))
                poly.lineTo(QPointF(w, 0))
            else:  # left / right 备用
                poly.moveTo(QPointF(0, 0))
                poly.lineTo(QPointF(w * 2, h))
                poly.lineTo(QPointF(0, h * 2))
            poly.closeSubpath()
            p.fillPath(poly, QColor(color))
            p.end()
            pm.save(str(path))
        return f"url('{path.as_posix()}')"

    return {
        "down": draw("down.png", 10, 6, "down", "#9FB0D0"),
        "down_hover": draw("down_hover.png", 10, 6, "down", "#D5E1F7"),
        "up": draw("up.png", 8, 5, "up", "#9FB0D0"),
        "up_hover": draw("up_hover.png", 8, 5, "up", "#D5E1F7"),
        "check": _check_image(cache),
    }


def _check_image(cache) -> str:
    """复选框选中态的白色对勾（Qt 不会自动画 tick，只有纯色块无法判断状态）。"""
    from PySide6.QtCore import QPointF, Qt as _Qt
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

    path = cache / "check.png"
    if not path.exists():
        pm = QPixmap(14, 14)  # 与 indicator 内容区一致，避免被拉伸
        pm.fill(_Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#FFFFFF"))
        pen.setWidthF(2.2)
        pen.setCapStyle(_Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(_Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        qp = QPainterPath(QPointF(3.2, 7.2))
        qp.lineTo(QPointF(5.7, 10.0))
        qp.lineTo(QPointF(10.8, 3.8))
        p.drawPath(qp)
        p.end()
        pm.save(str(path))
    return f"url('{path.as_posix()}')"


QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {PALETTE['text']};
}}QWidget#root, QMainWindow {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0A0F1F, stop:0.45 #0E1830, stop:1 #13294F);
}}
QDialog {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0C1226, stop:1 #14203F);
}}
QToolTip {{
    background:{PALETTE['accent']}; color:#FFFFFF;
    border:1px solid #2F6FD9; border-radius:6px; padding:6px 10px;
    font-size: 12px;
}}

/* ---- 毛玻璃面板 ---- */
QFrame#panel {{
    background: {GLASS['panel']};
    border: 1px solid {GLASS['border']};
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
    background: {GLASS['field']}; color: #B9C6E2;
    border-radius: 10px; padding: 3px 9px; font-size: 12px;
}}
QLabel#statusOK  {{ color: {PALETTE['ok']};   font-size: 12px; font-weight: 600; }}
QLabel#statusOff {{ color: {PALETTE['muted']}; font-size: 12px; }}
QLabel#warnbox {{
    background: rgba(232, 163, 61, 32); color:{PALETTE['warn']};
    border:1px solid rgba(232, 163, 61, 92);
    border-radius:10px; padding:8px 10px; font-size: 12px;
}}
QLabel#titleBig {{ font-size: 17px; font-weight: 700; color: {PALETTE['text']}; }}
QLabel#titleSub {{ color: {PALETTE['muted']}; font-size: 12px; }}

/* ---- 输入控件：深底亮字，统一圆角与高度 ---- */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background: {GLASS['input']};
    color: {PALETTE['text']};
    border: 1px solid {GLASS['border']};
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 20px;
    selection-background-color: {PALETTE['accent']};
    selection-color: #FFFFFF;
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover,
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {GLASS['border_strong']};
}}
/* 键盘焦点：2px 亮蓝环 + 底色提亮；padding 减 1px 抵消边框增宽，避免内容跳动 */
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QComboBox:focus, QDateEdit:focus {{
    border: 2px solid {PALETTE['focus']};
    padding: 5px 9px;
    background: rgba(8, 14, 30, 200);
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 2px solid {PALETTE['focus']};
    padding: 5px 23px 5px 9px;   /* 右侧留出加减按钮区 */
    background: rgba(8, 14, 30, 200);
}}
QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background: rgba(255, 255, 255, 10); color: #57647F; border-color: rgba(255,255,255,16);
}}
QLineEdit[readOnly="true"] {{ color: {PALETTE['muted']}; }}

/* ---- 下拉框箭头：用真实 PNG（Qt 不支持 CSS 三角边框）---- */
QComboBox::drop-down {{
    border: none; width: 28px; background: transparent;
}}
QComboBox::down-arrow {{
    image: @@DOWN@@;
    width: 10px; height: 6px;
    margin: 0 11px 0 0;
}}
QComboBox::down-arrow:hover {{ image: @@DOWN_HOVER@@; }}
QComboBox::down-arrow:disabled {{ image: @@DOWN@@; }}
QComboBox QAbstractItemView {{
    background: #131B33; color: {PALETTE['text']};
    border: 1px solid {PALETTE['border']}; border-radius: 8px;
    selection-background-color: {PALETTE['accent_soft']};
    selection-color: #CFE0FF;
    outline: none; padding: 4px;
}}
QComboBox QAbstractItemView::item {{ min-height: 28px; padding: 4px 8px; border-radius: 6px; }}

/* ---- 数字框上下按钮：图片箭头，大小一致、完整对齐 ---- */
QSpinBox, QDoubleSpinBox {{ padding-right: 24px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 22px; height: 13px;
    border: none; background: transparent;
    margin: 1px 2px 0 0;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 22px; height: 13px;
    border: none; background: transparent;
    margin: 0 2px 1px 0;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: rgba(255, 255, 255, 26); border-radius: 4px;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: @@UP@@;
    width: 8px; height: 5px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: @@DOWN@@;
    width: 8px; height: 5px;
}}
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {{ image: @@UP_HOVER@@; }}
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {{ image: @@DOWN_HOVER@@; }}

/* ---- 按钮 ---- */
QPushButton {{
    background: {GLASS['field']}; color: {PALETTE['text']};
    border: 1px solid {GLASS['border']};
    border-radius: 8px; padding: 7px 14px; font-size: 13px;
    min-height: 16px;   /* 内容 16 + padding 14 + 边框 2 = 32px 点击高度 */
}}
QPushButton:hover {{ background:{GLASS['panel_hover']}; border-color:{GLASS['border_strong']}; }}
QPushButton:pressed {{ background: rgba(255, 255, 255, 40); }}
QPushButton:disabled {{ color:#57647F; background:rgba(255,255,255,10); border-color:rgba(255,255,255,16); }}
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {PALETTE['accent']}, stop:1 {PALETTE['accent2']});
    color:#FFFFFF;
    border:1px solid rgba(255,255,255,40); font-weight:600;
}}
/* hover 走"压深 + 亮边"，不提亮渐变：提亮后白字会跌到 4:1 以下 */
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {PALETTE['accent_hover']}, stop:1 {PALETTE['accent2_hover']});
    border-color: rgba(255,255,255,96);
}}
QPushButton#primary:pressed {{ background:{PALETTE['accent_hover']}; }}
QPushButton#primary:focus {{
    border:2px solid #CFE0FF; padding:6px 13px;
}}
QPushButton#primary:disabled {{ background:#33406B; color:#8A96B4; border-color:#33406B; }}
QPushButton#danger {{ color:{PALETTE['danger']}; border-color:rgba(241,106,106,110); background:rgba(241,106,106,24); }}
QPushButton#danger:hover {{ background:rgba(241,106,106,46); }}
QPushButton#danger:focus {{ border:2px solid {PALETTE['focus']}; padding:6px 13px; }}
QPushButton#ghost {{ border:1px solid transparent; background:transparent; padding:4px 8px; color:{PALETTE['muted']}; }}
QPushButton#ghost:hover {{ background:rgba(255,255,255,24); color:{PALETTE['text']}; }}
QPushButton#ghost:focus {{
    border:1px solid {PALETTE['focus']}; color:{PALETTE['text']};
    background: rgba(127,176,255,26);
}}
QPushButton:focus {{ border:2px solid {PALETTE['focus']}; padding:6px 13px; }}

/* ---- 图标按钮：28×28 点击区，图标 + tooltip 双通道 ---- */
QPushButton#iconBtn, QPushButton#iconBtnDanger {{
    padding:0; font-size:14px; border-radius:8px;
    background:transparent; border:1px solid transparent;
}}
QPushButton#iconBtn {{ color:{PALETTE['muted']}; }}
QPushButton#iconBtn:hover {{
    background:rgba(255,255,255,26); color:{PALETTE['text']};
    border-color:rgba(255,255,255,46);
}}
QPushButton#iconBtn:pressed {{ background:rgba(255,255,255,46); }}
QPushButton#iconBtnDanger {{ color:#FF9A9A; }}
QPushButton#iconBtnDanger:hover {{
    background:rgba(241,106,106,40); color:#FFC9C9;
    border-color:rgba(241,106,106,120);
}}
QPushButton#iconBtnDanger:pressed {{ background:rgba(241,106,106,64); }}
QPushButton#iconBtn:focus, QPushButton#iconBtnDanger:focus {{
    border:2px solid {PALETTE['focus']};
}}

/* ---- 单选 / 复选 ---- */
QRadioButton, QCheckBox {{ color: {PALETTE['text']}; spacing: 7px; background: transparent; }}
QRadioButton::indicator, QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid rgba(255,255,255,80); background: rgba(255,255,255,18);
}}
QRadioButton::indicator {{ border-radius: 8px; }}
QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
    background: {PALETTE['accent']}; border-color: {PALETTE['accent_bright']};
}}
/* Qt 不会自动画对勾，选中态补一张白色 tick，避免"纯色块=已开启"无法确认 */
QCheckBox::indicator:checked {{ image: @@CHECK@@; }}
/* 焦点：整行淡蓝底晕。注意不要写 QCheckBox:focus::indicator —— Qt 会忽略
   subcontrol 前的 :focus 伪状态，把边框泄漏给所有未聚焦的复选框 */
QCheckBox:focus, QRadioButton:focus {{
    background: rgba(127,176,255,26); border-radius:6px; color:#FFFFFF;
}}
QRadioButton::indicator:checked {{
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 #0D1426, stop:0.45 #0D1426, stop:0.55 {PALETTE['accent']}, stop:1 {PALETTE['accent']});
}}
QCheckBox:disabled, QRadioButton:disabled {{ color: #57647F; }}

/* ---- 列表 / 树 ---- */
QListWidget, QTreeWidget, QTreeView {{
    background: transparent; border: none; outline: none;
    color: {PALETTE['text']};
}}
QListWidget::item {{ padding:8px 12px; border-radius:8px; margin:1px 6px; color:{PALETTE['text']}; }}
QListWidget::item:hover {{ background:rgba(255,255,255,22); }}
QListWidget::item:selected {{ background:{PALETTE['accent_soft']}; color:#CFE0FF; font-weight:600; }}
QTreeWidget::item {{ height: 26px; color: {PALETTE['text']}; }}
QTreeWidget::item:hover {{ background:rgba(255,255,255,22); border-radius:6px; }}
QTreeWidget::item:selected {{ background:{PALETTE['accent_soft']}; color:#CFE0FF; border-radius:6px; }}
QTreeView::branch {{ background: transparent; }}

/* ---- 表格 ---- */
QTableWidget, QTableView {{
    background: rgba(8, 14, 30, 120); color:{PALETTE['text']};
    alternate-background-color: rgba(255,255,255,10);
    border:1px solid {GLASS['border']}; border-radius:10px;
    gridline-color:{PALETTE['border']}; outline:none;
}}
QTableWidget::item {{ padding: 4px 6px; color: {PALETTE['text']}; }}
QTableWidget::item:selected {{ background:{PALETTE['accent_soft']}; color:#CFE0FF; }}
QHeaderView::section {{
    background: rgba(255,255,255,22); color:{PALETTE['muted']};
    border:none; border-right:1px solid {PALETTE['border']};
    border-bottom:1px solid {PALETTE['border']};
    padding:7px 8px; font-weight:600; font-size: 12px;
}}

/* ---- 滑动条 ---- */
QSlider {{ background: transparent; min-height: 22px; }}
QSlider::groove:horizontal {{
    height: 6px; border-radius: 3px;
    background: rgba(255,255,255,38);
}}
QSlider::sub-page:horizontal {{
    height: 6px; border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {PALETTE['accent']}, stop:1 {PALETTE['accent2']});
}}
QSlider::add-page:horizontal {{ height: 6px; border-radius: 3px; background: rgba(255,255,255,38); }}
QSlider::handle:horizontal {{
    width: 16px; height: 16px; margin: -6px 0;
    border-radius: 8px; background: #EAF2FF;
    border: 1px solid {PALETTE['accent']};
}}
QSlider::handle:horizontal:hover {{ background: #FFFFFF; }}
/* 焦点：底层淡蓝晕（不改边框，避免 1px 位移把 16px 手柄挤到裁切） */
QSlider:focus {{
    background: rgba(127,176,255,30);
    border-radius: 9px;
}}

/* ---- Tab ---- */
QTabWidget::pane {{
    border:1px solid {GLASS['border']}; border-radius:10px;
    background: {GLASS['panel']}; top:-1px;
}}
QTabBar::tab {{
    padding:8px 18px; margin-right:4px; border:none; background:transparent;
    color: {PALETTE['muted']}; font-size: 13px;
}}
QTabBar::tab:hover {{ color: {PALETTE['text']}; }}
QTabBar::tab:selected {{
    background:{PALETTE['accent_soft']}; border-radius:8px;
    color:#CFE0FF; font-weight:600;
}}

/* ---- 滚动条 ---- */
QScrollArea, QScrollArea > QWidget > QWidget {{ background:transparent; border:none; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:0; }}
QScrollBar::handle:vertical {{ background:rgba(255,255,255,52); border-radius:5px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:rgba(255,255,255,88); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ background:transparent; height:10px; }}
QScrollBar::handle:horizontal {{ background:rgba(255,255,255,52); border-radius:5px; }}
QScrollBar::handle:horizontal:hover {{ background:rgba(255,255,255,88); }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}

/* ---- 其它 ---- */
QSplitter::handle {{ background: rgba(255,255,255,24); }}
QSplitter::handle:horizontal {{ width:1px; }}
QStatusBar {{
    background: rgba(255,255,255,14);
    border-top:1px solid {GLASS['border']}; color:{PALETTE['muted']};
}}
QStatusBar QLabel {{ color: {PALETTE['muted']}; }}
QProgressBar {{
    border:1px solid {GLASS['border']}; border-radius:8px;
    background: rgba(8,14,30,120); height:18px;
    text-align:center; color:{PALETTE['text']};
}}
QProgressBar::chunk {{
    border-radius:7px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {PALETTE['accent']}, stop:1 {PALETTE['accent2']});
}}
QMenu {{ background:#131B33; color:{PALETTE['text']}; border:1px solid {PALETTE['border']}; border-radius:10px; padding:6px; }}
QMenu::item {{ padding:7px 22px; border-radius:6px; color:{PALETTE['text']}; }}
QMenu::item:selected {{ background:{PALETTE['accent_soft']}; color:#CFE0FF; }}
QMessageBox {{ background: #101830; }}
QMessageBox QLabel {{ color: {PALETTE['text']}; }}
QGroupBox {{
    border: 1px solid {GLASS['border']}; border-radius: 10px;
    margin-top: 12px; color: {PALETTE['text']}; background: {GLASS['panel']};
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {PALETTE['muted']}; }}
"""


def style_sheet() -> str:
    """返回完整 QSS：把箭头图片令牌替换成真实文件路径。

    注意不能用 str.format()：QSS 是 f-string 产物，里面全是单层花括号。
    """
    arrows = _arrow_images()
    qss = QSS
    for key, url in arrows.items():
        qss = qss.replace(f"@@{key.upper()}@@", url)
    return qss
