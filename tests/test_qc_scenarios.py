"""양자 vs 고전 비교 시나리오 테스트.

Quantum vs Classical (QC) 비교 결과를 체계적으로 검증합니다:

1. 터널링: 고전(반사 100%) vs 양자(확률적 투과)
2. 중첩: 고전(0 또는 1 고정) vs 양자(시간에 따라 진동)
3. CHSH 부등식: 고전 한계(|S|≤2) vs 양자 위반(|S|≤2√2)
4. 벨 상태 상관: 고전 독립 vs 양자 비국소 상관
"""

import math
import os
import random
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


# ═══════════════════════════════════════════════════════
# 1. 터널링: 고전 vs 양자
# ═══════════════════════════════════════════════════════


class TestTunnelingClassicalVsQuantum(unittest.TestCase):
    """고전 역학에서는 E < V 장벽을 절대 통과 못하지만,
    양자 역학에서는 확률적으로 투과한다."""

    def test_classical_always_reflects(self):
        """고전 시나리오: tunnel_prob=0 → 100% 반사, 터널링 0건."""
        from quantum.tunneling_physics import BARRIER_WIDTH_DEFAULT, QuantumParticle

        p = QuantumParticle()
        n_trials = 200
        for _ in range(n_trials):
            p.reset()
            # 장벽 도달까지 전진
            for _ in range(500):
                p.update(1 / 60, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.0)
                if p.tunneled is not None:
                    break

        self.assertEqual(p.tunnel_count, 0, "Classical: zero tunneling expected")
        self.assertEqual(p.reflect_count, p.total_attempts, "Classical: all attempts should reflect")

    def test_quantum_tunnels_sometimes(self):
        """양자 시나리오: tunnel_prob=0.5 → 터널링이 발생해야 함."""
        from quantum.tunneling_physics import BARRIER_WIDTH_DEFAULT, QuantumParticle

        p = QuantumParticle()
        n_trials = 300
        for _ in range(n_trials):
            p.reset()
            for _ in range(500):
                p.update(1 / 60, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=0.5)
                if p.tunneled is not None:
                    break

        self.assertGreater(p.tunnel_count, 0, "Quantum: some tunneling expected")
        self.assertGreater(p.reflect_count, 0, "Quantum: some reflection expected")
        self.assertEqual(p.tunnel_count + p.reflect_count, p.total_attempts)

    def test_quantum_guaranteed_tunneling(self):
        """tunnel_prob=1.0 → 모든 시행에서 터널링 성공."""
        from quantum.tunneling_physics import BARRIER_WIDTH_DEFAULT, QuantumParticle

        p = QuantumParticle()
        n_trials = 100
        for _ in range(n_trials):
            p.reset()
            for _ in range(500):
                p.update(1 / 60, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=1.0)
                if p.tunneled is not None:
                    break

        self.assertEqual(p.tunnel_count, p.total_attempts, "prob=1.0: all should tunnel")
        self.assertEqual(p.reflect_count, 0)

    def test_tunneling_rate_approximates_probability(self):
        """충분히 많은 시행 → 실측 터널링 비율이 이론 확률에 수렴 (대수의 법칙)."""
        from quantum.tunneling_physics import BARRIER_WIDTH_DEFAULT, QuantumParticle

        target_prob = 0.3
        p = QuantumParticle()
        n_trials = 1000
        for _ in range(n_trials):
            p.reset()
            for _ in range(500):
                p.update(1 / 60, barrier_width=BARRIER_WIDTH_DEFAULT, tunnel_prob=target_prob)
                if p.tunneled is not None:
                    break

        actual_rate = p.tunnel_count / max(p.total_attempts, 1)
        # 5σ 범위: ±5 * sqrt(p(1-p)/n) ≈ ±0.072
        tolerance = 5 * math.sqrt(target_prob * (1 - target_prob) / max(p.total_attempts, 1))
        self.assertAlmostEqual(
            actual_rate,
            target_prob,
            delta=tolerance,
            msg=f"Rate {actual_rate:.3f} should be ~{target_prob} (±{tolerance:.3f})",
        )


