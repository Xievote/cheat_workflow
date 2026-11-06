"""库列表中的纵向条形游戏卡片。

一行一个游戏：左侧迷你封面色块，中间名称与关键信息，
右侧地址数 / 导入状态 / 运行次数 / 收藏 / 启动。点击整行进入游戏详情页。
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import Trainer
from .widgets import CoverLabel, cached_color

ROW_H = 72


class TrainerRow(QFrame):
    selected = Signal(int)
    launch = Signal(int)
    favorite_toggled = Signal(int)
    edit_requested = Signal(int)
    delete_requested = Signal(int)
    reveal_requested = Signal(int)
    open_page = Signal(int)

    def __init__(self, t: Trainer, mem_count: int = 0, parent=None):
        super().__init__(parent)
        self.t = t
        self.mem_count = mem_count
        self.setObjectName("panel")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(ROW_H)
        self._build()
        self.refresh(t)
        self._apply(False)

    # ------------------------------------------------------------ UI
    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(12)

        self.cover = CoverLabel("", "#3B6EA5", w=48, h=48, radius=9, text_scale=0.55)
        root.addWidget(self.cover, 0)

        mid = QVBoxLayout()
        mid.setSpacing(2)
        self.lbl_title = QLabel("")
        self.lbl_title.setStyleSheet(
            "QLabel{font-size:14px; font-weight:700; color:#1F2430; background:transparent;}"
        )
        mid.addWidget(self.lbl_title)
        self.lbl_sub = QLabel("")
        self.lbl_sub.setStyleSheet(
            "QLabel{font-size:11px; color:#6B7280; background:transparent;}"
        )
        mid.addWidget(self.lbl_sub)
        root.addLayout(mid, 1)

        # 右侧信息区
        self.chip_mem = QLabel("")
        self.chip_mem.setObjectName("chip")
        root.addWidget(self.chip_mem, 0)

        self.lbl_state = QLabel("")
        self.lbl_state.setStyleSheet("QLabel{font-size:12px; font-weight:600; background:transparent;}")
        root.addWidget(self.lbl_state, 0)

        self.lbl_runs = QLabel("")
        self.lbl_runs.setStyleSheet("QLabel{font-size:12px; color:#9AA3AF; background:transparent;}")
        root.addWidget(self.lbl_runs, 0)

        self.btn_fav = QPushButton("☆")
        self.btn_fav.setObjectName("ghost")
        self.btn_fav.setFixedSize(28, 26)
        self.btn_fav.setToolTip("收藏 / 取消收藏")
        self.btn_fav.clicked.connect(lambda: self.favorite_toggled.emit(self.t.id or 0))
        root.addWidget(self.btn_fav, 0)

        self.btn_run = QPushButton("启动")
        self.btn_run.setObjectName("primary")
        self.btn_run.setFixedSize(56, 28)
        self.btn_run.clicked.connect(lambda: self.launch.emit(self.t.id or 0))
        root.addWidget(self.btn_run, 0)

    # ------------------------------------------------------------ 数据
    def refresh(self, t: Trainer | None = None, mem_count: int | None = None) -> None:
        if t:
            self.t = t
        if mem_count is not None:
            self.mem_count = mem_count
        t = self.t

        self.cover.set_content(t.game_title or t.title, t.cover_color or cached_color(t.game_title))
        self.lbl_title.setText(t.game_title or t.title)
        self.lbl_title.setToolTip(f"{t.title}\n{t.source_url}")

        bits = [t.category]
        bits += [f"#{x}" for x in t.tags[:3]]
        if t.author:
            bits.append(t.author)
        if t.version:
            bits.append(f"v{t.version}")
        self.lbl_sub.setText("  ·  ".join(bits))
        self.lbl_sub.setToolTip(t.notes[:120] if t.notes else "")

        self.chip_mem.setText(f" {self.mem_count} 条地址 " if self.mem_count else "")
        self.chip_mem.setVisible(bool(self.mem_count))

        if t.installed:
            self.lbl_state.setText("● 已导入")
            self.lbl_state.setStyleSheet("QLabel{color:#2E9E5B; font-size:12px; font-weight:600; background:transparent;}")
        else:
            self.lbl_state.setText("○ 待导入")
            self.lbl_state.setStyleSheet("QLabel{color:#B26B00; font-size:12px; font-weight:600; background:transparent;}")

        self.lbl_runs.setText(f"运行 {t.run_count} 次")
        self.btn_fav.setText("★" if t.favorite else "☆")
        self.btn_fav.setStyleSheet(
            "QPushButton{color:#E8B400; font-size:15px; border:none; background:transparent;}"
            if t.favorite
            else "QPushButton{color:#9AA3AF; font-size:15px; border:none; background:transparent;}"
        )

    def set_selected(self, on: bool) -> None:
        self._apply(on)

    def _apply(self, on: bool) -> None:
        if on:
            self.setStyleSheet(
                "QFrame#panel{background:#F0F5FF;border:2px solid #2F6FEB;border-radius:12px;}"
            )
        else:
            self.setStyleSheet(
                "QFrame#panel{background:#FFFFFF;border:1px solid #E2E5EA;border-radius:12px;}"
                "QFrame#panel:hover{border:1px solid #BDC7D6;background:#FDFEFF;}"
            )

    def set_running(self, running: bool, elapsed: int = 0) -> None:
        if running:
            self.btn_run.setText("运行中")
            self.btn_run.setStyleSheet(
                "background:#FFF6E6;color:#B26B00;border:1px solid #F3DCA8;border-radius:8px;font-weight:600;"
            )
            self.btn_run.setToolTip(f"已运行 {elapsed}s，点击停止")
        else:
            self.btn_run.setText("启动")
            self.btn_run.setStyleSheet("")
            self.btn_run.setToolTip("启动该游戏")

    # ------------------------------------------------------------ 交互
    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.t.id or 0)
        elif event.button() == Qt.MouseButton.RightButton:
            self._menu(event)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self.launch.emit(self.t.id or 0)
        super().mouseDoubleClickEvent(event)

    def _menu(self, event) -> None:
        m = QMenu(self)
        a_open = m.addAction("进入详情页")
        a_launch = m.addAction("启动 / 停止")
        a_page = m.addAction("打开官方页面")
        a_fav = m.addAction("切换收藏")
        m.addSeparator()
        a_edit = m.addAction("编辑信息")
        a_reveal = m.addAction("打开所在目录")
        a_del = m.addAction("从库中删除")
        act = m.exec(QCursor.pos())
        if not act:
            return
        tid = self.t.id or 0
        if act is a_open:
            self.selected.emit(tid)
        elif act is a_launch:
            self.launch.emit(tid)
        elif act is a_page:
            self.open_page.emit(tid)
        elif act is a_fav:
            self.favorite_toggled.emit(tid)
        elif act is a_edit:
            self.edit_requested.emit(tid)
        elif act is a_reveal:
            self.reveal_requested.emit(tid)
        elif act is a_del:
            self.delete_requested.emit(tid)
