"""양자 얽힘(Entanglement) 물리 엔진.

순수 Python으로 구현 (numpy 불필요):
  - 벨 상태(Bell State) 4종 생성 및 측정
  - CHSH 부등식 위반 실험 시뮬레이션
  - 양자 텔레포테이션 프로토콜 단계별 시뮬레이션

2-큐비트 상태 벡터: [|00⟩, |01⟩, |10⟩, |11⟩]
"""

import cmath
import math
import random
from dataclasses import dataclass, field
from typing import Tuple

SQRT2_INV = 1.0 / math.sqrt(2)

# ── 벨 상태 4종 ───────────────────────────────────────
# |Φ+⟩ = (|00⟩ + |11⟩) / √2
# |Φ-⟩ = (|00⟩ - |11⟩) / √2
# |Ψ+⟩ = (|01⟩ + |10⟩) / √2
# |Ψ-⟩ = (|01⟩ - |10⟩) / √2

BELL_STATES: dict[str, list[complex]] = {
    "Φ+": [SQRT2_INV, 0, 0, SQRT2_INV],
    "Φ-": [SQRT2_INV, 0, 0, -SQRT2_INV],
    "Ψ+": [0, SQRT2_INV, SQRT2_INV, 0],
    "Ψ-": [0, SQRT2_INV, -SQRT2_INV, 0],
}

BELL_LABELS = ["Φ+", "Φ-", "Ψ+", "Ψ-"]

BELL_DESCRIPTIONS: dict[str, str] = {
    "Φ+": "|Φ+⟩ = (|00⟩ + |11⟩)/√2",
    "Φ-": "|Φ-⟩ = (|00⟩ − |11⟩)/√2",
    "Ψ+": "|Ψ+⟩ = (|01⟩ + |10⟩)/√2",
    "Ψ-": "|Ψ-⟩ = (|01⟩ − |10⟩)/√2",
}


def bell_probabilities(state: list[complex]) -> list[float]:
    """상태 벡터에서 측정 확률 [P(00), P(01), P(10), P(11)]."""
    return [abs(a) ** 2 for a in state]


def measure_bell(state: list[complex]) -> Tuple[int, int]:
    """벨 상태 측정 → (qubit_A, qubit_B) 각각 0 또는 1.

    상태 벡터가 확률에 따라 붕괴됩니다.
    """
    probs = bell_probabilities(state)
    r = random.random()
    cumulative = 0.0
    outcome = 3
    for i, p in enumerate(probs):
        cumulative += p
        if r <= cumulative:
            outcome = i
            break
    a = (outcome >> 1) & 1
    b = outcome & 1
    return (a, b)


# ── 측정 기저 (CHSH용) ────────────────────────────────

def _rotation_matrix(angle: float) -> list[list[complex]]:
    """Z-Y 평면 회전 측정 기저 행렬."""
    c = math.cos(angle / 2)
    s = math.sin(angle / 2)
    return [[c, -s], [s, c]]


def _apply_2x2(mat: list[list[complex]], vec: list[complex]) -> list[complex]:
    """2×2 행렬 × 2-벡터."""
    return [
        mat[0][0] * vec[0] + mat[0][1] * vec[1],
        mat[1][0] * vec[0] + mat[1][1] * vec[1],
    ]


def measure_in_basis(state: list[complex], angle_a: float,
                     angle_b: float) -> Tuple[int, int]:
    """두 큐비트를 각각 다른 기저(각도)로 측정.

    Alice는 angle_a, Bob은 angle_b 회전 기저로 측정.
    Returns (result_A, result_B) 각각 +1 또는 -1.
    """
    # 회전 행렬 텐서곱 적용
    rot_a = _rotation_matrix(angle_a)
    rot_b = _rotation_matrix(angle_b)

    # 텐서곱: (Ra ⊗ Rb)|ψ⟩
    rotated = [complex(0)] * 4
    for i in range(2):
        for j in range(2):
            for k in range(2):
                for l in range(2):
                    src_idx = k * 2 + l
                    dst_idx = i * 2 + j
                    rotated[dst_idx] += (rot_a[i][k] * rot_b[j][l]
                                         * state[src_idx])

    probs = [abs(a) ** 2 for a in rotated]
    r = random.random()
    cumulative = 0.0
    outcome = 3
    for idx, p in enumerate(probs):
        cumulative += p
        if r <= cumulative:
            outcome = idx
            break

    a = 1 - 2 * ((outcome >> 1) & 1)  # 0→+1, 1→-1
    b = 1 - 2 * (outcome & 1)
    return (a, b)


