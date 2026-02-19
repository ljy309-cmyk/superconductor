"""양자 게이트 빌더 엔진 — 1~2큐비트 양자 회로 시뮬레이터.

numpy 없이 순수 Python으로 복소수 행렬 연산을 수행합니다.
  - 단일 큐비트 게이트: H, X, Y, Z, S, T
  - 2큐비트 게이트: CNOT
  - 상태 벡터 진화 및 측정 확률
  - 블로흐 구 좌표 계산

사용법:
    from quantum.gate_builder_engine import QuantumCircuit
    qc = QuantumCircuit(num_qubits=2)
    qc.add_gate("H", 0)
    qc.add_gate("CNOT", 0, 1)
    qc.run()
    probs = qc.probabilities()
"""

import cmath
import math
import random

# ── 기본 게이트 행렬 (2×2 복소수) ──────────────────────
# 행렬은 [[a, b], [c, d]] 형태의 리스트

SQRT2_INV = 1.0 / math.sqrt(2)

GATE_MATRICES: dict[str, list[list[complex]]] = {
    "I": [[1, 0], [0, 1]],
    "H": [[SQRT2_INV, SQRT2_INV], [SQRT2_INV, -SQRT2_INV]],
    "X": [[0, 1], [1, 0]],
    "Y": [[0, -1j], [1j, 0]],
    "Z": [[1, 0], [0, -1]],
    "S": [[1, 0], [0, 1j]],
    "T": [[1, 0], [0, cmath.exp(1j * math.pi / 4)]],
}

# 게이트 설명 (교육용)
GATE_INFO: dict[str, str] = {
    "I": "Identity — 변화 없음",
    "H": "Hadamard — 중첩 생성 (|0⟩→|+⟩, |1⟩→|−⟩)",
    "X": "Pauli-X (NOT) — 비트 플립 (|0⟩↔|1⟩)",
    "Y": "Pauli-Y — Y축 회전",
    "Z": "Pauli-Z — 위상 플립 (|1⟩→-|1⟩)",
    "S": "S (Phase) — π/2 위상 회전",
    "T": "T (π/8) — π/4 위상 회전",
    "CNOT": "CNOT — 조건부 NOT (제어+타겟)",
}

# 단일 큐비트 게이트 목록
SINGLE_GATES = ["H", "X", "Y", "Z", "S", "T"]
ALL_GATES = SINGLE_GATES + ["CNOT"]

MAX_QUBITS = 3
MAX_GATES = 12


def _mat_mul_2x2(a: list[list[complex]], b: list[list[complex]]) -> list[list[complex]]:
    """2×2 행렬 곱셈."""
    return [
        [a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1]],
        [a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1]],
    ]


def _tensor_product(a: list[list[complex]], b: list[list[complex]]) -> list[list[complex]]:
    """크로네커 텐서곱 (일반 크기)."""
    ra, ca = len(a), len(a[0])
    rb, cb = len(b), len(b[0])
    result = [[complex(0)] * (ca * cb) for _ in range(ra * rb)]
    for i in range(ra):
        for j in range(ca):
            for k in range(rb):
                for l in range(cb):  # noqa: E741
                    result[i * rb + k][j * cb + l] = a[i][j] * b[k][l]
    return result


def _identity(n: int) -> list[list[complex]]:
    """n×n 단위 행렬."""
    return [[complex(1 if i == j else 0) for j in range(n)] for i in range(n)]


def _mat_vec_mul(mat: list[list[complex]], vec: list[complex]) -> list[complex]:
    """행렬 × 벡터."""
    n = len(vec)
    return [sum(mat[i][j] * vec[j] for j in range(n)) for i in range(n)]


def _cnot_matrix(num_qubits: int, control: int, target: int) -> list[list[complex]]:
    """CNOT 게이트의 전체 행렬 (num_qubits 큐비트 공간)."""
    dim = 2**num_qubits
    result = [[complex(0)] * dim for _ in range(dim)]
    for i in range(dim):
        bits = [(i >> (num_qubits - 1 - q)) & 1 for q in range(num_qubits)]
        out_bits = bits[:]
        if bits[control] == 1:
            out_bits[target] = 1 - out_bits[target]
        j = sum(out_bits[q] << (num_qubits - 1 - q) for q in range(num_qubits))
        result[j][i] = complex(1)
    return result


def bloch_coords(alpha: complex, beta: complex) -> tuple[float, float, float]:
    """단일 큐비트 상태 |ψ⟩ = α|0⟩ + β|1⟩의 블로흐 구 좌표.

    Returns:
        (x, y, z) where x² + y² + z² ≈ 1
    """
    # 전역 위상 제거: α를 실수로 만들기
    if abs(alpha) > 1e-10:
        phase = cmath.phase(alpha)
        alpha = alpha * cmath.exp(-1j * phase)
        beta = beta * cmath.exp(-1j * phase)

    theta = 2 * math.acos(min(1.0, max(0.0, abs(alpha))))
    phi = cmath.phase(beta) if abs(beta) > 1e-10 else 0.0

    x = math.sin(theta) * math.cos(phi)
    y = math.sin(theta) * math.sin(phi)
    z = math.cos(theta)
    return (x, y, z)


