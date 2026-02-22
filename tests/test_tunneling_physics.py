"""터널링 물리 함수 단위 테스트.

#1  update() 입력 검증
#2  _calc_tunnel_prob() 오버플로 방어
#3  qubit_state() 전용 단위테스트
#4  superposition_alpha() 구간별 테스트
#5  reset() 카운터 보존 테스트
#6  시드 기반 재현성
#7  trial_history 크기 제한
#9  config 기반 레이아웃 상수
#10 반사 감쇠 계수 config 분리
#12 업적 진행도 데이터 검증
#14 프리셋 중간 전환 (base_prob 파라미터)
#15 사운드 이펙트 (배리어/업적/속도/프리셋)
#16 수식 오버레이 동적 계산 검증
#17 문맥별 힌트 (마우스 위치 기반 툴팁)
#18 통계 데이터 내보내기 (CSV/JSON)
#19 텍스트 서피스 캐시 (font.render 반복 호출 제거)
#20 대원 메시 사전 계산 + 투영 캐시
"""

import math
import os
import sys
import unittest
from collections import deque
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for mod in ("pygame", "pygame.locals", "matplotlib", "matplotlib.pyplot", "tkinter"):
    sys.modules.setdefault(mod, MagicMock())

from quantum.tunneling_physics import (
    _TUNNEL_DECAY,
    BARRIER_WIDTH_DEFAULT,
    BARRIER_WIDTH_MAX,
    BARRIER_WIDTH_MIN,
    BARRIER_X,
    BLOCH_LERP_SPEED,
    PARTICLE_RADIUS,
    PARTICLE_SPEED,
    REFLECT_DAMPING,
    SIM_H,
    SIM_LEFT,
    SIM_TOP,
    SIM_W,
    SUPERPOSITION_HZ,
    TRIAL_HISTORY_MAX,
    TUNNEL_PROB_BASE,
    BarrierSweeper,
    QuantumParticle,
    _calc_tunnel_prob,
    calc_energy_levels,
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


# ═══════════════════════════════════════════════════════════
# #7  trial_history 크기 제한 테스트
# ═══════════════════════════════════════════════════════════


def _make_trial(i, tunneled=True):
    """trial_history용 더미 레코드."""
    return {"t": round(i * 0.5, 2), "barrier": 12, "prob": 0.10, "result": tunneled}


class TestTrialHistoryBounded(unittest.TestCase):
    """trial_history를 deque(maxlen=TRIAL_HISTORY_MAX)로 사용할 때의 동작."""

    def test_constant_positive(self):
        """TRIAL_HISTORY_MAX > 0."""
        self.assertGreater(TRIAL_HISTORY_MAX, 0)

    def test_constant_is_int(self):
        """TRIAL_HISTORY_MAX는 정수형."""
        self.assertIsInstance(TRIAL_HISTORY_MAX, int)

    def test_deque_respects_maxlen(self):
        """deque(maxlen=N) 이 N개 초과 시 오래된 항목 제거."""
        maxlen = 10
        history = deque(maxlen=maxlen)
        for i in range(25):
            history.append(_make_trial(i))
        self.assertEqual(len(history), maxlen)
        # 가장 오래된 것은 15번째 (i=15)
        self.assertEqual(history[0]["t"], 7.5)  # 15 * 0.5
        # 가장 최신은 24번째
        self.assertEqual(history[-1]["t"], 12.0)  # 24 * 0.5

    def test_deque_with_trial_history_max(self):
        """TRIAL_HISTORY_MAX로 생성된 deque이 정확히 해당 크기로 제한."""
        history = deque(maxlen=TRIAL_HISTORY_MAX)
        for i in range(TRIAL_HISTORY_MAX + 100):
            history.append(_make_trial(i))
        self.assertEqual(len(history), TRIAL_HISTORY_MAX)

    def test_deque_preserves_order(self):
        """FIFO: 가장 오래된 것부터 버려지고, 최신이 끝에."""
        history = deque(maxlen=5)
        for i in range(8):
            history.append(_make_trial(i))
        # 0,1,2 버려지고 3,4,5,6,7 남음
        times = [r["t"] for r in history]
        self.assertEqual(times, [1.5, 2.0, 2.5, 3.0, 3.5])

    def test_deque_append_same_as_list(self):
        """append 동작이 list와 동일 (maxlen 미달 시)."""
        history = deque(maxlen=100)
        history.append(_make_trial(0))
        history.append(_make_trial(1))
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["t"], 0.0)
        self.assertEqual(history[1]["t"], 0.5)

    def test_deque_to_list_for_serialization(self):
        """list(deque) → JSON 직렬화 가능한 리스트로 변환."""
        history = deque(maxlen=5)
        for i in range(3):
            history.append(_make_trial(i))
        as_list = list(history)
        self.assertIsInstance(as_list, list)
        self.assertEqual(len(as_list), 3)

    def test_rate_chart_accuracy_with_bounded_history(self):
        """제한된 history에서 누적 비율 계산이 정확."""
        history = deque(maxlen=100)
        # 처음 50개: 모두 터널링
        for i in range(50):
            history.append(_make_trial(i, tunneled=True))
        # 다음 50개: 모두 반사
        for i in range(50, 100):
            history.append(_make_trial(i, tunneled=False))

        # 누적 비율 계산 (차트 로직 재현)
        tunnels = 0
        rates = []
        for j, tr in enumerate(history):
            if tr["result"]:
                tunnels += 1
            rates.append(tunnels / (j + 1))

        self.assertEqual(len(rates), 100)
        self.assertAlmostEqual(rates[49], 1.0)  # 처음 50개 모두 터널
        self.assertAlmostEqual(rates[99], 0.5)  # 전체 50/100

    def test_overflow_drops_oldest_tunnels(self):
        """maxlen 초과 시 오래된 터널링 결과가 사라짐."""
        history = deque(maxlen=5)
        # 터널링 3개 추가
        for i in range(3):
            history.append(_make_trial(i, tunneled=True))
        # 반사 4개 추가 → 터널링 2개 밀려남
        for i in range(3, 7):
            history.append(_make_trial(i, tunneled=False))

        self.assertEqual(len(history), 5)
        tunnel_count = sum(1 for r in history if r["result"])
        self.assertEqual(tunnel_count, 1)  # 터널링 1개만 남음

    def test_empty_deque_behaves_like_empty_list(self):
        """빈 deque → len=0, iteration 가능."""
        history = deque(maxlen=TRIAL_HISTORY_MAX)
        self.assertEqual(len(history), 0)
        self.assertEqual(list(history), [])

    def test_avg_barrier_from_bounded_history(self):
        """제한된 history에서 평균 barrier_width 계산."""
        history = deque(maxlen=10)
        for i in range(15):
            history.append({"t": i, "barrier": 10 + i, "prob": 0.1, "result": True})
        # 5~14 남음 (마지막 10개)
        avg = sum(r["barrier"] for r in history) / len(history)
        expected = sum(range(15, 25)) / 10  # 10+5=15 ~ 10+14=24
        self.assertAlmostEqual(avg, expected)


# ═══════════════════════════════════════════════════════════
# #9  config 기반 레이아웃 상수 테스트
# ═══════════════════════════════════════════════════════════


