"""마이스너 부상 & 플럭스 피닝 — 스프링-댐퍼 물리 단위 테스트.

Pygame 렌더링 없이 FluxPinningState 데이터클래스와
물리 공식만 단독으로 테스트합니다.
"""

import math
import os
import sys
import unittest
from unittest.mock import MagicMock

# Pygame mock (렌더링 불필요)
sys.modules.setdefault("pygame", MagicMock())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from physics.flux_pinning import (
    DAMPING,
    EQUILIBRIUM_GAP,
    FLOOR_Y,
    GRAVITY,
    LEVITATION_AMP,
    LEVITATION_FREQ,
    SPRING_K,
    FluxPinningState,
)


def step_superconducting(gs: FluxPinningState, dt: float, flipped: bool = False):
    """초전도 상태 물리 1스텝 — run_simulation 루프에서 추출."""
    direction = 1 if flipped else -1
    target_x = gs.magnet_x
    target_y = gs.magnet_y + direction * EQUILIBRIUM_GAP

    dx = gs.sc_x - target_x
    dy = gs.sc_y - target_y
    ax = -SPRING_K * dx
    ay = -SPRING_K * dy

    gs.sc_vx = (gs.sc_vx + ax * dt) * DAMPING
    gs.sc_vy = (gs.sc_vy + ay * dt) * DAMPING
    gs.sc_x += gs.sc_vx
    gs.sc_y += gs.sc_vy
    gs.t += dt


def step_falling(gs: FluxPinningState, dt: float):
    """비초전도 상태(낙하) 물리 1스텝."""
    gs.sc_vy += GRAVITY * dt
    gs.sc_y += gs.sc_vy * dt
    if gs.sc_y >= FLOOR_Y:
        gs.sc_y = FLOOR_Y
        gs.sc_vy = 0.0
    gs.t += dt


class TestSpringDamperConvergence(unittest.TestCase):
    """스프링-댐퍼 시스템이 평형점에 수렴하는지 검증."""

    def test_converges_to_equilibrium(self):
        """초전도체가 자석 아래 EQUILIBRIUM_GAP 위치로 수렴해야 한다."""
        gs = FluxPinningState(
            magnet_x=450.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=100.0,  # 평형점에서 멀리 떨어진 초기 위치
        )
        dt = 1 / 60.0
        target_y = gs.magnet_y - EQUILIBRIUM_GAP

        for _ in range(600):  # 10초 시뮬레이션
            step_superconducting(gs, dt, flipped=False)

        self.assertAlmostEqual(gs.sc_y, target_y, delta=1.0)
        self.assertAlmostEqual(gs.sc_x, gs.magnet_x, delta=1.0)

    def test_converges_flipped(self):
        """flipped 모드에서 초전도체가 자석 아래로 수렴해야 한다."""
        gs = FluxPinningState(
            magnet_x=450.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=500.0,
        )
        dt = 1 / 60.0
        target_y = gs.magnet_y + EQUILIBRIUM_GAP

        for _ in range(600):
            step_superconducting(gs, dt, flipped=True)

        self.assertAlmostEqual(gs.sc_y, target_y, delta=1.0)

    def test_velocity_decays(self):
        """댐핑에 의해 속도가 시간에 따라 감소해야 한다."""
        gs = FluxPinningState(
            magnet_x=450.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=100.0,
            sc_vy=100.0,  # 큰 초기 속도
        )
        dt = 1 / 60.0

        for _ in range(300):
            step_superconducting(gs, dt)

        self.assertLess(abs(gs.sc_vy), 1.0)
        self.assertLess(abs(gs.sc_vx), 1.0)

    def test_follows_magnet_x(self):
        """자석이 수평 이동하면 초전도체가 따라가야 한다."""
        gs = FluxPinningState(
            magnet_x=450.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=300.0 - EQUILIBRIUM_GAP,
        )
        dt = 1 / 60.0

        # 자석을 오른쪽으로 이동
        gs.magnet_x = 600.0

        for _ in range(600):
            step_superconducting(gs, dt)

        self.assertAlmostEqual(gs.sc_x, 600.0, delta=1.0)


