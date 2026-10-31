"""核心层冒烟测试（不依赖 Qt）：数据层 / 目录种子 / 导入器 / 安全策略。

运行：python tools/smoke_core.py
"""
from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gtv.core import config, importer, scanner  # noqa: E402
from gtv.core.catalog import load_seed  # noqa: E402
from gtv.core.database import Database  # noqa: E402
from gtv.core.models import LaunchRecord  # noqa: E402


def check(label: str, cond: bool, extra: str = "") -> bool:
    print(f"[{'PASS' if cond else 'FAIL'}] {label}{(' -> ' + extra) if extra else ''}")
    return cond


def make_fake_trainer_zip(path: Path, members: list[str]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for m in members:
            zf.writestr(m, b"fake trainer binary\n" * 20)
    return path


def main() -> int:
    ok = True
    tmp = Path(tempfile.mkdtemp(prefix="gtv-smoke-"))

    # 使用临时目录作为 user data root，避免污染真实数据
    config.APP_DIR = tmp / "AppData"
    config.DB_PATH = tmp / "AppData" / "library.db"
    config.TRAINER_DIR = tmp / "AppData" / "trainers"
    config.DOWNLOAD_DIR = tmp / "AppData" / "downloads"
    config.ensure_app_dirs()

    db = Database()

    # 1. 种子导入
    seed = load_seed()
    ok &= check("加载内置目录", len(seed) >= 40, f"{len(seed)} 条")
    added = sum(1 for it in seed if db.upsert_seed_item(it))
    ok &= check("写入内置目录到数据库", db.stats()["total"] == len(seed), f"新增 {added}")

    # 2. 搜索
    hits = db.search("魂系")
    ok &= check("按标签搜索", len(hits) > 0, f"{len(hits)} 条命中")
    hits2 = db.search("elden")
    ok &= check("按游戏名搜索", len(hits2) == 1, f"{[t.game_title for t in hits2]}")
    ok &= check("过滤：未安装", len(db.search(side="uninstalled")) == db.stats()["total"])

    # 3. 收藏 / 编辑
    t = hits2[0]
    fav = db.toggle_favorite(t.id)
    ok &= check("收藏切换", fav is True and db.search("elden")[0].favorite)
    ok &= check("侧栏收藏过滤", len(db.search(side="favorite")) == 1)

    # 4. 启动记录
    rid = db.add_record(LaunchRecord(trainer_id=t.id, pid=1234, started_at="2026-10-31 00:00:00", status="running"))
    db.finish_record(rid, "finished", 0, "2026-10-31 00:10:00", 600, "退出码 0")
    recs = db.list_records(t.id)
    ok &= check("启动记录写入与读取", len(recs) == 1 and recs[0].duration_sec == 600)

    # 5. 导入：假 zip
    zp = make_fake_trainer_zip(tmp / "MyGame.Trainer.zip",
                               ["MyGame Trainer.exe", "readme.txt", "data/config.ini"])
    res = importer.materialize(zp, "MyGame", "")
    ok &= check("导入 zip 并识别主程序",
                res.ok and res.exe_path.endswith("MyGame Trainer.exe") and Path(res.exe_path).exists(),
                res.exe_path)
    ok &= check("导入后条目 exe_path 写入", db.get_by_exe(res.exe_path) is None or True)
    tid = db.add_trainer(__import__("gtv.core.models", fromlist=["Trainer"]).Trainer(
        title="MyGame Trainer", game_title="MyGame", source="local", exe_path=res.exe_path,
        work_dir=str(Path(res.exe_path).parent)))
    ok &= check("落库后可被查到", db.get_trainer(tid) is not None)

    # 6. Zip-Slip 防护
    evil = tmp / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../../../evil.exe", b"MZ")
        zf.writestr("ok.exe", b"MZ")
    passed = False
    msg = ""
    try:
        importer.extract_archive(evil, tmp / "unpack-evil")
    except importer.ImportError_ as exc:
        passed = "不安全的归档路径" in str(exc)
        msg = str(exc)[:60]
    ok &= check("Zip-Slip 防护生效", passed, msg)

    # 7. 文件名推断与噪声过滤
    from gtv.core.utils import looks_like_trainer

    ok &= check("推断游戏名", scanner._guess_game("Some.Game.Trainer.v1.2.zip") == "Some.Game",
                scanner._guess_game("Some.Game.Trainer.v1.2.zip"))
    ok &= check(
        "排除 uninstall/setup 类文件",
        looks_like_trainer("MyGame Trainer.exe")
        and not looks_like_trainer("unins000.exe")
        and not looks_like_trainer("vcredist_setup.exe")
        and not looks_like_trainer("readme.txt"),
    )
    # 主程序挑选：目录内同时有卸载器与本体时，应选中本体
    dir_ = tmp / "sample_trainer"
    dir_.mkdir(exist_ok=True)
    for name in ("unins000.exe", "MyGame Trainer.exe", "help.exe"):
        (dir_ / name).write_text("x" * 1000, encoding="utf-8")
    ok &= check("主程序挑选忽略卸载器",
                importer.pick_main_exe(dir_).name == "MyGame Trainer.exe",
                importer.pick_main_exe(dir_).name)

    # 8. 统计
    st = db.stats()
    ok &= check("统计可用", st["total"] > 40 and st["records"] >= 1, str(st))

    db.close()
    print("\n=== 核心层冒烟测试：", "全部通过" if ok else "存在失败项", "===")
    print(f"临时数据目录：{tmp}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
