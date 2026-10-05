"""Record which processes actually get created during app startup.

    python tools/process_audit.py

The app is a PyInstaller onedir bundle, so it is worth knowing whether it
forks child processes (console shells, Qt helpers, sync subprocesses) before
the window appears. This snapshots the process table via the Win32 toolhelp
API, attributes every new PID to its parent, and stamps each one with the
millisecond offset from launch.

Runs the child with QT_QPA_PLATFORM=offscreen so no window is ever mapped --
a tiling WM cannot fight a window that does not exist.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ctypes  # noqa: E402
import ctypes.wintypes as wt  # noqa: E402

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


def snapshot() -> dict[int, tuple[str, int]]:
    """Return {pid: (exe_name, parent_pid)} for every live process."""
    kernel32 = ctypes.windll.kernel32
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        return {}
    out: dict[int, tuple[str, int]] = {}
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if kernel32.Process32First(snap, ctypes.byref(entry)):
            while True:
                out[int(entry.th32ProcessID)] = (
                    entry.szExeFile.decode("ascii", "replace"),
                    int(entry.th32ParentProcessID),
                )
                if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snap)
    return out


def main() -> int:
    exe = ROOT / "dist" / "QtPublicAPis" / "QtPublicAPIs.exe"
    if not exe.exists():
        print(f"missing {exe}\nbuild it first")
        return 1

    before = snapshot()
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"

    t0 = time.perf_counter()
    proc = subprocess.Popen(
        [str(exe), "--selftest", "proc_selftest.json"],
        cwd=str(ROOT),
        env=env,
    )

    seen: dict[int, tuple[float, str, int]] = {}
    while proc.poll() is None:
        now = snapshot()
        for pid, (name, ppid) in now.items():
            if pid not in before and pid not in seen:
                seen[pid] = ((time.perf_counter() - t0) * 1000.0, name, ppid)
        time.sleep(0.002)

    # One final sweep to catch anything that lived entirely inside the window.
    for pid, (name, ppid) in snapshot().items():
        if pid not in before and pid not in seen:
            seen[pid] = ((time.perf_counter() - t0) * 1000.0, name, ppid)

    rc = proc.wait()
    print(f"\nlaunched pid {proc.pid}, exit {rc}, {len(seen)} process(es) created\n")
    for pid, (ms, name, ppid) in sorted(seen.items(), key=lambda kv: kv[1][0]):
        parent = seen.get(ppid, ("?", "?", 0))[1] if ppid in seen else "pre-existing"
        tag = " <- app" if ppid == proc.pid or pid == proc.pid else f" <- {parent}"
        print(f"  +{ms:8.1f} ms  pid {pid:<7} {name:<28}{tag}")

    report = ROOT / "proc_selftest.json"
    if report.exists():
        report.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())