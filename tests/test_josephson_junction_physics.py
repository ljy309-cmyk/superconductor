"""조셉슨 접합 물리 엔진 단위 테스트."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from physics.josephson_junction_physics import (
    BIAS_MAX,
    JosephsonJunction,
    ac_frequency,
    iv_curve_point,
    josephson_current,
    washboard_potential,
)


class TestJosephsonCurrent(unittest.TestCase):
    """josephson_current(φ) — DC 조셉슨 전류."""

    def test_at_zero_phase(self):
        """φ=0에서 전류가 0이어야 한다."""
        self.assertAlmostEqual(josephson_current(0.0), 0.0)

    def test_at_pi_half(self):
        """φ=π/2에서 전류가 Ic여야 한다."""
        self.assertAlmostEqual(josephson_current(math.pi / 2), 1.0, places=5)

    def test_at_pi(self):
        """φ=π에서 전류가 0이어야 한다."""
        self.assertAlmostEqual(josephson_current(math.pi), 0.0, places=5)

    def test_at_3pi_half(self):
        """φ=3π/2에서 전류가 -Ic여야 한다."""
        self.assertAlmostEqual(josephson_current(3 * math.pi / 2), -1.0, places=5)

    def test_sinusoidal(self):
        """I = Ic × sin(φ) 공식과 일치해야 한다."""
        for phi in [0.1, 0.5, 1.0, 2.0, 3.0, 5.0]:
            ic = 2.5
            expected = ic * math.sin(phi)
            self.assertAlmostEqual(josephson_current(phi, ic), expected)

    def test_periodic(self):
        """2π 주기여야 한다."""
        phi = 1.23
        self.assertAlmostEqual(
            josephson_current(phi),
            josephson_current(phi + 2 * math.pi),
            places=10,
        )


class TestACFrequency(unittest.TestCase):
    """ac_frequency(V) — AC 조셉슨 주파수."""

    def test_zero_voltage(self):
        """V=0이면 주파수 0."""
        self.assertAlmostEqual(ac_frequency(0.0), 0.0)

    def test_proportional_to_voltage(self):
        """주파수가 전압에 비례해야 한다 (f = 2πV)."""
        self.assertAlmostEqual(ac_frequency(1.0), 2 * math.pi)
        self.assertAlmostEqual(ac_frequency(2.0), 4 * math.pi)

    def test_negative_voltage(self):
        """음의 전압은 음의 주파수를 준다."""
        self.assertAlmostEqual(ac_frequency(-1.0), -2 * math.pi)


class TestWashboardPotential(unittest.TestCase):
    """washboard_potential(φ) — 워시보드 퍼텐셜."""

    def test_zero_bias_is_cosine(self):
        """바이어스=0이면 U(φ) = -Ic cos(φ)."""
        for phi in [0, math.pi / 2, math.pi, 2 * math.pi]:
            expected = -1.0 * math.cos(phi)
            self.assertAlmostEqual(washboard_potential(phi, 0.0), expected)

    def test_tilt_with_bias(self):
        """바이어스가 있으면 퍼텐셜이 기울어져야 한다."""
        u_zero = washboard_potential(0.0, 1.0)
        u_pos = washboard_potential(2 * math.pi, 1.0)
        # 양의 바이어스 → φ 증가 방향으로 내려감
        self.assertLess(u_pos, u_zero)

    def test_symmetric_at_zero_bias(self):
        """바이어스=0이면 cos 함수의 대칭성."""
        self.assertAlmostEqual(
            washboard_potential(math.pi / 3, 0.0),
            washboard_potential(-math.pi / 3, 0.0),
        )


class TestIVCurve(unittest.TestCase):
    """iv_curve_point(I_bias) — I-V 특성."""

    def test_zero_voltage_below_ic(self):
        """I_bias ≤ Ic이면 전압이 0이어야 한다."""
        for bias in [0.0, 0.5, 0.99, 1.0]:
            self.assertAlmostEqual(iv_curve_point(bias, ic=1.0), 0.0)

    def test_finite_voltage_above_ic(self):
        """I_bias > Ic이면 전압이 0보다 커야 한다."""
        v = iv_curve_point(2.0, ic=1.0)
        self.assertGreater(v, 0.0)

    def test_negative_bias(self):
        """음의 바이어스 → 음의 전압."""
        v = iv_curve_point(-2.0, ic=1.0)
        self.assertLess(v, 0.0)

    def test_formula(self):
        """V = Rn × √(I² - Ic²) 공식 확인."""
        bias, ic, rn = 2.0, 1.0, 1.0
        expected = rn * math.sqrt(bias ** 2 - ic ** 2)
        self.assertAlmostEqual(iv_curve_point(bias, ic, rn), expected)

    def test_symmetric(self):
        """양/음 바이어스의 전압 크기가 같아야 한다."""
        v_pos = iv_curve_point(2.0, ic=1.0)
        v_neg = iv_curve_point(-2.0, ic=1.0)
        self.assertAlmostEqual(abs(v_pos), abs(v_neg))


class TestJosephsonJunction(unittest.TestCase):
    """JosephsonJunction — RCSJ 모델 시뮬레이션."""

    def test_initial_state(self):
        """초기 상태: φ=0, dφ/dt=0, V=0."""
        jj = JosephsonJunction()
        self.assertAlmostEqual(jj.phi, 0.0)
        self.assertAlmostEqual(jj.dphi, 0.0)
        self.assertAlmostEqual(jj.voltage, 0.0)
        self.assertTrue(jj.is_zero_voltage)

    def test_zero_voltage_small_bias(self):
        """작은 바이어스에서 제로 전압 상태를 유지해야 한다."""
        jj = JosephsonJunction()
        jj.set_bias(0.5)  # < Ic=1.0
        for _ in range(120):
            jj.update(1 / 60.0)
        # 충분한 시간 후에도 전압이 작아야 함
        # (감쇠가 있으므로 정상 상태에 도달)
        # 이 테스트는 근사적 — 완전한 0은 아니지만 작은 값
        self.assertLess(abs(jj.voltage), 1.0)

    def test_finite_voltage_large_bias(self):
        """큰 바이어스(>Ic)에서는 위상이 계속 변해야 한다."""
        jj = JosephsonJunction()
        jj.set_bias(2.0)  # > Ic=1.0
        for _ in range(120):
            jj.update(1 / 60.0)
        # 위상이 상당히 변했어야 함
        self.assertGreater(abs(jj.phi), 1.0)

    def test_supercurrent_property(self):
        """supercurrent = Ic × sin(φ)."""
        jj = JosephsonJunction()
        jj.phi = math.pi / 4
        expected = jj.ic * math.sin(math.pi / 4)
        self.assertAlmostEqual(jj.supercurrent, expected)

    def test_set_bias_clamped(self):
        """바이어스가 ±BIAS_MAX로 클램핑되어야 한다."""
        jj = JosephsonJunction()
        jj.set_bias(100)
        self.assertEqual(jj.bias_current, BIAS_MAX)
        jj.set_bias(-100)
        self.assertEqual(jj.bias_current, -BIAS_MAX)

    def test_reset(self):
        """리셋하면 모든 상태가 초기화되어야 한다."""
        jj = JosephsonJunction()
        jj.set_bias(2.0)
        for _ in range(60):
            jj.update(1 / 60.0)
        jj.reset()
        self.assertAlmostEqual(jj.phi, 0.0)
        self.assertAlmostEqual(jj.dphi, 0.0)
        self.assertEqual(len(jj.phi_history), 0)

    def test_history_recording(self):
        """히스토리가 기록되어야 한다."""
        jj = JosephsonJunction()
        jj.set_bias(1.5)
        for _ in range(10):
            jj.update(1 / 60.0)
        self.assertEqual(len(jj.phi_history), 10)
        self.assertEqual(len(jj.voltage_history), 10)
        self.assertEqual(len(jj.current_history), 10)

    def test_history_max_limit(self):
        """히스토리가 최대 길이를 넘지 않아야 한다."""
        jj = JosephsonJunction()
        jj.set_bias(1.5)
        for _ in range(500):
            jj.update(1 / 60.0)
        self.assertLessEqual(len(jj.phi_history), jj._history_max)

    def test_time_advances(self):
        """update 후 시간이 진행되어야 한다."""
        jj = JosephsonJunction()
        jj.update(1 / 60.0)
        self.assertGreater(jj.t, 0.0)

    def test_power(self):
        """전력 = 전압 × 바이어스."""
        jj = JosephsonJunction()
        jj.set_bias(2.0)
        for _ in range(60):
            jj.update(1 / 60.0)
        expected = jj.voltage * jj.bias_current
        self.assertAlmostEqual(jj.power, expected)

    def test_custom_ic(self):
        """커스텀 Ic로 생성 가능해야 한다."""
        jj = JosephsonJunction(ic=2.5)
        self.assertAlmostEqual(jj.ic, 2.5)


if __name__ == "__main__":
    unittest.main()