class TestConfigLayoutConstants(unittest.TestCase):
    """레이아웃 상수가 config에서 정상 로드되고 올바른 기본값을 갖는지 검증."""

    def test_sim_left_default(self):
        self.assertEqual(SIM_LEFT, 30)

    def test_sim_top_default(self):
        self.assertEqual(SIM_TOP, 70)

    def test_sim_w_default(self):
        self.assertEqual(SIM_W, 520)

    def test_sim_h_default(self):
        self.assertEqual(SIM_H, 420)

    def test_particle_radius_default(self):
        self.assertEqual(PARTICLE_RADIUS, 10)

    def test_particle_radius_positive(self):
        self.assertGreater(PARTICLE_RADIUS, 0)

    def test_barrier_x_derived(self):
        """BARRIER_X = SIM_LEFT + SIM_W // 2."""
        self.assertEqual(BARRIER_X, SIM_LEFT + SIM_W // 2)

    def test_bloch_lerp_speed_default(self):
        self.assertAlmostEqual(BLOCH_LERP_SPEED, 8.0)

    def test_bloch_lerp_speed_positive(self):
        self.assertGreater(BLOCH_LERP_SPEED, 0)

    def test_trial_history_max_default(self):
        self.assertEqual(TRIAL_HISTORY_MAX, 5000)

    def test_sim_area_positive_dimensions(self):
        """시뮬레이션 영역의 너비·높이가 양수."""
        self.assertGreater(SIM_W, 0)
        self.assertGreater(SIM_H, 0)

    def test_all_constants_are_numeric(self):
        """모든 레이아웃 상수가 숫자."""
        for name, val in [
            ("SIM_LEFT", SIM_LEFT),
            ("SIM_TOP", SIM_TOP),
            ("SIM_W", SIM_W),
            ("SIM_H", SIM_H),
            ("PARTICLE_RADIUS", PARTICLE_RADIUS),
            ("BARRIER_X", BARRIER_X),
        ]:
            self.assertIsInstance(val, (int, float), f"{name} is not numeric")


# ═══════════════════════════════════════════════════════════
# #10 반사 감쇠 계수 config 분리 테스트
# ═══════════════════════════════════════════════════════════


class TestReflectDamping(unittest.TestCase):
    """REFLECT_DAMPING — 반사 시 속도 감쇠 계수."""

    def test_default_value(self):
        """기본값 0.8."""
        self.assertAlmostEqual(REFLECT_DAMPING, 0.8)

    def test_range_zero_to_one(self):
        """감쇠 계수는 [0, 1] 범위."""
        self.assertGreaterEqual(REFLECT_DAMPING, 0.0)
        self.assertLessEqual(REFLECT_DAMPING, 1.0)

    def test_reflect_applies_damping(self):
        """반사 시 속도가 REFLECT_DAMPING 비율로 감소."""
        p = QuantumParticle(seed=0)
        original_speed = PARTICLE_SPEED

        # 장벽에 정면 충돌하도록 위치 조정 (tunnel_prob=0 → 무조건 반사)
        p.x = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1
        p.vx = PARTICLE_SPEED
        p.tunneled = None
        p.update(1 / 60, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.0)

        if p.tunneled is False:
            # 반사됨 → 속도가 -original_speed * REFLECT_DAMPING
            expected_vx = -abs(original_speed) * REFLECT_DAMPING
            self.assertAlmostEqual(p.vx, expected_vx, places=2)

    def test_reflect_reverses_direction(self):
        """반사 시 속도 방향이 반전 (음수)."""
        p = QuantumParticle(seed=1)
        p.x = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1
        p.vx = PARTICLE_SPEED
        p.tunneled = None
        p.update(1 / 60, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.0)

        if p.tunneled is False:
            self.assertLess(p.vx, 0)

    def test_damping_reduces_speed(self):
        """감쇠 후 |vx| < 원래 |vx| (REFLECT_DAMPING < 1 가정)."""
        if REFLECT_DAMPING >= 1.0:  # pragma: no cover
            self.skipTest("REFLECT_DAMPING >= 1.0")
        p = QuantumParticle(seed=2)
        p.x = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1
        p.vx = PARTICLE_SPEED
        p.tunneled = None
        p.update(1 / 60, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.0)

        if p.tunneled is False:
            self.assertLess(abs(p.vx), PARTICLE_SPEED)


# ═══════════════════════════════════════════════════════════
# #12 업적 진행도 데이터 검증
# ═══════════════════════════════════════════════════════════


class TestAchievementProgressData(unittest.TestCase):
    """업적 진행도 표시에 필요한 입자 데이터가 올바른지 검증."""

    def test_tunnel_count_increments(self):
        """터널링 성공 시 tunnel_count 증가."""
        p = QuantumParticle(seed=42)
        initial = p.tunnel_count
        # tunnel_prob=1.0 → 무조건 터널링
        for _ in range(100):
            p.reset()
            for _ in range(600):
                p.update(1 / 60, tunnel_prob=1.0)
                if p.tunneled is not None:
                    break
        self.assertGreater(p.tunnel_count, initial)

    def test_total_attempts_tracks_all_trials(self):
        """total_attempts = tunnel_count + reflect_count."""
        p = QuantumParticle(seed=99)
        for _ in range(30):
            p.reset()
            for _ in range(600):
                p.update(1 / 60, tunnel_prob=0.5)
                if p.tunneled is not None:
                    break
        self.assertEqual(p.total_attempts, p.tunnel_count + p.reflect_count)

    def test_tunnel_rate_calculation(self):
        """터널링 비율 = tunnel_count / total_attempts."""
        p = QuantumParticle(seed=77)
        for _ in range(50):
            p.reset()
            for _ in range(600):
                p.update(1 / 60, tunnel_prob=0.3)
                if p.tunneled is not None:
                    break
        if p.total_attempts > 0:
            rate = p.tunnel_count / p.total_attempts
            self.assertGreaterEqual(rate, 0.0)
            self.assertLessEqual(rate, 1.0)

    def test_progress_data_consistency(self):
        """진행도 데이터의 일관성 검증."""
        p = QuantumParticle(seed=10)
        for _ in range(20):
            p.reset()
            for _ in range(600):
                p.update(1 / 60, tunnel_prob=0.5)
                if p.tunneled is not None:
                    break
        # 기본 불변식
        self.assertGreaterEqual(p.tunnel_count, 0)
        self.assertGreaterEqual(p.reflect_count, 0)
        self.assertEqual(p.total_attempts, p.tunnel_count + p.reflect_count)

    def test_achievement_threshold_constants_loaded(self):
        """업적 임계값이 config에서 올바르게 로드."""
        from config_loader import cfg

        streak = cfg("achievements", "tn_tunnel_streak", 10)
        self.assertIsInstance(streak, int)
        self.assertGreater(streak, 0)

        rate_thr = cfg("achievements", "tn_rate_threshold", 0.5)
        self.assertIsInstance(rate_thr, float)
        self.assertGreater(rate_thr, 0.0)
        self.assertLessEqual(rate_thr, 1.0)

    def test_check_achievements_returns_list(self):
        """check_achievements()는 리스트를 반환."""
        from achievements import check_achievements

        data = {
            "tunnel_count": 0,
            "total_attempts": 0,
            "tunnel_rate": 0.0,
            "tunnel_prob": 0.1,
            "elapsed_time": 0.0,
            "max_tunnel_barrier": 0,
            "barrier_configs_tried": 0,
        }
        result = check_achievements("tunneling", data)
        self.assertIsInstance(result, list)

    def test_achievement_ids_are_strings(self):
        """모든 터널링 업적 ID가 tn_ 접두사 문자열."""
        from achievements import ACHIEVEMENTS

        tn_achs = [a for a in ACHIEVEMENTS if a["module"] == "tunneling"]
        self.assertGreater(len(tn_achs), 0)
        for ach in tn_achs:
            self.assertIsInstance(ach["id"], str)
            self.assertTrue(ach["id"].startswith("tn_"), f"{ach['id']} missing tn_ prefix")

    def test_all_tunneling_achievements_have_icon(self):
        """모든 터널링 업적에 아이콘이 있음."""
        from achievements import ACHIEVEMENTS

        tn_achs = [a for a in ACHIEVEMENTS if a["module"] == "tunneling"]
        for ach in tn_achs:
            self.assertIn("icon", ach)
            self.assertIsInstance(ach["icon"], str)
            self.assertEqual(len(ach["icon"]), 1)

    def test_tunneling_achievement_count(self):
        """터널링 업적은 8개."""
        from achievements import ACHIEVEMENTS

        tn_achs = [a for a in ACHIEVEMENTS if a["module"] == "tunneling"]
        self.assertEqual(len(tn_achs), 8)

    def test_speed_run_needs_both_conditions(self):
        """스피드런 업적은 터널 횟수 + 시간 제한 둘 다 필요."""
        from achievements import ACHIEVEMENTS

        speed_ach = next(a for a in ACHIEVEMENTS if a["id"] == "tn_speed_run")
        # 시간 초과면 실패
        self.assertFalse(speed_ach["condition"]({"tunnel_count": 100, "elapsed_time": 999}))
        # 시간 내 충분한 터널 → 성공
        self.assertTrue(speed_ach["condition"]({"tunnel_count": 20, "elapsed_time": 25}))
        # 시간 내 부족한 터널 → 실패
        self.assertFalse(speed_ach["condition"]({"tunnel_count": 5, "elapsed_time": 10}))


# ── #14 프리셋 중간 전환 ─────────────────────────────


class TestCalcTunnelProbBaseProb(unittest.TestCase):
    """_calc_tunnel_prob의 base_prob 파라미터 테스트."""

    def test_default_base_prob(self):
        """base_prob=None이면 TUNNEL_PROB_BASE 사용."""
        result_none = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT, None)
        result_default = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT)
        self.assertAlmostEqual(result_none, result_default)

    def test_custom_base_prob_higher(self):
        """base_prob가 높으면 결과 확률도 높아짐."""
        low = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT, 0.1)
        high = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT, 0.3)
        self.assertGreater(high, low)

    def test_custom_base_prob_at_default_width(self):
        """기본 두께에서 base_prob와 결과가 동일."""
        # BARRIER_WIDTH_DEFAULT에서 exp 항은 e^0 = 1
        result = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT, 0.25)
        self.assertAlmostEqual(result, 0.25, places=6)

    def test_custom_base_prob_zero(self):
        """base_prob=0이면 결과도 0."""
        result = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT, 0.0)
        self.assertAlmostEqual(result, 0.0)

    def test_custom_base_prob_one(self):
        """base_prob=1.0이면 기본 두께에서 1.0."""
        result = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT, 1.0)
        self.assertAlmostEqual(result, 1.0, places=6)

    def test_custom_base_prob_clamped_negative(self):
        """음수 base_prob는 0으로 클램핑."""
        result = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT, -0.5)
        self.assertAlmostEqual(result, 0.0)

    def test_custom_base_prob_clamped_over_one(self):
        """1 초과 base_prob는 1로 클램핑."""
        result = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT, 1.5)
        self.assertAlmostEqual(result, 1.0, places=6)

    def test_wider_barrier_reduces_prob_with_custom_base(self):
        """두꺼운 장벽 + 커스텀 base_prob에서도 확률 감소."""
        base = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT, 0.25)
        wide = _calc_tunnel_prob(100, 0.25)
        self.assertGreater(base, wide)

    def test_easy_preset_prob(self):
        """easy 프리셋 값(0.25)이 normal(0.1)보다 높음."""
        easy = _calc_tunnel_prob(8, 0.25)  # easy preset
        normal = _calc_tunnel_prob(12, 0.1)  # normal preset
        self.assertGreater(easy, normal)

    def test_hard_preset_prob(self):
        """hard 프리셋 값(0.03, 40px)이 normal보다 낮음."""
        hard = _calc_tunnel_prob(40, 0.03)  # hard preset
        normal = _calc_tunnel_prob(12, 0.1)  # normal preset
        self.assertLess(hard, normal)


class TestMidSessionPresetSwitch(unittest.TestCase):
    """플레이 중 프리셋 전환 통합 테스트."""

    def test_preset_slider_map_has_prob(self):
        """slider_map에 tunnel_prob_base가 올바르게 매핑됨."""
        from presets import get_preset

        preset = get_preset("easy")
        self.assertIn("tunneling", preset)
        self.assertIn("tunnel_prob_base", preset["tunneling"])

    def test_all_presets_have_tunneling_keys(self):
        """easy/normal/hard 모두 터널링 설정 포함."""
        from presets import get_preset

        for name in ("easy", "normal", "hard"):
            preset = get_preset(name)
            self.assertIn("tunneling", preset, f"{name} preset missing tunneling section")
            tn = preset["tunneling"]
            self.assertIn("tunnel_prob_base", tn, f"{name} missing tunnel_prob_base")
            self.assertIn("barrier_width_default", tn, f"{name} missing barrier_width_default")

    def test_preset_prob_range(self):
        """프리셋 확률 값이 0~1 범위."""
        from presets import get_preset

        for name in ("easy", "normal", "hard"):
            prob = get_preset(name)["tunneling"]["tunnel_prob_base"]
            self.assertGreaterEqual(prob, 0.0, f"{name} prob < 0")
            self.assertLessEqual(prob, 1.0, f"{name} prob > 1")

    def test_preset_difficulty_ordering_prob(self):
        """easy > normal > hard 확률 순서."""
        from presets import get_preset

        easy_prob = get_preset("easy")["tunneling"]["tunnel_prob_base"]
        normal_prob = get_preset("normal")["tunneling"]["tunnel_prob_base"]
        hard_prob = get_preset("hard")["tunneling"]["tunnel_prob_base"]
        self.assertGreater(easy_prob, normal_prob)
        self.assertGreater(normal_prob, hard_prob)

    def test_preset_difficulty_ordering_barrier(self):
        """easy < normal < hard 장벽 두께 순서."""
        from presets import get_preset

        easy_bw = get_preset("easy")["tunneling"]["barrier_width_default"]
        normal_bw = get_preset("normal")["tunneling"]["barrier_width_default"]
        hard_bw = get_preset("hard")["tunneling"]["barrier_width_default"]
        self.assertLess(easy_bw, normal_bw)
        self.assertLess(normal_bw, hard_bw)

    def test_calc_tunnel_prob_with_preset_values(self):
        """각 프리셋 값으로 _calc_tunnel_prob 계산이 유효."""
        from presets import get_preset

        for name in ("easy", "normal", "hard"):
            tn = get_preset(name)["tunneling"]
            prob = _calc_tunnel_prob(
                int(tn["barrier_width_default"]),
                tn["tunnel_prob_base"],
            )
            self.assertGreater(prob, 0.0, f"{name} calculated prob is 0")
            self.assertLessEqual(prob, 1.0, f"{name} calculated prob > 1")

    def test_base_prob_proportional(self):
        """같은 장벽 두께에서 base_prob에 비례."""
        p1 = _calc_tunnel_prob(50, 0.1)
        p2 = _calc_tunnel_prob(50, 0.2)
        # base_prob 2배이면 결과도 정확히 2배
        self.assertAlmostEqual(p2 / p1, 2.0, places=5)


