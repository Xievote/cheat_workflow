"""通用工具：文件名清洗、路径相对化、封面绘制数据、模糊匹配打分。"""
from __future__ import annotations

import difflib
import hashlib
import re
import unicodedata
from pathlib import Path

_INVALID = r'<>:"/\|?*'


def safe_name(name: str, limit: int = 60) -> str:
    """生成安全的目录/文件名。"""
    name = unicodedata.normalize("NFKC", str(name)).strip()
    name = re.sub(r"\s+", " ", name)
    for ch in _INVALID:
        name = name.replace(ch, "")
    name = name.strip(" .")
    return (name or "unnamed")[:limit]


def short_path(p: str | Path, max_len: int = 60) -> str:
    s = str(p)
    if len(s) <= max_len:
        return s
    return s[: max_len // 2 - 2] + "..." + s[-(max_len // 2 - 1) :]


def file_sha1(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def human_size(n: float) -> str:
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB"):
        if n < step or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= step
    return f"{n:.1f} GB"


def parse_version_from_name(name: str) -> str:
    """从文件名里抽一个粗略版本号，如 Trainer_v1.2 / +27 v1.03。"""
    m = re.search(r"v(\d+(?:\.\d+){0,3})", name, re.I)
    return m.group(0) if m else ""


def looks_like_trainer(name: str) -> bool:
    """根据文件名猜测是否为修改器本体。"""
    low = name.lower()
    if any(k in low for k in NON_TRAINER):
        return False
    return True


NON_TRAINER = tuple(
    k.lower() for k in (
        "unins", "setup", "install", "uninstall", "crack", "keygen", "patcher",
        "readme", "help", "activate", "activator", "regfix", "dxwebsetup",
        "vcredist", "oalinst", "dotnet", "nfo", "license", "changelog",
    )
)
