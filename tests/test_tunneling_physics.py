"""터널링 물리 함수 단위 테스트.

#1  update() 입력 검증
#2  _calc_tunnel_prob() 오버플로 방어
#3  qubit_state() 전용 단위테스트
#4  superposition_alpha() 구간별 테스트
#5  reset() 카운터 보존 테스트
"""

import math
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for mod in ("pygame", "pygame.locals", "matplotlib", "matplotlib.pyplot", "tkinter"):
    sys.modules.setdefault(mod, MagicMock())

from quantum.tunneling_physics import (
    _TUNNEL_DECAY,
    BARRIER_WIDTH_DEFAULT,
    BARRIER_WIDTH_MAX,
    BARRIER_WIDTH_MIN,
    PARTICLE_SPEED,
    SIM_H,
    SIM_LEFT,
    SIM_TOP,
    SUPERPOSITION_HZ,
    TUNNEL_PROB_BASE,
    QuantumParticle,
    _calc_tunnel_prob,
)


class TestCalcTunnelProb(unittest.TestCase):
    """_calc_tunnel_prob() — 장벽 두께에 따른 터널링 확률."""

    def test_default_width_returns_base_prob(self):
        prob = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT)
        self.assertAlmostEqual(prob, TUNNEL_PROB_BASE)

    def test_wider_barrier_lower_prob(self):
        p_default = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT)
        p_wide = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT + 50)
        self.assertLess(p_wide, p_default)

    def test_thinner_barrier_higher_prob(self):
        p_default = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT)
        p_thin = _calc_tunnel_prob(BARRIER_WIDTH_MIN)
        self.assertGreater(p_thin, p_default)

    def test_exponential_decay(self):
        width = 50
        expected = TUNNEL_PROB_BASE * math.exp(-_TUNNEL_DECAY * (width - BARRIER_WIDTH_DEFAULT))
        self.assertAlmostEqual(_calc_tunnel_prob(width), expected)

    def test_always_positive(self):
        for w in range(BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX + 1, 10):
            self.assertGreater(_calc_tunnel_prob(w), 0)

    def test_max_width_very_small_prob(self):
        p = _calc_tunnel_prob(BARRIER_WIDTH_MAX)
        self.assertLess(p, TUNNEL_PROB_BASE * 0.1)

    def test_monotonic_decrease(self):
        widths = list(range(BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX, 5))
        probs = [_calc_tunnel_prob(w) for w in widths]
        for i in range(len(probs) - 1):
            self.assertGreaterEqual(probs[i], probs[i + 1])


# ═══════════════════════════════════════════════════════════
# #2  _calc_tunnel_prob 오버플로 방어
# ═══════════════════════════════════════════════════════════


class TestCalcTunnelProbOverflow(unittest.TestCase):
    """_calc_tunnel_prob() — 극단 입력에서도 안전."""

    def test_extreme_negative_width_clamped(self):
        """음수 barrier_width → BARRIER_WIDTH_MIN 클램핑."""
        p = _calc_tunnel_prob(-1000)
        self.assertEqual(p, _calc_tunnel_prob(BARRIER_WIDTH_MIN))

    def test_extreme_large_width_clamped(self):
        """매우 큰 barrier_width → BARRIER_WIDTH_MAX 클램핑."""
        p = _calc_tunnel_prob(999999)
        self.assertEqual(p, _calc_tunnel_prob(BARRIER_WIDTH_MAX))

    def test_zero_width_clamped_to_min(self):
        """barrier_width=0 → MIN으로 클램핑."""
        p = _calc_tunnel_prob(0)
        self.assertEqual(p, _calc_tunnel_prob(BARRIER_WIDTH_MIN))

    def test_float_width_truncated(self):
        """float barrier_width → int 변환."""
        p = _calc_tunnel_prob(12.9)  # type: ignore[arg-type]
        self.assertEqual(p, _calc_tunnel_prob(12))

    def test_no_overflow_at_min(self):
        """MIN에서 exp 오버플로 없음."""
        p = _calc_tunnel_prob(BARRIER_WIDTH_MIN)
        self.assertTrue(math.isfinite(p))
        self.assertGreater(p, 0)

    def test_no_overflow_at_max(self):
        """MAX에서 exp 오버플로 없음."""
        p = _calc_tunnel_prob(BARRIER_WIDTH_MAX)
        self.assertTrue(math.isfinite(p))
        self.assertGreater(p, 0)

    def test_result_always_finite(self):
        """어떤 입력이든 결과는 유한."""
        for w in (-10000, -1, 0, 1, 500, 10000):
            p = _calc_tunnel_prob(w)
            self.assertTrue(math.isfinite(p), f"width={w} → {p}")