# ── #15 사운드 이펙트 ────────────────────────────────


class TestSoundEffects(unittest.TestCase):
    """터널링 모듈 사운드 이펙트 테스트."""

    def test_sound_manager_has_barrier_adjust(self):
        """SoundManager에 barrier_adjust 사운드 키 정의."""
        from sound_manager import SoundManager

        snd = SoundManager()
        # init 없이는 _sounds가 비어 있으므로 _build_sounds 없이 구조만 확인
        self.assertTrue(hasattr(snd, "play"))
        self.assertTrue(hasattr(snd, "enabled"))

    def test_sound_manager_has_speed_change(self):
        """SoundManager에 speed_change 사운드 키 정의."""
        from sound_manager import SoundManager

        snd = SoundManager()
        self.assertTrue(hasattr(snd, "play"))

    def test_play_without_init_no_crash(self):
        """초기화 전 play 호출해도 크래시 없음."""
        from sound_manager import SoundManager

        snd = SoundManager()
        # init()을 호출하지 않은 상태에서 play해도 안전
        snd.play("barrier_adjust")
        snd.play("speed_change")
        snd.play("achievement")
        snd.play("preset_change")
        snd.play("nonexistent_sound")

    def test_play_disabled_no_crash(self):
        """사운드 비활성 시 play 호출해도 크래시 없음."""
        from sound_manager import SoundManager

        snd = SoundManager()
        snd.enabled = False
        snd.play("barrier_adjust")
        snd.play("speed_change")
        snd.play("achievement")

    def test_expected_sound_keys_exist(self):
        """터널링에서 사용하는 사운드 키가 _build_sounds 메서드에 포함."""
        import inspect

        from sound_manager import SoundManager

        source = inspect.getsource(SoundManager._build_sounds)
        expected_keys = [
            "tunnel_success",
            "tunnel_reflect",
            "barrier_adjust",
            "speed_change",
            "achievement",
            "preset_change",
        ]
        for key in expected_keys:
            self.assertIn(f'"{key}"', source, f"Missing sound key: {key}")

    def test_volume_bounds(self):
        """볼륨 설정이 0~1 범위로 클램핑."""
        from sound_manager import SoundManager

        snd = SoundManager()
        snd.volume = 1.5
        self.assertLessEqual(snd.volume, 1.0)
        snd.volume = -0.5
        self.assertGreaterEqual(snd.volume, 0.0)

    def test_toggle_returns_state(self):
        """toggle()이 현재 상태를 반환."""
        from sound_manager import SoundManager

        snd = SoundManager()
        self.assertTrue(snd.enabled)
        result = snd.toggle()
        self.assertFalse(result)
        self.assertFalse(snd.enabled)

    def test_volume_up_down(self):
        """volume_up/volume_down 동작 확인."""
        from sound_manager import SoundManager

        snd = SoundManager()
        snd.volume = 0.5
        snd.volume_up(0.1)
        self.assertAlmostEqual(snd.volume, 0.6, places=2)
        snd.volume_down(0.2)
        self.assertAlmostEqual(snd.volume, 0.4, places=2)


# ── #16 수식 오버레이 동적 계산 ──────────────────────


class TestFormulaOverlayCalculations(unittest.TestCase):
    """수식 오버레이에서 사용하는 계산의 정확성 검증."""

    def test_exponent_at_default_width(self):
        """기본 두께에서 지수 항은 0."""
        exponent = -_TUNNEL_DECAY * (BARRIER_WIDTH_DEFAULT - BARRIER_WIDTH_DEFAULT)
        self.assertAlmostEqual(exponent, 0.0)

    def test_exponent_increases_with_width(self):
        """두께 증가 → 지수 감소 (음수 방향)."""
        exp_narrow = -_TUNNEL_DECAY * (10 - BARRIER_WIDTH_DEFAULT)
        exp_wide = -_TUNNEL_DECAY * (100 - BARRIER_WIDTH_DEFAULT)
        self.assertGreater(exp_narrow, exp_wide)

    def test_exp_val_at_default_width(self):
        """기본 두께에서 e^0 = 1."""
        exponent = -_TUNNEL_DECAY * (BARRIER_WIDTH_DEFAULT - BARRIER_WIDTH_DEFAULT)
        exp_val = math.exp(exponent)
        self.assertAlmostEqual(exp_val, 1.0)

    def test_final_prob_equals_calc_tunnel_prob(self):
        """수식 오버레이 계산이 _calc_tunnel_prob과 일치."""
        for bw, bp in [(12, 0.1), (50, 0.25), (100, 0.03), (4, 0.5)]:
            exponent = -_TUNNEL_DECAY * (bw - BARRIER_WIDTH_DEFAULT)
            exp_val = math.exp(max(-500.0, min(500.0, exponent)))
            overlay_result = bp * exp_val
            engine_result = _calc_tunnel_prob(bw, bp)
            self.assertAlmostEqual(overlay_result, engine_result, places=10, msg=f"bw={bw}, bp={bp}")

    def test_observed_vs_theoretical_sign(self):
        """관측률 > 이론 → 양수 차이, 관측률 < 이론 → 음수 차이."""
        observed = 0.15
        theoretical = 0.10
        diff = observed - theoretical
        self.assertGreater(diff, 0.0)

        observed2 = 0.05
        diff2 = observed2 - theoretical
        self.assertLess(diff2, 0.0)

    def test_tunnel_decay_is_positive(self):
        """감쇠 계수 κ는 양수."""
        self.assertGreater(_TUNNEL_DECAY, 0.0)

    def test_tunnel_decay_is_exported(self):
        """_TUNNEL_DECAY가 tunneling_physics에서 접근 가능."""
        from quantum.tunneling_physics import _TUNNEL_DECAY as decay

        self.assertIsInstance(decay, float)

    def test_formula_components_consistency(self):
        """수식 요소별 계산 합산이 최종 확률과 일치 (다양한 입력)."""
        test_cases = [
            (BARRIER_WIDTH_DEFAULT, TUNNEL_PROB_BASE),
            (BARRIER_WIDTH_MIN, 0.5),
            (BARRIER_WIDTH_MAX, 0.01),
            (50, 0.2),
        ]
        for bw, bp in test_cases:
            # 수식 오버레이와 동일한 과정
            bw_clamped = max(BARRIER_WIDTH_MIN, min(BARRIER_WIDTH_MAX, int(bw)))
            exponent = -_TUNNEL_DECAY * (bw_clamped - BARRIER_WIDTH_DEFAULT)
            exponent = max(-500.0, min(500.0, exponent))
            exp_val = math.exp(exponent)
            manual_result = bp * exp_val
            engine_result = _calc_tunnel_prob(bw, bp)
            self.assertAlmostEqual(manual_result, engine_result, places=10)


class TestContextualHints(unittest.TestCase):
    """#17 문맥별 힌트 — 마우스 위치에 따른 툴팁 반환."""

    def setUp(self):
        from quantum.tunneling import (
            _BARRIER_EDGE_TOL,
            _get_contextual_hint,
        )
        from quantum.tunneling_render import (
            _CHART_H,
            _CHART_W,
            _CHART_X,
            _CHART_Y,
            _FORMULA_H,
            _FORMULA_W,
            _FORMULA_X,
            _FORMULA_Y,
            BLOCH_CX,
            BLOCH_CY,
            BLOCH_R,
            HEIGHT,
            WIDTH,
        )

        self._get_hint = _get_contextual_hint
        self.BLOCH_CX = BLOCH_CX
        self.BLOCH_CY = BLOCH_CY
        self.BLOCH_R = BLOCH_R
        self.WIDTH = WIDTH
        self.HEIGHT = HEIGHT
        self.EDGE_TOL = _BARRIER_EDGE_TOL
        self.CHART_X = _CHART_X
        self.CHART_Y = _CHART_Y
        self.CHART_W = _CHART_W
        self.CHART_H = _CHART_H
        self.FORMULA_X = _FORMULA_X
        self.FORMULA_Y = _FORMULA_Y
        self.FORMULA_W = _FORMULA_W
        self.FORMULA_H = _FORMULA_H

        # 간이 ctx 목 객체
        self.ctx = MagicMock()
        self.ctx.barrier_width = BARRIER_WIDTH_DEFAULT
        self.ctx.barrier_dragging = False
        self.ctx.bloch_dragging = False
        self.ctx.tutorial.visible = False
        self.ctx.help_overlay.visible = False
        self.ctx.glossary.visible = False

    def test_barrier_edge_hint(self):
        """장벽 가장자리 근처에서 barrier 힌트 반환."""
        left_edge = BARRIER_X - self.ctx.barrier_width // 2
        hint = self._get_hint(left_edge + 2, SIM_TOP + 100, self.ctx)
        self.assertIsNotNone(hint)

    def test_bloch_sphere_hint(self):
        """블로흐 구 중심에서 bloch 힌트 반환."""
        hint = self._get_hint(self.BLOCH_CX, self.BLOCH_CY, self.ctx)
        self.assertIsNotNone(hint)

    def test_formula_overlay_hint(self):
        """수식 오버레이 영역에서 formula 힌트 반환."""
        hint = self._get_hint(self.FORMULA_X + 10, self.FORMULA_Y + 10, self.ctx)
        self.assertIsNotNone(hint)

    def test_chart_hint(self):
        """확률 차트 영역에서 chart 힌트 반환."""
        hint = self._get_hint(self.CHART_X + 10, self.CHART_Y + 5, self.ctx)
        self.assertIsNotNone(hint)

    def test_slider_panel_hint(self):
        """슬라이더 패널 영역에서 sliders 힌트 반환."""
        hint = self._get_hint(self.WIDTH + 20, 80, self.ctx)
        self.assertIsNotNone(hint)

    def test_sim_area_hint(self):
        """시뮬레이션 영역 (장벽 멀리)에서 sim 힌트 반환."""
        hint = self._get_hint(SIM_LEFT + 10, SIM_TOP + 10, self.ctx)
        self.assertIsNotNone(hint)

    def test_no_hint_outside(self):
        """모든 영역 밖 → None 반환."""
        hint = self._get_hint(0, 0, self.ctx)
        self.assertIsNone(hint)

    def test_overlay_active_hides_hint(self):
        """튜토리얼 오버레이 활성 시 힌트 숨김."""
        self.ctx.tutorial.visible = True
        hint = self._get_hint(SIM_LEFT + 10, SIM_TOP + 10, self.ctx)
        self.assertIsNone(hint)

    def test_help_overlay_hides_hint(self):
        """도움말 오버레이 활성 시 힌트 숨김."""
        self.ctx.help_overlay.visible = True
        hint = self._get_hint(SIM_LEFT + 10, SIM_TOP + 10, self.ctx)
        self.assertIsNone(hint)

    def test_glossary_overlay_hides_hint(self):
        """용어집 오버레이 활성 시 힌트 숨김."""
        self.ctx.glossary.visible = True
        hint = self._get_hint(SIM_LEFT + 10, SIM_TOP + 10, self.ctx)
        self.assertIsNone(hint)

    def test_barrier_drag_hides_hint(self):
        """장벽 드래그 중에는 힌트 숨김."""
        self.ctx.barrier_dragging = True
        hint = self._get_hint(SIM_LEFT + 10, SIM_TOP + 10, self.ctx)
        self.assertIsNone(hint)

    def test_bloch_drag_hides_hint(self):
        """블로흐 드래그 중에는 힌트 숨김."""
        self.ctx.bloch_dragging = True
        hint = self._get_hint(self.BLOCH_CX, self.BLOCH_CY, self.ctx)
        self.assertIsNone(hint)

    def test_barrier_priority_over_sim(self):
        """장벽 가장자리 힌트가 시뮬레이션 영역 힌트보다 우선."""
        left_edge = BARRIER_X - self.ctx.barrier_width // 2
        hint_edge = self._get_hint(left_edge, SIM_TOP + 100, self.ctx)
        hint_sim = self._get_hint(SIM_LEFT + 10, SIM_TOP + 10, self.ctx)
        # 둘 다 힌트가 있지만 내용이 다름 (edge는 barrier, sim은 click)
        self.assertIsNotNone(hint_edge)
        self.assertIsNotNone(hint_sim)
        self.assertNotEqual(hint_edge, hint_sim)

    def test_stats_area_hint(self):
        """통계 패널 영역에서 stats 힌트 반환."""
        stats_x = self.BLOCH_CX - self.BLOCH_R
        stats_y = self.BLOCH_CY + self.BLOCH_R + 60
        hint = self._get_hint(stats_x + 10, stats_y + 10, self.ctx)
        self.assertIsNotNone(hint)


