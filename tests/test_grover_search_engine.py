"""Grover's Search Algorithm 엔진 단위 테스트.

핵심 양자 연산(Oracle, Diffusion, 측정)과 단계별 진행,
시각화 데이터 생성, 고전 비교 데이터를 검증합니다.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum.grover_search_engine import (
    AmplitudeSnapshot,
    ClassicalComparison,
    GroverPhase,
    GroverState,
    apply_diffusion,
    apply_oracle,
    compute_comparison,
    get_phase_description,
    get_probabilities,
    get_quantum_advantage_message,
    grover_run_full,
    grover_step,
    init_superposition,
    measure,
    optimal_iterations,
    reset_state,
    target_probability,
)


# ── 균등 중첩 초기화 테스트 ──────────────────────────

class TestInitSuperposition(unittest.TestCase):
    """init_superposition: 균등 중첩 상태 생성."""

    def test_length(self):
        """상태 수 = N."""
        for n in [2, 4, 8, 16, 256]:
            amps = init_superposition(n)
            self.assertEqual(len(amps), n)

    def test_uniform_amplitude(self):
        """모든 진폭 = 1/√N."""
        for n in [4, 16, 64]:
            amps = init_superposition(n)
            expected = 1.0 / math.sqrt(n)
            for a in amps:
                self.assertAlmostEqual(a, expected)

    def test_normalization(self):
        """확률 합 = 1."""
        for n in [4, 16, 256]:
            amps = init_superposition(n)
            total = sum(a * a for a in amps)
            self.assertAlmostEqual(total, 1.0, places=10)

    def test_single_state(self):
        """N=1: 진폭 = 1."""
        amps = init_superposition(1)
        self.assertEqual(len(amps), 1)
        self.assertAlmostEqual(amps[0], 1.0)


# ── Oracle 테스트 ────────────────────────────────────

class TestOracle(unittest.TestCase):
    """apply_oracle: 마킹 상태 위상 반전."""

    def test_single_target_flip(self):
        """단일 대상: 해당 진폭만 부호 반전."""
        amps = [0.5, 0.5, 0.5, 0.5]
        result = apply_oracle(amps, [2])
        self.assertAlmostEqual(result[0], 0.5)
        self.assertAlmostEqual(result[1], 0.5)
        self.assertAlmostEqual(result[2], -0.5)
        self.assertAlmostEqual(result[3], 0.5)

    def test_multiple_targets(self):
        """다중 대상: 모든 대상 진폭 반전."""
        amps = [0.5, 0.5, 0.5, 0.5]
        result = apply_oracle(amps, [0, 3])
        self.assertAlmostEqual(result[0], -0.5)
        self.assertAlmostEqual(result[1], 0.5)
        self.assertAlmostEqual(result[2], 0.5)
        self.assertAlmostEqual(result[3], -0.5)

    def test_no_target(self):
        """대상 없음: 변화 없음."""
        amps = [0.5, 0.5, 0.5, 0.5]
        result = apply_oracle(amps, [])
        self.assertEqual(result, amps)

    def test_preserves_normalization(self):
        """Oracle은 정규화를 보존."""
        amps = init_superposition(8)
        result = apply_oracle(amps, [3, 5])
        total = sum(a * a for a in result)
        self.assertAlmostEqual(total, 1.0, places=10)

    def test_does_not_modify_original(self):
        """원본 배열 변경 없음."""
        amps = [0.5, 0.5, 0.5, 0.5]
        original = amps[:]
        apply_oracle(amps, [1])
        self.assertEqual(amps, original)

    def test_out_of_range_target_ignored(self):
        """범위 밖 대상 인덱스 무시."""
        amps = [0.5, 0.5, 0.5, 0.5]
        result = apply_oracle(amps, [10])
        self.assertEqual(result, amps)

    def test_double_oracle_identity(self):
        """Oracle 2회 적용 = 항등."""
        amps = init_superposition(8)
        once = apply_oracle(amps, [3])
        twice = apply_oracle(once, [3])
        for a, b in zip(amps, twice):
            self.assertAlmostEqual(a, b, places=10)


# ── Diffusion 테스트 ─────────────────────────────────

class TestDiffusion(unittest.TestCase):
    """apply_diffusion: 평균 반전 연산."""

    def test_uniform_unchanged(self):
        """균등 분포에 Diffusion 적용 → 변화 없음."""
        amps = [0.5, 0.5, 0.5, 0.5]
        result = apply_diffusion(amps)
        for a, r in zip(amps, result):
            self.assertAlmostEqual(a, r)

    def test_amplification_effect(self):
        """Oracle 후 Diffusion: 마킹 진폭 증가."""
        amps = init_superposition(4)
        after_oracle = apply_oracle(amps, [2])
        after_diffusion = apply_diffusion(after_oracle)

        # 마킹 상태의 진폭이 증가해야 함
        self.assertGreater(abs(after_diffusion[2]), abs(amps[2]))

    def test_preserves_normalization(self):
        """Diffusion은 정규화를 보존."""
        amps = init_superposition(16)
        after_oracle = apply_oracle(amps, [5])
        result = apply_diffusion(after_oracle)
        total = sum(a * a for a in result)
        self.assertAlmostEqual(total, 1.0, places=10)

    def test_inversion_about_mean(self):
        """2*mean - a_i 공식 검증."""
        amps = [0.3, 0.5, -0.2, 0.4]
        mean = sum(amps) / len(amps)
        result = apply_diffusion(amps)
        for i, a in enumerate(amps):
            expected = 2.0 * mean - a
            self.assertAlmostEqual(result[i], expected)


# ── 최적 반복 횟수 테스트 ────────────────────────────

class TestOptimalIterations(unittest.TestCase):
    """optimal_iterations: π/4 × √(N/M)."""

    def test_n16_m1(self):
        """N=16, M=1 → ⌊π/4 × 4⌋ = 3."""
        k = optimal_iterations(16, 1)
        self.assertEqual(k, 3)

    def test_n64_m1(self):
        """N=64, M=1 → ⌊π/4 × 8⌋ = 6."""
        k = optimal_iterations(64, 1)
        self.assertEqual(k, 6)

    def test_n256_m1(self):
        """N=256, M=1 → ⌊π/4 × 16⌋ = 12."""
        k = optimal_iterations(256, 1)
        self.assertEqual(k, 12)

    def test_n1024_m1(self):
        """N=1024, M=1 → ⌊π/4 × 32⌋ = 25."""
        k = optimal_iterations(1024, 1)
        self.assertEqual(k, 25)

    def test_multiple_targets(self):
        """다중 대상: √(N/M) 감소."""
        k1 = optimal_iterations(64, 1)
        k4 = optimal_iterations(64, 4)
        self.assertGreater(k1, k4)

    def test_minimum_1(self):
        """최소값 = 1."""
        k = optimal_iterations(4, 4)
        self.assertGreaterEqual(k, 1)

    def test_zero_targets(self):
        """M=0 → 1."""
        k = optimal_iterations(16, 0)
        self.assertEqual(k, 1)


# ── 측정 테스트 ──────────────────────────────────────

class TestMeasure(unittest.TestCase):
    """measure: 확률적 측정."""

    def test_deterministic_state(self):
        """확정 상태: 항상 같은 결과."""
        amps = [0.0, 0.0, 1.0, 0.0]
        for _ in range(20):
            self.assertEqual(measure(amps), 2)

    def test_result_in_range(self):
        """결과가 유효 범위 내."""
        amps = init_superposition(8)
        for _ in range(50):
            result = measure(amps)
            self.assertGreaterEqual(result, 0)
            self.assertLess(result, 8)

    def test_high_probability_target(self):
        """높은 확률 상태가 자주 측정됨."""
        # Grover 반복 후 진폭 설정
        amps = [0.01] * 16
        amps[7] = 0.99  # 거의 확정
        # 정규화
        total = math.sqrt(sum(a * a for a in amps))
        amps = [a / total for a in amps]

        counts = {7: 0}
        for _ in range(100):
            r = measure(amps)
            if r == 7:
                counts[7] += 1
        self.assertGreater(counts[7], 80)


# ── target_probability 테스트 ────────────────────────

class TestTargetProbability(unittest.TestCase):
    """target_probability: 마킹 상태 총 확률."""

    def test_uniform(self):
        """균등 분포: 각 상태 1/N."""
        amps = init_superposition(16)
        prob = target_probability(amps, [5])
        self.assertAlmostEqual(prob, 1.0 / 16)

    def test_multiple_targets(self):
        """다중 대상: 확률 합산."""
        amps = init_superposition(8)
        prob = target_probability(amps, [1, 3, 5])
        self.assertAlmostEqual(prob, 3.0 / 8)

    def test_deterministic(self):
        """확정 상태: P = 1."""
        amps = [0.0, 0.0, 0.0, 1.0]
        prob = target_probability(amps, [3])
        self.assertAlmostEqual(prob, 1.0)

    def test_after_grover_iterations(self):
        """Grover 반복 후 확률 증가."""
        n = 16
        targets = [7]
        amps = init_superposition(n)
        prob_initial = target_probability(amps, targets)

        # 1회 반복
        amps = apply_oracle(amps, targets)
        amps = apply_diffusion(amps)
        prob_after = target_probability(amps, targets)

        self.assertGreater(prob_after, prob_initial)


# ── get_probabilities 테스트 ─────────────────────────

class TestGetProbabilities(unittest.TestCase):
    """get_probabilities: |a|² 변환."""

    def test_positive_amplitudes(self):
        """양수 진폭: P = a²."""
        probs = get_probabilities([0.5, 0.5, 0.5, 0.5])
        for p in probs:
            self.assertAlmostEqual(p, 0.25)

    def test_negative_amplitudes(self):
        """음수 진폭: P = |a|² = a²."""
        probs = get_probabilities([-0.5, 0.5, -0.5, 0.5])
        for p in probs:
            self.assertAlmostEqual(p, 0.25)

    def test_sum_one(self):
        """정규화된 상태: 확률 합 = 1."""
        amps = init_superposition(8)
        probs = get_probabilities(amps)
        self.assertAlmostEqual(sum(probs), 1.0, places=10)


# ── Grover 전체 파이프라인 테스트 ────────────────────

class TestGroverPipeline(unittest.TestCase):
    """전체 Grover 알고리즘 파이프라인."""

    def test_grover_4qubit_single_target(self):
        """4큐빗, 단일 대상: 높은 성공률."""
        successes = 0
        trials = 30
        for _ in range(trials):
            state = grover_run_full(4, [7])
            if state.measured == 7:
                successes += 1
        # 4큐빗 1대상: 이론 확률 ~96%
        self.assertGreater(successes, trials * 0.7)

    def test_grover_3qubit_single_target(self):
        """3큐빗, 단일 대상: 높은 성공률."""
        successes = 0
        trials = 30
        for _ in range(trials):
            state = grover_run_full(3, [5])
            if state.measured == 5:
                successes += 1
        self.assertGreater(successes, trials * 0.7)

    def test_grover_multiple_targets(self):
        """다중 대상: 마킹 상태 중 하나 측정."""
        targets = [2, 5, 11]
        successes = 0
        trials = 30
        for _ in range(trials):
            state = grover_run_full(4, targets)
            if state.measured in targets:
                successes += 1
        self.assertGreater(successes, trials * 0.7)

    def test_factors_populated(self):
        """실행 후 필수 필드가 채워짐."""
        state = grover_run_full(4, [7])
        self.assertIsNotNone(state.measured)
        self.assertGreater(state.total_oracle_calls, 0)
        self.assertIsNotNone(state.comparison)

    def test_amplitude_history_recorded(self):
        """amplitude_history에 반복 기록."""
        state = grover_run_full(4, [7])
        # 최소 2개 스냅샷 (초기 + 반복)
        self.assertGreaterEqual(len(state.amplitude_history), 2)
        # 첫 스냅샷: iteration 0
        self.assertEqual(state.amplitude_history[0].iteration, 0)

    def test_target_prob_history_monotonic_initial(self):
        """첫 몇 반복 동안 target_prob_history 증가."""
        state = grover_run_full(4, [7])
        if len(state.target_prob_history) >= 3:
            # 초기 증가 (최적 도달 전)
            self.assertGreater(state.target_prob_history[1],
                               state.target_prob_history[0])


# ── grover_step 단계별 테스트 ────────────────────────

class TestGroverStep(unittest.TestCase):
    """grover_step: 각 단계 올바르게 진행."""

    def test_input_to_superposition(self):
        """INPUT → INIT_SUPERPOSITION."""
        state = GroverState(n_qubits=4, targets=[7])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.INIT_SUPERPOSITION)

    def test_superposition_to_oracle(self):
        """INIT_SUPERPOSITION → ORACLE."""
        state = GroverState(n_qubits=4, targets=[7])
        grover_step(state)  # INPUT
        grover_step(state)  # INIT_SUPERPOSITION
        self.assertEqual(state.phase, GroverPhase.ORACLE)

    def test_superposition_initializes_amplitudes(self):
        """INIT_SUPERPOSITION: amplitudes 배열 생성."""
        state = GroverState(n_qubits=3, targets=[5])
        grover_step(state)
        grover_step(state)

        self.assertEqual(len(state.amplitudes), 8)
        expected = 1.0 / math.sqrt(8)
        for a in state.amplitudes:
            self.assertAlmostEqual(a, expected)

    def test_oracle_flips_target(self):
        """ORACLE: 대상 진폭 반전."""
        state = GroverState(n_qubits=2, targets=[3])
        grover_step(state)  # INPUT
        grover_step(state)  # INIT_SUPERPOSITION

        amp_before = state.amplitudes[3]
        grover_step(state)  # ORACLE
        amp_after = state.amplitudes[3]

        self.assertAlmostEqual(amp_after, -amp_before)
        self.assertEqual(state.phase, GroverPhase.DIFFUSION)

    def test_diffusion_amplifies(self):
        """DIFFUSION: 마킹 진폭 증가."""
        state = GroverState(n_qubits=4, targets=[7])
        grover_step(state)  # INPUT
        grover_step(state)  # INIT_SUPERPOSITION

        prob_initial = target_probability(state.amplitudes, [7])
        grover_step(state)  # ORACLE
        grover_step(state)  # DIFFUSION

        prob_after = target_probability(state.amplitudes, [7])
        self.assertGreater(prob_after, prob_initial)
        self.assertEqual(state.phase, GroverPhase.ITERATE)

    def test_iterate_continues_or_measures(self):
        """ITERATE: 계속 or 측정 판정."""
        state = GroverState(n_qubits=4, targets=[7])
        grover_step(state)  # INPUT
        grover_step(state)  # INIT_SUPERPOSITION
        grover_step(state)  # ORACLE
        grover_step(state)  # DIFFUSION
        grover_step(state)  # ITERATE

        # 4큐빗 1대상: optimal=3 → 1회 후 계속
        if state.current_iteration < state.optimal_iterations:
            self.assertEqual(state.phase, GroverPhase.ORACLE)
        else:
            self.assertEqual(state.phase, GroverPhase.MEASURE)

    def test_full_step_sequence(self):
        """전체 step 시퀀스 완료."""
        state = GroverState(n_qubits=3, targets=[5])
        phases_seen = set()

        for _ in range(100):
            grover_step(state)
            phases_seen.add(state.phase)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL,
                               GroverPhase.DONE):
                break

        # 핵심 단계를 모두 거쳐야 함
        self.assertIn(GroverPhase.INIT_SUPERPOSITION, phases_seen)
        self.assertIn(GroverPhase.ORACLE, phases_seen)
        self.assertIn(GroverPhase.DIFFUSION, phases_seen)
        self.assertIn(GroverPhase.MEASURE, phases_seen)

    def test_step_messages_not_empty(self):
        """각 단계에서 step_message가 비어있지 않음."""
        state = GroverState(n_qubits=3, targets=[5])
        for _ in range(100):
            grover_step(state)
            self.assertGreater(len(state.step_message), 0,
                               f"Empty message at {state.phase}")
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL,
                               GroverPhase.DONE):
                break


# ── 입력 검증 테스트 ─────────────────────────────────

class TestInputValidation(unittest.TestCase):
    """입력값 경계 검증."""

    def test_zero_qubits(self):
        """0큐빗 → DONE."""
        state = GroverState(n_qubits=0, targets=[0])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_too_many_qubits(self):
        """초과 큐빗 → DONE."""
        state = GroverState(n_qubits=20, targets=[0])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_invalid_target(self):
        """유효하지 않은 대상 → DONE."""
        state = GroverState(n_qubits=3, targets=[100])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_valid_input(self):
        """유효한 입력 → INIT_SUPERPOSITION."""
        state = GroverState(n_qubits=3, targets=[5])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.INIT_SUPERPOSITION)

    def test_partial_valid_targets(self):
        """일부 유효한 대상: 유효한 것만 유지."""
        state = GroverState(n_qubits=3, targets=[5, 100, 2])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.INIT_SUPERPOSITION)
        self.assertEqual(state.targets, [5, 2])


# ── reset_state 테스트 ───────────────────────────────

class TestResetState(unittest.TestCase):
    """reset_state: 상태 초기화."""

    def test_reset_clears_all(self):
        """리셋 후 모든 상태 초기화."""
        state = grover_run_full(4, [7])
        reset_state(state)

        self.assertEqual(state.phase, GroverPhase.INPUT)
        self.assertEqual(len(state.amplitudes), 0)
        self.assertEqual(state.current_iteration, 0)
        self.assertIsNone(state.measured)
        self.assertFalse(state.measured_is_target)
        self.assertEqual(len(state.amplitude_history), 0)
        self.assertEqual(len(state.target_prob_history), 0)

    def test_reset_with_new_params(self):
        """새 파라미터로 리셋."""
        state = grover_run_full(4, [7])
        reset_state(state, n_qubits=5, targets=[10, 20])

        self.assertEqual(state.n_qubits, 5)
        self.assertEqual(state.targets, [10, 20])
        self.assertEqual(state.phase, GroverPhase.INPUT)

    def test_reset_preserves_history(self):
        """리셋 후 search_history는 보존."""
        state = grover_run_full(4, [7])
        history_len = len(state.search_history)
        reset_state(state)

        self.assertEqual(len(state.search_history), history_len)


# ── 고전 비교 데이터 테스트 ──────────────────────────

class TestClassicalComparison(unittest.TestCase):
    """compute_comparison: 고전 vs 양자 비교."""

    def test_comparison_values(self):
        """비교 데이터 정확성."""
        comp = compute_comparison(1024, 1)
        self.assertEqual(comp.database_size, 1024)
        self.assertEqual(comp.n_targets, 1)
        self.assertAlmostEqual(comp.classical_expected, 1024.0)
        self.assertEqual(comp.quantum_iterations, 25)
        self.assertGreater(comp.speedup_ratio, 30)

    def test_speedup_increases_with_n(self):
        """N이 커지면 speedup 증가."""
        comp16 = compute_comparison(16, 1)
        comp256 = compute_comparison(256, 1)
        comp1024 = compute_comparison(1024, 1)
        self.assertGreater(comp256.speedup_ratio, comp16.speedup_ratio)
        self.assertGreater(comp1024.speedup_ratio, comp256.speedup_ratio)

    def test_more_targets_less_iterations(self):
        """대상이 많으면 반복 감소."""
        comp1 = compute_comparison(64, 1)
        comp4 = compute_comparison(64, 4)
        self.assertGreater(comp1.quantum_iterations, comp4.quantum_iterations)

    def test_comparison_populated_in_pipeline(self):
        """파이프라인에서 comparison 데이터 생성."""
        state = grover_run_full(4, [7])
        self.assertIsNotNone(state.comparison)
        self.assertEqual(state.comparison.database_size, 16)
        self.assertEqual(state.comparison.n_targets, 1)


# ── 시각화 데이터 테스트 ─────────────────────────────

class TestVisualizationData(unittest.TestCase):
    """시각화 렌더링에 필요한 데이터 정합성."""

    def test_amplitude_snapshot_structure(self):
        """AmplitudeSnapshot 구조 검증."""
        state = grover_run_full(3, [5])
        for snap in state.amplitude_history:
            self.assertIsInstance(snap, AmplitudeSnapshot)
            self.assertIsInstance(snap.iteration, int)
            self.assertIsInstance(snap.amplitudes, list)
            self.assertEqual(len(snap.amplitudes), 8)
            self.assertIsInstance(snap.target_probability, float)

    def test_amplitude_history_ordered(self):
        """amplitude_history가 반복 순서대로."""
        state = grover_run_full(4, [7])
        for i in range(1, len(state.amplitude_history)):
            self.assertGreater(state.amplitude_history[i].iteration,
                               state.amplitude_history[i - 1].iteration)

    def test_target_prob_history_length(self):
        """target_prob_history 길이 = amplitude_history 길이."""
        state = grover_run_full(4, [7])
        self.assertEqual(len(state.target_prob_history),
                         len(state.amplitude_history))

    def test_amplitudes_normalized_throughout(self):
        """모든 스냅샷에서 확률 합 = 1."""
        state = grover_run_full(4, [7])
        for snap in state.amplitude_history:
            total = sum(a * a for a in snap.amplitudes)
            self.assertAlmostEqual(total, 1.0, places=8)

    def test_search_history_entries(self):
        """search_history 항목 필수 필드."""
        state = grover_run_full(4, [7])
        self.assertGreater(len(state.search_history), 0)
        h = state.search_history[-1]
        self.assertIn("n_qubits", h)
        self.assertIn("targets", h)
        self.assertIn("measured", h)
        self.assertIn("success", h)
        self.assertIn("iterations", h)
        self.assertIn("optimal", h)

    def test_probabilities_for_bar_chart(self):
        """진폭에서 바 차트 렌더링 데이터 생성."""
        state = grover_run_full(4, [7])
        if state.amplitude_history:
            last_snap = state.amplitude_history[-1]
            probs = get_probabilities(last_snap.amplitudes)
            self.assertEqual(len(probs), 16)
            for p in probs:
                self.assertGreaterEqual(p, 0.0)
                self.assertLessEqual(p, 1.0)


# ── Phase Indicator 테스트 ───────────────────────────

class TestPhaseIndicator(unittest.TestCase):
    """Phase indicator 렌더링 데이터."""

    def test_phase_ordering(self):
        """GroverPhase enum 값 순서."""
        phases = list(GroverPhase)
        for i in range(len(phases) - 1):
            self.assertLess(phases[i].value, phases[i + 1].value)

    def test_all_phases_have_description(self):
        """모든 phase에 설명 존재."""
        for phase in GroverPhase:
            desc = get_phase_description(phase)
            self.assertIsInstance(desc, str)
            self.assertGreater(len(desc), 0)

    def test_quantum_advantage_message(self):
        """양자 우위 설명 메시지 존재."""
        msg = get_quantum_advantage_message()
        self.assertIsInstance(msg, str)
        self.assertGreater(len(msg), 50)


# ── 수학적 정확성 테스트 ─────────────────────────────

class TestMathematicalCorrectness(unittest.TestCase):
    """Grover 알고리즘의 수학적 정확성."""

    def test_probability_evolution_4qubits(self):
        """4큐빗 1대상: 반복별 확률 이론값 비교."""
        n = 16
        targets = [7]
        amps = init_superposition(n)

        # θ = arcsin(√(M/N))
        theta = math.asin(math.sqrt(1 / n))

        for k in range(1, 4):
            amps = apply_oracle(amps, targets)
            amps = apply_diffusion(amps)
            prob = target_probability(amps, targets)
            # 이론값: sin²((2k+1)θ)
            expected = math.sin((2 * k + 1) * theta) ** 2
            self.assertAlmostEqual(prob, expected, places=8,
                                   msg=f"Iteration {k}: {prob} != {expected}")

    def test_probability_at_optimal(self):
        """최적 반복 시 확률이 ~1에 근접."""
        for n_qubits in [3, 4, 5]:
            n = 1 << n_qubits
            targets = [0]
            amps = init_superposition(n)
            k_opt = optimal_iterations(n, 1)

            for _ in range(k_opt):
                amps = apply_oracle(amps, targets)
                amps = apply_diffusion(amps)

            prob = target_probability(amps, targets)
            self.assertGreater(prob, 0.5,
                               f"{n_qubits} qubits: prob={prob}")

    def test_overiteration_decreases_probability(self):
        """최적 초과 반복: 확률 감소."""
        n = 16
        targets = [7]
        amps = init_superposition(n)
        k_opt = optimal_iterations(n, 1)

        # 최적까지 반복
        for _ in range(k_opt):
            amps = apply_oracle(amps, targets)
            amps = apply_diffusion(amps)
        prob_opt = target_probability(amps, targets)

        # 추가 반복
        for _ in range(k_opt):
            amps = apply_oracle(amps, targets)
            amps = apply_diffusion(amps)
        prob_over = target_probability(amps, targets)

        self.assertGreater(prob_opt, prob_over)


# ── grover_run_full 테스트 ───────────────────────────

class TestGroverRunFull(unittest.TestCase):
    """grover_run_full: 자동 실행."""

    def test_returns_done_state(self):
        """완료 상태 반환."""
        state = grover_run_full(4, [7])
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_measured_is_set(self):
        """측정 결과가 설정됨."""
        state = grover_run_full(4, [7])
        self.assertIsNotNone(state.measured)
        self.assertGreaterEqual(state.measured, 0)
        self.assertLess(state.measured, 16)

    def test_statistics_updated(self):
        """통계가 업데이트됨."""
        state = grover_run_full(4, [7])
        self.assertEqual(state.total_searches, 1)
        self.assertGreater(state.total_oracle_calls, 0)

    def test_various_sizes(self):
        """다양한 크기에서 실행."""
        for n in [2, 3, 4, 5]:
            target = (1 << n) - 1
            state = grover_run_full(n, [target])
            self.assertEqual(state.phase, GroverPhase.DONE)
            self.assertIsNotNone(state.measured)


if __name__ == "__main__":
    unittest.main()
