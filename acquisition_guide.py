"""Sample-based advice only; this module never controls the apparatus."""
from collections import deque
from dataclasses import dataclass
import math
from statistics import mean


@dataclass(frozen=True)
class GuideConfig:
    idle_points: int = 50
    baseline_points: int = 30
    stable_points: int = 80
    idle_tolerance: float = 0.02
    dissolved_tolerance: float = 0.02
    final_tolerance: float = 0.03
    significant_change: float = 0.10
    confirmation_points: int = 5
    heating_offset: float = 0.30
    heating_min_rise: float = 0.05


class AcquisitionGuide:
    def __init__(self, config=None):
        self.config = config or GuideConfig()
        self.reset()

    def reset(self):
        self.phase = "idle"
        self.mode = None
        self.baseline = None
        self.baseline_samples = []
        self.window = deque(maxlen=max(self.config.idle_points, self.config.stable_points))
        self.recent = deque(maxlen=self.config.confirmation_points)
        self.change_count = 0
        self.hint = None
        self.heating_start_temperature = None
        self.last_temperature = None

    def start(self, mode):
        if mode not in ("dissolution", "combustion"):
            raise ValueError("Unknown experiment mode")
        self.reset()
        self.mode = mode
        self.phase = "waiting_change"

    def interrupt(self):
        """Require fresh windows after a missing/invalid serial reading."""
        self.window.clear()
        self.recent.clear()
        self.change_count = 0
        self.hint = None

    def start_heating(self):
        self.heating_start_temperature = mean(self.recent) if self.recent else self.last_temperature
        self.phase = "heating"
        self.interrupt()

    def stop_heating(self):
        self.phase = "final_stability"
        self.interrupt()

    def stop(self):
        self.phase = "finished"
        self.interrupt()

    def stable(self, count, tolerance):
        values = list(self.window)[-count:]
        return len(values) == count and max(values) - min(values) <= tolerance + 1e-12

    def feed(self, temperature):
        if not isinstance(temperature, (int, float)) or not math.isfinite(temperature):
            self.interrupt()
            return None
        if self.phase == "finished":
            return None
        self.last_temperature = temperature
        self.window.append(temperature)
        self.recent.append(temperature)
        # Hints stay visible until an action or serial interruption.
        if self.hint:
            return self.hint
        c = self.config
        if self.phase == "idle":
            if self.stable(c.idle_points, c.idle_tolerance):
                self.hint = "start_recording"
            return self.hint
        if self.baseline is None:
            self.baseline_samples.append(temperature)
            if len(self.baseline_samples) == c.baseline_points:
                self.baseline = mean(self.baseline_samples)
                self.window.clear()
                self.recent.clear()
            return None
        if self.phase == "waiting_change":
            delta = temperature - self.baseline
            changed = delta <= -c.significant_change + 1e-12 if self.mode == "dissolution" else delta >= c.significant_change - 1e-12
            self.change_count = self.change_count + 1 if changed else 0
            if self.change_count >= c.confirmation_points:
                self.phase = "dissolved_stability" if self.mode == "dissolution" else "burned_stability"
                self.window.clear()
        elif self.phase in ("dissolved_stability", "burned_stability"):
            dissolution = self.phase == "dissolved_stability"
            tolerance = c.dissolved_tolerance if dissolution else c.final_tolerance
            still_changed = (temperature <= self.baseline - c.significant_change + 1e-12 if dissolution
                             else temperature >= self.baseline + c.significant_change - 1e-12)
            if not still_changed:
                self.phase = "waiting_change"
                self.change_count = 0
                self.window.clear()
            elif self.stable(c.stable_points, tolerance):
                self.hint = "start_heating" if dissolution else "stop_recording"
        elif self.phase == "heating":
            # Even a small dissolution drop must show a real rise before advice.
            if self.heating_start_temperature is None:
                self.heating_start_temperature = temperature
            target = max(self.baseline - c.heating_offset,
                         self.heating_start_temperature + c.heating_min_rise)
            if len(self.recent) == c.confirmation_points and min(self.recent) >= target - 1e-12:
                self.hint = "stop_heating"
        elif self.phase == "final_stability":
            if self.stable(c.stable_points, c.final_tolerance):
                self.hint = "stop_recording"
        return self.hint