# ── CHSH 부등식 ───────────────────────────────────────

# 고전 한계: |S| ≤ 2
# 양자 한계: |S| ≤ 2√2 ≈ 2.828 (Tsirelson bound)
CHSH_CLASSICAL_BOUND = 2.0
CHSH_QUANTUM_BOUND = 2.0 * math.sqrt(2)

# 최적 CHSH 측정 각도 (Alice: 0, π/4, Bob: π/8, 3π/8)
CHSH_ANGLES_ALICE = [0.0, math.pi / 4]
CHSH_ANGLES_BOB = [math.pi / 8, 3 * math.pi / 8]


def chsh_correlator(state: list[complex], angle_a: float,
                    angle_b: float, n_shots: int = 100) -> float:
    """상관 함수 E(a,b) = ⟨A⊗B⟩ 측정 (n_shots 번 반복)."""
    total = 0.0
    for _ in range(n_shots):
        a, b = measure_in_basis(state, angle_a, angle_b)
        total += a * b
    return total / n_shots


def run_chsh_experiment(state: list[complex],
                        n_shots: int = 200) -> dict:
    """CHSH 실험 전체 수행.

    Returns:
        {"E": [[E00, E01], [E10, E11]], "S": float, "violated": bool}
    """
    e_matrix = [[0.0, 0.0], [0.0, 0.0]]
    for i, aa in enumerate(CHSH_ANGLES_ALICE):
        for j, ab in enumerate(CHSH_ANGLES_BOB):
            e_matrix[i][j] = chsh_correlator(state, aa, ab, n_shots)

    # S = E(a1,b1) - E(a1,b2) + E(a2,b1) + E(a2,b2)
    s_value = (e_matrix[0][0] - e_matrix[0][1]
               + e_matrix[1][0] + e_matrix[1][1])

    return {
        "E": e_matrix,
        "S": s_value,
        "violated": abs(s_value) > CHSH_CLASSICAL_BOUND,
    }


# ── 양자 텔레포테이션 ─────────────────────────────────

@dataclass
class TeleportationState:
    """양자 텔레포테이션 프로토콜 상태."""

    # 전송할 상태: α|0⟩ + β|1⟩
    alpha: complex = complex(1, 0)
    beta: complex = complex(0, 0)

    step: int = 0  # 0~5 단계
    step_names: list[str] = field(default_factory=lambda: [
        "prepare",       # 0: 전송할 상태 준비
        "bell_pair",     # 1: Alice-Bob 벨 쌍 공유
        "entangle",      # 2: Alice의 큐비트와 전송할 큐비트 얽힘
        "measure",       # 3: Alice 측정 (벨 측정)
        "classical",     # 4: 고전 채널로 결과 전송
        "correct",       # 5: Bob 보정 → 상태 복원
    ])

    # 3-큐비트 상태벡터 [|000⟩ .. |111⟩]
    state_vector: list[complex] = field(default_factory=lambda: [complex(0)] * 8)

    # Alice의 측정 결과
    measurement_result: Tuple[int, int] = (0, 0)

    # Bob의 최종 상태
    bob_alpha: complex = complex(0, 0)
    bob_beta: complex = complex(0, 0)

    # 재현성을 위한 fidelity
    fidelity: float = 0.0

    def reset(self, alpha: complex = None, beta: complex = None):
        """새 상태로 리셋."""
        if alpha is not None and beta is not None:
            # 정규화
            norm = math.sqrt(abs(alpha) ** 2 + abs(beta) ** 2)
            if norm > 1e-10:
                self.alpha = alpha / norm
                self.beta = beta / norm
            else:
                self.alpha = complex(1, 0)
                self.beta = complex(0, 0)
        self.step = 0
        self.state_vector = [complex(0)] * 8
        self.measurement_result = (0, 0)
        self.bob_alpha = complex(0, 0)
        self.bob_beta = complex(0, 0)
        self.fidelity = 0.0


