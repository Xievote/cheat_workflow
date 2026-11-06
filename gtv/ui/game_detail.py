"""游戏详情页：启动、进程附加、内存地址列表与元信息在同一界面协同工作。

页面结构（自上而下）：
  1. 头部：返回列表 / 封面 / 名称 / 分类标签 / 收藏·编辑·页面·目录
  2. 操作条：启动·停止 | 附加进程·选择进程·分离 | 新增地址
  3. 状态条：运行会话状态 · 内存附加状态
  4. 主体（左右分栏）：左＝内存地址列表（每条可切换修改方式），右＝热键/备注/启动记录
"""
from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import config
from ..core.memory_engine import MemoryEngine
from ..core.models import MemoryEntry, Option, Trainer, human_duration
from .memory_dialog import MemoryEntryDialog
from .widgets import ChipLabel, CoverLabel, HLine, confirm, open_local_path, reveal_in_explorer

READ_INTERVAL_MS = 500
WRITE_FLASH_MS = 900

CONTROL_CHOICES = [
    ("slider", "滑动条"),
    ("spin", "数值框"),
    ("button", "按钮"),
    ("toggle", "开关"),
]
_VALUE_STYLE = "QLabel{color:#1F2430; background:#F3F5F8; border-radius:8px; padding:6px 10px;}"
_VALUE_HL = "QLabel{color:#1F2430; background:#E8F0FE; border-radius:8px; padding:6px 10px;}"
_VALUE_ERR = "QLabel{color:#D64545; background:#FDF1F1; border-radius:8px; padding:6px 10px;}"


