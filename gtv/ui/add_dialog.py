"""添加修改器对话框：本地文件 / 文件夹 / 下载链接 / 目录扫描 / 手动录入。"""
from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, Signal
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
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import config, importer, scanner
from ..core.models import Option, Trainer
from ..core.utils import safe_name, short_path
from .widgets import info, warn

FILE_FILTER = "修改器文件 (*.exe *.zip *.7z *.rar);;所有文件 (*.*)"


def commit_import(db, result: importer.ImportResult, title: str, game: str, category: str,
                  tags: list[str], source: str, url: str = "", existing_id: int | None = None,
                  options: list[Option] | None = None) -> Trainer:
    """把一次导入结果落到数据库：更新已有条目或新建条目。"""
    if existing_id:
        t = db.get_trainer(existing_id) or Trainer()
        db.set_exe_path(existing_id, result.exe_path, str(Path(result.exe_path).parent))
        t.exe_path = result.exe_path
        t.work_dir = str(Path(result.exe_path).parent)
        t.source = source
        if url:
            t.source_url = url
        if options:
            t.options = options
        t.version = t.version if t.version and t.version != "see official page" else ""
        db.update_trainer(t)
        return t

    t = Trainer(
        title=title or (Path(result.exe_path).name if result.exe_path else "未命名"),
        game_title=game or title,
        category=category,
        tags=tags,
        source=source,
        source_url=url,
        exe_path=result.exe_path,
        work_dir=str(Path(result.exe_path).parent) if result.exe_path else "",
        version="",
        author="FLiNG",
        options=options or [],
    )
    t.id = db.add_trainer(t)
    return t


