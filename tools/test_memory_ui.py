"""重构后 UI 冒烟测试（离屏，不影响真实数据库）。

覆盖：
1. MainWindow 构建：中央为堆叠视图（列表页 / 详情页），无 Tab
2. 库列表为纵向条形卡片 TrainerRow
3. 点击卡片 → 进入详情页（stack 切换）
4. 详情页地址列表控件生成（slider / spin / button / toggle）
5. 每个地址可切换修改方式并持久化
6. 返回列表、增删改、级联删除
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

from PySide6.QtWidgets import QApplication, QCheckBox, QDoubleSpinBox, QPushButton, QSlider  # noqa: E402

from gtv.core.database import Database  # noqa: E402
from gtv.core.launcher import Launcher  # noqa: E402
from gtv.core.models import MemoryEntry, Trainer  # noqa: E402
from gtv.ui.game_detail import EntryRow, GameDetailPage  # noqa: E402
from gtv.ui.main_window import MainWindow  # noqa: E402
from gtv.ui.memory_dialog import parse_offsets  # noqa: E402
from gtv.ui.trainer_row import TrainerRow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)

    tmpdir = tempfile.mkdtemp(prefix="gtv-test-")
    db = Database(Path(tmpdir) / "test.db")

    # ---- 1. 窗口结构
    win = MainWindow(db, Launcher(db))
    assert win.stack.count() == 2, "应有两个堆叠页面"
    assert not hasattr(win, "tabs"), "不应再有 Tab 控件"
    print("[1] 堆叠视图（列表/详情）构建  OK")

    # ---- 2. 数据准备
    t = Trainer(title="Test Game", game_title="测试游戏", category="动作角色扮演",
                tags=["开放世界", "动作"], exe_path=r"C:\Games\test.exe")
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

    # ---- 3. 库列表：条形卡片
    win.reload_library()
    rows = win.container.findChildren(TrainerRow)
    assert len(rows) == 1, f"应有 1 个条形卡片，实际 {len(rows)}"
    row = rows[0]
    assert row.height() == 72
    assert row.chip_mem.text().strip() == "4 条地址", f"地址数徽标错误：{row.chip_mem.text()!r}"
    print(f"[2] 条形卡片：{row.lbl_title.text()} / {row.lbl_sub.text()} / {row.chip_mem.text().strip()}  OK")

    # ---- 4. 点击卡片 → 详情页
    win.select_trainer(tid)
    assert win.stack.currentWidget() is win.detail, "未跳转到详情页"
    page: GameDetailPage = win.detail
    assert page.t and page.t.id == tid
    assert len(page.rows) == 4, f"应生成 4 行，实际 {len(page.rows)}"
    kinds = [type(r._ctl).__name__ for r in page.rows]
    assert kinds == ["QDoubleSpinBox", "QSlider", "QPushButton", "QCheckBox"], kinds
    s: QSlider = page.rows[1]._ctl
    assert s.minimum() == 0 and s.maximum() == 200, "滑块范围换算（0~100 步长0.5）失败"
    print("[3] 进入详情页 + 控件生成  OK")

    # ---- 5. 切换修改方式（数值框 → 开关）并持久化
    r0: EntryRow = page.rows[0]
    idx_toggle = next(i for i in range(r0.cmb.count()) if r0.cmb.itemData(i) == "toggle")
    r0.cmb.setCurrentIndex(idx_toggle)
    assert isinstance(r0._ctl, QCheckBox), f"切换后控件类型未更新：{type(r0._ctl).__name__}"
    assert db.list_memory(tid)[0].control == "toggle", "修改方式未持久化"
    print("[4] 修改方式切换 + 持久化  OK")

    # ---- 6. 返回列表
    win.show_library()
    assert win.stack.currentWidget() is win.lib_page
    print("[5] 返回列表  OK")

    # ---- 7. 增删改 + 级联删除
    e = db.list_memory(tid)[0]
    e.name = "金币改"
    db.update_memory(e)
    assert db.list_memory(tid)[0].name == "金币改"
    db.delete_memory(entries[3].id)
    assert db.count_memory(tid) == 3
    win.reload_library()
    row = list(win.cards.values())[0]
    assert row.chip_mem.text().strip() == "3 条地址", row.chip_mem.text()
    db.delete_trainer(tid)
    assert db.count_memory(tid) == 0
    print("[6] 增删改 / 卡片地址数刷新 / 级联删除  OK")

    # ---- 8. 偏移链解析
    assert parse_offsets("10, 4") == [0x10, 0x4]
    assert parse_offsets("") == []
    try:
        parse_offsets("10, zz")
        raise AssertionError("非法偏移未被拒绝")
    except ValueError:
        pass
    print("[7] 偏移链解析与校验  OK")

    db.close()
    print("\nALL UI TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
