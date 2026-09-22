"""Exercise actual GUI method bodies without installing GUI/scientific dependencies.

Run: python -m unittest discover -s tests -v
"""
import ast
import csv
import io
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock


SOURCE = Path(__file__).resolve().parents[1] / "gui.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))


def load_function(name, namespace, class_name=None):
    body = TREE.body
    if class_name:
        body = next(n for n in body if isinstance(n, ast.ClassDef)
                    and n.name == class_name).body
    node = next(n for n in body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace[name]


class FileSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ns = dict(os=os, csv=csv, time=time, showinfo=Mock(), showwarning=Mock(), askyesno=Mock(return_value=True),
                       DATA_CONFIG={"mode": Mock(get=lambda: "燃烧热"), "window": Mock()},
                       filedialog=Mock(), np=Mock())
        for name in ("file_name_extension", "output_path", "dct2cols"):
            load_function(name, self.ns)

    def screen(self, filename):
        source = Path(self.directory.name) / filename
        source.write_text("time(s),Delta_T(K)\n0,0.123\n", encoding="utf-8")
        name, extension = self.ns["file_name_extension"](str(source))
        obj = Mock(absolute_path=str(source), file_name=name, extension=extension,
                   COLS=["filename", "result"], parameters={"filename": filename, "result": 1})
        return source, obj

    def test_raw_data_unchanged_after_result_save(self):
        save = load_function("save_file", self.ns, "Screen")
        for filename in ("1(1)", "run.part.1.csv", "中文.csv", "run.CSV"):
            with self.subTest(filename=filename):
                source, obj = self.screen(filename)
                original = source.read_bytes()
                save(obj)
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(len(list(csv.reader(io.StringIO(source.read_text())))), 2)
                obj.plot_frame.save_fig.assert_called_once_with(str(source.with_suffix(".png")))
        with (Path(self.directory.name) / "combustion.csv").open(encoding="utf-8") as result:
            rows = list(csv.reader(result))
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[-1], ["run.CSV", "1"])

    def test_result_and_image_collisions_block_before_writing(self):
        save = load_function("save_file", self.ns, "Screen")
        for filename in ("combustion.csv", "original.png"):
            with self.subTest(filename=filename):
                source, obj = self.screen(filename)
                original = source.read_bytes()
                save(obj)
                self.assertEqual(source.read_bytes(), original)
                obj.plot_frame.save_fig.assert_not_called()
                self.ns["showwarning"].assert_called()

    def test_hardlink_output_is_blocked(self):
        source, _ = self.screen("raw.csv")
        os.link(source, Path(self.directory.name) / "combustion.csv")
        with self.assertRaises(ValueError):
            self.ns["output_path"](str(source), "combustion.csv")

    def test_fitted_output_for_extensionless_file(self):
        source, obj = self.screen("fit")
        original = source.read_bytes()
        obj.n, obj.Qs, obj.Qs0, obj.a = [], [], 10, 0.1
        obj.dissolution_test_data = [["n0", "Qs(kJ/mol)"]]
        self.ns["np"].stack.return_value = []
        load_function("save_file", self.ns, "Screen4_Fit")(obj)
        self.assertEqual(source.read_bytes(), original)
        self.assertTrue((source.parent / "fit_fitted_data.csv").exists())
        obj.plot_frame.save_fig.assert_called_once_with(str(source.parent / "fit.png"))

    def test_save_dialog_supplies_default_extension_and_cancel_is_safe(self):
        self.ns["filedialog"].asksaveasfilename.return_value = ""
        obj = Mock()
        load_function("data_save", self.ns, "Screen1_Data")(obj)
        self.assertEqual(self.ns["filedialog"].asksaveasfilename.call_args.kwargs["defaultextension"], ".csv")
        obj.entries_frame.dump.assert_not_called()

    def test_stop_recording_and_close_explanation(self):
        obj = Mock(during_measuring=True, temp_file=io.StringIO())
        explain = load_function("explain_close_blocked", self.ns, "Screen1_Data")
        explain(obj)
        self.assertIn("正在采集", self.ns["showinfo"].call_args.kwargs["message"])
        load_function("data_end", self.ns, "Screen1_Data")(obj)
        self.assertFalse(obj.during_measuring)
        explain(obj)
        self.assertIn("尚未保存", self.ns["showinfo"].call_args.kwargs["message"])
        self.ns["DATA_CONFIG"]["window"].destroy.assert_not_called()

    def test_start_binds_explanation_to_window_close(self):
        self.ns["DATA_CONFIG"]["py_path"] = self.directory.name
        obj = Mock(temp_file=io.StringIO(), temp_file_name="tempfile.tmp", _confirming_start=False)
        obj.measure_mode.get.return_value = "combustion"
        load_function("data_start", self.ns, "Screen1_Data")(obj)
        self.addCleanup(obj.temp_file.close)
        self.assertTrue(obj.during_measuring)
        self.ns["DATA_CONFIG"]["window"].protocol.assert_called_once_with(
            "WM_DELETE_WINDOW", obj.explain_close_blocked)


if __name__ == "__main__":
    unittest.main()
