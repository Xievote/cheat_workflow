"""内存修改页：附加游戏进程 + 按地址条目自动生成交互控件 + 实时回读。

作为中央区第二个标签页嵌入主窗口：
* 选中左侧卡片 → set_trainer() 加载该游戏的内存地址条目
* 「附加进程」→ 按 exe 名自动查找，找不到/多个时弹选择框（可手输 PID）
* 每条条目一行：名称 + 实时值 + 控件（滑动条/数值框/按钮/开关）
* QTimer 周期回读当前值；目标进程退出自动分离
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..core.memory_engine import MemoryEngine
from ..core.models import MemoryEntry, Trainer
from .memory_dialog import MemoryEntryDialog
from .widgets import confirm

READ_INTERVAL_MS = 500          # 实时回读周期
WRITE_FLASH_MS = 900            # 写入成功后的高亮时长


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
            # 首次加载：列出全部进程（去重）
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
    """一行内存条目：名称 + 实时值 + 控件 + 编辑/删除。"""

    edited = Signal(object)      # MemoryEntry（编辑保存后）
    deleted = Signal(object)     # MemoryEntry
    activity = Signal(str)
    write_requested = Signal(object, object)   # entry, value

    def __init__(self, entry: MemoryEntry, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.entry = entry
        self._flash_until = 0.0
        self._writing = False     # 写入时屏蔽回读刷新，避免控件抖动

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(12)

        # ---- 左：名称 + 地址
        left = QVBoxLayout()
        left.setSpacing(2)
        self.lbl_name = QLabel(entry.name)
        self.lbl_name.setStyleSheet("QLabel{font-size:14px; font-weight:700; color:#1F2430; background:transparent;}")
        left.addWidget(self.lbl_name)
        self.lbl_addr = QLabel(entry.addr_display)
        self.lbl_addr.setObjectName("muted")
        self.lbl_addr.setStyleSheet("QLabel{font-size:11px; color:#9AA3AF; background:transparent;}")
        left.addWidget(self.lbl_addr)
        if entry.note:
            note = QLabel(entry.note)
            note.setStyleSheet("QLabel{font-size:11px; color:#6B7280; background:transparent;}")
            left.addWidget(note)
        if not entry.enabled:
            self.lbl_name.setText(f"{entry.name}（已停用）")
        root.addLayout(left, 2)

        # ---- 中：当前值
        self.lbl_value = QLabel("—")
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPointSize(12)
        f.setBold(True)
        self.lbl_value.setFont(f)
        self.lbl_value.setMinimumWidth(90)
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_value.setStyleSheet(
            "QLabel{color:#1F2430; background:#F3F5F8; border-radius:8px; padding:6px 10px;}"
        )
        self.lbl_value.setToolTip("实时读取到的当前值（每 0.5 秒刷新）")
        root.addWidget(self.lbl_value, 0)

        # ---- 右：控件
        self._ctl = self._build_control(entry)
        if self._ctl:
            root.addWidget(self._ctl, 3)
        else:
            root.addStretch(3)

        # ---- 操作
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
    def _build_control(self, e: MemoryEntry):
        is_float = e.dtype in ("float", "double")
        if e.control == "slider":
            s = QSlider(Qt.Orientation.Horizontal)
            lo = int(round(e.minv / (e.step or 1)))
            hi = int(round(e.maxv / (e.step or 1)))
            if hi <= lo:
                hi = lo + 1
            s.setRange(lo, hi)
            s.setSingleStep(1)
            s.setPageStep(max(1, (hi - lo) // 20))
            s.setToolTip(f"范围 {e.minv:g} ~ {e.maxv:g}，步长 {e.step:g}，松开即写入")
            s.sliderReleased.connect(lambda: self._emit_write(self._slider_value(s)))
            return s
        if e.control == "spin":
            sb = QDoubleSpinBox()
            sb.setRange(e.minv, e.maxv)
            sb.setSingleStep(e.step or 1)
            sb.setDecimals(2 if is_float else 0)
            sb.setToolTip("修改后按回车写入内存")
            sb.editingFinished.connect(lambda: self._emit_write(sb.value()))
            return sb
        if e.control == "button":
            b = QPushButton(f"写入 {e.value}")
            b.setObjectName("primary")
            b.setToolTip(f"点击把 {e.value} 写入内存")
            b.clicked.connect(lambda: self._emit_write(float(e.value) if is_float else int(e.value, 0)))
            return b
        if e.control == "toggle":
            cb = QCheckBox(f"开启（写入 {e.value}，取消写 0）")
            cb.setStyleSheet("QCheckBox{font-size:13px;}")
            cb.toggled.connect(
                lambda on: self._emit_write(
                    (float(e.value) if is_float else int(e.value, 0)) if on else 0
                )
            )
            return cb
        return None

    def _slider_value(self, s: QSlider) -> float:
        return s.value() * (self.entry.step or 1)

    # ------------------------------------------------------------ 写入
    def _emit_write(self, value) -> None:
        if not self.entry.enabled:
            self.activity.emit(f"「{self.entry.name}」已停用，跳过写入")
            return
        self._writing = True
        cast = MemoryEngine.cast_value(self.entry.dtype, value)
        self.write_requested.emit(self.entry, cast)

    def notify_write_done(self, ok: bool, value) -> None:
        self._writing = False
        if ok:
            import time

            self._flash_until = time.time() + WRITE_FLASH_MS / 1000
            self.show_value(value, flash=True)

    # ------------------------------------------------------------ 显示
    def show_value(self, v, flash: bool = False) -> None:
        if v is None:
            self.lbl_value.setText("读取失败")
            self.lbl_value.setStyleSheet(
                "QLabel{color:#D64545; background:#FDF1F1; border-radius:8px; padding:6px 10px;}"
            )
            return
        if self._writing:
            return
        if isinstance(v, float) and not v.is_integer():
            text = f"{v:,.2f}"
        else:
            text = f"{int(v):,}" if float(v).is_integer() else f"{v:,.4f}"
        self.lbl_value.setText(text)
        self.lbl_value.setStyleSheet(
            "QLabel{color:#1F2430; background:#E8F0FE; border-radius:8px; padding:6px 10px;}"
            if flash else
            "QLabel{color:#1F2430; background:#F3F5F8; border-radius:8px; padding:6px 10px;}"
        )

    # ------------------------------------------------------------ 编辑/删除
    def _edit(self) -> None:
        e = MemoryEntryDialog.edit(self.entry.name, self.entry, self)
        if e:
            self.edited.emit(e)

    def _del(self) -> None:
        if confirm(self, "删除地址条目", f"确定删除「{self.entry.name}」（{self.entry.addr_display}）吗？"):
            self.deleted.emit(self.entry)


class MemoryPage(QWidget):
    activity = Signal(str)
    request_tab_switch = Signal()   # 请求主窗口切到本页

    def __init__(self, db, engine: MemoryEngine, parent=None):
        super().__init__(parent)
        self.db = db
        self.eng = engine
        self.t: Trainer | None = None
        self.rows: list[EntryRow] = []

        self._build()

        self._timer = QTimer(self)
        self._timer.setInterval(READ_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        engine.attached.connect(self._on_attached)
        engine.detached.connect(self._on_detached)
        engine.error.connect(lambda m: self.activity.emit(m))

    # ------------------------------------------------------------ UI
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        # 顶栏：目标游戏 + 附加控件
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.lbl_game = QLabel("未选择游戏")
        self.lbl_game.setStyleSheet("QLabel{font-size:15px; font-weight:700; color:#1F2430; background:transparent;}")
        bar.addWidget(self.lbl_game)
        self.lbl_attach = QLabel("○ 未附加进程")
        self.lbl_attach.setStyleSheet("QLabel{font-size:12px; font-weight:600; color:#6B7280; background:transparent;}")
        bar.addWidget(self.lbl_attach)
        bar.addStretch(1)

        self.btn_attach = QPushButton("附加进程")
        self.btn_attach.setObjectName("primary")
        self.btn_attach.clicked.connect(self._auto_attach)
        bar.addWidget(self.btn_attach)
        self.btn_pick = QPushButton("选择进程…")
        self.btn_pick.clicked.connect(self._pick_process)
        bar.addWidget(self.btn_pick)
        self.btn_detach = QPushButton("分离")
        self.btn_detach.clicked.connect(lambda: self.eng.detach("手动分离"))
        self.btn_detach.setEnabled(False)
        bar.addWidget(self.btn_detach)
        self.btn_add = QPushButton("+ 新增地址")
        self.btn_add.clicked.connect(self._add_entry)
        bar.addWidget(self.btn_add)
        root.addLayout(bar)

        tip = QLabel(
            "提示：先用 Cheat Engine 找到数值地址，点「+ 新增地址」录入；"
            "推荐指针路径（模块+偏移），游戏重启后依然有效。"
        )
        tip.setObjectName("muted")
        root.addWidget(tip)

        # 条目滚动区
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.host = QWidget()
        self.host.setObjectName("gridHost")
        self.host.setStyleSheet("QWidget#gridHost{background:transparent;}")
        self.host_v = QVBoxLayout(self.host)
        self.host_v.setContentsMargins(0, 4, 0, 4)
        self.host_v.setSpacing(10)
        self.host_v.addStretch(1)
        self.scroll.setWidget(self.host)
        root.addWidget(self.scroll, 1)

        self.lbl_empty = QLabel("从左侧选择一个游戏，然后「+ 新增地址」录入 Cheat Engine 找到的内存地址。")
        self.lbl_empty.setObjectName("muted")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setMinimumHeight(200)
        root.addWidget(self.lbl_empty)

    # ------------------------------------------------------------ 数据
    def set_trainer(self, t: Trainer | None) -> None:
        # 切换游戏时自动分离，避免把 A 游戏的地址写进 B 游戏进程
        if t is None or (self.t and self.t.id != t.id):
            if self.eng.is_attached:
                self.eng.detach("切换游戏")
        self.t = t
        if t is None:
            self.lbl_game.setText("未选择游戏")
        else:
            n = self.db.count_memory(t.id or 0)
            self.lbl_game.setText(f"{t.game_title or t.title}　·　{n} 条地址")
        self._reload_rows()

    def _reload_rows(self) -> None:
        # 清空旧行
        while self.host_v.count() > 1:
            item = self.host_v.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.rows.clear()

        entries: list[MemoryEntry] = self.db.list_memory(self.t.id) if self.t else []
        self.lbl_empty.setVisible(not entries)
        self.scroll.setVisible(bool(entries))
        for e in entries:
            row = EntryRow(e)
            row.edited.connect(self._on_entry_edited)
            row.deleted.connect(self._on_entry_deleted)
            row.activity.connect(self.activity)
            row.write_requested.connect(self._write)
            self.host_v.insertWidget(self.host_v.count() - 1, row)
            self.rows.append(row)

    def _add_entry(self) -> None:
        if not self.t:
            self.activity.emit("请先在左侧选择一个游戏条目")
            return
        e = MemoryEntryDialog.edit(self.t.game_title or self.t.title, None, self)
        if not e:
            return
        e.trainer_id = self.t.id
        e.sort = len(self.rows)
        e.id = self.db.add_memory(e)
        self._reload_rows()
        self.set_trainer(self.t)   # 刷新计数
        self.activity.emit(f"已新增地址「{e.name}」")

    def _on_entry_edited(self, e: MemoryEntry) -> None:
        self.db.update_memory(e)
        self._reload_rows()
        self.activity.emit(f"已保存「{e.name}」")

    def _on_entry_deleted(self, e: MemoryEntry) -> None:
        if e.id:
            self.db.delete_memory(e.id)
        self._reload_rows()
        self.set_trainer(self.t)
        self.activity.emit(f"已删除「{e.name}」")

    # ------------------------------------------------------------ 附加进程
    def _auto_attach(self) -> None:
        if not self.t:
            self.activity.emit("请先选择游戏条目")
            return
        exe = self.t.exe_path
        if not exe:
            self._pick_process()
            return
        import os

        name = os.path.basename(exe)
        pids = self.eng.find_pids(name)
        if not pids:
            self._pick_process(name)
            return
        if len(pids) == 1:
            ok, msg = self.eng.attach_pid(pids[0][0])
            self.activity.emit(msg)
            return
        # 同名多进程 → 弹选择
        self._pick_process(name)

    def _pick_process(self, default: str = "") -> None:
        if not self.t:
            self.activity.emit("请先选择游戏条目")
            return
        exe = self.t.exe_path
        guess = default or (os.path.basename(exe) if exe else "")
        dlg = ProcessPickDialog(self.eng, guess, self)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.pid:
            return
        ok, msg = self.eng.attach_pid(dlg.pid)
        self.activity.emit(msg)
        if ok:
            self.request_tab_switch.emit()

    def auto_attach_pid(self, pid: int) -> None:
        """启动游戏后由主窗口调用：尝试自动附加刚启动的进程。"""
        if self.eng.is_attached or not pid:
            return
        ok, msg = self.eng.attach_pid(pid)
        self.activity.emit(msg)
        if ok and self.t and self.db.count_memory(self.t.id or 0):
            self.request_tab_switch.emit()

    # ------------------------------------------------------------ 读写循环
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
        if not self.eng.is_attached or not self.rows:
            return
        if not self.eng.alive():
            self.eng.detach("目标进程已退出")
            return
        for row in self.rows:
            if not row.entry.enabled:
                continue
            v = self.eng.read(row.entry)
            row.show_value(v)

    def _on_attached(self, pid: int, name: str) -> None:
        self.lbl_attach.setText(f"● 已附加 {name}（PID {pid}）")
        self.lbl_attach.setStyleSheet("QLabel{font-size:12px; font-weight:600; color:#2E9E5B; background:transparent;}")
        self.btn_detach.setEnabled(True)

    def _on_detached(self, reason: str) -> None:
        self.lbl_attach.setText("○ 未附加进程")
        self.lbl_attach.setStyleSheet("QLabel{font-size:12px; font-weight:600; color:#6B7280; background:transparent;}")
        self.btn_detach.setEnabled(False)
        for row in self.rows:
            row.lbl_value.setText("—")
            row.lbl_value.setStyleSheet(
                "QLabel{color:#1F2430; background:#F3F5F8; border-radius:8px; padding:6px 10px;}"
            )
        if reason:
            self.activity.emit(f"已分离进程（{reason}）")
