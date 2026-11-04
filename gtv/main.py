"""GTV 应用入口：环境准备 → 数据初始化 → 启动主窗口。"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

if getattr(sys, "frozen", False):  # 打包后：把根目录加入模块搜索路径
    sys.path.insert(0, str(Path(__file__).resolve().parent))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from gtv.core import config  # noqa: E402
from gtv.core.catalog import load_seed, seed_meta  # noqa: E402
from gtv.core.database import Database  # noqa: E402
from gtv.core.launcher import Launcher  # noqa: E402
from gtv.ui.dialogs import AboutDialog  # noqa: E402
from gtv.ui.main_window import MainWindow  # noqa: E402
from gtv.ui.theme import light_palette, style_sheet  # noqa: E402


def apply_trainer_dir(db: Database) -> str:
    """应用自定义修改器库目录（settings.trainer_dir，默认 D:\\cheat）。

    返回最终生效的目录字符串。目录创建失败时回退到默认 AppData 目录。
    """
    wanted = db.get_setting("trainer_dir", r"D:\cheat").strip() or r"D:\cheat"
    from pathlib import Path as _P

    try:
        p = _P(wanted)
        p.mkdir(parents=True, exist_ok=True)
        config.TRAINER_DIR = p
        return str(p)
    except Exception:  # noqa: BLE001
        config.TRAINER_DIR = config.APP_DIR / "trainers"
        config.TRAINER_DIR.mkdir(parents=True, exist_ok=True)
        return str(config.TRAINER_DIR)


def _log_exception(exc_type, exc, tb) -> None:
    config.ensure_app_dirs()
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(config.LOG_DIR / "gtv.log", "a", encoding="utf-8") as fh:
        fh.write(f"\n==== {stamp} ====\n{text}")
    print(text, file=sys.stderr)


def seed_if_needed(db: Database) -> int:
    """首次运行导入内置目录；已存在则刷新元数据。"""
    added = 0
    for item in load_seed():
        if db.upsert_seed_item(item):
            added += 1
    return added


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    config.ensure_app_dirs()

    # 高 DPI（Qt6 默认开启，这里只做兼容性设置）
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(argv)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationDisplayName(config.APP_TITLE)
    app.setStyle("Fusion")
    # 关键：强制浅色调色板，避免深色系统下出现"白底白字"
    app.setPalette(light_palette())
    app.setStyleSheet(style_sheet())

    # 单实例保护
    server_name = f"{config.APP_ID}.singleton"
    probe = QLocalSocket()
    probe.connectToServer(server_name)
    if probe.waitForConnected(300):
        QMessageBox.information(None, "GTV", "GTV 已经在运行了（可在系统托盘中打开）。")
        return 0
    server = QLocalServer()
    server.removeServer(server_name)
    server.listen(server_name)

    try:
        db = Database()
        trainer_dir = apply_trainer_dir(db)
        added = seed_if_needed(db)
        launcher = Launcher(db)
        win = MainWindow(db, launcher)
        win.show()
        if added:
            win.lbl_status.setText(f"已载入内置修改器目录 {added} 条（元数据，需自行导入本体）")
        else:
            win.lbl_status.setText(f"就绪 · 修改器库目录：{trainer_dir}")
        if db.get_setting("first_run_done", "0") != "1":
            db.set_setting("first_run_done", "1")
            AboutDialog(win).exec()
        return app.exec()
    except Exception as exc:  # noqa: BLE001
        _log_exception(type(exc), exc, exc.__traceback__)
        QMessageBox.critical(None, "GTV 启动失败", f"{exc}\n\n详细堆栈已写入：{config.LOG_DIR / 'gtv.log'}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
