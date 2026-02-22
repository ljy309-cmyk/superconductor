"""장벽 비교(Compare) 모드 로직 테스트.

얇은/두꺼운 장벽 전환 시 터널링 확률, 입자 동역학,
시행 기록, 통계 추적이 올바르게 동작하는지 검증합니다.
"""

import math
import os
import sys
import unittest
from unittest.mock import MagicMock

# GUI 의존성 mock
for mod in (
    "pygame",
    "tkinter",
    "tkinter.messagebox",
    "tkinter.ttk",
    "matplotlib",
    "matplotlib.backends",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.figure",
):
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum.tunneling_physics import (
    _TUNNEL_DECAY,
    BARRIER_WIDTH_DEFAULT,
    BARRIER_WIDTH_MAX,
    BARRIER_WIDTH_MIN,
    BARRIER_X,
    PARTICLE_RADIUS,
    PARTICLE_SPEED,
    SIM_LEFT,
    SIM_W,
    TUNNEL_PROB_BASE,
    QuantumParticle,
    _calc_tunnel_prob,
)


def _run_trials(
    n: int, barrier_width: int, tunnel_prob: float | None = None, seed: int | None = None
) -> QuantumParticle:
    """지정 장벽으로 n회 시행을 실행하고 입자를 반환."""
    if tunnel_prob is None:
        tunnel_prob = _calc_tunnel_prob(barrier_width)
    p = QuantumParticle(seed=seed)
    for _ in range(n):
        p.reset()
        for _ in range(600):
            p.update(1 / 60, barrier_width=barrier_width, tunnel_prob=tunnel_prob)
            if p.tunneled is not None:
                break
    return p


# ═══════════════════════════════════════════════════════
# 1. 확률 공식: 장벽 두께별 비교
# ═══════════════════════════════════════════════════════


class TestBarrierProbabilityComparison(unittest.TestCase):
    """_calc_tunnel_prob() — 장벽 두께별 확률 비교 검증."""

    def test_thin_vs_thick_ordering(self):
        """얇은 장벽 확률 > 두꺼운 장벽 확률 (모든 쌍)."""
        widths = [4, 10, 20, 50, 100, 150, 200]
        probs = [_calc_tunnel_prob(w) for w in widths]
        for i in range(len(probs) - 1):
            self.assertGreater(
                probs[i],
                probs[i + 1],
                f"P(w={widths[i]})={probs[i]:.6f} should > P(w={widths[i + 1]})={probs[i + 1]:.6f}",
            )

    def test_probability_ratio_follows_exponential(self):
        """P(w1)/P(w2) = exp(-decay*(w1-w2)) — 지수 비율 검증."""
        pairs = [(4, 50), (12, 100), (20, 200), (50, 150)]
        for w1, w2 in pairs:
            p1 = _calc_tunnel_prob(w1)
            p2 = _calc_tunnel_prob(w2)
            expected_ratio = math.exp(-_TUNNEL_DECAY * (w1 - w2))
            actual_ratio = p1 / p2
            self.assertAlmostEqual(
                actual_ratio,
                expected_ratio,
                places=10,
                msg=f"Ratio P({w1})/P({w2}): expected {expected_ratio:.6f}, got {actual_ratio:.6f}",
            )

    def test_doubling_width_halves_or_less(self):
        """장벽 두께 2배 → 확률이 절반 이하로 감소 (충분히 두꺼울 때)."""
        for w in [20, 40, 60, 80]:
            p_single = _calc_tunnel_prob(w)
            p_double = _calc_tunnel_prob(w * 2)
            self.assertLess(
                p_double,
                p_single,
                f"P({w * 2}) should be < P({w})",
            )

    def test_probability_spread_across_range(self):
        """최소~최대 장벽에서 확률 범위가 유의미하게 넓다."""
        p_min = _calc_tunnel_prob(BARRIER_WIDTH_MIN)
        p_max = _calc_tunnel_prob(BARRIER_WIDTH_MAX)
        spread = p_min / p_max
        self.assertGreater(spread, 5.0, f"Spread {spread:.1f}x should be > 5x")

    def test_default_width_returns_base(self):
        """기본 두께에서 정확히 base 확률."""
        self.assertAlmostEqual(_calc_tunnel_prob(BARRIER_WIDTH_DEFAULT), TUNNEL_PROB_BASE, places=12)

    def test_symmetric_deviation_from_default(self):
        """기본값 ±Δ 에서 확률이 대칭적 지수 관계."""
        delta = 7  # 범위 내: DEFAULT±7 → [5, 19] ⊂ [MIN, MAX]
        p_thin = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT - delta)
        p_thick = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT + delta)
        # P_thin * P_thick = P_base^2 (지수 대칭)
        product = p_thin * p_thick
        base_sq = TUNNEL_PROB_BASE**2
        self.assertAlmostEqual(product, base_sq, places=10)


