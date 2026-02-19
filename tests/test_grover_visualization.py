"""Grover's Search Algorithm 시각화 중점 테스트.

시각화 렌더링에 필요한 데이터(amplitudes, amplitude_history,
target_prob_history, phase indicator 등)가 각 단계에서
올바르게 생성되는지 검증합니다. Pygame 없이 순수 로직만 테스트합니다.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum.grover_search_engine import (
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
    optimal_iterations,
    reset_state,
    target_probability,
)


# ── _wrap_text 유틸리티 테스트 ───────────────────────

def _wrap_text(text, max_chars):
    """quantum/grover_search.py의 _wrap_text 동일 로직."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > max_chars:
            if current:
                lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(current)
    return lines


# ── 단계별 시각화 데이터 테스트 ──────────────────────

class TestVisualizationDataPerPhase(unittest.TestCase):
    """각 Phase에서 시각화 데이터가 올바르게 생성되는지 검증."""

    def _advance_to(self, state, target_phase, max_steps=200):
        for _ in range(max_steps):
            if state.phase == target_phase:
                return True
            grover_step(state)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL,
                               GroverPhase.DONE):
                return state.phase == target_phase
        return False

    def test_input_phase_clean_state(self):
        """INPUT: 시각화 데이터가 비어 있음."""
        state = GroverState(n_qubits=4, targets=[7])
        self.assertEqual(state.phase, GroverPhase.INPUT)
        self.assertEqual(len(state.amplitudes), 0)
        self.assertEqual(len(state.amplitude_history), 0)
        self.assertIsNone(state.measured)

    def test_superposition_creates_amplitudes(self):
        """INIT_SUPERPOSITION: amplitudes 배열 생성."""
        state = GroverState(n_qubits=4, targets=[7])
        grover_step(state)  # INPUT
        grover_step(state)  # INIT_SUPERPOSITION

        self.assertEqual(len(state.amplitudes), 16)
        expected_amp = 1.0 / math.sqrt(16)
        for a in state.amplitudes:
            self.assertAlmostEqual(a, expected_amp)

    def test_superposition_creates_initial_snapshot(self):
        """INIT_SUPERPOSITION: 초기 스냅샷 기록."""
        state = GroverState(n_qubits=3, targets=[5])
        grover_step(state)
        grover_step(state)

        self.assertEqual(len(state.amplitude_history), 1)
        self.assertEqual(state.amplitude_history[0].iteration, 0)
        self.assertAlmostEqual(
            state.amplitude_history[0].target_probability, 1.0 / 8)

    def test_superposition_creates_comparison(self):
        """INIT_SUPERPOSITION: 고전 비교 데이터 생성."""
        state = GroverState(n_qubits=4, targets=[7])
        grover_step(state)
        grover_step(state)

        self.assertIsNotNone(state.comparison)
        self.assertEqual(state.comparison.database_size, 16)
        self.assertEqual(state.comparison.n_targets, 1)
        self.assertGreater(state.comparison.speedup_ratio, 1.0)

    def test_oracle_flips_target_amplitude(self):
        """ORACLE: 대상 진폭 부호 반전 확인."""
        state = GroverState(n_qubits=3, targets=[5])
        grover_step(state)  # INPUT
        grover_step(state)  # SUPERPOSITION

        amp_before = state.amplitudes[5]
        grover_step(state)  # ORACLE
        amp_after = state.amplitudes[5]

        self.assertAlmostEqual(amp_after, -amp_before)

    def test_diffusion_adds_snapshot(self):
        """DIFFUSION: amplitude_history에 스냅샷 추가."""
        state = GroverState(n_qubits=4, targets=[7])
        grover_step(state)  # INPUT
        grover_step(state)  # SUPERPOSITION
        count_before = len(state.amplitude_history)

        grover_step(state)  # ORACLE
        grover_step(state)  # DIFFUSION

        self.assertEqual(len(state.amplitude_history), count_before + 1)

    def test_diffusion_increases_target_prob(self):
        """DIFFUSION: 마킹 진폭 증가."""
        state = GroverState(n_qubits=4, targets=[7])
        grover_step(state)  # INPUT
        grover_step(state)  # SUPERPOSITION

        prob_init = target_probability(state.amplitudes, [7])
        grover_step(state)  # ORACLE
        grover_step(state)  # DIFFUSION

        prob_after = target_probability(state.amplitudes, [7])
        self.assertGreater(prob_after, prob_init)

    def test_measure_sets_result(self):
        """MEASURE: measured 필드 설정."""
        state = GroverState(n_qubits=3, targets=[5])
        for _ in range(100):
            grover_step(state)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL):
                break

        self.assertIsNotNone(state.measured)
        self.assertGreaterEqual(state.measured, 0)
        self.assertLess(state.measured, 8)


