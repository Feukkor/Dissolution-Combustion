"""Time-based baseline advice only; never controls the apparatus.

Stationary environmental drift is allowed. A high R-squared alone is not
evidence of a usable baseline: compare against the initial drift as well as
checking curvature, fit residuals and a broad absolute-rate guardrail.
"""
from collections import deque
from dataclasses import dataclass
import math
from statistics import mean
import time


@dataclass(frozen=True)
class GuideConfig:
    # Candidate defaults for 0.5-0.6 s sampling; calibrate using real full runs.
    idle_window_s: float = 60.0
    idle_confirm_s: float = 30.0
    stable_window_s: float = 120.0
    stable_confirm_s: float = 60.0
    recent_window_s: float = 30.0
    max_gap_s: float = 2.0
    minimum_points: int = 30
    max_drift_k_min: float = 0.050
    reference_window_s: float = 30.0
    max_excess_drift_k_min: float = 0.006
    excess_drift_fraction: float = 0.5
    missing_reference_max_drift_k_min: float = 0.010
    max_slope_change_k_min: float = 0.003
    max_residual_rms_k: float = 0.002
    max_residual_peak_k: float = 0.006
    baseline_points: int = 30
    significant_change: float = 0.10
    confirmation_points: int = 5
    heating_offset: float = 0.30
    heating_min_rise: float = 0.05

    def __post_init__(self):
        for name, value in vars(self).items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        for name in ("minimum_points", "baseline_points", "confirmation_points"):
            if not isinstance(getattr(self, name), int):
                raise ValueError(f"{name} must be an integer")
        if self.minimum_points < 6:
            raise ValueError("minimum_points must allow two three-point fits")
        if self.recent_window_s > min(self.idle_window_s, self.stable_window_s) / 2:
            raise ValueError("recent_window_s must fit inside half of each long window")
        if self.max_gap_s >= self.recent_window_s:
            raise ValueError("max_gap_s must be shorter than recent_window_s")


@dataclass(frozen=True)
class StabilityResult:
    reason: str
    span_s: float = 0.0
    confirmed_s: float = 0.0
    slope_k_min: float = 0.0
    slope_change_k_min: float = 0.0
    residual_rms_k: float = 0.0
    residual_peak_k: float = 0.0
    reference_slope_k_min: float | None = None
    excess_drift_k_min: float = 0.0
    excess_limit_k_min: float = 0.0

    @property
    def ready(self):
        return self.reason == "ready"


def _line_fit(samples):
    """Centered least squares; input times are seconds, result slope K/min."""
    origin = samples[0][0]
    xs = [t - origin for t, _ in samples]
    ys = [y for _, y in samples]
    mx, my = mean(xs), mean(ys)
    xx = math.fsum((x - mx) ** 2 for x in xs)
    slope = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys)) / xx
    residuals = [y - (my + slope * (x - mx)) for x, y in zip(xs, ys)]
    rms = math.sqrt(math.fsum(r * r for r in residuals) / len(residuals))
    return slope * 60, rms, max(abs(r) for r in residuals)


