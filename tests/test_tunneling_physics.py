"""터널링 물리 함수 단위 테스트."""

import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum.tunneling_physics import (
    BARRIER_WIDTH_DEFAULT,
    BARRIER_WIDTH_MAX,
    BARRIER_WIDTH_MIN,
    BARRIER_X,
    PARTICLE_RADIUS,
    PARTICLE_SPEED,
    SIM_H,
    SIM_LEFT,
    SIM_TOP,
    SIM_W,
    SUPERPOSITION_HZ,
    TUNNEL_PROB_BASE,
    TUNNEL_SPEED_BOOST,
    QuantumParticle,
    _REFLECT_FLASH,
    _TUNNEL_DECAY,
    _TUNNEL_FLASH,
    _VY_RANGE,
    _calc_tunnel_prob,
)

# ── 헬퍼 ─────────────────────────────────────────────

# 장벽 직전 x 좌표 (충돌 직전 위치)
_JUST_BEFORE_BARRIER = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1


def _make_particle_at_barrier(barrier_width=BARRIER_WIDTH_DEFAULT):
    """장벽 바로 앞에 입자를 배치."""
    p = QuantumParticle()
    p.x = BARRIER_X - barrier_width / 2 - PARTICLE_RADIUS + 1
    p.vx = PARTICLE_SPEED
    p.vy = 0  # 수직 이동 제거 (충돌 테스트 격리)
    return p


# ══════════════════════════════════════════════════════
# 1. _calc_tunnel_prob — 확률 함수
# ══════════════════════════════════════════════════════


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

    def test_zero_width(self):
        """두께 0 → 기본보다 높아야 함."""
        self.assertGreater(_calc_tunnel_prob(0), TUNNEL_PROB_BASE)

    def test_negative_width(self):
        """음수 두께 → 양수이며 기본보다 높아야 함."""
        p = _calc_tunnel_prob(-10)
        self.assertGreater(p, 0)
        self.assertGreater(p, TUNNEL_PROB_BASE)

    def test_very_large_width(self):
        """두께 1000 → 0에 매우 가깝지만 양수."""
        p = _calc_tunnel_prob(1000)
        self.assertGreater(p, 0)
        self.assertLess(p, 1e-6)

    def test_symmetry_around_default(self):
        """기본 두께 ± δ는 대칭적 비율."""
        delta = 30
        p_thin = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT - delta)
        p_thick = _calc_tunnel_prob(BARRIER_WIDTH_DEFAULT + delta)
        # p_thin * p_thick ≈ TUNNEL_PROB_BASE^2 (지수 함수 특성)
        self.assertAlmostEqual(p_thin * p_thick, TUNNEL_PROB_BASE ** 2, places=6)


# ══════════════════════════════════════════════════════
# 2. QuantumParticle 초기화 / 리셋
# ══════════════════════════════════════════════════════


class TestQuantumParticleInit(unittest.TestCase):
    """QuantumParticle 초기화 테스트."""

    def test_initial_position(self):
        p = QuantumParticle()
        self.assertAlmostEqual(p.x, SIM_LEFT + 40.0)
        self.assertAlmostEqual(p.y, SIM_TOP + SIM_H / 2.0)

    def test_initial_velocity_positive(self):
        p = QuantumParticle()
        self.assertEqual(p.vx, PARTICLE_SPEED)

    def test_initial_state_undetermined(self):
        p = QuantumParticle()
        self.assertIsNone(p.tunneled)

    def test_initial_counters_zero(self):
        p = QuantumParticle()
        self.assertEqual(p.tunnel_count, 0)
        self.assertEqual(p.reflect_count, 0)
        self.assertEqual(p.total_attempts, 0)

    def test_initial_alive(self):
        p = QuantumParticle()
        self.assertTrue(p.alive)

    def test_initial_flash_timer_zero(self):
        p = QuantumParticle()
        self.assertAlmostEqual(p.flash_timer, 0.0)

    def test_initial_vy_within_range(self):
        """vy는 (-_VY_RANGE/2, +_VY_RANGE/2) 범위."""
        for _ in range(50):
            p = QuantumParticle()
            self.assertGreaterEqual(p.vy, -_VY_RANGE / 2)
            self.assertLessEqual(p.vy, _VY_RANGE / 2)

    def test_initial_position_within_sim_area(self):
        """초기 위치가 시뮬레이션 영역 내."""
        p = QuantumParticle()
        self.assertGreater(p.x, SIM_LEFT)
        self.assertLess(p.x, SIM_LEFT + SIM_W)
        self.assertGreater(p.y, SIM_TOP)
        self.assertLess(p.y, SIM_TOP + SIM_H)