class ProcessPickDialog(QDialog):
    """从系统进程列表选择目标进程（支持过滤 + 手输 PID）。"""

    def __init__(self, engine: MemoryEngine, exe_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择游戏进程")
        self.resize(420, 520)
        self.engine = engine
        self.pid = 0
        self.proc_name = ""

        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(8)

        tip = QLabel("按进程名过滤，双击选择；也可以直接输入 PID。")
        tip.setObjectName("muted")
        v.addWidget(tip)

        self.e_filter = QLineEdit()
        self.e_filter.setPlaceholderText("过滤进程名，如 game.exe")
        if exe_name:
            self.e_filter.setText(exe_name)
        self.e_filter.textChanged.connect(self._reload)
        v.addWidget(self.e_filter)

        self.listw = QListWidget()
        self.listw.itemDoubleClicked.connect(self._pick)
        v.addWidget(self.listw, 1)

        row = QHBoxLayout()
        self.e_pid = QLineEdit()
        self.e_pid.setPlaceholderText("或输入 PID")
        row.addWidget(self.e_pid, 1)
        b_pid = QPushButton("按 PID 附加")
        b_pid.clicked.connect(self._pick_pid)
        row.addWidget(b_pid)
        v.addLayout(row)

        self._all: list[tuple[int, str]] = []
        QTimer.singleShot(0, self._reload)

    def _reload(self) -> None:
        kw = self.e_filter.text().strip().lower()
        if not self._all:
            try:
                import pymem.process

                seen: dict[int, str] = {}
                for p in pymem.process.list_processes():
                    name = p.szExeFile
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", errors="replace")
                    name = name.strip()
                    if name:
                        seen[int(p.th32ProcessID)] = name
                self._all = sorted(seen.items())
            except Exception:  # noqa: BLE001
                self._all = []
        self.listw.clear()
        for pid, name in self._all:
            if kw and kw not in name.lower():
                continue
            self.listw.addItem(QListWidgetItem(f"{name}    PID {pid}"))

    def _pick(self, item) -> None:
        text = item.text()
        self.pid = int(text.rsplit("PID", 1)[1].strip())
        self.proc_name = text.split("    PID")[0].strip()
        self.accept()

    def _pick_pid(self) -> None:
        try:
            self.pid = int(self.e_pid.text().strip())
        except ValueError:
            QMessageBox.warning(self, "PID 无效", "请输入数字 PID。")
            return
        self.proc_name = ""
        self.accept()


class EntryRow(QFrame):
    """一条内存地址：名称 + 实时值 + 修改方式下拉 + 对应控件。"""

    edited = Signal(object)
    deleted = Signal(object)
    control_changed = Signal(object, str)
    activity = Signal(str)
    write_requested = Signal(object, object)

    def __init__(self, entry: MemoryEntry, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.entry = entry
        self._writing = False

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(10)

        # ---- 名称 / 地址
        left = QVBoxLayout()
        left.setSpacing(2)
        self.lbl_name = QLabel(entry.name)
        self.lbl_name.setStyleSheet(
            "QLabel{font-size:14px; font-weight:700; color:#1F2430; background:transparent;}"
        )
        left.addWidget(self.lbl_name)
        self.lbl_addr = QLabel(entry.addr_display)
        self.lbl_addr.setStyleSheet("QLabel{font-size:11px; color:#9AA3AF; background:transparent;}")
        left.addWidget(self.lbl_addr)
        if entry.note:
            note = QLabel(entry.note)
            note.setStyleSheet("QLabel{font-size:11px; color:#6B7280; background:transparent;}")
            left.addWidget(note)
        if not entry.enabled:
            self.lbl_name.setText(f"{entry.name}（已停用）")
        root.addLayout(left, 2)

        # ---- 当前值
        self.lbl_value = QLabel("—")
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPointSize(12)
        f.setBold(True)
        self.lbl_value.setFont(f)
        self.lbl_value.setMinimumWidth(96)
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_value.setStyleSheet(_VALUE_STYLE)
        self.lbl_value.setToolTip("实时读取到的当前值（每 0.5 秒刷新）")
        root.addWidget(self.lbl_value, 0)

        # ---- 修改方式（下拉）+ 控件
        self.cmb = QComboBox()
        for key, label in CONTROL_CHOICES:
            self.cmb.addItem(label, key)
        idx = next((i for i, (k, _l) in enumerate(CONTROL_CHOICES) if k == entry.control), 0)
        self.cmb.setCurrentIndex(idx)
        self.cmb.setFixedWidth(84)
        self.cmb.setToolTip("选择该数值的修改方式")
        self.cmb.currentIndexChanged.connect(self._on_control_pick)
        root.addWidget(self.cmb, 0)

        self._ctl_host = QWidget()
        self._ctl_lay = QHBoxLayout(self._ctl_host)
        self._ctl_lay.setContentsMargins(0, 0, 0, 0)
        self._ctl = None
        self._build_control()
        root.addWidget(self._ctl_host, 3)

        # ---- 编辑 / 删除
        ops = QVBoxLayout()
        ops.setSpacing(2)
        b_edit = QPushButton("编辑")
        b_edit.setObjectName("ghost")
        b_edit.setFixedWidth(44)
        b_edit.clicked.connect(self._edit)
        b_del = QPushButton("删除")
        b_del.setObjectName("ghost")
        b_del.setFixedWidth(44)
        b_del.clicked.connect(self._del)
        ops.addWidget(b_edit)
        ops.addWidget(b_del)
        root.addLayout(ops, 0)

        self.setFixedHeight(84)

    # ------------------------------------------------------------ 控件生成
    def _build_control(self) -> None:
        e = self.entry
        is_float = e.dtype in ("float", "double")
        if e.control == "slider":
            s = QSlider(Qt.Orientation.Horizontal)
            lo = int(round(e.minv / (e.step or 1)))
            hi = int(round(e.maxv / (e.step or 1)))
            if hi <= lo:
                hi = lo + 1
            s.setRange(lo, hi)
            s.setToolTip(f"范围 {e.minv:g} ~ {e.maxv:g}，步长 {e.step:g}，松开即写入")
            s.sliderReleased.connect(lambda: self._emit_write(self._slider_value(s)))
            ctl = s
        elif e.control == "spin":
            sb = QDoubleSpinBox()
            sb.setRange(e.minv, e.maxv)
            sb.setSingleStep(e.step or 1)
            sb.setDecimals(2 if is_float else 0)
            sb.setToolTip("修改后按回车写入内存")
            sb.editingFinished.connect(lambda: self._emit_write(sb.value()))
            ctl = sb
        elif e.control == "button":
            b = QPushButton(f"写入 {e.value}")
            b.setObjectName("primary")
            b.setFixedWidth(120)
            b.setToolTip(f"点击把 {e.value} 写入内存")
            b.clicked.connect(
                lambda: self._emit_write(float(e.value) if is_float else int(e.value, 0))
            )
            ctl = b
        elif e.control == "toggle":
            cb = QCheckBox(f"开启（写入 {e.value}，取消写 0）")
            cb.setStyleSheet("QCheckBox{font-size:13px;}")
            cb.toggled.connect(
                lambda on: self._emit_write(
                    (float(e.value) if is_float else int(e.value, 0)) if on else 0
                )
            )
            ctl = cb
        else:
            ctl = QLabel("")

        self._ctl = ctl
        self._ctl_lay.addWidget(ctl)

    def _replace_control(self) -> None:
        if self._ctl is not None:
            self._ctl.setParent(None)
            self._ctl.deleteLater()
            self._ctl = None
        while self._ctl_lay.count():
            item = self._ctl_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._build_control()

    def _slider_value(self, s: QSlider) -> float:
        return s.value() * (self.entry.step or 1)

    def _on_control_pick(self) -> None:
        key = self.cmb.currentData()
        if not key or key == self.entry.control:
            return
        self.entry.control = key
        self._replace_control()
        self.control_changed.emit(self.entry, key)

    # ------------------------------------------------------------ 写入
    def _emit_write(self, value) -> None:
        if not self.entry.enabled:
            self.activity.emit(f"「{self.entry.name}」已停用，跳过写入")
            return
        self._writing = True
        self.write_requested.emit(self.entry, MemoryEngine.cast_value(self.entry.dtype, value))

    def notify_write_done(self, ok: bool, value) -> None:
        self._writing = False
        if ok:
            self.show_value(value, flash=True)

    # ------------------------------------------------------------ 显示
    def show_value(self, v, flash: bool = False) -> None:
        if v is None:
            self.lbl_value.setText("读取失败")
            self.lbl_value.setStyleSheet(_VALUE_ERR)
            return
        if self._writing:
            return
        if isinstance(v, float) and not float(v).is_integer():
            text = f"{v:,.2f}"
        elif float(v).is_integer():
            text = f"{int(v):,}"
        else:
            text = f"{v:,.4f}"
        self.lbl_value.setText(text)
        self.lbl_value.setStyleSheet(_VALUE_HL if flash else _VALUE_STYLE)

    # ------------------------------------------------------------ 编辑/删除
    def _edit(self) -> None:
        e = MemoryEntryDialog.edit(self.entry.name, self.entry, self)
        if e:
            self.edited.emit(e)

    def _del(self) -> None:
        if confirm(self, "删除地址条目", f"确定删除「{self.entry.name}」（{self.entry.addr_display}）吗？"):
            self.deleted.emit(self.entry)


class GameDetailPage(QWidget):
    activity = Signal(str)
    favorite_changed = Signal(int)
    edit_requested = Signal(int)
    delete_requested = Signal(int)
    back_requested = Signal()

    def __init__(self, db, launcher, engine: MemoryEngine, parent=None):
        super().__init__(parent)
        self.db = db
        self.launcher = launcher
        self.eng = engine
        self.t: Trainer | None = None
        self.rows: list[EntryRow] = []

        self._build()

        self._timer = QTimer(self)
        self._timer.setInterval(READ_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self.eng.attached.connect(self._on_attached)
        self.eng.detached.connect(self._on_detached)
        self.eng.error.connect(lambda m: self.activity.emit(m))
        self.launcher.sessionEnded.connect(self._on_session_end)

    # ============================================================ UI
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 10)
        root.setSpacing(8)

        # ---- 1. 头部
        head = QHBoxLayout()
        head.setSpacing(10)
        b_back = QPushButton("← 返回列表")
        b_back.setObjectName("ghost")
        b_back.clicked.connect(self.back_requested.emit)
        head.addWidget(b_back, 0, Qt.AlignmentFlag.AlignTop)

        self.cover = CoverLabel("GTV", "#3B6EA5", w=64, h=64, radius=10, text_scale=0.6)
        head.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignTop)

        titles = QVBoxLayout()
        titles.setSpacing(3)
        self.lbl_game = QLabel("未选择游戏")
        self.lbl_game.setStyleSheet(
            "QLabel{font-size:17px; font-weight:700; color:#1F2430; background:transparent;}"
        )
        titles.addWidget(self.lbl_game)
        self.lbl_sub = QLabel("")
        self.lbl_sub.setObjectName("muted")
        titles.addWidget(self.lbl_sub)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(4)
        titles.addLayout(self.chips)
        head.addLayout(titles, 1)

        self.btn_fav = QPushButton("☆ 收藏")
        self.btn_fav.clicked.connect(self._toggle_fav)
        head.addWidget(self.btn_fav, 0, Qt.AlignmentFlag.AlignTop)
        self.btn_edit = QPushButton("编辑信息")
        self.btn_edit.clicked.connect(lambda: self.t and self.edit_requested.emit(self.t.id or 0))
        head.addWidget(self.btn_edit, 0, Qt.AlignmentFlag.AlignTop)
        self.btn_page = QPushButton("官方页面")
        self.btn_page.clicked.connect(lambda: self.t and open_local_path(self.t.source_url))
        head.addWidget(self.btn_page, 0, Qt.AlignmentFlag.AlignTop)
        self.btn_folder = QPushButton("所在目录")
        self.btn_folder.clicked.connect(self._open_folder)
        head.addWidget(self.btn_folder, 0, Qt.AlignmentFlag.AlignTop)
        self.btn_del_game = QPushButton("删除")
        self.btn_del_game.setObjectName("danger")
        self.btn_del_game.clicked.connect(
            lambda: self.t and self.delete_requested.emit(self.t.id or 0)
        )
        head.addWidget(self.btn_del_game, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(head)

        # ---- 2. 操作条
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.btn_launch = QPushButton("启动游戏")
        self.btn_launch.setObjectName("primary")
        self.btn_launch.clicked.connect(self._toggle_launch)
        bar.addWidget(self.btn_launch)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.clicked.connect(self._stop)
        self.btn_stop.setEnabled(False)
        bar.addWidget(self.btn_stop)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color:#E2E5EA;")
        bar.addWidget(sep)

        self.btn_attach = QPushButton("附加进程")
        self.btn_attach.clicked.connect(self._auto_attach)
        bar.addWidget(self.btn_attach)
        self.btn_pick = QPushButton("选择进程…")
        self.btn_pick.clicked.connect(lambda: self._pick_process())
        bar.addWidget(self.btn_pick)
        self.btn_detach = QPushButton("分离")
        self.btn_detach.clicked.connect(lambda: self.eng.detach("手动分离"))
        self.btn_detach.setEnabled(False)
        bar.addWidget(self.btn_detach)
        bar.addStretch(1)
        self.btn_add = QPushButton("+ 新增地址")
        self.btn_add.clicked.connect(self._add_entry)
        bar.addWidget(self.btn_add)
        root.addLayout(bar)

        # ---- 3. 状态条
        st = QHBoxLayout()
        st.setSpacing(14)
        self.lbl_session = QLabel("○ 未运行")
        self.lbl_session.setStyleSheet(
            "QLabel{font-size:12px; font-weight:600; color:#6B7280; background:transparent;}"
        )
        st.addWidget(self.lbl_session)
        self.lbl_attach = QLabel("○ 未附加进程")
        self.lbl_attach.setStyleSheet(
            "QLabel{font-size:12px; font-weight:600; color:#6B7280; background:transparent;}"
        )
        st.addWidget(self.lbl_attach)
        st.addStretch(1)
        root.addLayout(st)

        self.warnbox = QLabel("")
        self.warnbox.setObjectName("warnbox")
        self.warnbox.setWordWrap(True)
        self.warnbox.hide()
        root.addWidget(self.warnbox)

        # ---- 4. 主体：左内存列表 / 右元信息
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.setHandleWidth(1)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 4, 8, 0)
        lv.setSpacing(6)
        self.lbl_mem = QLabel("内存地址 · 0 条")
        self.lbl_mem.setObjectName("section")
        lv.addWidget(self.lbl_mem)
        tip = QLabel("修改方式随时可切换；拖动滑动条 / 改数值 / 点按钮 / 拨开关即写入内存，中间格为实时读取值。")
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        lv.addWidget(tip)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.host = QWidget()
        self.host.setObjectName("gridHost")
        self.host.setStyleSheet("QWidget#gridHost{background:transparent;}")
        self.host_v = QVBoxLayout(self.host)
        self.host_v.setContentsMargins(0, 2, 0, 2)
        self.host_v.setSpacing(8)
        self.host_v.addStretch(1)
        self.scroll.setWidget(self.host)
        lv.addWidget(self.scroll, 1)

        self.lbl_empty = QLabel(
            "该游戏还没有内存地址。\n用 Cheat Engine 找到数值地址后，点上方「+ 新增地址」录入。"
        )
        self.lbl_empty.setObjectName("muted")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lv.addWidget(self.lbl_empty, 1)
        sp.addWidget(left)

        # 右侧元信息
        right = QWidget()
        right.setMinimumWidth(300)
        right.setMaximumWidth(400)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 4, 0, 0)
        rv.setSpacing(6)

        sec1 = QLabel("功能与热键")
        sec1.setObjectName("section")
        rv.addWidget(sec1)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["热键", "功能", "备注"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._on_option_edited)
        self.table.setMaximumHeight(190)
        rv.addWidget(self.table)

        row = QHBoxLayout()
        row.setSpacing(4)
        for text, fn in (
            ("+ 行", self._add_option_row),
            ("- 行", self._del_option_row),
            ("粘贴导入", self._paste_options),
            ("复制全部", self._copy_options),
        ):
            b = QPushButton(text)
            b.setStyleSheet("QPushButton{padding:4px 6px; font-size:12px;}")
            b.clicked.connect(fn)
            row.addWidget(b)
        rv.addLayout(row)

        sec2 = QLabel("备注")
        sec2.setObjectName("section")
        rv.addWidget(sec2)
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("使用注意事项：如需先启动游戏、改完需重开背包…")
        self.notes.setFixedHeight(84)
        self.notes.textChanged.connect(self._on_notes_changed)
        rv.addWidget(self.notes)

        rv.addWidget(HLine())
        sec3 = QLabel("最近启动记录")
        sec3.setObjectName("section")
        rv.addWidget(sec3)
        self.recent = QListWidget()
        self.recent.setMaximumHeight(130)
        rv.addWidget(self.recent, 1)
        sp.addWidget(right)

        sp.setStretchFactor(0, 1)
        sp.setStretchFactor(1, 0)
        sp.setSizes([680, 320])
        root.addWidget(sp, 1)

        self.setEnabled(False)

    # ============================================================ 数据加载
    def set_trainer(self, t: Trainer | None) -> None:
        if t is None or (self.t and self.t.id != t.id):
            if self.eng.is_attached:
                self.eng.detach("切换游戏")
        self.t = t
        self.setEnabled(t is not None)
        if t is None:
            self.lbl_game.setText("未选择游戏")
            self.lbl_sub.setText("")
            self._clear_chips()
            self.table.setRowCount(0)
            self.recent.clear()
            self.notes.blockSignals(True)
            self.notes.clear()
            self.notes.blockSignals(False)
            self.lbl_session.setText("○ 未运行")
            self.lbl_attach.setText("○ 未附加进程")
            self.warnbox.hide()
            self._reload_rows()
            return

        self._loading = True
        self.lbl_game.setText(t.game_title or t.title)
        self.lbl_sub.setText(
            f"{t.title or t.game_title} · {t.author or '未知来源'} · "
            f"{config.SOURCE_LABEL.get(t.source, t.source)}"
        )
        self.cover.set_content(t.game_title or t.title, t.cover_color)

        self._clear_chips()
        self.chips.addWidget(ChipLabel(t.category))
        for tag in t.tags[:4]:
            self.chips.addWidget(ChipLabel(tag, color="#2F6FEB"))
        self.chips.addStretch(1)

        self.warnbox.setVisible(bool(t.online_risk))
        if t.online_risk:
            self.warnbox.setText(
                "⚠ 该游戏包含联机模式。请仅在离线 / 单人剧情模式中使用内存修改，"
                "严禁进入多人模式，否则可能触发反作弊并导致账号处罚。"
            )

        self._fill_table(t.options)
        self.notes.blockSignals(True)
        self.notes.setPlainText(t.notes or "")
        self.notes.blockSignals(False)
        self._fill_recent(t.id or 0)
        self._refresh_buttons()
        self._reload_rows()
        self._refresh_session()
        self._loading = False

    def _clear_chips(self) -> None:
        while self.chips.count():
            item = self.chips.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # ---- 内存条目
    def _reload_rows(self) -> None:
        while self.host_v.count() > 1:
            item = self.host_v.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.rows.clear()

        entries: list[MemoryEntry] = self.db.list_memory(self.t.id) if self.t else []
        self.lbl_mem.setText(f"内存地址 · {len(entries)} 条")
        self.lbl_empty.setVisible(not entries)
        self.scroll.setVisible(bool(entries))
        for e in entries:
            row = EntryRow(e)
            row.edited.connect(self._on_entry_edited)
            row.deleted.connect(self._on_entry_deleted)
            row.control_changed.connect(self._on_control_changed)
            row.activity.connect(self.activity)
            row.write_requested.connect(self._write)
            self.host_v.insertWidget(self.host_v.count() - 1, row)
            self.rows.append(row)

    def _add_entry(self) -> None:
        if not self.t:
            return
        e = MemoryEntryDialog.edit(self.t.game_title or self.t.title, None, self)
        if not e:
            return
        e.trainer_id = self.t.id
        e.sort = len(self.rows)
        e.id = self.db.add_memory(e)
        self._reload_rows()
        self.activity.emit(f"已新增地址「{e.name}」")

    def _on_entry_edited(self, e: MemoryEntry) -> None:
        self.db.update_memory(e)
        self._reload_rows()
        self.activity.emit(f"已保存「{e.name}」")

    def _on_entry_deleted(self, e: MemoryEntry) -> None:
        if e.id:
            self.db.delete_memory(e.id)
        self._reload_rows()
        self.activity.emit(f"已删除「{e.name}」")

    def _on_control_changed(self, e: MemoryEntry, key: str) -> None:
        if e.id:
            self.db.update_memory(e)
        label = dict(CONTROL_CHOICES).get(key, key)
        self.activity.emit(f"「{e.name}」修改方式已切换为{label}")

    # ============================================================ 启动 / 停止
    def _toggle_launch(self) -> None:
        if not self.t:
            return
        if self.launcher.is_running(self.t.id or 0):
            self._stop()
        else:
            self._launch()

    def _launch(self) -> None:
        if not self.t:
            return
        t = self.db.get_trainer(self.t.id or 0) or self.t
        if not t.installed:
            self.activity.emit("该条目尚未关联游戏本体，请先「编辑信息」填入 exe 路径")
            return
        if t.online_risk:
            box = QMessageBox(self)
            box.setWindowTitle("联机风险提示")
            box.setText(
                f"《{t.game_title}》包含联机 / 在线模式。\n\n"
                "请确认当前处于离线或单人剧情模式，且未进入任何多人模式。\n"
                "在多人环境使用内存修改可能导致封号。"
            )
            box.setIcon(QMessageBox.Icon.Warning)
            box.addButton("我确认仅在单机使用", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.result() != QMessageBox.DialogCode.Accepted:
                return
        ok, msg = self.launcher.start(t)
        self.activity.emit(msg)
        if ok:
            self._refresh_session()
            self._fill_recent(t.id or 0)

    def _stop(self) -> None:
        if not self.t:
            return
        ok, msg = self.launcher.stop(self.t.id or 0)
        self.activity.emit(msg)

    def _toggle_fav(self) -> None:
        if not self.t:
            return
        fav = self.db.toggle_favorite(self.t.id or 0)
        self.t.favorite = fav
        self._refresh_buttons()
        self.favorite_changed.emit(self.t.id or 0)

    def _open_folder(self) -> None:
        if not self.t:
            return
        p = self.t.exe_path or self.t.work_dir
        if p:
            reveal_in_explorer(p)
        else:
            open_local_path(str(config.TRAINER_DIR))

    # ============================================================ 进程附加
    def _auto_attach(self) -> None:
        if not self.t:
            return
        exe = self.t.exe_path
        if not exe:
            self._pick_process()
            return
        name = os.path.basename(exe)
        pids = self.eng.find_pids(name)
        if not pids:
            self._pick_process(name)
            return
        if len(pids) == 1:
            ok, msg = self.eng.attach_pid(pids[0][0])
            self.activity.emit(msg)
            return
        self._pick_process(name)

    def _pick_process(self, default: str = "") -> None:
        exe = self.t.exe_path if self.t else ""
        guess = default or (os.path.basename(exe) if exe else "")
        dlg = ProcessPickDialog(self.eng, guess, self)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.pid:
            return
        ok, msg = self.eng.attach_pid(dlg.pid)
        self.activity.emit(msg)

    def auto_attach_pid(self, pid: int) -> None:
        """启动游戏后由主窗口调用。"""
        if self.eng.is_attached or not pid:
            return
        ok, msg = self.eng.attach_pid(pid)
        self.activity.emit(msg)

    # ============================================================ 读写
    def _write(self, entry: MemoryEntry, value) -> None:
        if not self.eng.is_attached:
            self.activity.emit("尚未附加进程，请先点「附加进程」")
            return
        ok, msg = self.eng.write(entry, value)
        self.activity.emit(msg)
        for row in self.rows:
            if row.entry.id == entry.id:
                row.notify_write_done(ok, value)

    def _tick(self) -> None:
        if not self.t:
            return
        if self.launcher.is_running(self.t.id or 0):
            self._refresh_session()
        if not self.eng.is_attached or not self.rows:
            return
        if not self.eng.alive():
            self.eng.detach("目标进程已退出")
            return
        for row in self.rows:
            if not row.entry.enabled:
                continue
            row.show_value(self.eng.read(row.entry))

    def _on_attached(self, pid: int, name: str) -> None:
        self.lbl_attach.setText(f"● 已附加 {name}（PID {pid}）")
        self.lbl_attach.setStyleSheet(
            "QLabel{font-size:12px; font-weight:600; color:#2E9E5B; background:transparent;}"
        )
        self.btn_detach.setEnabled(True)

    def _on_detached(self, reason: str) -> None:
        self.lbl_attach.setText("○ 未附加进程")
        self.lbl_attach.setStyleSheet(
            "QLabel{font-size:12px; font-weight:600; color:#6B7280; background:transparent;}"
        )
        self.btn_detach.setEnabled(False)
        for row in self.rows:
            row.lbl_value.setText("—")
            row.lbl_value.setStyleSheet(_VALUE_STYLE)
        if reason:
            self.activity.emit(f"已分离进程（{reason}）")

    # ============================================================ 热键表
    def _fill_table(self, options: list[Option]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for o in options:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, val in enumerate((o.key, o.desc, o.note)):
                it = QTableWidgetItem(val)
                it.setToolTip(val)
                self.table.setItem(r, c, it)
        self.table.blockSignals(False)

    def _save_options(self) -> None:
        if not self.t:
            return
        opts: list[Option] = []
        for r in range(self.table.rowCount()):
            def gv(c: int) -> str:
                it = self.table.item(r, c)
                return it.text().strip() if it else ""

            if not (gv(0) or gv(1)):
                continue
            opts.append(Option(gv(0), gv(1), gv(2)))
        self.t.options = opts
        self.db.update_trainer(self.t)

    def _add_option_row(self) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c in range(3):
            self.table.setItem(r, c, QTableWidgetItem(""))
        self.table.editItem(self.table.item(r, 0))
        self._save_options()

    def _del_option_row(self) -> None:
        r = self.table.currentRow()
        if r < 0:
            return
        self.table.removeRow(r)
        self._save_options()

    def _on_option_edited(self, _item) -> None:
        if getattr(self, "_loading", False):
            return
        self._save_options()

    def _copy_options(self) -> None:
        if not self.t:
            return
        from PySide6.QtWidgets import QApplication

        text = "\n".join(
            f"{o.key}\t{o.desc}" + (f"\t{o.note}" if o.note else "") for o in self.t.options
        )
        QApplication.clipboard().setText(text)
        self.activity.emit("已复制功能列表到剪贴板")

    def _paste_options(self) -> None:
        if not self.t:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("批量粘贴功能列表")
        dlg.resize(520, 340)
        v = QVBoxLayout(dlg)
        v.addWidget(
            QLabel(
                "每行一条，格式：热键 空格/Tab 功能说明\n例如：Num 1  无限生命\nCtrl+Num 2  无限弹药"
            )
        )
        ed = QTextEdit()
        v.addWidget(ed, 1)
        btns = QHBoxLayout()
        okb = QPushButton("导入")
        cancel = QPushButton("取消")
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(okb)
        v.addLayout(btns)
        cancel.clicked.connect(dlg.reject)
        okb.clicked.connect(dlg.accept)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        opts: list[Option] = []
        for ln in [x.strip() for x in ed.toPlainText().splitlines() if x.strip()]:
            parts = [p.strip() for p in (ln.split("\t") if "\t" in ln else ln.split(None, 1))]
            if len(parts) == 1:
                opts.append(Option("", parts[0]))
            else:
                opts.append(Option(parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
        if not opts:
            return
        self.t.options = opts
        self.db.update_trainer(self.t)
        self._fill_table(opts)
        self.activity.emit(f"已导入 {len(opts)} 条功能")

    def _on_notes_changed(self) -> None:
        if not self.t or getattr(self, "_loading", False):
            return
        self.t.notes = self.notes.toPlainText()
        self.db.update_trainer(self.t)

    # ============================================================ 会话状态
    def _refresh_buttons(self) -> None:
        if not self.t:
            return
        self.btn_fav.setText("★ 已收藏" if self.t.favorite else "☆ 收藏")
        self.btn_folder.setEnabled(bool(self.t.installed))

    def _refresh_session(self) -> None:
        if not self.t:
            return
        tid = self.t.id or 0
        if self.launcher.is_running(tid):
            s = self.launcher.session(tid)
            el = self.launcher.elapsed(tid)
            self.lbl_session.setText(f"● 运行中（PID {s.pid if s else '-'}）· 已运行 {human_duration(el)}")
            self.lbl_session.setStyleSheet(
                "QLabel{font-size:12px; font-weight:600; color:#B26B00; background:transparent;}"
            )
            self.btn_launch.setText("停止游戏")
            self.btn_stop.setEnabled(True)
        else:
            last = self.t.last_run_at or "从未"
            self.lbl_session.setText(f"○ 未运行 · 上次 {last} · 累计 {self.t.run_count} 次")
            self.lbl_session.setStyleSheet(
                "QLabel{font-size:12px; font-weight:600; color:#6B7280; background:transparent;}"
            )
            self.btn_launch.setText("启动游戏")
            self.btn_stop.setEnabled(False)

    def _fill_recent(self, tid: int) -> None:
        self.recent.clear()
        for rec in self.db.list_records(tid, limit=12):
            status_map = {
                "running": "运行中",
                "finished": "已结束",
                "killed": "已终止",
                "failed": "异常退出",
            }
            text = status_map.get(rec.status, rec.status)
            dur = human_duration(rec.duration_sec) if rec.duration_sec else "-"
            self.recent.addItem(QListWidgetItem(f"{rec.started_at}  {text}  时长 {dur}"))

    def _on_session_end(self, tid: int, code: int) -> None:
        if self.t and (self.t.id or 0) == tid:
            self._refresh_session()
            self._fill_recent(tid)
            self.activity.emit(f"进程结束（退出码 {code}）")
