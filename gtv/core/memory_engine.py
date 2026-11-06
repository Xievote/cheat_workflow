"""内存引擎：基于 pymem 的进程附加、地址解析与内存读写。

职责边界：
* 只负责"读写哪个进程的哪块内存"，不关心 UI 与持久化。
* 所有异常就地捕获并转为 (False, 消息) 或 error 信号，UI 层永不崩。
* 地址写法与 Cheat Engine 对齐：
    - "7FF6A1B2C3D0"          绝对地址
    - "game.exe+1A2B3C"       模块基址 + 偏移（推荐，跨重启稳定）
    - offsets 指针偏移链：    [0x10, 0x4] 逐级解引用后相加

权限说明：读写其他进程内存需要足够权限。若目标游戏以管理员运行，
GTV 也必须以管理员运行，否则附加成功但读写会报"拒绝访问"。
"""
from __future__ import annotations

import re

from PySide6.QtCore import QObject, Signal

from .models import MemoryEntry

try:  # pymem 仅 Windows 可用；缺失时引擎降级为不可用状态
    import pymem
    import pymem.exception
    import pymem.process

    HAVE_PYMEM = True
except Exception:  # noqa: BLE001
    HAVE_PYMEM = False

_ADDR_RE = re.compile(r"^\s*(?:(?P<mod>[^+\s]+)\s*\+\s*)?(?P<off>0x[0-9a-fA-F]+|[0-9a-fA-F]+)\s*$")

# dtype → (read_method, write_method, size)
_TYPE_MAP = {
    "int32": ("read_int", "write_int", 4),
    "int64": ("read_long", "write_long", 8),
    "int16": ("read_short", "write_short", 2),
    "byte": ("read_uchar", "write_uchar", 1),
    "float": ("read_float", "write_float", 4),
    "double": ("read_double", "write_double", 8),
}

_FLOAT_TYPES = {"float", "double"}


