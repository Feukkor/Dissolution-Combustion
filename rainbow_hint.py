"""Animated canvas overlay, retaining the original ttk button and its command."""
import colorsys
import tkinter as tk


class RainbowHint:
    def __init__(self):
        self.button = None
        self.canvas = None
        self.timer = None
        self.phase = 0

    def show(self, button):
        if self.button is button:
            return
        self.clear()
        self.button = button
        self.canvas = tk.Canvas(button, highlightthickness=0, borderwidth=0, takefocus=0)
        self.canvas.place(x=2, y=2, relwidth=1, relheight=1, width=-4, height=-4)
        self.canvas.bind("<ButtonRelease-1>", self._click)
        self._animate()

    def _click(self, event):
        if self.button is not None and not self.button.instate(["disabled"]):
            self.button.focus_set()
            self.button.invoke()

    def _animate(self):
        self.timer = None
        if self.canvas is None:
            return
        if self.button.instate(["disabled"]):
            self.clear()
            return
        width, height = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        self.canvas.delete("all")
        for i in range(48):
            rgb = colorsys.hsv_to_rgb((i / 48 + self.phase) % 1, 0.45, 1)
            color = "#%02x%02x%02x" % tuple(int(v * 255) for v in rgb)
            self.canvas.create_rectangle(i * width / 48, 0, (i + 1) * width / 48 + 1,
                                         height, fill=color, outline=color)
        self.canvas.create_text(width / 2, height / 2, text=self.button.cget("text"),
                                fill="#152030", font="TkDefaultFont")
        self.phase = (self.phase + 0.015) % 1
        self.timer = self.canvas.after(80, self._animate)

    def clear(self):
        if self.canvas is not None:
            if self.timer is not None:
                self.canvas.after_cancel(self.timer)
            self.canvas.destroy()
        self.timer = None
        self.canvas = None
        self.button = None