class TestTunnelingBarrierPhysics(unittest.TestCase):
    """장벽 두께에 따른 양자 터널링 확률 — 고전에는 없는 현상."""

    def test_exponential_decay_matches_formula(self):
        """T ≈ e^(-2κL) 형태의 지수 감쇠 검증."""
        from quantum.tunneling_physics import (
            _TUNNEL_DECAY,
            BARRIER_WIDTH_DEFAULT,
            TUNNEL_PROB_BASE,
            _calc_tunnel_prob,
        )

        for w in [4, 12, 50, 100, 150, 200]:
            expected = TUNNEL_PROB_BASE * math.exp(-_TUNNEL_DECAY * (w - BARRIER_WIDTH_DEFAULT))
            actual = _calc_tunnel_prob(w)
            self.assertAlmostEqual(actual, expected, places=12, msg=f"Width={w}: formula mismatch")

    def test_thicker_barrier_less_tunneling(self):
        """두꺼운 장벽 → 터널링 확률 감소 (고전에는 항상 0%)."""
        from quantum.tunneling_physics import _calc_tunnel_prob

        p_thin = _calc_tunnel_prob(10)
        p_medium = _calc_tunnel_prob(50)
        p_thick = _calc_tunnel_prob(150)

        self.assertGreater(p_thin, p_medium)
        self.assertGreater(p_medium, p_thick)
        # 양자: 항상 0보다 크다 (고전과의 핵심 차이)
        self.assertGreater(p_thick, 0, "Quantum: even thick barriers have nonzero probability")

    def test_classical_vs_quantum_barrier_response(self):
        """고전: 장벽 두께와 무관하게 투과=0.
        양자: 얇은 장벽에서 유의미한 투과, 두꺼운 장벽에서 작지만 0이 아닌 투과."""
        from quantum.tunneling_physics import (
            BARRIER_WIDTH_MAX,
            BARRIER_WIDTH_MIN,
            _calc_tunnel_prob,
        )

        classical_prob = 0.0  # 고전역학: 항상 0

        q_thin = _calc_tunnel_prob(BARRIER_WIDTH_MIN)
        q_thick = _calc_tunnel_prob(BARRIER_WIDTH_MAX)

        # 양자 확률은 고전(0)보다 항상 크다
        self.assertGreater(q_thin, classical_prob)
        self.assertGreater(q_thick, classical_prob)

        # 양자 확률은 얇을수록 유의미하게 크다
        self.assertGreater(q_thin, 0.05, "Thin barrier: significant tunneling")
        self.assertLess(q_thick, 0.01, "Thick barrier: negligible but nonzero tunneling")