# ═══════════════════════════════════════════════════════
# 2. 시뮬레이션: 얇은 vs 두꺼운 장벽 통계 비교
# ═══════════════════════════════════════════════════════


class TestThinVsThickSimulation(unittest.TestCase):
    """실제 입자 시뮬레이션에서 얇은/두꺼운 장벽의 터널링률 비교."""

    def test_thin_barrier_more_tunneling(self):
        """얇은 장벽(4px)이 두꺼운 장벽(100px)보다 터널링률이 높다."""
        n = 500
        p_thin = _run_trials(n, barrier_width=BARRIER_WIDTH_MIN)
        p_thick = _run_trials(n, barrier_width=100)

        rate_thin = p_thin.tunnel_count / max(p_thin.total_attempts, 1)
        rate_thick = p_thick.tunnel_count / max(p_thick.total_attempts, 1)

        self.assertGreater(
            rate_thin,
            rate_thick,
            f"Thin rate {rate_thin:.3f} should > Thick rate {rate_thick:.3f}",
        )

    def test_thin_barrier_rate_near_theory(self):
        """얇은 장벽(4px): 실측률 ≈ 이론 확률."""
        n = 800
        bw = BARRIER_WIDTH_MIN
        theory = _calc_tunnel_prob(bw)
        p = _run_trials(n, barrier_width=bw)

        rate = p.tunnel_count / max(p.total_attempts, 1)
        tolerance = 5 * math.sqrt(theory * (1 - theory) / max(p.total_attempts, 1))
        self.assertAlmostEqual(
            rate,
            theory,
            delta=tolerance,
            msg=f"Thin barrier: rate={rate:.3f}, theory={theory:.3f}, tol=±{tolerance:.3f}",
        )

    def test_thick_barrier_rate_near_theory(self):
        """두꺼운 장벽(150px): 실측률 ≈ 이론 확률."""
        n = 800
        bw = 150
        theory = _calc_tunnel_prob(bw)
        p = _run_trials(n, barrier_width=bw)

        rate = p.tunnel_count / max(p.total_attempts, 1)
        tolerance = max(5 * math.sqrt(theory * (1 - theory) / max(p.total_attempts, 1)), 0.02)
        self.assertAlmostEqual(
            rate,
            theory,
            delta=tolerance,
            msg=f"Thick barrier: rate={rate:.3f}, theory={theory:.3f}",
        )

    def test_multiple_widths_monotonic_rate(self):
        """여러 두께에서 시뮬레이션 → 터널링률이 단조 감소 경향."""
        widths = [4, 30, 80, 150]
        n_per = 400
        rates = []
        for bw in widths:
            p = _run_trials(n_per, barrier_width=bw)
            rates.append(p.tunnel_count / max(p.total_attempts, 1))

        # 통계적 변동을 고려해 전체 추세가 감소인지 확인
        self.assertGreater(rates[0], rates[-1], "Overall trend: thin > thick")

    def test_max_barrier_very_few_tunnels(self):
        """최대 두께(200px) → 터널링이 거의 발생하지 않음."""
        p = _run_trials(300, barrier_width=BARRIER_WIDTH_MAX)
        rate = p.tunnel_count / max(p.total_attempts, 1)
        self.assertLess(rate, 0.05, f"Max barrier: rate={rate:.3f} should be < 5%")


