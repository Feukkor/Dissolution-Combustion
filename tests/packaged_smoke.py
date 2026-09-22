"""Launch an exact built EXE with no Python on PATH; close its own window."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_version import WINDOW_TITLE


def run(executable):
    executable = Path(executable).resolve()
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    owned_windows = []

    @callback_type
    def inspect(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)
        if handle:
            try:
                name = ctypes.create_unicode_buffer(32768)
                size = wintypes.DWORD(len(name))
                if kernel32.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
                    if os.path.normcase(name.value) == os.path.normcase(str(executable)):
                        title = ctypes.create_unicode_buffer(1024)
                        user32.GetWindowTextW(hwnd, title, len(title))
                        owned_windows.append((hwnd, title.value))
            finally:
                kernel32.CloseHandle(handle)
        return True

    environment = os.environ.copy()
    for key in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
        environment.pop(key, None)
    environment["PATH"] = os.path.join(os.environ["SystemRoot"], "System32")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with tempfile.TemporaryDirectory() as directory:
        process = subprocess.Popen([str(executable)], cwd=directory, env=environment,
                                   startupinfo=startup)
        try:
            deadline = time.monotonic() + 45
            found = None
            while time.monotonic() < deadline:
                owned_windows.clear()
                user32.EnumWindows(inspect, 0)
                found = next(((h, title) for h, title in owned_windows if title == WINDOW_TITLE), None)
                if found:
                    break
                if process.poll() is not None:
                    raise RuntimeError(f"EXE exited before window appeared: {process.returncode}")
                time.sleep(0.2)
            if not found:
                raise RuntimeError(f"No main window: {owned_windows}")
            time.sleep(2)
            assert process.poll() is None, "EXE closed unexpectedly"
            print("PASS standalone EXE main window:", found[1])
            user32.PostMessageW(found[0], 0x0010, 0, 0)
            assert process.wait(timeout=15) == 0
            print("PASS normal close; exit code 0; no Python environment required")
        finally:
            if process.poll() is None:
                for hwnd, _ in owned_windows:
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=5)


if __name__ == "__main__":
    run(sys.argv[1])