class TestTunnelingParticlePosition(unittest.TestCase):
    """터널링/반사 후 입자의 위치 — 양자 터널링의 핵심 검증."""

    def test_tunneled_particle_passes_barrier(self):
        """터널링 성공 시 입자가 장벽 오른쪽에 위치."""
        from quantum.tunneling_physics import BARRIER_X, QuantumParticle

        p = QuantumParticle()
        for _ in range(200):
            p.reset()
            for _ in range(500):
                p.update(1 / 60, tunnel_prob=1.0)
                if p.tunneled is True:
                    break
            if p.tunneled is True:
                self.assertGreater(p.x, BARRIER_X, "Tunneled particle should be past barrier")
                return
        self.fail("No tunneling event occurred")

    def test_reflected_particle_stays_before_barrier(self):
        """반사 시 입자가 장벽 왼쪽에 위치."""
        from quantum.tunneling_physics import BARRIER_X, QuantumParticle

        p = QuantumParticle()
        for _ in range(200):
            p.reset()
            for _ in range(500):
                p.update(1 / 60, tunnel_prob=0.0)
                if p.tunneled is False:
                    break
            if p.tunneled is False:
                self.assertLess(p.x, BARRIER_X, "Reflected particle should be before barrier")
                return
        self.fail("No reflection event occurred")

    def test_reflected_particle_reverses_direction(self):
        """반사 시 입자의 수평 속도가 반전된다 (왼쪽으로)."""
        from quantum.tunneling_physics import QuantumParticle

        p = QuantumParticle()
        for _ in range(200):
            p.reset()
            for _ in range(500):
                p.update(1 / 60, tunnel_prob=0.0)
                if p.tunneled is False:
                    break
            if p.tunneled is False:
                self.assertLess(p.vx, 0, "Reflected particle should move left")
                return
        self.fail("No reflection event occurred")

    def test_tunneled_particle_speed_boosted(self):
        """터널링 성공 시 속도 부스트 적용."""
        from quantum.tunneling_physics import PARTICLE_SPEED, QuantumParticle

        boost = 3.0
        p = QuantumParticle()
        for _ in range(200):
            p.reset()
            for _ in range(500):
                p.update(1 / 60, tunnel_prob=1.0, speed_boost=boost)
                if p.tunneled is True:
                    break
            if p.tunneled is True:
                expected_vx = PARTICLE_SPEED * boost
                self.assertAlmostEqual(p.vx, expected_vx, delta=1.0)
                return
        self.fail("No tunneling event occurred")


# ═══════════════════════════════════════════════════════
# 2. 중첩: 고전 비트 vs 양자 큐비트
# ═══════════════════════════════════════════════════════


class TestSuperpositionClassicalVsQuantum(unittest.TestCase):
    """고전 비트는 0 또는 1로 고정되지만,
    양자 큐비트는 |0⟩과 |1⟩ 사이를 진동한다."""

    def test_classical_bit_is_fixed(self):
        """고전 비트: 한 번 정해지면 시간에 따라 변하지 않음."""
        classical_bit = 0
        for _ in range(100):
            self.assertEqual(classical_bit, 0)

    def test_quantum_qubit_oscillates(self):
        """양자 큐비트: 시간이 지나면 |0⟩과 |1⟩을 모두 방문."""
        from quantum.tunneling_physics import QuantumParticle

        p = QuantumParticle()
        states_seen = set()
        # 1초 동안 1ms 간격으로 관측
        for ms in range(0, 1000, 1):
            states_seen.add(p.qubit_state(float(ms)))

        self.assertEqual(states_seen, {0, 1}, "Qubit should visit both |0⟩ and |1⟩")

    def test_quantum_superposition_is_periodic(self):
        """양자 중첩: superposition_alpha()는 주기적이다."""
        from quantum.tunneling_physics import SUPERPOSITION_HZ, QuantumParticle

        p = QuantumParticle()
        period_ms = 1000.0 / SUPERPOSITION_HZ

        for t_ms in range(0, 5000, 17):
            a1 = p.superposition_alpha(float(t_ms))
            a2 = p.superposition_alpha(float(t_ms) + period_ms)
            self.assertAlmostEqual(a1, a2, places=6, msg=f"Should be periodic with T={period_ms:.1f}ms")

    def test_quantum_equal_time_in_both_states(self):
        """양자 중첩: 충분히 오래 관측하면 |0⟩과 |1⟩ 시간 비율 ≈ 50:50."""
        from quantum.tunneling_physics import QuantumParticle

        p = QuantumParticle()
        count_0, count_1 = 0, 0
        n_samples = 10000
        for i in range(n_samples):
            t_ms = float(i) * 0.1  # 0.1ms 간격
            s = p.qubit_state(t_ms)
            if s == 0:
                count_0 += 1
            else:
                count_1 += 1

        ratio_0 = count_0 / n_samples
        # 정현파 기반이므로 정확히 50:50
        self.assertAlmostEqual(ratio_0, 0.5, delta=0.05, msg=f"|0⟩ ratio {ratio_0:.3f} should be ~0.5")


