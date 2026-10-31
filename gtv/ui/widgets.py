"""通用小控件：流式布局、封面、图标按钮、吐司提示。"""
from __future__ import annotations

import hashlib

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from ..core import config


class FlowLayout(QLayout):
    """自适应宽度的网格/流式布局。"""

    def __init__(self, parent=None, hspace: int = 12, vspace: int = 12):
        super().__init__(parent)
        self._items: list = []
        self.hspace = hspace
        self.vspace = vspace

    # --- QLayout 接口
    def addItem(self, item):  # noqa: N802
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self):  # noqa: N802
        return True

    def heightForWidth(self, width):  # noqa: N802
        return self._layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._layout(rect, False)

    def sizeHint(self):  # noqa: N802
        return QSize(320, 200)

    def minimumSize(self):  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        eff = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y = eff.x(), eff.y()
        row_h = 0
        for item in self._items:
            if not item.widget() or item.widget().isHidden():
                continue
            sz = item.sizeHint()
            if x + sz.width() > eff.right() and x > eff.x():
                x = eff.x()
                y += row_h + self.vspace
                row_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), sz))
            x += sz.width() + self.hspace
            row_h = max(row_h, sz.height())
        return y + row_h - rect.y() + m.bottom()


def color_variant(hex_color: str, factor: float = 0.72) -> QColor:
    c = QColor(hex_color)
    return QColor(
        max(0, min(255, int(c.red() * factor))),
        max(0, min(255, int(c.green() * factor))),
        max(0, min(255, int(c.blue() * factor))),
    )


class CoverLabel(QLabel):
    """按游戏名生成确定性的渐变占位封面。"""

    def __init__(self, game: str, color: str = "#3B6EA5", w: int = 220, h: int = 132, radius: int = 10,
                 text_scale: float = 1.0, parent=None):
        super().__init__(parent)
        self.cfg = (game, color, w, h, radius, text_scale)
        self.setFixedSize(w, h)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.render()

    def set_content(self, game: str, color: str | None = None) -> None:
        _g, old, w, h, radius, scale = self.cfg
        self.cfg = (game, color or old, w, h, radius, scale)
        self.render()

    def render(self) -> None:
        game, color, w, h, radius, scale = self.cfg
        pm = QPixmap(w, h)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, radius, radius)
        p.setClipPath(path)
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0, QColor(color))
        g.setColorAt(1, color_variant(color, 0.58))
        p.fillRect(0, 0, w, h, g)
        # 装饰圆环
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 26))
        d = h * 0.9
        p.drawEllipse(int(w - d * 0.45), int(-d * 0.25), int(d), int(d))
        p.setBrush(QColor(0, 0, 0, 26))
        p.drawEllipse(int(-d * 0.35), int(h - d * 0.55), int(d * 0.8), int(d * 0.8))

        # 文字
        initials = self._initials(game)
        f = QFont("Microsoft YaHei UI", max(11, int(h * 0.26 * scale)), QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 235))
        fm = QFontMetrics(f)
        sub = QFont("Microsoft YaHei UI", max(7, int(h * 0.085 * scale)))
        p.setFont(sub)
        sfm = QFontMetrics(sub)
        subtitle = "TRAINER"
        ty = int(h * 0.56)
        p.drawText(QRect(0, ty - fm.height(), w, fm.height()), Qt.AlignmentFlag.AlignCenter, initials)
        y2 = ty + int(h * 0.08)
        p.drawText(QRect(0, y2, w, sfm.height()), Qt.AlignmentFlag.AlignCenter, subtitle)
        p.end()
        self.setPixmap(pm)

    @staticmethod
    def _initials(game: str) -> str:
        raw = game.split("/")[0].strip()
        ascii_part = "".join(ch for ch in raw if ch.isascii() and (ch.isalnum() or ch == " "))
        parts = [p for p in ascii_part.split() if p]
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        if ascii_part.strip():
            return ascii_part.strip()[:2].upper()
        return raw[:2]


def cached_color(seed: str) -> str:
    """由字符串稳定映射到一个柔和的封面配色。"""
    palette = [
        "#2F6FEB", "#C1440E", "#2E9E5B", "#7C3E8C", "#B03A2E",
        "#117864", "#1F5FA9", "#8A6D3B", "#34495E", "#8E44AD",
    ]
    h = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return palette[int(h[:8], 16) % len(palette)]


class ChipLabel(QLabel):
    def __init__(self, text: str, parent=None, color: str | None = None):
        super().__init__(f" {text} ", parent)
        self.setObjectName("chip")
        if color:
            self.setStyleSheet(
                f"background:{color}20; color:{color}; border-radius:10px; padding:3px 9px;"
            )


class HLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setStyleSheet("color:#E2E5EA;")


def elide(text: str, width: int, font: QFont) -> str:
    return QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, width)


def confirm(parent, title: str, text: str) -> bool:
    from PySide6.QtWidgets import QMessageBox

    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Question)
    yes = box.addButton("确定", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(yes)
    box.exec()
    return box.clickedButton() is yes


def info(parent, text: str, title: str = "提示") -> None:
    from PySide6.QtWidgets import QMessageBox

    QMessageBox.information(parent, title, text)


def warn(parent, text: str, title: str = "警告") -> None:
    from PySide6.QtWidgets import QMessageBox

    QMessageBox.warning(parent, title, text)


def open_local_path(path: str) -> None:
    import os
    import subprocess
    import sys

    p = str(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(p)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])  # noqa: S603
        else:
            subprocess.Popen(["xdg-open", p])  # noqa: S603
    except Exception:  # noqa: BLE001
        pass


def reveal_in_explorer(path: str) -> None:
    import subprocess
    import sys

    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(path)])  # noqa: S603
        else:
            open_local_path(path)
    except Exception:  # noqa: BLE001
        open_local_path(path)
