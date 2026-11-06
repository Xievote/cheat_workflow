"""内存地址条目的新增 / 编辑对话框。"""
from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..core.models import MemoryEntry

DTYPE_LABELS = {
    "int32": "整数 4 字节（int32）",
    "int64": "整数 8 字节（int64）",
    "int16": "整数 2 字节（int16）",
    "byte": "字节 1 字节（byte）",
    "float": "小数 4 字节（float）",
    "double": "小数 8 字节（double）",
}
CONTROL_LABELS = {
    "slider": "滑动条（拖动即写入）",
    "spin": "数值输入框（回车写入）",
    "button": "按钮（一键写入固定值）",
    "toggle": "开关（开=写入值，关=写 0）",
}

_ADDR_RE = re.compile(r"^\s*(?:(?P<mod>[^+\s]+)\s*\+\s*)?(?P<off>0x[0-9a-fA-F]+|[0-9a-fA-F]{4,})\s*$")


def parse_offsets(text: str) -> list[int]:
    """解析偏移链输入："10, 4" / "0x10 0x4" / "10;4" → [0x10, 0x4]。"""
    out: list[int] = []
    for tok in re.split(r"[,;\s]+", text.strip()):
        if not tok:
            continue
        try:
            out.append(int(tok, 16))
        except ValueError:
            raise ValueError(f"偏移 “{tok}” 不是合法十六进制数")
    return out