class TestBlochSphereClassicalVsQuantum(unittest.TestCase):
    """고전: 북극(0) 또는 남극(1) 고정.
    양자: 블로흐 구 표면 위를 연속적으로 이동."""

    def test_classical_only_poles(self):
        """고전 비트는 블로흐 구의 북극(θ=0) 또는 남극(θ=π)만 가능."""
        classical_angles = {0.0, math.pi}
        for angle in classical_angles:
            self.assertIn(angle, {0.0, math.pi})

    def test_quantum_traverses_full_range(self):
        """양자 큐비트의 θ는 0~π 전체를 연속 순회."""
        from quantum.tunneling_physics import QuantumParticle

        p = QuantumParticle()
        min_alpha, max_alpha = math.pi, 0.0
        for ms in range(0, 2000, 1):
            alpha = p.superposition_alpha(float(ms))
            min_alpha = min(min_alpha, alpha)
            max_alpha = max(max_alpha, alpha)

        self.assertLess(min_alpha, 0.1, "Should approach |0⟩ (θ≈0)")
        self.assertGreater(max_alpha, math.pi - 0.1, "Should approach |1⟩ (θ≈π)")

    def test_quantum_intermediate_states_exist(self):
        """양자: θ=π/2 부근(적도) 같은 중간 상태가 존재."""
        from quantum.tunneling_physics import QuantumParticle

        p = QuantumParticle()
        found_equator = False
        for ms in range(0, 2000, 1):
            alpha = p.superposition_alpha(float(ms))
            if abs(alpha - math.pi / 2) < 0.1:
                found_equator = True
                break

        self.assertTrue(found_equator, "Quantum state should pass through equator (θ≈π/2)")


# ═══════════════════════════════════════════════════════
# 3. CHSH 부등식: 고전 한계 vs 양자 위반
# ═══════════════════════════════════════════════════════


class TestCHSHClassicalVsQuantum(unittest.TestCase):
    """CHSH 부등식: 고전 한계 |S| ≤ 2 vs 양자 |S| ≤ 2√2."""

    def test_classical_bound_is_two(self):
        """고전 물리의 CHSH 한계는 정확히 2.0."""
        from quantum.entanglement_physics import CHSH_CLASSICAL_BOUND

        self.assertEqual(CHSH_CLASSICAL_BOUND, 2.0)

    def test_quantum_bound_is_tsirelson(self):
        """양자 물리의 Tsirelson 한계는 2√2."""
        from quantum.entanglement_physics import CHSH_QUANTUM_BOUND

        self.assertAlmostEqual(CHSH_QUANTUM_BOUND, 2 * math.sqrt(2), places=10)

    def test_quantum_bound_exceeds_classical(self):
        """양자 한계 > 고전 한계 (핵심 비교)."""
        from quantum.entanglement_physics import CHSH_CLASSICAL_BOUND, CHSH_QUANTUM_BOUND

        self.assertGreater(CHSH_QUANTUM_BOUND, CHSH_CLASSICAL_BOUND)

    def test_bell_state_violates_classical_bound(self):
        """|Φ+⟩ 벨 상태로 CHSH 실험 → |S| > 2 (고전 한계 위반)."""
        from quantum.entanglement_physics import (
            BELL_STATES,
            CHSH_CLASSICAL_BOUND,
            run_chsh_experiment,
        )

        # 여러 번 시도하여 다수가 위반해야 함
        violations = 0
        n_trials = 10
        for _ in range(n_trials):
            result = run_chsh_experiment(BELL_STATES["Φ+"], n_shots=500)
            if abs(result["S"]) > CHSH_CLASSICAL_BOUND:
                violations += 1

        self.assertGreater(
            violations, n_trials * 0.6, f"Bell state should mostly violate classical bound ({violations}/{n_trials})"
        )

    def test_product_state_respects_classical_bound(self):
        """비얽힘(곱 상태) |00⟩ → CHSH 실험에서 고전 한계 내."""
        from quantum.entanglement_physics import CHSH_CLASSICAL_BOUND, run_chsh_experiment

        product_state = [complex(1), complex(0), complex(0), complex(0)]  # |00⟩

        within_bound = 0
        n_trials = 10
        for _ in range(n_trials):
            result = run_chsh_experiment(product_state, n_shots=300)
            if abs(result["S"]) <= CHSH_CLASSICAL_BOUND + 0.3:  # 통계적 여유
                within_bound += 1

        self.assertGreater(
            within_bound,
            n_trials * 0.6,
            f"Product state should mostly respect classical bound ({within_bound}/{n_trials})",
        )

    def test_chsh_s_value_near_tsirelson_for_bell(self):
        """벨 상태의 |S| 값이 2√2에 근접해야 함 (최적 기저 사용 시)."""
        from quantum.entanglement_physics import BELL_STATES, run_chsh_experiment

        s_values = []
        for _ in range(5):
            result = run_chsh_experiment(BELL_STATES["Φ+"], n_shots=2000)
            s_values.append(abs(result["S"]))

        avg_s = sum(s_values) / len(s_values)
        # 2√2 ≈ 2.828, 통계적으로 2.4 이상이어야 함
        self.assertGreater(avg_s, 2.3, f"Average |S|={avg_s:.3f} should approach 2√2")


