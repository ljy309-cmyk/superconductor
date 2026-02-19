"""Grover's Search Algorithm 엔진 — 양자 탐색 알고리즘 시뮬레이션.

numpy 없이 순수 Python으로 Grover's Algorithm의 전 과정을 시뮬레이션합니다.
  - 데이터베이스 초기화: N개 상태의 균등 중첩
  - Oracle: 마킹 대상 상태의 위상 반전
  - Diffusion: 평균 반전 (2|ψ⟩⟨ψ| - I)
  - 반복: ~π/4 × √(N/M) 회 반복 후 측정
  - 고전 비교: O(N) vs O(√N) 양자 우위 체감

사용법:
    from quantum.grover_search_engine import GroverState, grover_step
    state = GroverState(n_qubits=4, targets=[7])
    while state.phase != GroverPhase.DONE:
        grover_step(state)
    print(state.measured)  # 7
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto

from config_loader import cfg
from i18n import t

# ── 설정 ──────────────────────────────────────────────
MAX_QUBITS = cfg("grover", "max_qubits", 10)
DEFAULT_QUBITS = cfg("grover", "default_qubits", 4)
ANIMATION_SPEED = cfg("grover", "animation_speed", 0.5)
AUTO_BATCH_SIZE = cfg("grover", "auto_batch_size", 1)


# ── 알고리즘 단계 (Phase) ────────────────────────────
class GroverPhase(Enum):
    """Grover's Algorithm 진행 단계."""
    INPUT = auto()              # 1. 입력 대기
    INIT_SUPERPOSITION = auto() # 2. Hadamard → 균등 중첩 |ψ⟩
    ORACLE = auto()             # 3. Oracle: 마킹 상태 위상 반전
    DIFFUSION = auto()          # 4. Diffusion: 평균 반전
    ITERATE = auto()            # 5. 반복 판정 (계속 or 측정)
    MEASURE = auto()            # 6. 측정
    SUCCESS = auto()            # 7. 탐색 성공
    FAIL = auto()               # 8. 탐색 실패
    DONE = auto()               # 9. 완료


# ── 상태 데이터 ──────────────────────────────────────

@dataclass
class AmplitudeSnapshot:
    """반복 시점의 진폭 스냅샷."""
    iteration: int
    amplitudes: list[float]          # 확률 진폭 (부호 포함)
    target_probability: float        # 마킹 상태의 총 확률


@dataclass
class ClassicalComparison:
    """고전 탐색 vs 양자 탐색 비교 데이터."""
    database_size: int               # N = 2^n
    n_targets: int                   # 마킹 대상 수 M
    classical_expected: float        # 고전 기대 탐색 횟수: N/M
    quantum_iterations: int          # Grover 최적 반복: ⌊π/4 × √(N/M)⌋
    speedup_ratio: float             # 속도 향상 비율


@dataclass
class GroverState:
    """Grover's Algorithm 전체 상태."""
    # 입력
    n_qubits: int = DEFAULT_QUBITS   # 큐빗 수 (데이터베이스 크기 N = 2^n)
    targets: list[int] = field(default_factory=lambda: [7])  # 마킹 대상 인덱스

    # 현재 단계
    phase: GroverPhase = GroverPhase.INPUT
    step_message: str = ""           # 현재 단계 설명 메시지

    # 양자 상태 (진폭)
    amplitudes: list[float] = field(default_factory=list)  # 실수 진폭 배열

    # 반복 추적
    current_iteration: int = 0       # 현재 반복 횟수
    optimal_iterations: int = 0      # 최적 반복 횟수
    max_iterations: int = 0          # 허용 최대 반복 (최적의 2배)

    # 시각화 데이터
    amplitude_history: list[AmplitudeSnapshot] = field(default_factory=list)
    target_prob_history: list[float] = field(default_factory=list)  # 반복별 목표 확률

    # 측정 결과
    measured: int | None = None      # 측정된 상태 인덱스
    measured_is_target: bool = False # 측정 결과가 마킹 상태인지

    # 고전 비교
    comparison: ClassicalComparison | None = None

    # 통계
    total_oracle_calls: int = 0
    total_searches: int = 0
    successful_searches: int = 0
    search_history: list[dict] = field(default_factory=list)