class MemoryEntryDialog(QDialog):
    """录入 / 编辑一条 MemoryEntry。entry 传 None 表示新增。"""

    def __init__(self, trainer_title: str, entry: MemoryEntry | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"内存地址 · {trainer_title}")
        self.resize(480, 520)
        self._orig = entry
        self._build()

        if entry:
            self._fill(entry)

    # ------------------------------------------------------------ UI
    def _build(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(10)

        tip = QLabel(
            "在 Cheat Engine 中找到目标数值的地址后录入。\n"
            "推荐用「模块+偏移」写法（如 game.exe+1A2B3C），游戏重启后依然有效；"
            "绿色地址可直接用，黑色地址请用指针路径并填写偏移链。"
        )
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        v.addWidget(tip)

        f = QFormLayout()
        f.setSpacing(8)

        self.e_name = QLineEdit()
        self.e_name.setPlaceholderText("如：金币 / 血量 / 无限弹药")
        f.addRow("名称 *", self.e_name)

        self.e_addr = QLineEdit()
        self.e_addr.setPlaceholderText("game.exe+1A2B3C 或 7FF6A1B2C3D0")
        self.e_addr.textChanged.connect(self._hint_addr)
        f.addRow("地址 *", self.e_addr)

        self.lbl_addr_hint = QLabel("")
        self.lbl_addr_hint.setObjectName("muted")
        f.addRow("", self.lbl_addr_hint)

        self.e_offsets = QLineEdit()
        self.e_offsets.setPlaceholderText("十六进制，逗号分隔，可留空。如：10, 4")
        f.addRow("指针偏移链", self.e_offsets)

        self.c_dtype = QComboBox()
        for k, label in DTYPE_LABELS.items():
            self.c_dtype.addItem(label, k)
        f.addRow("数据类型", self.c_dtype)

        self.c_control = QComboBox()
        for k, label in CONTROL_LABELS.items():
            self.c_control.addItem(label, k)
        self.c_control.currentIndexChanged.connect(self._sync_control_fields)
        f.addRow("界面控件", self.c_control)

        self.e_value = QLineEdit()
        self.e_value.setPlaceholderText("点击按钮 / 打开开关时写入的值")
        f.addRow("写入值", self.e_value)

        rng = QHBoxLayout()
        rng.setSpacing(6)
        self.s_min = QDoubleSpinBox()
        self.s_min.setRange(-1e12, 1e12)
        self.s_min.setDecimals(2)
        self.s_max = QDoubleSpinBox()
        self.s_max.setRange(-1e12, 1e12)
        self.s_max.setDecimals(2)
        self.s_max.setValue(100)
        self.s_step = QDoubleSpinBox()
        self.s_step.setRange(0.01, 1e9)
        self.s_step.setDecimals(2)
        self.s_step.setValue(1)
        for w, lab in ((self.s_min, "最小"), (self.s_max, "最大"), (self.s_step, "步长")):
            box = QHBoxLayout()
            box.addWidget(QLabel(lab))
            box.addWidget(w)
            rng.addLayout(box)
        f.addRow("范围（滑动条/数值框）", rng)

        self.e_note = QLineEdit()
        self.e_note.setPlaceholderText("备注（可选），如：改完需打开背包刷新")
        f.addRow("备注", self.e_note)

        self.chk_enabled = QCheckBox("启用该条目")
        self.chk_enabled.setChecked(True)
        f.addRow("", self.chk_enabled)

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

        self._sync_control_fields()

    # ------------------------------------------------------------ 逻辑
    def _hint_addr(self) -> None:
        m = _ADDR_RE.match(self.e_addr.text())
        if not self.e_addr.text().strip():
            self.lbl_addr_hint.setText("")
        elif m:
            kind = f"模块 {m.group('mod')} + 偏移" if m.group("mod") else "绝对地址"
            self.lbl_addr_hint.setText(f"✓ {kind}")
        else:
            self.lbl_addr_hint.setText("✗ 格式无法识别，应为 game.exe+1A2B3C 或十六进制地址")

    def _sync_control_fields(self) -> None:
        ctl = self.c_control.currentData()
        is_range = ctl in ("slider", "spin")
        self.s_min.setEnabled(is_range)
        self.s_max.setEnabled(is_range)
        self.s_step.setEnabled(is_range)
        self.e_value.setEnabled(ctl in ("button", "toggle"))
        if ctl == "toggle" and not self.e_value.text().strip():
            self.e_value.setText("1")

    def _fill(self, e: MemoryEntry) -> None:
        self.e_name.setText(e.name)
        self.e_addr.setText(e.addr)
        self.e_offsets.setText(", ".join(hex(o) for o in e.offsets))
        idx = list(DTYPE_LABELS).index(e.dtype) if e.dtype in DTYPE_LABELS else 0
        self.c_dtype.setCurrentIndex(idx)
        idx = list(CONTROL_LABELS).index(e.control) if e.control in CONTROL_LABELS else 1
        self.c_control.setCurrentIndex(idx)
        self.e_value.setText(e.value)
        self.s_min.setValue(e.minv)
        self.s_max.setValue(e.maxv)
        self.s_step.setValue(e.step or 1)
        self.e_note.setText(e.note)
        self.chk_enabled.setChecked(e.enabled)

    def _save(self) -> None:
        name = self.e_name.text().strip()
        addr = self.e_addr.text().strip()
        if not name:
            QMessageBox.warning(self, "缺少名称", "请填写条目名称（如：金币）。")
            return
        if not _ADDR_RE.match(addr):
            QMessageBox.warning(
                self, "地址格式错误",
                "地址应为以下两种写法之一：\n"
                "· 模块+偏移：game.exe+1A2B3C（推荐）\n"
                "· 绝对地址：7FF6A1B2C3D0",
            )
            return
        try:
            offsets = parse_offsets(self.e_offsets.text())
        except ValueError as exc:
            QMessageBox.warning(self, "偏移链格式错误", str(exc))
            return
        if self.s_min.value() >= self.s_max.value():
            QMessageBox.warning(self, "范围错误", "最大值必须大于最小值。")
            return

        e = self._orig or MemoryEntry()
        e.name = name
        e.addr = addr
        e.offsets = offsets
        e.dtype = self.c_dtype.currentData()
        e.control = self.c_control.currentData()
        e.value = self.e_value.text().strip() or "1"
        e.minv = self.s_min.value()
        e.maxv = self.s_max.value()
        e.step = self.s_step.value()
        e.note = self.e_note.text().strip()
        e.enabled = self.chk_enabled.isChecked()
        self.entry = e
        self.accept()

    @staticmethod
    def edit(trainer_title: str, entry: MemoryEntry | None, parent=None) -> MemoryEntry | None:
        dlg = MemoryEntryDialog(trainer_title, entry, parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.entry
        return None
