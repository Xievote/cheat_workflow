"""目录扫描：在用户指定路径下发现可能的修改器（zip / exe / 已解压文件夹）。"""
from __future__ import annotations

import concurrent.futures as _fut
from dataclasses import dataclass
from pathlib import Path

from . import config
from .utils import human_size, looks_like_trainer, parse_version_from_name


@dataclass
class Candidate:
    path: Path
    kind: str            # archive / exe / folder
    guess_game: str
    version: str
    size: str

    def as_row(self) -> list[str]:
        return [self.guess_game, self.kind, self.version or "-", self.size, str(self.path)]


_KIND_LABEL = {"archive": "压缩包", "exe": "可执行", "folder": "文件夹"}


def _guess_game(name: str) -> str:
    """从文件名推断游戏名：去掉 Trainer 后缀、版本号、来源标记。"""
    base = name
    for ext in (".zip", ".7z", ".rar", ".exe"):
        if base.lower().endswith(ext):
            base = base[: -len(ext)]
            break
    low = base.lower()
    for mark in ("trainer", "trainer.exe", "fling", "cheat", "mrantifun", "wemod"):
        idx = low.find(mark)
        if idx != -1:
            base = base[:idx]
            low = base.lower()
    base = base.strip(" .-_+[]()")
    for tok in ("v1", "v2", "v3"):
        # 不处理，交由 parse_version 处理
        pass
    return base.strip() or name


def scan(root: Path, depth: int = 3, max_items: int = 800) -> list[Candidate]:
    root = Path(root)
    if not root.exists():
        return []
    out: list[Candidate] = []

    def walk(dir_path: Path, level: int):
        if level > depth or len(out) >= max_items:
            return
        try:
            entries = sorted(dir_path.iterdir())
        except Exception:  # noqa: BLE001
            return
        dirs: list[Path] = []
        for p in entries:
            try:
                if p.is_file():
                    suf = p.suffix.lower()
                    if suf in config.ARCHIVE_EXTS:
                        out.append(Candidate(p, "archive", _guess_game(p.name),
                                             parse_version_from_name(p.name), human_size(p.stat().st_size)))
                    elif suf in config.EXE_EXTS and looks_like_trainer(p.name):
                        out.append(Candidate(p, "exe", _guess_game(p.name),
                                             parse_version_from_name(p.name), human_size(p.stat().st_size)))
                elif p.is_dir():
                    dirs.append(p)
            except Exception:  # noqa: BLE001
                continue
            if len(out) >= max_items:
                break
        for d in dirs:
            # 已解压的修改器文件夹：内含 exe 且不含大量子文件
            try:
                has_exe = any(x.suffix.lower() == ".exe" for x in d.iterdir() if x.is_file())
            except Exception:  # noqa: BLE001
                has_exe = False
            if has_exe and len(list(d.iterdir())) <= 40:
                out.append(Candidate(d, "folder", _guess_game(d.name), "", "-"))
            walk(d, level + 1)

    with _fut.ThreadPoolExecutor(max_workers=1) as ex:
        ex.submit(walk, root, 0).result()
    return out[:max_items]


def dedup(cands: list[Candidate], db) -> list[Candidate]:
    """过滤掉库中已存在的（按 exe 路径）。"""
    import sqlite3

    rows = db._query("SELECT exe_path FROM trainers WHERE exe_path<>''")
    known = {r["exe_path"].lower() for r in rows}
    return [c for c in cands if str(c.path).lower() not in known]