# ═══════════════════════════════════════════════════════════
# #1  update() 입력 검증
# ═══════════════════════════════════════════════════════════


class TestUpdateInputValidation(unittest.TestCase):
    """QuantumParticle.update() — 입력 검증."""

    def setUp(self):
        self.p = QuantumParticle()

    def test_negative_dt_no_movement(self):
        """dt < 0 → 위치 변화 없음."""
        x0, y0 = self.p.x, self.p.y
        self.p.update(-1.0)
        self.assertEqual(self.p.x, x0)
        self.assertEqual(self.p.y, y0)

    def test_zero_dt_no_movement(self):
        """dt = 0 → 위치 변화 없음."""
        x0, y0 = self.p.x, self.p.y
        self.p.update(0.0)
        self.assertEqual(self.p.x, x0)
        self.assertEqual(self.p.y, y0)

    def test_tunnel_prob_clamped_above_one(self):
        """tunnel_prob > 1 → 1로 클램핑 (항상 터널링)."""
        # tunnel_prob=2.0이면 1.0으로 클램핑 → 오류 없이 작동
        self.p.update(1 / 60, tunnel_prob=2.0)
        # 에러 없이 실행되면 성공

    def test_tunnel_prob_clamped_below_zero(self):
        """tunnel_prob < 0 → 0으로 클램핑."""
        self.p.update(1 / 60, tunnel_prob=-0.5)

    def test_barrier_width_clamped_below_min(self):
        """barrier_width < MIN → MIN으로 클램핑."""
        self.p.update(1 / 60, barrier_width=0)

    def test_barrier_width_clamped_above_max(self):
        """barrier_width > MAX → MAX로 클램핑."""
        self.p.update(1 / 60, barrier_width=9999)

    def test_negative_speed_boost_clamped(self):
        """speed_boost < 0 → 0으로 클램핑."""
        self.p.update(1 / 60, speed_boost=-5.0)

    def test_not_alive_skips_update(self):
        """alive=False → update 스킵."""
        self.p.alive = False
        x0 = self.p.x
        self.p.update(1 / 60)
        self.assertEqual(self.p.x, x0)

    def test_valid_inputs_normal_operation(self):
        """정상 입력 → 위치 변화 발생."""
        x0 = self.p.x
        self.p.update(1 / 60)
        self.assertNotEqual(self.p.x, x0)

    def test_float_barrier_width_converted(self):
        """float barrier_width → int 변환 후 정상 동작."""
        self.p.update(1 / 60, barrier_width=15.7)  # type: ignore[arg-type]
        # 에러 없이 실행


# ═══════════════════════════════════════════════════════════
# #3  qubit_state() 전용 단위테스트
# ═══════════════════════════════════════════════════════════


class TestQubitState(unittest.TestCase):
    """QuantumParticle.qubit_state() — 중첩 상태 관측값."""

    def setUp(self):
        self.p = QuantumParticle()
        # 주기 = 1 / SUPERPOSITION_HZ (초) = 1000 / SUPERPOSITION_HZ (밀리초)
        self.period_ms = 1000.0 / SUPERPOSITION_HZ

    def test_returns_zero_or_one(self):
        """반환값은 항상 0 또는 1."""
        for t_ms in range(0, 2000, 7):
            state = self.p.qubit_state(float(t_ms))
            self.assertIn(state, (0, 1))

    def test_at_time_zero(self):
        """t=0 → sin(0)=0 ≥ 0 → state=0."""
        self.assertEqual(self.p.qubit_state(0.0), 0)

    def test_at_quarter_period(self):
        """t=T/4 → sin(π/2)=1 > 0 → state=0."""
        t_ms = self.period_ms / 4
        self.assertEqual(self.p.qubit_state(t_ms), 0)

    def test_at_three_quarter_period(self):
        """t=3T/4 → sin(3π/2)=-1 < 0 → state=1."""
        t_ms = self.period_ms * 3 / 4
        self.assertEqual(self.p.qubit_state(t_ms), 1)

    def test_state_changes_within_period(self):
        """한 주기 내에서 0→1→0 전환이 일어남."""
        states = set()
        for i in range(100):
            t_ms = self.period_ms * i / 100
            states.add(self.p.qubit_state(t_ms))
        self.assertEqual(states, {0, 1})

    def test_frequency_matches_config(self):
        """1초 동안 0→1 전환 횟수 ≈ SUPERPOSITION_HZ × 2 (반주기마다)."""
        transitions = 0
        prev = self.p.qubit_state(0.0)
        # 1초 = 1000ms, 0.1ms 간격으로 샘플링
        for i in range(1, 10001):
            t_ms = i * 0.1
            cur = self.p.qubit_state(t_ms)
            if cur != prev:
                transitions += 1
            prev = cur
        # 1초에 SUPERPOSITION_HZ 주기 → 주기당 2번 전환
        expected = SUPERPOSITION_HZ * 2
        self.assertAlmostEqual(transitions, expected, delta=2)

    def test_negative_time(self):
        """음수 시간에서도 정상 동작 (sin은 주기함수)."""
        state = self.p.qubit_state(-500.0)
        self.assertIn(state, (0, 1))

    def test_very_large_time(self):
        """매우 큰 시간에서도 0 또는 1."""
        state = self.p.qubit_state(1e9)
        self.assertIn(state, (0, 1))


