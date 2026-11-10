"""Run explicitly in the project venv on an unlocked desktop: python tests/menu_switch_smoke.py.

Opens the mode menu with a real mouse click and picks entries with the keyboard,
the sequence that used to freeze the application: the menu command destroyed the
whole screen, and with it the still-posted menu, so the Tk event loop never resumed.
It drives the real mouse and keyboard, so do not touch them while it runs.
"""
import ctypes
from ctypes import wintypes
import faulthandler
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

# The Windows CI console cannot encode Chinese mode names, so always write UTF-8.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gui

user32 = ctypes.WinDLL("user32", use_last_error=True)
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
MOUSE_MOVE, MOUSE_DOWN, MOUSE_UP, MOUSE_ABSOLUTE = 0x1, 0x2, 0x4, 0x8000
KEY_UP = 0x2
VK_DOWN, VK_RETURN = 0x28, 0x0D


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def send(item):
    user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT))


def click(x, y):
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    dx, dy = int(x * 65535 / (width - 1)), int(y * 65535 / (height - 1))
    for flags in (MOUSE_MOVE, MOUSE_DOWN, MOUSE_UP):
        send(INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dx, dy, 0, flags | MOUSE_MOVE | MOUSE_ABSOLUTE, 0, None)))
        time.sleep(0.05)


def press(key):
    send(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(key, 0, 0, 0, None)))
    time.sleep(0.03)
    send(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(key, 0, KEY_UP, 0, None)))
    time.sleep(0.1)


def run():
    faulthandler.dump_traceback_later(90, exit=True)
    plan = ["溶解热", "燃烧热", "溶解热拟合", "数据记录", "燃烧热", "数据记录"]
    results, errors = [], []
    real_mainloop = gui.ttk.Window.mainloop

    def drive(root):
        root.geometry("1000x700+0+0")
        root.report_callback_exception = lambda *error: errors.append(error)
        beats = {"n": 0}

        def heartbeat():
            beats["n"] += 1
            root.after(100, heartbeat)

        def next_step(index=0):
            if index == len(plan):
                root.after(0, finish)
                return
            screen = gui.DATA_CONFIG["screen"]
            menu = screen.button_mode["menu"]
            labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]
            button = screen.button_mode
            root.lift()
            root.focus_force()
            root.update()
            target = (button.winfo_rootx() + button.winfo_width() // 2,
                      button.winfo_rooty() + button.winfo_height() // 2)
            threading.Thread(target=operate, args=(index, target, labels.index(plan[index]), beats["n"]),
                             daemon=True).start()

        def operate(index, target, position, beats_before):
            click(*target)
            time.sleep(0.5)
            for _ in range(position + 1):
                press(VK_DOWN)
            press(VK_RETURN)
            time.sleep(0.8)
            root.after(0, lambda: check(index, beats_before))

        def check(index, beats_before):
            results.append((plan[index], gui.DATA_CONFIG["mode"].get(),
                            type(gui.DATA_CONFIG["screen"]).__name__, beats["n"] > beats_before))
            root.after(100, lambda: next_step(index + 1))

        def finish():
            gui.DATA_CONFIG["screen"].destroy()
            root.destroy()

        root.after(100, heartbeat)
        root.after(600, next_step)
        real_mainloop(root)

    with patch.object(gui.ttk.Window, "mainloop", drive):
        gui.App(py_path=".", dpi=80)
    faulthandler.cancel_dump_traceback_later()
    screens = {"数据记录": "Screen1_Data", "溶解热": "Screen2_Dissolution",
               "燃烧热": "Screen3_Combustion", "溶解热拟合": "Screen4_Fit"}
    assert len(results) == len(plan), results
    for wanted, mode, screen, alive in results:
        assert mode == wanted and screen == screens[wanted], (wanted, mode, screen)
        assert alive, f"event loop stopped after choosing {wanted}"
        print(f"PASS mode menu -> {wanted} ({screen}); event loop still running")
    assert not errors, errors
    print("PASS no Tk callback errors")


if __name__ == "__main__":
    run()
