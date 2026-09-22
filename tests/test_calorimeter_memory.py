import math
import unittest
from unittest.mock import Mock

from test_file_safety import load_function


class CalorimeterMemoryTests(unittest.TestCase):
    def setUp(self):
        self.config = {"mode": Mock(get=lambda: "燃烧热"),
                       "combustion_mode": Mock(get=lambda: "constant"),
                       "calorimeter_constant": "1234.5"}
        self.namespace = dict(DATA_CONFIG=self.config, math=math, maths=Mock(), showwarning=Mock())
        self.screen = Mock(parameters={"constant(J/K)": "2345.6"})
        self.calculate = load_function("calc_result", self.namespace, "Screen")

    def test_successful_calibration_becomes_session_default(self):
        self.calculate(self.screen)
        self.assertEqual(self.config["calorimeter_constant"], "2345.6")
        self.screen.strEntries.set_value.assert_called_with("constant(J/K)", "2345.6")

    def test_failed_calibration_preserves_previous_default(self):
        self.namespace["maths"].calculate_combustion.side_effect = ZeroDivisionError()
        with self.assertRaises(ZeroDivisionError):
            self.calculate(self.screen)
        self.assertEqual(self.config["calorimeter_constant"], "1234.5")

    def test_nonfinite_result_does_not_replace_default(self):
        for result in ("nan", "inf", "-inf"):
            self.screen.parameters["constant(J/K)"] = result
            self.calculate(self.screen)
            self.assertEqual(self.config["calorimeter_constant"], "1234.5")
        self.assertEqual(self.namespace["showwarning"].call_count, 3)

    def test_input_change_restores_default_instead_of_clearing(self):
        load_function("change_entry", self.namespace, "Screen")(self.screen)
        self.screen.strEntries.set_value.assert_called_with("constant(J/K)", "1234.5")


if __name__ == "__main__":
    unittest.main()
