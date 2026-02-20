"""양자 게이트 빌더 엔진 단위 테스트."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum.gate_builder_engine import (
    MAX_GATES,
    QuantumCircuit,
    bloch_coords,
)

SQRT2_INV = 1.0 / math.sqrt(2)


class TestBlochCoords(unittest.TestCase):
    """bloch_coords — 블로흐 구 좌표."""

    def test_state_0(self):
        """| 0⟩ → 북극 (0, 0, 1)."""
        x, y, z = bloch_coords(1, 0)
        self.assertAlmostEqual(x, 0, places=5)
        self.assertAlmostEqual(y, 0, places=5)
        self.assertAlmostEqual(z, 1, places=5)

    def test_state_1(self):
        """| 1⟩ → 남극 (0, 0, -1)."""
        x, y, z = bloch_coords(0, 1)
        self.assertAlmostEqual(x, 0, places=5)
        self.assertAlmostEqual(z, -1, places=5)

    def test_state_plus(self):
        """| +⟩ = (|0⟩+|1⟩)/√2 → +X축 (1, 0, 0)."""
        x, y, z = bloch_coords(SQRT2_INV, SQRT2_INV)
        self.assertAlmostEqual(x, 1, places=4)
        self.assertAlmostEqual(z, 0, places=4)

    def test_unit_sphere(self):
        """블로흐 벡터 길이 ≈ 1."""
        for alpha, beta in [(1, 0), (0, 1), (SQRT2_INV, SQRT2_INV), (SQRT2_INV, -SQRT2_INV)]:
            x, y, z = bloch_coords(alpha, beta)
            length = math.sqrt(x**2 + y**2 + z**2)
            self.assertAlmostEqual(length, 1.0, places=4, msg=f"α={alpha}, β={beta}")


class TestQuantumCircuitBasic(unittest.TestCase):
    """QuantumCircuit — 기본 동작."""

    def test_initial_state(self):
        """초기 상태 |00⟩."""
        qc = QuantumCircuit(2)
        self.assertAlmostEqual(qc.state[0], 1.0)
        for i in range(1, 4):
            self.assertAlmostEqual(abs(qc.state[i]), 0.0)

    def test_probabilities_sum_to_one(self):
        """확률 합 = 1."""
        qc = QuantumCircuit(2)
        qc.add_gate("H", 0)
        qc.run()
        self.assertAlmostEqual(sum(qc.probabilities()), 1.0)

    def test_basis_labels(self):
        """기저 라벨."""
        qc = QuantumCircuit(2)
        labels = qc.basis_labels()
        self.assertEqual(labels, ["|00⟩", "|01⟩", "|10⟩", "|11⟩"])

    def test_clear(self):
        """clear()로 초기화."""
        qc = QuantumCircuit(2)
        qc.add_gate("H", 0)
        qc.run()
        qc.clear()
        self.assertEqual(len(qc.gates), 0)
        self.assertAlmostEqual(qc.state[0], 1.0)


class TestSingleGates(unittest.TestCase):
    """단일 큐비트 게이트."""

    def test_x_gate_flips(self):
        """X 게이트: |0⟩ → |1⟩."""
        qc = QuantumCircuit(1)
        qc.add_gate("X", 0)
        qc.run()
        probs = qc.probabilities()
        self.assertAlmostEqual(probs[0], 0.0)
        self.assertAlmostEqual(probs[1], 1.0)

    def test_x_gate_double(self):
        """XX = I: |0⟩ → |0⟩."""
        qc = QuantumCircuit(1)
        qc.add_gate("X", 0)
        qc.add_gate("X", 0)
        qc.run()
        probs = qc.probabilities()
        self.assertAlmostEqual(probs[0], 1.0)

    def test_h_gate_superposition(self):
        """H 게이트: |0⟩ → |+⟩ = 50/50 확률."""
        qc = QuantumCircuit(1)
        qc.add_gate("H", 0)
        qc.run()
        probs = qc.probabilities()
        self.assertAlmostEqual(probs[0], 0.5, places=5)
        self.assertAlmostEqual(probs[1], 0.5, places=5)

    def test_hh_identity(self):
        """HH = I."""
        qc = QuantumCircuit(1)
        qc.add_gate("H", 0)
        qc.add_gate("H", 0)
        qc.run()
        probs = qc.probabilities()
        self.assertAlmostEqual(probs[0], 1.0, places=5)

    def test_z_gate_phase(self):
        """Z|0⟩ = |0⟩, Z|1⟩ = -|1⟩ (확률은 변하지 않음)."""
        qc = QuantumCircuit(1)
        qc.add_gate("Z", 0)
        qc.run()
        probs = qc.probabilities()
        self.assertAlmostEqual(probs[0], 1.0)

    def test_y_gate(self):
        """Y|0⟩ = i|1⟩ (확률: |1⟩ = 1)."""
        qc = QuantumCircuit(1)
        qc.add_gate("Y", 0)
        qc.run()
        probs = qc.probabilities()
        self.assertAlmostEqual(probs[0], 0.0)
        self.assertAlmostEqual(probs[1], 1.0)

    def test_s_gate(self):
        """S 게이트 확률 불변 (위상만 변경)."""
        qc = QuantumCircuit(1)
        qc.add_gate("H", 0)
        qc.add_gate("S", 0)
        qc.run()
        probs = qc.probabilities()
        self.assertAlmostEqual(probs[0], 0.5, places=5)
        self.assertAlmostEqual(probs[1], 0.5, places=5)

    def test_t_gate(self):
        """T 게이트 확률 불변 (위상만 변경)."""
        qc = QuantumCircuit(1)
        qc.add_gate("H", 0)
        qc.add_gate("T", 0)
        qc.run()
        probs = qc.probabilities()
        self.assertAlmostEqual(probs[0], 0.5, places=5)
        self.assertAlmostEqual(probs[1], 0.5, places=5)


class TestCNOT(unittest.TestCase):
    """CNOT 게이트."""

    def test_cnot_control_0(self):
        """제어 = |0⟩이면 타겟 변하지 않음."""
        qc = QuantumCircuit(2)
        qc.add_gate("CNOT", 0, 1)
        qc.run()
        probs = qc.probabilities()
        self.assertAlmostEqual(probs[0], 1.0)  # |00⟩

    def test_cnot_control_1(self):
        """제어 = |1⟩이면 타겟 플립: |10⟩ → |11⟩."""
        qc = QuantumCircuit(2)
        qc.add_gate("X", 0)  # |10⟩
        qc.add_gate("CNOT", 0, 1)
        qc.run()
        probs = qc.probabilities()
        self.assertAlmostEqual(probs[3], 1.0)  # |11⟩

    def test_bell_state(self):
        """벨 상태: H → CNOT = (|00⟩ + |11⟩)/√2."""
        qc = QuantumCircuit(2)
        qc.add_gate("H", 0)
        qc.add_gate("CNOT", 0, 1)
        qc.run()
        probs = qc.probabilities()
        self.assertAlmostEqual(probs[0], 0.5, places=5)  # |00⟩
        self.assertAlmostEqual(probs[1], 0.0, places=5)  # |01⟩
        self.assertAlmostEqual(probs[2], 0.0, places=5)  # |10⟩
        self.assertAlmostEqual(probs[3], 0.5, places=5)  # |11⟩


class TestCircuitOperations(unittest.TestCase):
    """회로 조작."""

    def test_add_gate_returns_true(self):
        qc = QuantumCircuit(2)
        self.assertTrue(qc.add_gate("H", 0))

    def test_add_invalid_gate(self):
        qc = QuantumCircuit(2)
        self.assertFalse(qc.add_gate("INVALID", 0))

    def test_add_gate_invalid_qubit(self):
        qc = QuantumCircuit(2)
        self.assertFalse(qc.add_gate("H", 5))

    def test_cnot_same_qubit_rejected(self):
        qc = QuantumCircuit(2)
        self.assertFalse(qc.add_gate("CNOT", 0, 0))

    def test_cnot_no_target_rejected(self):
        qc = QuantumCircuit(2)
        self.assertFalse(qc.add_gate("CNOT", 0))

    def test_max_gates_limit(self):
        qc = QuantumCircuit(1)
        for _ in range(MAX_GATES):
            qc.add_gate("H", 0)
        self.assertFalse(qc.add_gate("H", 0))

    def test_remove_last_gate(self):
        qc = QuantumCircuit(1)
        qc.add_gate("H", 0)
        qc.add_gate("X", 0)
        self.assertTrue(qc.remove_last_gate())
        self.assertEqual(len(qc.gates), 1)
        self.assertEqual(qc.gates[0].name, "H")

    def test_remove_empty(self):
        qc = QuantumCircuit(1)
        self.assertFalse(qc.remove_last_gate())

    def test_measure_returns_valid(self):
        qc = QuantumCircuit(2)
        qc.add_gate("H", 0)
        qc.run()
        result = qc.measure()
        self.assertIn(result, [0, 1, 2, 3])

    def test_measure_deterministic(self):
        """확정 상태에서 측정은 항상 같은 결과."""
        qc = QuantumCircuit(1)
        qc.add_gate("X", 0)
        qc.run()
        for _ in range(20):
            self.assertEqual(qc.measure(), 1)


class TestBlochSphere(unittest.TestCase):
    """회로에서 블로흐 구 좌표."""

    def test_initial_state_north_pole(self):
        """초기 |0⟩ → 북극."""
        qc = QuantumCircuit(1)
        qc.run()
        x, y, z = qc.qubit_bloch(0)
        self.assertAlmostEqual(z, 1.0, places=4)

    def test_x_gate_south_pole(self):
        """X|0⟩ = |1⟩ → 남극."""
        qc = QuantumCircuit(1)
        qc.add_gate("X", 0)
        qc.run()
        x, y, z = qc.qubit_bloch(0)
        self.assertAlmostEqual(z, -1.0, places=4)

    def test_h_gate_equator(self):
        """H|0⟩ = |+⟩ → 적도."""
        qc = QuantumCircuit(1)
        qc.add_gate("H", 0)
        qc.run()
        x, y, z = qc.qubit_bloch(0)
        self.assertAlmostEqual(z, 0.0, places=4)
        self.assertAlmostEqual(abs(x), 1.0, places=4)

    def test_2qubit_bloch(self):
        """2큐비트에서도 블로흐 좌표 계산 가능."""
        qc = QuantumCircuit(2)
        qc.add_gate("X", 1)
        qc.run()
        # q0: |0⟩ → 북극
        _, _, z0 = qc.qubit_bloch(0)
        self.assertAlmostEqual(z0, 1.0, places=4)
        # q1: |1⟩ → 남극
        _, _, z1 = qc.qubit_bloch(1)
        self.assertAlmostEqual(z1, -1.0, places=4)


class TestThreeQubits(unittest.TestCase):
    """3큐비트 회로."""

    def test_3qubit_init(self):
        qc = QuantumCircuit(3)
        self.assertEqual(qc.dim, 8)
        self.assertEqual(len(qc.state), 8)

    def test_3qubit_labels(self):
        qc = QuantumCircuit(3)
        labels = qc.basis_labels()
        self.assertEqual(len(labels), 8)
        self.assertEqual(labels[0], "|000⟩")
        self.assertEqual(labels[7], "|111⟩")

    def test_3qubit_x_gate(self):
        qc = QuantumCircuit(3)
        qc.add_gate("X", 2)  # |001⟩
        qc.run()
        probs = qc.probabilities()
        self.assertAlmostEqual(probs[1], 1.0)  # |001⟩


if __name__ == "__main__":
    unittest.main()