class GateOp:
    """회로에 배치된 게이트 연산."""

    __slots__ = ("name", "qubit", "target")

    def __init__(self, name: str, qubit: int, target: int | None = None):
        self.name = name
        self.qubit = qubit  # 단일 게이트: 대상 큐비트, CNOT: 제어 큐비트
        self.target = target  # CNOT의 타겟 큐비트


class QuantumCircuit:
    """양자 회로 — 게이트 배치 + 시뮬레이션."""

    def __init__(self, num_qubits: int = 2):
        self.num_qubits = min(num_qubits, MAX_QUBITS)
        self.dim = 2**self.num_qubits
        self.gates: list[GateOp] = []
        self.state: list[complex] = self._init_state()
        self._executed = False
        self.max_gates: int = MAX_GATES

    def _init_state(self) -> list[complex]:
        """|00...0⟩ 초기 상태."""
        state = [complex(0)] * self.dim
        state[0] = complex(1)
        return state

    def add_gate(self, name: str, qubit: int, target: int | None = None) -> bool:
        """게이트 추가. 성공 시 True."""
        if len(self.gates) >= self.max_gates:
            return False
        if name == "CNOT":
            if target is None or qubit == target:
                return False
            if qubit >= self.num_qubits or target >= self.num_qubits:
                return False
        else:
            if name not in GATE_MATRICES:
                return False
            if qubit >= self.num_qubits:
                return False
        self.gates.append(GateOp(name, qubit, target))
        self._executed = False
        return True

    def remove_last_gate(self) -> bool:
        """마지막 게이트 제거."""
        if self.gates:
            self.gates.pop()
            self._executed = False
            return True
        return False

    def clear(self):
        """회로 초기화."""
        self.gates.clear()
        self.state = self._init_state()
        self._executed = False

    def run(self):
        """회로 실행 — 모든 게이트를 순서대로 적용."""
        self.state = self._init_state()
        for gate in self.gates:
            self._apply_gate(gate)
        self._executed = True

    def _apply_gate(self, gate: GateOp):
        """단일 게이트 적용."""
        if gate.name == "CNOT":
            mat = _cnot_matrix(self.num_qubits, gate.qubit, gate.target)
        else:
            gate_mat = GATE_MATRICES[gate.name]
            # 텐서곱으로 전체 행렬 구성
            mat = self._expand_single_gate(gate_mat, gate.qubit)
        self.state = _mat_vec_mul(mat, self.state)

    def _expand_single_gate(self, gate_mat: list[list[complex]], qubit: int) -> list[list[complex]]:
        """단일 큐비트 게이트를 전체 큐비트 공간으로 확장."""
        matrices = []
        for q in range(self.num_qubits):
            if q == qubit:
                matrices.append(gate_mat)
            else:
                matrices.append(GATE_MATRICES["I"])

        result = matrices[0]
        for m in matrices[1:]:
            result = _tensor_product(result, m)
        return result

    def probabilities(self) -> list[float]:
        """각 기저 상태의 측정 확률."""
        if not self._executed:
            self.run()
        return [abs(a) ** 2 for a in self.state]

    def measure(self) -> int:
        """측정 시뮬레이션 — 확률에 따라 붕괴."""
        probs = self.probabilities()
        r = random.random()
        cumulative = 0.0
        for i, p in enumerate(probs):
            cumulative += p
            if r <= cumulative:
                return i
        return len(probs) - 1

    def basis_labels(self) -> list[str]:
        """기저 상태 라벨 (|00⟩, |01⟩, ...)."""
        return [f"|{i:0{self.num_qubits}b}⟩" for i in range(self.dim)]

    def qubit_bloch(self, qubit: int) -> tuple[float, float, float]:
        """특정 큐비트의 블로흐 구 좌표 (부분 추적으로 축소).

        단순화: 1큐비트 회로이거나, 분리 가능 상태 근사.
        """
        if not self._executed:
            self.run()

        if self.num_qubits == 1:
            return bloch_coords(self.state[0], self.state[1])

        # 부분 추적: 해당 큐비트의 축소 밀도 행렬 계산
        rho00 = complex(0)
        rho01 = complex(0)
        rho10 = complex(0)
        rho11 = complex(0)

        for i in range(self.dim):
            for j in range(self.dim):
                bits_i = (i >> (self.num_qubits - 1 - qubit)) & 1
                bits_j = (j >> (self.num_qubits - 1 - qubit)) & 1
                # 다른 큐비트가 같은지 확인
                mask = ~(1 << (self.num_qubits - 1 - qubit))
                if (i & mask) == (j & mask):
                    val = self.state[i] * self.state[j].conjugate()
                    if bits_i == 0 and bits_j == 0:
                        rho00 += val
                    elif bits_i == 0 and bits_j == 1:
                        rho01 += val
                    elif bits_i == 1 and bits_j == 0:
                        rho10 += val
                    elif bits_i == 1 and bits_j == 1:
                        rho11 += val

        # 블로흐 벡터: r = (Tr(ρσx), Tr(ρσy), Tr(ρσz))
        x = 2 * rho01.real
        y = 2 * rho10.imag
        z = (rho00 - rho11).real
        return (x, y, z)
