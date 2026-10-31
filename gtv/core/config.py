"""GTV - Game Trainer Vault :: 全局配置与路径管理。

仅用于**单机/离线**游戏的修改器（Trainer）本地管理。
本程序不提供、不制作任何作弊程序本体，也不具备绕过反作弊/DRM 的能力。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "GameTrainerVault"
APP_ORG = "GTV"
APP_ID = "gtv.vault"
APP_VERSION = "1.0.0"

APP_TITLE = f"GTV · 单机游戏修改器管理器 v{APP_VERSION}"

DISCLAIMER = (
    "【用途声明】本工具仅用于整理与管理**单机/离线**游戏的修改器（Trainer），\n"
    "用于本地存档娱乐、无障碍辅助或降低重复劳动。\n"
    "严禁在任何联机模式、多人服务器、排行榜或竞技环境中使用，\n"
    "严禁用于损害他人游戏体验或绕过任何反作弊 / 版权保护措施。\n"
    "修改器与解压归档常被安全软件误报，请自行核验来源后再运行。"
)

# ---------------------------------------------------------------- 路径
BASE_DIR = Path(__file__).resolve().parents[2]          # 项目根目录
DATA_DIR = BASE_DIR / "data"                            # 内置元数据目录
ASSETS_DIR = BASE_DIR / "assets"
SEED_FILE = DATA_DIR / "trainers_seed.json"


def _user_data_root() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


APP_DIR = _user_data_root()          # 用户数据根目录
DB_PATH = APP_DIR / "library.db"
TRAINER_DIR = APP_DIR / "trainers"   # 修改器本体存放目录（每个一个子目录）
COVER_DIR = APP_DIR / "covers"       # 封面缓存
DOWNLOAD_DIR = APP_DIR / "downloads" # URL 下载暂存
BACKUP_DIR = APP_DIR / "backups"
LOG_DIR = APP_DIR / "logs"


def ensure_app_dirs() -> None:
    """确保用户数据目录结构存在。"""
    for d in (APP_DIR, TRAINER_DIR, COVER_DIR, DOWNLOAD_DIR, BACKUP_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- 常量
SOURCE_BUILTIN = "builtin"   # 内置目录条目（元数据索引，未安装本体）
SOURCE_LOCAL = "local"       # 用户通过本地文件导入
SOURCE_URL = "url"           # 用户通过下载链接导入

SOURCE_LABEL = {
    SOURCE_BUILTIN: "内置目录",
    SOURCE_LOCAL: "本地导入",
    SOURCE_URL: "链接下载",
}

# 允许导入的修改器本体扩展名
EXE_EXTS = {".exe"}
# 允许处理的归档扩展名
ARCHIVE_EXTS = {".zip", ".7z", ".rar"}
DOWNLOAD_EXTS = EXE_EXTS | ARCHIVE_EXTS
MAX_DOWNLOAD_BYTES = 300 * 1024 * 1024     # 单次下载上限 300MB

# 归档解压常见密码（用户在设置里可自定义，逗号分隔）
DEFAULT_ARCHIVE_PASSWORDS = ["", "flingtrainer.com", "FLiNGTrainer.COM", "flingtrainer"]

# 判定为"非修改器"可执行文件的关键词（安装器、卸载器、说明、破解补丁等）
NON_TRAINER_KEYWORDS = (
    "unins", "setup", "install", "uninstall", "crack", "keygen",
    "patcher", "readme", "help", "activate", "regfix", "dxwebsetup",
    "vcredist", "oalinst", "dotnet", "activator", "nfo",
)

DEFAULT_CATEGORIES = [
    "动作角色扮演", "射击", "开放世界", "生存建造", "策略模拟",
    "格斗", "竞速", "平台解谜", "恐怖", "其他",
]

ICON_TEXT = "GTV"


def db_url_display() -> str:
    return str(DB_PATH).replace(str(Path.home()), "~")