# ── 핵심 양자 연산 ──────────────────────────────────

def optimal_iterations(n_states: int, n_targets: int) -> int:
    """최적 Grover 반복 횟수: ⌊π/4 × √(N/M)⌋.

    Args:
        n_states: 전체 상태 수 N = 2^n
        n_targets: 마킹 대상 수 M

    Returns:
        최적 반복 횟수 (최소 1)
    """
    if n_targets <= 0 or n_targets >= n_states:
        return 1
    return max(1, int(math.pi / 4 * math.sqrt(n_states / n_targets)))


def init_superposition(n_states: int) -> list[float]:
    """균등 중첩 상태 초기화: |ψ⟩ = H⊗n|0⟩.

    모든 상태에 동일한 진폭 1/√N을 부여합니다.
    """
    amp = 1.0 / math.sqrt(n_states)
    return [amp] * n_states


def apply_oracle(amplitudes: list[float], targets: list[int]) -> list[float]:
    """Oracle 연산: 마킹 상태의 위상을 반전합니다.

    |x⟩ → -|x⟩  (x ∈ targets)
    |x⟩ →  |x⟩  (x ∉ targets)
    """
    result = amplitudes[:]
    for t_idx in targets:
        if 0 <= t_idx < len(result):
            result[t_idx] = -result[t_idx]
    return result


def apply_diffusion(amplitudes: list[float]) -> list[float]:
    """Diffusion 연산 (Grover diffusion operator).

    D = 2|ψ⟩⟨ψ| - I
    각 진폭을 평균값 기준으로 반전합니다:
        a_i → 2·mean - a_i
    """
    n = len(amplitudes)
    mean = sum(amplitudes) / n
    return [2.0 * mean - a for a in amplitudes]


def get_probabilities(amplitudes: list[float]) -> list[float]:
    """진폭에서 확률 계산: P(x) = |a_x|²."""
    return [a * a for a in amplitudes]


def target_probability(amplitudes: list[float], targets: list[int]) -> float:
    """마킹 상태들의 총 확률."""
    return sum(amplitudes[t] ** 2 for t in targets if 0 <= t < len(amplitudes))


def measure(amplitudes: list[float]) -> int:
    """양자 상태를 측정합니다.

    확률 분포에 따라 하나의 상태를 선택합니다.
    """
    probs = get_probabilities(amplitudes)
    total = sum(probs)
    if total == 0:
        return random.randint(0, len(amplitudes) - 1)

    r = random.random() * total
    cumulative = 0.0
    for i, p in enumerate(probs):
        cumulative += p
        if r <= cumulative:
            return i
    return len(amplitudes) - 1


def compute_comparison(n_states: int, n_targets: int) -> ClassicalComparison:
    """고전 vs 양자 탐색 비교 데이터를 계산합니다."""
    classical = n_states / max(1, n_targets)
    quantum = optimal_iterations(n_states, n_targets)
    speedup = classical / max(1, quantum)

    return ClassicalComparison(
        database_size=n_states,
        n_targets=n_targets,
        classical_expected=classical,
        quantum_iterations=quantum,
        speedup_ratio=speedup,
    )


# ── 단계별 실행 ──────────────────────────────────────

def grover_step(state: GroverState) -> GroverPhase:
    """Grover's Algorithm 한 단계 진행.

    UI에서 매 프레임/키 입력마다 호출하여 단계별 진행합니다.
    Returns: 현재 phase.
    """
    if state.phase == GroverPhase.INPUT:
        _step_input(state)
    elif state.phase == GroverPhase.INIT_SUPERPOSITION:
        _step_init_superposition(state)
    elif state.phase == GroverPhase.ORACLE:
        _step_oracle(state)
    elif state.phase == GroverPhase.DIFFUSION:
        _step_diffusion(state)
    elif state.phase == GroverPhase.ITERATE:
        _step_iterate(state)
    elif state.phase == GroverPhase.MEASURE:
        _step_measure(state)
    # SUCCESS, FAIL, DONE → 아무 동작 안 함
    return state.phase