class LinearStability:
    """Sliding time window plus continuous confirmation, with no hint latch."""
    def __init__(self, config, window_s, confirm_s):
        self.config = config
        self.window_s = window_s
        self.confirm_s = confirm_s
        self.reset()

    def reset(self):
        self.samples = deque()
        self.qualified_since = None
        self.result = StabilityResult("collecting")

    def feed(self, timestamp, temperature, reference_slope=None, direction=0,
             require_reference=False):
        c = self.config
        if self.samples and (timestamp <= self.samples[-1][0] or
                             timestamp - self.samples[-1][0] > c.max_gap_s):
            self.reset()
        self.samples.append((timestamp, temperature))
        # Retain one point at/before the left boundary, ensuring a full duration.
        cutoff = timestamp - self.window_s
        while len(self.samples) > 1 and self.samples[1][0] <= cutoff:
            self.samples.popleft()
        span = timestamp - self.samples[0][0]
        if span + 1e-9 < self.window_s or len(self.samples) < c.minimum_points:
            self.qualified_since = None
            self.result = StabilityResult("collecting", span)
            return self.result
        samples = list(self.samples)
        midpoint = timestamp - self.window_s / 2
        front = [p for p in samples if p[0] < midpoint]
        back = [p for p in samples if p[0] >= midpoint]
        recent = [p for p in samples if p[0] >= timestamp - c.recent_window_s]
        if min(len(front), len(back), len(recent)) < 3:
            self.qualified_since = None
            self.result = StabilityResult("collecting", span)
            return self.result
        slope, rms, peak = _line_fit(samples)
        front_slope = _line_fit(front)[0]
        back_slope = _line_fit(back)[0]
        recent_slope = _line_fit(recent)[0]
        change = max(abs(front_slope - back_slope), abs(recent_slope - slope))
        limit = max(c.max_excess_drift_k_min,
                    c.excess_drift_fraction * abs(reference_slope or 0.0))
        rates = (slope, front_slope, back_slope, recent_slope)
        excess = (max(direction * (rate - reference_slope) for rate in rates)
                  if reference_slope is not None and direction else 0.0)
        drift_limit = (min(c.max_drift_k_min, c.missing_reference_max_drift_k_min)
                       if require_reference and reference_slope is None else c.max_drift_k_min)
        # Peak residual also catches new jumps that a long-window RMS can dilute.
        if peak > c.max_residual_peak_k + 1e-12:
            reason = "disturbance"
        elif rms > c.max_residual_rms_k + 1e-12:
            reason = "noise"
        elif excess > limit + 1e-12:
            reason = "excess_drift"
        elif max(abs(rate) for rate in rates) > drift_limit + 1e-12:
            reason = "missing_reference" if require_reference and reference_slope is None else "drift"
        elif change > c.max_slope_change_k_min + 1e-12:
            reason = "curvature"
        else:
            reason = "confirming"
        confirmed = 0.0
        if reason == "confirming":
            if self.qualified_since is None:
                self.qualified_since = timestamp
            confirmed = timestamp - self.qualified_since
            if confirmed + 1e-9 >= self.confirm_s:
                reason = "ready"
        else:
            self.qualified_since = None
        self.result = StabilityResult(reason, span, confirmed, slope, change, rms, peak,
                                      reference_slope, max(0.0, excess), limit)
        return self.result


