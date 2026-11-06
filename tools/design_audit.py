"""P0 设计验收：对比度断言 + 键盘焦点覆盖 + 点击区尺寸断言。

每次改样式跑一次，防止"改着改着又掉回 4.5:1 以下"。

运行：.venv/Scripts/python.exe tools/design_audit.py
退出码 0 = 全部通过；1 = 有断言失败。
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from gtv.core.database import Database  # noqa: E402
from gtv.core.launcher import Launcher  # noqa: E402
from gtv.core.models import MemoryEntry, Trainer  # noqa: E402
from gtv.ui import theme  # noqa: E402
from gtv.ui.main_window import MainWindow  # noqa: E402

# 背景渐变里最亮的一档（QSS 中 #13294F）。玻璃面板叠在它上面是"最不利"的底色。
BG_LIGHTEST = "#13294F"

results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str) -> None:
    results.append((ok, name, detail))


# ---------------------------------------------------------------- 颜色工具
def rgb(color: str) -> tuple[int, int, int]:
    c = color.strip()
    if c.startswith("rgba"):
        parts = [int(x) for x in re.findall(r"[\d.]+", c)]
        return parts[0], parts[1], parts[2]
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def alpha_of(color: str) -> float:
    if color.strip().startswith("rgba"):
        return int(re.findall(r"[\d.]+", color)[3]) / 255.0
    return 1.0


def over(fg: str, bg: tuple[int, int, int]) -> tuple[int, int, int]:
    """把半透明前景合成到实色背景上，得到实际看到的颜色。"""
    a = alpha_of(fg)
    f = rgb(fg)
    return tuple(round(f[i] * a + bg[i] * (1 - a)) for i in range(3))


def _lin(v: float) -> float:
    v /= 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def lum(color) -> float:
    r, g, b = rgb(color) if isinstance(color, str) else color
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a, b) -> float:
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ---------------------------------------------------------------- 1. 对比度
def audit_contrast() -> None:
    bg = rgb(BG_LIGHTEST)
    glass_panel = over(theme.GLASS["panel"], bg)          # 卡片/面板最亮处
    glass_input = over(theme.GLASS["input"], glass_panel)  # 输入框底

    pairs = [
        ("主按钮白字 / 渐变左端", "#FFFFFF", theme.PALETTE["accent"], 4.5),
        ("主按钮白字 / 渐变右端", "#FFFFFF", theme.PALETTE["accent2"], 4.5),
        ("主按钮白字 / hover 左端", "#FFFFFF", theme.PALETTE["accent_hover"], 4.5),
        ("主按钮白字 / hover 右端", "#FFFFFF", theme.PALETTE["accent2_hover"], 4.5),
        ("正文 / 玻璃面板最亮处", theme.PALETTE["text"], glass_panel, 4.5),
        ("次级文字 / 玻璃面板最亮处", theme.PALETTE["muted"], glass_panel, 4.5),
        ("正文 / 页面深底", theme.PALETTE["text"], bg, 4.5),
        ("占位文字 / 输入框底", "#8593B0", glass_input, 4.5),
        ("强调文字 / 页面深底", theme.PALETTE["accent_bright"], bg, 4.5),
        ("焦点环 / 玻璃面板（非文本 3:1）", theme.PALETTE["focus"], glass_panel, 3.0),
        ("危险色 / 玻璃面板", theme.PALETTE["danger"], glass_panel, 4.5),
        ("成功色 / 玻璃面板", theme.PALETTE["ok"], glass_panel, 4.5),
    ]
    for name, fg, bgc, need in pairs:
        r = contrast(fg, bgc)
        check(r >= need, f"对比度 {name}", f"{r:.2f}:1 ≥ {need}（要求）")


# ---------------------------------------------------------------- 2. 焦点态
FOCUS_SELECTORS = [
    "QLineEdit:focus",
    "QComboBox:focus",
    "QSpinBox:focus",
    "QPushButton:focus",
    "QPushButton#primary:focus",
    "QPushButton#ghost:focus",
    "QSlider:focus",
    "QCheckBox:focus",
]


def audit_focus() -> None:
    qss = theme.style_sheet()
    for sel in FOCUS_SELECTORS:
        check(sel in qss, f"焦点样式存在 {sel}", "命中 QSS" if sel in qss else "缺失")


# ---------------------------------------------------------------- 3. 点击区
def audit_targets() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(theme.app_palette())
    app.setStyleSheet(theme.style_sheet())
    tmp = Path(tempfile.mkdtemp(prefix="gtv-audit-"))
    db = Database(tmp / "audit.db")
    t = Trainer(
        title="验收样例",
        game_title="验收样例",
        category="动作",
        exe_path=r"D:\Games\Demo\demo.exe",
    )
    tid = db.add_trainer(t)
    db.add_memory(
        MemoryEntry(
            trainer_id=tid,
            name="金币",
            addr="demo.exe+1A2B3C",
            dtype="int32",
            control="slider",
            minv=0,
            maxv=9999,
            step=1,
        )
    )
    win = MainWindow(db, Launcher(db))
    win.resize(1440, 900)
    win.select_trainer(tid)
    for _ in range(3):
        app.processEvents()

    detail = win.detail
    check(bool(detail.rows), "详情页生成地址行", f"{len(detail.rows)} 行")
    if detail.rows:
        row = detail.rows[0]
        icons = [b for b in row.findChildren(QPushButton) if b.objectName() in ("iconBtn", "iconBtnDanger")]
        check(len(icons) == 2, "每行有 2 个图标操作按钮", f"{len(icons)} 个")
        for b in icons:
            ok = b.width() >= 24 and b.height() >= 24
            check(ok, f"点击区 {b.objectName()} {b.text()}", f"{b.width()}×{b.height()} ≥ 24×24")
            check(bool(b.accessibleName()), f"无障碍名 {b.objectName()}", b.accessibleName() or "缺失")
            check(bool(b.toolTip()), f"tooltip {b.objectName()}", "有" if b.toolTip() else "缺失")
        check(
            row.lbl_value.width() >= 112,
            "实时值格子宽 ≥112（防长数字挤控件）",
            f"{row.lbl_value.width()}px",
        )
        check(
            bool(row.lbl_value.alignment() & Qt.AlignmentFlag.AlignRight),
            "实时值右对齐",
            str(row.lbl_value.alignment()),
        )

    for name, btn in (("启动游戏", detail.btn_launch), ("新增地址", detail.btn_add)):
        check(btn.height() >= 30, f"主按钮高度 {name}", f"{btn.height()}px ≥ 30")

    win.close()
    db.close()


def main() -> int:
    # 必须先建 QApplication：theme.style_sheet() 会用 QPixmap 画箭头/对勾，
    # 没有 GUI 实例时 QPixmap 会直接崩溃（表现为无输出的异常退出）。
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(theme.app_palette())

    audit_contrast()
    audit_focus()
    audit_targets()

    width = max(len(n) for _ok, n, _d in results)
    failed = 0
    print()
    for ok, name, detail in results:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  [{mark}] {name.ljust(width)}  {detail}")
    print(f"\n{len(results) - failed}/{len(results)} 项通过")
    if failed:
        print(f"❌ {failed} 项未通过")
        return 1
    print("✅ P0 验收全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