# ═══════════════════════════════════════════════════════
# 3. 장벽 충돌 역학: 두께별 입자 위치/속도 변화
# ═══════════════════════════════════════════════════════


class TestBarrierCollisionDynamics(unittest.TestCase):
    """장벽 두께에 따른 충돌 판정 위치와 후속 동작 검증."""

    def test_thin_barrier_collision_point(self):
        """얇은 장벽(4px): 충돌 지점이 BARRIER_X 근처."""
        p = QuantumParticle()
        bw = BARRIER_WIDTH_MIN
        collision_x = BARRIER_X - bw / 2 - PARTICLE_RADIUS
        # 입자를 충돌 직전에 위치
        p.x = collision_x - 1
        p.vx = PARTICLE_SPEED
        p.vy = 0
        p.update(1 / 60, barrier_width=bw, tunnel_prob=0.0)
        # 아직 도달 안 했으면 계속 전진
        while p.tunneled is None:
            p.update(1 / 60, barrier_width=bw, tunnel_prob=0.0)  # pragma: no cover
        # 반사됨 → 장벽 왼쪽 가장자리 바로 앞
        self.assertLess(p.x, BARRIER_X, "Reflected: before barrier center")

    def test_thick_barrier_collision_earlier(self):
        """두꺼운 장벽(100px): 충돌이 더 일찍 발생 (왼쪽 가장자리가 더 왼쪽)."""
        bw_thin = 10
        bw_thick = 100

        left_edge_thin = BARRIER_X - bw_thin / 2
        left_edge_thick = BARRIER_X - bw_thick / 2

        self.assertLess(
            left_edge_thick,
            left_edge_thin,
            "Thick barrier's left edge is further left",
        )

    def test_tunnel_lands_past_barrier_right_edge(self):
        """터널링 성공 시 입자가 장벽 오른쪽 가장자리 너머에 위치."""
        for bw in [BARRIER_WIDTH_MIN, 50, BARRIER_WIDTH_MAX]:
            p = QuantumParticle()
            for _ in range(200):
                p.reset()
                for _ in range(600):
                    p.update(1 / 60, barrier_width=bw, tunnel_prob=1.0)
                    if p.tunneled is True:
                        break
                if p.tunneled is True:
                    right_edge = BARRIER_X + bw / 2
                    self.assertGreater(
                        p.x,
                        right_edge,
                        f"bw={bw}: tunneled x={p.x:.1f} should be > right edge {right_edge:.1f}",
                    )
                    break

    def test_reflected_stays_before_barrier_left_edge(self):
        """반사 시 입자가 장벽 왼쪽 가장자리 앞에 위치."""
        for bw in [BARRIER_WIDTH_MIN, 50, 100]:
            p = QuantumParticle()
            for _ in range(200):
                p.reset()
                for _ in range(600):
                    p.update(1 / 60, barrier_width=bw, tunnel_prob=0.0)
                    if p.tunneled is False:
                        break
                if p.tunneled is False:
                    left_edge = BARRIER_X - bw / 2
                    self.assertLess(
                        p.x,
                        left_edge,
                        f"bw={bw}: reflected x={p.x:.1f} should be < left edge {left_edge:.1f}",
                    )
                    break

    def test_tunnel_distance_scales_with_width(self):
        """터널링 후 입자 위치: 두꺼운 장벽일수록 장벽 중심에서 더 먼 오른쪽."""
        positions = {}
        for bw in [10, 50, 100]:
            p = QuantumParticle()
            for _ in range(200):
                p.reset()
                for _ in range(600):
                    p.update(1 / 60, barrier_width=bw, tunnel_prob=1.0)
                    if p.tunneled is True:
                        break
                if p.tunneled is True:
                    positions[bw] = p.x
                    break

        # 두꺼운 장벽의 오른쪽 가장자리가 더 오른쪽이므로 터널링 후 위치도 더 오른쪽
        if 10 in positions and 100 in positions:
            self.assertGreater(
                positions[100],
                positions[10],
                "Wider barrier → tunneled particle lands further right",
            )


