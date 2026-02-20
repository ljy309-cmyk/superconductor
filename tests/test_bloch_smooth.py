"""7-4  블로흐 구 보간 검증 — _bloch_smooth_theta lerp 타이밍 정확도 테스트.

_lerp 와 _bloch_smooth_theta 의 수학적 정확성, 프레임 속도 독립성,
수렴 속도, 타이밍 정밀도를 검증합니다.
"""

import math
import sys
import unittest
from unittest.mock import MagicMock

# ── GUI 의존성 차단 ─────────────────────────────────────
for mod in ("pygame", "pygame.locals", "matplotlib", "matplotlib.pyplot", "tkinter"):
    sys.modules.setdefault(mod, MagicMock())

from quantum.tunneling_physics import (  # noqa: E402
    BLOCH_LERP_SPEED,
    QuantumParticle,
    _bloch_smooth_theta,
    _lerp,
)

# ═══════════════════════════════════════════════════════════
# 1. _lerp 기본 동작
# ═══════════════════════════════════════════════════════════


class TestLerpBasic(unittest.TestCase):
    """_lerp: 기본 선형 보간 동작."""

    def test_at_zero(self):
        """t=0 → a 반환."""
        self.assertAlmostEqual(_lerp(10.0, 20.0, 0.0), 10.0)

    def test_at_one(self):
        """t=1 → b 반환."""
        self.assertAlmostEqual(_lerp(10.0, 20.0, 1.0), 20.0)

    def test_midpoint(self):
        """t=0.5 → (a+b)/2."""
        self.assertAlmostEqual(_lerp(0.0, 100.0, 0.5), 50.0)

    def test_quarter(self):
        """t=0.25 → a + 0.25*(b-a)."""
        self.assertAlmostEqual(_lerp(0.0, 100.0, 0.25), 25.0)

    def test_clamp_below_zero(self):
        """t < 0 → t=0 처리 (a 반환)."""
        self.assertAlmostEqual(_lerp(10.0, 20.0, -0.5), 10.0)

    def test_clamp_above_one(self):
        """t > 1 → t=1 처리 (b 반환)."""
        self.assertAlmostEqual(_lerp(10.0, 20.0, 1.5), 20.0)

    def test_same_values(self):
        """a == b → 모든 t에서 a 반환."""
        for t in (0.0, 0.3, 0.5, 0.7, 1.0):
            self.assertAlmostEqual(_lerp(5.0, 5.0, t), 5.0)

    def test_negative_range(self):
        """음수 범위에서도 정상 동작."""
        self.assertAlmostEqual(_lerp(-10.0, 10.0, 0.5), 0.0)

    def test_reverse_direction(self):
        """b < a 인 경우 t=0.5 → (a+b)/2."""
        self.assertAlmostEqual(_lerp(100.0, 0.0, 0.5), 50.0)


# ═══════════════════════════════════════════════════════════
# 2. _bloch_smooth_theta 기본 동작
# ═══════════════════════════════════════════════════════════


class TestBlochSmoothBasic(unittest.TestCase):
    """_bloch_smooth_theta: 기본 보간 동작."""

    def test_no_movement_at_target(self):
        """current == target → 변화 없음."""
        for theta in (0.0, math.pi / 4, math.pi / 2, math.pi):
            result = _bloch_smooth_theta(theta, theta, 1 / 60)
            self.assertAlmostEqual(result, theta, places=10)

    def test_no_movement_at_dt_zero(self):
        """dt=0 → current 그대로 반환."""
        result = _bloch_smooth_theta(0.5, 2.0, 0.0)
        self.assertAlmostEqual(result, 0.5)

    def test_moves_toward_target_increasing(self):
        """target > current → result가 current와 target 사이."""
        result = _bloch_smooth_theta(0.0, math.pi, 1 / 60)
        self.assertGreater(result, 0.0)
        self.assertLess(result, math.pi)

    def test_moves_toward_target_decreasing(self):
        """target < current → result가 target과 current 사이."""
        result = _bloch_smooth_theta(math.pi, 0.0, 1 / 60)
        self.assertLess(result, math.pi)
        self.assertGreater(result, 0.0)

    def test_result_in_valid_range(self):
        """출력이 항상 [0, π] 범위."""
        cases = [
            (0.0, math.pi, 0.5),
            (math.pi, 0.0, 0.5),
            (math.pi / 2, math.pi / 4, 0.01),
            (0.0, 0.0, 1.0),
        ]
        for cur, tgt, dt in cases:
            result = _bloch_smooth_theta(cur, tgt, dt)
            self.assertGreaterEqual(result, 0.0, f"cur={cur}, tgt={tgt}, dt={dt}")
            self.assertLessEqual(result, math.pi, f"cur={cur}, tgt={tgt}, dt={dt}")

    def test_default_speed_is_config(self):
        """기본 speed가 BLOCH_LERP_SPEED와 동일."""
        # 기본 speed 사용
        r1 = _bloch_smooth_theta(0.0, math.pi, 1 / 60)
        # 명시적으로 BLOCH_LERP_SPEED 지정
        r2 = _bloch_smooth_theta(0.0, math.pi, 1 / 60, speed=BLOCH_LERP_SPEED)
        self.assertAlmostEqual(r1, r2, places=12)


