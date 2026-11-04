"""杂项对话框：编辑条目、启动记录、设置、关于。"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import config
from ..core.models import LaunchRecord, Trainer, human_duration
from .widgets import open_local_path


class EditDialog(QDialog):
    def __init__(self, db, trainer: Trainer, parent=None):
        super().__init__(parent)
        self.db = db
        self.t = trainer
        self.setWindowTitle(f"编辑 · {trainer.game_title}")
        self.resize(560, 460)

        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(12)
        f = QFormLayout()
        f.setSpacing(9)

        self.e_title = QLineEdit(trainer.title)
        self.e_game = QLineEdit(trainer.game_title)
        self.e_author = QLineEdit(trainer.author)
        self.e_ver = QLineEdit(trainer.version)
        self.e_url = QLineEdit(trainer.source_url)
        self.c_cat = QComboBox()
        self.c_cat.setEditable(True)
        cats = [c for c, _n in db.categories_with_count()] + config.DEFAULT_CATEGORIES
        seen = set()
        for c in cats:
            if c not in seen:
                seen.add(c)
                self.c_cat.addItem(c)
        self.c_cat.setCurrentText(trainer.category)
        self.e_tags = QLineEdit(", ".join(trainer.tags))
        self.e_exe = QLineEdit(trainer.exe_path)
        self.chk_admin = QCheckBox("以管理员权限启动（部分游戏需要）")
        self.chk_admin.setChecked(trainer.run_as_admin)
        self.chk_risk = QCheckBox("该游戏含联机模式（显示强提示）")
        self.chk_risk.setChecked(trainer.online_risk)
        self.e_args = QLineEdit(trainer.args)
        self.e_color = QLineEdit(trainer.cover_color)

        b_exe = QPushButton("…")
        b_exe.setFixedWidth(34)
        b_exe.clicked.connect(self._pick_exe)
        row_exe = QHBoxLayout()
        row_exe.addWidget(self.e_exe, 1)
        row_exe.addWidget(b_exe)

        f.addRow("游戏名", self.e_game)
        f.addRow("标题", self.e_title)
        f.addRow("作者/来源", self.e_author)
        f.addRow("版本", self.e_ver)
        f.addRow("分类", self.c_cat)
        f.addRow("标签（逗号分隔）", self.e_tags)
        f.addRow("官方页面", self.e_url)
        f.addRow("主程序路径", row_exe)
        f.addRow("启动参数", self.e_args)
        f.addRow("封面颜色", self.e_color)
        f.addRow("", self.chk_admin)
        f.addRow("", self.chk_risk)
        v.addLayout(f, 1)

        foot = QHBoxLayout()
        foot.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("保存")
        ok.setObjectName("primary")
        ok.clicked.connect(self._save)
        foot.addWidget(cancel)
        foot.addWidget(ok)
        v.addLayout(foot)

    def _pick_exe(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "选择主程序", "", "可执行文件 (*.exe)")
        if p:
            self.e_exe.setText(p)

    def _save(self) -> None:
        t = self.t
        t.title = self.e_title.text().strip() or t.title
        t.game_title = self.e_game.text().strip() or t.game_title
        t.author = self.e_author.text().strip()
        t.version = self.e_ver.text().strip()
        t.source_url = self.e_url.text().strip()
        t.category = self.c_cat.currentText().strip() or "其他"
        t.tags = [x.strip() for x in self.e_tags.text().replace("，", ",").split(",") if x.strip()]
        t.exe_path = self.e_exe.text().strip()
        t.work_dir = str(Path(t.exe_path).parent) if t.exe_path else ""
        t.args = self.e_args.text().strip()
        t.run_as_admin = self.chk_admin.isChecked()
        t.online_risk = self.chk_risk.isChecked()
        t.cover_color = self.e_color.text().strip() or t.cover_color
        if t.exe_path:
            t.source = t.source if t.source != config.SOURCE_BUILTIN else config.SOURCE_LOCAL
        self.db.update_trainer(t)
        self.accept()


STATUS_STYLE = {
    "running": ("运行中", "#B26B00"),
    "finished": ("正常结束", "#2E9E5B"),
    "killed": ("被终止", "#6B7280"),
    "failed": ("异常退出", "#D64545"),
}


class RecordsDialog(QDialog):
    """启动记录管理。"""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("启动记录")
        self.resize(820, 520)

        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(10)

        top = QHBoxLayout()
        self.c_range = QComboBox()
        self.c_range.addItems(["全部记录", "最近 7 天", "最近 30 天", "最近 90 天"])
        self.c_range.currentIndexChanged.connect(self.reload)
        self.lbl_stat = QLabel("")
        self.lbl_stat.setObjectName("muted")
        top.addWidget(QLabel("范围"))
        top.addWidget(self.c_range)
        top.addSpacing(12)
        top.addWidget(self.lbl_stat, 1)

        b_export = QPushButton("导出 CSV")
        b_export.clicked.connect(self._export)
        b_clear = QPushButton("清理旧记录")
        b_clear.setObjectName("danger")
        b_clear.clicked.connect(self._clear)
        top.addWidget(b_export)
        top.addWidget(b_clear)
        v.addLayout(top)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["开始时间", "修改器", "PID", "时长", "状态", "说明"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        from PySide6.QtWidgets import QHeaderView

        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.table, 1)

        self.reload()

    def reload(self) -> None:
        idx = self.c_range.currentIndex()
        days = {0: None, 1: 7, 2: 30, 3: 90}[idx]
        if days is None:
            recs = self.db.list_records(limit=2000)
        else:
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            recs = self.db.list_records_range(since)
        self.table.setRowCount(0)
        total_sec = 0
        for r in recs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            total_sec += r.duration_sec
            text, color = STATUS_STYLE.get(r.status, (r.status, "#6B7280"))
            vals = [
                r.started_at,
                r.trainer_title or str(r.trainer_id or "-"),
                str(r.pid or "-"),
                human_duration(r.duration_sec) if r.duration_sec else "-",
                text,
                r.message,
            ]
            for i, val in enumerate(vals):
                it = QTableWidgetItem(val)
                it.setToolTip(val)
                if i == 4:
                    it.setForeground(Qt.GlobalColor.black)
                    it.setData(Qt.ItemDataRole.DecorationRole, None)
                self.table.setItem(row, i, it)
        self.lbl_stat.setText(f"共 {len(recs)} 条 · 累计运行时长 {human_duration(total_sec)}")

    def _export(self) -> None:
        p, _ = QFileDialog.getSaveFileName(self, "导出 CSV", "gtv-launch-records.csv", "CSV (*.csv)")
        if not p:
            return
        recs = self.db.list_records(limit=5000)
        with open(p, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["开始时间", "修改器ID", "修改器", "PID", "时长(秒)", "状态", "说明"])
            for r in recs:
                w.writerow([r.started_at, r.trainer_id, r.trainer_title, r.pid, r.duration_sec, r.status, r.message])
        open_local_path(p)

    def _clear(self) -> None:
        d, ok = QInputSpinDialog.get_days(self)
        if not ok:
            return
        n = self.db.clear_records(None if d == 0 else d)
        QMessageBox.information(self, "完成", f"已清理 {n} 条记录")
        self.reload()


class QInputSpinDialog(QDialog):
    @staticmethod
    def get_days(parent) -> tuple[int, bool]:
        dlg = QDialog(parent)
        dlg.setWindowTitle("清理旧记录")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("保留最近多少天？\n填 0 表示清空全部记录。"))
        sp = QSpinBox()
        sp.setRange(0, 3650)
        sp.setValue(90)
        v.addWidget(sp)
        foot = QHBoxLayout()
        ok = QPushButton("确定")
        cancel = QPushButton("取消")
        foot.addStretch(1)
        foot.addWidget(cancel)
        foot.addWidget(ok)
        v.addLayout(foot)
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        res = dlg.exec()
        return sp.value(), res == QDialog.DialogCode.Accepted


class SettingsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("设置")
        self.resize(560, 420)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(12)

        f = QFormLayout()
        f.setSpacing(10)

        # 修改器库目录：可自定义（默认 D:\cheat），立即生效于之后的导入
        self.e_dir = QLineEdit(str(config.TRAINER_DIR))
        b_dir = QPushButton("浏览…")
        b_dir.setFixedWidth(64)
        b_dir.clicked.connect(self._pick_dir)
        row_dir = QHBoxLayout()
        row_dir.setSpacing(6)
        row_dir.addWidget(self.e_dir, 1)
        row_dir.addWidget(b_dir)
        f.addRow("修改器库目录", row_dir)
        tip_dir = QLabel("新目录对之后导入的文件生效；已有文件位置不变。")
        tip_dir.setObjectName("muted")
        f.addRow("", tip_dir)

        f.addRow("数据库", QLabel(config.db_url_display()))
        self.e_pwd = QLineEdit(db.get_setting("archive_passwords", ",".join(config.DEFAULT_ARCHIVE_PASSWORDS)))
        f.addRow("解压候选密码（逗号分隔）", self.e_pwd)
        self.chk_admin = QCheckBox("默认以管理员权限启动")
        self.chk_admin.setChecked(db.get_setting("default_admin", "0") == "1")
        f.addRow("", self.chk_admin)
        self.chk_tray = QCheckBox("关闭窗口时最小化到托盘")
        self.chk_tray.setChecked(db.get_setting("minimize_to_tray", "1") == "1")
        f.addRow("", self.chk_tray)
        self.chk_confirm = QCheckBox("启动含联机模式的游戏时弹出确认")
        self.chk_confirm.setChecked(db.get_setting("confirm_online", "1") == "1")
        f.addRow("", self.chk_confirm)
        v.addLayout(f, 1)

        row = QHBoxLayout()
        b_open = QPushButton("打开库目录")
        b_open.clicked.connect(lambda: open_local_path(str(config.TRAINER_DIR)))
        b_reseed = QPushButton("重置内置目录")
        b_reseed.clicked.connect(self._reseed)
        row.addWidget(b_open)
        row.addWidget(b_reseed)
        row.addStretch(1)
        v.addLayout(row)

        note = QLabel(config.DISCLAIMER)
        note.setObjectName("warnbox")
        note.setWordWrap(True)
        v.addWidget(note)

        foot = QHBoxLayout()
        foot.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("保存")
        ok.setObjectName("primary")
        ok.clicked.connect(self._save)
        foot.addWidget(cancel)
        foot.addWidget(ok)
        v.addLayout(foot)

    def _pick_dir(self) -> None:
        start = self.e_dir.text().strip() or str(config.TRAINER_DIR)
        d = QFileDialog.getExistingDirectory(self, "选择修改器库目录", start)
        if d:
            self.e_dir.setText(d)

    def _save(self) -> None:
        self.db.set_setting("archive_passwords", self.e_pwd.text().strip())
        self.db.set_setting("default_admin", "1" if self.chk_admin.isChecked() else "0")
        self.db.set_setting("minimize_to_tray", "1" if self.chk_tray.isChecked() else "0")
        self.db.set_setting("confirm_online", "1" if self.chk_confirm.isChecked() else "0")

        # 修改器库目录：校验可创建后立即生效（对之后导入的文件生效）
        new_dir = self.e_dir.text().strip()
        if new_dir and Path(new_dir) != config.TRAINER_DIR:
            from ..core import config as cfg

            try:
                p = Path(new_dir)
                p.mkdir(parents=True, exist_ok=True)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "目录不可用", f"无法使用该目录：{exc}\n\n设置未保存该目录项。")
            else:
                cfg.TRAINER_DIR = p
                self.db.set_setting("trainer_dir", str(p))
                QMessageBox.information(
                    self, "已生效",
                    f"修改器库目录已切换为：\n{p}\n\n（对之后导入的文件生效，已有文件位置不变）",
                )
        self.accept()

    def _reseed(self) -> None:
        from ..core.catalog import load_seed

        added = 0
        for item in load_seed():
            if self.db.upsert_seed_item(item):
                added += 1
        QMessageBox.information(self, "完成", f"已刷新内置目录，新增 {added} 条")
        self.accept()


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 GTV")
        self.resize(520, 320)
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(10)
        title = QLabel(f"GTV · 单机游戏修改器管理器 v{config.APP_VERSION}")
        title.setStyleSheet("font-size:16px; font-weight:700;")
        v.addWidget(title)
        body = QLabel(
            "一个用于**整理 / 检索 / 启停单机游戏修改器**的本地桌面工具。\n\n"
            "· 内置 flingtrainer.com 修改器目录索引（元数据，不含程序本体）\n"
            "· 支持本地文件、文件夹、下载链接、目录扫描四种导入方式\n"
            "· 分类、标签、收藏、热键清单、备注、启动记录统一管理\n"
            "· 数据存放于 SQLite："
            + str(config.DB_PATH)
        )
        body.setWordWrap(True)
        v.addWidget(body, 1)
        note = QLabel(config.DISCLAIMER)
        note.setObjectName("warnbox")
        note.setWordWrap(True)
        v.addWidget(note)
        b = QPushButton("知道了")
        b.setObjectName("primary")
        b.clicked.connect(self.accept)
        v.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)
