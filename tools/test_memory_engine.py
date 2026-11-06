"""内存引擎全链路测试（附加测试进程自身）。

说明：开发沙箱虚拟化了进程 API，跨进程读取无法在沙箱内验证；
因此本测试附加「测试进程自己」，覆盖引擎全部核心路径：
  1. 静态地址读取（int32 / float）
  2. 模块基址解析（python.exe+0 → PE 头 MZ）
  3. 指针偏移链解引用（两级指针）
  4. 写入与回读（int32 / float / 指针链目标）
真实跨进程验证请在沙箱外的实际游戏上运行平台完成。
运行：.venv/Scripts/python.exe tools/test_memory_engine.py
"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gtv.core.memory_engine import MemoryEngine  # noqa: E402
from gtv.core.models import MemoryEntry  # noqa: E402


def main() -> int:
    eng = MemoryEngine()
    ok, msg = eng.attach_pid(os.getpid())
    assert ok, msg
    print(f"[1] {msg}")

    # ---- 1. 静态地址读（int32 / float）
    hp = ctypes.c_int32(100)
    mp = ctypes.c_float(55.5)
    e_hp = MemoryEntry(id=1, trainer_id=1, name="血量", addr=hex(ctypes.addressof(hp)), dtype="int32")
    e_mp = MemoryEntry(id=2, trainer_id=1, name="魔法", addr=hex(ctypes.addressof(mp)), dtype="float")
    assert eng.read(e_hp) == 100, "read int32 失败"
    assert abs(eng.read(e_mp) - 55.5) < 0.001, "read float 失败"
    print("[2] 静态地址读取 int32/float  OK")

    # ---- 2. 模块基址解析："python.exe+0" 应读到 PE 头 MZ
    e_mz = MemoryEntry(id=3, trainer_id=1, name="PE头", addr="python.exe+0", dtype="int16")
    v = eng.read(e_mz)
    assert v == 0x5A4D, f"模块基址解析失败：{v}"
    print("[3] 模块基址解析 python.exe+0 → 'MZ'  OK")

    # ---- 3. 指针偏移链：hp_slot → (指向 mp_slot) → (指向 target)
    target = ctypes.c_int32(777)
    mp_slot = ctypes.c_void_p(ctypes.addressof(target))
    hp_slot = ctypes.c_void_p(ctypes.addressof(mp_slot))
    e_ptr = MemoryEntry(
        id=4, trainer_id=1, name="指针链",
        addr=hex(ctypes.addressof(hp_slot)), offsets=[0, 0], dtype="int32",
    )
    v = eng.read(e_ptr)
    assert v == 777, f"指针链读取失败：{v}"
    print("[4] 指针偏移链解引用（两级）读取  OK")

    # ---- 4. 写入（int32 / float）并直接用 ctypes 校验内存真的变了
    ok, _ = eng.write(e_hp, MemoryEngine.cast_value("int32", 999))
    assert ok and hp.value == 999, "写入 int32 失败"
    ok, _ = eng.write(e_mp, MemoryEngine.cast_value("float", 88.0))
    assert ok and abs(mp.value - 88.0) < 0.001, "写入 float 失败"
    print("[5] 写入 int32=999 / float=88.0 并回验  OK")

    # ---- 5. 通过指针链写入目标
    ok, _ = eng.write(e_ptr, MemoryEngine.cast_value("int32", 12345))
    assert ok and target.value == 12345, "指针链写入失败"
    print("[6] 指针链写入 target=12345  OK")

    # ---- 6. detach
    eng.detach("测试结束")
    assert not eng.is_attached
    print("[7] detach  OK")

    print("\nALL TESTS PASSED（跨进程读写请在实际游戏上验证）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