# ═══════════════════════════════════════════════════════════
# 3. 수렴 동작
# ═══════════════════════════════════════════════════════════


class TestBlochSmoothConvergence(unittest.TestCase):
    """_bloch_smooth_theta: 수렴 속성 검증."""

    def test_converges_after_many_steps(self):
        """충분한 스텝 후 target에 수렴."""
        current = 0.0
        target = math.pi
        dt = 1 / 60
        for _ in range(600):  # 10초 @ 60fps
            current = _bloch_smooth_theta(current, target, dt)
        self.assertAlmostEqual(current, target, places=5)

    def test_never_overshoots(self):
        """보간 중 절대로 overshoot 하지 않음."""
        current = 0.0
        target = math.pi
        dt = 1 / 60
        for _ in range(300):
            prev = current
            current = _bloch_smooth_theta(current, target, dt)
            self.assertGreaterEqual(current, prev, "overshoot 발생!")
            self.assertLessEqual(current, target, "target 초과!")

    def test_never_overshoots_decreasing(self):
        """감소 방향에서도 overshoot 없음."""
        current = math.pi
        target = 0.0
        dt = 1 / 60
        for _ in range(300):
            prev = current
            current = _bloch_smooth_theta(current, target, dt)
            self.assertLessEqual(current, prev, "overshoot 발생 (감소)!")
            self.assertGreaterEqual(current, target, "target 미만!")

    def test_monotonic_approach(self):
        """매 스텝마다 target에 더 가까워짐 (단조 수렴)."""
        current = 0.3
        target = 2.5
        dt = 1 / 60
        prev_dist = abs(target - current)
        for _ in range(200):
            current = _bloch_smooth_theta(current, target, dt)
            dist = abs(target - current)
            self.assertLessEqual(dist, prev_dist + 1e-12)
            prev_dist = dist

    def test_exponential_decay_single_step(self):
        """단일 스텝에서 해석적 수식과 정확히 일치."""
        current = 0.0
        target = math.pi
        dt = 0.05
        speed = 10.0
        expected_alpha = 1.0 - math.exp(-speed * dt)
        expected = current + (target - current) * expected_alpha
        result = _bloch_smooth_theta(current, target, dt, speed=speed)
        self.assertAlmostEqual(result, expected, places=10)


# ═══════════════════════════════════════════════════════════
# 4. 프레임 속도 독립성
# ═══════════════════════════════════════════════════════════