# ═══════════════════════════════════════════════════════════
# #4  superposition_alpha() 구간별 테스트
# ═══════════════════════════════════════════════════════════


class TestSuperpositionAlpha(unittest.TestCase):
    """QuantumParticle.superposition_alpha() — 블로흐 구 θ 각도."""

    def setUp(self):
        self.p = QuantumParticle()
        self.period_ms = 1000.0 / SUPERPOSITION_HZ

    def test_at_time_zero(self):
        """t=0 → sin(0)=0 → α = π/2."""
        alpha = self.p.superposition_alpha(0.0)
        self.assertAlmostEqual(alpha, math.pi / 2, places=10)

    def test_at_quarter_period(self):
        """t=T/4 → sin(π/2)=1 → α = 0 (|0⟩)."""
        alpha = self.p.superposition_alpha(self.period_ms / 4)
        self.assertAlmostEqual(alpha, 0.0, places=10)

    def test_at_half_period(self):
        """t=T/2 → sin(π)≈0 → α ≈ π/2."""
        alpha = self.p.superposition_alpha(self.period_ms / 2)
        self.assertAlmostEqual(alpha, math.pi / 2, places=6)

    def test_at_three_quarter_period(self):
        """t=3T/4 → sin(3π/2)=-1 → α = π (|1⟩)."""
        alpha = self.p.superposition_alpha(self.period_ms * 3 / 4)
        self.assertAlmostEqual(alpha, math.pi, places=10)

    def test_at_full_period(self):
        """t=T → sin(2π)≈0 → α ≈ π/2."""
        alpha = self.p.superposition_alpha(self.period_ms)
        self.assertAlmostEqual(alpha, math.pi / 2, places=6)

    def test_range_always_0_to_pi(self):
        """모든 시간에서 α ∈ [0, π]."""
        for i in range(1000):
            t_ms = i * 0.37  # 불규칙 간격
            alpha = self.p.superposition_alpha(t_ms)
            self.assertGreaterEqual(alpha, 0.0, f"t_ms={t_ms}")
            self.assertLessEqual(alpha, math.pi, f"t_ms={t_ms}")

    def test_minimum_is_zero(self):
        """최솟값은 0 (|0⟩ 상태)."""
        min_alpha = min(self.p.superposition_alpha(i * 0.1) for i in range(int(self.period_ms * 10)))
        self.assertAlmostEqual(min_alpha, 0.0, places=2)

    def test_maximum_is_pi(self):
        """최댓값은 π (|1⟩ 상태)."""
        max_alpha = max(self.p.superposition_alpha(i * 0.1) for i in range(int(self.period_ms * 10)))
        self.assertAlmostEqual(max_alpha, math.pi, places=2)

    def test_continuity(self):
        """인접 시간 샘플 간 연속성 (급격한 점프 없음)."""
        dt_ms = 0.1
        prev = self.p.superposition_alpha(0.0)
        max_jump = 0.0
        for i in range(1, 5000):
            cur = self.p.superposition_alpha(i * dt_ms)
            max_jump = max(max_jump, abs(cur - prev))
            prev = cur
        # 0.1ms 간격에서 최대 점프는 작아야 함
        self.assertLess(max_jump, 0.1)

    def test_periodic(self):
        """α(t) = α(t + T)  (주기성)."""
        for t_ms in (10.0, 50.0, 123.4):
            a1 = self.p.superposition_alpha(t_ms)
            a2 = self.p.superposition_alpha(t_ms + self.period_ms)
            self.assertAlmostEqual(a1, a2, places=6)

    def test_consistent_with_qubit_state(self):
        """α < π/2 → qubit_state=0, α > π/2 → qubit_state=1."""
        # 정확한 π/2 지점(경계)은 제외
        for i in range(1000):
            t_ms = i * 0.37
            alpha = self.p.superposition_alpha(t_ms)
            state = self.p.qubit_state(t_ms)
            if alpha < math.pi / 2 - 0.01:
                self.assertEqual(state, 0, f"t_ms={t_ms}, α={alpha}")
            elif alpha > math.pi / 2 + 0.01:
                self.assertEqual(state, 1, f"t_ms={t_ms}, α={alpha}")

    def test_negative_time(self):
        """음수 시간 → 범위 내 값."""
        alpha = self.p.superposition_alpha(-1000.0)
        self.assertGreaterEqual(alpha, 0.0)
        self.assertLessEqual(alpha, math.pi)