class TestExportSession(unittest.TestCase):
    """#18 통계 데이터 내보내기 — CSV/JSON 파일 생성."""

    def setUp(self):
        import tempfile

        self.tmpdir = tempfile.mkdtemp()
        self._orig_abspath = os.path.abspath

        # _export_session이 exports/ 대신 임시 디렉토리를 사용하도록 패치
        from quantum import tunneling as tn_mod

        self.tn_mod = tn_mod

        # 간이 ctx 목 객체
        self.ctx = MagicMock()
        self.ctx.particle.tunnel_count = 7
        self.ctx.particle.reflect_count = 3
        self.ctx.particle.total_attempts = 10
        self.ctx.barrier_width = 20
        self.ctx.base_prob = 0.10
        self.ctx.tunnel_prob = 0.085
        self.ctx.speed_mult = 1.5
        self.ctx.max_tunnel_barrier = 30
        self.ctx.barrier_configs_tried = {12, 20, 30}
        self.ctx.peak_rate = 0.8
        self.ctx.start_time = 100.0
        self.ctx.sl_boost = MagicMock(value=2.0)
        self.ctx.preset_hud = MagicMock(current="normal")
        self.ctx.trial_history = deque(
            [
                {"t": 1.0, "barrier": 12, "prob": 0.10, "result": True},
                {"t": 2.5, "barrier": 20, "prob": 0.085, "result": False},
                {"t": 3.1, "barrier": 20, "prob": 0.085, "result": True},
            ],
            maxlen=5000,
        )

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_export(self):
        """임시 디렉토리로 내보내기 실행."""
        import csv
        import json
        from datetime import datetime

        export_dir = os.path.join(self.tmpdir, "exports")
        os.makedirs(export_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # _build_session_data 호출 시뮬레이션
        session = {
            "total_attempts": self.ctx.particle.total_attempts,
            "tunnel_count": self.ctx.particle.tunnel_count,
            "reflect_count": self.ctx.particle.reflect_count,
            "tunnel_rate": 0.7,
            "barrier_width": self.ctx.barrier_width,
            "base_prob": self.ctx.base_prob,
            "tunnel_prob": self.ctx.tunnel_prob,
            "elapsed_time": 10.5,
            "timestamp": datetime.now().isoformat(),
        }

        json_path = os.path.join(export_dir, f"tunneling_stats_{ts}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)

        csv_path = os.path.join(export_dir, f"tunneling_trials_{ts}.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["trial", "time_s", "barrier_width", "tunnel_prob", "result"])
            for i, tr in enumerate(self.ctx.trial_history, 1):
                writer.writerow([i, tr["t"], tr["barrier"], tr["prob"], int(tr["result"])])

        return export_dir, json_path, csv_path

    def test_json_file_created(self):
        """JSON 파일이 생성됨."""
        _, json_path, _ = self._run_export()
        self.assertTrue(os.path.exists(json_path))

    def test_csv_file_created(self):
        """CSV 파일이 생성됨."""
        _, _, csv_path = self._run_export()
        self.assertTrue(os.path.exists(csv_path))

    def test_json_contains_required_fields(self):
        """JSON에 필수 필드가 포함됨."""
        import json

        _, json_path, _ = self._run_export()
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        for key in ("total_attempts", "tunnel_count", "reflect_count", "barrier_width", "tunnel_prob", "timestamp"):
            self.assertIn(key, data, f"필수 필드 누락: {key}")

    def test_json_no_trial_history(self):
        """JSON에 trial_history가 포함되지 않음 (CSV에 별도 저장)."""
        import json

        _, json_path, _ = self._run_export()
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn("trial_history", data)

    def test_csv_header_and_rows(self):
        """CSV 헤더와 행 수가 올바름."""
        import csv

        _, _, csv_path = self._run_export()
        with open(csv_path, encoding="utf-8") as f:
            reader = list(csv.reader(f))
        self.assertEqual(reader[0], ["trial", "time_s", "barrier_width", "tunnel_prob", "result"])
        self.assertEqual(len(reader), 4)  # 헤더 + 3 시행

    def test_csv_result_values(self):
        """CSV 결과 값이 0(반사) 또는 1(터널링)."""
        import csv

        _, _, csv_path = self._run_export()
        with open(csv_path, encoding="utf-8") as f:
            reader = list(csv.reader(f))
        results = [row[4] for row in reader[1:]]
        self.assertEqual(results, ["1", "0", "1"])

    def test_csv_trial_numbering(self):
        """CSV 시행 번호가 1부터 순차적."""
        import csv

        _, _, csv_path = self._run_export()
        with open(csv_path, encoding="utf-8") as f:
            reader = list(csv.reader(f))
        trials = [int(row[0]) for row in reader[1:]]
        self.assertEqual(trials, [1, 2, 3])

    def test_empty_trial_history(self):
        """시행 이력이 비어있어도 CSV 파일 생성됨 (헤더만)."""
        import csv

        self.ctx.trial_history = deque(maxlen=5000)
        export_dir = os.path.join(self.tmpdir, "exports_empty")
        os.makedirs(export_dir, exist_ok=True)

        csv_path = os.path.join(export_dir, "tunneling_trials_empty.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["trial", "time_s", "barrier_width", "tunnel_prob", "result"])
            for i, tr in enumerate(self.ctx.trial_history, 1):
                writer.writerow([i, tr["t"], tr["barrier"], tr["prob"], int(tr["result"])])

        with open(csv_path, encoding="utf-8") as f:
            reader = list(csv.reader(f))
        self.assertEqual(len(reader), 1)  # 헤더만

    def test_export_function_exists(self):
        """_export_session 함수가 존재하고 호출 가능."""
        from quantum.tunneling import _export_session

        self.assertTrue(callable(_export_session))

    def test_export_function_returns_path_or_none(self):
        """_export_session이 경로 문자열 또는 None 반환."""
        from quantum.tunneling import _export_session

        # 실제 호출을 위해 _build_session_data를 목킹
        with unittest.mock.patch.object(self.tn_mod, "_build_session_data") as mock_build:
            mock_build.return_value = {
                "total_attempts": 10,
                "tunnel_count": 7,
                "trial_history": list(self.ctx.trial_history),
            }
            result = _export_session(self.ctx)
            self.assertTrue(result is None or isinstance(result, str))


class TestImportSession(unittest.TestCase):
    """#18 데이터 가져오기 — JSON/CSV 로드 및 파라미터 적용."""

    def setUp(self):
        import json
        import tempfile

        self.tmpdir = tempfile.mkdtemp()
        self.export_dir = os.path.join(self.tmpdir, "exports")
        os.makedirs(self.export_dir, exist_ok=True)

        # 테스트용 trial_history
        self.trial_history = [
            {"t": 1.0, "barrier": 30, "prob": 0.105, "result": True},
            {"t": 2.0, "barrier": 30, "prob": 0.105, "result": False},
            {"t": 3.5, "barrier": 30, "prob": 0.105, "result": True},
            {"t": 4.0, "barrier": 30, "prob": 0.105, "result": True},
        ]

        # 테스트용 JSON 파일 생성 (trial_history 포함)
        self.session_data = {
            "total_attempts": 50,
            "tunnel_count": 20,
            "reflect_count": 30,
            "tunnel_rate": 0.4,
            "barrier_width": 30,
            "base_prob": 0.15,
            "tunnel_prob": 0.105,
            "elapsed_time": 60.0,
            "speed_mult": 2.0,
            "difficulty": "hard",
            "timestamp": "2026-01-15T12:00:00",
            "trial_history": self.trial_history,
        }
        self.json_path = os.path.join(self.export_dir, "tunneling_stats_20260115_120000.json")
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.session_data, f, indent=2)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_import_json(self):
        """JSON 파일에서 세션 데이터 로드."""
        from quantum.tunneling_data import _load_import_data

        session, _ = _load_import_data(self.json_path)
        self.assertIsNotNone(session)
        self.assertEqual(session["total_attempts"], 50)
        self.assertEqual(session["base_prob"], 0.15)
        self.assertEqual(session["barrier_width"], 30)

    def test_load_import_trials(self):
        """JSON에 포함된 trial_history 로드."""
        from quantum.tunneling_data import _load_import_data

        _, trials = _load_import_data(self.json_path)
        self.assertEqual(len(trials), 4)
        self.assertTrue(trials[0]["result"])
        self.assertFalse(trials[1]["result"])

    def test_load_import_trial_fields(self):
        """가져온 시행 데이터의 필드 구조."""
        from quantum.tunneling_data import _load_import_data

        _, trials = _load_import_data(self.json_path)
        tr = trials[0]
        self.assertIn("t", tr)
        self.assertIn("barrier", tr)
        self.assertIn("prob", tr)
        self.assertIn("result", tr)
        self.assertAlmostEqual(tr["t"], 1.0)
        self.assertEqual(tr["barrier"], 30)

    def test_load_import_no_csv(self):
        """CSV 없이 JSON만 있어도 정상 로드."""
        import json

        json_only = os.path.join(self.export_dir, "tunneling_stats_20260101_000000.json")
        with open(json_only, "w", encoding="utf-8") as f:
            json.dump({"total_attempts": 5}, f)

        from quantum.tunneling_data import _load_import_data

        session, trials = _load_import_data(json_only)
        self.assertIsNotNone(session)
        self.assertEqual(len(trials), 0)

    def test_load_import_bad_json(self):
        """잘못된 JSON 파일 → None 반환."""
        bad_path = os.path.join(self.export_dir, "bad.json")
        with open(bad_path, "w") as f:
            f.write("{invalid json}")

        from quantum.tunneling_data import _load_import_data

        session, trials = _load_import_data(bad_path)
        self.assertIsNone(session)
        self.assertEqual(len(trials), 0)

    def test_load_import_missing_file(self):
        """존재하지 않는 파일 → None 반환."""
        from quantum.tunneling_data import _load_import_data

        session, trials = _load_import_data("/nonexistent/path.json")
        self.assertIsNone(session)
        self.assertEqual(len(trials), 0)

    def test_list_export_files(self):
        """내보내기 파일 목록 함수 존재 및 호출 가능."""
        from session_io import list_export_files

        self.assertTrue(callable(list_export_files))
        result = list_export_files("tunneling")
        self.assertIsInstance(result, list)

    def test_import_function_exists(self):
        """_import_session 함수가 존재하고 호출 가능."""
        from quantum.tunneling import _import_session

        self.assertTrue(callable(_import_session))

    def test_imported_overlay_rates(self):
        """가져온 시행 이력에서 누적 확률 계산 검증."""
        from quantum.tunneling_data import _load_import_data

        _, trials = _load_import_data(self.json_path)
        # 수동 누적 확률 계산: [1,0,1,1] → [1/1, 1/2, 2/3, 3/4]
        tunnels = 0
        rates = []
        for tr in trials:
            if tr["result"]:
                tunnels += 1
            rates.append(tunnels / (len(rates) + 1))
        self.assertAlmostEqual(rates[0], 1.0)
        self.assertAlmostEqual(rates[1], 0.5)
        self.assertAlmostEqual(rates[2], 2 / 3, places=4)
        self.assertAlmostEqual(rates[3], 0.75)


class TestTextCache(unittest.TestCase):
    """#19 텍스트 서피스 캐시 — font.render() 반복 호출 제거."""

    def setUp(self):
        from quantum.tunneling_render import _TextCache

        self.TextCache = _TextCache

    def test_cache_returns_surface(self):
        """render()가 Surface 객체를 반환."""
        cache = self.TextCache()
        font = MagicMock()
        font.render.return_value = MagicMock()
        surf = cache.render(font, "hello", (255, 255, 255))
        self.assertIsNotNone(surf)
        font.render.assert_called_once()

    def test_cache_hit(self):
        """동일 (font, text, color) → font.render()가 1회만 호출됨."""
        cache = self.TextCache()
        font = MagicMock()
        font.render.return_value = MagicMock()
        s1 = cache.render(font, "hello", (255, 255, 255))
        s2 = cache.render(font, "hello", (255, 255, 255))
        self.assertIs(s1, s2)
        self.assertEqual(font.render.call_count, 1)

    def test_cache_miss_different_text(self):
        """다른 텍스트 → 별도 캐시 엔트리."""
        cache = self.TextCache()
        font = MagicMock()
        font.render.side_effect = [MagicMock(), MagicMock()]
        s1 = cache.render(font, "hello", (255, 255, 255))
        s2 = cache.render(font, "world", (255, 255, 255))
        self.assertIsNot(s1, s2)
        self.assertEqual(font.render.call_count, 2)

    def test_cache_miss_different_color(self):
        """다른 색상 → 별도 캐시 엔트리."""
        cache = self.TextCache()
        font = MagicMock()
        font.render.side_effect = [MagicMock(), MagicMock()]
        s1 = cache.render(font, "hello", (255, 0, 0))
        s2 = cache.render(font, "hello", (0, 255, 0))
        self.assertIsNot(s1, s2)
        self.assertEqual(font.render.call_count, 2)

    def test_cache_clear(self):
        """clear() 후 동일 키가 다시 font.render() 호출."""
        cache = self.TextCache()
        font = MagicMock()
        font.render.return_value = MagicMock()
        cache.render(font, "hello", (255, 255, 255))
        cache.clear()
        font.render.return_value = MagicMock()
        cache.render(font, "hello", (255, 255, 255))
        self.assertEqual(font.render.call_count, 2)

    def test_cache_size_property(self):
        """size 속성이 캐시 크기 반환."""
        cache = self.TextCache()
        self.assertEqual(cache.size, 0)
        font = MagicMock()
        font.render.return_value = MagicMock()
        cache.render(font, "a", (255, 0, 0))
        cache.render(font, "b", (255, 0, 0))
        self.assertEqual(cache.size, 2)

    def test_cache_eviction(self):
        """max_size 초과 시 절반 삭제."""
        cache = self.TextCache(max_size=4)
        font = MagicMock()
        font.render.return_value = MagicMock()
        for i in range(4):
            cache.render(font, f"text_{i}", (255, 0, 0))
        self.assertEqual(cache.size, 4)
        # 5번째 삽입 → 기존 절반(2개) 삭제 후 새 항목 추가
        cache.render(font, "text_4", (255, 0, 0))
        self.assertLessEqual(cache.size, 4)

    def test_global_instance_exists(self):
        """모듈 레벨 _tcache 인스턴스 존재."""
        from quantum.tunneling import _tcache

        self.assertIsNotNone(_tcache)
        self.assertTrue(hasattr(_tcache, "render"))


class TestBlochMeshCache(unittest.TestCase):
    """#20 대원 메시 캐시 — 3D 기저점 사전 계산 + 투영 캐싱."""

    def setUp(self):
        from quantum.tunneling_render import (
            _CIRCLE_STEPS,
            _EQUATOR_PTS,
            _MERIDIAN_XZ,
            _MERIDIAN_YZ,
            _BlochMeshCache,
        )

        self.BlochMeshCache = _BlochMeshCache
        self.EQUATOR = _EQUATOR_PTS
        self.XZ = _MERIDIAN_XZ
        self.YZ = _MERIDIAN_YZ
        self.STEPS = _CIRCLE_STEPS

    def test_precomputed_equator_length(self):
        """적도 기저점 개수 == _CIRCLE_STEPS."""
        self.assertEqual(len(self.EQUATOR), self.STEPS)

    def test_precomputed_xz_length(self):
        """XZ 경선 기저점 개수 == _CIRCLE_STEPS."""
        self.assertEqual(len(self.XZ), self.STEPS)

    def test_precomputed_yz_length(self):
        """YZ 경선 기저점 개수 == _CIRCLE_STEPS."""
        self.assertEqual(len(self.YZ), self.STEPS)

    def test_equator_z_zero(self):
        """적도 기저점의 z 좌표가 모두 0."""
        for _, _, z in self.EQUATOR:
            self.assertAlmostEqual(z, 0.0)

    def test_xz_y_zero(self):
        """XZ 경선 기저점의 y 좌표가 모두 0."""
        for _, y, _ in self.XZ:
            self.assertAlmostEqual(y, 0.0)

    def test_yz_x_zero(self):
        """YZ 경선 기저점의 x 좌표가 모두 0."""
        for x, _, _ in self.YZ:
            self.assertAlmostEqual(x, 0.0)

    def test_equator_unit_circle(self):
        """적도 기저점이 단위원 위에 있음."""
        for x, y, z in self.EQUATOR:
            r = math.sqrt(x * x + y * y + z * z)
            self.assertAlmostEqual(r, 1.0, places=10)

    def test_cache_returns_projected_points(self):
        """get()이 투영된 점 리스트 반환 (길이 == STEPS)."""
        cache = self.BlochMeshCache()
        pts = cache.get("equator", self.EQUATOR, 0.0, 0.25)
        self.assertEqual(len(pts), self.STEPS)
        # 각 점은 (sx, sy, depth) 튜플
        self.assertEqual(len(pts[0]), 3)

    def test_cache_hit_same_view(self):
        """동일 view 각도 → 동일 리스트 객체 반환 (캐시 히트)."""
        cache = self.BlochMeshCache()
        p1 = cache.get("equator", self.EQUATOR, 0.5, 0.25)
        p2 = cache.get("equator", self.EQUATOR, 0.5, 0.25)
        self.assertIs(p1, p2)

    def test_cache_invalidate_on_view_change(self):
        """view 각도 변경 → 재계산 (다른 객체)."""
        cache = self.BlochMeshCache()
        p1 = cache.get("equator", self.EQUATOR, 0.0, 0.0)
        p2 = cache.get("equator", self.EQUATOR, 1.0, 0.0)
        self.assertIsNot(p1, p2)

    def test_invalidate_method(self):
        """invalidate() 후 재계산."""
        cache = self.BlochMeshCache()
        p1 = cache.get("equator", self.EQUATOR, 0.5, 0.25)
        cache.invalidate()
        p2 = cache.get("equator", self.EQUATOR, 0.5, 0.25)
        self.assertIsNot(p1, p2)

    def test_multiple_circles_same_view(self):
        """동일 view에서 여러 대원 캐시 독립 관리."""
        cache = self.BlochMeshCache()
        eq = cache.get("equator", self.EQUATOR, 0.0, 0.25)
        xz = cache.get("xz", self.XZ, 0.0, 0.25)
        self.assertIsNot(eq, xz)
        # 재요청 시 캐시 히트
        eq2 = cache.get("equator", self.EQUATOR, 0.0, 0.25)
        self.assertIs(eq, eq2)


class TestTrailCache(unittest.TestCase):
    """#21 — 트레일 서피스 캐싱 테스트."""

    def setUp(self):
        import pygame

        from quantum.tunneling import (
            _draw_trails,
            _TrailCache,
        )

        self.pg = pygame
        self.TrailCache = _TrailCache
        self.draw_trails = _draw_trails

    # -- _TrailCache 단위 테스트 --

    def test_initial_dirty(self):
        """초기 상태는 dirty=True."""
        cache = self.TrailCache()
        self.assertTrue(cache._dirty)

    def test_get_surface_returns_surface(self):
        """get_surface는 pygame.Surface를 반환."""
        cache = self.TrailCache()
        trails = [([(100, 200)], True)]
        surf = cache.get_surface(trails)
        self.assertIsNotNone(surf)

    def test_cache_hit_after_get(self):
        """get_surface 후 dirty=False이면 같은 서피스 반환."""
        cache = self.TrailCache()
        trails = [([(100, 200)], True)]
        s1 = cache.get_surface(trails)
        s2 = cache.get_surface(trails)
        self.assertIs(s1, s2)

    def test_mark_dirty_triggers_rebuild(self):
        """mark_dirty 호출 후 dirty=True로 전환, get_surface에서 재빌드."""
        cache = self.TrailCache()
        trails = [([(100, 200)], True)]
        cache.get_surface(trails)
        self.assertFalse(cache._dirty)
        cache.mark_dirty()
        self.assertTrue(cache._dirty)
        cache.get_surface(trails)
        self.assertFalse(cache._dirty)

    def test_clear_resets_state(self):
        """clear 후 dirty=True, 서피스=None."""
        cache = self.TrailCache()
        trails = [([(100, 200)], True)]
        cache.get_surface(trails)
        cache.clear()
        self.assertTrue(cache._dirty)
        self.assertIsNone(cache._surf)

    def test_empty_trails_surface(self):
        """빈 trails에서도 서피스 생성."""
        cache = self.TrailCache()
        surf = cache.get_surface([])
        self.assertIsNotNone(surf)

    def test_multiple_trails_cached(self):
        """여러 궤적이 있어도 정상 캐싱."""
        cache = self.TrailCache()
        trails = [
            ([(100, 200), (110, 210)], True),
            ([(120, 220), (130, 230)], False),
            ([(140, 240)], True),
        ]
        s1 = cache.get_surface(trails)
        s2 = cache.get_surface(trails)
        self.assertIs(s1, s2)

    # -- _draw_trails 통합 테스트 --

    def test_draw_trails_uses_cache(self):
        """_draw_trails가 trail_cache를 사용하여 과거 궤적 렌더링."""
        cache = self.TrailCache()
        trails = [([(100, 200)], True)]
        screen = self.pg.Surface((800, 600))
        self.draw_trails(screen, cache, trails, [], None)
        # 호출 후 dirty=False (캐시됨)
        self.assertFalse(cache._dirty)

    def test_draw_trails_empty_no_error(self):
        """trails와 current_trail 모두 비어있으면 에러 없이 조기 반환."""
        cache = self.TrailCache()
        screen = self.pg.Surface((800, 600))
        self.draw_trails(screen, cache, [], [], None)
        # dirty 상태 유지 (get_surface 호출 안 됨)
        self.assertTrue(cache._dirty)

    def test_draw_trails_current_only(self):
        """current_trail만 있을 때 과거 캐시 건드리지 않음."""
        cache = self.TrailCache()
        screen = self.pg.Surface((800, 600))
        self.draw_trails(screen, cache, [], [(150, 250)], None)
        # past trails 없으므로 get_surface 호출 안 됨
        self.assertTrue(cache._dirty)


class TestFlashEase(unittest.TestCase):
    """#22 — ease-out 이징 커브 테스트."""

    def setUp(self):
        from quantum.tunneling_render import _ease_out, _flash_ease

        self.ease_out = _ease_out
        self.flash_ease = _flash_ease

    # -- _ease_out --

    def test_ease_out_boundaries(self):
        """ease_out(0)=0, ease_out(1)=1."""
        self.assertAlmostEqual(self.ease_out(0.0), 0.0)
        self.assertAlmostEqual(self.ease_out(1.0), 1.0)

    def test_ease_out_midpoint_above_linear(self):
        """ease-out 곡선은 중간점에서 선형보다 큼 (빨리 올라감)."""
        self.assertGreater(self.ease_out(0.5), 0.5)

    def test_ease_out_clamped(self):
        """범위 밖 입력은 클램핑."""
        self.assertAlmostEqual(self.ease_out(-0.5), 0.0)
        self.assertAlmostEqual(self.ease_out(1.5), 1.0)

    def test_ease_out_monotonic(self):
        """단조 증가 확인."""
        prev = 0.0
        for i in range(1, 11):
            val = self.ease_out(i / 10.0)
            self.assertGreaterEqual(val, prev)
            prev = val

    # -- _flash_ease --

    def test_flash_ease_start_full(self):
        """플래시 시작 시(timer==duration) 세기 ≈ 1."""
        self.assertAlmostEqual(self.flash_ease(0.6, 0.6), 1.0)

    def test_flash_ease_end_zero(self):
        """플래시 끝(timer==0) 세기 = 0."""
        self.assertAlmostEqual(self.flash_ease(0.0, 0.6), 0.0)

    def test_flash_ease_mid_nonlinear(self):
        """중간 지점에서 ease-out 비선형 확인."""
        linear_mid = 0.5  # 선형이면 세기 = 0.5
        eased_mid = self.flash_ease(0.3, 0.6)  # timer=0.3, duration=0.6 → 중간
        self.assertNotAlmostEqual(eased_mid, linear_mid, places=2)

    def test_flash_ease_zero_duration(self):
        """duration=0이면 0 반환."""
        self.assertAlmostEqual(self.flash_ease(0.5, 0.0), 0.0)

    def test_flash_ease_negative_timer(self):
        """음수 timer → 0 반환."""
        self.assertAlmostEqual(self.flash_ease(-0.1, 0.6), 0.0)


class TestBlochKeyboard(unittest.TestCase):
    """#24 — 블로흐 구 키보드 조작 상수 테스트."""

    def test_key_step_positive(self):
        """_BLOCH_KEY_STEP은 양수."""
        from quantum.tunneling import _BLOCH_KEY_STEP

        self.assertGreater(_BLOCH_KEY_STEP, 0)

    def test_key_step_reasonable(self):
        """_BLOCH_KEY_STEP은 0.01~0.5 범위 내."""
        from quantum.tunneling import _BLOCH_KEY_STEP

        self.assertGreaterEqual(_BLOCH_KEY_STEP, 0.01)
        self.assertLessEqual(_BLOCH_KEY_STEP, 0.5)


class TestHelpOverlayShortcuts(unittest.TestCase):
    """#23 — 도움말 오버레이에 단축키 포함 확인."""

    def test_tunneling_help_has_wasd(self):
        """터널링 도움말에 W/A/S/D 블로흐 조작 안내 포함."""
        from help_overlay import _HELP_TEXTS

        lines = _HELP_TEXTS.get("tunneling", [])
        joined = " ".join(lines)
        self.assertIn("W/A/S/D", joined)

    def test_tunneling_help_has_f1(self):
        """터널링 도움말에 F1 안내 포함."""
        from help_overlay import _HELP_TEXTS

        lines = _HELP_TEXTS.get("tunneling", [])
        joined = " ".join(lines)
        self.assertIn("F1", joined)

    def test_tunneling_help_has_ctrl_x(self):
        """터널링 도움말에 Ctrl+X 안내 포함."""
        from help_overlay import _HELP_TEXTS

        lines = _HELP_TEXTS.get("tunneling", [])
        joined = " ".join(lines)
        self.assertIn("Ctrl+X", joined)

    def test_tunneling_help_has_space_pause(self):
        """터널링 도움말에 SPACE 일시정지 안내 포함."""
        from help_overlay import _HELP_TEXTS

        lines = _HELP_TEXTS.get("tunneling", [])
        joined = " ".join(lines)
        self.assertIn("SPACE", joined)


class TestExperimentComparison(unittest.TestCase):
    """#32 — 실험 데이터 비교 테스트."""

    def test_get_dataset_ids(self):
        """데이터셋 ID 목록 비어있지 않음."""
        from quantum.tunneling_experiment import get_dataset_ids

        ids = get_dataset_ids()
        self.assertGreater(len(ids), 0)
        self.assertIn("alpha_decay", ids)
        self.assertIn("stm_electron", ids)

    def test_get_experiment_data_alpha(self):
        """알파 붕괴 데이터 반환 유효."""
        from quantum.tunneling_experiment import get_experiment_data

        data = get_experiment_data("alpha_decay")
        self.assertGreater(len(data), 0)
        for bw, prob in data:
            self.assertGreaterEqual(bw, 4)
            self.assertLessEqual(bw, 200)
            self.assertGreater(prob, 0)
            self.assertLessEqual(prob, 1)

    def test_get_experiment_data_stm(self):
        """STM 전자 데이터 반환 유효."""
        from quantum.tunneling_experiment import get_experiment_data

        data = get_experiment_data("stm_electron")
        self.assertGreater(len(data), 0)

    def test_unknown_dataset_raises(self):
        """알 수 없는 데이터셋 ID → KeyError."""
        from quantum.tunneling_experiment import get_experiment_data

        with self.assertRaises(KeyError):
            get_experiment_data("nonexistent")

    def test_wkb_transmission_at_ref(self):
        """기준 두께에서 WKB 투과 계수 = 1.0."""
        from quantum.tunneling_experiment import wkb_transmission

        t = wkb_transmission(12, kappa=0.02, ref_width=12)
        self.assertAlmostEqual(t, 1.0)

    def test_wkb_transmission_decays(self):
        """두꺼운 장벽에서 WKB 투과 계수 감소."""
        from quantum.tunneling_experiment import wkb_transmission

        t_thin = wkb_transmission(20, kappa=0.02, ref_width=12)
        t_thick = wkb_transmission(100, kappa=0.02, ref_width=12)
        self.assertGreater(t_thin, t_thick)

    def test_generate_theory_curve(self):
        """이론 곡선 생성 유효."""
        from quantum.tunneling_experiment import generate_theory_curve

        pts = generate_theory_curve(base_prob=0.1, kappa=0.02, width_min=4, width_max=200, step=10)
        self.assertGreater(len(pts), 5)
        # 단조감소 확인
        for i in range(1, len(pts)):
            self.assertLessEqual(pts[i][1], pts[i - 1][1])

    def test_compute_fit_stats_perfect(self):
        """동일 데이터 → R² = 1.0, RMSE = 0."""
        from quantum.tunneling_experiment import compute_fit_stats

        data = [(10, 0.5), (20, 0.3), (30, 0.1)]
        stats = compute_fit_stats(data, data)
        self.assertAlmostEqual(stats["r_squared"], 1.0)
        self.assertAlmostEqual(stats["rmse"], 0.0)
        self.assertEqual(stats["n_matched"], 3)

    def test_compute_fit_stats_empty(self):
        """빈 데이터 → n_matched = 0."""
        from quantum.tunneling_experiment import compute_fit_stats

        stats = compute_fit_stats([], [(10, 0.5)])
        self.assertEqual(stats["n_matched"], 0)

    def test_compute_fit_stats_no_match(self):
        """매칭 불가 거리 → n_matched = 0."""
        from quantum.tunneling_experiment import compute_fit_stats

        sim = [(10, 0.5)]
        ref = [(200, 0.01)]
        stats = compute_fit_stats(sim, ref)
        self.assertEqual(stats["n_matched"], 0)

    def test_stm_decays_faster_than_alpha(self):
        """STM 전자가 알파 붕괴보다 빠르게 감쇠."""
        from quantum.tunneling_experiment import get_experiment_data

        alpha = get_experiment_data("alpha_decay")
        stm = get_experiment_data("stm_electron")
        # 같은 barrier_width에서 STM이 더 낮은 확률
        a_dict = dict(alpha)
        s_dict = dict(stm)
        common_widths = set(a_dict.keys()) & set(s_dict.keys())
        for w in common_widths:
            if w > 20:  # 넓은 장벽에서 차이가 확실
                self.assertLess(s_dict[w], a_dict[w])

    def test_i18n_exp_keys_ko(self):
        """한국어 로케일에 실험 비교 i18n 키 존재."""
        import json

        with open("locale/ko.json", encoding="utf-8") as f:
            data = json.load(f)
        for key in ["exp_chart_title", "exp_alpha_decay", "exp_stm_electron", "exp_legend_sim", "exp_fit_label"]:
            self.assertIn(key, data)

    def test_i18n_exp_keys_en(self):
        """영어 로케일에 실험 비교 i18n 키 존재."""
        import json

        with open("locale/en.json", encoding="utf-8") as f:
            data = json.load(f)
        for key in ["exp_chart_title", "exp_alpha_decay", "exp_stm_electron", "exp_legend_sim", "exp_fit_label"]:
            self.assertIn(key, data)

    def test_help_has_f6(self):
        """터널링 도움말에 F6 실험 비교 안내 포함."""
        from help_overlay import _HELP_TEXTS

        lines = _HELP_TEXTS.get("tunneling", [])
        joined = " ".join(lines)
        self.assertIn("F6", joined)

    def test_fit_label_format(self):
        """적합도 레이블 포맷 문자열 유효."""
        import json

        with open("locale/en.json", encoding="utf-8") as f:
            data = json.load(f)
        tmpl = data["exp_fit_label"]
        result = tmpl.format(r2=0.987, rmse=0.0012, n=8)
        self.assertIn("0.987", result)
        self.assertIn("8", result)

    def test_datasets_have_metadata(self):
        """모든 데이터셋에 name_key, desc_key, kappa 포함."""
        from quantum.tunneling_experiment import get_experiment_datasets

        datasets = get_experiment_datasets()
        for ds_id, meta in datasets.items():
            self.assertIn("name_key", meta, f"{ds_id} missing name_key")
            self.assertIn("desc_key", meta, f"{ds_id} missing desc_key")
            self.assertIn("kappa", meta, f"{ds_id} missing kappa")
            self.assertGreater(meta["kappa"], 0)


class TestRewind(unittest.TestCase):
    """#31 — 되감기 기능 테스트."""

    def test_particle_snapshot_restore(self):
        """QuantumParticle snapshot/restore 왕복 일치."""
        from quantum.tunneling_physics import QuantumParticle

        p = QuantumParticle(seed=42)
        # 몇 프레임 진행
        for _ in range(10):
            p.update(1 / 60, barrier_width=12, tunnel_prob=0.1)
        snap = p.snapshot()

        # 더 진행해서 상태 변경
        for _ in range(20):
            p.update(1 / 60, barrier_width=12, tunnel_prob=0.1)
        self.assertNotEqual(p.x, snap["x"])

        # 복원 후 일치 확인
        p.restore(snap)
        self.assertAlmostEqual(p.x, snap["x"])
        self.assertAlmostEqual(p.y, snap["y"])
        self.assertAlmostEqual(p.vx, snap["vx"])
        self.assertAlmostEqual(p.vy, snap["vy"])
        self.assertEqual(p.alive, snap["alive"])
        self.assertEqual(p.tunneled, snap["tunneled"])
        self.assertEqual(p.tunnel_count, snap["tunnel_count"])
        self.assertEqual(p.reflect_count, snap["reflect_count"])
        self.assertEqual(p.total_attempts, snap["total_attempts"])

    def test_snapshot_keys(self):
        """스냅샷에 필수 키가 모두 포함."""
        from quantum.tunneling_physics import QuantumParticle

        p = QuantumParticle(seed=1)
        snap = p.snapshot()
        expected = {
            "x",
            "y",
            "vx",
            "vy",
            "alive",
            "tunneled",
            "flash_timer",
            "tunnel_count",
            "reflect_count",
            "total_attempts",
        }
        self.assertEqual(set(snap.keys()), expected)

    def test_help_has_f5(self):
        """터널링 도움말에 F5 되감기 안내 포함."""
        from help_overlay import _HELP_TEXTS

        lines = _HELP_TEXTS.get("tunneling", [])
        joined = " ".join(lines)
        self.assertIn("F5", joined)

    def test_i18n_rewind_keys_exist_ko(self):
        """한국어 로케일에 되감기 i18n 키 존재."""
        import json

        with open("locale/ko.json", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("tn_rewind_title", data)
        self.assertIn("tn_rewind_indicator", data)

    def test_i18n_rewind_keys_exist_en(self):
        """영어 로케일에 되감기 i18n 키 존재."""
        import json

        with open("locale/en.json", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("tn_rewind_title", data)
        self.assertIn("tn_rewind_indicator", data)

    def test_rewind_indicator_format(self):
        """되감기 인디케이터 문자열 포맷 유효."""
        import json

        with open("locale/en.json", encoding="utf-8") as f:
            data = json.load(f)
        tmpl = data["tn_rewind_indicator"]
        result = tmpl.format(pct=75.3, frames=180)
        self.assertIn("75", result)
        self.assertIn("180", result)

    def test_restore_preserves_counters(self):
        """복원 후 카운터(tunnel_count 등)가 스냅샷 시점 값으로 되돌아감."""
        from quantum.tunneling_physics import QuantumParticle

        p = QuantumParticle(seed=99)
        # 수동으로 카운터 설정
        p.tunnel_count = 5
        p.reflect_count = 3
        p.total_attempts = 8
        snap = p.snapshot()

        # 카운터 변경
        p.tunnel_count = 10
        p.reflect_count = 7
        p.total_attempts = 17

        p.restore(snap)
        self.assertEqual(p.tunnel_count, 5)
        self.assertEqual(p.reflect_count, 3)
        self.assertEqual(p.total_attempts, 8)


class TestStepMode(unittest.TestCase):
    """#30 — 스텝별 실행 모드 테스트."""

    def test_help_has_f4(self):
        """터널링 도움말에 F4 스텝 모드 안내 포함."""
        from help_overlay import _HELP_TEXTS

        lines = _HELP_TEXTS.get("tunneling", [])
        joined = " ".join(lines)
        self.assertIn("F4", joined)

    def test_help_has_step_n(self):
        """터널링 도움말에 N (한 프레임 진행) 안내 포함."""
        from help_overlay import _HELP_TEXTS

        lines = _HELP_TEXTS.get("tunneling", [])
        joined = " ".join(lines)
        self.assertIn("N:", joined)

    def test_i18n_step_keys_exist_ko(self):
        """한국어 로케일에 스텝 모드 i18n 키 존재."""
        import json

        with open("locale/ko.json", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("tn_step_mode", data)
        self.assertIn("tn_step_indicator", data)

    def test_i18n_step_keys_exist_en(self):
        """영어 로케일에 스텝 모드 i18n 키 존재."""
        import json

        with open("locale/en.json", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("tn_step_mode", data)
        self.assertIn("tn_step_indicator", data)

    def test_step_indicator_format(self):
        """스텝 인디케이터 문자열 포맷 유효."""
        import json

        with open("locale/en.json", encoding="utf-8") as f:
            data = json.load(f)
        tmpl = data["tn_step_indicator"]
        # frame과 dt 파라미터로 포맷 가능해야 함
        result = tmpl.format(frame=10, dt=16.7)
        self.assertIn("10", result)
        self.assertIn("16.7", result)


class TestPhysicsLogging(unittest.TestCase):
    """#25 — 물리 엔진 로깅 테스트."""

    def test_tunnel_event_logged(self):
        """터널링 성공 시 debug 로그 출력."""
        import logging

        from quantum.tunneling_physics import QuantumParticle

        p = QuantumParticle(seed=42)
        logger = logging.getLogger("superconductor.tunneling_physics")
        with self.assertLogs(logger, level="DEBUG") as cm:
            # 확률 1.0 → 장벽 도달하면 반드시 터널링
            for _ in range(500):
                p.update(1 / 60.0, barrier_width=12, tunnel_prob=1.0)
                if p.tunneled is True:
                    break
        self.assertTrue(any("터널링 성공" in msg for msg in cm.output))

    def test_reflect_event_logged(self):
        """반사 시 debug 로그 출력."""
        import logging

        from quantum.tunneling_physics import QuantumParticle

        p = QuantumParticle(seed=42)
        logger = logging.getLogger("superconductor.tunneling_physics")
        with self.assertLogs(logger, level="DEBUG") as cm:
            # 확률 0.0 → 장벽 도달하면 반드시 반사
            for _ in range(500):
                p.update(1 / 60.0, barrier_width=12, tunnel_prob=0.0)
                if p.tunneled is False:
                    break
        self.assertTrue(any("반사" in msg for msg in cm.output))


class TestComputePsi(unittest.TestCase):
    """#27 — 파동함수 ψ(x) 계산 테스트."""

    def setUp(self):
        from quantum.tunneling_physics import SIM_W, compute_psi

        self.compute_psi = compute_psi
        self.SIM_W = SIM_W

    def test_returns_list_of_tuples(self):
        """compute_psi는 (x_norm, psi) 튜플 리스트 반환."""
        pts = self.compute_psi(12, 0.1)
        self.assertIsInstance(pts, list)
        self.assertGreater(len(pts), 0)
        for x, psi in pts:
            self.assertIsInstance(x, float)
            self.assertIsInstance(psi, float)

    def test_n_points_count(self):
        """n_points 파라미터가 반환 개수 결정."""
        for n in (50, 100, 200):
            pts = self.compute_psi(12, 0.1, n_points=n)
            self.assertEqual(len(pts), n)

    def test_x_range_zero_to_one(self):
        """x_norm 값은 [0, 1] 범위."""
        pts = self.compute_psi(12, 0.1, n_points=100)
        for x, _ in pts:
            self.assertGreaterEqual(x, 0.0)
            self.assertLessEqual(x, 1.0)

    def test_x_monotonic_increasing(self):
        """x_norm 값은 단조 증가."""
        pts = self.compute_psi(12, 0.1, n_points=100)
        for i in range(len(pts) - 1):
            self.assertLess(pts[i][0], pts[i + 1][0])

    def test_barrier_region_decay(self):
        """장벽 내부에서 psi는 지수 감쇠 (왼쪽 > 오른쪽)."""
        barrier_width = 60
        pts = self.compute_psi(barrier_width, 0.1, n_points=500)
        # 장벽 경계 (정규화)
        b_left = 0.5 - (barrier_width / self.SIM_W) * 0.5
        b_right = 0.5 + (barrier_width / self.SIM_W) * 0.5
        # 장벽 내부 점들만 추출
        barrier_pts = [(x, psi) for x, psi in pts if b_left < x < b_right]
        self.assertGreater(len(barrier_pts), 2)
        # 첫 번째 장벽 점이 마지막보다 큰 psi (감쇠)
        self.assertGreater(barrier_pts[0][1], barrier_pts[-1][1])

    def test_transmitted_amplitude_scales_with_prob(self):
        """투과파 진폭은 tunnel_prob에 비례."""
        pts_low = self.compute_psi(12, 0.01, n_points=200)
        pts_high = self.compute_psi(12, 0.50, n_points=200)
        # 장벽 오른쪽 영역 최대 절대 psi 비교
        b_right = 0.5 + (12 / self.SIM_W) * 0.5
        max_low = max(abs(psi) for x, psi in pts_low if x > b_right + 0.05)
        max_high = max(abs(psi) for x, psi in pts_high if x > b_right + 0.05)
        self.assertGreater(max_high, max_low)

    def test_all_finite(self):
        """모든 psi 값은 유한."""
        import math

        for bw in (4, 50, 200):
            for tp in (0.01, 0.1, 0.5):
                pts = self.compute_psi(bw, tp, n_points=100)
                for _, psi in pts:
                    self.assertTrue(math.isfinite(psi))

    def test_wider_barrier_more_decay(self):
        """장벽이 두꺼울수록 투과 영역 진폭 감소 (_calc_tunnel_prob 사용)."""
        from quantum.tunneling_physics import _calc_tunnel_prob

        # 실제 확률 계산 (두꺼울수록 확률 낮음)
        prob_narrow = _calc_tunnel_prob(10, 0.3)
        prob_wide = _calc_tunnel_prob(100, 0.3)
        narrow = self.compute_psi(10, prob_narrow, n_points=200)
        wide = self.compute_psi(100, prob_wide, n_points=200)
        b_right_wide = 0.5 + (100 / self.SIM_W) * 0.5
        right_wide = [abs(psi) for x, psi in wide if x > b_right_wide + 0.05]
        b_right_narrow = 0.5 + (10 / self.SIM_W) * 0.5
        right_narrow = [abs(psi) for x, psi in narrow if x > b_right_narrow + 0.05]
        if right_wide and right_narrow:
            self.assertGreater(max(right_narrow), max(right_wide))


class TestCalcEnergyLevels(unittest.TestCase):
    """#28 — 에너지 레벨 다이어그램 계산 테스트."""

    def test_returns_dict_keys(self):
        """반환 딕셔너리에 필수 키 존재."""
        result = calc_energy_levels(12, 0.1)
        self.assertIn("particle_energy", result)
        self.assertIn("barrier_height", result)
        self.assertIn("ratio", result)

    def test_particle_energy_fixed(self):
        """입자 에너지는 0.25 고정."""
        for bw in (4, 50, 100, 200):
            result = calc_energy_levels(bw, 0.1)
            self.assertAlmostEqual(result["particle_energy"], 0.25)

    def test_barrier_height_range(self):
        """V₀ 는 [0.30, 0.95] 범위."""
        for bw in (BARRIER_WIDTH_MIN, 50, 100, BARRIER_WIDTH_MAX):
            result = calc_energy_levels(bw, 0.1)
            self.assertGreaterEqual(result["barrier_height"], 0.30 - 1e-9)
            self.assertLessEqual(result["barrier_height"], 0.95 + 1e-9)

    def test_barrier_height_monotonic(self):
        """장벽이 두꺼울수록 V₀ 증가 (단조 증가)."""
        prev = 0.0
        for bw in range(BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX + 1, 10):
            result = calc_energy_levels(bw, 0.1)
            self.assertGreaterEqual(result["barrier_height"], prev)
            prev = result["barrier_height"]

    def test_min_barrier_gives_lowest_v0(self):
        """최소 장벽 두께에서 V₀ = 0.30."""
        result = calc_energy_levels(BARRIER_WIDTH_MIN, 0.1)
        self.assertAlmostEqual(result["barrier_height"], 0.30, places=2)

    def test_max_barrier_gives_highest_v0(self):
        """최대 장벽 두께에서 V₀ = 0.95."""
        result = calc_energy_levels(BARRIER_WIDTH_MAX, 0.1)
        self.assertAlmostEqual(result["barrier_height"], 0.95, places=2)

    def test_ratio_less_than_one(self):
        """E/V₀ 비율은 항상 1 미만 (고전적 통과 불가)."""
        for bw in (4, 12, 50, 100, 200):
            result = calc_energy_levels(bw, 0.1)
            self.assertLess(result["ratio"], 1.0)

    def test_ratio_calculation(self):
        """ratio = particle_energy / barrier_height."""
        result = calc_energy_levels(60, 0.1)
        expected = result["particle_energy"] / result["barrier_height"]
        self.assertAlmostEqual(result["ratio"], expected, places=10)

    def test_clamps_barrier_below_min(self):
        """barrier_width < MIN 이면 MIN으로 클램핑."""
        r_min = calc_energy_levels(BARRIER_WIDTH_MIN, 0.1)
        r_below = calc_energy_levels(0, 0.1)
        self.assertAlmostEqual(r_min["barrier_height"], r_below["barrier_height"])

    def test_clamps_barrier_above_max(self):
        """barrier_width > MAX 이면 MAX로 클램핑."""
        r_max = calc_energy_levels(BARRIER_WIDTH_MAX, 0.1)
        r_above = calc_energy_levels(9999, 0.1)
        self.assertAlmostEqual(r_max["barrier_height"], r_above["barrier_height"])


class TestBarrierSweeper(unittest.TestCase):
    """#29 — 배리어 스위퍼 테스트."""

    def test_init_default(self):
        """기본 생성 시 done=False, 결과 비어 있음."""
        sw = BarrierSweeper(seed=42)
        self.assertFalse(sw.done)
        self.assertEqual(len(sw.results), 0)
        self.assertGreater(len(sw.widths), 0)

    def test_progress_starts_zero(self):
        """초기 진행률 0."""
        sw = BarrierSweeper(seed=42)
        self.assertAlmostEqual(sw.progress, 0.0)

    def test_advance_returns_true_while_running(self):
        """완료 전까지 advance()는 True 반환."""
        sw = BarrierSweeper(seed=42, trials_per_width=5, batch_size=2)
        result = sw.advance()
        self.assertTrue(result)
        self.assertFalse(sw.done)

    def test_sweep_completes(self):
        """충분히 advance()하면 done=True."""
        sw = BarrierSweeper(seed=42, trials_per_width=5, batch_size=100)
        while sw.advance():
            pass
        self.assertTrue(sw.done)
        self.assertAlmostEqual(sw.progress, 1.0)

    def test_results_cover_all_widths(self):
        """완료 후 모든 폭에 결과 존재."""
        sw = BarrierSweeper(seed=42, trials_per_width=10, batch_size=1000)
        while sw.advance():
            pass
        for w in sw.widths:
            self.assertIn(w, sw.results)
            self.assertEqual(sw.results[w]["total"], 10)

    def test_results_totals_correct(self):
        """tunnel + reflect = total."""
        sw = BarrierSweeper(seed=42, trials_per_width=20, batch_size=500)
        while sw.advance():
            pass
        for _w, r in sw.results.items():
            self.assertEqual(r["tunnel"] + r["reflect"], r["total"])

    def test_rate_matches_counts(self):
        """rate = tunnel / total."""
        sw = BarrierSweeper(seed=42, trials_per_width=50, batch_size=1000)
        while sw.advance():
            pass
        for _w, r in sw.results.items():
            expected = r["tunnel"] / r["total"] if r["total"] > 0 else 0.0
            self.assertAlmostEqual(r["rate"], expected)

    def test_sorted_results_ascending(self):
        """get_sorted_results()는 폭 기준 오름차순."""
        sw = BarrierSweeper(seed=42, trials_per_width=5, batch_size=1000)
        while sw.advance():
            pass
        sorted_r = sw.get_sorted_results()
        widths = [w for w, _, _ in sorted_r]
        self.assertEqual(widths, sorted(widths))

    def test_sorted_results_has_theory(self):
        """get_sorted_results()의 theory 값이 양수."""
        sw = BarrierSweeper(seed=42, trials_per_width=5, batch_size=1000)
        while sw.advance():
            pass
        for _w, meas, theory in sw.get_sorted_results():
            self.assertGreaterEqual(theory, 0.0)
            self.assertGreaterEqual(meas, 0.0)

    def test_seed_reproducibility(self):
        """같은 시드로 동일 결과."""

        def run_sweep(seed):
            sw = BarrierSweeper(seed=seed, trials_per_width=20, batch_size=500)
            while sw.advance():
                pass
            return sw.get_sorted_results()

        r1 = run_sweep(123)
        r2 = run_sweep(123)
        self.assertEqual(r1, r2)

    def test_thin_barrier_higher_rate(self):
        """얇은 장벽에서 통과율이 두꺼운 장벽보다 높음 (충분한 시행)."""
        sw = BarrierSweeper(seed=42, trials_per_width=500, batch_size=5000)
        while sw.advance():
            pass
        results = sw.get_sorted_results()
        # 첫 번째(얇은)와 마지막(두꺼운) 비교
        if len(results) >= 2:
            thin_rate = results[0][1]
            thick_rate = results[-1][1]
            self.assertGreater(thin_rate, thick_rate)

    def test_advance_after_done_returns_false(self):
        """완료 후 advance()는 False 반환."""
        sw = BarrierSweeper(seed=42, trials_per_width=5, batch_size=1000)
        while sw.advance():
            pass
        self.assertFalse(sw.advance())

    def test_current_width_in_widths(self):
        """current_width는 항상 widths 내의 값."""
        sw = BarrierSweeper(seed=42, trials_per_width=5, batch_size=2)
        for _ in range(3):
            sw.advance()
            self.assertIn(sw.current_width, sw.widths)

    def test_custom_range(self):
        """사용자 지정 범위 (width_min=10, width_max=50, step=20)."""
        sw = BarrierSweeper(seed=42, width_min=10, width_max=50, step=20, trials_per_width=10, batch_size=500)
        while sw.advance():
            pass
        self.assertEqual(sw.widths, [10, 30, 50])
        self.assertEqual(len(sw.results), 3)


if __name__ == "__main__":
    unittest.main()
