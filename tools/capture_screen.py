"""Capture a screenshot of a real application screen for the manual.

Renders the requested screen in a real Tk window, optionally after feeding the
guidance panel some readings, then saves a PNG of the window client area.
"""
import ctypes
from ctypes import wintypes
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gui

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def capture(hwnd, path):
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bitmap = gdi32.CreateCompatibleBitmap(hdc, width, height)
    gdi32.SelectObject(memdc, bitmap)
    # PW_CLIENTONLY | PW_RENDERFULLCONTENT
    ok = user32.PrintWindow(hwnd, memdc, 0x00000001 | 0x00000002)
    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = width
    info.bmiHeader.biHeight = -height
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = 0
    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memdc, bitmap, 0, height, buffer, ctypes.byref(info), 0)
    from PIL import Image
    image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)
    image.convert("RGB").save(path)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)
    return bool(ok), width, height


def main():
    out = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "数据记录"
    real_mainloop = gui.ttk.Window.mainloop

    def drive(root):
        gui.DATA_CONFIG["mode"].set(mode)
        gui.DATA_CONFIG["app"].change_mode()
        root.geometry("1280x960+0+0")
        root.update()
        screen = gui.DATA_CONFIG["screen"]
        if mode == "数据记录":
            screen.measure_mode.set("dissolution")
            screen.change_measure_mode()
            # Enable the next-step button so the rainbow hint is part of the figure.
            screen.button_data_start.config(state="normal")
            # Feed a stable baseline so the guidance panel shows real status text
            # and the rainbow hint appears on the next-step button.
            for i in range(400):
                screen.update_guidance(1.235, i * 0.55)
            root.update()
        hwnd = int(root.winfo_id())
        parent = user32.GetParent(hwnd) or hwnd
        # Let timers and the rainbow animation paint before grabbing the client area.
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)
        ok, w, h = capture(parent, out)
        print(f"saved {out} ({w}x{h}) client-only={ok}")
        gui.DATA_CONFIG["screen"].destroy()
        root.destroy()

    with patch.object(gui.ttk.Window, "mainloop", drive):
        gui.App(py_path=str(Path(__file__).resolve().parents[1]), dpi=80)


if __name__ == "__main__":
    main()
