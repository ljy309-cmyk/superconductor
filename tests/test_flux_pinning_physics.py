"""마이스너 부상 & 플럭스 피닝 — 스프링-댐퍼 물리 단위 테스트.

Pygame 렌더링 없이 FluxPinningState 데이터클래스와
물리 공식만 단독으로 테스트합니다.

v2: 온도 시스템, 2D 핀닝 잠금, sc_fraction, pin_force 테스트 추가.
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
    PIN_LOCK_RADIUS,
    SPRING_K,
    TC_KELVIN,
    TEMP_MIN,
    FluxPinningState,
    PinningSite,
    effective_spring_k,
    pin_force,
    sc_fraction,
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


def step_with_temperature(gs: FluxPinningState, dt: float, flipped: bool = False):
    """온도를 고려한 초전도 상태 물리 1스텝."""
    eff_k = effective_spring_k(gs.temperature)
    direction = 1 if flipped else -1
    target_x = gs.magnet_x
    target_y = gs.magnet_y + direction * EQUILIBRIUM_GAP

    dx = gs.sc_x - target_x
    dy = gs.sc_y - target_y
    ax = -eff_k * dx
    ay = -eff_k * dy

    if gs.pinned:
        frac = sc_fraction(gs.temperature)
        pfx, pfy = pin_force(gs.sc_x, gs.sc_y, gs.pin_anchor_x, gs.pin_anchor_y)
        ax += pfx * frac
        ay += pfy * frac

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

    def test_new_temperature_field(self):
        """새 온도 필드의 기본값 확인."""
        gs = FluxPinningState()
        self.assertEqual(gs.temperature, 4.0)
        self.assertFalse(gs.pinned)
        self.assertEqual(gs.pin_anchor_x, 0.0)
        self.assertEqual(gs.pin_anchor_y, 0.0)
        self.assertIsInstance(gs.pinning_sites, list)

    def test_pinning_site_creation(self):
        """PinningSite 데이터클래스 기본값."""
        site = PinningSite(rel_x=10.0, rel_y=5.0)
        self.assertEqual(site.rel_x, 10.0)
        self.assertFalse(site.flux_locked)
        self.assertEqual(site.lock_strength, 1.0)


# ── 온도-초전도 전이 테스트 ─────────────────────────────


class TestScFraction(unittest.TestCase):
    """sc_fraction(): 온도에 따른 초전도 분율."""

    def test_zero_temperature(self):
        """T=0K에서 분율은 1.0이어야 한다."""
        self.assertAlmostEqual(sc_fraction(0.0), 1.0)

    def test_negative_temperature(self):
        """음수 온도는 1.0으로 클램프."""
        self.assertAlmostEqual(sc_fraction(-10.0), 1.0)

    def test_at_tc(self):
        """T=Tc에서 분율은 0.0이어야 한다."""
        self.assertAlmostEqual(sc_fraction(TC_KELVIN), 0.0)

    def test_above_tc(self):
        """T>Tc에서 분율은 0.0이어야 한다."""
        self.assertAlmostEqual(sc_fraction(TC_KELVIN + 10), 0.0)
        self.assertAlmostEqual(sc_fraction(200.0), 0.0)

    def test_half_tc(self):
        """T=Tc/2에서 분율은 0.75 (1 - 0.5^2)."""
        half_tc = TC_KELVIN / 2.0
        expected = 1.0 - (half_tc / TC_KELVIN) ** 2
        self.assertAlmostEqual(sc_fraction(half_tc), expected, places=5)

    def test_monotonically_decreasing(self):
        """온도 증가 시 분율은 단조 감소해야 한다."""
        prev = sc_fraction(TEMP_MIN)
        for temp in range(int(TEMP_MIN) + 1, int(TC_KELVIN)):
            current = sc_fraction(float(temp))
            self.assertLessEqual(current, prev)
            prev = current

    def test_custom_tc(self):
        """커스텀 Tc 값으로도 올바르게 동작."""
        self.assertAlmostEqual(sc_fraction(50.0, tc=50.0), 0.0)
        self.assertAlmostEqual(sc_fraction(0.0, tc=50.0), 1.0)
        self.assertAlmostEqual(sc_fraction(60.0, tc=50.0), 0.0)

    def test_range_zero_to_one(self):
        """모든 온도에서 0 <= frac <= 1."""
        for temp_int in range(0, 200):
            frac = sc_fraction(float(temp_int))
            self.assertGreaterEqual(frac, 0.0)
            self.assertLessEqual(frac, 1.0)


class TestEffectiveSpringK(unittest.TestCase):
    """effective_spring_k(): 온도에 따른 유효 스프링 상수."""

    def test_low_temperature(self):
        """저온에서 유효 K는 기본 K에 가까워야 한다."""
        eff = effective_spring_k(4.0)
        self.assertAlmostEqual(eff, SPRING_K * sc_fraction(4.0), places=3)
        self.assertGreater(eff, SPRING_K * 0.9)

    def test_at_tc_zero(self):
        """Tc 이상에서 유효 K는 0이어야 한다."""
        self.assertAlmostEqual(effective_spring_k(TC_KELVIN), 0.0)
        self.assertAlmostEqual(effective_spring_k(TC_KELVIN + 10), 0.0)

    def test_custom_base_k(self):
        """커스텀 base_k 전달 테스트."""
        eff = effective_spring_k(0.0, base_k=10.0)
        self.assertAlmostEqual(eff, 10.0)

    def test_weakens_near_tc(self):
        """Tc 근처에서 K가 약해져야 한다."""
        k_low = effective_spring_k(4.0)
        k_near_tc = effective_spring_k(TC_KELVIN * 0.95)
        self.assertGreater(k_low, k_near_tc)


# ── 2D 핀닝 잠금력 테스트 ────────────────────────────────


class TestPinForce(unittest.TestCase):
    """pin_force(): 핀닝 사이트의 잠금 복원력."""

    def test_at_anchor_no_force(self):
        """앵커 위치에서 힘은 0이어야 한다."""
        fx, fy = pin_force(100.0, 200.0, 100.0, 200.0)
        self.assertAlmostEqual(fx, 0.0)
        self.assertAlmostEqual(fy, 0.0)

    def test_within_radius_restoring(self):
        """잠금 반경 내에서 앵커 방향으로 복원력."""
        # 오른쪽으로 10px 이탈
        fx, fy = pin_force(110.0, 200.0, 100.0, 200.0)
        self.assertLess(fx, 0.0)  # 왼쪽으로 복원
        self.assertAlmostEqual(fy, 0.0, delta=0.01)

    def test_outside_radius_no_force(self):
        """잠금 반경 밖에서는 힘이 0이어야 한다."""
        far_x = 100.0 + PIN_LOCK_RADIUS + 10
        fx, fy = pin_force(far_x, 200.0, 100.0, 200.0)
        self.assertAlmostEqual(fx, 0.0)
        self.assertAlmostEqual(fy, 0.0)

    def test_force_proportional_to_distance(self):
        """힘은 거리에 비례해야 한다."""
        fx1, _ = pin_force(105.0, 200.0, 100.0, 200.0)
        fx2, _ = pin_force(110.0, 200.0, 100.0, 200.0)
        # 거리 2배 → 힘 2배
        self.assertAlmostEqual(abs(fx2) / abs(fx1), 2.0, delta=0.01)

    def test_y_direction(self):
        """Y축 방향 이탈에 대해서도 복원력."""
        _, fy = pin_force(100.0, 215.0, 100.0, 200.0)
        self.assertLess(fy, 0.0)  # 위쪽으로 복원

    def test_diagonal_force(self):
        """대각선 이탈 시 두 축 모두 복원력."""
        fx, fy = pin_force(110.0, 210.0, 100.0, 200.0)
        self.assertLess(fx, 0.0)
        self.assertLess(fy, 0.0)

    def test_custom_parameters(self):
        """커스텀 k, lock_radius 전달."""
        fx, fy = pin_force(110.0, 200.0, 100.0, 200.0, lock_radius=5.0)
        # 거리 10 > lock_radius 5 → 힘 0
        self.assertAlmostEqual(fx, 0.0)
        self.assertAlmostEqual(fy, 0.0)

    def test_at_boundary(self):
        """잠금 반경 경계에서 최대 힘."""
        fx, _ = pin_force(100.0 + PIN_LOCK_RADIUS, 200.0, 100.0, 200.0)
        # 경계에서는 힘이 0이 아님
        self.assertLess(fx, 0.0)

    def test_just_outside_boundary(self):
        """잠금 반경 바로 밖에서 힘은 0."""
        fx, fy = pin_force(100.0 + PIN_LOCK_RADIUS + 0.2, 200.0, 100.0, 200.0)
        self.assertAlmostEqual(fx, 0.0)
        self.assertAlmostEqual(fy, 0.0)


# ── 온도 연동 물리 통합 테스트 ────────────────────────────


class TestTemperaturePhysicsIntegration(unittest.TestCase):
    """온도 변화에 따른 부양/낙하 시나리오 통합 테스트."""

    def test_low_temp_levitation(self):
        """저온(4K)에서 정상 부양 수렴."""
        gs = FluxPinningState(
            magnet_x=450.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=100.0,
            temperature=4.0,
        )
        dt = 1 / 60.0
        target_y = gs.magnet_y - EQUILIBRIUM_GAP

        for _ in range(600):
            step_with_temperature(gs, dt)

        self.assertAlmostEqual(gs.sc_y, target_y, delta=1.0)

    def test_above_tc_no_spring(self):
        """Tc 이상에서 스프링 상수가 0 → 초전도체 움직이지 않음 (외력 없음)."""
        gs = FluxPinningState(
            magnet_x=450.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=200.0,
            temperature=TC_KELVIN + 10,
        )
        initial_y = gs.sc_y
        step_with_temperature(gs, 1 / 60.0)
        # K=0이므로 힘 없음, 속도도 0이므로 위치 변화 없음 (댐핑 후)
        self.assertAlmostEqual(gs.sc_y, initial_y, delta=0.1)

    def test_weaker_spring_near_tc(self):
        """Tc 근처에서 스프링 약화 → 초기 반응 속도 느려짐."""
        dt = 1 / 60.0

        # 저온 (강한 스프링) — 초기 10스텝에서 더 빠르게 이동
        gs_low = FluxPinningState(
            magnet_x=450.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=100.0,
            temperature=4.0,
        )
        for _ in range(10):
            step_with_temperature(gs_low, dt)
        low_movement = abs(gs_low.sc_y - 100.0)

        # 고온 근처 (약한 스프링) — 초기 10스텝에서 더 느리게 이동
        gs_high = FluxPinningState(
            magnet_x=450.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=100.0,
            temperature=TC_KELVIN * 0.9,
        )
        for _ in range(10):
            step_with_temperature(gs_high, dt)
        high_movement = abs(gs_high.sc_y - 100.0)

        # 강한 스프링이 초기에 더 많이 이동
        self.assertGreater(low_movement, high_movement)


class TestPinningLockPhysics(unittest.TestCase):
    """2D 핀닝 잠금 효과 통합 테스트."""

    def test_pinned_resists_lateral_movement(self):
        """핀닝 잠금 시 수평 이동에 저항."""
        dt = 1 / 60.0

        # 핀닝 없이
        gs_free = FluxPinningState(
            magnet_x=450.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=300.0 - EQUILIBRIUM_GAP,
            temperature=4.0,
            pinned=False,
        )
        gs_free.magnet_x = 550.0  # 자석 수평 이동
        for _ in range(60):
            step_with_temperature(gs_free, dt)

        # 핀닝 잠금
        gs_pin = FluxPinningState(
            magnet_x=450.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=300.0 - EQUILIBRIUM_GAP,
            temperature=4.0,
            pinned=True,
            pin_anchor_x=450.0,
            pin_anchor_y=300.0 - EQUILIBRIUM_GAP,
        )
        gs_pin.magnet_x = 550.0
        for _ in range(60):
            step_with_temperature(gs_pin, dt)

        # 핀닝된 쪽이 수평 이동량이 적어야 함 (앵커에 붙잡혀 있으므로)
        free_dx = abs(gs_free.sc_x - 450.0)
        pin_dx = abs(gs_pin.sc_x - 450.0)
        self.assertLess(pin_dx, free_dx)

    def test_pinning_weakens_at_high_temp(self):
        """고온에서 전체 힘이 약화 → 초기 반응 속도 둔화."""
        dt = 1 / 60.0

        # 저온 핀닝 — 강한 스프링 + 강한 핀
        gs_cold = FluxPinningState(
            magnet_x=500.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=300.0 - EQUILIBRIUM_GAP,
            temperature=4.0,
            pinned=True,
            pin_anchor_x=450.0,
            pin_anchor_y=300.0 - EQUILIBRIUM_GAP,
        )
        for _ in range(10):
            step_with_temperature(gs_cold, dt)
        cold_movement = abs(gs_cold.sc_x - 450.0)

        # 고온 핀닝 — 약한 스프링 + 약한 핀 (전반적 둔화)
        gs_hot = FluxPinningState(
            magnet_x=500.0,
            magnet_y=300.0,
            sc_x=450.0,
            sc_y=300.0 - EQUILIBRIUM_GAP,
            temperature=TC_KELVIN * 0.95,
            pinned=True,
            pin_anchor_x=450.0,
            pin_anchor_y=300.0 - EQUILIBRIUM_GAP,
        )
        for _ in range(10):
            step_with_temperature(gs_hot, dt)
        hot_movement = abs(gs_hot.sc_x - 450.0)

        # 저온에서 전체 힘이 강하므로 초기 이동량이 더 큼
        self.assertGreater(cold_movement, hot_movement)


if __name__ == "__main__":
    unittest.main()
