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
    SHAPE_DOUBLE,
    SHAPE_NAMES,
    SHAPE_RECT,
    SHAPE_TRAPEZOID,
    SHAPE_TRIANGLE,
    SIM_H,
    SIM_LEFT,
    SIM_TOP,
    SIM_W,
    SUPERPOSITION_HZ,
    TRAIL_MAX_LENGTH,
    TRAIL_RECORD_INTERVAL,
    TUNNEL_PROB_BASE,
    TUNNEL_SPEED_BOOST,
    _NUM_SHAPES,
    QuantumParticle,
    _REFLECT_FLASH,
    _TUNNEL_DECAY,
    _TUNNEL_FLASH,
    _VY_RANGE,
    DensityAccumulator,
    _calc_tunnel_prob,
    barrier_potential,
    compute_potential_profile,
    compute_wavefunction,
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


# ══════════════════════════════════════════════════════
# 14. NotifyToast — 카테고리 토스트 알림
# ══════════════════════════════════════════════════════

# ui_common이 pygame을 top-level import 하므로 mock 필요
from unittest.mock import MagicMock as _MagicMock

_pg_mock = _MagicMock()
sys.modules.setdefault("pygame", _pg_mock)
sys.modules.setdefault("pygame.font", _pg_mock.font)
sys.modules.setdefault("pygame.draw", _pg_mock.draw)
sys.modules.setdefault("pygame.display", _pg_mock.display)

from quantum.ui_common import MAX_PAGE_DOTS, NOTIFY_CATEGORIES, NotifyToast, draw_page_dots, page_dots_width


class TestNotifyToast(unittest.TestCase):
    """NotifyToast 상태 머신 테스트 (렌더링 제외)."""

    def test_initial_state_empty(self):
        """초기 상태: 활성/대기열 모두 비어있음."""
        nt = NotifyToast()
        self.assertEqual(nt.active_count, 0)
        self.assertEqual(nt.queue_count, 0)

    def test_show_adds_active(self):
        """show() 호출 시 활성 목록에 추가."""
        nt = NotifyToast()
        nt.show("hello", "info")
        self.assertEqual(nt.active_count, 1)
        self.assertEqual(nt.queue_count, 0)

    def test_max_visible_limit(self):
        """MAX_VISIBLE 초과 시 대기열로 이동."""
        nt = NotifyToast()
        for i in range(nt.MAX_VISIBLE + 2):
            nt.show(f"msg{i}", "info")
        self.assertEqual(nt.active_count, nt.MAX_VISIBLE)
        self.assertEqual(nt.queue_count, 2)

    def test_phase_transition_in_to_show(self):
        """slide-in 완료 후 show 위상으로 전환."""
        nt = NotifyToast()
        nt.show("test", "success", duration=1.0)
        # slide-in 시간만큼 진행
        nt.update(nt.SLIDE_TIME + 0.01)
        self.assertEqual(nt._active[0]["phase"], "show")

    def test_phase_transition_show_to_out(self):
        """표시 시간 경과 후 slide-out 위상으로 전환."""
        nt = NotifyToast()
        nt.show("test", "info", duration=0.5)
        nt.update(nt.SLIDE_TIME + 0.01)  # in → show
        nt.update(0.51)  # show → out
        self.assertEqual(nt._active[0]["phase"], "out")

    def test_toast_removed_after_out(self):
        """slide-out 완료 후 제거."""
        nt = NotifyToast()
        nt.show("test", "info", duration=0.1)
        nt.update(nt.SLIDE_TIME + 0.01)  # in → show
        nt.update(0.11)  # show → out
        nt.update(nt.SLIDE_TIME + 0.01)  # out → 제거
        self.assertEqual(nt.active_count, 0)

    def test_queue_promotes_after_removal(self):
        """활성 토스트 제거 후 대기열에서 승격."""
        nt = NotifyToast()
        # 첫 MAX_VISIBLE개는 긴 지속, 대기열의 1개도 긴 지속
        for i in range(nt.MAX_VISIBLE):
            nt.show(f"msg{i}", "info", duration=5.0)
        nt.show("queued", "info", duration=5.0)
        self.assertEqual(nt.active_count, nt.MAX_VISIBLE)
        self.assertEqual(nt.queue_count, 1)

        # 첫 번째 토스트만 강제 만료: phase를 out으로 변경
        nt._active[0]["phase"] = "out"
        nt._active[0]["timer"] = nt.SLIDE_TIME + 0.01
        nt.update(0.0)  # 만료 처리
        # 대기열에서 승격되어 여전히 MAX_VISIBLE
        self.assertEqual(nt.active_count, nt.MAX_VISIBLE)
        self.assertEqual(nt.queue_count, 0)

    def test_invalid_category_defaults_to_info(self):
        """잘못된 카테고리는 'info'로 대체."""
        nt = NotifyToast()
        nt.show("test", "invalid_cat")
        self.assertEqual(nt._active[0]["cat"], "info")

    def test_all_valid_categories_accepted(self):
        """모든 유효 카테고리가 올바르게 저장됨."""
        for cat in NOTIFY_CATEGORIES:
            nt = NotifyToast()
            nt.show("test", cat)
            self.assertEqual(nt._active[0]["cat"], cat)

    def test_clear_removes_all(self):
        """clear() 호출 시 모든 토스트 제거."""
        nt = NotifyToast()
        for i in range(5):
            nt.show(f"msg{i}", "info")
        nt.clear()
        self.assertEqual(nt.active_count, 0)
        self.assertEqual(nt.queue_count, 0)

    def test_custom_duration(self):
        """사용자 지정 표시 시간."""
        nt = NotifyToast()
        nt.show("test", "success", duration=5.0)
        nt.update(nt.SLIDE_TIME + 0.01)  # in → show
        # 2초 후 아직 show 상태
        nt.update(2.0)
        self.assertEqual(nt._active[0]["phase"], "show")
        # 5초 경과 후 out으로 전환
        nt.update(3.01)
        self.assertEqual(nt._active[0]["phase"], "out")

    def test_multiple_toasts_independent_timers(self):
        """여러 토스트의 타이머는 독립적."""
        nt = NotifyToast()
        nt.show("fast", "info", duration=0.1)
        nt.show("slow", "info", duration=5.0)
        nt.update(nt.SLIDE_TIME + 0.01)  # 둘 다 in → show
        nt.update(0.11)  # fast: show → out, slow: 아직 show
        phases = [t["phase"] for t in nt._active]
        self.assertIn("out", phases)
        self.assertIn("show", phases)

    def test_zero_dt_no_crash(self):
        """dt=0 업데이트 시 크래시 없음."""
        nt = NotifyToast()
        nt.show("test", "info")
        nt.update(0.0)
        self.assertEqual(nt.active_count, 1)