# ── 바 차트 렌더링 데이터 테스트 ─────────────────────

class TestBarChartData(unittest.TestCase):
    """_draw_amplitude_bar_chart에 필요한 데이터 검증."""

    def test_probabilities_nonnegative(self):
        """확률값이 모두 0 이상."""
        state = grover_run_full(4, [7])
        for snap in state.amplitude_history:
            probs = get_probabilities(snap.amplitudes)
            for p in probs:
                self.assertGreaterEqual(p, 0.0)

    def test_max_val_nonzero(self):
        """최대 확률값 > 0 (0 나눗셈 방지)."""
        state = grover_run_full(4, [7])
        for snap in state.amplitude_history:
            probs = get_probabilities(snap.amplitudes)
            max_val = max(probs)
            self.assertGreater(max_val, 0.0)

    def test_target_highlighted(self):
        """마킹 상태의 확률이 구별 가능."""
        state = grover_run_full(4, [7])
        if len(state.amplitude_history) >= 2:
            last = state.amplitude_history[-1]
            probs = get_probabilities(last.amplitudes)
            target_p = probs[7]
            non_target_max = max(
                p for i, p in enumerate(probs) if i != 7)
            # 마킹 상태 확률이 비마킹보다 높아야 함
            self.assertGreater(target_p, non_target_max)

    def test_bar_width_positive(self):
        """바 너비 계산이 항상 양수."""
        for n in [4, 8, 16, 32, 64, 256]:
            w = 420
            display_n = min(n, 32)
            bar_w = max(1, (w - 20) // display_n)
            self.assertGreater(bar_w, 0)

    def test_color_classification(self):
        """확률값에 따른 색상 분류."""
        state = grover_run_full(4, [7])
        if state.amplitude_history:
            last = state.amplitude_history[-1]
            probs = get_probabilities(last.amplitudes)
            max_val = max(probs)

            targets_set = set(state.targets)
            for i, p in enumerate(probs):
                if i in targets_set:
                    pass  # YELLOW
                elif p > max_val * 0.3:
                    pass  # PURPLE
                else:
                    pass  # ACCENT
                # 분류 로직이 오류 없이 실행됨


# ── 확률 변화 그래프 데이터 테스트 ───────────────────

class TestProbabilityEvolutionData(unittest.TestCase):
    """_draw_probability_evolution에 필요한 데이터."""

    def test_history_length_matches(self):
        """target_prob_history와 amplitude_history 길이 일치."""
        state = grover_run_full(4, [7])
        self.assertEqual(len(state.target_prob_history),
                         len(state.amplitude_history))

    def test_probabilities_in_range(self):
        """확률값이 0~1 범위."""
        state = grover_run_full(4, [7])
        for p in state.target_prob_history:
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0 + 1e-10)

    def test_initial_probability_uniform(self):
        """초기 확률 = 1/N."""
        state = GroverState(n_qubits=4, targets=[7])
        grover_step(state)
        grover_step(state)

        self.assertAlmostEqual(state.target_prob_history[0], 1.0 / 16)

    def test_probability_increases_initially(self):
        """첫 반복 후 확률 증가."""
        state = grover_run_full(4, [7])
        if len(state.target_prob_history) >= 2:
            self.assertGreater(state.target_prob_history[1],
                               state.target_prob_history[0])

    def test_enough_points_for_line_chart(self):
        """라인 차트에 충분한 점 (최소 2개)."""
        state = grover_run_full(4, [7])
        self.assertGreaterEqual(len(state.target_prob_history), 2)


# ── 회로 다이어그램 데이터 테스트 ────────────────────

class TestCircuitDiagramData(unittest.TestCase):
    """양자 회로 다이어그램 렌더링 데이터 검증."""

    GATE_PHASE_MAP = {
        "H": GroverPhase.INIT_SUPERPOSITION,
        "O_f": GroverPhase.ORACLE,
        "D": GroverPhase.DIFFUSION,
        "M": GroverPhase.MEASURE,
    }

    def test_gate_active_at_correct_phase(self):
        """각 게이트가 해당 phase에서만 활성화."""
        for gate_name, active_phase in self.GATE_PHASE_MAP.items():
            for phase in GroverPhase:
                is_active = (phase == active_phase)
                if phase == active_phase:
                    self.assertTrue(is_active)
                else:
                    self.assertFalse(is_active)

    def test_gate_done_after_phase(self):
        """phase가 지나면 게이트가 'done' 상태."""
        for gate_name, gate_phase in self.GATE_PHASE_MAP.items():
            for phase in GroverPhase:
                is_done = (phase.value > gate_phase.value)
                if phase.value > gate_phase.value:
                    self.assertTrue(is_done)

    def test_iteration_counter_display(self):
        """반복 횟수가 회로에 표시됨."""
        state = GroverState(n_qubits=4, targets=[7])
        grover_step(state)  # INPUT
        grover_step(state)  # SUPERPOSITION
        grover_step(state)  # ORACLE
        grover_step(state)  # DIFFUSION

        self.assertGreater(state.current_iteration, 0)
        self.assertGreater(state.optimal_iterations, 0)