class TestBlochSmoothFrameRateIndependence(unittest.TestCase):
    """지수 보간은 프레임 속도와 무관하게 동일한 결과를 제공해야 합니다."""

    def _run_steps(self, current, target, dt, n_steps, speed=BLOCH_LERP_SPEED):
        """n_steps 만큼 보간 반복."""
        for _ in range(n_steps):
            current = _bloch_smooth_theta(current, target, dt, speed=speed)
        return current

    def test_60fps_vs_30fps(self):
        """60fps × 2프레임 ≈ 30fps × 1프레임 (동일 총 시간)."""
        cur, tgt, spd = 0.0, math.pi, 5.0
        r60 = self._run_steps(cur, tgt, 1 / 60, 2, speed=spd)
        r30 = self._run_steps(cur, tgt, 1 / 30, 1, speed=spd)
        # 지수 감쇠 보간은 정확히 일치하지는 않지만 매우 가까움
        self.assertAlmostEqual(r60, r30, places=2)

    def test_120fps_vs_60fps(self):
        """120fps × 120프레임 ≈ 60fps × 60프레임 (총 1초)."""
        cur, tgt, spd = 0.5, 2.5, 5.0
        r120 = self._run_steps(cur, tgt, 1 / 120, 120, speed=spd)
        r60 = self._run_steps(cur, tgt, 1 / 60, 60, speed=spd)
        self.assertAlmostEqual(r120, r60, places=2)

    def test_many_small_vs_few_large(self):
        """1000 × 0.001s ≈ 1 × 1.0s (총 1초)."""
        cur, tgt, spd = 0.0, math.pi, 3.0
        r_small = self._run_steps(cur, tgt, 0.001, 1000, speed=spd)
        r_large = self._run_steps(cur, tgt, 1.0, 1, speed=spd)
        self.assertAlmostEqual(r_small, r_large, places=2)

    def test_analytical_vs_iterative(self):
        """해석해: θ(T) = target - (target-current)*e^(-speed*T).

        반복 적용 vs 한 번의 큰 스텝 비교.
        """
        cur, tgt, spd = 0.2, 2.8, 6.0
        total_time = 0.5
        # 해석해
        analytical = tgt - (tgt - cur) * math.exp(-spd * total_time)
        analytical = max(0.0, min(math.pi, analytical))
        # 반복 (300 스텝)
        iterative = self._run_steps(cur, tgt, total_time / 300, 300, speed=spd)
        self.assertAlmostEqual(iterative, analytical, places=3)


# ═══════════════════════════════════════════════════════════
# 5. speed 파라미터 동작
# ═══════════════════════════════════════════════════════════


class TestBlochSmoothSpeed(unittest.TestCase):
    """speed 파라미터에 따른 보간 속도 변화."""

    def test_higher_speed_converges_faster(self):
        """speed가 높을수록 한 스텝에서 target에 더 가까이 접근."""
        cur, tgt, dt = 0.0, math.pi, 1 / 60
        r_slow = _bloch_smooth_theta(cur, tgt, dt, speed=2.0)
        r_fast = _bloch_smooth_theta(cur, tgt, dt, speed=20.0)
        self.assertGreater(r_fast, r_slow)

    def test_zero_speed_no_movement(self):
        """speed=0 → 이동 없음 (alpha=0)."""
        result = _bloch_smooth_theta(0.5, 2.0, 1.0, speed=0.0)
        self.assertAlmostEqual(result, 0.5)

    def test_very_high_speed_snaps_to_target(self):
        """speed 매우 크면 한 프레임 내 target에 도달."""
        result = _bloch_smooth_theta(0.0, math.pi / 2, 1 / 60, speed=1000.0)
        self.assertAlmostEqual(result, math.pi / 2, places=5)

    def test_speed_proportional_to_step_size(self):
        """동일 dt에서 speed ×2 → 더 큰 step."""
        cur, tgt, dt = 0.0, math.pi, 0.1
        r1 = _bloch_smooth_theta(cur, tgt, dt, speed=4.0)
        r2 = _bloch_smooth_theta(cur, tgt, dt, speed=8.0)
        step1 = r1 - cur
        step2 = r2 - cur
        self.assertGreater(step2, step1)


# ═══════════════════════════════════════════════════════════
# 6. 타이밍 정밀도
# ═══════════════════════════════════════════════════════════