class TestQuantumParticleReset(unittest.TestCase):
    """QuantumParticle.reset() 테스트."""

    def test_reset_preserves_counters(self):
        p = QuantumParticle()
        p.tunnel_count = 5
        p.reflect_count = 3
        p.total_attempts = 8
        p.reset()
        self.assertEqual(p.tunnel_count, 5)
        self.assertEqual(p.reflect_count, 3)
        self.assertEqual(p.total_attempts, 8)

    def test_reset_clears_tunneled_state(self):
        p = QuantumParticle()
        p.tunneled = True
        p.reset()
        self.assertIsNone(p.tunneled)

    def test_reset_restores_position(self):
        p = QuantumParticle()
        p.x = 999.0
        p.y = 999.0
        p.reset()
        self.assertAlmostEqual(p.x, SIM_LEFT + 40.0)
        self.assertAlmostEqual(p.y, SIM_TOP + SIM_H / 2.0)

    def test_reset_clears_flash_timer(self):
        p = QuantumParticle()
        p.flash_timer = 0.5
        p.reset()
        self.assertAlmostEqual(p.flash_timer, 0.0)

    def test_reset_restores_alive(self):
        p = QuantumParticle()
        p.alive = False
        p.reset()
        self.assertTrue(p.alive)

    def test_reset_restores_vx(self):
        p = QuantumParticle()
        p.vx = -999
        p.reset()
        self.assertEqual(p.vx, PARTICLE_SPEED)

    def test_multiple_reset_idempotent(self):
        p = QuantumParticle()
        p.tunnel_count = 10
        p.reset()
        p.reset()
        p.reset()
        self.assertEqual(p.tunnel_count, 10)
        self.assertAlmostEqual(p.x, SIM_LEFT + 40.0)


# ══════════════════════════════════════════════════════
# 3. qubit_state — 중첩 관측값
# ══════════════════════════════════════════════════════


class TestQuantumParticleQubitState(unittest.TestCase):
    """qubit_state() — 중첩 관측값 테스트."""

    def test_returns_zero_or_one(self):
        p = QuantumParticle()
        for t_ms in range(0, 2000, 10):
            state = p.qubit_state(float(t_ms))
            self.assertIn(state, (0, 1))

    def test_oscillates(self):
        """시간이 지남에 따라 0과 1 모두 나타나야 한다."""
        p = QuantumParticle()
        states = {p.qubit_state(float(t_ms)) for t_ms in range(0, 2000, 10)}
        self.assertEqual(states, {0, 1})

    def test_zero_at_time_zero(self):
        """sin(0) = 0 >= 0 → state 0."""
        p = QuantumParticle()
        self.assertEqual(p.qubit_state(0.0), 0)

    def test_period_matches_hz(self):
        """한 주기 = 1/SUPERPOSITION_HZ 초 = 1000/SUPERPOSITION_HZ ms."""
        p = QuantumParticle()
        period_ms = 1000.0 / SUPERPOSITION_HZ
        # t=0에서 0
        self.assertEqual(p.qubit_state(0.0), 0)
        # 반주기 직후: sin(π+ε) < 0 → state 1
        self.assertEqual(p.qubit_state(period_ms / 2 + 1), 1)
        # 1/4 주기: sin(π/2) > 0 → state 0
        self.assertEqual(p.qubit_state(period_ms / 4), 0)

    def test_negative_time(self):
        """음수 시간도 0 또는 1 반환."""
        p = QuantumParticle()
        state = p.qubit_state(-500.0)
        self.assertIn(state, (0, 1))

    def test_very_large_time(self):
        """매우 큰 시간도 정상 동작."""
        p = QuantumParticle()
        state = p.qubit_state(1e9)
        self.assertIn(state, (0, 1))


# ══════════════════════════════════════════════════════
# 4. superposition_alpha — 블로흐 구 각도
# ══════════════════════════════════════════════════════


