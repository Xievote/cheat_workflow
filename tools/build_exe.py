"""PyInstaller 打包脚本：python tools/build_exe.py

产出 dist/GTV.exe（单目录模式，-D 便于附带 data/ 目录）。
如需单文件模式，把 --onedir 换成 --onefile。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "GTV"


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", APP_NAME,
        "--add-data", f"{ROOT / 'data'};data",
        "--paths", str(ROOT),
        "--collect-all", "PySide6",
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.Qt3DCore",
        str(ROOT / "gtv" / "main.py"),
    ]
    print(">>>", " ".join(cmd))
    res = subprocess.run(cmd, cwd=str(ROOT), check=False)
    if res.returncode == 0:
        print(f"\n打包完成：{ROOT / 'dist' / APP_NAME / (APP_NAME + '.exe')}")
    return res.returncode


if __name__ == "__main__":
    sys.exit(main())