class TestSpringPhysics(unittest.TestCase):
    """스프링 힘 계산 정확성."""

    def test_spring_restoring_force(self):
        """변위 방향과 반대 방향으로 힘이 작용해야 한다."""
        gs = FluxPinningState(
            magnet_x=450.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=100.0,  # 평형점보다 위
        )
        initial_vy = gs.sc_vy
        step_superconducting(gs, 1 / 60.0)
        # 아래쪽(양의 y)으로 가속해야 함
        self.assertGreater(gs.sc_vy, initial_vy)

    def test_at_equilibrium_no_force(self):
        """평형점에서는 스프링 힘이 0이어야 한다."""
        target_y = 300.0 - EQUILIBRIUM_GAP
        gs = FluxPinningState(
            magnet_x=450.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=target_y,
            sc_vx=0.0,
            sc_vy=0.0,
        )
        step_superconducting(gs, 1 / 60.0)
        # 속도가 거의 0 유지
        self.assertAlmostEqual(gs.sc_vy, 0.0, delta=0.01)
        self.assertAlmostEqual(gs.sc_vx, 0.0, delta=0.01)

    def test_damping_factor(self):
        """DAMPING < 1이면 에너지가 매 스텝 감소해야 한다."""
        self.assertLess(DAMPING, 1.0)
        self.assertGreater(DAMPING, 0.0)


class TestGravityFall(unittest.TestCase):
    """비초전도 상태 (중력 낙하) 물리."""

    def test_falls_with_gravity(self):
        """초전도 해제 시 아래로 가속해야 한다."""
        gs = FluxPinningState(sc_y=200.0, sc_vy=0.0)
        step_falling(gs, 1 / 60.0)
        self.assertGreater(gs.sc_vy, 0.0)
        self.assertGreater(gs.sc_y, 200.0)

    def test_stops_at_floor(self):
        """바닥에 도달하면 멈춰야 한다."""
        gs = FluxPinningState(sc_y=FLOOR_Y - 1, sc_vy=500.0)
        step_falling(gs, 1 / 60.0)
        self.assertEqual(gs.sc_y, FLOOR_Y)
        self.assertEqual(gs.sc_vy, 0.0)

    def test_already_on_floor(self):
        """바닥에 있으면 추가 낙하 없어야 한다."""
        gs = FluxPinningState(sc_y=FLOOR_Y, sc_vy=0.0)
        step_falling(gs, 1 / 60.0)
        # 중력으로 vy 증가 후 sc_y가 FLOOR_Y 초과하면 클램프
        self.assertLessEqual(gs.sc_y, FLOOR_Y)

    def test_velocity_increases_linearly(self):
        """자유낙하 속도는 시간에 비례해야 한다."""
        gs = FluxPinningState(sc_y=100.0, sc_vy=0.0)
        dt = 1 / 60.0
        step_falling(gs, dt)
        expected_vy = GRAVITY * dt
        self.assertAlmostEqual(gs.sc_vy, expected_vy, delta=0.001)


class TestLevitationOscillation(unittest.TestCase):
    """부양 진동 효과 (LEVITATION_AMP, LEVITATION_FREQ)."""

    def test_oscillation_amplitude(self):
        """부양 진동 진폭이 LEVITATION_AMP를 초과하지 않아야 한다."""
        for t in [i * 0.01 for i in range(200)]:
            offset = LEVITATION_AMP * math.sin(LEVITATION_FREQ * 2 * math.pi * t)
            self.assertLessEqual(abs(offset), LEVITATION_AMP + 0.001)

    def test_oscillation_period(self):
        """주파수에 맞는 주기를 가져야 한다."""
        period = 1.0 / LEVITATION_FREQ
        # t=0에서 offset=0
        offset_0 = LEVITATION_AMP * math.sin(LEVITATION_FREQ * 2 * math.pi * 0)
        # t=period에서 offset≈0
        offset_T = LEVITATION_AMP * math.sin(LEVITATION_FREQ * 2 * math.pi * period)
        self.assertAlmostEqual(offset_0, 0.0, delta=0.001)
        self.assertAlmostEqual(offset_T, 0.0, delta=0.001)


class TestFluxPinningState(unittest.TestCase):
    """FluxPinningState 데이터클래스."""

    def test_default_values(self):
        gs = FluxPinningState()
        self.assertEqual(gs.sc_vx, 0.0)
        self.assertEqual(gs.sc_vy, 0.0)
        self.assertTrue(gs.superconducting)
        self.assertFalse(gs.flipped)
        self.assertFalse(gs.dragging)


if __name__ == "__main__":
    unittest.main()
