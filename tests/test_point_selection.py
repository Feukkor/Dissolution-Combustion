import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maths


def dissolution_curve(t1=230.0, plateau=100.0):
    """生成一条带噪声的溶解热曲线：前基线 → 急降 → 谷底平台 → 加热 → 后基线。"""
    t = np.arange(0.0, 420.0, 0.5)
    y = 0.02 + 1e-5 * t
    y -= 0.69 / (1.0 + np.exp(-(t - (t1 - plateau - 30.0)) / 6.0))
    y += 1.8e-4 * np.clip(t - (t1 - plateau + 10.0), 0, None)
    y += np.where(
        t < t1,
        0.0,
        np.where(t < t1 + 70.0, 0.005 * (t - t1), 0.35 + 5e-4 * (t - t1 - 70.0)),
    )
    y += np.random.default_rng(7).normal(0.0, 5e-4, t.size)
    return np.column_stack((t, np.round(y, 3)))


class DissolutionSelectionTests(unittest.TestCase):
    def test_low_plateau_stays_on_plateau_and_keeps_enough_points(self):
        plateau = 100.0
        for t1 in (200.0, 230.0, 260.0):
            with self.subTest(t1=t1):
                csv = dissolution_curve(t1=t1, plateau=plateau)
                t = csv[:, 0]
                pts = maths.find_start_end_point(csv, "溶解热", 0, 0, 0, t1)
                self.assertEqual(len(pts), 6)
                self.assertEqual(pts, sorted(pts))
                # 左端必须已经越过急降段，不能落在降温尾段上
                self.assertGreater(t[pts[2]], t1 - plateau + 5.0)
                # 右端仍应在加热开始之前
                self.assertLess(t[pts[3]], t1)
                # 平台区间保留足够多的点，而不是靠最大化 R² 缩到几个点
                self.assertGreaterEqual(pts[3] - pts[2] + 1, 60)
                # 平台本身应当近似线性
                self.assertGreater(maths.linear_regression(csv, pts[2], pts[3])[4], 0.9)
                self.assertGreater(maths.linear_regression(csv, pts[4], pts[5])[4], 0.9)


if __name__ == "__main__":
    unittest.main()