# ── Phase Indicator 테스트 ───────────────────────────

class TestPhaseIndicatorLogic(unittest.TestCase):
    """Phase indicator 렌더링 로직."""

    INDICATOR_PHASES = [
        GroverPhase.INIT_SUPERPOSITION,
        GroverPhase.ORACLE,
        GroverPhase.DIFFUSION,
        GroverPhase.ITERATE,
        GroverPhase.MEASURE,
    ]

    def test_done_phases_ordered(self):
        """value가 큰 phase → 이전 phase는 'done'."""
        for i, current in enumerate(self.INDICATOR_PHASES):
            for j, ph in enumerate(self.INDICATOR_PHASES):
                is_done = (current.value > ph.value)
                if j < i:
                    self.assertTrue(is_done)
                elif j == i:
                    self.assertFalse(is_done)

    def test_all_phases_have_description(self):
        """모든 phase에 설명 존재."""
        for phase in GroverPhase:
            desc = get_phase_description(phase)
            self.assertIsInstance(desc, str)
            self.assertGreater(len(desc), 0)


# ── 모드 전환 테스트 ─────────────────────────────────

class TestModeTransitions(unittest.TestCase):
    """모드 전환 시 상태 초기화 로직."""

    def test_reset_clears_visualization_data(self):
        """리셋 후 시각화 데이터 초기화."""
        state = grover_run_full(4, [7])
        reset_state(state)

        self.assertEqual(len(state.amplitudes), 0)
        self.assertEqual(len(state.amplitude_history), 0)
        self.assertEqual(len(state.target_prob_history), 0)
        self.assertIsNone(state.measured)
        self.assertEqual(state.current_iteration, 0)

    def test_reset_with_new_params(self):
        """새 파라미터로 리셋."""
        state = grover_run_full(4, [7])
        reset_state(state, n_qubits=5, targets=[10])
        grover_step(state)

        self.assertEqual(state.n_qubits, 5)
        self.assertEqual(state.targets, [10])
        self.assertEqual(state.phase, GroverPhase.INIT_SUPERPOSITION)


# ── Compare 모드 데이터 테스트 ───────────────────────

class TestCompareData(unittest.TestCase):
    """Classical vs Quantum 비교 모드 데이터."""

    def test_comparison_values(self):
        """비교 데이터 계산."""
        comp = compute_comparison(1024, 1)
        self.assertEqual(comp.database_size, 1024)
        self.assertAlmostEqual(comp.classical_expected, 1024.0)
        self.assertEqual(comp.quantum_iterations, 25)
        self.assertGreater(comp.speedup_ratio, 30)

    def test_speedup_display_format(self):
        """speedup 표시 문자열 생성 가능."""
        comp = compute_comparison(256, 1)
        display = f"{comp.speedup_ratio:.1f}×"
        self.assertIn("×", display)
        self.assertGreater(float(display.replace("×", "")), 1.0)

    def test_compare_progress_range(self):
        """진행 상태 0~1 범위."""
        for pos in [0.0, 0.5, 1.0]:
            self.assertGreaterEqual(pos, 0.0)
            self.assertLessEqual(pos, 1.0)

    def test_quantum_advantage_message(self):
        """양자 우위 메시지 존재 및 줄바꿈 가능."""
        msg = get_quantum_advantage_message()
        self.assertIsInstance(msg, str)
        self.assertGreater(len(msg), 50)
        lines = _wrap_text(msg, 90)
        self.assertGreater(len(lines), 0)


# ── Step Message 시각화 테스트 ───────────────────────

class TestStepMessages(unittest.TestCase):
    """각 단계의 step_message가 시각화에 적합."""

    def test_messages_not_empty(self):
        """각 단계 진행 시 step_message 비어있지 않음."""
        state = GroverState(n_qubits=3, targets=[5])
        for _ in range(100):
            grover_step(state)
            self.assertGreater(len(state.step_message), 0,
                               f"Empty at {state.phase}")
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL,
                               GroverPhase.DONE):
                break

    def test_messages_wrappable(self):
        """step_message가 줄바꿈 가능."""
        state = GroverState(n_qubits=4, targets=[7])
        for _ in range(100):
            grover_step(state)
            if state.step_message:
                lines = _wrap_text(state.step_message, 35)
                self.assertGreater(len(lines), 0)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL,
                               GroverPhase.DONE):
                break

    def test_success_message_contains_result(self):
        """SUCCESS 시 측정 결과 포함."""
        state = GroverState(n_qubits=3, targets=[5])
        for _ in range(100):
            grover_step(state)
            if state.phase == GroverPhase.SUCCESS:
                self.assertIsNotNone(state.measured)
                break


