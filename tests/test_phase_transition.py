"""상전이 물리 함수 단위 테스트."""

import os
import sys
import unittest
from unittest.mock import MagicMock

# matplotlib/tkinter mock (phase_transition.py가 import하므로)
sys.modules.setdefault("matplotlib", MagicMock())
sys.modules.setdefault("matplotlib.backends", MagicMock())
sys.modules.setdefault("matplotlib.backends.backend_tkagg", MagicMock())
sys.modules.setdefault("matplotlib.figure", MagicMock())

# numpy는 실제로 필요하지만 없을 수 있으므로 skip 처리
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@unittest.skipUnless(HAS_NUMPY, "numpy not installed")
class TestTemperatureConversion(unittest.TestCase):
    """섭씨 ↔ 켈빈 변환 함수."""

    def setUp(self):
        from physics.phase_transition import _celsius_to_kelvin, _kelvin_to_celsius

        self.c2k = _celsius_to_kelvin
        self.k2c = _kelvin_to_celsius

    def test_celsius_to_kelvin_zero(self):
        self.assertAlmostEqual(self.c2k(0), 273.15)

    def test_kelvin_to_celsius_zero(self):
        self.assertAlmostEqual(self.k2c(0), -273.15)

    def test_roundtrip(self):
        for temp in [-196.0, 0.0, 25.0, 100.0]:
            self.assertAlmostEqual(self.k2c(self.c2k(temp)), temp)

    def test_absolute_zero(self):
        self.assertAlmostEqual(self.c2k(-273.15), 0.0)


@unittest.skipUnless(HAS_NUMPY, "numpy not installed")
class TestResistance(unittest.TestCase):
    """resistance(t, tc, noise) — 초전도 상전이 계산."""

    def setUp(self):
        from physics.phase_transition import MATERIALS, R_NORMAL, resistance

        self.resistance = resistance
        self.MATERIALS = MATERIALS
        self.R_NORMAL = R_NORMAL

    def test_below_tc_zero_resistance(self):
        tc = -196.0
        t = np.array([-250.0, -220.0, -200.0, -197.0])
        r = self.resistance(t, tc, noise=False)
        np.testing.assert_array_equal(r, 0.0)

    def test_at_tc_zero_resistance(self):
        tc = -196.0
        r = self.resistance(np.array([tc]), tc, noise=False)
        self.assertAlmostEqual(r[0], 0.0)

    def test_above_tc_positive_resistance(self):
        tc = -196.0
        t = np.array([-190.0, -100.0, 0.0, 50.0])
        r = self.resistance(t, tc, noise=False)
        self.assertTrue(all(r > 0))

    def test_resistance_increases_with_temp(self):
        tc = -196.0
        t = np.linspace(tc + 1, 50, 100)
        r = self.resistance(t, tc, noise=False)
        self.assertTrue(all(np.diff(r) >= 0))

    def test_resistance_clipped_nonnegative(self):
        tc = -196.0
        t = np.linspace(-275, 50, 500)
        r = self.resistance(t, tc, noise=False)
        self.assertTrue(all(r >= 0))

    def test_noise_below_tc_still_zero(self):
        tc = -196.0
        t = np.array([-250.0, -220.0, -200.0])
        r = self.resistance(t, tc, noise=True)
        np.testing.assert_array_equal(r, 0.0)

    def test_different_materials(self):
        for name, tc in self.MATERIALS.items():
            t = np.array([tc - 10, tc, tc + 10])
            r = self.resistance(t, tc, noise=False)
            self.assertEqual(r[0], 0.0, f"{name}: below Tc")
            self.assertEqual(r[1], 0.0, f"{name}: at Tc")
            self.assertGreater(r[2], 0, f"{name}: above Tc")


@unittest.skipUnless(HAS_NUMPY, "numpy not installed")
class TestMaterials(unittest.TestCase):
    def setUp(self):
        from physics.phase_transition import MATERIALS

        self.MATERIALS = MATERIALS

    def test_materials_exist(self):
        self.assertGreaterEqual(len(self.MATERIALS), 2)

    def test_tc_below_room_temp(self):
        for name, tc in self.MATERIALS.items():
            self.assertLess(tc, 25.0, f"{name}")

    def test_tc_above_absolute_zero(self):
        for name, tc in self.MATERIALS.items():
            self.assertGreater(tc, -273.15, f"{name}")


if __name__ == "__main__":
    unittest.main()
