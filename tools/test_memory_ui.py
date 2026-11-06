"""内存修改功能整体冒烟测试（离屏，不影响真实数据库）。

覆盖：
1. MainWindow 构建成功（含新 Tab：修改器库 / 内存修改）
2. 建游戏条目 → 录入 3 条不同控件类型的内存地址 → 持久化 → 重读校验
3. MemoryPage 行控件生成（slider / spin / button / toggle 各一行）
4. offset 解析与非法输入拒绝
运行：.venv/Scripts/python.exe tools/test_memory_ui.py
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
from gtv.core.models import MemoryEntry, Trainer  # noqa: E402
from gtv.ui.main_window import MainWindow  # noqa: E402
from gtv.ui.memory_dialog import parse_offsets  # noqa: E402
from gtv.ui.memory_page import MemoryPage  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)

    tmpdir = tempfile.mkdtemp(prefix="gtv-test-")
    db = Database(Path(tmpdir) / "test.db")

    # ---- 1. 主窗口构建
    win = MainWindow(db, Launcher(db))
    assert win.tabs.count() == 2, "应有 2 个标签页"
    assert win.tabs.tabText(0) == "修改器库" and win.tabs.tabText(1) == "内存修改"
    print("[1] MainWindow 双标签构建  OK")

    # ---- 2. 游戏条目 + 内存地址持久化
    t = Trainer(title="Test Game", game_title="测试游戏", category="测试", exe_path=r"C:\Games\test.exe")
    tid = db.add_trainer(t)
    entries = [
        MemoryEntry(trainer_id=tid, name="金币", addr="game.exe+1A2B3C", offsets=[0x10, 0x4],
                    dtype="int32", control="spin", minv=0, maxv=999999),
        MemoryEntry(trainer_id=tid, name="血量", addr="7FF6A1B2C3D0", dtype="float",
                    control="slider", minv=0, maxv=100, step=0.5),
        MemoryEntry(trainer_id=tid, name="一键满魔", addr="game.exe+2B3C", dtype="int32",
                    control="button", value="999"),
        MemoryEntry(trainer_id=tid, name="无敌开关", addr="game.exe+3D4E", dtype="byte",
                    control="toggle", value="1", enabled=False),
    ]
    for e in entries:
        e.id = db.add_memory(e)
    loaded = db.list_memory(tid)
    assert len(loaded) == 4, f"应加载 4 条，实际 {len(loaded)}"
    assert loaded[0].offsets == [0x10, 0x4], "偏移链持久化/回读失败"
    assert loaded[1].addr == "7FF6A1B2C3D0"
    assert loaded[3].enabled is False
    assert db.count_memory(tid) == 4
    print("[2] 内存地址持久化（含指针链/启停状态）  OK")

    # ---- 3. 选中游戏 → MemoryPage 生成行控件
    win.select_trainer(tid)
    page: MemoryPage = win.mem_page
    assert page.t and page.t.id == tid
    assert len(page.rows) == 4, f"应生成 4 行，实际 {len(page.rows)}"
    kinds = [type(row._ctl).__name__ for row in page.rows]
    assert kinds == ["QDoubleSpinBox", "QSlider", "QPushButton", "QCheckBox"], kinds
    from PySide6.QtWidgets import QSlider

    s: QSlider = page.rows[1]._ctl
    assert s.minimum() == 0 and s.maximum() == 200, "滑动条范围换算（0~100 步长0.5）失败"
    print(f"[3] 控件自动生成 {kinds}  OK")

    # ---- 4. 编辑 + 删除
    e = loaded[0]
    e.name = "金币改"
    db.update_memory(e)
    assert db.list_memory(tid)[0].name == "金币改"
    db.delete_memory(loaded[3].id)
    assert db.count_memory(tid) == 3
    print("[4] 地址条目改/删  OK")

    # ---- 5. 删除游戏 → 级联删除地址
    db.delete_trainer(tid)
    assert db.count_memory(tid) == 0
    print("[5] 删除游戏级联清理地址  OK")

    # ---- 6. 偏移链解析（含非法输入）
    assert parse_offsets("10, 4") == [0x10, 0x4]
    assert parse_offsets("0x10 0x4; 8") == [0x10, 0x4, 8]
    assert parse_offsets("") == []
    try:
        parse_offsets("10, zz")
        raise AssertionError("非法偏移未被拒绝")
    except ValueError:
        pass
    print("[6] 偏移链解析与校验  OK")

    db.close()
    print("\nALL UI TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
