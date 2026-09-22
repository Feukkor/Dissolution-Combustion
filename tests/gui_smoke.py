"""Run explicitly in the project venv: python tests/gui_smoke.py.

Creates real Tk widgets and plots using synthetic data, without a serial device.
"""
import csv
import math
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gui
from data_loading import RAW_FIELDS, FIT_FIELDS


def run():
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        warnings = []
        callbacks = []
        with patch.object(gui.ttk.Window, "mainloop", lambda window: window.withdraw()), \
                patch.object(gui, "showinfo"), \
                patch.object(gui, "showwarning", lambda **kw: warnings.append(kw)), \
                patch.object(gui, "askyesno", return_value=True):
            gui.DATA_CONFIG["calorimeter_constant"] = "999.9"
            app = gui.App(py_path=directory, dpi=80)
            assert gui.DATA_CONFIG["calorimeter_constant"] is None
            root = gui.DATA_CONFIG["window"]
            root.report_callback_exception = lambda *error: callbacks.append(error)
            try:
                root.update()
                screen = gui.DATA_CONFIG["screen"]
                screen.button_data_start.configure(state="normal")
                for _ in range(50):
                    screen.update_guidance(1.0)
                assert screen.rainbow.canvas is not None
                phase = screen.rainbow.phase
                until = time.monotonic() + 0.3
                while time.monotonic() < until:
                    root.update()
                    time.sleep(0.02)
                assert screen.rainbow.phase != phase
                screen.temp_file = (folder / "tempfile.tmp").open("w", encoding="utf-8")
                screen.data_start()
                for value in [1.0] * 30 + [0.2] * 85:
                    screen.update_guidance(value)
                assert screen.rainbow.button is screen.button_heat_start
                screen.heat_start()
                for _ in range(5):
                    screen.update_guidance(0.7)
                assert screen.rainbow.button is screen.button_heat_stop
                screen.heat_end()
                for _ in range(80):
                    screen.update_guidance(0.9)
                assert screen.rainbow.button is screen.button_data_stop
                screen.data_end()
                print("PASS real Tk recording controls and animated gradient")

                for mode in ("燃烧热", "溶解热"):
                    raw = folder / ("combustion_run.csv" if mode == "燃烧热" else "dissolution_run.csv")
                    values = {"room_temperature(K)": 298.15, "water_volume(mL)": 500,
                              "cotton_mass(g)": 0.01, "combustible_mass(g)": 1,
                              "Nickel_before_mass(g)": 0.008, "Nickel_after_mass(g)": 0.003,
                              "solute_mass(g)": 1, "solute_molarmass(g/mol)": 74.5,
                              "R1(Omega)": 10, "R2(Omega)": 10, "t1(s)": 230,
                              "t2(s)": 330, "current(A)": 1}
                    with raw.open("w", newline="", encoding="utf-8") as output:
                        writer = csv.writer(output)
                        writer.writerows((key, values[key]) for key in RAW_FIELDS[mode])
                        writer.writerow(["time(s)", "Delta_T(K)"])
                        for t in range(480):
                            step1 = 1 / (1 + math.exp(-(t - 120) / 8))
                            step2 = 1 / (1 + math.exp(-(t - 290) / 8))
                            temperature = 0.00002 * t + (step1 if mode == "燃烧热" else -step1 + step2)
                            writer.writerow([t, temperature])
                    original = raw.read_bytes()
                    gui.DATA_CONFIG["mode"].set(mode)
                    app.change_mode()
                    screen = gui.DATA_CONFIG["screen"]
                    with patch.object(gui.filedialog, "askopenfilename", return_value=str(raw)):
                        screen.open_file()
                    assert not warnings, warnings
                    screen.spinEntries.calc()
                    screen.save_file()
                    assert raw.read_bytes() == original
                    assert raw.with_suffix(".png").exists()
                    result = folder / ("combustion.csv" if mode == "燃烧热" else "dissolution.csv")
                    assert result.exists()
                    root.update()
                    print("PASS raw data import, calculation, PNG and CSV export:", mode)
                    if mode == "燃烧热":
                        constant = screen.strEntries.dump()["constant(J/K)"]
                        assert constant == gui.DATA_CONFIG["calorimeter_constant"]
                        screen.change_entry()
                        screen.remake_file()
                        assert screen.strEntries.dump()["constant(J/K)"] == constant
                        with patch.object(gui.filedialog, "askopenfilename", return_value=str(raw)):
                            screen.open_file()
                        assert screen.strEntries.dump()["constant(J/K)"] == constant
                        gui.DATA_CONFIG["combustion_mode"].set("combustible")
                        screen.set_entry_state()
                        entry = screen.strEntries.entries_table["constant(J/K)"].entry
                        assert not entry.instate(["readonly"]) and not entry.instate(["disabled"])
                        screen.spinEntries.calc()
                        assert screen.parameters["constant(J/K)"] == constant
                        # A manual sample-specific override must not change the calibration default.
                        screen.strEntries.set_value("constant(J/K)", str(float(constant) + 100))
                        screen.spinEntries.calc()
                        assert gui.DATA_CONFIG["calorimeter_constant"] == constant
                        gui.DATA_CONFIG["combustion_mode"].set("constant")
                        screen.set_entry_state()
                        assert screen.strEntries.dump()["constant(J/K)"] == constant
                        screen.strEntries.set_value("combustible_mass(g)", "1.1")
                        screen.spinEntries.calc()
                        session_constant = screen.strEntries.dump()["constant(J/K)"]
                        assert session_constant != constant
                        assert gui.DATA_CONFIG["calorimeter_constant"] == session_constant
                        print("PASS calibration default survives reload/reset; samples use it; recalibration updates it")

                fitted = folder / "fit_input.csv"
                with fitted.open("w", newline="", encoding="utf-8") as output:
                    writer = csv.writer(output)
                    writer.writerow(FIT_FIELDS)
                    last_heat = 0
                    for i in range(1, 7):
                        n = (500 / 18.015) / (i / 74.5)
                        qs = 20 * 0.005 * n / (1 + 0.005 * n)
                        total_heat = qs * i / 74.5
                        writer.writerow([500, 1, 1, 74.5, total_heat - last_heat])
                        last_heat = total_heat
                gui.DATA_CONFIG["mode"].set("溶解热拟合")
                app.change_mode()
                screen = gui.DATA_CONFIG["screen"]
                with patch.object(gui.filedialog, "askopenfilename", return_value=str(fitted)):
                    screen.open_file()
                assert not warnings, warnings
                screen.save_file()
                assert (folder / "fit_input_fitted_data.csv").exists()
                assert fitted.with_suffix(".png").exists()
                print("PASS fitted heat calculations and exports")

                gui.DATA_CONFIG["mode"].set("燃烧热")
                app.change_mode()
                screen = gui.DATA_CONFIG["screen"]
                assert screen.strEntries.dump()["constant(J/K)"] == session_constant
                with patch.object(gui.filedialog, "askopenfilename", return_value=str(folder / "combustion_run.csv")):
                    screen.open_file()
                assert screen.strEntries.dump()["constant(J/K)"] == session_constant
                print("PASS calibration default survives switching through other modules")

                broken = folder / "broken.csv"
                broken.write_bytes(b"%PDF-1.7")
                with patch.object(gui.filedialog, "askopenfilename", return_value=str(broken)):
                    screen.open_file()
                assert len(warnings) == 1 and "文件格式错误" in warnings[0]["message"]
                root.update()
                assert not callbacks, callbacks
                print("PASS invalid-file warning; no Tk callback errors")
            finally:
                gui.DATA_CONFIG["screen"].destroy()
                root.destroy()


if __name__ == "__main__":
    run()