# ═══════════════════════════════════════════════════════
# 4. 벨 상태 상관: 고전 독립 vs 양자 비국소 상관
# ═══════════════════════════════════════════════════════


class TestBellCorrelationClassicalVsQuantum(unittest.TestCase):
    """고전: 두 입자는 독립적으로 측정됨.
    양자: 얽힌 입자는 비국소적으로 상관됨."""

    def test_classical_independent_no_correlation(self):
        """고전 시나리오: 독립적인 두 비트 → 상관 없음."""
        random.seed(42)
        n = 2000
        correlated = 0
        for _ in range(n):
            a = random.choice([0, 1])
            b = random.choice([0, 1])
            if a == b:
                correlated += 1

        ratio = correlated / n
        self.assertAlmostEqual(
            ratio, 0.5, delta=0.05, msg=f"Classical independent: correlation={ratio:.3f} should be ~0.5"
        )

    def test_quantum_phi_plus_perfect_correlation(self):
        """|Φ+⟩: 같은 기저로 측정 시 Alice=Bob 항상 (100% 상관)."""
        from quantum.entanglement_physics import BELL_STATES, measure_bell

        state = BELL_STATES["Φ+"]
        n = 500
        match_count = 0
        for _ in range(n):
            a, b = measure_bell(state)
            if a == b:
                match_count += 1

        self.assertEqual(match_count, n, "|Φ+⟩: perfect correlation expected")

    def test_quantum_psi_minus_perfect_anticorrelation(self):
        """|Ψ-⟩: 같은 기저로 측정 시 Alice≠Bob 항상 (100% 반상관)."""
        from quantum.entanglement_physics import BELL_STATES, measure_bell

        state = BELL_STATES["Ψ-"]
        n = 500
        antimatch_count = 0
        for _ in range(n):
            a, b = measure_bell(state)
            if a != b:
                antimatch_count += 1

        self.assertEqual(antimatch_count, n, "|Ψ-⟩: perfect anti-correlation expected")

    def test_quantum_vs_classical_correlation_strength(self):
        """양자 상관(100%) > 고전 상관(~50%) 비교."""
        from quantum.entanglement_physics import BELL_STATES, measure_bell

        # 양자: |Φ+⟩ 상관
        state = BELL_STATES["Φ+"]
        quantum_match = 0
        n = 500
        for _ in range(n):
            a, b = measure_bell(state)
            if a == b:
                quantum_match += 1
        quantum_ratio = quantum_match / n

        # 고전: 독립 비트
        random.seed(123)
        classical_match = 0
        for _ in range(n):
            a = random.choice([0, 1])
            b = random.choice([0, 1])
            if a == b:
                classical_match += 1
        classical_ratio = classical_match / n

        self.assertGreater(
            quantum_ratio, classical_ratio, f"Quantum({quantum_ratio:.3f}) > Classical({classical_ratio:.3f})"
        )
        self.assertAlmostEqual(quantum_ratio, 1.0, places=5, msg="Quantum: perfect correlation")
        self.assertAlmostEqual(classical_ratio, 0.5, delta=0.06, msg="Classical: ~50%")