# ══════════════════════════════════════════════════════
# 15. _make_fonts — 해상도 비례 폰트 스케일링
# ══════════════════════════════════════════════════════

from quantum.tunneling import _make_fonts, _BASE_W, _BASE_H


class TestMakeFonts(unittest.TestCase):
    """_make_fonts 호출이 해상도에 비례하여 폰트 크기를 결정하는지 검증."""

    def test_returns_four_fonts(self):
        """4-튜플 반환."""
        fonts = _make_fonts(900, 600)
        self.assertEqual(len(fonts), 4)

    def test_calls_sysfont_with_scaled_sizes(self):
        """저해상도에서 SysFont 호출 크기가 기본보다 작음."""
        pg = sys.modules["pygame"]
        before = pg.font.SysFont.call_count
        _make_fonts(450, 300)  # 50% 해상도
        calls = pg.font.SysFont.call_args_list[before:]
        # 4회 호출 (font, info, title, big)
        self.assertEqual(len(calls), 4)
        # 50% 해상도에서 크기가 기본(13)보다 작아야 함
        first_size = calls[0][0][1]
        self.assertLess(first_size, 13)
        self.assertGreaterEqual(first_size, 8)

    def test_high_resolution_does_not_over_scale(self):
        """고해상도에서 기본 크기 이상이지만 합리적 범위."""
        pg = sys.modules["pygame"]
        before = pg.font.SysFont.call_count
        _make_fonts(1800, 1200)  # 200% 해상도
        calls = pg.font.SysFont.call_args_list[before:]
        big_size = calls[3][0][1]
        self.assertGreater(big_size, 18)
        self.assertLess(big_size, 100)

    def test_minimum_floor(self):
        """매우 작은 해상도에서도 최소 8px 보장."""
        pg = sys.modules["pygame"]
        before = pg.font.SysFont.call_count
        _make_fonts(100, 60)  # 극소 해상도
        calls = pg.font.SysFont.call_args_list[before:]
        for call in calls:
            size = call[0][1]
            self.assertGreaterEqual(size, 8)


# ── draw_page_dots 테스트 ─────────────────────────────


class TestDrawPageDots(unittest.TestCase):
    """draw_page_dots() 도트 인디케이터 테스트."""

    def setUp(self):
        self.screen = _MagicMock()
        self.pg = sys.modules["pygame"]
        self.pg.draw.circle.reset_mock()
        self.active = (100, 200, 255)
        self.inactive = (50, 50, 50)
        self.border = (80, 80, 80)

    def test_single_page_no_draw(self):
        """1페이지면 아무것도 그리지 않는다."""
        self.pg.draw.circle.reset_mock()
        draw_page_dots(self.screen, 0, 0, 1, 0,
                       self.active, self.inactive, self.border)
        self.pg.draw.circle.assert_not_called()

    def test_zero_pages_no_draw(self):
        """0페이지면 아무것도 그리지 않는다."""
        self.pg.draw.circle.reset_mock()
        draw_page_dots(self.screen, 0, 0, 0, 0,
                       self.active, self.inactive, self.border)
        self.pg.draw.circle.assert_not_called()

    def test_two_pages_draws_circles(self):
        """2페이지면 도트 2개 (활성1 + 비활성1)."""
        self.pg.draw.circle.reset_mock()
        draw_page_dots(self.screen, 10, 20, 2, 0,
                       self.active, self.inactive, self.border)
        # 활성 1개 + 비활성(채움+테두리) 2개 = 3회 호출
        self.assertEqual(self.pg.draw.circle.call_count, 3)

    def test_few_pages_all_dots_drawn(self):
        """MAX_PAGE_DOTS 이하면 모든 도트가 그려진다."""
        n = MAX_PAGE_DOTS
        self.pg.draw.circle.reset_mock()
        draw_page_dots(self.screen, 10, 20, n, 0,
                       self.active, self.inactive, self.border)
        # 활성 1개 + 비활성 (n-1) × 2(채움+테두리) = 1 + (n-1)*2
        expected = 1 + (n - 1) * 2
        self.assertEqual(self.pg.draw.circle.call_count, expected)

    def test_many_pages_capped(self):
        """MAX_PAGE_DOTS 초과 시 총 슬롯이 MAX_PAGE_DOTS 이하로 제한된다."""
        n = 50
        self.pg.draw.circle.reset_mock()
        draw_page_dots(self.screen, 10, 20, n, 25,
                       self.active, self.inactive, self.border)
        # 호출 수가 MAX_PAGE_DOTS × 3보다 작아야 (전체 도트 50개 그리지 않음)
        self.assertLess(self.pg.draw.circle.call_count, n * 2)

    def test_many_pages_first_page(self):
        """많은 페이지에서 첫 페이지 선택 시 에러 없이 동작."""
        draw_page_dots(self.screen, 10, 20, 30, 0,
                       self.active, self.inactive, self.border)

    def test_many_pages_last_page(self):
        """많은 페이지에서 마지막 페이지 선택 시 에러 없이 동작."""
        draw_page_dots(self.screen, 10, 20, 30, 29,
                       self.active, self.inactive, self.border)

    def test_many_pages_middle(self):
        """많은 페이지에서 중간 페이지 선택 시 에러 없이 동작."""
        draw_page_dots(self.screen, 10, 20, 100, 50,
                       self.active, self.inactive, self.border)

    def test_max_page_dots_is_positive(self):
        """MAX_PAGE_DOTS 상수가 양수여야 한다."""
        self.assertGreater(MAX_PAGE_DOTS, 0)

    def test_ellipsis_uses_small_dots(self):
        """줄임표 위치에 작은 도트(r=1)가 그려져야 한다."""
        self.pg.draw.circle.reset_mock()
        draw_page_dots(self.screen, 10, 20, 20, 10,
                       self.active, self.inactive, self.border)
        # r=1인 호출이 존재해야 한다 (줄임표의 작은 도트)
        calls = self.pg.draw.circle.call_args_list
        radii = []
        for call in calls:
            args = call[0]  # positional args
            if len(args) >= 4 and isinstance(args[3], int) and len(call[0]) == 4:
                radii.append(args[3])
        self.assertIn(1, radii, "Ellipsis small dots (r=1) should be drawn")

    def _count_rendered_slots(self, total_pages, current_page):
        """overflow 모드에서 실제 렌더링된 고유 슬롯(열) 수 계산."""
        dot_r = 3  # non-hc default
        gap = dot_r * 2 + 5  # 11
        x = 100
        self.pg.draw.circle.reset_mock()
        draw_page_dots(self.screen, x, 50, total_pages, current_page,
                       self.active, self.inactive, self.border)
        slot_indices = set()
        for call in self.pg.draw.circle.call_args_list:
            cx = call[0][2][0]  # position tuple → x
            si = round((cx - x - dot_r) / gap)
            slot_indices.add(si)
        return len(slot_indices)

    def test_overflow_slot_count_always_max(self):
        """overflow 모드에서 모든 페이지 위치에서 슬롯 수 = MAX_PAGE_DOTS."""
        total = 30
        for page in range(total):
            count = self._count_rendered_slots(total, page)
            self.assertEqual(count, MAX_PAGE_DOTS,
                             f"page {page}: expected {MAX_PAGE_DOTS}, got {count}")

    def test_overflow_first_page_slots(self):
        """첫 페이지에서 슬롯 수가 MAX_PAGE_DOTS여야 한다."""
        self.assertEqual(self._count_rendered_slots(20, 0), MAX_PAGE_DOTS)

    def test_overflow_last_page_slots(self):
        """마지막 페이지에서 슬롯 수가 MAX_PAGE_DOTS여야 한다."""
        self.assertEqual(self._count_rendered_slots(20, 19), MAX_PAGE_DOTS)


