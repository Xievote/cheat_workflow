"""UI 冒烟测试：离屏渲染启动主窗口，模拟选中/收藏/搜索，并输出截图。

运行：python tools/smoke_ui.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # 无窗口环境下渲染
os.environ.setdefault("QT_SCALE_FACTOR", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gtv.core.database import Database  # noqa: E402
from gtv.core.launcher import Launcher  # noqa: E402
from gtv.ui.main_window import MainWindow  # noqa: E402
from gtv.ui.theme import style_sheet  # noqa: E402

OUT = ROOT / "docs" / "ui-smoke.png"


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(style_sheet())

    db = Database()
    from gtv.core.catalog import load_seed

    added = sum(1 for it in load_seed() if db.upsert_seed_item(it))

    launcher = Launcher(db)
    win = MainWindow(db, launcher)
    win.resize(1320, 860)
    win.show()

    results: list[tuple[str, bool, str]] = []

    def scenario() -> None:
        app.processEvents()
        results.append(("主窗口渲染", win.isVisible(), f"size={win.width()}x{win.height()}"))
        results.append(("卡片数量", len(win.cards) > 0, f"{len(win.cards)} 张卡片"))

        first = sorted(win.cards.keys())[0]
        win.select_trainer(first)
        app.processEvents()
        results.append(("选中后详情填充", win.detail.t is not None, win.detail.t.game_title if win.detail.t else ""))
        results.append(("功能表行数", win.detail.table.rowCount() > 0, f"{win.detail.table.rowCount()} 行"))

        win.toggle_favorite(first)
        app.processEvents()
        results.append(("收藏切换", db.get_trainer(first).favorite, ""))

        win.search.setText("魂系")
        win.reload_library()
        app.processEvents()
        results.append(("搜索过滤", 0 < len(win.cards) < 51, f"{len(win.cards)} 命中"))

        win.search.clear()
        win.side_key = "favorite"
        win.reload_library()
        app.processEvents()
        results.append(("侧栏收藏过滤", len(win.cards) == 1, f"{len(win.cards)} 张"))

        win.side_key = "all"
        win.reload_library()
        app.processEvents()

        OUT.parent.mkdir(parents=True, exist_ok=True)
        pix = win.grab()
        ok_save = pix.save(str(OUT))
        results.append(("截图保存", ok_save, str(OUT)))

    QTimer.singleShot(300, scenario)
    QTimer.singleShot(1500, app.quit)
    app.exec()

    passed = True
    for label, cond, extra in results:
        passed = passed and bool(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {label}{(' -> ' + str(extra)) if extra else ''}")
    db.close()
    print("\n=== UI 冒烟测试：", "全部通过" if passed else "存在失败项", "===")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
