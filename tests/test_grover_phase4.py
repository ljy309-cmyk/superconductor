"""Grover's Search Phase 4 — 포괄적 테스트.

Edge case, boundary, state transition, large qubit, mathematical correctness,
reset/replay, compare/auto mode를 커버합니다.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum.grover_search_engine import (
    MAX_QUBITS,
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


# ── 1. Edge Cases & Boundary Values ─────────────────────

class TestQubitBoundaries(unittest.TestCase):
    """큐빗 수 경계값 테스트."""

    def test_n_qubits_exactly_at_max(self):
        state = GroverState(n_qubits=MAX_QUBITS, targets=[0])
        grover_step(state)  # INPUT
        self.assertEqual(state.phase, GroverPhase.INIT_SUPERPOSITION)

    def test_n_qubits_over_max(self):
        state = GroverState(n_qubits=MAX_QUBITS + 1, targets=[0])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_n_qubits_zero(self):
        state = GroverState(n_qubits=0, targets=[0])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_n_qubits_negative(self):
        state = GroverState(n_qubits=-5, targets=[0])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_n_qubits_1_minimal(self):
        """1큐비트: 2개 상태에서 탐색."""
        state = GroverState(n_qubits=1, targets=[0])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.INIT_SUPERPOSITION)
        grover_step(state)
        self.assertEqual(len(state.amplitudes), 2)


class TestTargetBoundaries(unittest.TestCase):
    """대상 인덱스 경계값 테스트."""

    def test_target_zero(self):
        state = GroverState(n_qubits=3, targets=[0])
        grover_step(state)
        self.assertEqual(state.targets, [0])
        self.assertEqual(state.phase, GroverPhase.INIT_SUPERPOSITION)

    def test_target_last_state(self):
        n = 3
        last = (1 << n) - 1
        state = GroverState(n_qubits=n, targets=[last])
        grover_step(state)
        self.assertEqual(state.targets, [last])

    def test_target_out_of_range(self):
        state = GroverState(n_qubits=3, targets=[100])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_target_negative(self):
        state = GroverState(n_qubits=3, targets=[-1])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_target_mixed_valid_invalid(self):
        state = GroverState(n_qubits=3, targets=[-1, 5, 100, 2])
        grover_step(state)
        self.assertEqual(sorted(state.targets), [2, 5])
        self.assertEqual(state.phase, GroverPhase.INIT_SUPERPOSITION)

    def test_duplicate_targets(self):
        state = GroverState(n_qubits=3, targets=[5, 5, 5])
        grover_step(state)
        # 중복 허용 - 유효한 인덱스이므로 통과
        self.assertEqual(state.phase, GroverPhase.INIT_SUPERPOSITION)

    def test_empty_targets(self):
        state = GroverState(n_qubits=3, targets=[])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_all_states_as_targets(self):
        n = 3
        n_states = 1 << n
        state = GroverState(n_qubits=n, targets=list(range(n_states)))
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.INIT_SUPERPOSITION)
        self.assertEqual(len(state.targets), n_states)

    def test_half_states_as_targets(self):
        n = 4
        half = (1 << n) // 2
        state = GroverState(n_qubits=n, targets=list(range(half)))
        grover_step(state)
        self.assertEqual(len(state.targets), half)


class TestOptimalIterationsBoundaries(unittest.TestCase):
    """optimal_iterations 경계값 테스트."""

    def test_n_targets_equals_n_states(self):
        result = optimal_iterations(8, 8)
        self.assertEqual(result, 1)

    def test_n_targets_greater_than_n_states(self):
        result = optimal_iterations(8, 100)
        self.assertEqual(result, 1)

    def test_n_targets_zero(self):
        result = optimal_iterations(8, 0)
        self.assertEqual(result, 1)

    def test_n_targets_negative(self):
        result = optimal_iterations(8, -5)
        self.assertEqual(result, 1)

    def test_n_states_1_single(self):
        result = optimal_iterations(1, 1)
        self.assertEqual(result, 1)

    def test_formula_precision_large_n(self):
        """큰 N에서 공식 정확도."""
        # N=1024, M=1: pi/4 * sqrt(1024) ≈ 25.13 → 25
        result = optimal_iterations(1024, 1)
        expected = int(math.pi / 4 * math.sqrt(1024))
        self.assertEqual(result, expected)

    def test_many_targets_reduces_iterations(self):
        # M 증가 → 반복 횟수 감소
        iter_1 = optimal_iterations(256, 1)
        iter_4 = optimal_iterations(256, 4)
        iter_16 = optimal_iterations(256, 16)
        self.assertGreaterEqual(iter_1, iter_4)
        self.assertGreaterEqual(iter_4, iter_16)


# ── 2. Phase Transition Tests ────────────────────────────

class TestPhaseTransitions(unittest.TestCase):
    """상태 머신 전이 검증."""

    def _advance_to(self, state, target_phase, max_steps=50):
        for _ in range(max_steps):
            if state.phase == target_phase:
                return True
            grover_step(state)
        return state.phase == target_phase

    def test_full_success_path(self):
        """INPUT → INIT → ORACLE → DIFF → ITERATE → MEASURE → SUCCESS."""
        state = GroverState(n_qubits=2, targets=[0])
        phases_seen = [state.phase]
        for _ in range(50):
            grover_step(state)
            phases_seen.append(state.phase)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL,
                               GroverPhase.DONE):
                break
        # Must have passed through core phases
        self.assertIn(GroverPhase.INIT_SUPERPOSITION, phases_seen)
        self.assertIn(GroverPhase.ORACLE, phases_seen)
        self.assertIn(GroverPhase.DIFFUSION, phases_seen)
        self.assertIn(GroverPhase.MEASURE, phases_seen)

    def test_input_to_done_invalid_qubits(self):
        state = GroverState(n_qubits=0, targets=[0])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_input_to_done_no_valid_targets(self):
        state = GroverState(n_qubits=3, targets=[100, 200])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_iterate_goes_to_oracle_if_not_optimal(self):
        """반복 횟수가 최적에 미달하면 ORACLE로 돌아감."""
        state = GroverState(n_qubits=5, targets=[10])
        self._advance_to(state, GroverPhase.ITERATE)
        # 5큐빗은 opt_iter > 1이므로 첫 ITERATE에서 ORACLE로
        if state.current_iteration < state.optimal_iterations:
            self.assertEqual(state.phase, GroverPhase.ITERATE)
            grover_step(state)
            self.assertEqual(state.phase, GroverPhase.ORACLE)

    def test_iterate_goes_to_measure_at_optimal(self):
        """최적 반복에 도달하면 MEASURE로 전이."""
        state = GroverState(n_qubits=3, targets=[5])
        # 3큐빗, 1타겟: opt = floor(pi/4*sqrt(8)) = 2
        reached = self._advance_to(state, GroverPhase.MEASURE)
        self.assertTrue(reached)

    def test_success_then_noop(self):
        """SUCCESS 상태에서 step을 해도 변화 없음."""
        state = GroverState(n_qubits=2, targets=[0])
        for _ in range(50):
            grover_step(state)
            if state.phase == GroverPhase.SUCCESS:
                break
        if state.phase == GroverPhase.SUCCESS:
            grover_step(state)
            self.assertEqual(state.phase, GroverPhase.SUCCESS)

    def test_fail_then_noop(self):
        """FAIL 상태에서 step을 해도 변화 없음."""
        state = GroverState(n_qubits=2, targets=[0])
        for _ in range(50):
            grover_step(state)
            if state.phase == GroverPhase.FAIL:
                break
        if state.phase == GroverPhase.FAIL:
            grover_step(state)
            self.assertEqual(state.phase, GroverPhase.FAIL)

    def test_done_then_noop(self):
        """DONE 상태에서 step을 해도 변화 없음."""
        state = GroverState(n_qubits=0, targets=[0])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_no_phase_skip(self):
        """INIT_SUPERPOSITION 이후 반드시 ORACLE 다음."""
        state = GroverState(n_qubits=3, targets=[5])
        grover_step(state)  # INPUT → INIT_SUPERPOSITION
        grover_step(state)  # INIT_SUPERPOSITION → ORACLE
        self.assertEqual(state.phase, GroverPhase.ORACLE)
        grover_step(state)  # ORACLE → DIFFUSION
        self.assertEqual(state.phase, GroverPhase.DIFFUSION)
        grover_step(state)  # DIFFUSION → ITERATE
        self.assertEqual(state.phase, GroverPhase.ITERATE)


class TestIterationExactBoundary(unittest.TestCase):
    """반복 횟수 정확한 경계 테스트."""

    def test_iteration_equals_optimal_goes_to_measure(self):
        """current_iteration == optimal_iterations → MEASURE."""
        state = GroverState(n_qubits=3, targets=[5])
        # Run until just before measure
        for _ in range(100):
            grover_step(state)
            if state.phase == GroverPhase.MEASURE:
                break
        self.assertEqual(state.phase, GroverPhase.MEASURE)
        self.assertGreaterEqual(state.current_iteration,
                                state.optimal_iterations)

    def test_max_iterations_reached(self):
        """max_iterations에 도달하면 MEASURE."""
        state = GroverState(n_qubits=5, targets=[10])
        # Manually set iteration near max to force the branch
        grover_step(state)  # INPUT → INIT_SUPERPOSITION
        grover_step(state)  # INIT_SUPERPOSITION → ORACLE
        state.current_iteration = state.max_iterations
        state.phase = GroverPhase.ITERATE
        grover_step(state)
        # optimal or max reached → MEASURE
        self.assertEqual(state.phase, GroverPhase.MEASURE)


# ── 3. Large Qubit Scenarios ────────────────────────────

class TestLargeQubits(unittest.TestCase):
    """대규모 큐비트 시나리오."""

    def test_8_qubits_256_states(self):
        state = grover_run_full(8, [42])
        self.assertEqual(state.n_qubits, 8)
        self.assertIsNotNone(state.measured)
        self.assertGreaterEqual(len(state.search_history), 1)

    def test_9_qubits_512_states(self):
        state = grover_run_full(9, [100])
        self.assertEqual(state.n_qubits, 9)
        self.assertIsNotNone(state.measured)

    def test_10_qubits_at_max(self):
        state = grover_run_full(10, [500])
        self.assertEqual(state.n_qubits, 10)
        self.assertIsNotNone(state.measured)

    def test_large_n_amplitude_count(self):
        state = GroverState(n_qubits=8, targets=[42])
        grover_step(state)  # INPUT
        grover_step(state)  # INIT_SUPERPOSITION
        self.assertEqual(len(state.amplitudes), 256)

    def test_large_n_normalization(self):
        state = GroverState(n_qubits=8, targets=[42])
        grover_step(state)
        grover_step(state)
        total = sum(a * a for a in state.amplitudes)
        self.assertAlmostEqual(total, 1.0, places=10)

    def test_large_n_oracle_correct(self):
        state = GroverState(n_qubits=8, targets=[42])
        grover_step(state)
        grover_step(state)
        before = state.amplitudes[42]
        grover_step(state)  # ORACLE
        after = state.amplitudes[42]
        self.assertAlmostEqual(after, -before, places=10)

    def test_large_n_search_success_rate(self):
        """큰 N에서도 높은 성공률."""
        successes = 0
        trials = 10
        for _ in range(trials):
            state = grover_run_full(6, [30])
            if state.measured == 30:
                successes += 1
        # Grover는 ~97% 이상 성공해야 함
        self.assertGreaterEqual(successes, 7)


# ── 4. Mathematical Correctness ──────────────────────────

class TestNormalizationPreservation(unittest.TestCase):
    """반복 과정에서 정규화 보존 검증."""

    def test_normalization_after_oracle(self):
        amps = init_superposition(16)
        amps = apply_oracle(amps, [3])
        total = sum(a * a for a in amps)
        self.assertAlmostEqual(total, 1.0, places=12)

    def test_normalization_after_diffusion(self):
        amps = init_superposition(16)
        amps = apply_oracle(amps, [3])
        amps = apply_diffusion(amps)
        total = sum(a * a for a in amps)
        self.assertAlmostEqual(total, 1.0, places=12)

    def test_normalization_over_10_iterations(self):
        """10회 반복 후에도 정규화 유지."""
        amps = init_superposition(64)
        targets = [20]
        for _ in range(10):
            amps = apply_oracle(amps, targets)
            amps = apply_diffusion(amps)
        total = sum(a * a for a in amps)
        self.assertAlmostEqual(total, 1.0, places=8)

    def test_normalization_many_targets(self):
        amps = init_superposition(32)
        targets = [0, 5, 10, 15, 20, 25, 30]
        for _ in range(5):
            amps = apply_oracle(amps, targets)
            amps = apply_diffusion(amps)
        total = sum(a * a for a in amps)
        self.assertAlmostEqual(total, 1.0, places=8)


class TestProbabilityBounds(unittest.TestCase):
    """확률이 항상 [0, 1] 범위인지 검증."""

    def test_all_probabilities_nonnegative(self):
        state = GroverState(n_qubits=4, targets=[7])
        for _ in range(30):
            grover_step(state)
            if state.amplitudes:
                probs = get_probabilities(state.amplitudes)
                for p in probs:
                    self.assertGreaterEqual(p, 0.0)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL,
                               GroverPhase.DONE):
                break

    def test_target_prob_in_range(self):
        state = GroverState(n_qubits=4, targets=[7])
        for _ in range(30):
            grover_step(state)
            if state.amplitudes:
                tp = target_probability(state.amplitudes, state.targets)
                self.assertGreaterEqual(tp, 0.0)
                self.assertLessEqual(tp, 1.0 + 1e-10)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL,
                               GroverPhase.DONE):
                break

    def test_probabilities_sum_to_one(self):
        state = GroverState(n_qubits=4, targets=[7])
        for _ in range(30):
            grover_step(state)
            if state.amplitudes:
                probs = get_probabilities(state.amplitudes)
                self.assertAlmostEqual(sum(probs), 1.0, places=8)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL,
                               GroverPhase.DONE):
                break


class TestProbabilityEvolution(unittest.TestCase):
    """확률 진화 패턴 검증."""

    def test_initial_uniform_probability(self):
        amps = init_superposition(16)
        probs = get_probabilities(amps)
        expected = 1.0 / 16
        for p in probs:
            self.assertAlmostEqual(p, expected, places=12)

    def test_first_iteration_increases_target_prob(self):
        """첫 반복 후 목표 확률 증가."""
        amps = init_superposition(16)
        initial_prob = target_probability(amps, [5])
        amps = apply_oracle(amps, [5])
        amps = apply_diffusion(amps)
        after_prob = target_probability(amps, [5])
        self.assertGreater(after_prob, initial_prob)

    def test_oscillation_pattern(self):
        """최적 이후 반복하면 확률이 감소 (진동)."""
        n_states = 64
        targets = [30]
        opt = optimal_iterations(n_states, 1)
        amps = init_superposition(n_states)

        # 최적까지 반복
        for _ in range(opt):
            amps = apply_oracle(amps, targets)
            amps = apply_diffusion(amps)
        peak_prob = target_probability(amps, targets)

        # 추가 반복
        for _ in range(opt):
            amps = apply_oracle(amps, targets)
            amps = apply_diffusion(amps)
        after_prob = target_probability(amps, targets)

        # 진동: 최적 이후 확률 감소
        self.assertLess(after_prob, peak_prob)

    def test_multiple_targets_equal_probability(self):
        """다중 타겟은 동일한 확률을 가짐."""
        amps = init_superposition(16)
        targets = [2, 7, 11]
        for _ in range(3):
            amps = apply_oracle(amps, targets)
            amps = apply_diffusion(amps)
        probs = get_probabilities(amps)
        target_probs = [probs[t] for t in targets]
        for tp in target_probs:
            self.assertAlmostEqual(tp, target_probs[0], places=10)

    def test_sin_squared_formula(self):
        """P(target) ≈ sin²((2k+1)θ) 공식 검증."""
        n_states = 64
        n_targets = 1
        theta = math.asin(math.sqrt(n_targets / n_states))
        amps = init_superposition(n_states)
        targets = [30]

        for k in range(1, 6):
            amps = apply_oracle(amps, targets)
            amps = apply_diffusion(amps)
            actual = target_probability(amps, targets)
            expected = math.sin((2 * k + 1) * theta) ** 2
            self.assertAlmostEqual(actual, expected, places=6,
                                   msg=f"Mismatch at iteration {k}")


class TestMeasureEdgeCases(unittest.TestCase):
    """measure() 함수 특수 경우."""

    def test_measure_deterministic_state(self):
        """단일 상태에 모든 확률."""
        amps = [0.0] * 8
        amps[3] = 1.0
        result = measure(amps)
        self.assertEqual(result, 3)

    def test_measure_zero_amplitudes(self):
        """모든 진폭이 0인 경우."""
        amps = [0.0] * 8
        result = measure(amps)
        self.assertIn(result, range(8))

    def test_measure_two_equal_states(self):
        """두 상태에만 확률이 집중."""
        amps = [0.0] * 8
        amps[2] = 1 / math.sqrt(2)
        amps[5] = 1 / math.sqrt(2)
        results = {measure(amps) for _ in range(100)}
        self.assertIn(2, results)
        self.assertIn(5, results)

    def test_measure_returns_valid_index(self):
        amps = init_superposition(16)
        for _ in range(50):
            result = measure(amps)
            self.assertIn(result, range(16))


# ── 5. Multi-Target Scenarios ────────────────────────────

class TestMultiTargetScenarios(unittest.TestCase):
    """다중 타겟 시나리오."""

    def test_many_targets_6(self):
        """6개 이상 타겟 (메시지 truncation 포함)."""
        targets = [0, 1, 2, 3, 4, 5, 6, 7]
        state = GroverState(n_qubits=4, targets=targets)
        grover_step(state)  # INPUT
        grover_step(state)  # INIT_SUPERPOSITION
        grover_step(state)  # ORACLE
        # 메시지에 "..." 포함 확인
        self.assertIn("...", state.step_message)

    def test_5_targets_no_truncation(self):
        targets = [0, 1, 2, 3, 4]
        state = GroverState(n_qubits=4, targets=targets)
        grover_step(state)
        grover_step(state)
        grover_step(state)
        self.assertNotIn("...", state.step_message)

    def test_all_targets_fast_convergence(self):
        """모든 상태가 타겟이면 즉시 성공."""
        n = 3
        targets = list(range(1 << n))
        state = grover_run_full(n, targets)
        self.assertIsNotNone(state.measured)
        self.assertTrue(state.measured_is_target or
                        state.phase == GroverPhase.DONE)

    def test_half_targets_success(self):
        n = 4
        half = list(range((1 << n) // 2))
        state = grover_run_full(n, half)
        self.assertIsNotNone(state.measured)

    def test_multi_target_oracle_flips_all(self):
        amps = init_superposition(8)
        targets = [1, 3, 5, 7]
        result = apply_oracle(amps, targets)
        for t in targets:
            self.assertAlmostEqual(result[t], -amps[t])
        for i in [0, 2, 4, 6]:
            self.assertAlmostEqual(result[i], amps[i])


# ── 6. Reset/Replay Scenarios ───────────────────────────

class TestResetDuringExecution(unittest.TestCase):
    """실행 중 리셋 테스트."""

    def test_reset_during_oracle(self):
        state = GroverState(n_qubits=3, targets=[5])
        grover_step(state)  # INPUT
        grover_step(state)  # INIT_SUPERPOSITION
        grover_step(state)  # ORACLE
        self.assertEqual(state.phase, GroverPhase.DIFFUSION)
        reset_state(state)
        self.assertEqual(state.phase, GroverPhase.INPUT)
        self.assertEqual(len(state.amplitudes), 0)

    def test_reset_during_diffusion(self):
        state = GroverState(n_qubits=3, targets=[5])
        for _ in range(4):
            grover_step(state)
        reset_state(state)
        self.assertEqual(state.phase, GroverPhase.INPUT)
        self.assertIsNone(state.measured)

    def test_reset_preserves_history(self):
        state = grover_run_full(3, [5])
        self.assertGreaterEqual(len(state.search_history), 1)
        history_len = len(state.search_history)
        reset_state(state)
        self.assertEqual(len(state.search_history), history_len)

    def test_reset_clears_amplitudes(self):
        state = grover_run_full(3, [5])
        self.assertTrue(len(state.amplitudes) > 0 or state.phase == GroverPhase.DONE)
        reset_state(state)
        self.assertEqual(len(state.amplitudes), 0)

    def test_reset_with_new_qubits(self):
        state = GroverState(n_qubits=3, targets=[5])
        grover_step(state)
        grover_step(state)
        reset_state(state, n_qubits=5)
        self.assertEqual(state.n_qubits, 5)
        self.assertEqual(state.phase, GroverPhase.INPUT)

    def test_reset_with_new_targets(self):
        state = GroverState(n_qubits=3, targets=[5])
        grover_step(state)
        grover_step(state)
        reset_state(state, targets=[1, 2, 3])
        self.assertEqual(state.targets, [1, 2, 3])

    def test_reset_only_qubits(self):
        state = GroverState(n_qubits=3, targets=[5])
        reset_state(state, n_qubits=4)
        self.assertEqual(state.n_qubits, 4)
        self.assertEqual(state.targets, [5])

    def test_reset_only_targets(self):
        state = GroverState(n_qubits=3, targets=[5])
        reset_state(state, targets=[1])
        self.assertEqual(state.n_qubits, 3)
        self.assertEqual(state.targets, [1])

    def test_multiple_resets(self):
        state = GroverState(n_qubits=3, targets=[5])
        for i in range(5):
            grover_step(state)
            grover_step(state)
            reset_state(state)
            self.assertEqual(state.phase, GroverPhase.INPUT)

    def test_reset_clears_comparison(self):
        state = GroverState(n_qubits=3, targets=[5])
        grover_step(state)
        grover_step(state)
        self.assertIsNotNone(state.comparison)
        reset_state(state)
        self.assertIsNone(state.comparison)


class TestHistoryAccumulation(unittest.TestCase):
    """히스토리 누적 검증."""

    def test_history_grows_per_search(self):
        state = GroverState(n_qubits=3, targets=[5])
        # 첫 번째 탐색
        for _ in range(50):
            grover_step(state)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL):
                break
        self.assertEqual(len(state.search_history), 1)

        # 리셋 후 두 번째 탐색
        reset_state(state)
        grover_step(state)
        for _ in range(50):
            grover_step(state)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL):
                break
        self.assertEqual(len(state.search_history), 2)

    def test_history_entries_complete(self):
        state = grover_run_full(3, [5])
        self.assertGreaterEqual(len(state.search_history), 1)
        entry = state.search_history[0]
        required_keys = ["n_qubits", "targets", "measured", "success",
                         "iterations", "optimal", "target_prob"]
        for key in required_keys:
            self.assertIn(key, entry, f"Missing key: {key}")

    def test_history_target_prob_is_float(self):
        state = grover_run_full(3, [5])
        for entry in state.search_history:
            self.assertIsInstance(entry["target_prob"], float)
            self.assertGreaterEqual(entry["target_prob"], 0.0)
            self.assertLessEqual(entry["target_prob"], 1.0 + 1e-10)


# ── 7. Compare/Auto Mode Data ───────────────────────────

class TestComputeComparison(unittest.TestCase):
    """compute_comparison 함수 검증."""

    def test_comparison_basic(self):
        comp = compute_comparison(16, 1)
        self.assertEqual(comp.database_size, 16)
        self.assertEqual(comp.n_targets, 1)
        self.assertEqual(comp.classical_expected, 16.0)
        self.assertGreater(comp.speedup_ratio, 1.0)

    def test_comparison_many_targets(self):
        comp = compute_comparison(64, 8)
        self.assertEqual(comp.classical_expected, 8.0)
        self.assertGreater(comp.speedup_ratio, 0)

    def test_comparison_speedup_increases_with_n(self):
        """N 증가 시 speedup도 증가."""
        s1 = compute_comparison(16, 1)
        s2 = compute_comparison(256, 1)
        s3 = compute_comparison(1024, 1)
        self.assertLess(s1.speedup_ratio, s2.speedup_ratio)
        self.assertLess(s2.speedup_ratio, s3.speedup_ratio)

    def test_comparison_zero_targets(self):
        comp = compute_comparison(16, 0)
        self.assertEqual(comp.quantum_iterations, 1)

    def test_comparison_all_targets(self):
        comp = compute_comparison(16, 16)
        self.assertEqual(comp.classical_expected, 1.0)
        self.assertEqual(comp.quantum_iterations, 1)


class TestGroverRunFull(unittest.TestCase):
    """grover_run_full 자동 실행 검증."""

    def test_run_full_completes(self):
        state = grover_run_full(3, [5])
        self.assertIn(state.phase, (GroverPhase.DONE, GroverPhase.FAIL))

    def test_run_full_measures(self):
        state = grover_run_full(4, [7])
        self.assertIsNotNone(state.measured)

    def test_run_full_invalid_input(self):
        state = grover_run_full(0, [0])
        self.assertEqual(state.phase, GroverPhase.DONE)

    def test_run_full_max_steps_limit(self):
        """max_steps에 도달해도 크래시 없음."""
        state = grover_run_full(10, [500])
        self.assertIsNotNone(state.measured)

    def test_run_full_success_transitions_to_done(self):
        state = grover_run_full(3, [5])
        if state.measured == 5:
            self.assertEqual(state.phase, GroverPhase.DONE)


# ── 8. Visualization Data ───────────────────────────────

class TestAmplitudeHistory(unittest.TestCase):
    """amplitude_history 검증."""

    def test_initial_snapshot_recorded(self):
        state = GroverState(n_qubits=3, targets=[5])
        grover_step(state)
        grover_step(state)  # INIT → ORACLE (snapshot at init)
        self.assertGreaterEqual(len(state.amplitude_history), 1)
        self.assertEqual(state.amplitude_history[0].iteration, 0)

    def test_snapshot_after_diffusion(self):
        state = GroverState(n_qubits=3, targets=[5])
        for _ in range(4):
            grover_step(state)
        # After diffusion, snapshot recorded
        self.assertGreaterEqual(len(state.amplitude_history), 2)

    def test_snapshot_amplitudes_length(self):
        state = GroverState(n_qubits=3, targets=[5])
        grover_step(state)
        grover_step(state)
        snap = state.amplitude_history[0]
        self.assertEqual(len(snap.amplitudes), 8)

    def test_target_prob_history_grows(self):
        state = GroverState(n_qubits=3, targets=[5])
        for _ in range(10):
            grover_step(state)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL,
                               GroverPhase.DONE):
                break
        self.assertGreaterEqual(len(state.target_prob_history), 2)

    def test_prob_history_values_in_range(self):
        state = GroverState(n_qubits=3, targets=[5])
        for _ in range(20):
            grover_step(state)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL,
                               GroverPhase.DONE):
                break
        for p in state.target_prob_history:
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0 + 1e-10)


class TestPhaseDescriptions(unittest.TestCase):
    """모든 단계의 설명이 존재하는지 검증."""

    def test_all_phases_have_descriptions(self):
        for phase in GroverPhase:
            desc = get_phase_description(phase)
            self.assertIsInstance(desc, str)
            self.assertTrue(len(desc) > 0)

    def test_quantum_advantage_message(self):
        msg = get_quantum_advantage_message()
        self.assertIsInstance(msg, str)
        self.assertTrue(len(msg) > 0)


# ── 9. Oracle Edge Cases ────────────────────────────────

class TestOracleEdgeCases(unittest.TestCase):
    """apply_oracle 특수 상황."""

    def test_oracle_no_targets(self):
        amps = init_superposition(8)
        result = apply_oracle(amps, [])
        self.assertEqual(amps, result)

    def test_oracle_out_of_range_target_ignored(self):
        amps = init_superposition(8)
        result = apply_oracle(amps, [100])
        self.assertEqual(amps, result)

    def test_oracle_all_targets(self):
        """모든 상태를 뒤집으면 → 전체 위상 반전 (동일한 확률)."""
        amps = init_superposition(8)
        targets = list(range(8))
        result = apply_oracle(amps, targets)
        for i in range(8):
            self.assertAlmostEqual(result[i], -amps[i])

    def test_oracle_preserves_normalization(self):
        amps = init_superposition(16)
        result = apply_oracle(amps, [3, 7, 12])
        total = sum(a * a for a in result)
        self.assertAlmostEqual(total, 1.0, places=12)

    def test_oracle_double_application_identity(self):
        """Oracle을 두 번 적용하면 원래 상태."""
        amps = init_superposition(8)
        targets = [3, 5]
        result1 = apply_oracle(amps, targets)
        result2 = apply_oracle(result1, targets)
        for i in range(8):
            self.assertAlmostEqual(result2[i], amps[i])


# ── 10. Diffusion Edge Cases ────────────────────────────

class TestDiffusionEdgeCases(unittest.TestCase):
    """apply_diffusion 특수 상황."""

    def test_diffusion_uniform_state_unchanged(self):
        """균등 상태에 diffusion → 변화 없음 (mean = each value)."""
        amps = init_superposition(8)
        result = apply_diffusion(amps)
        for i in range(8):
            self.assertAlmostEqual(result[i], amps[i], places=12)

    def test_diffusion_preserves_normalization(self):
        amps = [0.5, 0.5, -0.5, 0.5]
        result = apply_diffusion(amps)
        total = sum(a * a for a in result)
        total_before = sum(a * a for a in amps)
        self.assertAlmostEqual(total, total_before, places=10)

    def test_diffusion_single_state(self):
        """단일 상태 진폭 리스트."""
        amps = [1.0]
        result = apply_diffusion(amps)
        self.assertAlmostEqual(result[0], 1.0)


# ── 11. Statistics Tracking ─────────────────────────────

class TestStatisticsTracking(unittest.TestCase):
    """통계 필드 추적 검증."""

    def test_oracle_call_count(self):
        state = grover_run_full(3, [5])
        self.assertGreater(state.total_oracle_calls, 0)

    def test_search_count_increments(self):
        state = grover_run_full(3, [5])
        self.assertEqual(state.total_searches, 1)

    def test_successful_search_count(self):
        state = grover_run_full(3, [5])
        if state.measured == 5:
            self.assertEqual(state.successful_searches, 1)

    def test_multiple_runs_accumulate_stats(self):
        state = GroverState(n_qubits=3, targets=[5])
        for _ in range(50):
            grover_step(state)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL):
                break
        first_oracle_calls = state.total_oracle_calls
        reset_state(state)
        for _ in range(50):
            grover_step(state)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL):
                break
        # oracle calls accumulate (reset clears total_oracle_calls)
        # Reset sets total_oracle_calls = 0
        self.assertEqual(state.total_oracle_calls,
                         state.current_iteration)


# ── 12. Init Superposition Edge Cases ────────────────────

class TestInitSuperpositionEdgeCases(unittest.TestCase):
    """init_superposition 특수 상황."""

    def test_init_2_states(self):
        amps = init_superposition(2)
        self.assertEqual(len(amps), 2)
        self.assertAlmostEqual(amps[0], 1 / math.sqrt(2))

    def test_init_1024_states(self):
        amps = init_superposition(1024)
        self.assertEqual(len(amps), 1024)
        expected = 1 / math.sqrt(1024)
        self.assertAlmostEqual(amps[0], expected)

    def test_init_normalization(self):
        for n in [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]:
            amps = init_superposition(n)
            total = sum(a * a for a in amps)
            self.assertAlmostEqual(total, 1.0, places=10,
                                   msg=f"Failed for n={n}")


# ── 13. get_probabilities Edge Cases ─────────────────────

class TestGetProbabilitiesEdgeCases(unittest.TestCase):

    def test_empty_amplitudes(self):
        result = get_probabilities([])
        self.assertEqual(result, [])

    def test_negative_amplitudes(self):
        result = get_probabilities([-0.5, 0.5, -0.5, 0.5])
        for p in result:
            self.assertGreaterEqual(p, 0.0)

    def test_single_amplitude(self):
        result = get_probabilities([1.0])
        self.assertEqual(result, [1.0])


# ── 14. target_probability Edge Cases ────────────────────

class TestTargetProbabilityEdgeCases(unittest.TestCase):

    def test_empty_targets(self):
        amps = init_superposition(8)
        result = target_probability(amps, [])
        self.assertEqual(result, 0.0)

    def test_out_of_range_targets(self):
        amps = init_superposition(8)
        result = target_probability(amps, [100, -1])
        self.assertEqual(result, 0.0)

    def test_all_targets(self):
        amps = init_superposition(8)
        result = target_probability(amps, list(range(8)))
        self.assertAlmostEqual(result, 1.0, places=10)

    def test_mixed_valid_invalid_targets(self):
        amps = init_superposition(8)
        result = target_probability(amps, [3, 100, -1])
        expected = amps[3] ** 2
        self.assertAlmostEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