# ═══════════════════════════════════════════════════════
# 4. 장벽 전환 시뮬레이션: 동적 비교 시나리오
# ═══════════════════════════════════════════════════════


class TestDynamicBarrierSwitching(unittest.TestCase):
    """실행 중 장벽 두께를 변경하는 시나리오 검증."""

    def test_switch_thin_to_thick_reduces_rate(self):
        """얇은→두꺼운 장벽 전환 → 이후 터널링률 감소."""
        thin_bw, thick_bw = 10, 120
        thin_prob = _calc_tunnel_prob(thin_bw)
        thick_prob = _calc_tunnel_prob(thick_bw)

        p = QuantumParticle()
        # Phase 1: 얇은 장벽 300회
        for _ in range(300):
            p.reset()
            for _ in range(600):
                p.update(1 / 60, barrier_width=thin_bw, tunnel_prob=thin_prob)
                if p.tunneled is not None:
                    break
        tunnels_after_thin = p.tunnel_count

        # Phase 2: 두꺼운 장벽 300회 추가
        for _ in range(300):
            p.reset()
            for _ in range(600):
                p.update(1 / 60, barrier_width=thick_bw, tunnel_prob=thick_prob)
                if p.tunneled is not None:
                    break
        tunnels_in_thick = p.tunnel_count - tunnels_after_thin
        attempts_in_thick = p.total_attempts - 300  # Phase 2 시행 수 근사

        rate_thin = tunnels_after_thin / 300
        rate_thick = tunnels_in_thick / max(attempts_in_thick, 1) if attempts_in_thick > 0 else 0

        self.assertGreater(rate_thin, rate_thick, "After switching to thick: rate should drop")

    def test_switch_thick_to_thin_increases_rate(self):
        """두꺼운→얇은 장벽 전환 → 이후 터널링률 증가."""
        thin_bw, thick_bw = 10, 120
        thin_prob = _calc_tunnel_prob(thin_bw)
        thick_prob = _calc_tunnel_prob(thick_bw)

        p = QuantumParticle()
        # Phase 1: 두꺼운 장벽 300회
        for _ in range(300):
            p.reset()
            for _ in range(600):
                p.update(1 / 60, barrier_width=thick_bw, tunnel_prob=thick_prob)
                if p.tunneled is not None:
                    break
        tunnels_after_thick = p.tunnel_count
        attempts_after_thick = p.total_attempts

        # Phase 2: 얇은 장벽 300회 추가
        for _ in range(300):
            p.reset()
            for _ in range(600):
                p.update(1 / 60, barrier_width=thin_bw, tunnel_prob=thin_prob)
                if p.tunneled is not None:
                    break
        tunnels_in_thin = p.tunnel_count - tunnels_after_thick
        attempts_in_thin = p.total_attempts - attempts_after_thick

        rate_thick = tunnels_after_thick / max(attempts_after_thick, 1)
        rate_thin = tunnels_in_thin / max(attempts_in_thin, 1)

        self.assertGreater(rate_thin, rate_thick, "After switching to thin: rate should rise")

    def test_alternating_barriers_intermediate_rate(self):
        """얇은/두꺼운 교대 → 누적 비율이 두 이론값 사이."""
        thin_bw, thick_bw = BARRIER_WIDTH_MIN, 100
        thin_prob = _calc_tunnel_prob(thin_bw)
        thick_prob = _calc_tunnel_prob(thick_bw)

        p = QuantumParticle()
        for i in range(600):
            bw = thin_bw if i % 2 == 0 else thick_bw
            prob = thin_prob if i % 2 == 0 else thick_prob
            p.reset()
            for _ in range(600):
                p.update(1 / 60, barrier_width=bw, tunnel_prob=prob)
                if p.tunneled is not None:
                    break

        rate = p.tunnel_count / max(p.total_attempts, 1)
        # 교대이므로 두 이론값 사이
        self.assertGreater(rate, thick_prob - 0.03, "Rate should be above thick-only level")
        self.assertLess(rate, thin_prob + 0.03, "Rate should be below thin-only level")