class AddDialog(QDialog):
    """返回 created_ids 列表供主窗口刷新。"""

    imported = Signal(list)      # list[int] trainer ids
    activity = Signal(str)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.created_ids: list[int] = []
        self._candidates: list[scanner.Candidate] = []
        self.setWindowTitle("添加修改器")
        self.resize(680, 480)
        self.setObjectName("root")

        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(12)

        self.tabs = QTabWidget()
        v.addWidget(self.tabs, 1)
        self._build_file_tab()
        self._build_folder_tab()
        self._build_url_tab()
        self._build_scan_tab()
        self._build_manual_tab()

        foot = QHBoxLayout()
        self.lbl_hint = QLabel("所有来源均需你自行核验；建议先用杀软扫描。")
        self.lbl_hint.setObjectName("muted")
        foot.addWidget(self.lbl_hint, 1)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        foot.addWidget(close)
        v.addLayout(foot)

    # ============================================================ 通用
    def _target_group(self) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(6)
        self.rdo_new = QRadioButton("新建条目")
        self.rdo_existing = QRadioButton("关联到已有条目（为其补充本体）")
        self.rdo_new.setChecked(True)
        box.addWidget(self.rdo_new)
        box.addWidget(self.rdo_existing)
        return box

    def _form(self) -> QFormLayout:
        f = QFormLayout()
        f.setSpacing(8)
        self.ed_game = QLineEdit()
        self.ed_game.setPlaceholderText("例如：ELDEN RING")
        self.ed_title = QLineEdit()
        self.ed_title.setPlaceholderText("选填，例如 ELDEN RING Trainer +27")
        self.ed_tags = QLineEdit()
        self.ed_tags.setPlaceholderText("英文逗号分隔，如 魂系,开放世界")
        self.cmb_cat = QComboBox()
        self.cmb_cat.setEditable(True)
        cats = [c for c, _n in self.db.categories_with_count()] or config.DEFAULT_CATEGORIES
        for c in cats + [x for x in config.DEFAULT_CATEGORIES if x not in cats]:
            self.cmb_cat.addItem(c)
        self.cmb_existing = QComboBox()
        for t in self.db.search(sort="name"):
            self.cmb_existing.addItem(f"{t.game_title}（{ '已安装' if t.installed else '未导入'}）", t.id)
        f.addRow("游戏名 *", self.ed_game)
        f.addRow("修改器标题", self.ed_title)
        f.addRow("分类", self.cmb_cat)
        f.addRow("标签", self.ed_tags)
        f.addRow("关联条目", self.cmb_existing)
        return f

    def _collect(self) -> tuple[str, str, str, list[str], int | None]:
        game = self.ed_game.text().strip()
        title = self.ed_title.text().strip() or f"{game} Trainer"
        cat = self.cmb_cat.currentText().strip() or "其他"
        tags = [x.strip() for x in self.ed_tags.text().replace("，", ",").split(",") if x.strip()]
        existing = None
        if self.rdo_existing.isChecked() and self.cmb_existing.currentIndex() >= 0:
            existing = self.cmb_existing.currentData()
            if game:
                pass
        return game, title, cat, tags, existing

    def _new_term(self, mode: str) -> None:
        for name in ("ed_game", "ed_title", "ed_tags", "cmb_cat"):
            w = getattr(self, name)
            w.setEnabled(mode == "new")
        self.cmb_existing.setEnabled(mode == "existing")

    # ============================================================ Tab1 文件
    def _build_file_tab(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)
        v.addLayout(self._target_group())
        self.rdo_new.toggled.connect(lambda: self._new_term("new" if self.rdo_new.isChecked() else "existing"))
        v.addLayout(self._form())
        self._new_term("new")

        row = QHBoxLayout()
        self.ed_file = QLineEdit()
        self.ed_file.setPlaceholderText("选择 .exe 或 .zip/.7z/.rar 压缩包")
        pick = QPushButton("浏览…")
        pick.clicked.connect(self._pick_file)
        row.addWidget(self.ed_file, 1)
        row.addWidget(pick)
        v.addLayout(row)
        self.btn_import_file = QPushButton("导入到库")
        self.btn_import_file.setObjectName("primary")
        self.btn_import_file.clicked.connect(lambda: self._do_import(Path(self.ed_file.text().strip())))
        v.addWidget(self.btn_import_file, 0, Qt.AlignmentFlag.AlignLeft)
        v.addStretch(1)
        self.tabs.addTab(w, "本地文件")

    def _pick_file(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "选择修改器文件", "", FILE_FILTER)
        if p:
            self.ed_file.setText(p)
            if not self.ed_game.text().strip():
                guess = scanner._guess_game(Path(p).name)
                self.ed_game.setText(guess)
            if not self.ed_title.text().strip():
                self.ed_title.setText(Path(p).stem)

    # ============================================================ Tab2 文件夹
    def _build_folder_tab(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)
        v.addWidget(QLabel("适合已解压好的修改器目录（内含 .exe）。整个目录会被复制到库中。"))
        row = QHBoxLayout()
        self.ed_dir = QLineEdit()
        pick = QPushButton("浏览…")
        pick.clicked.connect(self._pick_dir)
        row.addWidget(self.ed_dir, 1)
        row.addWidget(pick)
        v.addLayout(row)
        self.btn_import_dir = QPushButton("导入目录")
        self.btn_import_dir.setObjectName("primary")
        self.btn_import_dir.clicked.connect(lambda: self._do_import(Path(self.ed_dir.text().strip())))
        v.addWidget(self.btn_import_dir, 0, Qt.AlignmentFlag.AlignLeft)
        v.addStretch(1)
        self.tabs.addTab(w, "本地文件夹")

    def _pick_dir(self) -> None:
        p = QFileDialog.getExistingDirectory(self, "选择修改器目录")
        if p:
            self.ed_dir.setText(p)
            if not getattr(self, "ed_game", None) or not self.ed_game.text().strip():
                self.ed_game.setText(Path(p).name)

    # ============================================================ Tab3 URL
    def _build_url_tab(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)
        v.addWidget(QLabel("粘贴你自己获取的直链（需以 .zip/.7z/.rar/.exe 结尾）。\n"
                           "本程序不会自动抓取任何站点内容，也不会绕过下载限制。"))
        self.ed_url = QLineEdit()
        self.ed_url.setPlaceholderText("https://…/xxx.zip")
        v.addWidget(self.ed_url)
        b_open = QPushButton("打开 flingtrainer.com 查找并复制链接")
        b_open.clicked.connect(lambda: webbrowser.open("https://flingtrainer.com/"))
        v.addWidget(b_open, 0, Qt.AlignmentFlag.AlignLeft)
        self.bar = QProgressBar()
        self.bar.setFormat("准备就绪")
        v.addWidget(self.bar)
        self.btn_download = QPushButton("下载并导入")
        self.btn_download.setObjectName("primary")
        self.btn_download.clicked.connect(self._do_url)
        v.addWidget(self.btn_download, 0, Qt.AlignmentFlag.AlignLeft)
        v.addStretch(1)
        self.tabs.addTab(w, "下载链接")

    def _progress(self, done: int, total: int, msg: str) -> None:
        from PySide6.QtWidgets import QApplication

        if total:
            self.bar.setMaximum(max(total, 1))
            self.bar.setValue(min(done, total))
        self.bar.setFormat(f"{msg}")
        QApplication.processEvents()

    def _do_url(self) -> None:
        url = self.ed_url.text().strip()
        if not url:
            warn(self, "请填写链接")
            return
        game, title, cat, tags, existing = self._collect()
        if not existing and not game:
            warn(self, "请填写游戏名，或选择关联已有条目")
            return
        self.btn_download.setEnabled(False)
        try:
            file = importer.download_file(url, progress=self._progress)
        except importer.ImportError_ as exc:
            warn(self, str(exc))
            self.bar.setFormat("下载失败")
        else:
            self._do_import(file, source=config.SOURCE_URL, url=url)
        finally:
            self.btn_download.setEnabled(True)

    # ============================================================ Tab4 扫描
    def _build_scan_tab(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)
        row = QHBoxLayout()
        self.ed_scan = QLineEdit()
        self.ed_scan.setPlaceholderText("选择一个存放修改器的目录进行扫描")
        pick = QPushButton("浏览…")
        pick.clicked.connect(self._pick_scan)
        scan = QPushButton("开始扫描")
        scan.setObjectName("primary")
        scan.clicked.connect(self._do_scan)
        row.addWidget(self.ed_scan, 1)
        row.addWidget(pick)
        row.addWidget(scan)
        v.addLayout(row)

        self.tbl_scan = QTableWidget(0, 4)
        self.tbl_scan.setHorizontalHeaderLabels(["推断游戏名", "类型", "大小", "路径"])
        self.tbl_scan.verticalHeader().setVisible(False)
        self.tbl_scan.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_scan.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        from PySide6.QtWidgets import QHeaderView

        self.tbl_scan.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.tbl_scan, 1)

        foot = QHBoxLayout()
        self.btn_import_sel = QPushButton("导入选中项")
        self.btn_import_sel.setObjectName("primary")
        self.btn_import_sel.clicked.connect(self._import_selected)
        foot.addStretch(1)
        foot.addWidget(self.btn_import_sel)
        v.addLayout(foot)
        self.tabs.addTab(w, "目录扫描")

    def _pick_scan(self) -> None:
        p = QFileDialog.getExistingDirectory(self, "选择要扫描的目录")
        if p:
            self.ed_scan.setText(p)

    def _do_scan(self) -> None:
        root = Path(self.ed_scan.text().strip() or ".")
        self.lbl_hint.setText("扫描中…")
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()
        cands = scanner.scan(root)
        cands = scanner.dedup(cands, self.db)
        self._candidates = cands
        self.tbl_scan.setRowCount(0)
        for c in cands:
            r = self.tbl_scan.rowCount()
            self.tbl_scan.insertRow(r)
            vals = [c.guess_game, c.kind, c.size, str(c.path)]
            for i, val in enumerate(vals):
                self.tbl_scan.setItem(r, i, QTableWidgetItem(val))
        self.lbl_hint.setText(f"发现 {len(cands)} 个候选（已排除重复）")

    def _import_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.tbl_scan.selectedIndexes()})
        if not rows:
            warn(self, "请先选择要导入的项")
            return
        done = 0
        for r in rows:
            if r >= len(self._candidates):
                continue
            c = self._candidates[r]
            res = importer.materialize(c.path, c.guess_game)
            if res.ok:
                commit_import(self.db, res, f"{c.guess_game} Trainer", c.guess_game, "其他",
                              [], config.SOURCE_LOCAL)
                done += 1
        info(self, f"导入完成：成功 {done} / 选中 {len(rows)}")
        self.created_ids = [0]
        self.imported.emit(["refresh"])
        self.lbl_hint.setText(f"已导入 {done} 项")

    # ============================================================ Tab5 手动
    def _build_manual_tab(self) -> None:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)
        tip = QLabel("仅录入元数据（适用于先登记、后补文件的场景）。")
        tip.setObjectName("muted")
        v.addWidget(tip)
        f = QFormLayout()
        self.m_game = QLineEdit()
        self.m_title = QLineEdit()
        self.m_author = QLineEdit("FLiNG")
        self.m_url = QLineEdit()
        self.m_ver = QLineEdit()
        self.m_opts = QTextEdit()
        self.m_opts.setPlaceholderText("每行一条：Num 1  无限生命\n或仅写功能说明")
        f.addRow("游戏名 *", self.m_game)
        f.addRow("标题", self.m_title)
        f.addRow("作者/来源", self.m_author)
        f.addRow("官方页面", self.m_url)
        f.addRow("版本", self.m_ver)
        f.addRow("功能列表", self.m_opts)
        v.addLayout(f, 1)
        b = QPushButton("保存条目")
        b.setObjectName("primary")
        b.clicked.connect(self._save_manual)
        v.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        self.tabs.addTab(w, "手动录入")

    def _save_manual(self) -> None:
        game = self.m_game.text().strip()
        if not game:
            warn(self, "请填写游戏名")
            return
        opts: list[Option] = []
        for ln in self.m_opts.toPlainText().splitlines():
            ln = ln.strip()
            if not ln:
                continue
            parts = ln.split(None, 1)
            opts.append(Option(parts[0], parts[1]) if len(parts) == 2 else Option("", ln))
        t = Trainer(
            title=self.m_title.text().strip() or f"{game} Trainer",
            game_title=game,
            author=self.m_author.text().strip() or "FLiNG",
            source=config.SOURCE_BUILTIN if not self.m_url.text().strip() else config.SOURCE_URL,
            source_url=self.m_url.text().strip(),
            version=self.m_ver.text().strip(),
            options=opts,
        )
        t.id = self.db.add_trainer(t)
        self.created_ids.append(t.id)
        info(self, "已保存条目")
        self.imported.emit(["refresh"])

    # ============================================================ 执行导入
    def _do_import(self, src: Path, source: str = config.SOURCE_LOCAL, url: str = "") -> None:
        if not str(src) or not src.exists():
            warn(self, "请先选择有效的文件或目录")
            return
        game, title, cat, tags, existing = self._collect()
        if not existing and not game:
            warn(self, "请填写游戏名，或选择关联已有条目")
            return
        name = game or (self.db.get_trainer(existing).game_title if existing else "Trainer")
        self.lbl_hint.setText("正在导入（压缩包较大时请稍候）…")
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()
        try:
            res = importer.materialize(src, name)
        except importer.ImportError_ as exc:
            warn(self, str(exc))
            self.lbl_hint.setText("导入失败")
            return
        if not res.ok:
            warn(self, res.message)
            self.lbl_hint.setText(res.message)
            if res.trainer_dir and res.candidates:
                from PySide6.QtWidgets import QInputDialog

                choice, ok = QInputDialog.getItem(
                    self, "选择主程序", "未自动识别主程序，请手动指定：", res.candidates, 0, False
                )
                if ok and choice:
                    res.exe_path = choice
                    res.ok = True
            else:
                return
        t = commit_import(self.db, res, title, game, cat, tags, source, url, existing)
        self.created_ids.append(t.id or 0)
        self.activity.emit(f"已导入：{t.game_title}")
        self.imported.emit(["refresh"])
        self.lbl_hint.setText(f"导入成功 → {short_path(res.exe_path)}")
