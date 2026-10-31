"""右侧详情 / 会话管理面板：一个修改器的"管理界面"。

包含：元信息、一键启动与停止、运行会话实时状态、热键功能表（可编辑）、
备注、最近启动记录。
"""
from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import config
from ..core.models import Option, Trainer, human_duration
from .widgets import (
    ChipLabel,
    CoverLabel,
    HLine,
    open_local_path,
    reveal_in_explorer,
    warn,
)


class DetailPanel(QWidget):
    """单例面板：通过 set_trainer() 切换内容。"""

    # 需要主窗口协同的动作
    activity = Signal(str)                  # 状态栏文本
    favorite_changed = Signal(int)          # 收藏状态变化 → 刷新卡片
    options_changed = Signal(int)           # 元数据变化
    delete_requested = Signal(int)
    edit_requested = Signal(int)

    def __init__(self, db, launcher, parent=None):
        super().__init__(parent)
        self.db = db
        self.launcher = launcher
        self.t: Trainer | None = None

        self.setMinimumWidth(330)
        self._build()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick_session)
        self._timer.start()

        launcher.sessionEnded.connect(self._on_session_end)

    # ------------------------------------------------------------ 构建
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # 头部：封面 + 标题
        head = QHBoxLayout()
        head.setSpacing(12)
        self.cover = CoverLabel("GTV", "#3B6EA5", w=104, h=72, radius=9, text_scale=0.8)
        head.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignTop)

        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.lbl_game = QLabel("未选择修改器")
        self.lbl_game.setStyleSheet("font-size:16px; font-weight:700;")
        self.lbl_game.setWordWrap(True)
        titles.addWidget(self.lbl_game)
        self.lbl_sub = QLabel("从左侧选择一个修改器查看详情")
        self.lbl_sub.setObjectName("muted")
        self.lbl_sub.setWordWrap(True)
        titles.addWidget(self.lbl_sub)
        self.chips = QHBoxLayout()
        self.chips.setSpacing(4)
        titles.addLayout(self.chips)
        head.addLayout(titles, 1)
        root.addLayout(head)

        self.warnbox = QLabel("")
        self.warnbox.setObjectName("warnbox")
        self.warnbox.setWordWrap(True)
        self.warnbox.hide()
        root.addWidget(self.warnbox)

        # 按钮区
        btns = QHBoxLayout()
        btns.setSpacing(6)
        self.btn_launch = QPushButton("启动修改器")
        self.btn_launch.setObjectName("primary")
        self.btn_launch.clicked.connect(self._toggle_launch)
        btns.addWidget(self.btn_launch, 1)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.clicked.connect(self._stop)
        btns.addWidget(self.btn_stop, 0)
        self.btn_page = QPushButton("官方页面")
        self.btn_page.clicked.connect(lambda: self.t and open_local_path(self.t.source_url))
        btns.addWidget(self.btn_page, 0)
        root.addLayout(btns)

        btns2 = QHBoxLayout()
        btns2.setSpacing(6)
        self.btn_fav = QPushButton("☆ 收藏")
        self.btn_fav.clicked.connect(self._toggle_fav)
        btns2.addWidget(self.btn_fav)
        self.btn_folder = QPushButton("所在目录")
        self.btn_folder.clicked.connect(self._open_folder)
        btns2.addWidget(self.btn_folder)
        self.btn_edit = QPushButton("编辑信息")
        self.btn_edit.clicked.connect(lambda: self.t and self.edit_requested.emit(self.t.id or 0))
        btns2.addWidget(self.btn_edit)
        root.addLayout(btns2)

        # 会话状态卡
        self.session_box = QFrame()
        self.session_box.setObjectName("panel")
        sb = QVBoxLayout(self.session_box)
        sb.setContentsMargins(12, 10, 12, 10)
        sb.setSpacing(4)
        self.lbl_session = QLabel("未运行")
        self.lbl_session.setStyleSheet("font-weight:600;")
        sb.addWidget(self.lbl_session)
        self.lbl_session_sub = QLabel("")
        self.lbl_session_sub.setObjectName("muted")
        sb.addWidget(self.lbl_session_sub)
        root.addWidget(self.session_box)

        # 功能 / 热键表
        root.addWidget(QLabel("功能与热键（可双击编辑，自动保存）"))
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
        self.table.setMaximumHeight(230)
        root.addWidget(self.table)

        row = QHBoxLayout()
        row.setSpacing(6)
        b_add = QPushButton("+ 新增行")
        b_add.clicked.connect(self._add_option_row)
        b_del = QPushButton("- 删除行")
        b_del.clicked.connect(self._del_option_row)
        b_paste = QPushButton("批量粘贴导入")
        b_paste.clicked.connect(self._paste_options)
        b_copy = QPushButton("复制全部")
        b_copy.clicked.connect(self._copy_options)
        for b in (b_add, b_del, b_paste, b_copy):
            row.addWidget(b)
        root.addLayout(row)

        # 备注
        root.addWidget(QLabel("备注"))
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("记录使用该 Trainer 的注意事项，例如：需先启动游戏、某些选项会导致任务卡死…")
        self.notes.setFixedHeight(78)
        self.notes.textChanged.connect(self._on_notes_changed)
        root.addWidget(self.notes)

        root.addWidget(HLine())
        root.addWidget(QLabel("最近启动记录"))
        self.recent = QListWidget()
        self.recent.setMaximumHeight(120)
        self.recent.itemDoubleClicked.connect(lambda _i: None)
        root.addWidget(self.recent)

        root.addStretch(1)
        self.setEnabled(False)

    # ------------------------------------------------------------ 数据
    def set_trainer(self, t: Trainer | None) -> None:
        self.t = t
        self.setEnabled(t is not None)
        if t is None:
            self.lbl_game.setText("未选择修改器")
            self.lbl_sub.setText("从左侧选择一个修改器查看详情")
            self._clear_chips()
            self.table.setRowCount(0)
            self.recent.clear()
            self.notes.blockSignals(True)
            self.notes.clear()
            self.notes.blockSignals(False)
            self.lbl_session.setText("未运行")
            self.lbl_session_sub.setText("")
            self.warnbox.hide()
            return

        self._loading = True
        self.lbl_game.setText(t.game_title or t.title)
        self.lbl_sub.setText(f"{t.title} · {t.author or '未知来源'} · {config.SOURCE_LABEL.get(t.source, t.source)}")
        self.cover.set_content(t.game_title or t.title, t.cover_color)

        self._clear_chips()
        self.chips.addWidget(ChipLabel(t.category))
        for tag in t.tags[:4]:
            self.chips.addWidget(ChipLabel(tag, color="#2F6FEB"))
        self.chips.addStretch(1)

        self.warnbox.setVisible(bool(t.online_risk))
        if t.online_risk:
            self.warnbox.setText(
                "⚠ 该游戏包含联机模式。请仅在离线 / 单人剧情模式中使用修改器，"
                "严禁进入多人模式，否则可能触发反作弊并导致账号处罚。"
            )

        self._fill_table(t.options)
        self.notes.blockSignals(True)
        self.notes.setPlainText(t.notes or "")
        self.notes.blockSignals(False)
        self._fill_recent(t.id or 0)
        self._refresh_buttons()
        self._refresh_session()
        self._loading = False

    def _clear_chips(self) -> None:
        while self.chips.count():
            item = self.chips.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

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

    def _fill_recent(self, tid: int) -> None:
        self.recent.clear()
        for rec in self.db.list_records(tid, limit=12):
            status_map = {
                "running": ("运行中", "#B26B00"),
                "finished": ("已结束", "#2E9E5B"),
                "killed": ("已终止", "#6B7280"),
                "failed": ("异常退出", "#D64545"),
            }
            text, _c = status_map.get(rec.status, (rec.status, "#6B7280"))
            dur = human_duration(rec.duration_sec) if rec.duration_sec else "-"
            item = QListWidgetItem(f"{rec.started_at}   {text}   时长 {dur}   PID {rec.pid or '-'}")
            self.recent.addItem(item)

    # ------------------------------------------------------------ 交互
    def _toggle_launch(self) -> None:
        if not self.t:
            return
        tid = self.t.id or 0
        if self.launcher.is_running(tid):
            self._stop()
        else:
            self._launch()

    def _launch(self) -> None:
        if not self.t:
            return
        t = self.db.get_trainer(self.t.id or 0) or self.t
        if not t.installed:
            self.activity.emit("该修改器尚未导入本体，请先添加本地文件或下载链接")
            return
        if t.online_risk:
            box = QMessageBox(self)
            box.setWindowTitle("联机风险提示")
            box.setText(
                f"《{t.game_title}》包含联机 / 在线模式。\n\n"
                "请确认当前处于离线或单人剧情模式，且未进入任何多人模式。\n"
                "在多人环境使用修改器可能导致封号。"
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

    # ------------------------------------------------------------ 表格编辑
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
        self.options_changed.emit(self.t.id or 0)

    def _copy_options(self) -> None:
        if not self.t:
            return
        text = "\n".join(f"{o.key}\t{o.desc}" + (f"\t{o.note}" if o.note else "") for o in self.t.options)
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(text)
        self.activity.emit("已复制功能列表到剪贴板")

    def _paste_options(self) -> None:
        if not self.t:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("批量粘贴功能列表")
        dlg.resize(520, 360)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("每行一条，支持「热键 空格/Tab 功能说明」，例如：\nNum 1  无限生命\nCtrl+Num 2  无限弹药\n（留行常被忽略，坐标/生效条件可写在备注列）"))
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
        lines = [ln.strip() for ln in ed.toPlainText().splitlines() if ln.strip()]
        opts: list[Option] = []
        for ln in lines:
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
        self.options_changed.emit(self.t.id or 0)
        self.activity.emit(f"已导入 {len(opts)} 条功能")

    def _on_notes_changed(self) -> None:
        if not self.t or getattr(self, "_loading", False):
            return
        self.t.notes = self.notes.toPlainText()
        self.db.update_trainer(self.t)

    # ------------------------------------------------------------ 实时
    def _refresh_buttons(self) -> None:
        if not self.t:
            return
        self.btn_fav.setText("★ 已收藏" if self.t.favorite else "☆ 收藏")
        installed = bool(self.t.installed)
        self.btn_folder.setEnabled(installed)
        self.btn_launch.setEnabled(True)
        self.btn_launch.setText("启动修改器" if installed else "未导入本体（点击仍需选择）")

    def _refresh_session(self) -> None:
        if not self.t:
            return
        tid = self.t.id or 0
        running = self.launcher.is_running(tid)
        if running:
            s = self.launcher.session(tid)
            el = self.launcher.elapsed(tid)
            self.lbl_session.setText(f"● 运行中（PID {s.pid if s else '-'}）")
            self.lbl_session.setStyleSheet("color:#B26B00; font-weight:700;")
            self.lbl_session_sub.setText(f"已运行 {human_duration(el)}　·　关闭本程序会一并结束进程")
            self.btn_launch.setText("停止")
            self.btn_launch.setObjectName("primary")
            self.btn_stop.setEnabled(True)
        else:
            self.lbl_session.setText("○ 未运行")
            self.lbl_session.setStyleSheet("color:#6B7280; font-weight:600;")
            last = self.t.last_run_at or "从未"
            self.lbl_session_sub.setText(f"上次启动：{last}　·　累计 {self.t.run_count} 次")
            self.btn_launch.setText("启动修改器")
            self.btn_stop.setEnabled(False)
        self.btn_launch.setStyle(self.btn_launch.style())

    def _tick_session(self) -> None:
        if not self.t or not self.launcher.is_running(self.t.id or 0):
            return
        self._refresh_session()

    def _on_session_end(self, tid: int, code: int) -> None:
        if self.t and (self.t.id or 0) == tid:
            self._refresh_session()
            self._fill_recent(tid)
            self.activity.emit(f"进程结束（退出码 {code}）")