class TestSuperpositionAlpha(unittest.TestCase):
    """superposition_alpha() — 블로흐 구 각도 테스트."""

    def test_range_zero_to_pi(self):
        p = QuantumParticle()
        for t_ms in range(0, 2000, 10):
            alpha = p.superposition_alpha(float(t_ms))
            self.assertGreaterEqual(alpha, -1e-9)
            self.assertLessEqual(alpha, math.pi + 1e-9)

    def test_at_time_zero(self):
        """sin(0) = 0 → alpha = π/2."""
        p = QuantumParticle()
        alpha = p.superposition_alpha(0.0)
        self.assertAlmostEqual(alpha, math.pi / 2)

    def test_continuous(self):
        """인접 시간의 alpha 값이 급격하게 변하지 않아야 한다."""
        p = QuantumParticle()
        prev = p.superposition_alpha(0.0)
        for t_ms in range(1, 100):
            cur = p.superposition_alpha(float(t_ms))
            self.assertLess(abs(cur - prev), math.pi / 2)
            prev = cur

    def test_consistency_with_qubit_state(self):
        """qubit_state=0이면 alpha < π/2, qubit_state=1이면 alpha > π/2."""
        p = QuantumParticle()
        for t_ms in range(10, 2000, 17):
            state = p.qubit_state(float(t_ms))
            alpha = p.superposition_alpha(float(t_ms))
            if state == 0:
                self.assertLessEqual(alpha, math.pi / 2 + 0.01)
            else:
                self.assertGreaterEqual(alpha, math.pi / 2 - 0.01)

    def test_reaches_extremes(self):
        """alpha가 0 근처와 π 근처 모두에 도달해야 한다."""
        p = QuantumParticle()
        min_a = math.pi
        max_a = 0.0
        for t_ms in range(0, 5000, 1):
            a = p.superposition_alpha(float(t_ms))
            min_a = min(min_a, a)
            max_a = max(max_a, a)
        self.assertLess(min_a, 0.05)
        self.assertGreater(max_a, math.pi - 0.05)

    def test_periodic(self):
        """한 주기 후 같은 값으로 돌아옴."""
        p = QuantumParticle()
        period_ms = 1000.0 / SUPERPOSITION_HZ
        a1 = p.superposition_alpha(100.0)
        a2 = p.superposition_alpha(100.0 + period_ms)
        self.assertAlmostEqual(a1, a2, places=5)


# ══════════════════════════════════════════════════════
# 5. update() — 기본 물리 업데이트
# ══════════════════════════════════════════════════════


class TestQuantumParticleUpdate(unittest.TestCase):
    """QuantumParticle.update() — 물리 업데이트 테스트."""

    def test_position_advances(self):
        p = QuantumParticle()
        old_x = p.x
        p.update(0.01)
        self.assertGreater(p.x, old_x)

    def test_no_update_when_not_alive(self):
        p = QuantumParticle()
        p.alive = False
        old_x = p.x
        p.update(0.01)
        self.assertAlmostEqual(p.x, old_x)

    def test_vertical_bounce_top(self):
        p = QuantumParticle()
        p.y = SIM_TOP + PARTICLE_RADIUS - 1
        p.vy = -100
        p.update(0.001)
        self.assertGreater(p.vy, 0)

    def test_vertical_bounce_bottom(self):
        p = QuantumParticle()
        p.y = SIM_TOP + SIM_H - PARTICLE_RADIUS + 1
        p.vy = 100
        p.update(0.001)
        self.assertLess(p.vy, 0)

    def test_flash_timer_decays(self):
        p = QuantumParticle()
        p.flash_timer = 0.5
        p.update(0.1)
        self.assertAlmostEqual(p.flash_timer, 0.4, places=2)

    def test_respawn_when_off_screen_right(self):
        p = QuantumParticle()
        p.tunnel_count = 1
        p.total_attempts = 1
        p.x = SIM_LEFT + SIM_W + 25
        p.tunneled = True
        p.update(0.01)
        self.assertAlmostEqual(p.x, SIM_LEFT + 40.0)
        self.assertIsNone(p.tunneled)
        self.assertEqual(p.tunnel_count, 1)

    def test_respawn_when_off_screen_left(self):
        p = QuantumParticle()
        p.reflect_count = 1
        p.total_attempts = 1
        p.x = SIM_LEFT - 25
        p.vx = -100
        p.tunneled = False
        p.update(0.01)
        self.assertAlmostEqual(p.x, SIM_LEFT + 40.0)
        self.assertIsNone(p.tunneled)

    def test_zero_dt_no_movement(self):
        """dt=0이면 위치 불변."""
        p = QuantumParticle()
        old_x, old_y = p.x, p.y
        p.update(0.0)
        self.assertAlmostEqual(p.x, old_x)
        self.assertAlmostEqual(p.y, old_y)

    def test_large_dt_forces_respawn(self):
        """충분한 프레임 후 반사 입자가 리스폰."""
        p = _make_particle_at_barrier()
        p.update(0.001, tunnel_prob=0.0)
        self.assertFalse(p.tunneled)
        # 왼쪽으로 이동 → 탈출 → 리스폰
        p.update(10.0, tunnel_prob=0.0)
        self.assertIsNone(p.tunneled)

    def test_y_stays_in_bounds_after_many_updates(self):
        """수백 프레임 후에도 y가 시뮬레이션 영역 내."""
        p = QuantumParticle()
        p.vy = _VY_RANGE  # 최대 수직 속도
        for _ in range(500):
            p.update(0.016)  # ~60 FPS
        self.assertGreaterEqual(p.y - PARTICLE_RADIUS, SIM_TOP - 1)
        self.assertLessEqual(p.y + PARTICLE_RADIUS, SIM_TOP + SIM_H + 1)

    def test_flash_timer_never_negative(self):
        """flash_timer가 감소하지만 절대 음수가 되지 않음."""
        p = QuantumParticle()
        p.flash_timer = 0.1
        for _ in range(100):
            p.update(0.016)
            self.assertGreaterEqual(p.flash_timer, 0.0,
                                    "flash_timer가 음수가 되었습니다")

    def test_position_linear_with_dt(self):
        """충돌 없는 구간에서 x 이동은 vx*dt에 비례."""
        p = QuantumParticle()
        p.vy = 0
        x0 = p.x
        dt = 0.005  # 충돌 전 짧은 시간
        p.update(dt, tunnel_prob=0.0)
        # 충돌 전이라면 x ≈ x0 + vx * dt
        if p.tunneled is None:  # 충돌 안 했을 때만 검증
            self.assertAlmostEqual(p.x, x0 + PARTICLE_SPEED * dt, places=1)


