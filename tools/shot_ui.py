"""离屏渲染界面截图，用于视觉检查（不影响真实数据库）。

输出：docs/preview_library.png（条形卡片列表）、docs/preview_detail.png（游戏详情页）
运行：.venv/Scripts/python.exe tools/shot_ui.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gtv.core.database import Database  # noqa: E402
from gtv.core.launcher import Launcher  # noqa: E402
from gtv.core.models import MemoryEntry, Option, Trainer  # noqa: E402
from gtv.ui.main_window import MainWindow  # noqa: E402

GAMES = [
    ("艾尔登法环 / ELDEN RING", "动作角色扮演", ["开放世界", "魂类"], True),
    ("博德之门3 / Baldur's Gate 3", "角色扮演", ["回合制", "剧情"], True),
    ("赛博朋克2077 / Cyberpunk 2077", "射击", ["开放世界", "科幻"], False),
    ("荒野大镖客2 / RDR2", "动作冒险", ["开放世界", "西部"], True),
    ("只狼 / Sekiro", "动作冒险", ["魂类", "忍者"], False),
    ("巫师3 / The Witcher 3", "角色扮演", ["开放世界", "奇幻"], True),
    ("星空 / Starfield", "角色扮演", ["太空", "探索"], False),
    ("生化危机4 / RE4", "恐怖", ["生存", "重制"], True),
]


def main() -> int:
    app = QApplication(sys.argv)
    tmpdir = tempfile.mkdtemp(prefix="gtv-shot-")
    db = Database(Path(tmpdir) / "preview.db")

    for i, (name, cat, tags, installed) in enumerate(GAMES):
        t = Trainer(
            title=f"{name} Trainer +2{i}",
            game_title=name,
            category=cat,
            tags=tags,
            exe_path=rf"D:\Games\Game{i}\game.exe" if installed else "",
            options=[Option("Num 1", "无限生命"), Option("Num 2", "无限弹药")],
            notes="需先启动游戏并进入存档。" if i == 0 else "",
        )
        tid = db.add_trainer(t)
        if i == 0:
            tid_with_mem = tid
            for e in (
                MemoryEntry(trainer_id=tid, name="金币", addr="eldenring.exe+2A1B3C",
                            offsets=[0x10, 0x8], dtype="int32", control="spin", minv=0, maxv=99999999),
                MemoryEntry(trainer_id=tid, name="生命值", addr="eldenring.exe+3C2D1E",
                            dtype="float", control="slider", minv=0, maxv=2000, step=10),
                MemoryEntry(trainer_id=tid, name="耐力", addr="eldenring.exe+3C2D30",
                            dtype="float", control="slider", minv=0, maxv=300, step=5),
                MemoryEntry(trainer_id=tid, name="一键满卢恩", addr="eldenring.exe+2A1B40",
                            dtype="int32", control="button", value="9999999"),
                MemoryEntry(trainer_id=tid, name="无敌模式", addr="eldenring.exe+4D5E6F",
                            dtype="byte", control="toggle", value="1"),
            ):
                db.add_memory(e)

    win = MainWindow(db, Launcher(db))
    win.resize(1440, 900)
    win.show()
    app.processEvents()

    out = ROOT / "docs"
    out.mkdir(exist_ok=True)
    win.reload_library()
    app.processEvents()
    win.grab().save(str(out / "preview_library.png"))

    first_tid = tid_with_mem
    win.select_trainer(first_tid)
    app.processEvents()
    # 让详情页控件完成布局
    for _ in range(3):
        app.processEvents()
    win.grab().save(str(out / "preview_detail.png"))

    print("saved:", out / "preview_library.png")
    print("saved:", out / "preview_detail.png")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
