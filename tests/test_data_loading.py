import csv
from functools import wraps
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data_loading import DataLoadError, FIT_FIELDS, RAW_FIELDS, load_fit, load_raw
from test_file_safety import load_function


class LoadingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "无后缀"

    def write(self, text):
        self.path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        return str(self.path)

    def raw(self, mode="燃烧热", parameters=True):
        rows = [[field, "1"] for field in RAW_FIELDS[mode]] if parameters else []
        rows += [["time(s)", "Delta_T(K)"]] + [[str(i), "0.1"] for i in range(8)]
        return "\n".join(",".join(row) for row in rows)

    def fit(self):
        return ",".join(FIT_FIELDS) + "\n" + "500,1,1,74.5,0.1\n" * 3

    def test_valid_raw_files_and_utf8_bom(self):
        for mode in RAW_FIELDS:
            for params in (True, False):
                for bom in ("", "\ufeff"):
                    with self.subTest(mode=mode, parameters=params, bom=bool(bom)):
                        result, data = load_raw(self.write(bom + self.raw(mode, params)), mode)
                        self.assertEqual(len(result), len(RAW_FIELDS[mode]) if params else 0)
                        self.assertEqual(len(data), 8)

    def test_format_and_encoding_errors(self):
        cases = [(b"PK\x03\x04Excel", "文件格式错误"),
                 (b"%PDF-1.7", "文件格式错误"),
                 ("温度,时间".encode("gbk"), "编码错误"),
                 (self.raw().encode("utf-16"), "编码错误"),
                 (b"abc\x00def", "文件格式错误"),
                 ("\n\n", "文件为空"),
                 ('"unterminated', "CSV 格式错误")]
        for content, expected in cases:
            with self.subTest(expected=expected, content=content[:15]):
                with self.assertRaisesRegex(DataLoadError, expected):
                    load_raw(self.write(content), "燃烧热")

    def test_raw_schema_errors(self):
        cases = [(self.raw() + "\n" + ",".join(["1"] * 20), "第 16 行应有 2 列，实际有 20 列"),
                 (self.raw("溶解热"), "正确的处理模块"),
                 (self.raw().replace("cotton_mass(g)", "water_volume(mL)"), "重复参数"),
                 (self.raw().replace("0,0.1", "0,bad"), "第 8 行.*必须是数字"),
                 (self.raw().replace("0,0.1", "0,nan"), "有限数值"),
                 (self.raw().replace("1,0.1", "0,0.1"), "时间 0.0 重复"),
                 ("time(s),Delta_T(K)\n0,1", "至少需要 4"),
                 (self.raw().replace("Delta_T(K)", "temperature"), "表头错误")]
        for content, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(DataLoadError, expected):
                    load_raw(self.write(content), "燃烧热")

    def test_fit_schema(self):
        self.assertEqual(len(load_fit(self.write(self.fit()))), 3)
        cases = [(self.raw(), "缺少必要列"),
                 (self.fit().replace("500,1,1,74.5,0.1", "500,1,1,74.5"), "实际有 4 列"),
                 (self.fit().replace("74.5", "0"), "必须大于零"),
                 (self.fit().replace("0.1", "0"), "累计溶解热为零"),
                 (self.fit().replace("0.1", "inf"), "有限数值"),
                 (",".join(FIT_FIELDS) + "\n500,1,1,74.5,1", "至少需要 3")]
        for content, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(DataLoadError, expected):
                    load_fit(self.write(content))

    def test_missing_file(self):
        with self.assertRaisesRegex(DataLoadError, "无法读取文件"):
            load_raw(str(self.path), "燃烧热")

    def test_invalid_load_shows_reason_without_replacing_previous_data(self):
        for class_name in ("Screen", "Screen4_Fit"):
            with self.subTest(module=class_name):
                ns = dict(wraps=wraps, DataLoadError=DataLoadError, load_raw=load_raw,
                          load_fit=load_fit, showwarning=Mock(),
                          DATA_CONFIG={"mode": Mock(get=lambda: "燃烧热"), "window": Mock(), "csv": "previous"},
                          filedialog=Mock())
                ns["filedialog"].askopenfilename.return_value = self.write(b"%PDF-1.7")
                load_function("explain_load_failure", ns)
                obj = Mock(absolute_path="previous.csv")
                load_function("open_file", ns, class_name)(obj)
                self.assertIn("文件格式错误", ns["showwarning"].call_args.kwargs["message"])
                self.assertEqual(obj.absolute_path, "previous.csv")
                self.assertEqual(ns["DATA_CONFIG"]["csv"], "previous")
                obj.table_frame.clear.assert_not_called()

    def test_numerical_failure_shows_diagnostics_and_disables_save(self):
        ns = dict(wraps=wraps, DataLoadError=DataLoadError, showwarning=Mock(), DATA_CONFIG={"window": Mock()})
        decorate = load_function("explain_load_failure", ns)
        def fail(obj):
            raise RuntimeError("fit did not converge")
        obj = Mock()
        decorate(fail)(obj)
        self.assertIn("fit did not converge", ns["showwarning"].call_args.kwargs["message"])
        obj.button_save.config.assert_called_with(state="disabled")


if __name__ == "__main__":
    unittest.main()
