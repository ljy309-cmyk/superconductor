"""양자 얽힘 물리 엔진 단위 테스트.

벨 상태, CHSH 부등식, 양자 텔레포테이션 로직을 검증합니다.
"""

import math
import os
import sys
import unittest
from unittest.mock import MagicMock

# GUI 의존성 mock
for mod in ("pygame", "tkinter", "tkinter.messagebox", "tkinter.ttk",
            "matplotlib", "matplotlib.backends", "matplotlib.backends.backend_tkagg",
            "matplotlib.figure"):
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBellStates(unittest.TestCase):
    """벨 상태 4종 검증."""

    def test_four_bell_states_exist(self):
        from quantum.entanglement_physics import BELL_STATES, BELL_LABELS
        self.assertEqual(len(BELL_STATES), 4)
        self.assertEqual(len(BELL_LABELS), 4)
        for name in BELL_LABELS:
            self.assertIn(name, BELL_STATES)

    def test_bell_states_normalized(self):
        """모든 벨 상태는 정규화되어야 한다 (|ψ|² = 1)."""
        from quantum.entanglement_physics import BELL_STATES
        for name, state in BELL_STATES.items():
            norm_sq = sum(abs(a) ** 2 for a in state)
            self.assertAlmostEqual(norm_sq, 1.0, places=10,
                                   msg=f"|{name}⟩ not normalized: {norm_sq}")

    def test_phi_plus_probabilities(self):
        """|Φ+⟩ = (|00⟩+|11⟩)/√2 → P(00)=P(11)=0.5."""
        from quantum.entanglement_physics import BELL_STATES, bell_probabilities
        probs = bell_probabilities(BELL_STATES["Φ+"])
        self.assertAlmostEqual(probs[0], 0.5, places=10)  # |00⟩
        self.assertAlmostEqual(probs[1], 0.0, places=10)  # |01⟩
        self.assertAlmostEqual(probs[2], 0.0, places=10)  # |10⟩
        self.assertAlmostEqual(probs[3], 0.5, places=10)  # |11⟩

    def test_phi_minus_probabilities(self):
        """|Φ-⟩ = (|00⟩-|11⟩)/√2 → P(00)=P(11)=0.5."""
        from quantum.entanglement_physics import BELL_STATES, bell_probabilities
        probs = bell_probabilities(BELL_STATES["Φ-"])
        self.assertAlmostEqual(probs[0], 0.5, places=10)
        self.assertAlmostEqual(probs[3], 0.5, places=10)

    def test_psi_plus_probabilities(self):
        """|Ψ+⟩ = (|01⟩+|10⟩)/√2 → P(01)=P(10)=0.5."""
        from quantum.entanglement_physics import BELL_STATES, bell_probabilities
        probs = bell_probabilities(BELL_STATES["Ψ+"])
        self.assertAlmostEqual(probs[0], 0.0, places=10)
        self.assertAlmostEqual(probs[1], 0.5, places=10)
        self.assertAlmostEqual(probs[2], 0.5, places=10)
        self.assertAlmostEqual(probs[3], 0.0, places=10)

    def test_psi_minus_probabilities(self):
        """|Ψ-⟩ = (|01⟩-|10⟩)/√2 → P(01)=P(10)=0.5."""
        from quantum.entanglement_physics import BELL_STATES, bell_probabilities
        probs = bell_probabilities(BELL_STATES["Ψ-"])
        self.assertAlmostEqual(probs[1], 0.5, places=10)
        self.assertAlmostEqual(probs[2], 0.5, places=10)


class TestBellMeasurement(unittest.TestCase):
    """벨 상태 측정 통계 검증."""

    def test_phi_plus_correlation(self):
        """|Φ+⟩ 측정 시 Alice와 Bob은 항상 같은 결과."""
        from quantum.entanglement_physics import BELL_STATES, measure_bell
        state = BELL_STATES["Φ+"]
        for _ in range(100):
            a, b = measure_bell(state)
            self.assertEqual(a, b, "|Φ+⟩: Alice and Bob should agree")

    def test_psi_plus_anticorrelation(self):
        """|Ψ+⟩ 측정 시 Alice와 Bob은 항상 다른 결과."""
        from quantum.entanglement_physics import BELL_STATES, measure_bell
        state = BELL_STATES["Ψ+"]
        for _ in range(100):
            a, b = measure_bell(state)
            self.assertNotEqual(a, b, "|Ψ+⟩: Alice and Bob should disagree")

    def test_psi_minus_anticorrelation(self):
        """|Ψ-⟩ 측정 시 Alice와 Bob은 항상 다른 결과."""
        from quantum.entanglement_physics import BELL_STATES, measure_bell
        state = BELL_STATES["Ψ-"]
        for _ in range(100):
            a, b = measure_bell(state)
            self.assertNotEqual(a, b, "|Ψ-⟩: Alice and Bob should disagree")

    def test_measurement_returns_binary(self):
        """측정 결과는 0 또는 1."""
        from quantum.entanglement_physics import BELL_STATES, measure_bell
        for name, state in BELL_STATES.items():
            a, b = measure_bell(state)
            self.assertIn(a, (0, 1))
            self.assertIn(b, (0, 1))

    def test_phi_plus_statistics(self):
        """|Φ+⟩의 1000회 측정 → 00과 11이 약 50:50."""
        from quantum.entanglement_physics import BELL_STATES, measure_bell
        state = BELL_STATES["Φ+"]
        counts = {"00": 0, "11": 0}
        n = 1000
        for _ in range(n):
            a, b = measure_bell(state)
            counts[f"{a}{b}"] += 1
        # 통계적으로 400~600 범위에 있어야 함 (5σ)
        self.assertGreater(counts["00"], 350)
        self.assertGreater(counts["11"], 350)
        self.assertEqual(counts["00"] + counts["11"], n)