# ═══════════════════════════════════════════════════════════
# #5  reset() 카운터 보존 테스트
# ═══════════════════════════════════════════════════════════


class TestResetCounterPreservation(unittest.TestCase):
    """QuantumParticle.reset() — 카운터 보존 및 상태 초기화."""

    def setUp(self):
        self.p = QuantumParticle()

    def test_counters_preserved_after_reset(self):
        """reset() 후 tunnel_count, reflect_count, total_attempts 유지."""
        self.p.tunnel_count = 5
        self.p.reflect_count = 3
        self.p.total_attempts = 8
        self.p.reset()
        self.assertEqual(self.p.tunnel_count, 5)
        self.assertEqual(self.p.reflect_count, 3)
        self.assertEqual(self.p.total_attempts, 8)

    def test_position_reset_to_start(self):
        """reset() 후 x는 초기 위치로."""
        self.p.x = 999.0
        self.p.reset()
        self.assertAlmostEqual(self.p.x, SIM_LEFT + 40.0)

    def test_y_reset_to_center(self):
        """reset() 후 y는 영역 중앙."""
        self.p.y = 0.0
        self.p.reset()
        self.assertAlmostEqual(self.p.y, SIM_TOP + SIM_H / 2.0)

    def test_velocity_reset(self):
        """reset() 후 vx는 PARTICLE_SPEED, vy는 랜덤 범위 내."""
        self.p.vx = -50.0
        self.p.reset()
        self.assertEqual(self.p.vx, PARTICLE_SPEED)

    def test_tunneled_state_cleared(self):
        """reset() 후 tunneled = None."""
        self.p.tunneled = True
        self.p.reset()
        self.assertIsNone(self.p.tunneled)

    def test_alive_restored(self):
        """reset() 후 alive = True."""
        self.p.alive = False
        self.p.reset()
        self.assertTrue(self.p.alive)

    def test_flash_timer_cleared(self):
        """reset() 후 flash_timer = 0."""
        self.p.flash_timer = 0.5
        self.p.reset()
        self.assertEqual(self.p.flash_timer, 0.0)

    def test_multiple_resets_preserve_counters(self):
        """여러 번 reset() 해도 카운터 유지."""
        self.p.tunnel_count = 10
        self.p.reflect_count = 7
        self.p.total_attempts = 17
        for _ in range(5):
            self.p.reset()
        self.assertEqual(self.p.tunnel_count, 10)
        self.assertEqual(self.p.reflect_count, 7)
        self.assertEqual(self.p.total_attempts, 17)

    def test_init_counters_zero(self):
        """__init__ 직후 카운터는 0."""
        p = QuantumParticle()
        self.assertEqual(p.tunnel_count, 0)
        self.assertEqual(p.reflect_count, 0)
        self.assertEqual(p.total_attempts, 0)

    def test_counters_accumulate_across_resets(self):
        """reset + update 반복 시 카운터 누적."""
        p = QuantumParticle(seed=42)
        for _ in range(50):
            p.reset()
            for _ in range(600):
                p.update(1 / 60, barrier_width=12, tunnel_prob=0.5)
                if p.tunneled is not None:
                    break
        total = p.tunnel_count + p.reflect_count
        self.assertEqual(total, p.total_attempts)
        self.assertGreater(p.total_attempts, 0)


# ═══════════════════════════════════════════════════════════
# #6  시드 기반 재현성 테스트
# ═══════════════════════════════════════════════════════════


