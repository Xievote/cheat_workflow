"""导入器：把本地文件 / 文件夹 / 归档 / 下载链接变成库内条目。

安全策略
--------
* 解压做 **Zip-Slip 防护**：任何成员的目标路径必须落在解压根目录内，绝对路径 / .. / 盘符一律拒绝。
* 单成员解压上限 + 成员数量上限（防止解压炸弹）。
* 下载：仅 http/https，限制体积，扩展名白名单，先落地 downloads/ 再校验解压。
"""
from __future__ import annotations

import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import config
from .utils import human_size, looks_like_trainer, parse_version_from_name, safe_name, short_path

UA = "GTV/1.0 (offline single-player trainer manager)"
MAX_MEMBERS = 2000
MAX_SINGLE_RATIO = 400          # 单文件压缩比上限
PROGRESS = Callable[[int, int, str], None] | None


class ImportError_(Exception):
    """导入失败（可读消息直接呈现给用户）。"""


@dataclass
class ImportResult:
    ok: bool = False
    message: str = ""
    trainer_dir: str = ""
    exe_path: str = ""
    candidates: list[str] = field(default_factory=list)
    extracted_root: str = ""


# ----------------------------------------------------------------- 选择主程序
def _exe_score(p: Path) -> tuple[int, int]:
    """给候选 exe 打分：含 trainer 关键词加分，排除安装器/卸载器。"""
    low = p.name.lower()
    if not looks_like_trainer(p.name):
        return (-1, 0)
    score = 0
    for kw in ("trainer", "trainer.exe", "fling", "cheat", "+", "v1", "v2"):
        if kw in low:
            score += 3 if kw == "trainer" else 1
    if "fling" in low:
        score += 5
    size = p.stat().st_size if p.exists() else 0
    return (score, min(size // (1024 * 1024), 200))


def find_exe_candidates(root: Path, recursive: bool = True) -> list[Path]:
    it = root.rglob("*.exe") if recursive else root.glob("*.exe")
    cands = [p for p in it if p.is_file()]
    cands.sort(key=_exe_score, reverse=True)
    return [p for p in cands if _exe_score(p)[0] >= 0] or cands


def pick_main_exe(root: Path) -> Path | None:
    cands = find_exe_candidates(root)
    return cands[0] if cands else None


# ----------------------------------------------------------------- 解压
def _safe_extract_zip(zf: zipfile.ZipFile, dest: Path, passwords: list[str]) -> list[str]:
    members = zf.infolist()
    if len(members) > MAX_MEMBERS:
        raise ImportError_(f"归档成员过多（{len(members)}），已中止")
    dest.mkdir(parents=True, exist_ok=True)
    dest_root = dest.resolve()

    pwd_used = None
    if zf.needs_password() if hasattr(zf, "needs_password") else False:
        raise ImportError_("不支持的加密方式")
    for pwd in passwords:
        if pwd == "":
            try:
                bad = zf.testzip()
            except RuntimeError:
                continue
        else:
            try:
                # 探测密码：读取第一个成员的第一个字节
                first = members[0]
                with zf.open(first, pwd=pwd.encode()) as fh:
                    fh.read(1)
            except Exception:
                continue
        pwd_used = pwd
        break
    else:
        raise ImportError_("压缩包需要密码，且给定密码均不正确（可在设置里补充常用密码）")

    written: list[str] = []
    for info in members:
        name = info.filename
        target = (dest_root / name).resolve()
        if not str(target).startswith(str(dest_root) + "\\") and not str(target).startswith(str(dest_root) + "/"):
            if target != dest_root:
                raise ImportError_(f"检测到不安全的归档路径，已拒绝解压：{short_path(name)}")
        if target == dest_root:
            continue
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if info.file_size > MAX_SINGLE_RATIO * max(info.compress_size, 1) and info.file_size > 200 * 1024 * 1024:
            raise ImportError_(f"成员压缩比异常（疑似解压炸弹）：{short_path(name)}")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with zf.open(info, pwd=pwd_used.encode() if pwd_used else None) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1 << 20)
            written.append(str(target))
        except Exception as exc:  # noqa: BLE001
            raise ImportError_(f"解压 {short_path(name)} 失败：{exc}") from exc
    return written


def _external_7z() -> str | None:
    for exe in ("7z", "7z.exe", "7za", "7za.exe"):
        found = shutil.which(exe)
        if found:
            return found
    for p in (
        Path(r"C:\Program Files\7-Zip\7z.exe"),
        Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
        Path(r"C:\Program Files\WinRAR\WinRAR.exe"),
    ):
        if p.exists():
            return str(p)
    return None


def extract_archive(archive: Path, dest: Path, passwords: list[str] | None = None) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    passwords = passwords if passwords is not None else list(config.DEFAULT_ARCHIVE_PASSWORDS)
    ext = archive.suffix.lower()

    if ext == ".zip":
        with zipfile.ZipFile(archive) as zf:
            return _safe_extract_zip(zf, dest, passwords)

    tool = _external_7z()
    if not tool:
        raise ImportError_(
            f"{ext} 需要外部解压工具：请安装 7-Zip（推荐）或手动解压后导入文件夹；"
            "也可先把 rar/7z 转成 zip 再导入。"
        )
    cmd = [tool, "x", "-y", f"-o{dest}"]
    for pwd in passwords:
        if pwd:
            cmd.append(f"-p{pwd}")
            break
    cmd.append(str(archive))
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=300, shell=False)
    except Exception as exc:  # noqa: BLE001
        raise ImportError_(f"调用解压工具失败：{exc}") from exc
    if out.returncode != 0:
        raise ImportError_(f"解压失败：{(out.stderr or out.stdout or '').strip()[:300]}")
    return [str(p) for p in dest.rglob("*") if p.is_file()]