class TestCHSH(unittest.TestCase):
    """CHSH 부등식 실험 검증."""

    def test_chsh_bounds(self):
        from quantum.entanglement_physics import (
            CHSH_CLASSICAL_BOUND, CHSH_QUANTUM_BOUND,
        )
        self.assertAlmostEqual(CHSH_CLASSICAL_BOUND, 2.0)
        self.assertAlmostEqual(CHSH_QUANTUM_BOUND, 2 * math.sqrt(2),
                               places=10)

    def test_chsh_experiment_structure(self):
        """run_chsh_experiment 반환 구조 확인."""
        from quantum.entanglement_physics import (
            BELL_STATES, run_chsh_experiment,
        )
        result = run_chsh_experiment(BELL_STATES["Φ+"], n_shots=50)
        self.assertIn("E", result)
        self.assertIn("S", result)
        self.assertIn("violated", result)
        self.assertEqual(len(result["E"]), 2)
        self.assertEqual(len(result["E"][0]), 2)
        self.assertIsInstance(result["S"], float)
        self.assertIsInstance(result["violated"], bool)

    def test_chsh_violation_with_bell_state(self):
        """|Φ+⟩로 CHSH 실험 → 고전 한계(2.0) 위반 경향."""
        from quantum.entanglement_physics import (
            BELL_STATES, CHSH_CLASSICAL_BOUND, run_chsh_experiment,
        )
        # 여러 번 시도하여 적어도 대부분 위반해야 함
        violations = 0
        n_trials = 5
        for _ in range(n_trials):
            result = run_chsh_experiment(BELL_STATES["Φ+"], n_shots=500)
            if result["violated"]:
                violations += 1
        self.assertGreater(violations, n_trials // 2,
                           f"Only {violations}/{n_trials} violations")

    def test_chsh_correlator_range(self):
        """상관 함수 E(a,b)는 [-1, 1] 범위."""
        from quantum.entanglement_physics import (
            BELL_STATES, chsh_correlator,
        )
        e = chsh_correlator(BELL_STATES["Φ+"], 0.0, math.pi / 8, n_shots=100)
        self.assertGreaterEqual(e, -1.0)
        self.assertLessEqual(e, 1.0)