class TestBellMeasurementStatistics(unittest.TestCase):
    """벨 상태 측정 통계가 양자역학 예측과 일치하는지 검증."""

    def test_phi_plus_outcome_distribution(self):
        """|Φ+⟩ = (|00⟩+|11⟩)/√2 → P(00)=P(11)=0.5, P(01)=P(10)=0."""
        from quantum.entanglement_physics import BELL_STATES, measure_bell

        counts = {(0, 0): 0, (0, 1): 0, (1, 0): 0, (1, 1): 0}
        n = 2000
        for _ in range(n):
            a, b = measure_bell(BELL_STATES["Φ+"])
            counts[(a, b)] += 1

        # 00과 11만 나와야 함
        self.assertEqual(counts[(0, 1)], 0, "|Φ+⟩: |01⟩ should never occur")
        self.assertEqual(counts[(1, 0)], 0, "|Φ+⟩: |10⟩ should never occur")
        ratio_00 = counts[(0, 0)] / n
        self.assertAlmostEqual(ratio_00, 0.5, delta=0.05)

    def test_psi_plus_outcome_distribution(self):
        """|Ψ+⟩ = (|01⟩+|10⟩)/√2 → P(01)=P(10)=0.5, P(00)=P(11)=0."""
        from quantum.entanglement_physics import BELL_STATES, measure_bell

        counts = {(0, 0): 0, (0, 1): 0, (1, 0): 0, (1, 1): 0}
        n = 2000
        for _ in range(n):
            a, b = measure_bell(BELL_STATES["Ψ+"])
            counts[(a, b)] += 1

        self.assertEqual(counts[(0, 0)], 0)
        self.assertEqual(counts[(1, 1)], 0)
        ratio_01 = counts[(0, 1)] / n
        self.assertAlmostEqual(ratio_01, 0.5, delta=0.05)


# ═══════════════════════════════════════════════════════
# 5. 텔레포테이션: 고전 불가 vs 양자 가능
# ═══════════════════════════════════════════════════════