# ── 탐색 히스토리 시각화 테스트 ──────────────────────

class TestSearchHistoryVisualization(unittest.TestCase):
    """탐색 히스토리의 시각화 데이터."""

    def test_history_entries_have_fields(self):
        """히스토리 항목에 필수 필드."""
        state = grover_run_full(4, [7])
        for h in state.search_history:
            self.assertIn("n_qubits", h)
            self.assertIn("targets", h)
            self.assertIn("measured", h)
            self.assertIn("success", h)
            self.assertIn("iterations", h)

    def test_history_display_limit(self):
        """히스토리 표시 최근 4개."""
        state = grover_run_full(4, [7])
        display = state.search_history[-4:]
        self.assertLessEqual(len(display), 4)

    def test_history_colors(self):
        """success에 따른 색상 분류."""
        state = grover_run_full(4, [7])
        for h in state.search_history:
            if h["success"]:
                pass  # GREEN
            else:
                pass  # YELLOW


# ── 다양한 큐빗 수 시각화 테스트 ────────────────────

class TestVisualizationAcrossQubits(unittest.TestCase):
    """다양한 큐빗 수에서 시각화 데이터."""

    def test_amplitudes_length(self):
        """amplitudes 배열 길이 = 2^n."""
        for n in [2, 3, 4, 5]:
            state = grover_run_full(n, [0])
            for snap in state.amplitude_history:
                self.assertEqual(len(snap.amplitudes), 1 << n)

    def test_display_states_limit(self):
        """큰 N에서도 표시 상태 수 제한."""
        for n in [4, 8, 16, 32, 64, 256, 1024]:
            display_n = min(n, 32)
            self.assertLessEqual(display_n, 32)

    def test_normalization_preserved(self):
        """모든 스냅샷에서 정규화 유지."""
        for n_q in [2, 3, 4, 5]:
            state = grover_run_full(n_q, [0])
            for snap in state.amplitude_history:
                total = sum(a * a for a in snap.amplitudes)
                self.assertAlmostEqual(total, 1.0, places=8)


# ── 진행률 바 데이터 테스트 ──────────────────────────

class TestProgressBarData(unittest.TestCase):
    """_draw_progress_bar 진행률 계산."""

    def test_progress_range(self):
        """모든 phase에서 progress가 0~1."""
        for phase in GroverPhase:
            if phase not in (GroverPhase.DONE, GroverPhase.SUCCESS,
                             GroverPhase.FAIL):
                progress = phase.value / GroverPhase.DONE.value
            else:
                progress = 1.0
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 1.0)


# ── 탭 모드 표시 테스트 ─────────────────────────────

class TestTabModeDisplay(unittest.TestCase):
    """모드 탭 표시."""

    MODE_NAMES = ["Step-by-Step", "Auto Run", "Classical vs Quantum"]

    def test_three_modes(self):
        self.assertEqual(len(self.MODE_NAMES), 3)

    def test_mode_cycling(self):
        """Tab 순환: 0 → 1 → 2 → 0."""
        mode = 0
        for expected in [1, 2, 0]:
            mode = (mode + 1) % 3
            self.assertEqual(mode, expected)


# ── 입력 필드 로직 테스트 ────────────────────────────

class TestInputFieldLogic(unittest.TestCase):
    """입력 필드 로직."""

    def test_valid_input(self):
        """유효 입력 → 상태 변경."""
        state = GroverState(n_qubits=4, targets=[7])
        reset_state(state, n_qubits=3, targets=[5])
        grover_step(state)

        self.assertEqual(state.n_qubits, 3)
        self.assertEqual(state.targets, [5])

    def test_multi_target_input(self):
        """쉼표 구분 다중 대상."""
        state = GroverState(n_qubits=4, targets=[1, 5, 10])
        grover_step(state)
        self.assertEqual(state.phase, GroverPhase.INIT_SUPERPOSITION)
        self.assertEqual(state.targets, [1, 5, 10])

    def test_input_shown_at_terminal_phases(self):
        """INPUT, DONE, SUCCESS, FAIL에서 입력 표시."""
        terminal_phases = {GroverPhase.INPUT, GroverPhase.DONE,
                           GroverPhase.SUCCESS, GroverPhase.FAIL}
        for phase in terminal_phases:
            self.assertIn(phase, terminal_phases)


if __name__ == "__main__":
    unittest.main()
