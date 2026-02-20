"""쿠퍼 쌍 물리 엔진 단위 테스트."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from physics.cooper_pair_physics import (
    GAP_DELTA_MAX,
    TC_KELVIN,
    TEMP_MAX,
    TEMP_MIN,
    Electron,
    LatticeIon,
    LatticeSimulation,
    cooper_pair_density,
    energy_gap,
    lattice_vibration_amplitude,
    resistance_factor,
)


class TestEnergyGap(unittest.TestCase):
    """energy_gap(T) — BCS 에너지 갭 근사."""

    def test_at_zero_kelvin(self):
        """T=0K 에서 에너지 갭이 최대(Δ₀)여야 한다."""
        gap = energy_gap(0.0)
        self.assertAlmostEqual(gap, GAP_DELTA_MAX)

    def test_at_tc_zero(self):
        """T=Tc 에서 에너지 갭이 0이어야 한다."""
        gap = energy_gap(TC_KELVIN)
        self.assertAlmostEqual(gap, 0.0)

    def test_above_tc_zero(self):
        """T > Tc 에서 에너지 갭이 0이어야 한다."""
        for t in [TC_KELVIN + 1, TC_KELVIN + 50, 300]:
            self.assertAlmostEqual(energy_gap(t), 0.0, msg=f"T={t}")

    def test_monotonic_decrease(self):
        """온도가 올라가면 에너지 갭이 감소해야 한다."""
        temps = [i * 5.0 for i in range(int(TC_KELVIN // 5) + 1)]
        gaps = [energy_gap(t) for t in temps]
        for i in range(len(gaps) - 1):
            self.assertGreaterEqual(gaps[i], gaps[i + 1], f"T={temps[i]} → T={temps[i + 1]}")

    def test_always_non_negative(self):
        """에너지 갭은 항상 0 이상이어야 한다."""
        for t in range(0, 200):
            self.assertGreaterEqual(energy_gap(float(t)), 0.0)

    def test_bcs_formula(self):
        """BCS 공식 Δ₀ × √(1 - (T/Tc)²)와 일치해야 한다."""
        t = TC_KELVIN / 2
        expected = GAP_DELTA_MAX * math.sqrt(1 - (t / TC_KELVIN) ** 2)
        self.assertAlmostEqual(energy_gap(t), expected)

    def test_tc_zero_returns_zero(self):
        """Tc=0 이면 갭이 항상 0이어야 한다."""
        self.assertAlmostEqual(energy_gap(10, tc=0), 0.0)


class TestCooperPairDensity(unittest.TestCase):
    """cooper_pair_density(T) — 쿠퍼 쌍 밀도."""

    def test_at_zero_kelvin(self):
        """T=0K에서 밀도가 1.0이어야 한다."""
        self.assertAlmostEqual(cooper_pair_density(0.0), 1.0)

    def test_at_tc_zero(self):
        """T=Tc에서 밀도가 0이어야 한다."""
        self.assertAlmostEqual(cooper_pair_density(TC_KELVIN), 0.0)

    def test_above_tc_zero(self):
        """T > Tc에서 밀도가 0이어야 한다."""
        self.assertAlmostEqual(cooper_pair_density(TC_KELVIN + 10), 0.0)

    def test_between_0_and_1(self):
        """0 < T < Tc에서 밀도가 0과 1 사이여야 한다."""
        for t in [10, 30, 50, TC_KELVIN - 1]:
            d = cooper_pair_density(t)
            self.assertGreater(d, 0.0, f"T={t}")
            self.assertLessEqual(d, 1.0, f"T={t}")


class TestResistanceFactor(unittest.TestCase):
    """resistance_factor(T) — 정규화 저항."""

    def test_below_tc_zero(self):
        """T < Tc에서 저항이 0이어야 한다."""
        self.assertAlmostEqual(resistance_factor(TC_KELVIN - 1), 0.0)

    def test_at_tc_normal(self):
        """T >= Tc에서 저항이 1이어야 한다."""
        self.assertAlmostEqual(resistance_factor(TC_KELVIN), 1.0)

    def test_above_tc_normal(self):
        self.assertAlmostEqual(resistance_factor(TC_KELVIN + 50), 1.0)


class TestLatticeVibrationAmplitude(unittest.TestCase):
    """lattice_vibration_amplitude(T) — 격자 진동."""

    def test_zero_at_zero_temp(self):
        self.assertAlmostEqual(lattice_vibration_amplitude(0.0), 0.0)

    def test_max_at_max_temp(self):
        self.assertAlmostEqual(lattice_vibration_amplitude(TEMP_MAX), 1.0)

    def test_clamped(self):
        """값이 0~1 범위를 벗어나지 않아야 한다."""
        self.assertEqual(lattice_vibration_amplitude(TEMP_MAX + 100), 1.0)
        self.assertEqual(lattice_vibration_amplitude(-10), 0.0)


class TestLatticeIon(unittest.TestCase):
    """LatticeIon — 격자 이온 진동."""

    def test_initial_position(self):
        ion = LatticeIon(100.0, 200.0)
        self.assertEqual(ion.x, 100.0)
        self.assertEqual(ion.y, 200.0)

    def test_vibration_stays_near_equilibrium(self):
        """진동해도 평형점 근처에 있어야 한다."""
        ion = LatticeIon(100.0, 200.0)
        amplitude = 8.0
        for _ in range(100):
            ion.update(1 / 60.0, amplitude)
        self.assertAlmostEqual(ion.x, 100.0, delta=amplitude + 1)
        self.assertAlmostEqual(ion.y, 200.0, delta=amplitude + 1)

    def test_zero_amplitude_no_movement(self):
        """진폭 0이면 움직이지 않아야 한다."""
        ion = LatticeIon(100.0, 200.0)
        ion.update(1 / 60.0, 0.0)
        self.assertAlmostEqual(ion.x, 100.0, delta=0.001)
        self.assertAlmostEqual(ion.y, 200.0, delta=0.001)


class TestElectron(unittest.TestCase):
    """Electron — 전도 전자."""

    def test_move(self):
        e = Electron(100, 100, 60, 0)
        e.update(1.0, (0, 0, 500, 500))
        self.assertAlmostEqual(e.x, 160.0)

    def test_boundary_reflection_x(self):
        """경계에서 반사해야 한다."""
        e = Electron(490, 100, 60, 0)
        e.update(1.0, (0, 0, 500, 500))
        self.assertLessEqual(e.x, 500)
        self.assertLess(e.vx, 0)  # 방향 반전

    def test_boundary_reflection_y(self):
        e = Electron(100, 10, 0, -60)
        e.update(1.0, (0, 0, 500, 500))
        self.assertGreaterEqual(e.y, 0)
        self.assertGreater(e.vy, 0)

    def test_distance_to(self):
        e1 = Electron(0, 0, 0, 0)
        e2 = Electron(3, 4, 0, 0)
        self.assertAlmostEqual(e1.distance_to(e2), 5.0)

    def test_initial_not_paired(self):
        e = Electron(0, 0, 0, 0)
        self.assertFalse(e.paired)
        self.assertIsNone(e.partner)


class TestLatticeSimulation(unittest.TestCase):
    """LatticeSimulation — 통합 시뮬레이션."""

    def test_initial_state_normal(self):
        """초기 온도가 Tc 위이므로 정상 상태여야 한다."""
        sim = LatticeSimulation()
        self.assertFalse(sim.is_superconducting)
        self.assertAlmostEqual(sim.gap, 0.0)

    def test_superconducting_below_tc(self):
        sim = LatticeSimulation()
        sim.set_temperature(TC_KELVIN - 20)
        self.assertTrue(sim.is_superconducting)
        self.assertGreater(sim.gap, 0.0)

    def test_set_temperature_clamped(self):
        sim = LatticeSimulation()
        sim.set_temperature(-100)
        self.assertEqual(sim.temperature, TEMP_MIN)
        sim.set_temperature(9999)
        self.assertEqual(sim.temperature, TEMP_MAX)

    def test_grid_size(self):
        sim = LatticeSimulation(cols=5, rows=3)
        self.assertEqual(len(sim.ions), 15)

    def test_electron_count(self):
        sim = LatticeSimulation()
        self.assertEqual(len(sim.electrons), 12)

    def test_update_advances_time(self):
        sim = LatticeSimulation()
        sim.update(1 / 60.0)
        self.assertGreater(sim.t, 0.0)

    def test_pairing_at_low_temp(self):
        """저온에서 쿠퍼 쌍이 형성되어야 한다."""
        sim = LatticeSimulation()
        sim.set_temperature(TEMP_MIN + 1)
        # 여러 프레임 시뮬레이션
        for _ in range(60):
            sim.update(1 / 60.0)
        self.assertGreater(sim.pair_count, 0)

    def test_no_pairing_above_tc(self):
        """Tc 이상에서는 쌍이 형성되지 않아야 한다."""
        sim = LatticeSimulation()
        sim.set_temperature(TC_KELVIN + 20)
        for _ in range(60):
            sim.update(1 / 60.0)
        self.assertEqual(sim.pair_count, 0)

    def test_pair_density_property(self):
        sim = LatticeSimulation()
        sim.set_temperature(TC_KELVIN / 2)
        self.assertGreater(sim.pair_density, 0.0)
        self.assertLessEqual(sim.pair_density, 1.0)


if __name__ == "__main__":
    unittest.main()