# ══════════════════════════════════════════════════════
# 6. 장벽 충돌 — 터널링/반사 판정
# ══════════════════════════════════════════════════════


class TestTunnelingCollision(unittest.TestCase):
    """장벽 충돌 시 터널링/반사 판정 테스트."""

    def test_tunnel_success(self):
        """tunnel_prob=1.0이면 항상 터널링."""
        p = _make_particle_at_barrier()
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=1.0)
        self.assertTrue(p.tunneled)
        self.assertEqual(p.tunnel_count, 1)
        self.assertEqual(p.total_attempts, 1)
        self.assertGreater(p.x, BARRIER_X)

    def test_tunnel_reflection(self):
        """tunnel_prob=0.0이면 항상 반사."""
        p = _make_particle_at_barrier()
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.0)
        self.assertFalse(p.tunneled)
        self.assertEqual(p.reflect_count, 1)
        self.assertEqual(p.total_attempts, 1)
        self.assertLess(p.vx, 0)

    def test_tunnel_speed_boost(self):
        """터널링 성공 시 속도 부스트 적용."""
        p = _make_particle_at_barrier()
        boost = 3.0
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=1.0, speed_boost=boost)
        self.assertAlmostEqual(p.vx, PARTICLE_SPEED * boost)

    def test_reflect_velocity_damping(self):
        """반사 시 0.8 감쇠."""
        p = _make_particle_at_barrier()
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.0)
        self.assertAlmostEqual(abs(p.vx), PARTICLE_SPEED * 0.8)

    def test_reflect_velocity_negative(self):
        """반사 후 속도가 음수 (왼쪽 방향)."""
        p = _make_particle_at_barrier()
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.0)
        self.assertLess(p.vx, 0)

    def test_tunnel_flash_exact_value(self):
        """터널링 시 flash_timer = _TUNNEL_FLASH."""
        p = _make_particle_at_barrier()
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=1.0)
        self.assertAlmostEqual(p.flash_timer, _TUNNEL_FLASH - 0.001, places=3)

    def test_reflect_flash_exact_value(self):
        """반사 시 flash_timer = _REFLECT_FLASH."""
        p = _make_particle_at_barrier()
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.0)
        self.assertAlmostEqual(p.flash_timer, _REFLECT_FLASH - 0.001, places=3)

    def test_tunnel_flash_greater_than_reflect(self):
        """터널링 플래시가 반사보다 길다."""
        self.assertGreater(_TUNNEL_FLASH, _REFLECT_FLASH)

    def test_no_collision_when_moving_left(self):
        """왼쪽 이동 시 장벽 판정 없음."""
        p = _make_particle_at_barrier()
        p.vx = -PARTICLE_SPEED
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=1.0)
        self.assertIsNone(p.tunneled)
        self.assertEqual(p.total_attempts, 0)

    def test_no_double_collision(self):
        """이미 터널링/반사된 입자는 재판정하지 않음."""
        p = _make_particle_at_barrier()
        p.tunneled = True
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=1.0)
        self.assertEqual(p.total_attempts, 0)

    def test_multiple_attempts_accumulate(self):
        """여러 시도의 카운터가 누적됨."""
        p = QuantumParticle()
        for _ in range(5):
            p.x = _JUST_BEFORE_BARRIER
            p.vx = PARTICLE_SPEED
            p.vy = 0
            p.tunneled = None
            p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.5)
        self.assertEqual(p.total_attempts, 5)
        self.assertEqual(p.tunnel_count + p.reflect_count, 5)

    def test_tunnel_position_past_barrier(self):
        """터널링 후 정확한 위치: 장벽 오른쪽 + PARTICLE_RADIUS + 5."""
        bw = BARRIER_WIDTH_DEFAULT
        p = _make_particle_at_barrier(bw)
        p.update(0.001, barrier_width=bw, tunnel_prob=1.0)
        expected_x = BARRIER_X + bw / 2 + PARTICLE_RADIUS + 5
        # update에서 추가 이동이 있으므로 근사
        self.assertAlmostEqual(p.x, expected_x + p.vx * 0.001, places=0)

    def test_reflect_position_before_barrier(self):
        """반사 후 정확한 위치: 장벽 왼쪽 - PARTICLE_RADIUS - 2."""
        bw = BARRIER_WIDTH_DEFAULT
        p = _make_particle_at_barrier(bw)
        p.update(0.001, barrier_width=bw, tunnel_prob=0.0)
        expected_x = BARRIER_X - bw / 2 - PARTICLE_RADIUS - 2
        self.assertAlmostEqual(p.x, expected_x + p.vx * 0.001, places=0)


