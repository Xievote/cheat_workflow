"""启动器：进程管理（启动 / 监控 / 停止）+ 启动记录写入。

两种模式：
* 普通启动 —— subprocess.Popen，可拿到 PID 并精确监控退出码。
* 管理员启动 —— Windows ShellExecute("runas")，可提权但拿不到 PID，
  停止时降级为按进程名匹配（taskkill /IM）。
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from . import config
from .models import LaunchRecord, Session, Trainer, _now

IS_WIN = sys.platform.startswith("win")

if IS_WIN:  # pragma: no cover - Windows only
    import ctypes

    def shell_execute(file: str, params: str, work_dir: str, verb: str = "open") -> bool:
        rc = ctypes.windll.shell32.ShellExecuteW(None, verb, file, params, work_dir, 1)
        return int(rc) > 32
else:  # pragma: no cover - POSIX
    def shell_execute(file: str, params: str, work_dir: str, verb: str = "open") -> bool:
        return False


class Launcher(QObject):
    sessionStarted = Signal(int, int)     # trainer_id, pid
    sessionEnded = Signal(int, int)       # trainer_id, exit_code
    message = Signal(int, str)            # trainer_id, 文本

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._sessions: dict[int, Session] = {}
        self._records: dict[int, int] = {}   # trainer_id -> record_id
        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    # ------------------------------------------------------------ 启动
    def start(self, t: Trainer) -> tuple[bool, str]:
        exe = t.exe_path
        if not exe or not Path(exe).exists():
            return False, "尚未安装修改器本体（请先导入本地文件或下载链接）"
        work_dir = t.work_dir or str(Path(exe).parent)
        args = shlex.split(t.args or "") if not IS_WIN else (t.args or "")

        proc = None
        pid = 0
        try:
            if t.run_as_admin and IS_WIN:
                ok = shell_execute(exe, t.args or "", work_dir, "runas")
                if not ok:
                    self.message.emit(t.id or 0, "提权被拒绝或失败，已改为普通启动")
                    proc = subprocess.Popen(  # noqa: S603
                        [exe, *(args.split() if isinstance(args, str) else args)],
                        cwd=work_dir,
                        close_fds=True,
                    )
                    pid = proc.pid
                else:
                    pid = 0
            else:
                cmdline = [exe]
                if isinstance(args, str) and args.strip():
                    cmdline += args.split()
                elif isinstance(args, list):
                    cmdline += args
                if not IS_WIN:
                    proc = subprocess.Popen(cmdline, cwd=work_dir, close_fds=True)  # noqa: S603
                    pid = proc.pid
                else:
                    proc = subprocess.Popen(  # noqa: S603
                        cmdline,
                        cwd=work_dir,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                        close_fds=True,
                    )
                    pid = proc.pid
        except Exception as exc:  # noqa: BLE001
            return False, f"启动失败：{exc}"

        if pid:
            self._sessions[t.id or 0] = Session(t.id or 0, pid, time.time(), proc)
        else:
            # 提权进程无法跟踪，记录 pid=0 的“一次性”会话（不进入轮询）
            pass

        rec = LaunchRecord(
            trainer_id=t.id,
            pid=pid,
            started_at=_now(),
            status="running",
            trainer_title=t.display_name,
            message="管理员权限启动（无法跟踪进程）" if not pid else "",
        )
        rid = self.db.add_record(rec)
        self._records[t.id or 0] = rid
        self.db.mark_launched(t.id or 0)

        if not pid:
            # 立即补一条完成记录，避免出现永久 running
            self.db.finish_record(rid, "finished", None, _now(), 0, "以管理员权限启动，进程状态不可跟踪")

        self.sessionStarted.emit(t.id or 0, pid)
        return True, f"已启动（PID {pid}）" if pid else "已启动（管理员权限）"

    # ------------------------------------------------------------ 停止
    def stop(self, tid: int) -> tuple[bool, str]:
        sess = self._sessions.get(tid)
        if sess is None:
            return False, "该修改器未在运行"
        try:
            if sess.proc is not None:
                sess.proc.terminate()
                try:
                    sess.proc.wait(timeout=3)
                except Exception:  # noqa: BLE001
                    sess.proc.kill()
            elif IS_WIN:
                subprocess.run(  # noqa: S603
                    ["taskkill", "/PID", str(sess.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
        except Exception as exc:  # noqa: BLE001
            return False, f"停止失败：{exc}"
        return True, "已请求停止"

    def stop_by_pid(self, pid: int) -> bool:
        if not pid:
            return False
        if IS_WIN:
            res = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],  # noqa: S603
                                 capture_output=True, check=False)
            return res.returncode == 0
        try:
            os.kill(pid, 9)
            return True
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------ 查询
    def is_running(self, tid: int) -> bool:
        return tid in self._sessions

    def session(self, tid: int) -> Session | None:
        return self._sessions.get(tid)

    def elapsed(self, tid: int) -> int:
        s = self._sessions.get(tid)
        return s.elapsed_sec() if s else 0

    def running_ids(self) -> list[int]:
        return list(self._sessions.keys())

    def running_count(self) -> int:
        return len(self._sessions)

    # ------------------------------------------------------------ 轮询
    def _poll(self) -> None:
        if not self._sessions:
            return
        dead: list[tuple[int, int]] = []
        for tid, sess in list(self._sessions.items()):
            rc = None
            if sess.proc is not None:
                rc = sess.proc.poll()
            elif not self._pid_alive(sess.pid):
                rc = -1
            if rc is None:
                continue
            dur = sess.elapsed_sec()
            status = "finished" if rc == 0 else ("killed" if rc < 0 else "failed")
            rid = self._records.pop(tid, None)
            if rid:
                self.db.finish_record(rid, status, rc, _now(), dur, f"退出码 {rc}")
            dead.append((tid, rc))
            self._sessions.pop(tid, None)
        for tid, rc in dead:
            self.sessionEnded.emit(tid, rc)

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if not pid:
            return False
        if IS_WIN:
            res = subprocess.run(  # noqa: S603
                ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, check=False
            )
            return str(pid) in (res.stdout or "")
        try:
            os.kill(pid, 0)
            return True
        except Exception:  # noqa: BLE001
            return False