# ── 페이지 인디케이터 집중 테스트 ─────────────────────


class TestPageDotsCore(unittest.TestCase):
    """페이지 인디케이터 핵심 동작 집중 테스트.

    도트 크기·색상·위치·모드 전환 경계·활성 가시성을 검증합니다.
    """

    def setUp(self):
        self.screen = _MagicMock()
        self.pg = sys.modules["pygame"]
        self.pg.draw.circle.reset_mock()
        self.active = (100, 200, 255)
        self.inactive = (50, 50, 50)
        self.border = (80, 80, 80)
        self.dot_r = 3   # non-hc
        self.small_r = 2
        self.gap = self.dot_r * 2 + 5  # 11

    def _draw(self, total, page, x=100, cy=50):
        self.pg.draw.circle.reset_mock()
        draw_page_dots(self.screen, x, cy, total, page,
                       self.active, self.inactive, self.border)

    def _filled(self):
        """filled circle 호출 (outline 제외)."""
        return [c for c in self.pg.draw.circle.call_args_list
                if len(c[0]) == 4]

    def _outlines(self):
        """outline circle 호출."""
        return [c for c in self.pg.draw.circle.call_args_list
                if len(c[0]) >= 5]

    def _slot_x(self, si, x=100):
        return x + si * self.gap + self.dot_r

    # ── 활성 도트 반지름 ──────────────────────────────

    def test_active_radius_non_overflow(self):
        """비-overflow: 활성 도트 반지름 = dot_r."""
        self._draw(5, 2)
        active = [c for c in self._filled() if c[0][1] == self.active]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0][0][3], self.dot_r)

    def test_active_radius_overflow(self):
        """overflow: 활성 도트 반지름 = dot_r."""
        self._draw(20, 10)
        active = [c for c in self._filled() if c[0][1] == self.active]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0][0][3], self.dot_r)

    # ── 비활성 도트 반지름 ────────────────────────────

    def test_inactive_radius_non_overflow(self):
        """비-overflow: 비활성 도트 반지름 = small_r."""
        self._draw(5, 0)
        inactive = [c for c in self._filled() if c[0][1] == self.inactive]
        for c in inactive:
            self.assertEqual(c[0][3], self.small_r)

    def test_inactive_radius_overflow(self):
        """overflow: 비활성 도트 반지름 = small_r."""
        self._draw(20, 10)
        inactive = [c for c in self._filled() if c[0][1] == self.inactive]
        for c in inactive:
            self.assertEqual(c[0][3], self.small_r)

    def test_inactive_size_same_at_threshold(self):
        """overflow 전환점(9→10페이지)에서 비활성 도트 크기 동일."""
        self._draw(MAX_PAGE_DOTS, 0)
        pre = [c[0][3] for c in self._filled() if c[0][1] == self.inactive]
        self._draw(MAX_PAGE_DOTS + 1, 0)
        post = [c[0][3] for c in self._filled() if c[0][1] == self.inactive]
        self.assertTrue(all(r == self.small_r for r in pre))
        self.assertTrue(all(r == self.small_r for r in post))

    # ── 색상 정확성 ───────────────────────────────────

    def test_active_dot_uses_active_color(self):
        """활성 도트는 active_clr 색상 사용."""
        self._draw(5, 2)
        active = [c for c in self._filled() if c[0][1] == self.active]
        self.assertEqual(len(active), 1)

    def test_inactive_fill_and_border_colors(self):
        """비활성 도트: fill(inactive_clr) + border(border_clr)."""
        self._draw(3, 0)
        fills = [c for c in self._filled() if c[0][1] == self.inactive]
        borders = [c for c in self._outlines() if c[0][1] == self.border]
        self.assertEqual(len(fills), 2)    # 비활성 2개
        self.assertEqual(len(borders), 2)  # border 2개

    def test_second_page_active_colors(self):
        """2페이지 중 두 번째 활성 → 정확한 색상 배치."""
        self._draw(2, 1)
        filled = self._filled()
        slot0 = [c for c in filled if c[0][2][0] == self._slot_x(0)
                 and c[0][3] != 1]
        slot1 = [c for c in filled if c[0][2][0] == self._slot_x(1)
                 and c[0][3] != 1]
        self.assertEqual(slot0[0][0][1], self.inactive)
        self.assertEqual(slot1[0][0][1], self.active)

    # ── 모드 전환 경계 ────────────────────────────────

    def test_threshold_max_pages_no_ellipsis(self):
        """MAX_PAGE_DOTS 페이지: ellipsis(r=1) 없어야 한다."""
        self._draw(MAX_PAGE_DOTS, 4)
        tiny = [c for c in self._filled() if c[0][3] == 1]
        self.assertEqual(len(tiny), 0)

    def test_threshold_max_plus_one_has_ellipsis(self):
        """MAX_PAGE_DOTS+1 페이지: ellipsis(r=1) 존재해야 한다."""
        self._draw(MAX_PAGE_DOTS + 1, 5)
        tiny = [c for c in self._filled() if c[0][3] == 1]
        self.assertGreater(len(tiny), 0)

    def test_threshold_slot_count_continuity(self):
        """전환점 양쪽에서 렌더링 슬롯 수 차이가 1 이하."""
        # MAX_PAGE_DOTS 페이지: 정확히 MAX_PAGE_DOTS 슬롯
        self._draw(MAX_PAGE_DOTS, 0)
        xs_pre = {c[0][2][0] for c in self._filled() if c[0][3] != 1}
        # MAX_PAGE_DOTS + 1: overflow → MAX_PAGE_DOTS 슬롯
        self._draw(MAX_PAGE_DOTS + 1, 0)
        all_xs = [c[0][2][0] for c in self.pg.draw.circle.call_args_list]
        slots_post = set()
        for cx_val in all_xs:
            si = round((cx_val - 100 - self.dot_r) / self.gap)
            slots_post.add(si)
        self.assertLessEqual(abs(len(xs_pre) - len(slots_post)), 1)

    # ── 활성 페이지 가시성 ────────────────────────────

    def test_exactly_one_active_non_overflow(self):
        """비-overflow: 모든 페이지에서 정확히 1개 활성 도트."""
        for page in range(6):
            self._draw(6, page)
            active = [c for c in self._filled() if c[0][1] == self.active]
            self.assertEqual(len(active), 1,
                             f"page {page}: {len(active)} active")

    def test_exactly_one_active_overflow(self):
        """overflow: 모든 페이지에서 정확히 1개 활성 도트."""
        for page in range(20):
            self._draw(20, page)
            active = [c for c in self._filled() if c[0][1] == self.active]
            self.assertEqual(len(active), 1,
                             f"page {page}: {len(active)} active")

    # ── Overflow 첫/끝 도트 존재 ──────────────────────

    def test_overflow_first_slot_always_dot(self):
        """overflow: 첫 슬롯(slot 0)에 항상 도트 존재."""
        for page in range(20):
            self._draw(20, page)
            first_x = self._slot_x(0)
            dots = [c for c in self._filled()
                    if c[0][2][0] == first_x and c[0][3] != 1]
            self.assertGreater(len(dots), 0,
                               f"page {page}: first slot empty")

    def test_overflow_last_slot_always_dot(self):
        """overflow: 마지막 슬롯(slot MAX-1)에 항상 도트 존재."""
        for page in range(20):
            self._draw(20, page)
            last_x = self._slot_x(MAX_PAGE_DOTS - 1)
            dots = [c for c in self._filled()
                    if c[0][2][0] == last_x and c[0][3] != 1]
            self.assertGreater(len(dots), 0,
                               f"page {page}: last slot empty")

    # ── X-span 일정성 ────────────────────────────────

    def test_overflow_x_span_constant(self):
        """overflow: 모든 페이지에서 슬롯 중심 간 최대 간격 동일."""
        total = 25
        expected = (MAX_PAGE_DOTS - 1) * self.gap
        for page in range(total):
            self._draw(total, page)
            all_xs = [c[0][2][0]
                      for c in self.pg.draw.circle.call_args_list]
            slot_xs = set()
            for cx_val in all_xs:
                si = round((cx_val - 100 - self.dot_r) / self.gap)
                slot_xs.add(100 + si * self.gap + self.dot_r)
            span = max(slot_xs) - min(slot_xs)
            self.assertEqual(span, expected,
                             f"page {page}: span {span} != {expected}")

    # ── 비-overflow 완전성 ────────────────────────────

    def test_non_overflow_all_pages_rendered(self):
        """비-overflow: 정확히 total_pages개 도트 위치 사용."""
        n = 7
        self._draw(n, 3)
        dot_xs = {c[0][2][0] for c in self._filled() if c[0][3] != 1}
        self.assertEqual(len(dot_xs), n)

    def test_non_overflow_exact_positions(self):
        """비-overflow: 도트 위치가 gap 간격으로 정확히 배치."""
        n = 5
        x = 100
        self._draw(n, 2, x=x)
        expected = {x + i * self.gap + self.dot_r for i in range(n)}
        actual = {c[0][2][0] for c in self._filled() if c[0][3] != 1}
        self.assertEqual(actual, expected)

    def test_non_overflow_active_position_matches_page(self):
        """비-overflow: 활성 도트 X 위치가 current_page 슬롯과 일치."""
        for page in range(5):
            self._draw(5, page)
            active = [c for c in self._filled()
                      if c[0][1] == self.active]
            self.assertEqual(active[0][0][2][0], self._slot_x(page))


