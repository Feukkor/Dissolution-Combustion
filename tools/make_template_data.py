"""Rebuild the TemplateData sample package from the recorded sample runs.

Sources live in ``samples/`` and use the current parameter names. Each sample is
opened, calculated and saved through the GUI, so the exported CSV/PNG pair comes
from the same code path a student uses.

Usage: python tools/make_template_data.py [source_dir] [target_dir]
"""
import csv
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gui

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples"
TARGET = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build" / "TemplateData"
RENAME = {"temperature(K)": "room_temperature(K)"}
WARNINGS = []


def convert(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open(encoding="utf-8-sig", newline="") as reader, \
            target.open("w", encoding="utf-8", newline="") as writer:
        rows = csv.reader(reader)
        out = csv.writer(writer)
        for row in rows:
            out.writerow([RENAME.get(cell, cell) for cell in row])


def run():
    with patch.object(gui.ttk.Window, "mainloop", lambda window: window.withdraw()), \
            patch.object(gui, "showinfo", lambda **kw: None), \
            patch.object(gui, "showwarning", lambda **kw: WARNINGS.append(kw["message"])), \
            patch.object(gui, "askyesno", return_value=True):
        gui.DATA_CONFIG["calorimeter_constant"] = None
        app = gui.App(py_path=str(TARGET), dpi=600)
        root = gui.DATA_CONFIG["window"]
        try:
            # 燃烧热先标定量热计常数，后续样品沿用，与人工操作顺序一致
            for mode, files in (("燃烧热", ["0_benzoic"]), ("燃烧热", ["1_sucrose", "2_milk", "3_oil"]),
                                ("溶解热", [f"dissolution_{i}" for i in range(1, 7)])):
                for name in files:
                    raw = TARGET / ("combustion" if mode == "燃烧热" else "dissolution") / f"{name}.csv"
                    if not raw.exists():
                        raise SystemExit(f"missing sample: {raw}")
                    gui.DATA_CONFIG["mode"].set(mode)
                    app.change_mode()
                    screen = gui.DATA_CONFIG["screen"]
                    if mode == "燃烧热":
                        gui.DATA_CONFIG["combustion_mode"].set("constant" if name == "0_benzoic" else "combustible")
                        screen.set_entry_state()
                    with patch.object(gui.filedialog, "askopenfilename", return_value=str(raw)):
                        screen.open_file()
                    if WARNINGS:
                        raise SystemExit(f"load failed for {name}: {WARNINGS}")
                    screen.spinEntries.calc()
                    screen.save_file()
                    if WARNINGS:
                        raise SystemExit(f"calc failed for {name}: {WARNINGS}")
                    root.update()
                    print(f"saved {mode} {name}")
            gui.DATA_CONFIG["mode"].set("溶解热拟合")
            app.change_mode()
            screen = gui.DATA_CONFIG["screen"]
            with patch.object(gui.filedialog, "askopenfilename",
                              return_value=str(TARGET / "dissolution" / "dissolution.csv")):
                screen.open_file()
            if WARNINGS:
                raise SystemExit(f"fit failed: {WARNINGS}")
            screen.save_file()
            print("saved 溶解热拟合 dissolution.csv")
        finally:
            gui.DATA_CONFIG["screen"].destroy()
            root.destroy()


if __name__ == "__main__":
    if TARGET.exists():
        shutil.rmtree(TARGET)
    for group in ("dissolution", "combustion"):
        for source in sorted((SOURCE / group).glob("*.csv")):
            if source.stem in ("dissolution", "combustion", "dissolution_fitted_data"):
                continue
            convert(source, TARGET / group / source.name)
    run()
    print("TARGET:", TARGET)
