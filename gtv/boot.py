"""无控制台启动引导层（供 pythonw.exe 使用）。

pythonw.exe 没有 stdout / stderr，程序一旦出错就"静默消失"。
本模块把标准输出/错误重定向到日志文件，并在异常时弹出系统提示框 + 写日志。

用法：pythonw.exe -m gtv.boot
"""
from __future__ import annotations

import io
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gtv.core import config  # noqa: E402


class _LogWriter(io.TextIOBase):
    """把 print / traceback 输出写进日志文件（pythonw 下没有控制台）。"""

    def __init__(self, fh):
        self.fh = fh

    def write(self, s: str) -> int:
        try:
            self.fh.write(s)
            self.fh.flush()
        except Exception:  # noqa: BLE001
            pass
        return len(s)

    def flush(self) -> None:
        try:
            self.fh.flush()
        except Exception:  # noqa: BLE001
            pass


def _alert(msg: str) -> None:
    """无控制台时也要让用户看到错误：弹一个原生 MessageBox。"""
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, msg, "GTV", 0x10)  # MB_ICONERROR
            return
        except Exception:  # noqa: BLE001
            pass
    print(msg)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    config.ensure_app_dirs()
    log_file = config.LOG_DIR / "gtv.log"

    fh = open(log_file, "a", encoding="utf-8", errors="replace")
    fh.write(f"\n==== GTV start {datetime.now():%Y-%m-%d %H:%M:%S} pid={os.getpid()} ====\n")
    sys.stdout = _LogWriter(fh)
    sys.stderr = sys.stdout

    try:
        from gtv.main import main as app_main

        rc = app_main(argv)
        fh.write(f"==== GTV exit rc={rc} ====\n")
        return int(rc or 0)
    except BaseException as exc:  # noqa: BLE001
        fh.write(traceback.format_exc() + "\n")
        fh.flush()
        _alert(f"GTV 启动失败：{exc}\n\n详细堆栈见：{log_file}")
        return 1
    finally:
        try:
            fh.close()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    sys.exit(main())
