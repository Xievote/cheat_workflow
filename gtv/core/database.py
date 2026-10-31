"""SQLite 持久层：修改器库、启动记录、设置。

所有 SQL 内嵌，无需外部 .sql 文件即可打包。
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Iterable

from . import config
from .models import LaunchRecord, Trainer, _now

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS trainers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT NOT NULL DEFAULT '',
    game_title     TEXT NOT NULL DEFAULT '',
    category       TEXT NOT NULL DEFAULT '其他',
    tags           TEXT NOT NULL DEFAULT '[]',
    version        TEXT NOT NULL DEFAULT '',
    author         TEXT NOT NULL DEFAULT '',
    source         TEXT NOT NULL DEFAULT 'builtin',
    source_url     TEXT NOT NULL DEFAULT '',
    exe_path       TEXT NOT NULL DEFAULT '',
    work_dir       TEXT NOT NULL DEFAULT '',
    args           TEXT NOT NULL DEFAULT '',
    run_as_admin   INTEGER NOT NULL DEFAULT 0,
    cover_color    TEXT NOT NULL DEFAULT '#3B6EA5',
    cover_path     TEXT NOT NULL DEFAULT '',
    options        TEXT NOT NULL DEFAULT '[]',
    notes          TEXT NOT NULL DEFAULT '',
    online_risk    INTEGER NOT NULL DEFAULT 0,
    favorite       INTEGER NOT NULL DEFAULT 0,
    run_count      INTEGER NOT NULL DEFAULT 0,
    last_run_at    TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT '',
    updated_at     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_trainers_game  ON trainers(game_title);
CREATE INDEX IF NOT EXISTS idx_trainers_cat   ON trainers(category);
CREATE INDEX IF NOT EXISTS idx_trainers_fav   ON trainers(favorite);

CREATE TABLE IF NOT EXISTS launch_records (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trainer_id    INTEGER,
    pid           INTEGER NOT NULL DEFAULT 0,
    started_at    TEXT NOT NULL DEFAULT '',
    ended_at      TEXT NOT NULL DEFAULT '',
    duration_sec  INTEGER NOT NULL DEFAULT 0,
    exit_code     INTEGER,
    status        TEXT NOT NULL DEFAULT 'finished',
    message       TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(trainer_id) REFERENCES trainers(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_records_trainer ON launch_records(trainer_id);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class Database:
    """线程安全的轻量 DAO（SQLite 连接带锁复用）。"""

    def __init__(self, db_path: Path | None = None):
        config.ensure_app_dirs()
        self._conn = connect(db_path)
        self._lock = threading.RLock()
        self.init_schema()

    # ------------------------------------------------------------ 基础
    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def _query(self, sql: str, params: Iterable = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            rows = cur.fetchall()
        return rows

    def _exec(self, sql: str, params: Iterable = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return cur

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------ settings
    def get_setting(self, key: str, default: str = "") -> str:
        rows = self._query("SELECT value FROM settings WHERE key=?", (key,))
        return rows[0]["value"] if rows else default

    def set_setting(self, key: str, value: str) -> None:
        self._exec(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )

    # ------------------------------------------------------------ trainers
    def add_trainer(self, t: Trainer) -> int:
        row = t.to_row()
        cols = ", ".join(row.keys())
        marks = ", ".join("?" for _ in row)
        cur = self._exec(f"INSERT INTO trainers({cols}) VALUES({marks})", row.values())
        return int(cur.lastrowid)

    def update_trainer(self, t: Trainer) -> None:
        if not t.id:
            raise ValueError("trainer id 为空，无法更新")
        row = t.to_row()
        row.pop("created_at", None)
        sets = ", ".join(f"{k}=?" for k in row.keys())
        self._exec(f"UPDATE trainers SET {sets} WHERE id=?", (*row.values(), t.id))

    def get_trainer(self, tid: int) -> Trainer | None:
        rows = self._query("SELECT * FROM trainers WHERE id=?", (tid,))
        return Trainer.from_row(rows[0]) if rows else None

    def get_by_exe(self, exe: str) -> Trainer | None:
        rows = self._query("SELECT * FROM trainers WHERE lower(exe_path)=lower(?)", (exe,))
        return Trainer.from_row(rows[0]) if rows else None

    def delete_trainer(self, tid: int) -> None:
        self._exec("DELETE FROM launch_records WHERE trainer_id=?", (tid,))
        self._exec("DELETE FROM trainers WHERE id=?", (tid,))

    def toggle_favorite(self, tid: int) -> bool:
        rows = self._query("SELECT favorite FROM trainers WHERE id=?", (tid,))
        if not rows:
            return False
        new = 0 if rows[0]["favorite"] else 1
        self._exec("UPDATE trainers SET favorite=?, updated_at=? WHERE id=?", (new, _now(), tid))
        return bool(new)

    def mark_launched(self, tid: int) -> None:
        self._exec(
            "UPDATE trainers SET run_count=run_count+1, last_run_at=?, updated_at=? WHERE id=?",
            (_now(), _now(), tid),
        )

    def set_exe_path(self, tid: int, exe: str, work_dir: str = "") -> None:
        self._exec(
            "UPDATE trainers SET exe_path=?, work_dir=?, source=CASE WHEN source='builtin' THEN 'local' ELSE source END, updated_at=? WHERE id=?",
            (exe, work_dir, _now(), tid),
        )

    # ------------------------------------------------------------ 查询
    # side: all / favorite / installed / uninstalled / category:<name> / tag:<name>
    def search(
        self,
        keyword: str = "",
        side: str = "all",
        sort: str = "name",
        limit: int = 2000,
    ) -> list[Trainer]:
        sql = ["SELECT t.* FROM trainers t WHERE 1=1"]
        params: list = []

        for tok in keyword.split():
            tok = tok.strip()
            if not tok:
                continue
            like = f"%{tok.lower()}%"
            sql.append(
                "AND (lower(t.game_title) LIKE ? OR lower(t.title) LIKE ? "
                "OR lower(t.tags) LIKE ? OR lower(t.category) LIKE ? OR lower(t.author) LIKE ?)"
            )
            params.extend([like] * 5)

        if side == "favorite":
            sql.append("AND t.favorite=1")
        elif side == "installed":
            sql.append("AND t.exe_path<>''")
        elif side == "uninstalled":
            sql.append("AND t.exe_path=''")
        elif side.startswith("category:"):
            sql.append("AND t.category=?")
            params.append(side.split(":", 1)[1])
        elif side.startswith("tag:"):
            sql.append("AND lower(t.tags) LIKE ?")
            params.append(f'%{side.split(":", 1)[1].lower()}%')

        order = {
            "name": "lower(t.game_title) ASC",
            "recent": "t.last_run_at DESC, lower(t.game_title) ASC",
            "hot": "t.run_count DESC, lower(t.game_title) ASC",
            "new": "t.created_at DESC",
        }.get(sort, "lower(t.game_title) ASC")
        sql.append(f"ORDER BY {order} LIMIT ?")
        params.append(limit)

        return [Trainer.from_row(r) for r in self._query(" ".join(sql), params)]

    def all_tags(self) -> list[tuple[str, int]]:
        rows = self._query("SELECT tags FROM trainers WHERE tags<>'' AND tags<>'[]'")
        counter: dict[str, int] = {}
        for r in rows:
            try:
                import json

                for tag in json.loads(r["tags"]):
                    k = str(tag).strip()
                    if k:
                        counter[k] = counter.get(k, 0) + 1
            except Exception:
                continue
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))

    def categories_with_count(self) -> list[tuple[str, int]]:
        rows = self._query("SELECT category, COUNT(*) c FROM trainers GROUP BY category")
        return sorted(((r["category"], r["c"]) for r in rows), key=lambda kv: -kv[1])

    def stats(self) -> dict:
        total = self._query("SELECT COUNT(*) c FROM trainers")[0]["c"]
        installed = self._query("SELECT COUNT(*) c FROM trainers WHERE exe_path<>''")[0]["c"]
        fav = self._query("SELECT COUNT(*) c FROM trainers WHERE favorite=1")[0]["c"]
        runs = self._query("SELECT COUNT(*) c FROM launch_records")[0]["c"]
        total_run = self._query("SELECT COALESCE(SUM(run_count),0) s FROM trainers")[0]["s"]
        return {
            "total": total,
            "installed": installed,
            "favorite": fav,
            "records": runs,
            "runs": total_run,
        }

    # ------------------------------------------------------------ 记录
    def add_record(self, rec: LaunchRecord) -> int:
        row = rec.to_row()
        cols = ", ".join(row.keys())
        marks = ", ".join("?" for _ in row)
        cur = self._exec(f"INSERT INTO launch_records({cols}) VALUES({marks})", row.values())
        return int(cur.lastrowid)

    def finish_record(
        self, rid: int, status: str, exit_code: int | None, ended_at: str, duration: int, message: str = ""
    ) -> None:
        self._exec(
            "UPDATE launch_records SET status=?, exit_code=?, ended_at=?, duration_sec=?, message=? WHERE id=?",
            (status, exit_code, ended_at, duration, message, rid),
        )

    def list_records(self, trainer_id: int | None = None, limit: int = 500) -> list[LaunchRecord]:
        sql = (
            "SELECT r.*, COALESCE(t.title, r.trainer_id, '') AS trainer_title "
            "FROM launch_records r LEFT JOIN trainers t ON t.id=r.trainer_id "
        )
        params: list = []
        if trainer_id:
            sql += "WHERE r.trainer_id=? "
            params.append(trainer_id)
        sql += "ORDER BY r.id DESC LIMIT ?"
        params.append(limit)
        return [LaunchRecord.from_row(r) for r in self._query(sql, params)]

    def list_records_range(self, since_date: str, limit: int = 5000) -> list[LaunchRecord]:
        sql = (
            "SELECT r.*, COALESCE(t.title,'') AS trainer_title "
            "FROM launch_records r LEFT JOIN trainers t ON t.id=r.trainer_id "
            "WHERE r.started_at>=? ORDER BY r.id DESC LIMIT ?"
        )
        return [LaunchRecord.from_row(r) for r in self._query(sql, (since_date, limit))]

    def delete_records(self, ids: list[int]) -> None:
        if not ids:
            return
        marks = ",".join("?" for _ in ids)
        self._exec(f"DELETE FROM launch_records WHERE id IN ({marks})", ids)

    def clear_records(self, before_days: int | None = None) -> int:
        if before_days is None:
            cur = self._exec("DELETE FROM launch_records")
            return cur.rowcount or 0
        cutoff = (datetime.now() - __import__("datetime").timedelta(days=before_days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        cur = self._exec("DELETE FROM launch_records WHERE started_at<>'' AND started_at<?", (cutoff,))
        return cur.rowcount or 0

    # ------------------------------------------------------------ 种子
    def count_by_source(self, source: str) -> int:
        return int(self._query("SELECT COUNT(*) c FROM trainers WHERE source=?", (source,))[0]["c"])

    def upsert_seed_item(self, item: dict) -> bool:
        """按 game_title + author 去重插入种子条目，返回是否新增。"""
        rows = self._query(
            "SELECT id, exe_path FROM trainers WHERE lower(game_title)=lower(?) AND lower(author)=lower(?)",
            (item["game_title"], item.get("author", "FLiNG")),
        )
        if rows:
            if rows[0]["exe_path"]:
                return False  # 用户已安装本体，保留
            self._exec(
                "UPDATE trainers SET title=?, category=?, tags=?, source_url=?, options=?, "
                "online_risk=?, cover_color=?, version=?, updated_at=? WHERE id=?",
                (
                    item["title"],
                    item.get("category", "其他"),
                    item.get("tags_json", "[]"),
                    item.get("source_url", ""),
                    item.get("options_json", "[]"),
                    int(item.get("online_risk", False)),
                    item.get("cover_color", "#3B6EA5"),
                    item.get("version", ""),
                    _now(),
                    rows[0]["id"],
                ),
            )
            return False
        self._exec(
            "INSERT INTO trainers(title,game_title,category,tags,author,source,source_url,"
            "options,online_risk,cover_color,version,favorite,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,0,?,?)",
            (
                item["title"],
                item["game_title"],
                item.get("category", "其他"),
                item.get("tags_json", "[]"),
                item.get("author", "FLiNG"),
                config.SOURCE_BUILTIN,
                item.get("source_url", ""),
                item.get("options_json", "[]"),
                int(item.get("online_risk", False)),
                item.get("cover_color", "#3B6EA5"),
                item.get("version", ""),
                _now(),
                _now(),
            ),
        )
        return True