def grover_run_full(n_qubits: int, targets: list[int]) -> GroverState:
    """Grover's Algorithm 전체 실행 (자동 모드).

    모든 단계를 한번에 실행하고 최종 상태를 반환합니다.
    """
    state = GroverState(n_qubits=n_qubits, targets=targets[:])
    max_steps = 500
    for _ in range(max_steps):
        grover_step(state)
        if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL, GroverPhase.DONE):
            break
    if state.phase == GroverPhase.SUCCESS:
        state.phase = GroverPhase.DONE
    return state


def reset_state(state: GroverState, n_qubits: int | None = None,
                targets: list[int] | None = None):
    """상태를 초기화합니다."""
    if n_qubits is not None:
        state.n_qubits = n_qubits
    if targets is not None:
        state.targets = targets[:]

    state.phase = GroverPhase.INPUT
    state.step_message = ""
    state.amplitudes.clear()
    state.current_iteration = 0
    state.optimal_iterations = 0
    state.max_iterations = 0
    state.amplitude_history.clear()
    state.target_prob_history.clear()
    state.measured = None
    state.measured_is_target = False
    state.comparison = None
    state.total_oracle_calls = 0


# ── 각 단계 구현 ─────────────────────────────────────

def _step_input(state: GroverState):
    """Step 1: 입력 검증."""
    n = state.n_qubits
    if n < 1:
        state.step_message = t("grover_msg_qubits_too_small")
        state.phase = GroverPhase.DONE
        return
    if n > MAX_QUBITS:
        state.step_message = t("grover_msg_qubits_too_large", max=MAX_QUBITS)
        state.phase = GroverPhase.DONE
        return

    n_states = 1 << n
    # 대상 검증
    valid_targets = [t_val for t_val in state.targets if 0 <= t_val < n_states]
    if not valid_targets:
        state.step_message = t("grover_msg_no_targets")
        state.phase = GroverPhase.DONE
        return

    state.targets = valid_targets
    state.step_message = t("grover_msg_input_ok", n=n, N=n_states,
                           M=len(valid_targets))
    state.phase = GroverPhase.INIT_SUPERPOSITION


def _step_init_superposition(state: GroverState):
    """Step 2: Hadamard → 균등 중첩."""
    n_states = 1 << state.n_qubits
    state.amplitudes = init_superposition(n_states)
    state.optimal_iterations = optimal_iterations(n_states, len(state.targets))
    state.max_iterations = max(1, state.optimal_iterations * 2)

    # 비교 데이터 생성
    state.comparison = compute_comparison(n_states, len(state.targets))

    # 초기 스냅샷
    prob = target_probability(state.amplitudes, state.targets)
    state.amplitude_history.append(AmplitudeSnapshot(
        iteration=0,
        amplitudes=state.amplitudes[:],
        target_probability=prob,
    ))
    state.target_prob_history.append(prob)

    state.step_message = t("grover_msg_superposition",
                           N=n_states, amp=f"{state.amplitudes[0]:.4f}",
                           opt=state.optimal_iterations)
    state.phase = GroverPhase.ORACLE


def _step_oracle(state: GroverState):
    """Step 3: Oracle — 마킹 상태 위상 반전."""
    state.amplitudes = apply_oracle(state.amplitudes, state.targets)
    state.total_oracle_calls += 1
    state.current_iteration += 1

    targets_str = ", ".join(str(t_val) for t_val in state.targets[:5])
    if len(state.targets) > 5:
        targets_str += ", ..."
    state.step_message = t("grover_msg_oracle",
                           iter=state.current_iteration, targets=targets_str)
    state.phase = GroverPhase.DIFFUSION