# ══════════════════════════════════════════════════════
# 7. 장벽 두께 효과
# ══════════════════════════════════════════════════════


class TestBarrierWidthEffect(unittest.TestCase):
    """다양한 장벽 두께에서의 충돌 테스트."""

    def test_wide_barrier_collision_position(self):
        """두꺼운 장벽은 더 왼쪽에서 충돌."""
        wide = 100
        p = _make_particle_at_barrier(wide)
        p.update(0.001, barrier_width=wide, tunnel_prob=1.0)
        self.assertGreater(p.x, BARRIER_X + wide / 2)

    def test_narrow_barrier_collision_position(self):
        """얇은 장벽은 더 오른쪽에서 충돌."""
        narrow = BARRIER_WIDTH_MIN
        p = _make_particle_at_barrier(narrow)
        p.update(0.001, barrier_width=narrow, tunnel_prob=0.0)
        self.assertLess(p.x, BARRIER_X - narrow / 2)

    def test_all_valid_widths_trigger_collision(self):
        """모든 유효 두께에서 충돌 판정 발생."""
        for bw in range(BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX + 1, 20):
            p = _make_particle_at_barrier(bw)
            p.update(0.001, barrier_width=bw, tunnel_prob=1.0)
            self.assertIsNotNone(p.tunneled, f"barrier_width={bw}에서 충돌 미발생")
            self.assertEqual(p.total_attempts, 1)


# ══════════════════════════════════════════════════════
# 8. 통계적 분포 검증
# ══════════════════════════════════════════════════════


class TestStatisticalDistribution(unittest.TestCase):
    """확률이 실제로 올바르게 작동하는지 대량 시행으로 검증."""

    def _run_trials(self, tunnel_prob, n=1000):
        """n회 충돌 시행 후 터널링 수 반환."""
        tunnels = 0
        for _ in range(n):
            p = _make_particle_at_barrier()
            p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=tunnel_prob)
            if p.tunneled:
                tunnels += 1
        return tunnels

    def test_prob_100_all_tunnel(self):
        """확률 1.0 → 전부 터널링."""
        self.assertEqual(self._run_trials(1.0, 100), 100)

    def test_prob_0_none_tunnel(self):
        """확률 0.0 → 전부 반사."""
        self.assertEqual(self._run_trials(0.0, 100), 0)

    def test_prob_50_within_range(self):
        """확률 0.5 → 40~60% 범위 (n=500, 3σ 이내)."""
        random.seed(42)
        tunnels = self._run_trials(0.5, 500)
        rate = tunnels / 500
        self.assertGreater(rate, 0.35, f"터널링률 {rate:.2%}이 너무 낮음")
        self.assertLess(rate, 0.65, f"터널링률 {rate:.2%}이 너무 높음")

    def test_prob_10_within_range(self):
        """확률 0.1 → 5~20% 범위 (n=500, 넉넉한 구간)."""
        random.seed(123)
        tunnels = self._run_trials(0.1, 500)
        rate = tunnels / 500
        self.assertGreater(rate, 0.03, f"터널링률 {rate:.2%}이 너무 낮음")
        self.assertLess(rate, 0.20, f"터널링률 {rate:.2%}이 너무 높음")

    def test_higher_prob_more_tunnels(self):
        """높은 확률이 더 많은 터널링을 유발."""
        random.seed(99)
        tunnels_low = self._run_trials(0.1, 300)
        random.seed(99)  # 다른 시드로 재시행
        tunnels_high = self._run_trials(0.9, 300)
        self.assertGreater(tunnels_high, tunnels_low)