def _simulate(seed, n_trials=30, barrier_width=12, tunnel_prob=0.10):
    """동일 시드로 n_trials 반복 → (tunnel_count, reflect_count, vy 리스트)."""
    p = QuantumParticle(seed=seed)
    vy_list = [p.vy]
    for _ in range(n_trials):
        p.reset()
        vy_list.append(p.vy)
        for _ in range(600):
            p.update(1 / 60, barrier_width=barrier_width, tunnel_prob=tunnel_prob)
            if p.tunneled is not None:
                break
    return p.tunnel_count, p.reflect_count, vy_list


class TestSeedReproducibility(unittest.TestCase):
    """QuantumParticle(seed=...) — 시드 기반 재현성."""

    def test_same_seed_same_result(self):
        """동일 시드 → 동일 결과."""
        t1, r1, vy1 = _simulate(seed=123)
        t2, r2, vy2 = _simulate(seed=123)
        self.assertEqual(t1, t2)
        self.assertEqual(r1, r2)
        self.assertEqual(vy1, vy2)

    def test_different_seed_different_result(self):
        """다른 시드 → 다른 vy 시퀀스."""
        _, _, vy1 = _simulate(seed=100)
        _, _, vy2 = _simulate(seed=200)
        self.assertNotEqual(vy1, vy2)

    def test_none_seed_nondeterministic(self):
        """seed=None → 비결정적 (두 인스턴스의 vy가 다를 가능성 매우 높음)."""
        p1 = QuantumParticle(seed=None)
        p2 = QuantumParticle(seed=None)
        # vy는 random이므로 동일할 확률은 극히 낮음
        # 10회 reset으로 시퀀스 비교
        vy1 = [p1.vy]
        vy2 = [p2.vy]
        for _ in range(10):
            p1.reset()
            p2.reset()
            vy1.append(p1.vy)
            vy2.append(p2.vy)
        self.assertNotEqual(vy1, vy2)

    def test_seed_zero(self):
        """seed=0 도 유효한 시드."""
        t1, r1, vy1 = _simulate(seed=0)
        t2, r2, vy2 = _simulate(seed=0)
        self.assertEqual(t1, t2)
        self.assertEqual(vy1, vy2)

    def test_seed_does_not_affect_global_random(self):
        """인스턴스 RNG가 글로벌 random 모듈에 영향 주지 않음."""
        import random

        random.seed(999)
        global_before = [random.random() for _ in range(5)]

        random.seed(999)
        _ = QuantumParticle(seed=42)  # 인스턴스 생성 (reset 포함)
        global_after = [random.random() for _ in range(5)]

        self.assertEqual(global_before, global_after)

    def test_reproducible_tunnel_sequence(self):
        """동일 시드 → 터널링/반사 시퀀스 동일."""

        def _get_sequence(seed):
            p = QuantumParticle(seed=seed)
            results = []
            for _ in range(20):
                p.reset()
                for _ in range(600):
                    p.update(1 / 60, barrier_width=12, tunnel_prob=0.3)
                    if p.tunneled is not None:
                        results.append(p.tunneled)
                        break
            return results

        seq1 = _get_sequence(seed=777)
        seq2 = _get_sequence(seed=777)
        self.assertEqual(seq1, seq2)
        # 시퀀스에 True와 False가 섞여 있어야 함 (prob=0.3)
        self.assertIn(True, seq1)
        self.assertIn(False, seq1)

    def test_reproducible_vy_values(self):
        """동일 시드 → reset마다 동일한 vy."""
        p1 = QuantumParticle(seed=55)
        p2 = QuantumParticle(seed=55)
        for _ in range(20):
            self.assertEqual(p1.vy, p2.vy)
            p1.reset()
            p2.reset()

    def test_backward_compatible_no_seed(self):
        """seed 없이 생성 → 기존처럼 동작."""
        p = QuantumParticle()
        self.assertIsNotNone(p._rng)
        # 정상 작동 확인
        p.update(1 / 60)
        self.assertNotEqual(p.x, SIM_LEFT + 40.0)

    def test_large_seed(self):
        """큰 시드값도 정상 동작."""
        t1, r1, vy1 = _simulate(seed=2**31 - 1)
        t2, r2, vy2 = _simulate(seed=2**31 - 1)
        self.assertEqual(t1, t2)
        self.assertEqual(vy1, vy2)

    def test_negative_seed(self):
        """음수 시드도 정상 동작."""
        t1, _, vy1 = _simulate(seed=-42)
        t2, _, vy2 = _simulate(seed=-42)
        self.assertEqual(t1, t2)
        self.assertEqual(vy1, vy2)


if __name__ == "__main__":
    unittest.main()