def _step_diffusion(state: GroverState):
    """Step 4: Diffusion — 평균 반전."""
    state.amplitudes = apply_diffusion(state.amplitudes)

    # 스냅샷 기록
    prob = target_probability(state.amplitudes, state.targets)
    state.amplitude_history.append(AmplitudeSnapshot(
        iteration=state.current_iteration,
        amplitudes=state.amplitudes[:],
        target_probability=prob,
    ))
    state.target_prob_history.append(prob)

    state.step_message = t("grover_msg_diffusion",
                           iter=state.current_iteration,
                           prob=f"{prob:.1%}")
    state.phase = GroverPhase.ITERATE


def _step_iterate(state: GroverState):
    """Step 5: 반복 판정."""
    if state.current_iteration >= state.optimal_iterations:
        state.step_message = t("grover_msg_optimal_reached",
                               iter=state.current_iteration,
                               opt=state.optimal_iterations)
        state.phase = GroverPhase.MEASURE
    elif state.current_iteration >= state.max_iterations:
        state.step_message = t("grover_msg_max_reached",
                               max=state.max_iterations)
        state.phase = GroverPhase.MEASURE
    else:
        prob = target_probability(state.amplitudes, state.targets)
        state.step_message = t("grover_msg_continue",
                               iter=state.current_iteration,
                               opt=state.optimal_iterations,
                               prob=f"{prob:.1%}")
        state.phase = GroverPhase.ORACLE


def _step_measure(state: GroverState):
    """Step 6: 측정."""
    result = measure(state.amplitudes)
    state.measured = result
    state.measured_is_target = result in state.targets
    state.total_searches += 1

    prob = target_probability(state.amplitudes, state.targets)
    state.step_message = t("grover_msg_measured",
                           result=result,
                           prob=f"{prob:.1%}")

    # 히스토리 기록
    state.search_history.append({
        "n_qubits": state.n_qubits,
        "targets": state.targets[:],
        "measured": result,
        "success": state.measured_is_target,
        "iterations": state.current_iteration,
        "optimal": state.optimal_iterations,
        "target_prob": prob,
    })

    if state.measured_is_target:
        state.successful_searches += 1
        state.step_message = t("grover_msg_success",
                               result=result,
                               iter=state.current_iteration)
        state.phase = GroverPhase.SUCCESS
    else:
        state.step_message = t("grover_msg_fail",
                               result=result,
                               target=state.targets[0])
        state.phase = GroverPhase.FAIL


# ── 교육 메시지 ──────────────────────────────────────

_PHASE_DESC_KEYS = {
    GroverPhase.INPUT: "grover_desc_input",
    GroverPhase.INIT_SUPERPOSITION: "grover_desc_superposition",
    GroverPhase.ORACLE: "grover_desc_oracle",
    GroverPhase.DIFFUSION: "grover_desc_diffusion",
    GroverPhase.ITERATE: "grover_desc_iterate",
    GroverPhase.MEASURE: "grover_desc_measure",
    GroverPhase.SUCCESS: "grover_desc_success",
    GroverPhase.FAIL: "grover_desc_fail",
    GroverPhase.DONE: "grover_desc_done",
}


def get_phase_description(phase: GroverPhase) -> str:
    """현재 단계의 다국어 설명을 반환합니다."""
    key = _PHASE_DESC_KEYS.get(phase, "grover_desc_done")
    return t(key)


class _PhaseDescProxy:
    """Dict-like proxy that returns i18n strings on access."""

    def get(self, phase, default=""):
        return get_phase_description(phase) if phase in _PHASE_DESC_KEYS else default

    def __getitem__(self, phase):
        return get_phase_description(phase)

    def __contains__(self, phase):
        return phase in _PHASE_DESC_KEYS


PHASE_DESCRIPTIONS = _PhaseDescProxy()


def get_quantum_advantage_message() -> str:
    """양자 우위 설명 메시지를 다국어로 반환합니다."""
    return t("grover_quantum_advantage")
