"""Reproduce selection edge cases without changing the algorithm.
Run from source root: .venv/Scripts/python.exe tools/point_selection_examples.py
"""
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maths


def cases():
    t = np.arange(40.) * 10
    yield "sparse_complete_curve", np.column_stack((t, .00002*t + 1/(1+np.exp(-(t-160)/8))))
    t = np.arange(100.) * .1
    yield "high_rate_short_record", np.column_stack((t, .001*t))
    t = np.arange(100.)
    yield "drift_without_event", np.column_stack((t, .001*t))
    t = np.arange(480.)
    yield "complete_combustion_curve", np.column_stack((t, .00002*t + 1/(1+np.exp(-(t-120)/8))))


def main():
    for name, data in cases():
        modes = ("燃烧热",) if name == "complete_combustion_curve" else ("燃烧热", "溶解热")
        for mode in modes:
            result = dict(case=name, mode=mode, points=len(data), duration_s=float(data[-1, 0]))
            try:
                indices = maths.find_start_end_point(data, mode, 30, 40, .005)
                result["indices"] = indices
                result["ordered_and_in_bounds"] = all(0 <= p < len(data) for p in indices) and all(a < b for a, b in zip(indices, indices[1:]))
            except Exception as error:
                result["error"] = f"{type(error).__name__}: {error}"
            print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