# ----------------------------------------------------------------- 下载
def _filename_from_url(url: str) -> str:
    name = urllib.parse.unquote(urllib.parse.urlparse(url).path).rsplit("/", 1)[-1]
    return name or "download.bin"


def download_file(url: str, dest_dir: Path | None = None, progress: PROGRESS = None, timeout: int = 60) -> Path:
    dest_dir = Path(dest_dir or config.DOWNLOAD_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ImportError_("仅支持 http / https 链接")
    if not re.search(r"\.(zip|7z|rar|exe)$", parsed.path.lower()):
        raise ImportError_("链接看起来不是修改器文件（需以 .zip/.7z/.rar/.exe 结尾）")

    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)  # noqa: S310
    except urllib.error.HTTPError as exc:
        raise ImportError_(f"下载失败：HTTP {exc.code}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ImportError_(f"下载失败：{exc}") from exc

    total = int(resp.headers.get("Content-Length") or 0)
    if total and total > config.MAX_DOWNLOAD_BYTES:
        resp.close()
        raise ImportError_(f"文件过大（{human_size(total)}），超过上限 {human_size(config.MAX_DOWNLOAD_BYTES)}")

    name = _filename_from_url(url)
    dest = dest_dir / safe_name(name, 120)
    i = 1
    while dest.exists():
        dest = dest_dir / safe_name(f"{Path(name).stem}_{i}{Path(name).suffix}", 120)
        i += 1

    done = 0
    try:
        with open(dest, "wb") as fh:
            while True:
                chunk = resp.read(1 << 18)
                if not chunk:
                    break
                done += len(chunk)
                if done > config.MAX_DOWNLOAD_BYTES:
                    raise ImportError_("下载体积超过上限，已中止")
                fh.write(chunk)
                if progress:
                    progress(done, total, human_size(done))
    finally:
        resp.close()
    if progress:
        progress(done, done, "完成")
    return dest


# ----------------------------------------------------------------- 落地到库
def materialize(src: Path, game_title: str, version: str = "") -> ImportResult:
    """把来源（exe/文件夹）复制到库目录 TRAINER_DIR/<safe name>/ 下并返回主 exe。"""
    src = Path(src)
    if not src.exists():
        return ImportResult(False, f"路径不存在：{short_path(str(src))}")

    base = safe_name(game_title or src.stem)
    target_dir = config.TRAINER_DIR / base
    n = 1
    while target_dir.exists():
        target_dir = config.TRAINER_DIR / f"{base}_{n}"
        n += 1
    target_dir.mkdir(parents=True, exist_ok=True)

    if src.is_file():
        if src.suffix.lower() in config.ARCHIVE_EXTS:
            files = extract_archive(src, target_dir)
            if not files:
                return ImportResult(False, "解压后没有可用文件", trainer_dir=str(target_dir))
        elif src.suffix.lower() in config.EXE_EXTS:
            shutil.copy2(src, target_dir / safe_name(src.name, 120))
        else:
            return ImportResult(False, f"不支持的文件类型：{src.suffix}")
    else:
        for item in src.iterdir():
            d = target_dir / safe_name(item.name, 120)
            if item.is_dir():
                shutil.copytree(item, d, dirs_exist_ok=True)
            else:
                shutil.copy2(item, d)

    cands = find_exe_candidates(target_dir)
    main = cands[0] if cands else None
    if main is None:
        return ImportResult(
            False,
            "已复制到库中，但未找到可执行文件，请手动指定主程序",
            trainer_dir=str(target_dir),
        )
    return ImportResult(
        True,
        f"已导入到库：{short_path(str(target_dir))}",
        trainer_dir=str(target_dir),
        exe_path=str(main),
        candidates=[str(c) for c in cands[:8]],
    )


def quick_import_url(url: str, game_title: str, progress: PROGRESS = None) -> ImportResult:
    file = download_file(url, progress=progress)
    if file.suffix.lower() in config.ARCHIVE_EXTS:
        return materialize(file, game_title or file.stem)
    return materialize(file, game_title or file.stem)
