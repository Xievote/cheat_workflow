"""库中的修改器卡片。"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from ..core import config
from ..core.models import Trainer
from .widgets import ChipLabel, CoverLabel, cached_color

CARD_W, CARD_H = 196, 236


class TrainerCard(QFrame):
    selected = Signal(int)
    launch = Signal(int)
    favorite_toggled = Signal(int)
    edit_requested = Signal(int)
    delete_requested = Signal(int)
    reveal_requested = Signal(int)
    open_page = Signal(int)

    def __init__(self, t: Trainer, parent=None):
        super().__init__(parent)
        self.t = t
        self.setObjectName("panel")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedWidth(CARD_W)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(7)

        # 封面 + 状态角标
        self.cover = CoverLabel(t.game_title, t.cover_color or cached_color(t.game_title),
                                w=CARD_W - 20, h=108)
        root.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignTop)

        # 标题
        self.lbl_title = QLabel(t.game_title)
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setStyleSheet("font-weight:600; font-size:13px;")
        self.lbl_title.setFixedHeight(34)
        root.addWidget(self.lbl_title)

        # 分类 / 来源
        row = QHBoxLayout()
        row.setSpacing(5)
        self.chip_cat = ChipLabel(t.category)
        row.addWidget(self.chip_cat, 0)
        row.addStretch(1)
        self.lbl_state = QLabel("")
        self.lbl_state.setStyleSheet("font-size:11px;")
        row.addWidget(self.lbl_state)
        root.addLayout(row)

        # 底部：运行次数 + 收藏 + 启动
        foot = QHBoxLayout()
        foot.setSpacing(4)
        self.lbl_runs = QLabel("")
        self.lbl_runs.setStyleSheet("color:#6B7280; font-size:11px;")
        foot.addWidget(self.lbl_runs, 1)

        self.btn_fav = QPushButton("☆")
        self.btn_fav.setObjectName("ghost")
        self.btn_fav.setToolTip("收藏 / 取消收藏")
        self.btn_fav.setFixedSize(26, 24)
        self.btn_fav.clicked.connect(lambda: self.favorite_toggled.emit(self.t.id or 0))
        foot.addWidget(self.btn_fav, 0)

        self.btn_run = QPushButton("启动")
        self.btn_run.setObjectName("primary")
        self.btn_run.setFixedSize(52, 24)
        self.btn_run.clicked.connect(lambda: self.launch.emit(self.t.id or 0))
        foot.addWidget(self.btn_run, 0)
        root.addLayout(foot)

        self.refresh(t)
        self._apply(False)

    # ------------------------------------------------------------
    def refresh(self, t: Trainer | None = None) -> None:
        if t:
            self.t = t
        t = self.t
        self.cover.set_content(t.game_title, t.cover_color or cached_color(t.game_title))

        self.lbl_title.setText(t.game_title)
        self.lbl_title.setToolTip(f"{t.game_title}\n{t.title}\n{t.source_url}")
        self.chip_cat.setText(f" {t.category} ")

        if t.installed:
            self.lbl_state.setText("● 已安装")
            self.lbl_state.setStyleSheet("color:#2E9E5B; font-size:11px;")
        else:
            self.lbl_state.setText("○ 未导入")
            self.lbl_state.setStyleSheet("color:#9AA3AF; font-size:11px;")
        self.lbl_runs.setText(f"运行 {t.run_count} 次")
        self.btn_fav.setText("★" if t.favorite else "☆")
        self.btn_fav.setStyleSheet(
            "color:#E8B400; border:none;" if t.favorite else "color:#9AA3AF; border:none;"
        )

    def set_selected(self, on: bool) -> None:
        self._apply(on)

    def _apply(self, on: bool) -> None:
        if on:
            base = "QFrame#panel{background:#FFFFFF;border:2px solid #2F6FEB;border-radius:12px;}"
        else:
            base = (
                "QFrame#panel{background:#FFFFFF;border:1px solid #E2E5EA;border-radius:12px;}"
                "QFrame#panel:hover{border:1px solid #BDC7D6;background:#FDFEFF;}"
            )
        self.setStyleSheet(base)

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
            self.btn_run.setToolTip("启动该修改器")

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

    def enterEvent(self, event):  # noqa: N802
        super().enterEvent(event)

    def _menu(self, event) -> None:
        m = QMenu(self)
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
        if act is a_launch:
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