def teleport_step(ts: TeleportationState) -> str:
    """텔레포테이션 다음 단계 실행. 설명 문자열 반환."""
    if ts.step >= 6:
        return "Protocol complete!"

    step = ts.step
    a, b = ts.alpha, ts.beta

    if step == 0:
        # Step 0: 전송할 상태 준비
        # |ψ⟩_in = α|0⟩ + β|1⟩ (qubit 0)
        # 초기: qubit1, qubit2 = |00⟩
        # 3-qubit: (α|0⟩ + β|1⟩) ⊗ |0⟩ ⊗ |0⟩
        ts.state_vector = [complex(0)] * 8
        ts.state_vector[0] = a  # α|000⟩
        ts.state_vector[4] = b  # β|100⟩
        ts.step = 1
        return "Prepared input state: α|0⟩ + β|1⟩"

    elif step == 1:
        # Step 1: Alice-Bob 벨 쌍 생성 (qubit 1,2)
        # H on qubit1 → CNOT(1→2)
        # |00⟩ → (|00⟩+|11⟩)/√2
        # 3-qubit에서: 각 |x00⟩ → |x⟩(|00⟩+|11⟩)/√2
        new_sv = [complex(0)] * 8
        for i in range(8):
            if abs(ts.state_vector[i]) < 1e-15:
                continue
            q0 = (i >> 2) & 1
            q1 = (i >> 1) & 1
            q2 = i & 1
            if q1 == 0 and q2 == 0:
                # |x00⟩ → (|x00⟩ + |x11⟩)/√2
                new_sv[q0 * 4 + 0] += ts.state_vector[i] * SQRT2_INV
                new_sv[q0 * 4 + 3] += ts.state_vector[i] * SQRT2_INV
            else:
                new_sv[i] += ts.state_vector[i]
        ts.state_vector = new_sv
        ts.step = 2
        return "Bell pair shared: (|00⟩+|11⟩)/√2 between Alice & Bob"

    elif step == 2:
        # Step 2: CNOT(0→1) then H(0)
        # CNOT on qubit 0→1
        new_sv = [complex(0)] * 8
        for i in range(8):
            if abs(ts.state_vector[i]) < 1e-15:
                continue
            q0 = (i >> 2) & 1
            q1 = (i >> 1) & 1
            q2 = i & 1
            new_q1 = q1 ^ q0  # CNOT
            j = (q0 << 2) | (new_q1 << 1) | q2
            new_sv[j] += ts.state_vector[i]
        # H on qubit 0
        h_sv = [complex(0)] * 8
        for i in range(8):
            if abs(new_sv[i]) < 1e-15:
                continue
            q0 = (i >> 2) & 1
            q1 = (i >> 1) & 1
            q2 = i & 1
            # H: |0⟩ → (|0⟩+|1⟩)/√2, |1⟩ → (|0⟩-|1⟩)/√2
            for new_q0 in range(2):
                sign = 1 if q0 == 0 else (1 if new_q0 == 0 else -1)
                j = (new_q0 << 2) | (q1 << 1) | q2
                h_sv[j] += new_sv[i] * sign * SQRT2_INV
        ts.state_vector = h_sv
        ts.step = 3
        return "Alice entangles input qubit with her Bell qubit (CNOT + H)"

    elif step == 3:
        # Step 3: Alice 측정 (qubit 0, 1)
        probs = [0.0] * 4
        for i in range(8):
            q01 = (i >> 1)  # upper 2 bits
            probs[q01] += abs(ts.state_vector[i]) ** 2

        r = random.random()
        cumulative = 0.0
        result = 3
        for idx, p in enumerate(probs):
            cumulative += p
            if r <= cumulative:
                result = idx
                break

        m0 = (result >> 1) & 1
        m1 = result & 1
        ts.measurement_result = (m0, m1)

        # 붕괴: 측정 결과에 해당하는 성분만 남기고 정규화
        collapsed = [complex(0)] * 8
        norm_sq = 0.0
        for i in range(8):
            q01 = (i >> 1)
            if q01 == result:
                collapsed[i] = ts.state_vector[i]
                norm_sq += abs(collapsed[i]) ** 2

        if norm_sq > 1e-15:
            norm = math.sqrt(norm_sq)
            for i in range(8):
                collapsed[i] /= norm
        ts.state_vector = collapsed
        ts.step = 4
        return f"Alice measures: |{m0}{m1}⟩ (sent via classical channel)"

    elif step == 4:
        # Step 4: 고전 채널 전송 (시각화 단계)
        ts.step = 5
        m0, m1 = ts.measurement_result
        return f"Classical bits ({m0},{m1}) transmitted to Bob"

    elif step == 5:
        # Step 5: Bob 보정
        m0, m1 = ts.measurement_result
        # Bob의 큐비트 (qubit 2) 상태 추출
        bob_0 = complex(0)
        bob_1 = complex(0)
        for i in range(8):
            q2 = i & 1
            if abs(ts.state_vector[i]) > 1e-15:
                if q2 == 0:
                    bob_0 += ts.state_vector[i]
                else:
                    bob_1 += ts.state_vector[i]

        # 보정 게이트 적용
        if m1 == 1:  # X gate
            bob_0, bob_1 = bob_1, bob_0
        if m0 == 1:  # Z gate
            bob_1 = -bob_1

        # 정규화
        norm = math.sqrt(abs(bob_0) ** 2 + abs(bob_1) ** 2)
        if norm > 1e-10:
            bob_0 /= norm
            bob_1 /= norm

        ts.bob_alpha = bob_0
        ts.bob_beta = bob_1

        # Fidelity: |⟨ψ_in|ψ_out⟩|²
        overlap = ts.alpha.conjugate() * bob_0 + ts.beta.conjugate() * bob_1
        ts.fidelity = abs(overlap) ** 2

        ts.step = 6
        corrections = []
        if m1 == 1:
            corrections.append("X")
        if m0 == 1:
            corrections.append("Z")
        corr_str = " + ".join(corrections) if corrections else "None"
        return f"Bob applies correction ({corr_str}) → Fidelity: {ts.fidelity:.4f}"