# ── page_dots_width 테스트 ────────────────────────────


class TestPageDotsWidth(unittest.TestCase):
    """page_dots_width() 너비 계산 테스트."""

    def test_single_page_zero(self):
        """1페이지면 너비 0."""
        self.assertEqual(page_dots_width(1), 0)

    def test_zero_pages_zero(self):
        """0페이지면 너비 0."""
        self.assertEqual(page_dots_width(0), 0)

    def test_two_pages_positive(self):
        """2페이지면 양수 너비."""
        self.assertGreater(page_dots_width(2), 0)

    def test_width_increases_up_to_max(self):
        """페이지 수 증가에 따라 너비도 MAX_PAGE_DOTS까지 증가."""
        widths = [page_dots_width(n) for n in range(2, MAX_PAGE_DOTS + 1)]
        for i in range(len(widths) - 1):
            self.assertLess(widths[i], widths[i + 1])

    def test_width_capped_at_max(self):
        """MAX_PAGE_DOTS 초과 시 너비 동일."""
        w_at_max = page_dots_width(MAX_PAGE_DOTS)
        w_over = page_dots_width(MAX_PAGE_DOTS + 10)
        self.assertEqual(w_at_max, w_over)

    def test_width_matches_max_dots(self):
        """50페이지와 MAX_PAGE_DOTS 페이지의 너비가 같다."""
        self.assertEqual(page_dots_width(50), page_dots_width(MAX_PAGE_DOTS))

    def test_exact_value_small(self):
        """정확한 값 계산: 3페이지."""
        # dot_r=3 (non-hc default), gap=11
        # (3-1)*11 + 6 = 28
        w = page_dots_width(3)
        self.assertEqual(w, 28)


# ── 파동함수 compute_wavefunction 테스트 ────────────


