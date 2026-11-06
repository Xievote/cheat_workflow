"""数据模型（纯数据对象，不依赖 Qt）。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Iterable


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def rowget(row: Any, key: str, default: Any = None) -> Any:
    """同时兼容 sqlite3.Row 与 dict 的行读取。"""
    try:
        val = row[key]
    except (IndexError, KeyError, TypeError):
        return default
    return default if val is None else val


def loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


@dataclass
class Option:
    """一条修改器功能项（热键 + 说明）。"""

    key: str = ""
    desc: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Option":
        return Option(str(d.get("key", "")), str(d.get("desc", "")), str(d.get("note", "")))


@dataclass
class Trainer:
    """一个游戏修改器条目。"""

    id: int | None = None
    title: str = ""            # 修改器标题（如 "ELDEN RING Trainer +27"）
    game_title: str = ""       # 游戏名
    category: str = "其他"
    tags: list[str] = field(default_factory=list)
    version: str = ""
    author: str = "FLiNG"
    source: str = "builtin"        # builtin / local / url
    source_url: str = ""           # 官方页面（用于跳转下载/查看）
    exe_path: str = ""             # 本地可执行文件路径
    work_dir: str = ""             # 工作目录
    args: str = ""                 # 启动参数
    run_as_admin: bool = False     # 是否以管理员权限启动
    cover_color: str = "#3B6EA5"   # 生成占位封面的主色
    cover_path: str = ""           # 自定义封面图片
    options: list[Option] = field(default_factory=list)
    notes: str = ""
    online_risk: bool = False      # 该游戏是否含联机模式（需要额外警示）
    favorite: bool = False
    run_count: int = 0
    last_run_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    # -------- 序列化
    def to_row(self) -> dict:
        return {
            "title": self.title,
            "game_title": self.game_title,
            "category": self.category,
            "tags": dumps(self.tags),
            "version": self.version,
            "author": self.author,
            "source": self.source,
            "source_url": self.source_url,
            "exe_path": self.exe_path,
            "work_dir": self.work_dir,
            "args": self.args,
            "run_as_admin": int(self.run_as_admin),
            "cover_color": self.cover_color,
            "cover_path": self.cover_path,
            "options": dumps([o.to_dict() for o in self.options]),
            "notes": self.notes,
            "online_risk": int(self.online_risk),
            "favorite": int(self.favorite),
            "run_count": self.run_count,
            "last_run_at": self.last_run_at,
            "created_at": self.created_at or _now(),
            "updated_at": _now(),
        }

    @staticmethod
    def from_row(row: dict) -> "Trainer":
        g = rowget
        return Trainer(
            id=g(row, "id"),
            title=g(row, "title", "") or "",
            game_title=g(row, "game_title", "") or "",
            category=g(row, "category", "其他") or "其他",
            tags=loads(g(row, "tags"), []) or [],
            version=g(row, "version", "") or "",
            author=g(row, "author", "") or "",
            source=g(row, "source", "builtin") or "builtin",
            source_url=g(row, "source_url", "") or "",
            exe_path=g(row, "exe_path", "") or "",
            work_dir=g(row, "work_dir", "") or "",
            args=g(row, "args", "") or "",
            run_as_admin=bool(g(row, "run_as_admin", 0)),
            cover_color=g(row, "cover_color") or "#3B6EA5",
            cover_path=g(row, "cover_path", "") or "",
            options=[Option.from_dict(o) for o in loads(g(row, "options"), []) or []],
            notes=g(row, "notes", "") or "",
            online_risk=bool(g(row, "online_risk", 0)),
            favorite=bool(g(row, "favorite", 0)),
            run_count=int(g(row, "run_count", 0) or 0),
            last_run_at=g(row, "last_run_at", "") or "",
            created_at=g(row, "created_at", "") or "",
            updated_at=g(row, "updated_at", "") or "",
        )

    @property
    def installed(self) -> bool:
        return bool(self.exe_path)

    @property
    def display_name(self) -> str:
        return self.title or self.game_title or "(未命名)"


@dataclass
class MemoryEntry:
    """一条内存地址配置：由用户在 Cheat Engine 中找到地址后录入。

    地址写法（addr 字段）：
    * 绝对地址：      "7FF6A1B2C3D0" 或 "0x7FF6A1B2C3D0"
    * 模块+偏移：     "game.exe+1A2B3C"（推荐，游戏重启后依然有效）

    offsets 字段为指针偏移链（十六进制，如 [0x10, 0x4]），可为空。
    解析规则（与 Cheat Engine 一致）：
      最终地址 = *(基地址 + 模块偏移) + offset1 → 再解引用 + offset2 …
    """

    DTYPES = ("int32", "int64", "int16", "byte", "float", "double")
    CONTROLS = ("slider", "spin", "button", "toggle")

    id: int | None = None
    trainer_id: int | None = None
    name: str = ""             # 显示名，如 "金币" / "血量"
    addr: str = ""             # 基地址（见上文写法）
    offsets: list[int] = field(default_factory=list)   # 指针偏移链
    dtype: str = "int32"       # int32/int64/int16/byte/float/double
    control: str = "spin"      # slider/spin/button/toggle
    value: str = "999"         # button 写入值 / toggle 开启值（关闭固定写 0）
    minv: float = 0            # slider/spin 下限
    maxv: float = 100          # slider/spin 上限
    step: float = 1            # slider/spin 步长
    note: str = ""
    enabled: bool = True
    sort: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_row(self) -> dict:
        return {
            "trainer_id": self.trainer_id,
            "name": self.name,
            "addr": self.addr.strip(),
            "offsets": dumps([hex(o) for o in self.offsets]),
            "dtype": self.dtype,
            "control": self.control,
            "value": self.value,
            "minv": self.minv,
            "maxv": self.maxv,
            "step": self.step or 1,
            "note": self.note,
            "enabled": int(self.enabled),
            "sort": self.sort,
            "created_at": self.created_at or _now(),
            "updated_at": _now(),
        }

    @staticmethod
    def from_row(row) -> "MemoryEntry":
        g = rowget
        offs_raw = loads(g(row, "offsets"), []) or []
        offsets: list[int] = []
        for o in offs_raw:
            try:
                offsets.append(int(str(o), 16))
            except (ValueError, TypeError):
                continue
        return MemoryEntry(
            id=g(row, "id"),
            trainer_id=g(row, "trainer_id"),
            name=g(row, "name", "") or "",
            addr=g(row, "addr", "") or "",
            offsets=offsets,
            dtype=g(row, "dtype", "int32") or "int32",
            control=g(row, "control", "spin") or "spin",
            value=str(g(row, "value", "") or ""),
            minv=float(g(row, "minv", 0) or 0),
            maxv=float(g(row, "maxv", 100) or 100),
            step=float(g(row, "step", 1) or 1),
            note=g(row, "note", "") or "",
            enabled=bool(g(row, "enabled", 1)),
            sort=int(g(row, "sort", 0) or 0),
            created_at=g(row, "created_at", "") or "",
            updated_at=g(row, "updated_at", "") or "",
        )

    @property
    def addr_display(self) -> str:
        """给 UI 显示的完整地址描述。"""
        s = self.addr
        if self.offsets:
            s += " → " + " → ".join(hex(o) for o in self.offsets)
        return s


@dataclass
class LaunchRecord:
    """一次启动记录。"""

    id: int | None = None
    trainer_id: int | None = None
    trainer_title: str = ""
    pid: int = 0
    started_at: str = ""
    ended_at: str = ""
    duration_sec: int = 0
    exit_code: int | None = None
    status: str = "running"     # running / finished / failed / killed
    message: str = ""

    def to_row(self) -> dict:
        return {
            "trainer_id": self.trainer_id,
            "pid": self.pid,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_sec": self.duration_sec,
            "exit_code": self.exit_code,
            "status": self.status,
            "message": self.message,
        }

    @staticmethod
    def from_row(row: dict) -> "LaunchRecord":
        g = rowget
        return LaunchRecord(
            id=g(row, "id"),
            trainer_id=g(row, "trainer_id"),
            pid=int(g(row, "pid") or 0),
            started_at=g(row, "started_at", "") or "",
            ended_at=g(row, "ended_at", "") or "",
            duration_sec=int(g(row, "duration_sec") or 0),
            exit_code=g(row, "exit_code"),
            status=g(row, "status", "") or "",
            trainer_title=g(row, "trainer_title", "") or "",
            message=g(row, "message", "") or "",
        )


@dataclass
class Session:
    """运行中的修改器会话（内存态）。"""

    trainer_id: int
    pid: int
    started_at: float          # time.time()
    proc: Any = None           # subprocess.Popen

    def elapsed_sec(self) -> int:
        import time

        return int(time.time() - self.started_at)


def human_duration(sec: int) -> str:
    if sec < 60:
        return f"{sec} 秒"
    if sec < 3600:
        return f"{sec // 60} 分 {sec % 60} 秒"
    return f"{sec // 3600} 时 {(sec % 3600) // 60} 分"