class MemoryEngine(QObject):
    """单例引擎：同一时间只附加一个游戏进程。"""

    attached = Signal(int, str)     # pid, 进程名
    detached = Signal(str)          # 原因
    error = Signal(str)             # 读写出错（附加态丢失等）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pm = None            # pymem.Pymem
        self._pid = 0
        self._proc_name = ""

    # ------------------------------------------------------------ 状态
    @property
    def is_attached(self) -> bool:
        return self._pm is not None

    @property
    def pid(self) -> int:
        return self._pid

    @property
    def process_name(self) -> str:
        return self._proc_name

    # ------------------------------------------------------------ 附加 / 分离
    def find_pids(self, name: str) -> list[tuple[int, str]]:
        """按进程名（不区分大小写）查找所有匹配的 (pid, 进程名)。"""
        if not HAVE_PYMEM:
            return []
        target = name.strip().lower()
        out: list[tuple[int, str]] = []
        try:
            for p in pymem.process.list_processes():
                pname = (p.szExeFile or "").strip()
                if pname.lower() == target:
                    out.append((int(p.th32ProcessID), pname))
        except Exception:  # noqa: BLE001
            pass
        return out

    def attach_name(self, name: str) -> tuple[bool, str]:
        """按进程名附加（同名多进程时取第一个）。"""
        if not HAVE_PYMEM:
            return False, "未安装 pymem 库，内存功能不可用（pip install pymem）"
        self.detach(reason="切换目标进程")
        try:
            pm = pymem.Pymem()
            pm.open_process_from_name(name.strip())
        except pymem.exception.ProcessNotFound:
            return False, f"找不到进程：{name}"
        except Exception as exc:  # noqa: BLE001
            return False, f"附加进程失败：{exc}"
        return self._finish_attach(pm)

    def attach_pid(self, pid: int) -> tuple[bool, str]:
        if not HAVE_PYMEM:
            return False, "未安装 pymem 库，内存功能不可用（pip install pymem）"
        self.detach(reason="切换目标进程")
        try:
            pm = pymem.Pymem()
            pm.open_process_from_id(int(pid))
        except Exception as exc:  # noqa: BLE001
            return False, f"附加 PID {pid} 失败：{exc}"
        return self._finish_attach(pm)

    def _finish_attach(self, pm) -> tuple[bool, str]:
        self._pm = pm
        self._pid = int(pm.process_id)
        # 取进程名用于展示（szExeFile 可能为 bytes，统一转 str）
        try:
            from pymem import process as _pp

            entry = _pp.process_from_id(pm.process_id)
            name = entry.szExeFile if entry else ""
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            self._proc_name = name.strip() or f"PID {pm.process_id}"
        except Exception:  # noqa: BLE001
            self._proc_name = f"PID {pm.process_id}"
        self.attached.emit(self._pid, self._proc_name)
        return True, f"已附加 {self._proc_name}（PID {self._pid}）"

    def detach(self, reason: str = "手动分离") -> None:
        if self._pm is None:
            return
        try:
            self._pm.close_process()
        except Exception:  # noqa: BLE001
            pass
        self._pm = None
        self._pid = 0
        self._proc_name = ""
        self.detached.emit(reason)

    def alive(self) -> bool:
        """检查附加的进程是否仍然存活（用 PEB 探测，读不到即视为已退出）。"""
        if self._pm is None:
            return False
        try:
            self._pm.read_bytes(self._pm.process_base.lpBaseOfDll, 2)
            return True
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------ 地址解析
    def resolve(self, entry: MemoryEntry) -> int:
        """把 MemoryEntry 解析为最终线性地址。失败抛异常。"""
        if self._pm is None:
            raise RuntimeError("尚未附加进程")
        m = _ADDR_RE.match(entry.addr or "")
        if not m:
            raise ValueError(f"地址格式无法识别：{entry.addr!r}")
        off = int(m.group("off"), 16)
        mod = m.group("mod")
        if mod:
            module = pymem.process.module_from_name(self._pm.process_handle, mod)
            if module is None:
                raise ValueError(f"目标进程中找不到模块：{mod}")
            addr = module.lpBaseOfDll + off
        else:
            addr = off
        # 指针链：逐级解引用 + 偏移（与 CE 的指针路径一致）
        for i, o in enumerate(entry.offsets):
            try:
                ptr = self._pm.read_ulonglong(addr)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"指针链第 {i + 1} 级解引用失败（{hex(addr)}）：{exc}") from exc
            if not ptr:
                raise RuntimeError(f"指针链第 {i + 1} 级读到空指针（{hex(addr)}）")
            addr = ptr + o
        return addr

    # ------------------------------------------------------------ 读 / 写
    def read(self, entry: MemoryEntry):
        """读取条目当前值。失败返回 None 并发 error 信号。"""
        if self._pm is None:
            return None
        try:
            addr = self.resolve(entry)
            method = getattr(self._pm, _TYPE_MAP[entry.dtype][0])
            return method(addr)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(f"读取「{entry.name}」失败：{exc}")
            return None

    def read_raw(self, addr: int, dtype: str):
        if self._pm is None:
            return None
        try:
            return getattr(self._pm, _TYPE_MAP[dtype][0])(addr)
        except Exception:  # noqa: BLE001
            return None

    def write(self, entry: MemoryEntry, value) -> tuple[bool, str]:
        """把 value 写入条目地址。value 类型需与 dtype 匹配（int/float）。"""
        if self._pm is None:
            return False, "尚未附加进程"
        try:
            addr = self.resolve(entry)
            method = getattr(self._pm, _TYPE_MAP[entry.dtype][1])
            method(addr, value)
            return True, f"已写入「{entry.name}」= {value}"
        except Exception as exc:  # noqa: BLE001
            msg = f"写入「{entry.name}」失败：{exc}"
            self.error.emit(msg)
            return False, msg

    def write_raw(self, addr: int, dtype: str, value) -> bool:
        if self._pm is None:
            return False
        try:
            getattr(self._pm, _TYPE_MAP[dtype][1])(addr, value)
            return True
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def cast_value(dtype: str, value) -> object:
        """把控件传来的数值转成该 dtype 的合法写入值。"""
        if dtype in _FLOAT_TYPES:
            return float(value)
        if dtype == "byte":
            return int(value) & 0xFF
        return int(value)
