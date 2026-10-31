"""内置目录加载：读取 data/trainers_seed.json 并合并入库。

设计要点：
1. 种子数据只含**元数据**（游戏名 / 分类 / 标签 / 常见功能），不含任何程序本体。
2. 每项生成指向 flingtrainer.com 的官方搜索页（稳定可用，不臆造详情页路径）。
3. 版本号不臆造，统一标记 "see official page"，用户导入本体后可在应用内改写。
"""
from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

from . import config
from .models import Option

HOME = "https://flingtrainer.com/"


def official_search_url(game: str) -> str:
    return HOME + "?s=" + urllib.parse.quote_plus(game)


def _hotkeys(count: int) -> list[str]:
    """FLiNG 风格热键：Num 1..9 之后使用 Num . / Ctrl+Num n。"""
    keys: list[str] = []
    for i in range(count):
        if i < 9:
            keys.append(f"Num {i + 1}")
        elif i < 18:
            keys.append(f"Ctrl+Num {i - 8}")
        elif i < 27:
            keys.append(f"Alt+Num {i - 17}")
        else:
            keys.append(f"Shift+Num {i - 26}")
    return keys


def build_options(opts: list[str]) -> list[Option]:
    return [Option(k, d) for k, d in zip(_hotkeys(len(opts)), opts)]


def load_seed(file: Path | None = None) -> list[dict]:
    path = Path(file or config.SEED_FILE)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for it in raw.get("items", []):
        game = it["game"].strip()
        cn = (it.get("cn") or "").strip()
        title_game = f"{cn} / {game}" if cn else game
        opts = build_options(it.get("opts", []))
        meta_opt = Option("提示", "以上为常见功能模板，热键请以实际下载的 Trainer 界面为准")
        opts.append(meta_opt)
        items.append(
            {
                "title": f"{game} Trainer",
                "game_title": title_game,
                "category": it.get("cat", "其他"),
                "tags_json": json.dumps(it.get("tags", []), ensure_ascii=False),
                "author": raw.get("meta", {}).get("author", "FLiNG"),
                "source_url": official_search_url(game),
                "options_json": json.dumps([o.to_dict() for o in opts], ensure_ascii=False),
                "online_risk": bool(it.get("online", 0)),
                "cover_color": it.get("color", "#3B6EA5"),
                "version": "see official page",
            }
        )
    return items


def seed_meta(file: Path | None = None) -> dict:
    path = Path(file or config.SEED_FILE)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("meta", {})


def load_extra_index(file: Path) -> None:
    """可选：加载用户自己维护的同结构 JSON 索引（预留扩展点）。"""
    raise NotImplementedError("预留接口，暂未实现")
