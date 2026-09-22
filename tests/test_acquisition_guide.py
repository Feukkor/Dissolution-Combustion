import io
import math
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition_guide import AcquisitionGuide
from test_file_safety import load_function


def feed(guide, values):
    for value in values:
        hint = guide.feed(value)
    return hint


class GuideTests(unittest.TestCase):
    def baseline(self, mode="dissolution"):
        guide = AcquisitionGuide()
        guide.start(mode)
        feed(guide, [1.0] * 30)
        self.assertEqual(guide.baseline, 1.0)
        return guide

    def test_idle_full_window_and_latched_hint(self):
        g = AcquisitionGuide()
        self.assertIsNone(feed(g, [1.0] * 49))
        self.assertEqual(g.feed(1.02), "start_recording")
        self.assertEqual(g.feed(1.5), "start_recording")
        g.interrupt()
        self.assertIsNone(feed(g, [1.0] * 49))
        self.assertEqual(g.feed(1.0), "start_recording")

    def test_unstable_idle(self):
        g = AcquisitionGuide()
        self.assertIsNone(feed(g, [1.0, 1.021] * 100))

    def test_baseline_uses_only_first_thirty_recorded_points(self):
        g = AcquisitionGuide()
        feed(g, [10.0] * 60)
        g.start("dissolution")
        feed(g, [1.0] * 15 + [1.02] * 14)
        self.assertIsNone(g.baseline)
        g.feed(1.02)
        self.assertAlmostEqual(g.baseline, 1.01)
        feed(g, [3.0] * 100)
        self.assertAlmostEqual(g.baseline, 1.01)

    def test_full_dissolution_sequence(self):
        g = self.baseline()
        self.assertIsNone(feed(g, [1.0] * 100))
        self.assertIsNone(feed(g, [0.2] * 5))
        self.assertIsNone(feed(g, [0.2] * 79))
        self.assertEqual(g.feed(0.2), "start_heating")
        self.assertEqual(g.feed(0.1), "start_heating")
        g.start_heating()
        self.assertIsNone(feed(g, [0.69] * 8))
        self.assertIsNone(feed(g, [0.7] * 4))
        self.assertEqual(g.feed(0.7), "stop_heating")
        g.stop_heating()
        self.assertIsNone(feed(g, [0.8, 0.84] * 40))
        self.assertIsNone(feed(g, [0.9] * 79))
        self.assertEqual(g.feed(0.9), "stop_recording")
        g.stop()
        self.assertIsNone(feed(g, [0.9] * 100))

    def test_small_drop_requires_actual_heating_rise(self):
        g = self.baseline()
        feed(g, [0.9] * 85)
        self.assertEqual(g.hint, "start_heating")
        g.start_heating()
        self.assertIsNone(feed(g, [0.9] * 20))
        self.assertEqual(feed(g, [0.95] * 5), "stop_heating")

    def test_combustion_needs_sustained_rise_then_new_stable_window(self):
        g = self.baseline("combustion")
        self.assertIsNone(feed(g, [1.0] * 100))
        feed(g, [2.0] * 4 + [1.0] * 80)
        self.assertIsNone(g.hint)
        feed(g, [1.1] * 5)
        self.assertIsNone(feed(g, [1.1] * 79))
        self.assertEqual(g.feed(1.13), "stop_recording")

    def test_transient_change_returning_to_baseline_does_not_qualify(self):
        for mode, excursion in (("combustion", 2.0), ("dissolution", 0.2)):
            g = self.baseline(mode)
            feed(g, [excursion] * 5)
            self.assertIsNone(feed(g, [1.0] * 100))
            self.assertEqual(g.phase, "waiting_change")

    def test_invalid_sample_clears_hint_and_stability_window(self):
        for invalid in (None, float("nan"), float("inf")):
            g = self.baseline()
            feed(g, [0.2] * 85)
            self.assertEqual(g.hint, "start_heating")
            self.assertIsNone(g.feed(invalid))
            self.assertIsNone(feed(g, [0.2] * 79))
            self.assertEqual(g.feed(0.2), "start_heating")

    def test_manual_stage_changes_and_new_run_reset(self):
        g = self.baseline()
        g.start_heating()
        g.stop_heating()
        self.assertEqual(feed(g, [1.0] * 80), "stop_recording")
        g.reset()
        self.assertIsNone(g.baseline)
        self.assertEqual(g.phase, "idle")
        self.assertIsNone(g.hint)


class GUIIntegrationTests(unittest.TestCase):
    def test_cancel_confirmation_does_not_start_or_clear_data(self):
        ns = dict(askyesno=Mock(return_value=False), DATA_CONFIG={"window": Mock()})
        obj = Mock(_confirming_start=False, during_measuring=False)
        obj.measure_mode.get.return_value = "combustion"
        load_function("data_start", ns, "Screen1_Data")(obj)
        self.assertIn("燃烧热", ns["askyesno"].call_args.kwargs["message"])
        obj.guide.start.assert_not_called()
        obj.rainbow.clear.assert_not_called()
        obj.temp_file.close.assert_not_called()
        self.assertFalse(obj.during_measuring)
        self.assertFalse(obj._confirming_start)

    def test_duplicate_confirmation_is_ignored(self):
        ns = dict(askyesno=Mock())
        load_function("data_start", ns, "Screen1_Data")(Mock(_confirming_start=True))
        ns["askyesno"].assert_not_called()

    def test_serial_failure_drops_hint_and_reschedules(self):
        class Timeout(Exception):
            pass
        ns = dict(math=math, time=time, FunctionTimedOut=Timeout,
                  DATA_CONFIG={"time_interval": 500, "plot_max_points": 500})
        method = load_function("read_comport", ns, "Screen1_Data")
        obj = Mock(comport=Mock(read=Mock(return_value=None)))
        method(obj)
        obj.guide.interrupt.assert_called_once()
        obj.rainbow.clear.assert_called_once()
        obj.update_guidance.assert_not_called()
        obj.after.assert_called_once_with(500, obj.read_comport)

    def test_good_serial_sample_flows_to_recording_and_guidance(self):
        class Timeout(Exception):
            pass
        ns = dict(math=math, time=time, FunctionTimedOut=Timeout,
                  DATA_CONFIG={"time_interval": 500, "plot_max_points": 500})
        obj = Mock(comport=Mock(read=Mock(return_value=0.123)), start_time=time.time(),
                   temp_file=io.StringIO(), during_measuring=True, csv_data=[],
                   temp_Delta_t=[], temp_Delta_T=[])
        load_function("read_comport", ns, "Screen1_Data")(obj)
        self.assertEqual(len(obj.csv_data), 1)
        obj.update_guidance.assert_called_once_with(0.123)
        obj.after.assert_called_once_with(500, obj.read_comport)

    def test_disconnected_startup_still_schedules_reading(self):
        ns = dict(DATA_CONFIG={"time_interval": 500}, FunctionTimedOut=Exception)
        obj = Mock(comport=None)
        load_function("read_comport", ns, "Screen1_Data")(obj)
        obj.after.assert_called_once_with(500, obj.read_comport)


if __name__ == "__main__":
    unittest.main()
