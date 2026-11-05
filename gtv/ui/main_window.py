"""主窗口：三栏布局（分类导航 / 卡片网格 / 详情与会话管理）。"""
from __future__ import annotations

import webbrowser

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import config
from ..core.database import Database
from ..core.launcher import Launcher
from ..core.models import Trainer
from . import theme
from .detail_panel import DetailPanel
from .dialogs import AboutDialog, EditDialog, RecordsDialog, SettingsDialog
from .trainer_card import TrainerCard
from .widgets import (
    FlowLayout,
    confirm,
    open_local_path,
    reveal_in_explorer,
)

SORT_LABELS = {"name": "按名称", "hot": "按运行次数", "recent": "按最近运行", "new": "按添加时间"}


class MainWindow(QMainWindow):
    def __init__(self, db: Database, launcher: Launcher):
        super().__init__()
        self.db = db
        self.launcher = launcher
        self.side_key = "all"
        self.sort_key = "name"
        self.keyword = ""
        self.selected_id: int | None = None
        self.cards: dict[int, TrainerCard] = {}

        self.setWindowTitle(config.APP_TITLE)
        self.resize(1320, 860)
        self._build_ui()
        self._wire_launcher()
        self._apply_theme()

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(220)
        self._search_timer.timeout.connect(self.reload_library)

        self._build_tray()
        self.reload_nav()
        self.reload_library()
        QTimer.singleShot(100, self._sync_launcher_state)

    # ============================================================ UI
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar())
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        root.addWidget(splitter, 1)

        # 左：导航
        self.nav = QTreeWidget()
        self.nav.setHeaderHidden(True)
        self.nav.setRootIsDecorated(True)
        self.nav.setIndentation(14)
        self.nav.setMinimumWidth(190)
        self.nav.setMaximumWidth(260)
        self.nav.itemClicked.connect(self._on_nav_clicked)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(10, 12, 10, 12)
        lv.setSpacing(8)
        lv.addWidget(self.nav, 1)
        self.lbl_stat_side = QLabel("")
        self.lbl_stat_side.setObjectName("muted")
        self.lbl_stat_side.setWordWrap(True)
        lv.addWidget(self.lbl_stat_side)
        splitter.addWidget(left)

        # 中：卡片网格
        mid = QWidget()
        mv = QVBoxLayout(mid)
        mv.setContentsMargins(14, 12, 14, 12)
        mv.setSpacing(8)
        head = QHBoxLayout()
        self.lbl_view = QLabel("全部修改器")
        self.lbl_view.setStyleSheet("QLabel{font-size:15px; font-weight:700; color:#1F2430; background:transparent;}")
        head.addWidget(self.lbl_view, 1)
        self.lbl_count = QLabel("")
        self.lbl_count.setObjectName("muted")
        head.addWidget(self.lbl_count)
        mv.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        # 注意：必须用带选择器的规则，裸样式（"background:transparent;"）
        # 会级联污染所有卡片子控件，把"启动"按钮的蓝底覆盖成透明
        self.container.setObjectName("gridHost")
        self.container.setStyleSheet("QWidget#gridHost{background:transparent;}")
        self.flow = FlowLayout(self.container, hspace=12, vspace=12)
        self.container.setLayout(self.flow)
        self.scroll.setWidget(self.container)
        mv.addWidget(self.scroll, 1)
        splitter.addWidget(mid)

        # 右：详情
        self.detail = DetailPanel(self.db, self.launcher, self)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([210, 730, 380])

        sb = QStatusBar()
        self.setStatusBar(sb)
        self.lbl_status = QLabel("就绪")
        sb.addWidget(self.lbl_status, 1)
        self.lbl_running = QLabel("运行中 0")
        sb.addPermanentWidget(self.lbl_running)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        # 带选择器的规则：避免裸样式级联覆盖子按钮的 #primary 蓝底白字
        bar.setObjectName("topBar")
        bar.setStyleSheet(
            f"QWidget#topBar{{background:{theme.PALETTE['panel']};"
            f"border-bottom:1px solid {theme.PALETTE['border']};}}"
        )
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(10)

        logo = QLabel("GTV")
        logo.setStyleSheet("QLabel{font-size:18px; font-weight:800; color:#2F6FEB; letter-spacing:1px; background:transparent;}")
        h.addWidget(logo)
        sub = QLabel("单机游戏修改器管理器")
        sub.setObjectName("muted")
        h.addWidget(sub)
        h.addSpacing(12)

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索游戏名 / 标签 / 分类 / 作者…   （Ctrl+F）")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(300)
        self.search.textChanged.connect(lambda _t: self._search_timer.start())
        h.addWidget(self.search, 1)

        self.cmb_sort = QComboBox()
        self.cmb_sort.setMinimumWidth(120)
        for k, label in SORT_LABELS.items():
            self.cmb_sort.addItem(label, k)
        self.cmb_sort.currentIndexChanged.connect(self._on_sort_changed)
        h.addWidget(self.cmb_sort)

        b_add = QPushButton("+ 添加修改器")
        b_add.setObjectName("primary")
        b_add.clicked.connect(self.open_add)
        h.addWidget(b_add)
        b_scan = QPushButton("扫描目录")
        b_scan.clicked.connect(self.open_add_scan)
        h.addWidget(b_scan)
        b_rec = QPushButton("启动记录")
        b_rec.clicked.connect(self.open_records)
        h.addWidget(b_rec)
        b_set = QPushButton("设置")
        b_set.clicked.connect(self.open_settings)
        h.addWidget(b_set)
        b_about = QPushButton("关于")
        b_about.clicked.connect(lambda: AboutDialog(self).exec())
        h.addWidget(b_about)
        return bar

    def _apply_theme(self) -> None:
        self.setStyleSheet(theme.style_sheet())

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        pm = QPixmap(64, 64)
        pm.fill(Qt.GlobalColor.transparent)
        from PySide6.QtGui import QPainter

        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(Qt.GlobalColor.white)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, 64, 64, 14, 14)
        p.setPen(QColor("#2F6FEB"))
        p.setFont(QFont("Microsoft YaHei UI", 20, QFont.Weight.Bold))
        p.drawText(0, 0, 64, 64, Qt.AlignmentFlag.AlignCenter, "G")
        p.end()

        self.tray = QSystemTrayIcon(QIcon(pm), self)
        self.tray.setToolTip(config.APP_TITLE)
        menu = self.tray.contextMenu()
        if menu is None:
            from PySide6.QtWidgets import QMenu

            menu = QMenu()
            self.tray.setContextMenu(menu)
        act_show = QAction("显示主窗口", self)
        act_show.triggered.connect(self.show_normal)
        act_stop = QAction("停止所有修改器", self)
        act_stop.triggered.connect(self.stop_all)
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self.quit_app)
        menu.addAction(act_show)
        menu.addAction(act_stop)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.activated.connect(lambda reason: self.show_normal()
                                    if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    # ============================================================ 导航
    def reload_nav(self) -> None:
        self.nav.blockSignals(True)
        self.nav.clear()
        stats = self.db.stats()

        def add_top(title: str) -> QTreeWidgetItem:
            it = QTreeWidgetItem([title])
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            f = it.font(0)
            f.setBold(True)
            it.setFont(0, f)
            self.nav.addTopLevelItem(it)
            return it

        lib = add_top("库")
        lib_items = [
            ("全部修改器", "all", stats["total"]),
            ("★ 收藏", "favorite", stats["favorite"]),
            ("已导入本体", "installed", stats["installed"]),
            ("待导入本体", "uninstalled", stats["total"] - stats["installed"]),
            ("最近运行", "recent:side", 0),
        ]
        for name, key, cnt in lib_items:
            child = QTreeWidgetItem([f"{name}  {cnt}"])
            child.setData(0, Qt.ItemDataRole.UserRole, key)
            lib.addChild(child)
        lib.setExpanded(True)

        cats = add_top("分类")
        for name, cnt in self.db.categories_with_count():
            child = QTreeWidgetItem([f"{name}  {cnt}"])
            child.setData(0, Qt.ItemDataRole.UserRole, f"category:{name}")
            cats.addChild(child)
        cats.setExpanded(True)

        tags = add_top("标签")
        for name, cnt in self.db.all_tags()[:28]:
            child = QTreeWidgetItem([f"#{name}  {cnt}"])
            child.setData(0, Qt.ItemDataRole.UserRole, f"tag:{name}")
            tags.addChild(child)
        self.nav.blockSignals(False)

        self.lbl_stat_side.setText(
            f"共 {stats['total']} 条 · 已安装 {stats['installed']}\n累计启动 {stats['runs']} 次"
        )

    def _on_nav_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if not key:
            return
        self.side_key = key
        self.reload_library()

    def _on_sort_changed(self) -> None:
        self.sort_key = self.cmb_sort.currentData() or "name"
        self.reload_library()

    # ============================================================ 库网格
    def reload_library(self) -> None:
        self.keyword = self.search.text().strip()
        sort = "recent" if self.side_key == "recent:side" else self.sort_key
        trainers = self.db.search(keyword=self.keyword, side=self.side_key, sort=sort)

        while self.flow.count():
            item = self.flow.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self.cards.clear()

        for t in trainers:
            card = TrainerCard(t, self.container)
            card.selected.connect(self.select_trainer)
            card.launch.connect(self.toggle_launch)
            card.favorite_toggled.connect(self.toggle_favorite)
            card.edit_requested.connect(self.edit_trainer)
            card.delete_requested.connect(self.delete_trainer)
            card.reveal_requested.connect(self.reveal_trainer)
            card.open_page.connect(lambda tid: self.open_page(tid))
            card.set_running(self.launcher.is_running(t.id or 0))
            if t.id == self.selected_id:
                card.set_selected(True)
            self.flow.addWidget(card)
            self.cards[t.id or 0] = card

        self.lbl_count.setText(f"{len(trainers)} 项")
        self.lbl_view.setText(NAV_TITLE.get(self.side_key, self._nav_title()))
        if not trainers:
            empty = QLabel(self._empty_text())
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setMinimumHeight(220)
            self.flow.addWidget(empty)
        self.container.adjustSize()

    def _nav_title(self) -> str:
        key = self.side_key
        if key.startswith("category:"):
            return f"分类 · {key.split(':', 1)[1]}"
        if key.startswith("tag:"):
            return f"标签 · #{key.split(':', 1)[1]}"
        return "修改器库"

    def _empty_text(self) -> str:
        if not self.db.stats()["total"]:
            return "库是空的 —— 点击右上角「+ 添加修改器」导入你的第一个修改器。"
        if self.keyword:
            return f"没有匹配 “{self.keyword}” 的修改器。"
        return "该分类下暂无内容。"

    # ============================================================ 选择
    def select_trainer(self, tid: int) -> None:
        for cid, card in self.cards.items():
            card.set_selected(cid == tid)
        self.selected_id = tid
        t = self.db.get_trainer(tid)
        self.detail.set_trainer(t)

    def refresh_card(self, tid: int) -> None:
        card = self.cards.get(tid)
        t = self.db.get_trainer(tid)
        if card and t:
            card.refresh(t)
            card.set_running(self.launcher.is_running(tid))

    # ============================================================ 动作
    def toggle_launch(self, tid: int) -> None:
        if self.launcher.is_running(tid):
            ok, msg = self.launcher.stop(tid)
            self.lbl_status.setText(msg)
            return
        t = self.db.get_trainer(tid)
        if not t:
            return
        if not t.installed:
            self.lbl_status.setText(
                "该条目尚未导入本体 —— 请点击「+ 添加修改器」，用本地文件 / 下载链接为其补充程序。"
            )
            QMessageBox.information(
                self, "尚未导入本体",
                f"《{t.game_title}》还没有修改器程序。\n\n"
                "方式一：点击「+ 添加修改器」→ 本地文件/文件夹，选择你下载好的 exe 或压缩包；\n"
                "方式二：切换到「下载链接」页，粘贴你自己获取的地址；\n"
                "方式三：打开官方页面手动下载后，在「关联已有条目」中补录。",
            )
            return
        if t.online_risk and self.db.get_setting("confirm_online", "1") == "1":
            box = QMessageBox(self)
            box.setWindowTitle("联机风险提示")
            box.setText(
                f"《{t.game_title}》包含联机 / 在线模式。\n\n"
                "请确认当前处于离线或单人剧情模式。在多人环境使用修改器可能导致封号。"
            )
            box.setIcon(QMessageBox.Icon.Warning)
            box.addButton("我确认仅在单机使用", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.result() != QMessageBox.DialogCode.Accepted:
                return
        ok, msg = self.launcher.start(t)
        self.lbl_status.setText(msg)
        if ok:
            self.select_trainer(tid)
            self.refresh_card(tid)

    def toggle_favorite(self, tid: int) -> None:
        fav = self.db.toggle_favorite(tid)
        card = self.cards.get(tid)
        if card:
            card.t.favorite = fav
            card.refresh()
        if self.selected_id == tid:
            t = self.db.get_trainer(tid)
            self.detail.set_trainer(t)
        if self.side_key == "favorite":
            self.reload_library()

    def edit_trainer(self, tid: int) -> None:
        t = self.db.get_trainer(tid)
        if not t:
            return
        if EditDialog(self.db, t, self).exec() == EditDialog.DialogCode.Accepted:
            self.select_trainer(tid)
            self.reload_library()
            self.reload_nav()
            self.lbl_status.setText("已保存")

    def delete_trainer(self, tid: int) -> None:
        t = self.db.get_trainer(tid)
        if not t:
            return
        if not confirm(self, "删除条目", f"确定要从库中移除《{t.game_title}》吗？\n（本地文件不会被自动删除）"):
            return
        if self.launcher.is_running(tid):
            self.launcher.stop(tid)
        self.db.delete_trainer(tid)
        if self.selected_id == tid:
            self.selected_id = None
            self.detail.set_trainer(None)
        self.reload_library()
        self.reload_nav()

    def reveal_trainer(self, tid: int) -> None:
        t = self.db.get_trainer(tid)
        if t and t.exe_path:
            reveal_in_explorer(t.exe_path)
        else:
            open_local_path(str(config.TRAINER_DIR))

    def open_page(self, tid: int) -> None:
        t = self.db.get_trainer(tid)
        if t and t.source_url:
            webbrowser.open(t.source_url)
        else:
            webbrowser.open("https://flingtrainer.com/")

    # ============================================================ 对话框
    def open_add(self) -> None:
        from .add_dialog import AddDialog

        dlg = AddDialog(self.db, self)
        dlg.imported.connect(lambda _x: self._after_import())
        dlg.activity.connect(self.lbl_status.setText)
        dlg.exec()
        self.reload_nav()

    def open_add_scan(self) -> None:
        from .add_dialog import AddDialog

        dlg = AddDialog(self.db, self)
        dlg.tabs.setCurrentIndex(3)
        dlg.imported.connect(lambda _x: self._after_import())
        dlg.exec()
        self.reload_nav()

    def _after_import(self) -> None:
        self.reload_library()
        self.reload_nav()
        self.lbl_status.setText("已刷新库")

    def open_records(self) -> None:
        RecordsDialog(self.db, self).exec()

    def open_settings(self) -> None:
        SettingsDialog(self.db, self).exec()
        self.reload_library()

    # ============================================================ 联动
    def _wire_launcher(self) -> None:
        self.launcher.sessionStarted.connect(self._on_started)
        self.launcher.sessionEnded.connect(self._on_ended)
        self.launcher.message.connect(lambda _tid, m: self.lbl_status.setText(m))
        self.detail.activity.connect(self.lbl_status.setText)
        self.detail.favorite_changed.connect(self._on_fav_changed)
        self.detail.edit_requested.connect(self.edit_trainer)
        self.detail.delete_requested.connect(self.delete_trainer)

    def _on_fav_changed(self, tid: int) -> None:
        self.refresh_card(tid)
        if self.side_key == "favorite":
            self.reload_library()
        self.reload_nav()

    def _on_started(self, tid: int, pid: int) -> None:
        self.refresh_card(tid)
        self._update_running_label()
        if self.selected_id == tid:
            self.detail._refresh_session()

    def _on_ended(self, tid: int, code: int) -> None:
        self.refresh_card(tid)
        self._update_running_label()
        t = self.db.get_trainer(tid)
        if t and self.selected_id == tid:
            self.detail.set_trainer(t)

    def _update_running_label(self) -> None:
        n = self.launcher.running_count()
        self.lbl_running.setText(f"运行中 {n}")
        if self.tray:
            self.tray.setToolTip(f"{config.APP_TITLE} · 运行中 {n}")

    def _sync_launcher_state(self) -> None:
        for tid in self.launcher.running_ids():
            self.refresh_card(tid)
        self._update_running_label()

    # ============================================================ 窗口行为
    def stop_all(self) -> bool:
        ids = self.launcher.running_ids()
        if not ids:
            return True
        for tid in ids:
            self.launcher.stop(tid)
        self._update_running_label()
        return True

    def show_normal(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):  # noqa: N802
        running = self.launcher.running_count()
        minimize = self.db.get_setting("minimize_to_tray", "1") == "1" and self.tray is not None
        if minimize and running == 0:
            event.ignore()
            self.hide()
            if self.tray:
                self.tray.showMessage("GTV", "已最小化到托盘，双击图标可重新打开",
                                      QSystemTrayIcon.MessageIcon.Information, 1800)
            return
        if running and not confirm(
            self, "退出确认",
            f"还有 {running} 个修改器正在运行，退出前是否结束这些进程？\n\n"
            "选择「确定」= 结束并退出；选择「取消」= 留在当前窗口。",
        ):
            event.ignore()
            return
        self.stop_all()
        self.db.close()
        event.accept()

    def quit_app(self) -> None:
        self.stop_all()
        self.db.close()
        QApplication.quit()

    def keyPressEvent(self, event):  # noqa: N802
        if event.matches(QKeySequence.StandardKey.Find) or (
            event.key() == Qt.Key.Key_F and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.search.setFocus()
            self.search.selectAll()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.search.clear()
            return
        super().keyPressEvent(event)


NAV_TITLE = {
    "all": "全部修改器",
    "favorite": "★ 收藏夹",
    "installed": "已导入本体",
    "uninstalled": "待导入本体",
    "recent:side": "最近运行",
}