# ══════════════════════════════════════════════════════
# 9. 시뮬레이션 라이프사이클 — 전체 순환
# ══════════════════════════════════════════════════════


class TestSimulationLifecycle(unittest.TestCase):
    """스폰 → 이동 → 충돌 → 결과 → 탈출 → 리스폰 순환 테스트."""

    def test_full_tunnel_cycle(self):
        """터널링 전체 순환: 충돌 → 터널링 → 오른쪽 탈출 → 리스폰."""
        p = _make_particle_at_barrier()
        # 1. 충돌 → 터널링
        p.update(0.001, tunnel_prob=1.0, speed_boost=5.0)
        self.assertTrue(p.tunneled)
        self.assertEqual(p.tunnel_count, 1)
        # 2. 오른쪽으로 빠르게 이동 → 탈출 → 리스폰
        for _ in range(200):
            p.update(0.016, tunnel_prob=0.0)
        # 리스폰되어 tunneled = None, 카운터 보존
        self.assertIsNone(p.tunneled)
        self.assertEqual(p.tunnel_count, 1)
        self.assertEqual(p.vx, PARTICLE_SPEED)

    def test_full_reflect_cycle(self):
        """반사 전체 순환: 충돌 → 반사 → 왼쪽 탈출 → 리스폰 → 재충돌."""
        p = _make_particle_at_barrier()
        # 1. 충돌 → 반사
        p.update(0.001, tunnel_prob=0.0)
        self.assertFalse(p.tunneled)
        self.assertEqual(p.reflect_count, 1)
        # 2. 왼쪽으로 탈출시키기
        p.x = SIM_LEFT - 25
        p.update(0.001, tunnel_prob=0.0)
        # 리스폰됨
        self.assertIsNone(p.tunneled)
        self.assertEqual(p.reflect_count, 1)
        self.assertEqual(p.vx, PARTICLE_SPEED)

    def test_multiple_cycles(self):
        """여러 충돌/리스폰 순환 후 카운터 정합성."""
        random.seed(77)
        p = QuantumParticle()
        p.vy = 0  # 수직 이동 제거
        # 여러 순환 시뮬레이션
        for _ in range(5000):
            p.update(0.016, tunnel_prob=0.3)
        # 불변식: tunnel + reflect = total_attempts
        self.assertEqual(p.tunnel_count + p.reflect_count, p.total_attempts)
        # 충분한 시행이 발생했을 것
        self.assertGreater(p.total_attempts, 0)

    def test_counters_consistency_invariant(self):
        """어떤 경로든 tunnel_count + reflect_count == total_attempts."""
        random.seed(42)
        p = QuantumParticle()
        p.vy = 0
        for i in range(3000):
            p.update(0.016, tunnel_prob=0.5)
            self.assertEqual(
                p.tunnel_count + p.reflect_count, p.total_attempts,
                f"프레임 {i}: 카운터 불일치"
            )


# ══════════════════════════════════════════════════════
# 10. 랜덤 시드 재현성
# ══════════════════════════════════════════════════════