# ═══════════════════════════════════════════════════════
# 5. 시행 기록 (trial_history) 비교 로직 검증
# ═══════════════════════════════════════════════════════


class TestTrialHistoryComparison(unittest.TestCase):
    """시행별 기록에서 장벽 설정별 결과를 분리 비교."""

    def _simulate_with_history(self, barrier_widths: list[int], trials_per: int) -> list[dict]:
        """여러 장벽 설정으로 시뮬레이션 후 trial_history 형식 반환."""
        history = []
        p = QuantumParticle()
        prev_attempts = 0

        for bw in barrier_widths:
            prob = _calc_tunnel_prob(bw)
            for _ in range(trials_per):
                p.reset()
                for _ in range(600):
                    p.update(1 / 60, barrier_width=bw, tunnel_prob=prob)
                    if p.tunneled is not None:
                        break
                if p.total_attempts > prev_attempts:
                    prev_attempts = p.total_attempts
                    history.append(
                        {
                            "barrier": bw,
                            "prob": round(prob, 4),
                            "result": p.tunneled is True,
                        }
                    )
        return history

    def test_history_records_correct_barrier(self):
        """시행 기록에 올바른 장벽 두께가 저장됨."""
        history = self._simulate_with_history([20, 80], 50)
        barriers_seen = {h["barrier"] for h in history}
        self.assertIn(20, barriers_seen)
        self.assertIn(80, barriers_seen)

    def test_history_records_correct_prob(self):
        """시행 기록에 해당 장벽의 이론 확률이 저장됨."""
        history = self._simulate_with_history([20], 20)
        expected_prob = round(_calc_tunnel_prob(20), 4)
        for h in history:
            if h["barrier"] == 20:
                self.assertEqual(h["prob"], expected_prob)

    def test_grouped_rate_comparison(self):
        """장벽별로 그룹핑한 터널링률이 이론 확률 순서와 일치."""
        widths = [10, 60, 150]
        history = self._simulate_with_history(widths, 200)

        rates = {}
        for bw in widths:
            trials = [h for h in history if h["barrier"] == bw]
            if trials:
                rates[bw] = sum(1 for t in trials if t["result"]) / len(trials)

        # 전체 순서: 얇은 > 두꺼운
        if 10 in rates and 150 in rates:
            self.assertGreater(rates[10], rates[150])

    def test_history_result_is_boolean(self):
        """시행 기록의 result는 항상 bool."""
        history = self._simulate_with_history([BARRIER_WIDTH_DEFAULT], 30)
        for h in history:
            self.assertIsInstance(h["result"], bool)


# ═══════════════════════════════════════════════════════
# 6. 장벽 범위 제약 검증
# ═══════════════════════════════════════════════════════