class TestBlochSmoothTimingAccuracy(unittest.TestCase):
    """수학적 타이밍 정밀도 검증."""

    def test_exact_formula_known_dt(self):
        """알려진 dt에서 수식 정확도: current + (target-current)*(1-e^(-s*dt))."""
        cur, tgt, spd = 0.3, 2.5, 6.0
        for dt in (0.01, 0.02, 0.05, 0.1, 0.5, 1.0):
            expected = cur + (tgt - cur) * (1.0 - math.exp(-spd * dt))
            expected = max(0.0, min(math.pi, expected))
            result = _bloch_smooth_theta(cur, tgt, dt, speed=spd)
            self.assertAlmostEqual(result, expected, places=10, msg=f"dt={dt}")

    def test_half_life(self):
        """반감기: 거리가 절반이 되는 시간 = ln(2)/speed."""
        spd = 5.0
        half_life = math.log(2) / spd
        cur, tgt = 0.0, math.pi
        result = _bloch_smooth_theta(cur, tgt, half_life, speed=spd)
        # 반감기 후 target까지 거리 = 초기 거리의 절반
        expected_dist = (tgt - cur) / 2
        actual_dist = tgt - result
        self.assertAlmostEqual(actual_dist, expected_dist, places=8)

    def test_90_percent_convergence_time(self):
        """90% 수렴 시간: t_90 = ln(10)/speed."""
        spd = 5.0
        t_90 = math.log(10) / spd
        cur, tgt = 0.0, 2.0
        result = _bloch_smooth_theta(cur, tgt, t_90, speed=spd)
        # 90% 수렴 → 초기 거리의 10% 남음
        expected_remaining = (tgt - cur) * 0.1
        actual_remaining = tgt - result
        self.assertAlmostEqual(actual_remaining, expected_remaining, places=8)

    def test_99_percent_convergence_time(self):
        """99% 수렴 시간: t_99 = ln(100)/speed."""
        spd = 5.0
        t_99 = math.log(100) / spd
        cur, tgt = 0.0, 2.0
        result = _bloch_smooth_theta(cur, tgt, t_99, speed=spd)
        expected_remaining = (tgt - cur) * 0.01
        actual_remaining = tgt - result
        self.assertAlmostEqual(actual_remaining, expected_remaining, places=8)

    def test_consistent_across_starting_positions(self):
        """시작점 무관: 같은 (target-current) 차이 → 같은 이동량."""
        dt, spd = 0.05, 8.0
        alpha = 1.0 - math.exp(-spd * dt)
        # 두 가지 시작점, 같은 거리
        step_a = _bloch_smooth_theta(0.0, 1.0, dt, speed=spd) - 0.0
        step_b = _bloch_smooth_theta(1.0, 2.0, dt, speed=spd) - 1.0
        self.assertAlmostEqual(step_a, step_b, places=10)
        self.assertAlmostEqual(step_a, 1.0 * alpha, places=10)


# ═══════════════════════════════════════════════════════════
# 7. 엣지 케이스
# ═══════════════════════════════════════════════════════════


class TestBlochSmoothEdgeCases(unittest.TestCase):
    """_bloch_smooth_theta: 경계 조건 및 특수 케이스."""

    def test_pi_to_zero(self):
        """π → 0 보간: 결과는 (0, π) 범위."""
        result = _bloch_smooth_theta(math.pi, 0.0, 0.1)
        self.assertGreater(result, 0.0)
        self.assertLess(result, math.pi)

    def test_zero_to_pi(self):
        """0 → π 보간: 결과는 (0, π) 범위."""
        result = _bloch_smooth_theta(0.0, math.pi, 0.1)
        self.assertGreater(result, 0.0)
        self.assertLess(result, math.pi)

    def test_negative_dt_no_movement(self):
        """dt < 0 → current 그대로 (클램핑 적용)."""
        result = _bloch_smooth_theta(1.0, 2.0, -0.1)
        self.assertAlmostEqual(result, 1.0)

    def test_very_small_dt(self):
        """매우 작은 dt → 거의 이동 없음."""
        result = _bloch_smooth_theta(0.0, math.pi, 1e-10)
        # speed=8, dt=1e-10 → alpha ≈ 8e-10
        self.assertAlmostEqual(result, 0.0, places=6)

    def test_very_large_dt(self):
        """매우 큰 dt → target에 수렴."""
        result = _bloch_smooth_theta(0.0, math.pi / 2, 100.0)
        self.assertAlmostEqual(result, math.pi / 2, places=10)

    def test_clamp_output_above_pi(self):
        """current > π 인 경우 출력이 π로 클램핑."""
        # dt=0 이면 current 그대로 반환하지만 클램핑
        result = _bloch_smooth_theta(4.0, 0.0, 0.0)
        self.assertAlmostEqual(result, math.pi)

    def test_clamp_output_below_zero(self):
        """current < 0 인 경우 출력이 0으로 클램핑."""
        result = _bloch_smooth_theta(-1.0, 2.0, 0.0)
        self.assertAlmostEqual(result, 0.0)

    def test_both_at_zero(self):
        """current=0, target=0 → 0."""
        self.assertAlmostEqual(_bloch_smooth_theta(0.0, 0.0, 1.0), 0.0)

    def test_both_at_pi(self):
        """current=π, target=π → π."""
        self.assertAlmostEqual(_bloch_smooth_theta(math.pi, math.pi, 1.0), math.pi)