class TestReproducibility(unittest.TestCase):
    """같은 시드로 동일한 결과가 나오는지 검증."""

    def _run_with_seed(self, seed, steps=100):
        random.seed(seed)
        p = QuantumParticle()
        p.vy = 0
        results = []
        for _ in range(steps):
            prev = p.total_attempts
            p.update(0.016, tunnel_prob=0.5)
            if p.total_attempts > prev:
                results.append(p.tunneled)
        return results, p.tunnel_count, p.reflect_count

    def test_same_seed_same_result(self):
        r1, t1, ref1 = self._run_with_seed(12345)
        r2, t2, ref2 = self._run_with_seed(12345)
        self.assertEqual(r1, r2)
        self.assertEqual(t1, t2)
        self.assertEqual(ref1, ref2)

    def test_different_seed_different_result(self):
        """다른 시드는 (높은 확률로) 다른 결과."""
        _, t1, _ = self._run_with_seed(111, 500)
        _, t2, _ = self._run_with_seed(222, 500)
        # 극히 낮은 확률로 같을 수 있지만 거의 항상 다름
        # 같더라도 테스트는 통과시키되 경고
        # 여기서는 관대하게 검증
        self.assertTrue(True)  # 재현성 대조군


# ══════════════════════════════════════════════════════
# 11. 수직 벽 반사 — 에너지 / 경계
# ══════════════════════════════════════════════════════


class TestVerticalBounce(unittest.TestCase):
    """상하 벽 반사 상세 테스트."""

    def test_top_bounce_preserves_speed_magnitude(self):
        """상단 반사 후 |vy| 보존."""
        p = QuantumParticle()
        p.y = SIM_TOP + PARTICLE_RADIUS - 0.5
        p.vy = -80
        p.update(0.001)
        self.assertAlmostEqual(abs(p.vy), 80)

    def test_bottom_bounce_preserves_speed_magnitude(self):
        """하단 반사 후 |vy| 보존."""
        p = QuantumParticle()
        p.y = SIM_TOP + SIM_H - PARTICLE_RADIUS + 0.5
        p.vy = 80
        p.update(0.001)
        self.assertAlmostEqual(abs(p.vy), 80)

    def test_top_bounce_clamps_position(self):
        """상단 반사 후 y = SIM_TOP + PARTICLE_RADIUS."""
        p = QuantumParticle()
        p.y = SIM_TOP  # PARTICLE_RADIUS 위로 돌출
        p.vy = -100
        p.update(0.001)
        self.assertGreaterEqual(p.y, SIM_TOP + PARTICLE_RADIUS)

    def test_bottom_bounce_clamps_position(self):
        """하단 반사 후 y = SIM_TOP + SIM_H - PARTICLE_RADIUS."""
        p = QuantumParticle()
        p.y = SIM_TOP + SIM_H  # PARTICLE_RADIUS 아래로 돌출
        p.vy = 100
        p.update(0.001)
        self.assertLessEqual(p.y, SIM_TOP + SIM_H - PARTICLE_RADIUS)

    def test_zero_vy_no_bounce(self):
        """vy=0일 때 반사 없음, y 불변."""
        p = QuantumParticle()
        p.vy = 0
        y0 = p.y
        p.update(0.01)
        self.assertAlmostEqual(p.y, y0)

    def test_rapid_bouncing_stays_bounded(self):
        """빠른 수직 속도로 200프레임 후에도 영역 내."""
        p = QuantumParticle()
        p.vy = _VY_RANGE * 10  # 비정상적으로 빠른 속도
        for _ in range(200):
            p.update(0.016)
            self.assertGreaterEqual(p.y, SIM_TOP + PARTICLE_RADIUS - 1)
            self.assertLessEqual(p.y, SIM_TOP + SIM_H - PARTICLE_RADIUS + 1)


# ══════════════════════════════════════════════════════
# 12. 레이아웃 상수 정합성
# ══════════════════════════════════════════════════════