class TestTeleportationClassicalVsQuantum(unittest.TestCase):
    """고전: 미지의 상태를 완벽 복제 불가 (no-cloning 정리).
    양자: 얽힘 + 고전 통신으로 상태를 완벽 전송."""

    def test_classical_random_guess_low_fidelity(self):
        """고전 전략: 미지 상태를 랜덤 추측 → fidelity ≈ 0.5."""
        from quantum.entanglement_physics import create_random_state

        fidelities = []
        for _ in range(200):
            alpha, beta = create_random_state()
            # 고전: Bob이 랜덤 상태로 추측
            guess_alpha, guess_beta = create_random_state()
            # Fidelity: |⟨ψ|guess⟩|²
            overlap = alpha.conjugate() * guess_alpha + beta.conjugate() * guess_beta
            fidelity = abs(overlap) ** 2
            fidelities.append(fidelity)

        avg_fidelity = sum(fidelities) / len(fidelities)
        self.assertLess(avg_fidelity, 0.7, f"Classical random guess: avg fidelity={avg_fidelity:.3f} should be low")

    def test_quantum_teleportation_perfect_fidelity(self):
        """양자 텔레포테이션: fidelity ≈ 1.0 (완벽 전송)."""
        from quantum.entanglement_physics import (
            TeleportationState,
            create_random_state,
            teleport_step,
        )

        fidelities = []
        for _ in range(30):
            alpha, beta = create_random_state()
            ts = TeleportationState()
            ts.reset(alpha, beta)
            for _ in range(6):
                teleport_step(ts)
            fidelities.append(ts.fidelity)

        avg_fidelity = sum(fidelities) / len(fidelities)
        self.assertAlmostEqual(
            avg_fidelity, 1.0, places=4, msg=f"Quantum teleportation: avg fidelity={avg_fidelity:.6f}"
        )

    def test_quantum_beats_classical(self):
        """양자 텔레포테이션 fidelity > 고전 랜덤 추측 fidelity."""
        from quantum.entanglement_physics import (
            TeleportationState,
            create_random_state,
            teleport_step,
        )

        random.seed(777)
        states = [create_random_state() for _ in range(50)]

        # 양자 전송
        q_fidelities = []
        for alpha, beta in states:
            ts = TeleportationState()
            ts.reset(alpha, beta)
            for _ in range(6):
                teleport_step(ts)
            q_fidelities.append(ts.fidelity)

        # 고전 추측
        c_fidelities = []
        for alpha, beta in states:
            g_alpha, g_beta = create_random_state()
            overlap = alpha.conjugate() * g_alpha + beta.conjugate() * g_beta
            c_fidelities.append(abs(overlap) ** 2)

        avg_q = sum(q_fidelities) / len(q_fidelities)
        avg_c = sum(c_fidelities) / len(c_fidelities)

        self.assertGreater(avg_q, avg_c, f"Quantum({avg_q:.4f}) should beat Classical({avg_c:.4f})")
        self.assertGreater(avg_q, 0.99, "Quantum should achieve near-perfect fidelity")


# ═══════════════════════════════════════════════════════
# 6. 통합 시나리오: 전체 양자 우위 검증
# ═══════════════════════════════════════════════════════


class TestQuantumAdvantageScenarios(unittest.TestCase):
    """양자 역학이 고전 역학보다 우위인 시나리오 통합 검증."""

    def test_tunneling_nonzero_for_all_barrier_widths(self):
        """양자: 어떤 두께의 장벽이든 투과 확률 > 0 (고전: 항상 0)."""
        from quantum.tunneling_physics import (
            BARRIER_WIDTH_MAX,
            BARRIER_WIDTH_MIN,
            _calc_tunnel_prob,
        )

        for w in range(BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX + 1, 5):
            prob = _calc_tunnel_prob(w)
            self.assertGreater(prob, 0, f"Width={w}: quantum prob should be >0 (classical is 0)")

    def test_superposition_has_more_info_than_classical(self):
        """양자 중첩: 연속적 θ 값 vs 고전: 이산 {0, 1} 만 가능."""
        from quantum.tunneling_physics import QuantumParticle

        p = QuantumParticle()
        # 고전: 오직 2가지 상태
        classical_states = {0.0, math.pi}

        # 양자: 수많은 고유 α 값
        quantum_alphas = set()
        for ms in range(0, 1000, 1):
            alpha = round(p.superposition_alpha(float(ms)), 4)
            quantum_alphas.add(alpha)

        self.assertEqual(len(classical_states), 2)
        self.assertGreater(len(quantum_alphas), 50, "Quantum: many distinct intermediate states")

    def test_entanglement_correlation_impossible_classically(self):
        """벨 상태의 완벽한 상관은 고전 독립 입자로 재현 불가."""
        from quantum.entanglement_physics import BELL_STATES, measure_bell

        # |Φ+⟩: 100% 상관 검증
        n = 1000
        all_correlated = True
        for _ in range(n):
            a, b = measure_bell(BELL_STATES["Φ+"])
            if a != b:
                all_correlated = False
                break

        self.assertTrue(all_correlated, "Quantum entanglement: perfect correlation over 1000 trials")

        # 고전적으로 독립 비트 1000개로 100% 상관은 확률 ~2^{-1000} ≈ 0
        # (테스트 자체가 양자 우위의 증거)


if __name__ == "__main__":
    unittest.main()