# ═══════════════════════════════════════════════════════════
# 8. QuantumParticle 연동
# ═══════════════════════════════════════════════════════════


class TestBlochSmoothWithParticle(unittest.TestCase):
    """_bloch_smooth_theta + QuantumParticle.superposition_alpha 연동."""

    def test_smooth_tracks_superposition_alpha(self):
        """smooth theta가 superposition_alpha를 추적 (지연 팔로잉)."""
        p = QuantumParticle()
        smooth_theta = p.superposition_alpha(0)
        dt = 1 / 60
        max_error = 0.0
        time_ms = 0.0
        for _ in range(300):
            time_ms += dt * 1000
            target = p.superposition_alpha(time_ms)
            smooth_theta = _bloch_smooth_theta(smooth_theta, target, dt)
            error = abs(smooth_theta - target)
            max_error = max(max_error, error)
        # 부드럽게 따라가므로 약간의 지연은 있지만 범위 내
        self.assertLess(max_error, math.pi)  # 절대 π 초과 오차 없음

    def test_smooth_stays_in_valid_range_during_tracking(self):
        """superposition_alpha 추적 중 항상 [0, π] 범위."""
        p = QuantumParticle()
        smooth_theta = math.pi / 2
        dt = 1 / 60
        time_ms = 0.0
        for _ in range(600):
            time_ms += dt * 1000
            target = p.superposition_alpha(time_ms)
            smooth_theta = _bloch_smooth_theta(smooth_theta, target, dt)
            self.assertGreaterEqual(smooth_theta, 0.0)
            self.assertLessEqual(smooth_theta, math.pi)

    def test_smooth_converges_to_static_alpha(self):
        """고정된 superposition_alpha 값에 수렴."""
        p = QuantumParticle()
        # superposition_alpha(0) = π/2 (sin(0)=0 → π*(1-0)/2 = π/2)
        target = p.superposition_alpha(0)
        self.assertAlmostEqual(target, math.pi / 2, places=8)

        smooth_theta = 0.0  # 먼 곳에서 시작
        for _ in range(600):
            smooth_theta = _bloch_smooth_theta(smooth_theta, target, 1 / 60)
        self.assertAlmostEqual(smooth_theta, math.pi / 2, places=4)

    def test_smooth_after_tunnel_snap(self):
        """터널링 후 θ=0 (|0⟩) 으로 급격 전환 시 부드러운 수렴."""
        # 터널링 이벤트 후 target을 0으로 설정한 시나리오
        smooth_theta = math.pi / 2  # 중첩 상태에서 시작
        target_after_tunnel = 0.0
        dt = 1 / 60

        history = [smooth_theta]
        for _ in range(120):  # 2초
            smooth_theta = _bloch_smooth_theta(smooth_theta, target_after_tunnel, dt)
            history.append(smooth_theta)

        # 단조 감소 (overshoot 없음)
        for i in range(1, len(history)):
            self.assertLessEqual(history[i], history[i - 1] + 1e-12)

        # 최종 수렴
        self.assertAlmostEqual(smooth_theta, 0.0, places=4)

    def test_smooth_after_reflect_snap(self):
        """반사 후 θ=π (|1⟩) 으로 급격 전환 시 부드러운 수렴."""
        smooth_theta = math.pi / 2
        target_after_reflect = math.pi
        dt = 1 / 60

        history = [smooth_theta]
        for _ in range(120):
            smooth_theta = _bloch_smooth_theta(smooth_theta, target_after_reflect, dt)
            history.append(smooth_theta)

        # 단조 증가
        for i in range(1, len(history)):
            self.assertGreaterEqual(history[i], history[i - 1] - 1e-12)

        # 최종 수렴
        self.assertAlmostEqual(smooth_theta, math.pi, places=4)