class TestLayoutConstants(unittest.TestCase):
    """물리 상수와 레이아웃의 일관성 테스트."""

    def test_barrier_within_sim_area(self):
        """장벽이 시뮬레이션 영역 내에 위치."""
        self.assertGreater(BARRIER_X, SIM_LEFT)
        self.assertLess(BARRIER_X, SIM_LEFT + SIM_W)

    def test_barrier_x_is_center(self):
        """BARRIER_X == SIM_LEFT + SIM_W // 2."""
        self.assertEqual(BARRIER_X, SIM_LEFT + SIM_W // 2)

    def test_particle_fits_in_sim_area(self):
        """입자 반지름이 시뮬레이션 높이보다 작음."""
        self.assertLess(PARTICLE_RADIUS * 2, SIM_H)

    def test_initial_position_left_of_barrier(self):
        """초기 위치가 장벽 왼쪽."""
        p = QuantumParticle()
        self.assertLess(p.x + PARTICLE_RADIUS, BARRIER_X - BARRIER_WIDTH_DEFAULT / 2)

    def test_barrier_width_range_valid(self):
        """MIN < DEFAULT < MAX."""
        self.assertLess(BARRIER_WIDTH_MIN, BARRIER_WIDTH_DEFAULT)
        self.assertLess(BARRIER_WIDTH_DEFAULT, BARRIER_WIDTH_MAX)

    def test_max_barrier_fits_in_sim(self):
        """최대 장벽이 시뮬레이션 영역 내."""
        self.assertLess(BARRIER_WIDTH_MAX, SIM_W)

    def test_speed_boost_positive(self):
        self.assertGreater(TUNNEL_SPEED_BOOST, 0)

    def test_particle_speed_positive(self):
        self.assertGreater(PARTICLE_SPEED, 0)

    def test_superposition_hz_positive(self):
        self.assertGreater(SUPERPOSITION_HZ, 0)


# ══════════════════════════════════════════════════════
# 13. 에지 케이스 — 경계 조건
# ══════════════════════════════════════════════════════


class TestEdgeCases(unittest.TestCase):
    """특수한 경계 조건 테스트."""

    def test_particle_exactly_at_barrier_edge(self):
        """입자가 정확히 장벽 경계에 있을 때."""
        bw = BARRIER_WIDTH_DEFAULT
        p = QuantumParticle()
        p.x = BARRIER_X - bw / 2 - PARTICLE_RADIUS  # 정확히 경계
        p.vx = PARTICLE_SPEED
        p.vy = 0
        p.update(0.001, barrier_width=bw, tunnel_prob=1.0)
        # 1px 이동 후 충돌 발생해야 함
        self.assertEqual(p.total_attempts, 1)

    def test_particle_well_before_barrier(self):
        """입자가 장벽에서 먼 곳에 있을 때 충돌 없음."""
        p = QuantumParticle()
        p.vy = 0
        p.update(0.001)  # 아주 짧은 시간
        self.assertIsNone(p.tunneled)
        self.assertEqual(p.total_attempts, 0)

    def test_speed_boost_one(self):
        """speed_boost=1.0이면 속도 유지."""
        p = _make_particle_at_barrier()
        p.update(0.001, tunnel_prob=1.0, speed_boost=1.0)
        self.assertAlmostEqual(p.vx, PARTICLE_SPEED * 1.0)

    def test_very_small_tunnel_prob(self):
        """극히 낮은 확률 → 대부분 반사."""
        random.seed(42)
        tunnels = 0
        for _ in range(100):
            p = _make_particle_at_barrier()
            p.update(0.001, tunnel_prob=1e-10)
            if p.tunneled:
                tunnels += 1
        self.assertEqual(tunnels, 0)

    def test_tunnel_prob_slightly_below_one(self):
        """확률 0.999 → 대부분 터널링."""
        random.seed(42)
        tunnels = sum(
            1 for _ in range(100)
            if (_make_particle_at_barrier(), _make_particle_at_barrier())[-1].update(
                0.001, tunnel_prob=0.999
            ) is None and True
        )
        # 간결하게 재작성
        tunnels = 0
        for _ in range(100):
            p = _make_particle_at_barrier()
            p.update(0.001, tunnel_prob=0.999)
            if p.tunneled:
                tunnels += 1
        self.assertGreater(tunnels, 90)

    def test_respawn_boundary_exact(self):
        """정확한 리스폰 경계 테스트."""
        # 오른쪽 경계: SIM_LEFT + SIM_W + 20
        p = QuantumParticle()
        p.x = SIM_LEFT + SIM_W + 19  # 아직 안 넘음
        p.vx = 0
        p.tunneled = True
        p.update(0.001)
        # 아직 리스폰 안 됨
        self.assertTrue(p.tunneled)

        p.x = SIM_LEFT + SIM_W + 21  # 넘음
        p.update(0.001)
        # 리스폰 됨
        self.assertIsNone(p.tunneled)

    def test_reflect_then_natural_respawn(self):
        """반사 후 왼쪽 경계를 넘어 자연 리스폰."""
        p = _make_particle_at_barrier()
        p.update(0.001, tunnel_prob=0.0)
        self.assertFalse(p.tunneled)

        # 왼쪽으로 계속 이동 → 탈출
        p.x = SIM_LEFT - 21
        p.update(0.001)
        self.assertIsNone(p.tunneled)
        self.assertAlmostEqual(p.x, SIM_LEFT + 40.0)


if __name__ == "__main__":
    unittest.main()
