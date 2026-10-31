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