# ═══════════════════════════════════════════════════════════
# 9. lerp 와 smooth_theta 관계
# ═══════════════════════════════════════════════════════════


class TestLerpAndSmoothRelation(unittest.TestCase):
    """_lerp 와 _bloch_smooth_theta 사이의 수학적 관계."""

    def test_smooth_is_lerp_with_exponential_t(self):
        """smooth_theta 는 _lerp(cur, tgt, 1-e^(-s*dt)) 와 동일."""
        cur, tgt, dt, spd = 0.5, 2.5, 0.05, 6.0
        alpha = 1.0 - math.exp(-spd * dt)
        lerp_result = _lerp(cur, tgt, alpha)
        smooth_result = _bloch_smooth_theta(cur, tgt, dt, speed=spd)
        self.assertAlmostEqual(lerp_result, smooth_result, places=10)

    def test_smooth_at_large_dt_approaches_lerp_t1(self):
        """dt 매우 크면 alpha → 1 → _lerp(cur, tgt, 1) = tgt."""
        cur, tgt = 0.5, 2.0
        result = _bloch_smooth_theta(cur, tgt, 100.0, speed=5.0)
        self.assertAlmostEqual(result, tgt, places=8)

    def test_smooth_at_dt_zero_equals_lerp_t0(self):
        """dt=0 → alpha=0 → _lerp(cur, tgt, 0) = cur."""
        cur, tgt = 0.5, 2.0
        result = _bloch_smooth_theta(cur, tgt, 0.0, speed=5.0)
        self.assertAlmostEqual(result, cur)

    def test_lerp_symmetry(self):
        """_lerp(a, b, t) + _lerp(b, a, t) = a + b."""
        a, b, t = 1.0, 3.0, 0.3
        self.assertAlmostEqual(_lerp(a, b, t) + _lerp(b, a, t), a + b)

    def test_lerp_linearity(self):
        """_lerp 는 선형: lerp(a,b,t) = (1-t)*a + t*b."""
        a, b, t = 2.0, 8.0, 0.4
        expected = (1 - t) * a + t * b
        self.assertAlmostEqual(_lerp(a, b, t), expected)


# ═══════════════════════════════════════════════════════════
# 10. 연속 목표 변경 시나리오
# ═══════════════════════════════════════════════════════════


class TestBlochSmoothTargetSwitch(unittest.TestCase):
    """목표 θ가 동적으로 변경될 때의 동작."""

    def test_switch_target_mid_transition(self):
        """전환 중간에 target 변경 → 새 target으로 방향 전환."""
        smooth = 0.0
        dt = 1 / 60

        # 먼저 π 방향으로 60프레임
        for _ in range(60):
            smooth = _bloch_smooth_theta(smooth, math.pi, dt)
        mid_value = smooth
        self.assertGreater(mid_value, 0.0)

        # target을 0으로 변경 → 방향 전환
        for _ in range(300):
            smooth = _bloch_smooth_theta(smooth, 0.0, dt)
        self.assertAlmostEqual(smooth, 0.0, places=3)

    def test_oscillating_target(self):
        """교대로 바뀌는 target 추적 — 항상 [0, π] 범위."""
        smooth = math.pi / 2
        dt = 1 / 60
        for i in range(300):
            target = 0.0 if i % 60 < 30 else math.pi
            smooth = _bloch_smooth_theta(smooth, target, dt)
            self.assertGreaterEqual(smooth, 0.0)
            self.assertLessEqual(smooth, math.pi)

    def test_rapid_target_changes_bounded(self):
        """빠르게 target이 바뀌어도 출력이 항상 안정."""
        import random as rng

        rng.seed(42)
        smooth = math.pi / 2
        dt = 1 / 60
        for _ in range(500):
            target = rng.uniform(0.0, math.pi)
            smooth = _bloch_smooth_theta(smooth, target, dt)
            self.assertGreaterEqual(smooth, 0.0)
            self.assertLessEqual(smooth, math.pi)


if __name__ == "__main__":
    unittest.main()