class TestTeleportation(unittest.TestCase):
    """양자 텔레포테이션 프로토콜 검증."""

    def test_teleportation_state_init(self):
        from quantum.entanglement_physics import TeleportationState
        ts = TeleportationState()
        self.assertEqual(ts.step, 0)
        self.assertEqual(len(ts.step_names), 6)
        self.assertEqual(len(ts.state_vector), 8)

    def test_teleportation_full_protocol(self):
        """전체 6단계 텔레포테이션 실행 → fidelity ≈ 1."""
        from quantum.entanglement_physics import (
            TeleportationState, create_random_state, teleport_step,
        )
        alpha, beta = create_random_state()
        ts = TeleportationState()
        ts.reset(alpha, beta)

        for _ in range(6):
            msg = teleport_step(ts)
            self.assertIsInstance(msg, str)

        self.assertEqual(ts.step, 6)
        self.assertAlmostEqual(ts.fidelity, 1.0, places=6,
                               msg="Teleportation fidelity should be ~1.0")

    def test_teleportation_known_state_0(self):
        """|0⟩ 텔레포테이션 → Bob도 |0⟩."""
        from quantum.entanglement_physics import TeleportationState, teleport_step
        ts = TeleportationState()
        ts.reset(complex(1, 0), complex(0, 0))

        for _ in range(6):
            teleport_step(ts)

        self.assertAlmostEqual(ts.fidelity, 1.0, places=6)
        self.assertAlmostEqual(abs(ts.bob_alpha), 1.0, places=6)
        self.assertAlmostEqual(abs(ts.bob_beta), 0.0, places=6)

    def test_teleportation_known_state_1(self):
        """|1⟩ 텔레포테이션 → Bob도 |1⟩."""
        from quantum.entanglement_physics import TeleportationState, teleport_step
        ts = TeleportationState()
        ts.reset(complex(0, 0), complex(1, 0))

        for _ in range(6):
            teleport_step(ts)

        self.assertAlmostEqual(ts.fidelity, 1.0, places=6)
        self.assertAlmostEqual(abs(ts.bob_alpha), 0.0, places=6)
        self.assertAlmostEqual(abs(ts.bob_beta), 1.0, places=6)

    def test_teleportation_plus_state(self):
        """|+⟩ = (|0⟩+|1⟩)/√2 텔레포테이션 → fidelity ≈ 1."""
        from quantum.entanglement_physics import TeleportationState, teleport_step
        s2 = 1.0 / math.sqrt(2)
        ts = TeleportationState()
        ts.reset(complex(s2, 0), complex(s2, 0))

        for _ in range(6):
            teleport_step(ts)

        self.assertAlmostEqual(ts.fidelity, 1.0, places=6)

    def test_teleportation_multiple_random_states(self):
        """여러 랜덤 상태 텔레포테이션 → 모두 fidelity ≈ 1."""
        from quantum.entanglement_physics import (
            TeleportationState, create_random_state, teleport_step,
        )
        for _ in range(20):
            alpha, beta = create_random_state()
            ts = TeleportationState()
            ts.reset(alpha, beta)
            for _ in range(6):
                teleport_step(ts)
            self.assertAlmostEqual(
                ts.fidelity, 1.0, places=5,
                msg=f"Fidelity {ts.fidelity} for α={alpha}, β={beta}")

    def test_teleportation_reset(self):
        """reset() 후 초기 상태 복원."""
        from quantum.entanglement_physics import TeleportationState
        ts = TeleportationState()
        ts.step = 4
        ts.fidelity = 0.99
        ts.reset(complex(1, 0), complex(0, 0))
        self.assertEqual(ts.step, 0)
        self.assertEqual(ts.fidelity, 0.0)

    def test_step_past_complete(self):
        """step 6 이후 호출 시 에러 없이 종료 메시지."""
        from quantum.entanglement_physics import TeleportationState, teleport_step
        ts = TeleportationState()
        ts.step = 6
        msg = teleport_step(ts)
        self.assertEqual(msg, "Protocol complete!")
        self.assertEqual(ts.step, 6)  # 변하지 않음


class TestBlochCoordinates(unittest.TestCase):
    """블로흐 구 좌표 변환 검증."""

    def test_state_0_is_north_pole(self):
        """|0⟩ → (0, 0, 1) 북극."""
        from quantum.entanglement_physics import bloch_xyz
        x, y, z = bloch_xyz(complex(1, 0), complex(0, 0))
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(y, 0.0, places=6)
        self.assertAlmostEqual(z, 1.0, places=6)

    def test_state_1_is_south_pole(self):
        """|1⟩ → (0, 0, -1) 남극."""
        from quantum.entanglement_physics import bloch_xyz
        x, y, z = bloch_xyz(complex(0, 0), complex(1, 0))
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(z, -1.0, places=6)

    def test_plus_state_is_x_axis(self):
        """|+⟩ = (|0⟩+|1⟩)/√2 → (+1, 0, 0)."""
        from quantum.entanglement_physics import bloch_xyz
        s2 = 1.0 / math.sqrt(2)
        x, y, z = bloch_xyz(complex(s2, 0), complex(s2, 0))
        self.assertAlmostEqual(x, 1.0, places=5)
        self.assertAlmostEqual(z, 0.0, places=5)

    def test_bloch_on_unit_sphere(self):
        """랜덤 상태의 블로흐 좌표는 단위구 위."""
        from quantum.entanglement_physics import bloch_xyz, create_random_state
        for _ in range(20):
            alpha, beta = create_random_state()
            x, y, z = bloch_xyz(alpha, beta)
            r = math.sqrt(x**2 + y**2 + z**2)
            self.assertAlmostEqual(r, 1.0, places=5)


class TestRandomState(unittest.TestCase):
    """랜덤 상태 생성 검증."""

    def test_normalized(self):
        """생성된 상태는 정규화."""
        from quantum.entanglement_physics import create_random_state
        for _ in range(50):
            alpha, beta = create_random_state()
            norm = abs(alpha) ** 2 + abs(beta) ** 2
            self.assertAlmostEqual(norm, 1.0, places=10)


if __name__ == "__main__":
    unittest.main()