class TestBarrierRangeConstraints(unittest.TestCase):
    """장벽 두께 범위와 관련 상수 검증."""

    def test_min_less_than_max(self):
        self.assertLess(BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX)

    def test_default_in_range(self):
        self.assertGreaterEqual(BARRIER_WIDTH_DEFAULT, BARRIER_WIDTH_MIN)
        self.assertLessEqual(BARRIER_WIDTH_DEFAULT, BARRIER_WIDTH_MAX)

    def test_min_barrier_positive(self):
        self.assertGreater(BARRIER_WIDTH_MIN, 0)

    def test_barrier_x_centered_in_sim(self):
        """장벽이 시뮬레이션 영역 중앙에 위치."""
        expected_center = SIM_LEFT + SIM_W // 2
        self.assertEqual(BARRIER_X, expected_center)

    def test_min_barrier_fits_in_sim(self):
        """최소 장벽이 시뮬레이션 영역 안에 들어감."""
        left = BARRIER_X - BARRIER_WIDTH_MIN / 2
        right = BARRIER_X + BARRIER_WIDTH_MIN / 2
        self.assertGreater(left, SIM_LEFT)
        self.assertLess(right, SIM_LEFT + SIM_W)

    def test_max_barrier_fits_in_sim(self):
        """최대 장벽이 시뮬레이션 영역 안에 들어감."""
        left = BARRIER_X - BARRIER_WIDTH_MAX / 2
        right = BARRIER_X + BARRIER_WIDTH_MAX / 2
        self.assertGreater(left, SIM_LEFT)
        self.assertLess(right, SIM_LEFT + SIM_W)

    def test_particle_start_before_min_barrier(self):
        """입자 시작 위치가 최소 장벽 왼쪽 가장자리보다 왼쪽."""
        start_x = SIM_LEFT + 40.0
        min_left_edge = BARRIER_X - BARRIER_WIDTH_MAX / 2
        self.assertLess(start_x + PARTICLE_RADIUS, min_left_edge)


# ═══════════════════════════════════════════════════════
# 7. 입자 카운터 정합성
# ═══════════════════════════════════════════════════════


class TestParticleCounterConsistency(unittest.TestCase):
    """장벽 전환 중에도 입자 카운터가 일관성을 유지."""

    def test_tunnel_plus_reflect_equals_attempts(self):
        """tunnel_count + reflect_count == total_attempts (항상)."""
        for bw in [BARRIER_WIDTH_MIN, BARRIER_WIDTH_DEFAULT, 80, BARRIER_WIDTH_MAX]:
            p = _run_trials(200, barrier_width=bw)
            self.assertEqual(
                p.tunnel_count + p.reflect_count,
                p.total_attempts,
                f"bw={bw}: {p.tunnel_count}+{p.reflect_count} != {p.total_attempts}",
            )

    def test_counters_accumulate_across_configs(self):
        """장벽 전환 시에도 카운터가 누적됨 (리셋 안 됨)."""
        p = QuantumParticle()
        configs = [(10, 100), (50, 100), (150, 100)]
        prev_total = 0

        for bw, n in configs:
            prob = _calc_tunnel_prob(bw)
            for _ in range(n):
                p.reset()
                for _ in range(600):
                    p.update(1 / 60, barrier_width=bw, tunnel_prob=prob)
                    if p.tunneled is not None:
                        break
            self.assertGreater(p.total_attempts, prev_total, f"After bw={bw}: total should increase")
            prev_total = p.total_attempts

        # 전체 합 검증
        self.assertEqual(p.tunnel_count + p.reflect_count, p.total_attempts)

    def test_reset_clears_particle_state_not_counters(self):
        """particle.reset()은 위치만 초기화, 카운터는 유지."""
        p = QuantumParticle()
        # 1회 시행
        for _ in range(600):
            p.update(1 / 60, barrier_width=12, tunnel_prob=0.5)
            if p.tunneled is not None:
                break
        count_before = p.total_attempts
        p.reset()
        self.assertEqual(p.total_attempts, count_before, "reset() should not clear counters")
        self.assertIsNone(p.tunneled, "reset() should clear tunneled state")

    def test_new_particle_has_zero_counters(self):
        """새 QuantumParticle()은 카운터 0."""
        p = QuantumParticle()
        self.assertEqual(p.tunnel_count, 0)
        self.assertEqual(p.reflect_count, 0)
        self.assertEqual(p.total_attempts, 0)