def create_random_state() -> Tuple[complex, complex]:
    """블로흐 구 위의 랜덤 순수 상태 생성."""
    theta = random.uniform(0, math.pi)
    phi = random.uniform(0, 2 * math.pi)
    alpha = complex(math.cos(theta / 2), 0)
    beta = cmath.exp(1j * phi) * math.sin(theta / 2)
    return (alpha, beta)


def bloch_angles(alpha: complex, beta: complex) -> Tuple[float, float]:
    """상태 벡터에서 블로흐 구 각도 (theta, phi) 추출."""
    if abs(alpha) > 1e-10:
        phase = cmath.phase(alpha)
        alpha = alpha * cmath.exp(-1j * phase)
        beta = beta * cmath.exp(-1j * phase)

    theta = 2 * math.acos(min(1.0, max(0.0, abs(alpha))))
    phi = cmath.phase(beta) if abs(beta) > 1e-10 else 0.0
    return (theta, phi)


def bloch_xyz(alpha: complex, beta: complex) -> Tuple[float, float, float]:
    """상태 벡터에서 블로흐 구 (x, y, z) 좌표."""
    theta, phi = bloch_angles(alpha, beta)
    x = math.sin(theta) * math.cos(phi)
    y = math.sin(theta) * math.sin(phi)
    z = math.cos(theta)
    return (x, y, z)
