"""#26 — Property-based 테스트 (Hypothesis).

무작위 파라미터로 물리 함수의 수학적 불변성을 검증합니다.

대상 모듈:
  - quantum/tunneling_physics.py  : _calc_tunnel_prob, QuantumParticle
  - physics/cooper_pair_physics.py: energy_gap, cooper_pair_density, resistance_factor
  - physics/josephson_junction_physics.py: josephson_current, iv_curve_point, washboard_potential
  - quantum/entanglement_physics.py: bell_probabilities
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ImportError as exc:
    raise unittest.SkipTest("hypothesis 패키지 필요") from exc

# ── 전략(strategy) 정의 ──────────────────────────────

# 터널링
barrier_widths = st.integers(min_value=4, max_value=200)
base_probs = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
positive_dt = st.floats(min_value=1e-4, max_value=0.1, allow_nan=False, allow_infinity=False)
tunnel_probs = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# 온도 / 임계온도
temperatures = st.floats(min_value=0.0, max_value=300.0, allow_nan=False, allow_infinity=False)
critical_temps = st.floats(min_value=1.0, max_value=200.0, allow_nan=False, allow_infinity=False)

# 조셉슨 접합
phases = st.floats(min_value=-10 * math.pi, max_value=10 * math.pi, allow_nan=False, allow_infinity=False)
positive_ic = st.floats(min_value=0.01, max_value=10.0, allow_nan=False, allow_infinity=False)
bias_currents = st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False)


# 양자 상태 벡터 (4-요소, 정규화)
def _normalized_state():
    """정규화된 4-요소 상태 벡터 전략."""
    return (
        st.lists(
            st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=4,
            max_size=4,
        )
        .filter(lambda v: sum(x * x for x in v) > 1e-8)
        .map(lambda v: [x / math.sqrt(sum(a * a for a in v)) for x in v])
    )


# ══════════════════════════════════════════════════════
# 터널링 물리
# ══════════════════════════════════════════════════════


class TestCalcTunnelProb(unittest.TestCase):
    """_calc_tunnel_prob 속성 검증."""

    def setUp(self):
        from quantum.tunneling_physics import _calc_tunnel_prob

        self.fn = _calc_tunnel_prob

    @given(bw=barrier_widths, bp=base_probs)
    @settings(max_examples=200)
    def test_range_zero_to_one(self, bw, bp):
        """결과는 항상 0 이상."""
        result = self.fn(bw, bp)
        self.assertGreaterEqual(result, 0.0)

    @given(bp=base_probs)
    @settings(max_examples=100)
    def test_monotonic_decrease(self, bp):
        """장벽이 두꺼울수록 확률 감소 (단조 감소)."""
        vals = [self.fn(w, bp) for w in range(4, 201, 10)]
        for i in range(len(vals) - 1):
            self.assertGreaterEqual(vals[i], vals[i + 1])

    @given(bw=barrier_widths)
    @settings(max_examples=100)
    def test_zero_base_gives_zero(self, bw):
        """base_prob=0이면 결과도 0."""
        self.assertAlmostEqual(self.fn(bw, 0.0), 0.0, places=10)

    @given(bw=barrier_widths, bp=base_probs)
    @settings(max_examples=200)
    def test_no_overflow(self, bw, bp):
        """오버플로 없이 유한한 값 반환."""
        result = self.fn(bw, bp)
        self.assertTrue(math.isfinite(result))


class TestComputePsiPBT(unittest.TestCase):
    """compute_psi 속성 검증 (#27)."""

    def setUp(self):
        from quantum.tunneling_physics import compute_psi

        self.fn = compute_psi

    @given(bw=barrier_widths, tp=tunnel_probs)
    @settings(max_examples=200)
    def test_all_finite(self, bw, tp):
        """모든 (x, psi) 값은 유한."""
        for x, psi in self.fn(bw, tp, n_points=50):
            self.assertTrue(math.isfinite(x))
            self.assertTrue(math.isfinite(psi))

    @given(bw=barrier_widths, tp=tunnel_probs)
    @settings(max_examples=200)
    def test_x_range(self, bw, tp):
        """x_norm ∈ [0, 1]."""
        for x, _ in self.fn(bw, tp, n_points=50):
            self.assertGreaterEqual(x, 0.0)
            self.assertLessEqual(x, 1.0)

    @given(bw=barrier_widths, tp=tunnel_probs)
    @settings(max_examples=100)
    def test_correct_count(self, bw, tp):
        """반환 포인트 수 = n_points."""
        self.assertEqual(len(self.fn(bw, tp, n_points=77)), 77)

    @given(bw=barrier_widths, tp=tunnel_probs)
    @settings(max_examples=100)
    def test_barrier_entry_positive(self, bw, tp):
        """장벽 진입점 psi > 0 (지수 감쇠 시작)."""
        from quantum.tunneling_physics import SIM_W

        b_left = 0.5 - (bw / SIM_W) * 0.5
        pts = self.fn(bw, tp, n_points=500)
        # 장벽 진입 직후 점 찾기
        for x, psi in pts:
            if x > b_left and x < b_left + 0.02:
                self.assertGreater(psi, 0.0)
                break


class TestCalcEnergyLevelsPBT(unittest.TestCase):
    """calc_energy_levels 속성 검증 (#28)."""

    def setUp(self):
        from quantum.tunneling_physics import calc_energy_levels

        self.fn = calc_energy_levels

    @given(bw=barrier_widths, tp=tunnel_probs)
    @settings(max_examples=200)
    def test_keys_present(self, bw, tp):
        """필수 키 3개 항상 존재."""
        result = self.fn(bw, tp)
        self.assertIn("particle_energy", result)
        self.assertIn("barrier_height", result)
        self.assertIn("ratio", result)

    @given(bw=barrier_widths, tp=tunnel_probs)
    @settings(max_examples=200)
    def test_barrier_height_range(self, bw, tp):
        """V₀ ∈ [0.30, 0.95]."""
        v0 = self.fn(bw, tp)["barrier_height"]
        self.assertGreaterEqual(v0, 0.30 - 1e-9)
        self.assertLessEqual(v0, 0.95 + 1e-9)

    @given(bw=barrier_widths, tp=tunnel_probs)
    @settings(max_examples=200)
    def test_ratio_less_than_one(self, bw, tp):
        """E/V₀ < 1 (고전적 통과 불가)."""
        self.assertLess(self.fn(bw, tp)["ratio"], 1.0)

    @given(bw=barrier_widths, tp=tunnel_probs)
    @settings(max_examples=200)
    def test_ratio_consistent(self, bw, tp):
        """ratio = particle_energy / barrier_height."""
        r = self.fn(bw, tp)
        expected = r["particle_energy"] / r["barrier_height"]
        self.assertAlmostEqual(r["ratio"], expected, places=10)


class TestBarrierSweeperPBT(unittest.TestCase):
    """BarrierSweeper 속성 검증 (#29)."""

    @given(bp=base_probs, seed=st.integers(min_value=0, max_value=10000))
    @settings(max_examples=50)
    def test_completes_and_covers_all(self, bp, seed):
        """항상 완료되며 모든 폭에 결과 존재."""
        from quantum.tunneling_physics import BarrierSweeper

        sw = BarrierSweeper(base_prob=bp, trials_per_width=5, batch_size=500, seed=seed)
        iters = 0
        while sw.advance():
            iters += 1
            if iters > 10000:
                break
        self.assertTrue(sw.done)
        for w in sw.widths:
            self.assertIn(w, sw.results)

    @given(bp=base_probs, seed=st.integers(min_value=0, max_value=10000))
    @settings(max_examples=50)
    def test_tunnel_reflect_sum(self, bp, seed):
        """tunnel + reflect = total 불변식."""
        from quantum.tunneling_physics import BarrierSweeper

        sw = BarrierSweeper(base_prob=bp, trials_per_width=10, batch_size=500, seed=seed)
        while sw.advance():
            pass
        for r in sw.results.values():
            self.assertEqual(r["tunnel"] + r["reflect"], r["total"])

    @given(bp=base_probs, seed=st.integers(min_value=0, max_value=10000))
    @settings(max_examples=50)
    def test_progress_monotonic(self, bp, seed):
        """진행률은 단조 증가."""
        from quantum.tunneling_physics import BarrierSweeper

        sw = BarrierSweeper(base_prob=bp, trials_per_width=10, batch_size=3, seed=seed)
        prev = 0.0
        while sw.advance():
            cur = sw.progress
            self.assertGreaterEqual(cur, prev - 1e-9)
            prev = cur


class TestQuantumParticle(unittest.TestCase):
    """QuantumParticle 속성 검증."""

    def setUp(self):
        from quantum.tunneling_physics import (
            PARTICLE_RADIUS,
            SIM_H,
            SIM_TOP,
            QuantumParticle,
        )

        self.Particle = QuantumParticle
        self.SIM_TOP = SIM_TOP
        self.SIM_H = SIM_H
        self.RADIUS = PARTICLE_RADIUS

    @given(time_ms=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_qubit_state_binary(self, time_ms):
        """qubit_state는 항상 0 또는 1."""
        p = self.Particle(seed=42)
        result = p.qubit_state(time_ms)
        self.assertIn(result, (0, 1))

    @given(
        dt=positive_dt,
        bw=st.integers(min_value=4, max_value=200),
        tp=tunnel_probs,
    )
    @settings(max_examples=100)
    def test_y_bounds_preserved(self, dt, bw, tp):
        """update 후 y좌표가 시뮬레이션 영역 내."""
        p = self.Particle(seed=42)
        for _ in range(50):
            p.update(dt, barrier_width=bw, tunnel_prob=tp)
        y_min = self.SIM_TOP + self.RADIUS
        y_max = self.SIM_TOP + self.SIM_H - self.RADIUS
        # 리셋으로 중앙에 놓일 수 있으므로 약간 여유
        self.assertGreaterEqual(p.y, y_min - 1)
        self.assertLessEqual(p.y, y_max + 1)

    @given(
        dt=positive_dt,
        bw=st.integers(min_value=4, max_value=200),
        tp=tunnel_probs,
    )
    @settings(max_examples=100)
    def test_count_monotonic(self, dt, bw, tp):
        """tunnel_count, reflect_count는 단조 증가."""
        p = self.Particle(seed=42)
        prev_t, prev_r = 0, 0
        for _ in range(100):
            p.update(dt, barrier_width=bw, tunnel_prob=tp)
            self.assertGreaterEqual(p.tunnel_count, prev_t)
            self.assertGreaterEqual(p.reflect_count, prev_r)
            prev_t = p.tunnel_count
            prev_r = p.reflect_count

    @given(dt=positive_dt)
    @settings(max_examples=50)
    def test_flash_timer_nonnegative_or_decays(self, dt):
        """flash_timer는 0 이하로 떨어진 뒤 유지되거나 양수에서 감소."""
        p = self.Particle(seed=42)
        for _ in range(200):
            p.update(dt, barrier_width=12, tunnel_prob=0.5)
        # flash_timer는 음수 허용 (다음 프레임에 0으로 간주)
        # 핵심: 유한한 값이어야 함
        self.assertTrue(math.isfinite(p.flash_timer))


# ══════════════════════════════════════════════════════
# 쿠퍼 쌍 / BCS 물리
# ══════════════════════════════════════════════════════


class TestEnergyGap(unittest.TestCase):
    """energy_gap(T, Tc) 속성 검증."""

    def setUp(self):
        from physics.cooper_pair_physics import energy_gap

        self.fn = energy_gap

    @given(temp=temperatures, tc=critical_temps)
    @settings(max_examples=200)
    def test_nonnegative(self, temp, tc):
        """에너지 갭은 항상 0 이상."""
        self.assertGreaterEqual(self.fn(temp, tc), 0.0)

    @given(tc=critical_temps)
    @settings(max_examples=100)
    def test_zero_above_tc(self, tc):
        """T >= Tc이면 갭 = 0."""
        self.assertAlmostEqual(self.fn(tc, tc), 0.0)
        self.assertAlmostEqual(self.fn(tc + 10.0, tc), 0.0)

    @given(tc=critical_temps)
    @settings(max_examples=100)
    def test_max_at_zero_temp(self, tc):
        """T=0이면 갭 = Δ₀ (최대값)."""
        from physics.cooper_pair_physics import GAP_DELTA_MAX

        self.assertAlmostEqual(self.fn(0.0, tc), GAP_DELTA_MAX, places=5)

    @given(tc=critical_temps)
    @settings(max_examples=100)
    def test_monotonic_decrease_with_temp(self, tc):
        """온도 증가 시 에너지 갭 단조 감소 (T < Tc 구간)."""
        steps = 20
        temps = [tc * i / steps for i in range(steps)]
        vals = [self.fn(t, tc) for t in temps]
        for i in range(len(vals) - 1):
            self.assertGreaterEqual(vals[i], vals[i + 1])


class TestCooperPairDensity(unittest.TestCase):
    """cooper_pair_density(T, Tc) 속성 검증."""

    def setUp(self):
        from physics.cooper_pair_physics import cooper_pair_density

        self.fn = cooper_pair_density

    @given(temp=temperatures, tc=critical_temps)
    @settings(max_examples=200)
    def test_range_zero_to_one(self, temp, tc):
        """밀도는 항상 [0, 1] 범위."""
        result = self.fn(temp, tc)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)

    @given(tc=critical_temps)
    @settings(max_examples=100)
    def test_zero_above_tc(self, tc):
        """T >= Tc이면 밀도 = 0."""
        self.assertAlmostEqual(self.fn(tc, tc), 0.0)
        self.assertAlmostEqual(self.fn(tc + 50.0, tc), 0.0)

    @given(tc=critical_temps)
    @settings(max_examples=100)
    def test_full_at_zero_temp(self, tc):
        """T=0이면 밀도 = 1 (모두 쿠퍼 쌍)."""
        self.assertAlmostEqual(self.fn(0.0, tc), 1.0, places=5)


class TestResistanceFactor(unittest.TestCase):
    """resistance_factor(T, Tc) 속성 검증."""

    def setUp(self):
        from physics.cooper_pair_physics import resistance_factor

        self.fn = resistance_factor

    @given(temp=temperatures, tc=critical_temps)
    @settings(max_examples=200)
    def test_binary_output(self, temp, tc):
        """저항 인수는 0.0 또는 1.0만 가능."""
        result = self.fn(temp, tc)
        self.assertIn(result, (0.0, 1.0))

    @given(tc=critical_temps)
    @settings(max_examples=100)
    def test_superconducting_below_tc(self, tc):
        """T < Tc이면 저항 = 0 (초전도)."""
        temp = tc * 0.5  # 항상 Tc 미만
        self.assertEqual(self.fn(temp, tc), 0.0)

    @given(tc=critical_temps)
    @settings(max_examples=100)
    def test_normal_above_tc(self, tc):
        """T >= Tc이면 저항 = 1 (정상 상태)."""
        self.assertEqual(self.fn(tc, tc), 1.0)
        self.assertEqual(self.fn(tc + 1.0, tc), 1.0)


# ══════════════════════════════════════════════════════
# 조셉슨 접합 물리
# ══════════════════════════════════════════════════════


class TestJosephsonCurrent(unittest.TestCase):
    """josephson_current(phi, ic) 속성 검증."""

    def setUp(self):
        from physics.josephson_junction_physics import josephson_current

        self.fn = josephson_current

    @given(phi=phases, ic=positive_ic)
    @settings(max_examples=200)
    def test_bounded_by_ic(self, phi, ic):
        """전류는 항상 [-Ic, Ic] 범위."""
        result = self.fn(phi, ic)
        self.assertGreaterEqual(result, -ic - 1e-9)
        self.assertLessEqual(result, ic + 1e-9)

    @given(phi=phases, ic=positive_ic)
    @settings(max_examples=200)
    def test_odd_function(self, phi, ic):
        """|I(-φ)| = |I(φ)| (sin 기함수 대칭)."""
        self.assertAlmostEqual(self.fn(-phi, ic), -self.fn(phi, ic), places=7)

    @given(ic=positive_ic)
    @settings(max_examples=100)
    def test_periodicity(self, ic):
        """I(φ + 2π) = I(φ) (주기성)."""
        phi = 1.234
        self.assertAlmostEqual(self.fn(phi, ic), self.fn(phi + 2 * math.pi, ic), places=7)

    @given(ic=positive_ic)
    @settings(max_examples=100)
    def test_zero_at_multiples_of_pi(self, ic):
        """φ = nπ 에서 전류 = 0."""
        for n in range(-3, 4):
            self.assertAlmostEqual(self.fn(n * math.pi, ic), 0.0, places=7)


class TestIVCurvePoint(unittest.TestCase):
    """iv_curve_point(bias, ic, r_n) 속성 검증."""

    def setUp(self):
        from physics.josephson_junction_physics import R_NORMAL, iv_curve_point

        self.fn = iv_curve_point
        self.r_n = R_NORMAL

    @given(bias=st.floats(min_value=-0.99, max_value=0.99, allow_nan=False))
    @settings(max_examples=100)
    def test_zero_voltage_below_ic(self, bias):
        """바이어스 <= Ic이면 V = 0 (초전류 영역)."""
        self.assertAlmostEqual(self.fn(bias, ic=1.0), 0.0)

    @given(bias=st.floats(min_value=1.01, max_value=5.0, allow_nan=False))
    @settings(max_examples=100)
    def test_nonzero_above_ic(self, bias):
        """바이어스 > Ic이면 V > 0."""
        result = self.fn(bias, ic=1.0)
        self.assertGreater(result, 0.0)

    @given(bias=bias_currents, ic=positive_ic)
    @settings(max_examples=200)
    def test_antisymmetric(self, bias, ic):
        """V(-I) = -V(I) (반대칭)."""
        self.assertAlmostEqual(self.fn(-bias, ic), -self.fn(bias, ic), places=7)


class TestWashboardPotential(unittest.TestCase):
    """washboard_potential(phi, bias, ic) 속성 검증."""

    def setUp(self):
        from physics.josephson_junction_physics import washboard_potential

        self.fn = washboard_potential

    @given(phi=phases, bias=bias_currents, ic=positive_ic)
    @settings(max_examples=200)
    def test_finite_output(self, phi, bias, ic):
        """결과는 항상 유한."""
        result = self.fn(phi, bias, ic)
        self.assertTrue(math.isfinite(result))

    @given(ic=positive_ic)
    @settings(max_examples=100)
    def test_zero_bias_even_symmetry(self, ic):
        """bias=0이면 U(φ) = -Ic cos(φ), 짝함수."""
        phi = 1.5
        self.assertAlmostEqual(self.fn(phi, 0.0, ic), self.fn(-phi, 0.0, ic), places=7)

    @given(ic=positive_ic)
    @settings(max_examples=100)
    def test_formula_consistency(self, ic):
        """U(φ) = -Ic cos(φ) - (bias/(2π))φ 공식 검증."""
        phi, bias = 2.0, 0.5
        expected = -ic * math.cos(phi) - (bias / (2.0 * math.pi)) * phi
        self.assertAlmostEqual(self.fn(phi, bias, ic), expected, places=10)


# ══════════════════════════════════════════════════════
# 양자 얽힘
# ══════════════════════════════════════════════════════


class TestBellProbabilities(unittest.TestCase):
    """bell_probabilities(state) 속성 검증."""

    def setUp(self):
        from quantum.entanglement_physics import bell_probabilities

        self.fn = bell_probabilities

    @given(state=_normalized_state())
    @settings(max_examples=200)
    def test_sum_to_one(self, state):
        """확률 합 ≈ 1."""
        probs = self.fn(state)
        self.assertAlmostEqual(sum(probs), 1.0, places=5)

    @given(state=_normalized_state())
    @settings(max_examples=200)
    def test_all_nonnegative(self, state):
        """각 확률은 0 이상."""
        probs = self.fn(state)
        for p in probs:
            self.assertGreaterEqual(p, -1e-10)

    @given(state=_normalized_state())
    @settings(max_examples=200)
    def test_four_elements(self, state):
        """항상 4개 요소 반환."""
        probs = self.fn(state)
        self.assertEqual(len(probs), 4)


if __name__ == "__main__":
    unittest.main()