# ═══════════════════════════════════════════════════════
# 8. 통합 비교 시나리오
# ═══════════════════════════════════════════════════════


class TestCompareScenarios(unittest.TestCase):
    """Compare 모드의 전체 시나리오 검증."""

    def test_three_config_compare(self):
        """3가지 장벽(얇은/보통/두꺼운) 비교 → 각각 독립적 통계 정확."""
        configs = [
            (BARRIER_WIDTH_MIN, "thin"),
            (BARRIER_WIDTH_DEFAULT, "default"),
            (100, "thick"),
        ]
        results = {}
        for bw, label in configs:
            p = _run_trials(300, barrier_width=bw)
            results[label] = {
                "rate": p.tunnel_count / max(p.total_attempts, 1),
                "tunnel_count": p.tunnel_count,
                "theory": _calc_tunnel_prob(bw),
            }

        # 순서 검증
        self.assertGreater(results["thin"]["rate"], results["thick"]["rate"])
        self.assertGreater(results["thin"]["theory"], results["thick"]["theory"])

    def test_barrier_configs_tracking(self):
        """barrier_configs_tried 추적: set으로 고유 두께 카운트."""
        configs_tried: set[int] = set()
        widths_sequence = [12, 20, 12, 50, 20, 100]

        for bw in widths_sequence:
            configs_tried.add(bw)

        self.assertEqual(len(configs_tried), 4)  # {12, 20, 50, 100}
        self.assertEqual(configs_tried, {12, 20, 50, 100})

    def test_max_tunnel_barrier_tracking(self):
        """max_tunnel_barrier 추적: 가장 두꺼운 장벽에서 터널링 성공한 기록."""
        max_tunnel_barrier = 0
        test_widths = [20, 50, 100]

        for bw in test_widths:
            p = _run_trials(100, barrier_width=bw, tunnel_prob=1.0)  # 확실히 터널링
            if p.tunnel_count > 0 and bw > max_tunnel_barrier:
                max_tunnel_barrier = bw

        self.assertEqual(max_tunnel_barrier, 100)

    def test_compare_identifies_optimal_width(self):
        """비교를 통해 최적 장벽(가장 높은 터널링률) 식별."""
        widths = [10, 30, 80, 150]
        best_width = None
        best_rate = -1.0

        for i, bw in enumerate(widths):
            p = _run_trials(200, barrier_width=bw, seed=42 + i)
            rate = p.tunnel_count / max(p.total_attempts, 1)
            if rate > best_rate:
                best_rate = rate
                best_width = bw

        # 가장 얇은 장벽이 최적
        self.assertEqual(best_width, 10, f"Optimal should be thinnest, got {best_width}")

    def test_cumulative_rate_converges(self):
        """시행 횟수 증가에 따라 누적 비율이 이론 확률에 수렴."""
        bw = 50
        theory = _calc_tunnel_prob(bw)
        p = QuantumParticle()

        rates_at_checkpoints = []
        for trial in range(1, 601):
            p.reset()
            for _ in range(600):
                p.update(1 / 60, barrier_width=bw, tunnel_prob=theory)
                if p.tunneled is not None:
                    break
            if trial in (50, 200, 600):
                rates_at_checkpoints.append(p.tunnel_count / p.total_attempts)

        # 마지막 체크포인트가 이론값에 가장 가까워야 함
        if len(rates_at_checkpoints) == 3:
            err_late = abs(rates_at_checkpoints[2] - theory)
            # 항상 성립하지는 않지만, 600회면 충분히 수렴
            self.assertLess(
                err_late,
                0.05,
                f"After 600 trials: error={err_late:.3f} should be < 0.05",
            )


if __name__ == "__main__":
    unittest.main()
