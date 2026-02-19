"""터널링 물리 함수 단위 테스트."""

import math
import os
import sys
import unittest
from unittest.mock import patch

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
    _TUNNEL_DECAY,
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


class TestSuperpositionAlpha(unittest.TestCase):
    """superposition_alpha() — 블로흐 구 각도 테스트."""

    def test_range_zero_to_pi(self):
        p = QuantumParticle()
        for t_ms in range(0, 2000, 10):
            alpha = p.superposition_alpha(float(t_ms))
            self.assertGreaterEqual(alpha, 0.0)
            self.assertLessEqual(alpha, math.pi)

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
        # reset 후 초기 위치로
        self.assertAlmostEqual(p.x, SIM_LEFT + 40.0)
        self.assertIsNone(p.tunneled)
        # 카운터는 보존
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


class TestTunnelingCollision(unittest.TestCase):
    """장벽 충돌 시 터널링/반사 판정 테스트."""

    def test_tunnel_success(self):
        """tunnel_prob=1.0이면 항상 터널링."""
        p = QuantumParticle()
        # 장벽 바로 앞으로 이동
        p.x = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1
        p.vx = PARTICLE_SPEED
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=1.0)
        self.assertTrue(p.tunneled)
        self.assertEqual(p.tunnel_count, 1)
        self.assertEqual(p.total_attempts, 1)
        # 장벽 오른쪽으로 이동해야 함
        self.assertGreater(p.x, BARRIER_X)

    def test_tunnel_reflection(self):
        """tunnel_prob=0.0이면 항상 반사."""
        p = QuantumParticle()
        p.x = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1
        p.vx = PARTICLE_SPEED
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.0)
        self.assertFalse(p.tunneled)
        self.assertEqual(p.reflect_count, 1)
        self.assertEqual(p.total_attempts, 1)
        # 왼쪽으로 반사
        self.assertLess(p.vx, 0)

    def test_tunnel_speed_boost(self):
        """터널링 성공 시 속도 부스트 적용."""
        p = QuantumParticle()
        p.x = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1
        p.vx = PARTICLE_SPEED
        boost = 3.0
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=1.0, speed_boost=boost)
        self.assertAlmostEqual(p.vx, PARTICLE_SPEED * boost)

    def test_reflect_velocity_damping(self):
        """반사 시 0.8 감쇠."""
        p = QuantumParticle()
        p.x = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1
        p.vx = PARTICLE_SPEED
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.0)
        self.assertAlmostEqual(abs(p.vx), PARTICLE_SPEED * 0.8)

    def test_flash_timer_on_tunnel(self):
        p = QuantumParticle()
        p.x = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1
        p.vx = PARTICLE_SPEED
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=1.0)
        self.assertGreater(p.flash_timer, 0)

    def test_flash_timer_on_reflect(self):
        p = QuantumParticle()
        p.x = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1
        p.vx = PARTICLE_SPEED
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.0)
        self.assertGreater(p.flash_timer, 0)

    def test_no_collision_when_moving_left(self):
        """왼쪽 이동 시 장벽 판정 없음."""
        p = QuantumParticle()
        p.x = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1
        p.vx = -PARTICLE_SPEED  # 왼쪽 이동
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=1.0)
        self.assertIsNone(p.tunneled)
        self.assertEqual(p.total_attempts, 0)

    def test_no_double_collision(self):
        """이미 터널링/반사된 입자는 재판정하지 않음."""
        p = QuantumParticle()
        p.x = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1
        p.vx = PARTICLE_SPEED
        p.tunneled = True  # 이미 결정됨
        p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=1.0)
        self.assertEqual(p.total_attempts, 0)  # 재판정 없음

    def test_multiple_attempts_accumulate(self):
        """여러 시도의 카운터가 누적됨."""
        p = QuantumParticle()
        for _ in range(5):
            p.x = BARRIER_X - BARRIER_WIDTH_DEFAULT / 2 - PARTICLE_RADIUS + 1
            p.vx = PARTICLE_SPEED
            p.tunneled = None
            p.update(0.001, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.5)
        self.assertEqual(p.total_attempts, 5)
        self.assertEqual(p.tunnel_count + p.reflect_count, 5)


class TestBarrierWidthEffect(unittest.TestCase):
    """다양한 장벽 두께에서의 충돌 테스트."""

    def test_wide_barrier_collision_position(self):
        """두꺼운 장벽은 더 왼쪽에서 충돌."""
        wide = 100
        p = QuantumParticle()
        p.x = BARRIER_X - wide / 2 - PARTICLE_RADIUS + 1
        p.vx = PARTICLE_SPEED
        p.update(0.001, barrier_width=wide, tunnel_prob=1.0)
        # 터널링 후 장벽 오른쪽으로 이동
        self.assertGreater(p.x, BARRIER_X + wide / 2)

    def test_narrow_barrier_collision_position(self):
        """얇은 장벽은 더 오른쪽에서 충돌."""
        narrow = BARRIER_WIDTH_MIN
        p = QuantumParticle()
        p.x = BARRIER_X - narrow / 2 - PARTICLE_RADIUS + 1
        p.vx = PARTICLE_SPEED
        p.update(0.001, barrier_width=narrow, tunnel_prob=0.0)
        # 반사 후 장벽 왼쪽에 위치
        self.assertLess(p.x, BARRIER_X - narrow / 2)


if __name__ == "__main__":
    unittest.main()