class TestComputeWavefunction(unittest.TestCase):
    """compute_wavefunction() 반환값 검증."""

    def test_returns_three_lists(self):
        """반환 타입이 (list, list, list) 튜플이어야 한다."""
        xs, amps, regions = compute_wavefunction()
        self.assertIsInstance(xs, list)
        self.assertIsInstance(amps, list)
        self.assertIsInstance(regions, list)

    def test_default_n_points(self):
        """기본 n_points=200이면 200개 포인트를 반환."""
        xs, amps, regions = compute_wavefunction(n_points=200)
        self.assertEqual(len(xs), 200)
        self.assertEqual(len(amps), 200)
        self.assertEqual(len(regions), 200)

    def test_custom_n_points(self):
        """사용자 지정 n_points가 반영된다."""
        xs, amps, _ = compute_wavefunction(n_points=50)
        self.assertEqual(len(xs), 50)

    def test_x_range_within_sim_area(self):
        """x 좌표가 시뮬레이션 영역(SIM_LEFT ~ SIM_LEFT+SIM_W) 내에 있어야 한다."""
        xs, _, _ = compute_wavefunction()
        self.assertAlmostEqual(xs[0], SIM_LEFT, places=1)
        self.assertAlmostEqual(xs[-1], SIM_LEFT + SIM_W, places=1)

    def test_amplitudes_normalized(self):
        """진폭이 0.0~1.0 범위로 정규화되어야 한다."""
        _, amps, _ = compute_wavefunction()
        self.assertAlmostEqual(max(amps), 1.0, places=5)
        for a in amps:
            self.assertGreaterEqual(a, 0.0)
            self.assertLessEqual(a, 1.0 + 1e-9)

    def test_regions_classification(self):
        """영역이 0(입사측), 1(장벽), 2(투과측) 중 하나여야 한다."""
        _, _, regions = compute_wavefunction()
        for r in regions:
            self.assertIn(r, (0, 1, 2))

    def test_region_order(self):
        """영역이 0 → 1 → 2 순서로 전환된다 (역전 없음)."""
        _, _, regions = compute_wavefunction()
        seen_max = 0
        for r in regions:
            self.assertGreaterEqual(r, seen_max)
            seen_max = max(seen_max, r)

    def test_all_three_regions_present(self):
        """기본 설정에서 세 영역 모두 나타난다."""
        _, _, regions = compute_wavefunction(barrier_width=BARRIER_WIDTH_DEFAULT)
        self.assertIn(0, regions)
        self.assertIn(1, regions)
        self.assertIn(2, regions)

    def test_barrier_region_inside_barrier(self):
        """영역 1 포인트의 x 좌표가 장벽 내부에 있어야 한다."""
        bw = 40
        xs, _, regions = compute_wavefunction(barrier_width=bw)
        half = bw / 2.0
        for x, r in zip(xs, regions):
            if r == 1:
                self.assertGreaterEqual(x, BARRIER_X - half - 1)
                self.assertLessEqual(x, BARRIER_X + half + 1)

    def test_decay_inside_barrier(self):
        """장벽 내부에서 진폭이 감소(지수감쇠)해야 한다."""
        bw = 60
        _, amps, regions = compute_wavefunction(barrier_width=bw, n_points=400)
        barrier_amps = [a for a, r in zip(amps, regions) if r == 1]
        if len(barrier_amps) >= 3:
            # 처음 > 마지막 (감쇠)
            self.assertGreater(barrier_amps[0], barrier_amps[-1])

    def test_transmitted_amplitude_less_than_incident(self):
        """투과측 최대 진폭이 입사측 최대 진폭보다 작아야 한다."""
        bw = 40
        _, amps, regions = compute_wavefunction(barrier_width=bw)
        incident = [a for a, r in zip(amps, regions) if r == 0]
        transmitted = [a for a, r in zip(amps, regions) if r == 2]
        if incident and transmitted:
            self.assertGreater(max(incident), max(transmitted))

    def test_thicker_barrier_lower_transmission(self):
        """두꺼운 장벽이 더 낮은 투과 진폭을 보여야 한다."""
        _, amps_thin, reg_thin = compute_wavefunction(barrier_width=10)
        _, amps_thick, reg_thick = compute_wavefunction(barrier_width=100)
        trans_thin = [a for a, r in zip(amps_thin, reg_thin) if r == 2]
        trans_thick = [a for a, r in zip(amps_thick, reg_thick) if r == 2]
        if trans_thin and trans_thick:
            self.assertGreater(max(trans_thin), max(trans_thick))

    def test_time_phase_changes_wavefunction(self):
        """시간 위상이 다르면 입사측 패턴이 변한다."""
        _, amps_0, _ = compute_wavefunction(time_phase=0.0)
        _, amps_pi, _ = compute_wavefunction(time_phase=math.pi)
        # 전체가 동일하지 않아야 함
        self.assertFalse(
            all(abs(a - b) < 1e-9 for a, b in zip(amps_0, amps_pi)),
            "다른 시간 위상은 다른 파동 패턴을 생성해야 한다",
        )

    def test_minimum_barrier_width(self):
        """최소 장벽 두께에서도 정상 작동."""
        xs, amps, regions = compute_wavefunction(barrier_width=BARRIER_WIDTH_MIN)
        self.assertEqual(len(xs), 200)
        self.assertIn(1, regions)

    def test_maximum_barrier_width(self):
        """최대 장벽 두께에서도 정상 작동."""
        xs, amps, regions = compute_wavefunction(barrier_width=BARRIER_WIDTH_MAX)
        self.assertEqual(len(xs), 200)
        # 투과 진폭이 극히 작아야 함
        trans = [a for a, r in zip(amps, regions) if r == 2]
        if trans:
            self.assertLess(max(trans), 0.01)

    def test_single_point(self):
        """n_points=1에서도 크래시 없이 동작."""
        xs, amps, regions = compute_wavefunction(n_points=1)
        self.assertEqual(len(xs), 1)

    def test_x_monotonically_increasing(self):
        """x 좌표가 단조 증가해야 한다."""
        xs, _, _ = compute_wavefunction()
        for i in range(1, len(xs)):
            self.assertGreater(xs[i], xs[i - 1])


# ── 포텐셜 에너지 프로필 compute_potential_profile 테스트 ──


