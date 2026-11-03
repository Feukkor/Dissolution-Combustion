"""Keep Reynolds integration usable with SciPy's keyword-only x API."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
from scipy.integrate import simpson
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maths


class ReynoldsCompatibilityTests(unittest.TestCase):
    def test_all_three_integrals_accept_keyword_only_x_and_preserve_results(self):
        t = np.arange(480.)
        data = np.column_stack((t, .00002*t + 1/(1+np.exp(-(t-120)/8))))
        expected = maths.Reynolds(data, 0, 60, 200, 479, .1)
        calls = []

        def keyword_only_integral(y, *, x):
            calls.append(len(x))
            return simpson(y, x=x)

        with patch.object(maths, "simpson", keyword_only_integral):
            actual = maths.Reynolds(data, 0, 60, 200, 479, .1)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(n > 1 for n in calls))
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)
        self.assertTrue(np.isfinite(actual).all())
        self.assertTrue(60 < actual[0] < 200)
        self.assertGreater(actual[1], 0)
        self.assertGreater(actual[2], 0)


if __name__ == "__main__":
    unittest.main()
