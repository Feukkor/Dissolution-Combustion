import io
import math
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from acquisition_guide import AcquisitionGuide, GuideConfig, LinearStability
from test_file_safety import load_function


class Replay:
    def __init__(self, guide=None, step=0.55):
        self.guide = guide or AcquisitionGuide()
        self.time = 0.0
        self.step = step

    def feed(self, value):
        self.time += self.step
        return self.guide.feed(value, self.time)

    def repeat(self, value, count):
        for _ in range(count):
            hint = self.feed(value)
        return hint

    def baseline(self, mode="dissolution"):
        self.guide.start(mode)
        self.repeat(1.0, 30)
        return self


def detector(step=0.55, duration=400, fn=lambda t: 1.0, start=0.0):
    c = GuideConfig()
    d = LinearStability(c, c.stable_window_s, c.stable_confirm_s)
    first = None
    for i in range(int(duration / step) + 1):
        t = i * step
        result = d.feed(start + t, fn(t))
        if result.ready and first is None:
            first = t
    return d, first


class LinearStabilityTests(unittest.TestCase):
    def test_flat_baseline_needs_full_window_and_confirmation(self):
        for dt in (0.5, 0.55, 0.6):
            with self.subTest(dt=dt):
                d, first = detector(step=dt, duration=185)
                self.assertGreaterEqual(first, 180 - 1e-8)
                self.assertLessEqual(first, 180 + 2*dt + 1e-8)
                self.assertEqual(d.result.residual_rms_k, 0)

    def test_irregular_timestamps_and_clock_origin_do_not_change_decision(self):
        c = GuideConfig()
        for origin in (0, 1_000_000):
            d = LinearStability(c, 120, 60)
            t = origin
            first = None
            for i in range(360):
                t += (0.5, 0.6, 0.55)[i % 3]
                result = d.feed(t, 1.0)
                if result.ready and first is None:
                    first = t - origin - 0.5
            self.assertGreaterEqual(first, 180 - 1e-8)
            self.assertLess(first, 182)

    def test_many_samples_in_short_time_cannot_skip_wait(self):
        d, first = detector(step=0.1, duration=70)
        self.assertIsNone(first)
        self.assertEqual(d.result.reason, "collecting")

    def test_small_constant_drift_and_quantization_are_allowed(self):
        for sign in (-1, 1):
            d, first = detector(fn=lambda t: round(1 + sign*.004*t/60, 3))
            self.assertIsNotNone(first)
            self.assertTrue(d.result.ready)

    def test_perfect_line_with_excessive_drift_is_not_equilibrium_advice(self):
        for sign in (-1, 1):
            d, first = detector(fn=lambda t: 1 + sign*.06*t/60)
            self.assertIsNone(first)
            self.assertEqual(d.result.reason, "drift")
            self.assertLess(d.result.residual_rms_k, 1e-12)

    def test_curvature_rejected_even_with_small_drift_and_residuals(self):
        c = GuideConfig()
        d = LinearStability(c, 120, 60)
        # Local slopes remain below 0.01 K/min, but change across the window.
        for i in range(241):
            t = i*.5
            result = d.feed(t, 0.5*1.2e-6*(t-60)**2)
        self.assertEqual(result.reason, "curvature")
        self.assertLess(result.residual_rms_k, c.max_residual_rms_k)
        self.assertGreater(result.slope_change_k_min, c.max_slope_change_k_min)

    def test_noise_rejected_without_drift(self):
        d, first = detector(fn=lambda t: 1 + .004 * (-1 if round(t/.55) % 2 else 1))
        self.assertIsNone(first)
        self.assertEqual(d.result.reason, "noise")

    def test_normal_sensor_noise_can_pass(self):
        d, first = detector(fn=lambda t: 1 + .0008*math.sin(t*2.1))
        self.assertIsNotNone(first)
        self.assertTrue(d.result.ready)

    def test_exponential_tail_rejected_at_old_early_hint_then_can_settle(self):
        d, first = detector(duration=185, fn=lambda t: 1-.2*math.exp(-t/180))
        self.assertIsNone(first)
        d, first = detector(duration=900, fn=lambda t: 1-.2*math.exp(-t/180))
        self.assertIsNotNone(first)
        self.assertGreater(first, 180)
        self.assertTrue(d.result.ready)

    def test_spike_revokes_and_requires_fresh_confirmation(self):
        d, _ = detector(step=.5, duration=190)
        self.assertTrue(d.result.ready)
        self.assertFalse(d.feed(190.5, 1.1).ready)
        self.assertIsNone(d.qualified_since)
        self.assertEqual(d.result.reason, "disturbance")
        for i in range(1, 359):
            result = d.feed(190.5+i*.5, 1.0)
            self.assertFalse(result.ready)
        for i in range(359, 365):
            result = d.feed(190.5+i*.5, 1.0)
        self.assertTrue(result.ready)

    def test_short_window_catches_new_trend(self):
        d, _ = detector(step=.5, duration=190)
        for i in range(1, 41):
            result = d.feed(190+i*.5, 1 + .015*(i*.5)/60)
        self.assertFalse(result.ready)
        self.assertIn(result.reason, ("drift", "curvature", "disturbance"))

    def test_gap_cannot_count_towards_confirmation(self):
        d, _ = detector(step=.5, duration=150)
        self.assertEqual(d.result.reason, "confirming")
        result = d.feed(220, 1.0)
        self.assertEqual(result.reason, "collecting")
        self.assertEqual(result.span_s, 0)
        self.assertIsNone(d.qualified_since)

    def test_invalid_config_fails_early(self):
        for kwargs in ({"stable_window_s": 0}, {"minimum_points": 2},
                       {"max_gap_s": math.nan}, {"recent_window_s": 90}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                GuideConfig(**kwargs)


class GuideTests(unittest.TestCase):
    def test_idle_hint_is_time_based_and_revoked_on_new_change(self):
        r=Replay()
        self.assertIsNone(r.repeat(1.0, 160))
        self.assertEqual(r.repeat(1.0, 10), "start_recording")
        self.assertIsNone(r.feed(1.1))

    def test_full_dissolution_and_final_sequence(self):
        r=Replay().baseline()
        self.assertEqual(r.guide.baseline, 1.0)
        self.assertIsNone(r.repeat(0.2, 100))
        self.assertEqual(r.repeat(0.2, 235), "start_heating")
        r.guide.start_heating()
        self.assertIsNone(r.repeat(.69, 8))
        self.assertEqual(r.repeat(.7, 5), "stop_heating")
        r.guide.stop_heating()
        self.assertIsNone(r.repeat(.9, 100))
        self.assertEqual(r.repeat(.9, 230), "stop_recording")
        self.assertIsNone(r.feed(1.0))
        r.guide.stop()
        self.assertIsNone(r.repeat(.9, 400))

    def test_both_dissolution_and_combustion_wait_and_revoke(self):
        for mode, value, hint in (("dissolution", .2, "start_heating"),
                                  ("combustion", 2., "stop_recording")):
            with self.subTest(mode=mode):
                r=Replay().baseline(mode)
                self.assertIsNone(r.repeat(value, 85))
                self.assertEqual(r.repeat(value, 250), hint)
                self.assertIsNone(r.feed(value+.1))
                self.assertIsNone(r.guide.hint)

    def test_return_to_initial_temperature_restarts_event_detection(self):
        for mode, value in (("combustion", 2.), ("dissolution", .2)):
            r=Replay().baseline(mode)
            r.repeat(value, 5)
            self.assertIsNone(r.repeat(1., 400))
            self.assertEqual(r.guide.phase, "waiting_change")

    def test_transient_event_is_not_enough(self):
        r=Replay().baseline("combustion")
        r.repeat(2.,4)
        self.assertIsNone(r.repeat(1.,400))
        self.assertEqual(r.guide.phase,"waiting_change")

    def test_invalid_sample_resets_hint_and_time_window(self):
        for invalid in (None, float("nan"), float("inf")):
            r=Replay().baseline()
            self.assertEqual(r.repeat(.2,335), "start_heating")
            self.assertIsNone(r.feed(invalid))
            self.assertIsNone(r.repeat(.2,100))
            self.assertEqual(r.repeat(.2,230), "start_heating")

    def test_baseline_uses_thirty_consecutive_valid_points(self):
        r=Replay(); r.guide.start("dissolution")
        r.repeat(10., 15); r.feed(None)
        r.repeat(1.,29)
        self.assertIsNone(r.guide.baseline)
        r.feed(1.)
        self.assertEqual(r.guide.baseline,1.)
        r.repeat(2.,40)
        self.assertEqual(r.guide.baseline,1.)

    def test_gap_and_nonmonotonic_times_cannot_leave_a_hint(self):
        for skip in (10., -1., 0.):
            r=Replay().baseline()
            r.repeat(.2,335)
            self.assertEqual(r.guide.hint,"start_heating")
            self.assertIsNone(r.guide.feed(.2,r.time+skip))
            self.assertIsNone(r.guide.hint)

    def test_clock_is_injected_for_live_sampling(self):
        r=Replay()
        g=AcquisitionGuide(clock=lambda:r.time)
        for i in range(170):
            r.time=i*.55
            g.feed(1.)
        self.assertEqual(g.hint,"start_recording")

    def test_heating_target_still_requires_actual_rise_and_is_not_latched(self):
        r=Replay().baseline()
        r.repeat(.9,335)
        r.guide.start_heating()
        self.assertIsNone(r.repeat(.9,20))
        self.assertEqual(r.repeat(.95,5),"stop_heating")
        self.assertIsNone(r.feed(.94))

    def test_manual_heating_before_baseline_does_not_crash_or_invent_target(self):
        r=Replay(); r.guide.start("dissolution")
        r.guide.start_heating()
        self.assertIsNone(r.repeat(.9,100))
        self.assertEqual(r.guide.status_key[1],"no_baseline")
        r.guide.stop_heating()
        self.assertEqual(r.repeat(1.,330),"stop_recording")
        r.guide.reset()
        self.assertIsNone(r.guide.baseline)
        self.assertEqual(r.guide.phase,"idle")


class RelativeDriftTests(unittest.TestCase):
    def run_linear(self, reference, slope, direction=1, require_reference=True):
        c=GuideConfig()
        d=LinearStability(c,120,60)
        ever_ready=False
        for i in range(501):
            t=i*.55
            r=d.feed(t,2+slope*t/60,reference_slope=reference,
                     direction=direction,require_reference=require_reference)
            ever_ready |= r.ready
        return d,ever_ready

    def test_environmental_drift_larger_than_old_limit_can_pass(self):
        for slope in (.02,-.02):
            d,ready=self.run_linear(slope,slope)
            self.assertTrue(ready)
            self.assertTrue(d.result.ready)

    def test_linear_residual_heating_rejected_even_with_zero_fit_residual(self):
        d,ready=self.run_linear(.0006,.019)
        self.assertFalse(ready)
        self.assertEqual(d.result.reason,'excess_drift')
        self.assertLess(d.result.residual_rms_k,1e-12)
        self.assertGreater(d.result.excess_drift_k_min,d.result.excess_limit_k_min)

    def test_difference_near_zero_reference_does_not_divide_by_zero(self):
        for slope,expected in ((.005,True),(.007,False)):
            _,ready=self.run_linear(0.,slope)
            self.assertEqual(ready,expected)

    def test_relative_allowance_for_nonzero_environmental_drift(self):
        d,ready=self.run_linear(.02,.028)
        self.assertTrue(ready)
        self.assertAlmostEqual(d.result.excess_limit_k_min,.01)

    def test_dissolution_allows_linear_rewarming_but_rejects_extra_cooling(self):
        self.assertTrue(self.run_linear(.011,.020,direction=-1)[1])
        d,ready=self.run_linear(.011,-.009,direction=-1)
        self.assertFalse(ready)
        self.assertEqual(d.result.reason,'excess_drift')

    def test_combustion_cooling_is_allowed_but_absolute_guardrail_remains(self):
        self.assertTrue(self.run_linear(.003,-.02)[1])
        d,ready=self.run_linear(.003,-.06)
        self.assertFalse(ready)
        self.assertEqual(d.result.reason,'drift')

    def test_missing_reference_uses_conservative_limit(self):
        self.assertTrue(self.run_linear(None,.005)[1])
        d,ready=self.run_linear(None,.02)
        self.assertFalse(ready)
        self.assertEqual(d.result.reason,'missing_reference')

    def test_reference_is_pre_event_frozen_and_reset_between_runs(self):
        r=Replay();r.guide.start('combustion')
        for _ in range(100):r.feed(1+.003*(r.time+r.step)/60)
        initial=r.guide.reference_slope
        self.assertAlmostEqual(initial,.003,places=10)
        for _ in range(600):r.feed(2+.02*(r.time+r.step)/60)
        self.assertEqual(r.guide.reference_slope,initial)
        self.assertIsNone(r.guide.hint)
        self.assertEqual(r.guide.stability.result.reason,'excess_drift')
        r.guide.interrupt()
        self.assertEqual(r.guide.reference_slope,initial)
        r.guide.start('combustion')
        self.assertIsNone(r.guide.reference_slope)

    def test_early_event_does_not_become_the_initial_reference(self):
        r=Replay().baseline('combustion')
        self.assertEqual(r.guide.status_key[1], 'reference_pending')
        self.assertIn('暂缓加料或点火', r.guide.status)
        r.repeat(2.,600)
        self.assertIsNone(r.guide.reference_slope)

    def test_gap_cannot_complete_initial_reference(self):
        r=Replay().baseline('combustion')
        r.time+=10
        r.repeat(1.,30)
        self.assertIsNone(r.guide.reference_slope)
        r.repeat(1.,30)
        self.assertAlmostEqual(r.guide.reference_slope,0.)

    def test_relative_condition_failure_revokes_and_restarts_confirmation(self):
        c=GuideConfig();d=LinearStability(c,120,60)
        for i in range(400):d.feed(i*.55,1.,reference_slope=0.,direction=1)
        self.assertTrue(d.result.ready)
        # Same points, a stricter reference illustrates that all conditions
        # participate in the confirmation timer, not a post-hoc overlay.
        r=d.feed(220.,1.,reference_slope=-.02,direction=1)
        self.assertEqual(r.reason,'excess_drift')
        self.assertIsNone(d.qualified_since)
        r=d.feed(220.55,1.,reference_slope=0.,direction=1)
        self.assertEqual(r.reason,'confirming')
        self.assertEqual(r.confirmed_s,0.)


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
