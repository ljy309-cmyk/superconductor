"""상전이 물리 함수 단위 테스트."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# numpy는 실제로 필요하지만 없을 수 있으므로 skip 처리
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:  # pragma: no cover
    HAS_NUMPY = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# physics/phase_transition.py가 tkinter + matplotlib TkAgg를 import하므로
# 모듈 로드 시에만 mock 적용 후 원복
_tk_mock = MagicMock()
_mpl_mock = MagicMock()
_mock_modules = {
    "tkinter": _tk_mock,
    "tkinter.ttk": _tk_mock,
    "tkinter.messagebox": _tk_mock,
    "tkinter.filedialog": _tk_mock,
    "tkinter.font": _tk_mock,
    "tkinter.simpledialog": _tk_mock,
}
# matplotlib은 이미 로드된 경우 건드리지 않음 (다른 테스트에 영향)
for _m in (
    "matplotlib",
    "matplotlib.backends",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends._backend_tk",
    "matplotlib.figure",
):
    if _m not in sys.modules:
        _mock_modules[_m] = _mpl_mock

with patch.dict(sys.modules, _mock_modules):
    from physics.phase_transition import (  # noqa: E402
        MATERIALS,
        _celsius_to_kelvin,
        _kelvin_to_celsius,
        resistance,
    )


@unittest.skipUnless(HAS_NUMPY, "numpy not installed")
class TestTemperatureConversion(unittest.TestCase):
    """섭씨 ↔ 켈빈 변환 함수."""

    def test_celsius_to_kelvin_zero(self):
        self.assertAlmostEqual(_celsius_to_kelvin(0), 273.15)

    def test_kelvin_to_celsius_zero(self):
        self.assertAlmostEqual(_kelvin_to_celsius(0), -273.15)

    def test_roundtrip(self):
        for temp in [-196.0, 0.0, 25.0, 100.0]:
            self.assertAlmostEqual(_kelvin_to_celsius(_celsius_to_kelvin(temp)), temp)

    def test_absolute_zero(self):
        self.assertAlmostEqual(_celsius_to_kelvin(-273.15), 0.0)


@unittest.skipUnless(HAS_NUMPY, "numpy not installed")
class TestResistance(unittest.TestCase):
    """resistance(t, tc, noise) — 초전도 상전이 계산."""

    def test_below_tc_zero_resistance(self):
        tc = -196.0
        t = np.array([-250.0, -220.0, -200.0, -197.0])
        r = resistance(t, tc, noise=False)
        np.testing.assert_array_equal(r, 0.0)

    def test_at_tc_zero_resistance(self):
        tc = -196.0
        r = resistance(np.array([tc]), tc, noise=False)
        self.assertAlmostEqual(r[0], 0.0)

    def test_above_tc_positive_resistance(self):
        tc = -196.0
        t = np.array([-190.0, -100.0, 0.0, 50.0])
        r = resistance(t, tc, noise=False)
        self.assertTrue(all(r > 0))

    def test_resistance_increases_with_temp(self):
        tc = -196.0
        t = np.linspace(tc + 1, 50, 100)
        r = resistance(t, tc, noise=False)
        self.assertTrue(all(np.diff(r) >= 0))

    def test_resistance_clipped_nonnegative(self):
        tc = -196.0
        t = np.linspace(-275, 50, 500)
        r = resistance(t, tc, noise=False)
        self.assertTrue(all(r >= 0))

    def test_noise_below_tc_still_zero(self):
        tc = -196.0
        t = np.array([-250.0, -220.0, -200.0])
        r = resistance(t, tc, noise=True)
        np.testing.assert_array_equal(r, 0.0)

    def test_different_materials(self):
        for name, tc in MATERIALS.items():
            t = np.array([tc - 10, tc, tc + 10])
            r = resistance(t, tc, noise=False)
            self.assertEqual(r[0], 0.0, f"{name}: below Tc")
            self.assertEqual(r[1], 0.0, f"{name}: at Tc")
            self.assertGreater(r[2], 0, f"{name}: above Tc")


@unittest.skipUnless(HAS_NUMPY, "numpy not installed")
class TestMaterials(unittest.TestCase):
    def test_materials_exist(self):
        self.assertGreaterEqual(len(MATERIALS), 2)

    def test_tc_below_room_temp(self):
        for name, tc in MATERIALS.items():
            self.assertLess(tc, 25.0, f"{name}")

    def test_tc_above_absolute_zero(self):
        for name, tc in MATERIALS.items():
            self.assertGreater(tc, -273.15, f"{name}")


if __name__ == "__main__":
    unittest.main()