class AcquisitionGuide:
    def __init__(self, config=None, clock=None):
        self.config = config or GuideConfig()
        self.clock = clock or time.monotonic
        self.reset()

    def reset(self):
        c = self.config
        self.phase = "idle"
        self.mode = None
        self.baseline = None
        self.baseline_samples = []
        self.reference_samples = deque()
        self.reference_slope = None
        self.recent = deque(maxlen=c.confirmation_points)
        self.change_count = 0
        self.hint = None
        self.heating_start_temperature = None
        self.last_temperature = None
        self.last_timestamp = None
        self.stability = LinearStability(c, c.idle_window_s, c.idle_confirm_s)
        self.status_key = (self.phase, "collecting")
        self.status = "正在观察记录前基线，请继续等待。"

    def _new_stability_window(self):
        c = self.config
        self.stability = LinearStability(c, c.stable_window_s, c.stable_confirm_s)

    def _status(self, reason, message):
        self.status_key = (self.phase, reason)
        self.status = message

    def start(self, mode):
        if mode not in ("dissolution", "combustion"):
            raise ValueError("Unknown experiment mode")
        self.reset()
        self.mode = mode
        self.phase = "waiting_change"
        self._new_stability_window()
        self._status("baseline", "正在建立本轮参考温差，请暂缓加料或点火。")

    def interrupt(self):
        """No elapsed gap or stale hint counts towards baseline qualification."""
        self.stability.reset()
        self.reference_samples.clear()
        self.recent.clear()
        self.change_count = 0
        self.hint = None
        self.last_temperature = None
        self.last_timestamp = None
        if self.baseline is None:
            self.baseline_samples.clear()
        self._status("interrupted", "数据不连续，已撤销操作建议；需要重新观察基线。")

    def start_heating(self):
        self.heating_start_temperature = mean(self.recent) if self.recent else self.last_temperature
        self.phase = "heating"
        self.interrupt()
        self._status("heating", "正在加热，按目标温差判断停止时机。")

    def stop_heating(self):
        self.phase = "final_stability"
        self.interrupt()
        self._new_stability_window()
        self._status("collecting", "已停止加热，正在观察余热与末期基线，请继续记录。")

    def stop(self):
        self.phase = "finished"
        self.interrupt()
        self._status("finished", "记录已结束，请保存数据。")

    def _observe_reference(self, timestamp, temperature):
        # Freeze the first valid pre-event baseline; never learn the post-event
        # tail as a new reference just because it is locally linear.
        if self.reference_slope is not None or self.phase != "waiting_change":
            return
        c = self.config
        if self.reference_samples and abs(temperature - self.reference_samples[0][1]) >= c.significant_change / 2:
            self.reference_samples.clear()
            return
        if self.baseline is not None and abs(temperature - self.baseline) >= c.significant_change / 2:
            self.reference_samples.clear()
            return
        self.reference_samples.append((timestamp, temperature))
        while len(self.reference_samples) > 1 and self.reference_samples[1][0] <= timestamp - c.reference_window_s:
            self.reference_samples.popleft()
        samples = list(self.reference_samples)
        if len(samples) < c.minimum_points or timestamp - samples[0][0] < c.reference_window_s:
            return
        slope, rms, peak = _line_fit(samples)
        midpoint = (samples[0][0] + timestamp) / 2
        front = [p for p in samples if p[0] < midpoint]
        back = [p for p in samples if p[0] >= midpoint]
        if min(len(front), len(back)) < 3:
            return
        a, b = _line_fit(front)[0], _line_fit(back)[0]
        if (max(abs(slope), abs(a), abs(b)) <= c.max_drift_k_min
                and abs(a-b) <= c.max_slope_change_k_min
                and rms <= c.max_residual_rms_k and peak <= c.max_residual_peak_k):
            self.reference_slope = slope
            self.reference_samples.clear()

    def _check_stability(self, timestamp, temperature, hint):
        direction = -1 if self.phase == "dissolved_stability" else 1
        result = self.stability.feed(timestamp, temperature,
                                     reference_slope=self.reference_slope,
                                     direction=0 if self.phase == "idle" else direction,
                                     require_reference=self.phase != "idle")
        labels = {"idle": "记录前基线", "dissolved_stability": "溶解后基线",
                  "burned_stability": "燃烧后基线", "final_stability": "加热后基线"}
        label = labels[self.phase]
        metrics = (f"温漂 {result.slope_k_min:+.4f} K/min，"
                   f"斜率变化 {result.slope_change_k_min:.4f} K/min，"
                   f"拟合残差 {result.residual_rms_k:.4f} K")
        if result.reference_slope_k_min is not None:
            metrics += f"，初期温漂 {result.reference_slope_k_min:+.4f} K/min"
        action = "降温" if self.phase == "dissolved_stability" else "升温"
        reasons = {
            "collecting": f"正在积累{label}：{min(result.span_s, self.stability.window_s):.0f}/{self.stability.window_s:.0f} 秒，请继续记录。",
            "excess_drift": f"{label}的{action}速率仍高于初期背景（超出 {result.excess_drift_k_min:.4f}，允许 {result.excess_limit_k_min:.4f} K/min），可能仍有热效应，请继续观察。{metrics}",
            "missing_reference": f"缺少足够的初期线性基线，暂按保守温漂上限等待，请人工核对。{metrics}",
            "drift": f"{label}仍在明显升降温，暂不建议下一步。{metrics}",
            "curvature": f"{label}变化速度尚未稳定，暂不建议下一步。{metrics}",
            "noise": f"{label}偏离直线的波动较大，请继续观察。{metrics}",
            "disturbance": f"{label}出现偏离直线的变化或扰动，请继续观察。{metrics}",
            "confirming": f"{label}初步符合，连续确认 {min(result.confirmed_s, self.stability.confirm_s):.0f}/{self.stability.confirm_s:.0f} 秒。{metrics}",
            "ready": f"{label}已满足设定判据。{metrics}",
        }
        self.hint = hint if result.ready else None
        self._status(result.reason, reasons[result.reason])

    def _waiting_reference_status(self):
        if self.reference_slope is None:
            self._status("reference_pending",
                         f"参考温差已建立，但初期温漂参考尚未建立；需连续 {self.config.reference_window_s:.0f} 秒近似线性数据，请暂缓加料或点火。")
        else:
            self._status("waiting_change",
                         f"初期温漂参考已建立（{self.reference_slope:+.4f} K/min），等待持续实验温变；参考值不代表体系已热平衡。")

    def feed(self, temperature, timestamp=None):
        timestamp = self.clock() if timestamp is None else timestamp
        if (not isinstance(temperature, (int, float)) or not math.isfinite(temperature)
                or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp)):
            self.interrupt()
            return None
        if self.phase == "finished":
            return None
        if self.last_timestamp is not None:
            if timestamp <= self.last_timestamp:
                self.interrupt()
                return None
            if timestamp - self.last_timestamp > self.config.max_gap_s:
                self.interrupt()
        self.last_timestamp = timestamp
        self.last_temperature = temperature
        self.recent.append(temperature)
        self.hint = None
        c = self.config
        self._observe_reference(timestamp, temperature)
        if self.phase == "idle":
            self._check_stability(timestamp, temperature, "start_recording")
        elif self.phase == "heating":
            # Target crossing is deliberately separate from equilibrium advice.
            if self.baseline is None:
                self._status("no_baseline", "本轮参考温差尚未建立，请人工判断停止加热时机。")
                return None
            if self.heating_start_temperature is None:
                self.heating_start_temperature = temperature
            target = max(self.baseline - c.heating_offset,
                         self.heating_start_temperature + c.heating_min_rise)
            if len(self.recent) == c.confirmation_points and min(self.recent) >= target - 1e-12:
                self.hint = "stop_heating"
            self._status("target_reached" if self.hint else "heating",
                         f"加热目标温差 {target:.3f} K；停止加热后仍需观察末期基线。")
        elif self.phase == "final_stability":
            self._check_stability(timestamp, temperature, "stop_recording")
        elif self.baseline is None:
            self.baseline_samples.append(temperature)
            if len(self.baseline_samples) == c.baseline_points:
                self.baseline = mean(self.baseline_samples)
                self.recent.clear()
                self._waiting_reference_status()
            else:
                self._status("baseline", f"正在建立参考温差：{len(self.baseline_samples)}/{c.baseline_points} 点，请暂缓加料或点火。")
        elif self.phase == "waiting_change":
            delta = temperature - self.baseline
            changed = delta <= -c.significant_change + 1e-12 if self.mode == "dissolution" else delta >= c.significant_change - 1e-12
            self.change_count = self.change_count + 1 if changed else 0
            self._waiting_reference_status()
            if self.change_count >= c.confirmation_points:
                self.phase = "dissolved_stability" if self.mode == "dissolution" else "burned_stability"
                self._new_stability_window()
                self._check_stability(timestamp, temperature,
                                      "start_heating" if self.mode == "dissolution" else "stop_recording")
        elif self.phase in ("dissolved_stability", "burned_stability"):
            dissolution = self.phase == "dissolved_stability"
            still_changed = (temperature <= self.baseline - c.significant_change + 1e-12 if dissolution
                             else temperature >= self.baseline + c.significant_change - 1e-12)
            if not still_changed:
                self.phase = "waiting_change"
                self.change_count = 0
                self.stability.reset()
                self._status("waiting_change", "温差已回到初始范围，重新等待持续实验温变。")
            else:
                self._check_stability(timestamp, temperature,
                                      "start_heating" if dissolution else "stop_recording")
        return self.hint