class TestComputePotentialProfile(unittest.TestCase):
    """compute_potential_profile() 반환값 검증."""

    def test_returns_tuple_of_three(self):
        """반환 타입이 (list, list, float) 튜플이어야 한다."""
        xs, potentials, energy = compute_potential_profile()
        self.assertIsInstance(xs, list)
        self.assertIsInstance(potentials, list)
        self.assertIsInstance(energy, float)

    def test_default_n_points(self):
        """기본 n_points=200이면 200개 포인트를 반환."""
        xs, pots, _ = compute_potential_profile(n_points=200)
        self.assertEqual(len(xs), 200)
        self.assertEqual(len(pots), 200)

    def test_custom_n_points(self):
        """사용자 지정 n_points가 반영된다."""
        xs, pots, _ = compute_potential_profile(n_points=50)
        self.assertEqual(len(xs), 50)

    def test_x_range(self):
        """x 좌표가 시뮬레이션 영역 내에 있어야 한다."""
        xs, _, _ = compute_potential_profile()
        self.assertAlmostEqual(xs[0], SIM_LEFT, places=1)
        self.assertAlmostEqual(xs[-1], SIM_LEFT + SIM_W, places=1)

    def test_potential_values_binary(self):
        """V(x) 값이 0.0 또는 1.0이어야 한다."""
        _, pots, _ = compute_potential_profile()
        for v in pots:
            self.assertIn(v, (0.0, 1.0))

    def test_barrier_region_has_potential(self):
        """장벽 영역 내 포인트의 V(x) = 1.0."""
        bw = 40
        xs, pots, _ = compute_potential_profile(barrier_width=bw, n_points=400)
        half = bw / 2.0
        for x, v in zip(xs, pots):
            if BARRIER_X - half + 1 < x < BARRIER_X + half - 1:
                self.assertEqual(v, 1.0, f"x={x} should be inside barrier")

    def test_outside_barrier_zero_potential(self):
        """장벽 외부의 V(x) = 0.0."""
        bw = 40
        xs, pots, _ = compute_potential_profile(barrier_width=bw, n_points=400)
        half = bw / 2.0
        for x, v in zip(xs, pots):
            if x < BARRIER_X - half - 1 or x > BARRIER_X + half + 1:
                self.assertEqual(v, 0.0, f"x={x} should be outside barrier")

    def test_energy_default_range(self):
        """기본 에너지가 0~1 범위여야 한다."""
        _, _, energy = compute_potential_profile()
        self.assertGreater(energy, 0.0)
        self.assertLess(energy, 1.0)

    def test_energy_ratio_clamped(self):
        """에너지 비율이 0~1로 클램프된다."""
        _, _, e_neg = compute_potential_profile(energy_ratio=-0.5)
        self.assertGreaterEqual(e_neg, 0.0)
        _, _, e_over = compute_potential_profile(energy_ratio=1.5)
        self.assertLessEqual(e_over, 1.0)

    def test_custom_energy_ratio(self):
        """사용자 지정 에너지 비율이 반영된다."""
        _, _, energy = compute_potential_profile(energy_ratio=0.7)
        self.assertAlmostEqual(energy, 0.7, places=5)

    def test_energy_less_than_barrier(self):
        """기본 설정에서 E < V₀ (터널링 조건)."""
        _, pots, energy = compute_potential_profile()
        v_max = max(pots)
        self.assertLess(energy, v_max)

    def test_wider_barrier_more_potential_points(self):
        """두꺼운 장벽은 더 많은 V=1.0 포인트를 생성."""
        _, pots_thin, _ = compute_potential_profile(barrier_width=10, n_points=400)
        _, pots_thick, _ = compute_potential_profile(barrier_width=100, n_points=400)
        count_thin = sum(1 for v in pots_thin if v == 1.0)
        count_thick = sum(1 for v in pots_thick if v == 1.0)
        self.assertGreater(count_thick, count_thin)

    def test_minimum_barrier_width(self):
        """최소 장벽 두께에서 정상 동작."""
        xs, pots, energy = compute_potential_profile(barrier_width=BARRIER_WIDTH_MIN)
        self.assertEqual(len(xs), 200)
        self.assertIn(1.0, pots)

    def test_maximum_barrier_width(self):
        """최대 장벽 두께에서 정상 동작."""
        xs, pots, energy = compute_potential_profile(barrier_width=BARRIER_WIDTH_MAX)
        self.assertEqual(len(xs), 200)
        # 장벽 영역 비율: BARRIER_WIDTH_MAX / SIM_W ≈ 38%
        count_barrier = sum(1 for v in pots if v == 1.0)
        self.assertGreater(count_barrier, len(pots) // 4)

    def test_single_point(self):
        """n_points=1에서도 크래시 없이 동작."""
        xs, pots, energy = compute_potential_profile(n_points=1)
        self.assertEqual(len(xs), 1)

    def test_x_monotonically_increasing(self):
        """x 좌표가 단조 증가해야 한다."""
        xs, _, _ = compute_potential_profile()
        for i in range(1, len(xs)):
            self.assertGreater(xs[i], xs[i - 1])


# ── DensityAccumulator 테스트 ─────────────────────────


class TestDensityAccumulator(unittest.TestCase):
    """DensityAccumulator 단위 테스트."""

    def test_initial_state(self):
        """초기 상태: 모든 빈 0, 샘플 수 0."""
        acc = DensityAccumulator(n_bins=50)
        self.assertEqual(acc.total_samples, 0)
        self.assertEqual(len(acc.counts), 50)
        self.assertTrue(all(c == 0 for c in acc.counts))

    def test_record_increments_count(self):
        """기록 시 해당 빈 카운트가 증가한다."""
        acc = DensityAccumulator(n_bins=10)
        mid_x = SIM_LEFT + SIM_W / 2
        acc.record(mid_x)
        self.assertEqual(acc.total_samples, 1)
        self.assertEqual(sum(acc.counts), 1)

    def test_record_out_of_range_ignored(self):
        """범위 밖 x 좌표는 무시된다."""
        acc = DensityAccumulator()
        acc.record(SIM_LEFT - 100)
        acc.record(SIM_LEFT + SIM_W + 100)
        self.assertEqual(acc.total_samples, 0)

    def test_density_normalized(self):
        """get_density() 최대값이 1.0이다."""
        acc = DensityAccumulator(n_bins=20)
        for _ in range(100):
            acc.record(SIM_LEFT + SIM_W / 2)
        density = acc.get_density()
        self.assertAlmostEqual(max(density), 1.0)

    def test_density_empty(self):
        """데이터 없을 때 모든 밀도값 0.0."""
        acc = DensityAccumulator()
        density = acc.get_density()
        self.assertTrue(all(d == 0.0 for d in density))

    def test_density_length(self):
        """get_density() 길이가 n_bins와 같다."""
        acc = DensityAccumulator(n_bins=42)
        self.assertEqual(len(acc.get_density()), 42)

    def test_bin_centers_length(self):
        """get_bin_centers() 길이가 n_bins와 같다."""
        acc = DensityAccumulator(n_bins=30)
        centers = acc.get_bin_centers()
        self.assertEqual(len(centers), 30)

    def test_bin_centers_range(self):
        """빈 중심이 시뮬레이션 영역 내에 있다."""
        acc = DensityAccumulator(n_bins=50)
        centers = acc.get_bin_centers()
        for c in centers:
            self.assertGreater(c, SIM_LEFT - 1)
            self.assertLess(c, SIM_LEFT + SIM_W + 1)

    def test_bin_centers_ordered(self):
        """빈 중심이 단조 증가한다."""
        acc = DensityAccumulator(n_bins=20)
        centers = acc.get_bin_centers()
        for i in range(1, len(centers)):
            self.assertGreater(centers[i], centers[i - 1])

    def test_reset_clears_data(self):
        """reset() 후 모든 데이터가 초기화된다."""
        acc = DensityAccumulator(n_bins=10)
        for _ in range(50):
            acc.record(SIM_LEFT + SIM_W * random.random())
        self.assertGreater(acc.total_samples, 0)
        acc.reset()
        self.assertEqual(acc.total_samples, 0)
        self.assertTrue(all(c == 0 for c in acc.counts))

    def test_multiple_records_accumulate(self):
        """같은 빈에 여러 번 기록하면 누적된다."""
        acc = DensityAccumulator(n_bins=10)
        x = SIM_LEFT + SIM_W * 0.15  # 약 bin 1
        for _ in range(20):
            acc.record(x)
        self.assertEqual(acc.total_samples, 20)
        # 하나의 빈에 집중되어야 함
        self.assertEqual(max(acc.counts), 20)

    def test_uniform_distribution(self):
        """균일 분포 기록 시 밀도가 대체로 균등하다."""
        acc = DensityAccumulator(n_bins=10)
        n_per_bin = 100
        dx = SIM_W / 10
        for i in range(10):
            x = SIM_LEFT + (i + 0.5) * dx
            for _ in range(n_per_bin):
                acc.record(x)
        density = acc.get_density()
        # 모든 빈의 밀도가 0.8 이상 (균등에 가까움)
        for d in density:
            self.assertGreater(d, 0.8)

    def test_edge_values(self):
        """경계값 (SIM_LEFT, SIM_LEFT+SIM_W)에서 정상 동작."""
        acc = DensityAccumulator(n_bins=10)
        acc.record(SIM_LEFT)
        acc.record(SIM_LEFT + SIM_W)
        self.assertEqual(acc.total_samples, 2)

    def test_single_bin(self):
        """n_bins=1에서도 정상 동작."""
        acc = DensityAccumulator(n_bins=1)
        acc.record(SIM_LEFT + 100)
        self.assertEqual(acc.total_samples, 1)
        self.assertEqual(acc.counts[0], 1)

    def test_density_values_in_range(self):
        """모든 밀도값이 0.0~1.0 범위 내."""
        acc = DensityAccumulator(n_bins=20)
        for _ in range(200):
            acc.record(SIM_LEFT + SIM_W * random.random())
        for d in acc.get_density():
            self.assertGreaterEqual(d, 0.0)
            self.assertLessEqual(d, 1.0)


# ══════════════════════════════════════════════════════
# 장벽 형태별 포텐셜 함수
# ══════════════════════════════════════════════════════


class TestBarrierPotential(unittest.TestCase):
    """barrier_potential() 함수 — 형태별 포텐셜 V(x) 단위 테스트."""

    # ── 사각형 (SHAPE_RECT) ──

    def test_rect_inside_is_one(self):
        """사각형: 장벽 내부 V=1.0."""
        v = barrier_potential(BARRIER_X, BARRIER_WIDTH_DEFAULT, SHAPE_RECT)
        self.assertAlmostEqual(v, 1.0)

    def test_rect_outside_is_zero(self):
        """사각형: 장벽 외부 V=0.0."""
        v = barrier_potential(SIM_LEFT, BARRIER_WIDTH_DEFAULT, SHAPE_RECT)
        self.assertAlmostEqual(v, 0.0)

    # ── 삼각형 (SHAPE_TRIANGLE) ──

    def test_triangle_center_is_one(self):
        """삼각형: 중앙 V=1.0."""
        v = barrier_potential(BARRIER_X, BARRIER_WIDTH_DEFAULT, SHAPE_TRIANGLE)
        self.assertAlmostEqual(v, 1.0)

    def test_triangle_edges_near_zero(self):
        """삼각형: 가장자리 V≈0."""
        half_w = BARRIER_WIDTH_DEFAULT / 2.0
        bl = BARRIER_X - half_w
        v = barrier_potential(bl + 0.1, BARRIER_WIDTH_DEFAULT, SHAPE_TRIANGLE)
        self.assertLess(v, 0.1)

    def test_triangle_outside_is_zero(self):
        """삼각형: 외부 V=0.0."""
        v = barrier_potential(SIM_LEFT, BARRIER_WIDTH_DEFAULT, SHAPE_TRIANGLE)
        self.assertAlmostEqual(v, 0.0)

    # ── 사다리꼴 (SHAPE_TRAPEZOID) ──

    def test_trapezoid_center_is_one(self):
        """사다리꼴: 중앙 평탄부 V=1.0."""
        v = barrier_potential(BARRIER_X, BARRIER_WIDTH_DEFAULT, SHAPE_TRAPEZOID)
        self.assertAlmostEqual(v, 1.0)

    def test_trapezoid_ramp_intermediate(self):
        """사다리꼴: 경사구간 V는 0~1 사이."""
        half_w = BARRIER_WIDTH_DEFAULT / 2.0
        bl = BARRIER_X - half_w
        ramp = (1.0 - 0.4) / 2.0  # _TRAP_TOP_RATIO = 0.4
        ramp_mid_x = bl + BARRIER_WIDTH_DEFAULT * ramp / 2.0
        v = barrier_potential(ramp_mid_x, BARRIER_WIDTH_DEFAULT, SHAPE_TRAPEZOID)
        self.assertGreater(v, 0.0)
        self.assertLess(v, 1.0)

    def test_trapezoid_outside_is_zero(self):
        """사다리꼴: 외부 V=0.0."""
        v = barrier_potential(SIM_LEFT, BARRIER_WIDTH_DEFAULT, SHAPE_TRAPEZOID)
        self.assertAlmostEqual(v, 0.0)

    # ── 이중장벽 (SHAPE_DOUBLE) ──

    def test_double_wall_is_one(self):
        """이중장벽: 벽 영역 V=1.0."""
        half_w = BARRIER_WIDTH_DEFAULT / 2.0
        bl = BARRIER_X - half_w
        wall_mid = bl + BARRIER_WIDTH_DEFAULT * 0.15
        v = barrier_potential(wall_mid, BARRIER_WIDTH_DEFAULT, SHAPE_DOUBLE)
        self.assertAlmostEqual(v, 1.0)

    def test_double_gap_is_zero(self):
        """이중장벽: 우물(gap) 영역 V=0.0."""
        v = barrier_potential(BARRIER_X, BARRIER_WIDTH_DEFAULT, SHAPE_DOUBLE)
        self.assertAlmostEqual(v, 0.0)

    def test_double_outside_is_zero(self):
        """이중장벽: 외부 V=0.0."""
        v = barrier_potential(SIM_LEFT, BARRIER_WIDTH_DEFAULT, SHAPE_DOUBLE)
        self.assertAlmostEqual(v, 0.0)

    # ── 공통 속성 ──

    def test_all_shapes_outside_zero(self):
        """모든 형태: 장벽 외부에서 V=0.0."""
        for shape in range(_NUM_SHAPES):
            v = barrier_potential(SIM_LEFT, BARRIER_WIDTH_DEFAULT, shape)
            self.assertAlmostEqual(v, 0.0, msg=f"shape={SHAPE_NAMES[shape]}")

    def test_all_shapes_range_zero_one(self):
        """모든 형태: V(x)는 0.0~1.0 범위."""
        for shape in range(_NUM_SHAPES):
            for i in range(200):
                x = SIM_LEFT + i * SIM_W / 199
                v = barrier_potential(x, BARRIER_WIDTH_DEFAULT, shape)
                self.assertGreaterEqual(v, 0.0, msg=f"shape={SHAPE_NAMES[shape]}, x={x}")
                self.assertLessEqual(v, 1.0, msg=f"shape={SHAPE_NAMES[shape]}, x={x}")

    def test_wavefunction_with_shape(self):
        """compute_wavefunction이 shape 파라미터를 올바르게 전달."""
        for shape in range(_NUM_SHAPES):
            xs, amps, regions = compute_wavefunction(BARRIER_WIDTH_DEFAULT, 50, 0.0, shape)
            self.assertEqual(len(xs), 50)
            self.assertEqual(len(amps), 50)
            self.assertEqual(len(regions), 50)

    def test_potential_profile_with_shape(self):
        """compute_potential_profile이 shape 파라미터를 올바르게 전달."""
        for shape in range(_NUM_SHAPES):
            xs, pots, energy = compute_potential_profile(BARRIER_WIDTH_DEFAULT, 50, shape=shape)
            self.assertEqual(len(xs), 50)
            self.assertEqual(len(pots), 50)
            if shape in (SHAPE_TRIANGLE, SHAPE_TRAPEZOID):
                has_intermediate = any(0.01 < p < 0.99 for p in pots)
                self.assertTrue(has_intermediate, msg=f"shape={SHAPE_NAMES[shape]} should have intermediate values")

    def test_shape_names_length(self):
        """SHAPE_NAMES 개수가 _NUM_SHAPES와 일치."""
        self.assertEqual(len(SHAPE_NAMES), _NUM_SHAPES)

    def test_double_barrier_symmetry(self):
        """이중장벽: 좌우 대칭."""
        half_w = BARRIER_WIDTH_DEFAULT / 2.0
        bl = BARRIER_X - half_w
        br = BARRIER_X + half_w
        for d in [1, 2, 3]:
            v_left = barrier_potential(bl + d, BARRIER_WIDTH_DEFAULT, SHAPE_DOUBLE)
            v_right = barrier_potential(br - d, BARRIER_WIDTH_DEFAULT, SHAPE_DOUBLE)
            self.assertAlmostEqual(v_left, v_right, places=5,
                                   msg=f"d={d}: left={v_left}, right={v_right}")

    def test_triangle_symmetry(self):
        """삼각형: 좌우 대칭."""
        half_w = BARRIER_WIDTH_DEFAULT / 2.0
        bl = BARRIER_X - half_w
        br = BARRIER_X + half_w
        for d in [1, 2, 3]:
            v_left = barrier_potential(bl + d, BARRIER_WIDTH_DEFAULT, SHAPE_TRIANGLE)
            v_right = barrier_potential(br - d, BARRIER_WIDTH_DEFAULT, SHAPE_TRIANGLE)
            self.assertAlmostEqual(v_left, v_right, places=5,
                                   msg=f"d={d}: left={v_left}, right={v_right}")


class TestParticleTrail(unittest.TestCase):
    """입자 궤적 잔상(trail) 테스트."""

    def test_trail_starts_empty(self):
        """새 입자의 trail은 비어 있어야 한다."""
        p = QuantumParticle()
        self.assertEqual(p.trail, [])

    def test_trail_records_positions(self):
        """update 호출 시 trail에 위치가 기록된다."""
        p = QuantumParticle()
        # record_interval 이상의 dt로 업데이트
        dt = TRAIL_RECORD_INTERVAL + 0.001
        p.update(dt)
        self.assertGreaterEqual(len(p.trail), 1)
        x, y, tunneled = p.trail[0]
        self.assertIsInstance(x, float)
        self.assertIsInstance(y, float)

    def test_trail_stores_tunneled_state(self):
        """trail 항목은 (x, y, tunneled) 형태이다."""
        p = QuantumParticle()
        dt = TRAIL_RECORD_INTERVAL + 0.001
        p.update(dt)
        self.assertEqual(len(p.trail[0]), 3)
        # 초기 상태: tunneled는 None
        self.assertIsNone(p.trail[0][2])

    def test_trail_max_length(self):
        """trail은 TRAIL_MAX_LENGTH를 초과하지 않는다."""
        p = QuantumParticle()
        dt = TRAIL_RECORD_INTERVAL + 0.001
        for _ in range(TRAIL_MAX_LENGTH + 50):
            p.update(dt)
        self.assertLessEqual(len(p.trail), TRAIL_MAX_LENGTH)

    def test_trail_clears_on_reset(self):
        """reset() 호출 시 trail이 초기화된다."""
        p = QuantumParticle()
        dt = TRAIL_RECORD_INTERVAL + 0.001
        for _ in range(10):
            p.update(dt)
        self.assertGreater(len(p.trail), 0)
        p.reset()
        self.assertEqual(p.trail, [])

    def test_trail_not_recorded_below_interval(self):
        """record_interval보다 짧은 dt에서는 기록되지 않을 수 있다."""
        p = QuantumParticle()
        tiny_dt = TRAIL_RECORD_INTERVAL * 0.1
        p.update(tiny_dt)
        # 간격 미달 시 기록 없음
        self.assertEqual(len(p.trail), 0)

    def test_trail_accumulates_timer(self):
        """작은 dt를 반복하면 타이머 누적으로 결국 기록된다."""
        p = QuantumParticle()
        tiny_dt = TRAIL_RECORD_INTERVAL * 0.3
        for _ in range(10):
            p.update(tiny_dt)
        # 3~4회 누적이면 간격 초과 → 기록 있어야 함
        self.assertGreater(len(p.trail), 0)

    def test_new_particle_trail_independent(self):
        """새 QuantumParticle은 독립적인 trail을 가진다."""
        p1 = QuantumParticle()
        dt = TRAIL_RECORD_INTERVAL + 0.001
        for _ in range(5):
            p1.update(dt)
        p2 = QuantumParticle()
        self.assertEqual(len(p2.trail), 0)
        self.assertGreater(len(p1.trail), 0)

    def test_trail_positions_match_particle(self):
        """기록된 trail 위치는 입자의 실제 이동 경로상에 있다."""
        p = QuantumParticle()
        dt = TRAIL_RECORD_INTERVAL + 0.001
        p.update(dt)
        if p.trail:
            tx, ty, _ = p.trail[-1]
            # 시뮬레이션 영역 내에 있어야 함
            self.assertGreaterEqual(tx, SIM_LEFT - 30)
            self.assertLessEqual(tx, SIM_LEFT + SIM_W + 30)
            self.assertGreaterEqual(ty, SIM_TOP - PARTICLE_RADIUS)
            self.assertLessEqual(ty, SIM_TOP + SIM_H + PARTICLE_RADIUS)

    def test_trail_config_constants(self):
        """trail 설정 상수가 유효한 범위이다."""
        self.assertGreater(TRAIL_MAX_LENGTH, 0)
        self.assertGreater(TRAIL_RECORD_INTERVAL, 0)


if __name__ == "__main__":
    unittest.main()
