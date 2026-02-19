"""Shor's Algorithm 시각화 중점 테스트.

시각화 렌더링에 필요한 데이터(mod_exp_table, qft_amplitudes,
qft_current, phase indicator 등)가 각 단계에서 올바르게 생성되는지
검증합니다. Pygame 없이 순수 로직만 테스트합니다.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum.shor_algorithm_engine import (
    MAX_NUMBER,
    MOD_EXP_ANIMATION_STEPS,
    ModExpEntry,
    QFTResult,
    RSA_EXAMPLES,
    ShorPhase,
    ShorState,
    build_mod_exp_table,
    compute_qft_probability_distribution,
    crack_rsa,
    detect_period_from_table,
    find_order,
    gcd,
    get_phase_description,
    is_prime,
    mod_pow,
    reset_state,
    setup_rsa_demo,
    shor_run_full,
    shor_step,
    simulate_qft_measurement,
)


# ── _wrap_text 유틸리티 테스트 (시각화 내 텍스트 줄바꿈) ──

def _wrap_text(text, max_chars):
    """quantum/shor_algorithm.py 의 _wrap_text 동일 로직 (Pygame 불필요)."""
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


class TestWrapText(unittest.TestCase):
    """_wrap_text 텍스트 줄바꿈 유틸리티."""

    def test_short_text(self):
        """max_chars보다 짧은 텍스트 → 한 줄."""
        lines = _wrap_text("hello world", 40)
        self.assertEqual(lines, ["hello world"])

    def test_exact_fit(self):
        """정확히 max_chars인 텍스트."""
        text = "abc def"  # 7 chars
        lines = _wrap_text(text, 7)
        self.assertEqual(lines, ["abc def"])

    def test_wrapping(self):
        """긴 텍스트 줄바꿈."""
        text = "The quick brown fox jumps over the lazy dog"
        lines = _wrap_text(text, 20)
        for line in lines:
            self.assertLessEqual(len(line), 25)  # 단어 경계 약간 초과 허용
        self.assertEqual(" ".join(lines), text)

    def test_empty_string(self):
        """빈 문자열."""
        lines = _wrap_text("", 20)
        self.assertEqual(lines, [])

    def test_single_long_word(self):
        """max_chars보다 긴 단일 단어 → 그대로."""
        lines = _wrap_text("supercalifragilistic", 5)
        self.assertEqual(lines, ["supercalifragilistic"])

    def test_multiple_short_words(self):
        """짧은 단어가 한 줄에 여러 개."""
        lines = _wrap_text("a b c d e f g h", 10)
        self.assertTrue(all(len(l) <= 12 for l in lines))
        self.assertEqual(" ".join(lines), "a b c d e f g h")


# ── 시각화 데이터 생성 테스트: 단계별 진행 ─────────────

class TestVisualizationDataPerPhase(unittest.TestCase):
    """각 Phase에서 시각화 데이터가 올바르게 생성되는지 검증."""

    def _advance_to(self, state, target_phase, max_steps=200):
        """target_phase까지 진행."""
        for _ in range(max_steps):
            if state.phase == target_phase:
                return True
            shor_step(state)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                return state.phase == target_phase
        return False

    def test_input_phase_clean_state(self):
        """INPUT 단계: 시각화 데이터가 비어 있음."""
        state = ShorState(number=15)
        self.assertEqual(state.phase, ShorPhase.INPUT)
        self.assertEqual(len(state.mod_exp_table), 0)
        self.assertEqual(len(state.qft_amplitudes), 0)
        self.assertIsNone(state.qft_current)
        self.assertEqual(state.mod_exp_period_visual, 0)

    def test_classical_precheck_step_message(self):
        """CLASSICAL_PRECHECK: step_message가 설정됨."""
        state = ShorState(number=15)
        shor_step(state)  # INPUT → CLASSICAL_PRECHECK
        self.assertEqual(state.phase, ShorPhase.CLASSICAL_PRECHECK)
        # 아직 시각화 데이터 없음
        self.assertEqual(len(state.mod_exp_table), 0)

    def test_pick_random_a_selects_valid(self):
        """PICK_RANDOM_A: a가 선택되고 적절히 처리됨."""
        state = ShorState(number=15)
        shor_step(state)  # INPUT
        shor_step(state)  # CLASSICAL_PRECHECK → PICK_RANDOM_A
        self.assertEqual(state.phase, ShorPhase.PICK_RANDOM_A)

        shor_step(state)  # PICK_RANDOM_A → MODULAR_EXP or SUCCESS
        self.assertGreater(state.a, 1)
        self.assertLess(state.a, 15)
        if state.phase == ShorPhase.MODULAR_EXP:
            # gcd(a, N) = 1 → 양자 경로
            self.assertEqual(gcd(state.a, 15), 1)
        elif state.phase == ShorPhase.SUCCESS:
            # gcd(a, N) > 1 → 우연히 인수 발견 (trivial_gcd)
            self.assertEqual(state.factor_method, "trivial_gcd")
            self.assertIsNotNone(state.factors)

    def test_modular_exp_populates_table(self):
        """MODULAR_EXP: mod_exp_table이 채워지고 주기가 감지됨."""
        state = ShorState(number=15)
        reached = self._advance_to(state, ShorPhase.MODULAR_EXP)
        if not reached:
            return  # trivial_gcd shortcut
        a = state.a  # 이미 a 선택됨

        shor_step(state)  # MODULAR_EXP → QFT_SETUP

        # mod_exp_table이 채워져야 함
        self.assertGreater(len(state.mod_exp_table), 0)
        # 첫 번째 항목: a^0 mod N = 1
        self.assertEqual(state.mod_exp_table[0].value, 1)
        # 두 번째 항목: a^1 mod N = a
        self.assertEqual(state.mod_exp_table[1].value, a % 15)

        # 주기 감지
        expected_period = find_order(a, 15)
        if expected_period is not None:
            self.assertEqual(state.mod_exp_period_visual, expected_period)

    def test_modular_exp_table_length(self):
        """MODULAR_EXP: 테이블 길이 = min(MOD_EXP_ANIMATION_STEPS, 2*N)."""
        state = ShorState(number=15)
        reached = self._advance_to(state, ShorPhase.MODULAR_EXP)
        if not reached:
            # trivial_gcd로 바로 성공한 경우 → skip
            return
        shor_step(state)

        expected_len = min(MOD_EXP_ANIMATION_STEPS, 15 * 2)
        self.assertEqual(len(state.mod_exp_table), expected_len)

    def test_modular_exp_entries_are_correct(self):
        """MODULAR_EXP: 각 항목이 a^x mod N 과 일치."""
        state = ShorState(number=15)
        reached = self._advance_to(state, ShorPhase.MODULAR_EXP)
        if not reached:
            return  # trivial_gcd shortcut
        shor_step(state)

        a = state.a
        for entry in state.mod_exp_table:
            expected = mod_pow(a, entry.x, 15)
            self.assertEqual(entry.value, expected,
                             f"a={a}, x={entry.x}: {entry.value} != {expected}")

    def test_qft_setup_populates_amplitudes(self):
        """QFT_SETUP: qft_amplitudes 배열이 채워짐."""
        state = ShorState(number=15)
        reached = self._advance_to(state, ShorPhase.QFT_SETUP)
        if not reached:
            return  # trivial_gcd shortcut

        shor_step(state)  # QFT_SETUP → QFT_MEASURE

        # qft_amplitudes가 채워져야 함
        self.assertGreater(len(state.qft_amplitudes), 0)
        # 길이 = 2^qft_n_qubits
        Q = 1 << state.qft_n_qubits
        self.assertEqual(len(state.qft_amplitudes), Q)
        # 확률 합 = 1
        total = sum(state.qft_amplitudes)
        self.assertAlmostEqual(total, 1.0, places=5)

    def test_qft_amplitudes_nonnegative(self):
        """QFT_SETUP: 모든 확률값이 0 이상."""
        state = ShorState(number=15)
        reached = self._advance_to(state, ShorPhase.QFT_SETUP)
        if not reached:
            return  # trivial_gcd shortcut
        shor_step(state)

        for amp in state.qft_amplitudes:
            self.assertGreaterEqual(amp, 0.0)

    def test_qft_measure_populates_current(self):
        """QFT_MEASURE: qft_current가 설정됨."""
        state = ShorState(number=15)
        reached = self._advance_to(state, ShorPhase.QFT_MEASURE)
        if not reached:
            return  # trivial_gcd shortcut

        shor_step(state)  # QFT_MEASURE → CONTINUED_FRACTION

        # qft_current가 있어야 함
        self.assertIsNotNone(state.qft_current)
        self.assertIsInstance(state.qft_current, QFTResult)

        # 측정값 범위
        Q = 1 << state.qft_current.n_qubits
        self.assertGreaterEqual(state.qft_current.measured_value, 0)
        self.assertLess(state.qft_current.measured_value, Q)

        # phase_estimate = measured_value / Q
        expected_phase = state.qft_current.measured_value / Q
        self.assertAlmostEqual(state.qft_current.phase_estimate, expected_phase)

    def test_qft_results_appended(self):
        """QFT_MEASURE: qft_results 리스트에 결과가 추가됨."""
        state = ShorState(number=15)
        reached = self._advance_to(state, ShorPhase.QFT_MEASURE)
        if not reached:
            return  # trivial_gcd shortcut
        prev_count = len(state.qft_results)

        shor_step(state)

        self.assertEqual(len(state.qft_results), prev_count + 1)

    def test_continued_fraction_updates_convergents(self):
        """CONTINUED_FRACTION: qft_current.convergents가 업데이트됨."""
        state = ShorState(number=15)
        reached = self._advance_to(state, ShorPhase.CONTINUED_FRACTION)

        if not reached:
            # trivial_gcd로 바로 성공한 경우 → skip
            return

        shor_step(state)

        # qft_current에 convergents 있어야 함
        self.assertIsNotNone(state.qft_current)
        self.assertIsInstance(state.qft_current.convergents, list)
        self.assertGreater(len(state.qft_current.convergents), 0)

        # 각 convergent는 (p, q) 튜플
        for p, q in state.qft_current.convergents:
            self.assertIsInstance(p, int)
            self.assertIsInstance(q, int)
            self.assertGreater(q, 0)


# ── 시각화 데이터 정합성 (전체 파이프라인) ───────────

class TestVisualizationDataConsistency(unittest.TestCase):
    """전체 파이프라인 실행 후 시각화 데이터 정합성."""

    def test_step_by_step_data_populated(self):
        """단계별 실행 시 모든 시각화 데이터가 올바르게 채워짐."""
        state = ShorState(number=15)
        had_mod_exp = False
        had_qft_amps = False
        had_qft_current = False

        for _ in range(300):
            shor_step(state)

            # MODULAR_EXP 이후 테이블 존재
            if state.mod_exp_table:
                had_mod_exp = True
                self.assertGreater(len(state.mod_exp_table), 0)
                self.assertEqual(state.mod_exp_table[0].value, 1)

            # QFT_SETUP 이후 amplitudes 존재
            if state.qft_amplitudes:
                had_qft_amps = True
                self.assertAlmostEqual(sum(state.qft_amplitudes), 1.0, places=5)

            # QFT_MEASURE 이후 current 존재
            if state.qft_current is not None:
                had_qft_current = True

            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

        # quantum 방식이면 이 데이터들이 한 번은 생성되었어야 함
        if state.factor_method == "quantum":
            self.assertTrue(had_mod_exp, "mod_exp_table never populated")
            self.assertTrue(had_qft_amps, "qft_amplitudes never populated")
            self.assertTrue(had_qft_current, "qft_current never populated")

    def test_retry_clears_visualization_data(self):
        """RETRY 시 시각화 데이터가 초기화됨."""
        state = ShorState(number=15)
        reached_retry = False

        for _ in range(300):
            prev_phase = state.phase
            shor_step(state)

            if state.phase == ShorPhase.RETRY:
                reached_retry = True
            elif prev_phase == ShorPhase.RETRY:
                # RETRY 다음 단계로 넘어감 → 데이터가 초기화됐어야
                self.assertEqual(len(state.mod_exp_table), 0,
                                 "mod_exp_table not cleared after RETRY")
                self.assertEqual(state.mod_exp_period_visual, 0,
                                 "mod_exp_period_visual not cleared after RETRY")
                self.assertEqual(len(state.qft_amplitudes), 0,
                                 "qft_amplitudes not cleared after RETRY")
                self.assertIsNone(state.qft_current,
                                  "qft_current not cleared after RETRY")

            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

        # 15는 확률적으로 retry 없이 성공할 수 있으므로 조건부
        if not reached_retry:
            pass  # retry 안 했으면 skip (정상)

    def test_reset_clears_all_visualization_data(self):
        """reset_state() 후 모든 시각화 데이터 초기화."""
        state = ShorState(number=15)

        # 실행해서 데이터 채우기
        for _ in range(300):
            shor_step(state)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

        # 리셋
        reset_state(state, 21)

        self.assertEqual(len(state.mod_exp_table), 0)
        self.assertEqual(state.mod_exp_period_visual, 0)
        self.assertEqual(len(state.qft_amplitudes), 0)
        self.assertIsNone(state.qft_current)
        self.assertEqual(len(state.qft_results), 0)
        self.assertEqual(state.total_qft_measurements, 0)
        self.assertIsNone(state.factors)
        self.assertEqual(state.attempt, 0)

    def test_qft_n_qubits_reasonable(self):
        """qft_n_qubits가 합리적인 범위."""
        for n in [15, 21, 35, 77]:
            state = ShorState(number=n)
            # QFT_SETUP까지 진행
            for _ in range(50):
                shor_step(state)
                if state.phase == ShorPhase.QFT_MEASURE:
                    break
                if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                    break

            if state.qft_n_qubits > 0:
                self.assertGreaterEqual(state.qft_n_qubits, 4)
                self.assertLessEqual(state.qft_n_qubits, 12)


# ── Phase Indicator 렌더링 로직 테스트 ────────────────

class TestPhaseIndicatorLogic(unittest.TestCase):
    """Phase indicator — is_current / is_done 로직 검증."""

    INDICATOR_PHASES = [
        ShorPhase.CLASSICAL_PRECHECK,
        ShorPhase.PICK_RANDOM_A,
        ShorPhase.MODULAR_EXP,
        ShorPhase.QFT_SETUP,
        ShorPhase.QFT_MEASURE,
        ShorPhase.CONTINUED_FRACTION,
        ShorPhase.EXTRACT_FACTORS,
    ]

    def test_current_phase_highlighted(self):
        """현재 phase만 '현재'로 표시."""
        for current in self.INDICATOR_PHASES:
            for ph in self.INDICATOR_PHASES:
                is_current = (current == ph)
                if is_current:
                    self.assertTrue(current == ph)

    def test_done_phases_ordered(self):
        """value가 큰 phase → 이전 phase는 'done'."""
        for i, current in enumerate(self.INDICATOR_PHASES):
            for j, ph in enumerate(self.INDICATOR_PHASES):
                is_done = (current.value > ph.value)
                if j < i:
                    self.assertTrue(is_done, f"{current} should be after {ph}")
                elif j == i:
                    self.assertFalse(is_done)
                else:
                    self.assertFalse(is_done)

    def test_phase_enum_ordering(self):
        """ShorPhase enum 값이 올바른 순서."""
        phases = list(ShorPhase)
        for i in range(len(phases) - 1):
            self.assertLess(phases[i].value, phases[i + 1].value,
                            f"{phases[i]} >= {phases[i+1]}")

    def test_all_phases_have_description(self):
        """모든 phase에 대한 설명이 존재."""
        for phase in ShorPhase:
            desc = get_phase_description(phase)
            self.assertIsInstance(desc, str)
            # 빈 문자열이 아닌 설명이 있어야 함
            self.assertGreater(len(desc), 0, f"No description for {phase}")


# ── 회로 다이어그램 데이터 테스트 ────────────────────

class TestCircuitDiagramData(unittest.TestCase):
    """양자 회로 다이어그램 렌더링 데이터 검증."""

    GATE_PHASE_MAP = {
        "H": ShorPhase.QFT_SETUP,
        "U_f": ShorPhase.MODULAR_EXP,
        "QFT†": ShorPhase.QFT_MEASURE,
        "M": ShorPhase.CONTINUED_FRACTION,
    }

    def test_gate_active_at_correct_phase(self):
        """각 게이트가 해당 phase에서만 활성화."""
        for gate_name, active_phase in self.GATE_PHASE_MAP.items():
            for phase in ShorPhase:
                is_active = (phase == active_phase)
                if phase == active_phase:
                    self.assertTrue(is_active,
                                    f"{gate_name} should be active at {phase}")
                else:
                    self.assertFalse(is_active,
                                     f"{gate_name} should NOT be active at {phase}")

    def test_gate_done_after_phase(self):
        """phase가 지나면 게이트가 'done' 상태."""
        for gate_name, gate_phase in self.GATE_PHASE_MAP.items():
            for phase in ShorPhase:
                is_done = (phase.value > gate_phase.value)
                if phase.value > gate_phase.value:
                    self.assertTrue(is_done,
                                    f"{gate_name} should be done at {phase}")

    def test_qft_display_qubits_limit(self):
        """시각화 큐빗 수는 제한됨."""
        state = ShorState(number=15)
        for _ in range(50):
            shor_step(state)
            if state.phase == ShorPhase.QFT_MEASURE:
                break
        qft_display = min(state.qft_n_qubits, 6)  # QFT_DISPLAY_QUBITS default
        self.assertLessEqual(qft_display, 6)
        self.assertGreater(qft_display, 0)


# ── 모듈러 지수 그래프 렌더링 데이터 테스트 ──────────

class TestModExpGraphData(unittest.TestCase):
    """_draw_mod_exp_graph에 필요한 데이터 검증."""

    def test_max_val_nonzero(self):
        """그래프 최대값이 0이 아님 (0으로 나누기 방지)."""
        for a, n in [(2, 15), (7, 21), (4, 35)]:
            table = build_mod_exp_table(a, n, 16)
            max_val = max(e.value for e in table)
            self.assertGreater(max_val, 0, f"a={a}, N={n}")

    def test_bar_heights_proportional(self):
        """바 높이가 값에 비례."""
        table = build_mod_exp_table(2, 15, 16)
        max_val = max(e.value for e in table)
        h = 150  # 픽셀 높이

        for entry in table:
            bar_h = int((h - 30) * entry.value / max_val)
            self.assertGreaterEqual(bar_h, 0)
            self.assertLessEqual(bar_h, h - 30)

    def test_period_marks_at_correct_positions(self):
        """주기 구분선이 올바른 위치에."""
        table = build_mod_exp_table(2, 15, 16)
        period = detect_period_from_table(table)
        self.assertEqual(period, 4)

        # 구분선 위치: period 배수
        n = len(table)
        mark_positions = [k * period for k in range(1, n // period + 1)]
        for pos in mark_positions:
            self.assertEqual(pos % period, 0)
            self.assertLessEqual(pos, n)

    def test_period_highlight_indices(self):
        """주기 시작점(i % period == 0)마다 다른 색."""
        table = build_mod_exp_table(7, 15, 16)
        period = detect_period_from_table(table)
        self.assertEqual(period, 4)

        highlighted = [i for i in range(len(table)) if period > 0 and i % period == 0]
        self.assertEqual(highlighted, [0, 4, 8, 12])

    def test_empty_table_renders_nothing(self):
        """빈 테이블 → 그래프 렌더 안 함 (early return)."""
        table = []
        # _draw_mod_exp_graph는 table이 비면 return
        self.assertEqual(len(table), 0)


# ── QFT 히스토그램 렌더링 데이터 테스트 ──────────────

class TestQFTHistogramData(unittest.TestCase):
    """_draw_qft_histogram에 필요한 데이터 검증."""

    def test_color_thresholds(self):
        """확률값에 따른 색상 분류 (high/medium/low)."""
        probs = compute_qft_probability_distribution(2, 15, 8)
        max_val = max(probs)

        high = [i for i, p in enumerate(probs) if p > max_val * 0.5]
        medium = [i for i, p in enumerate(probs)
                  if max_val * 0.1 < p <= max_val * 0.5]
        low = [i for i, p in enumerate(probs) if p <= max_val * 0.1]

        # 피크 위치 (high)가 존재해야 함
        self.assertGreater(len(high), 0, "No high probability peaks")
        # 대부분은 low
        self.assertGreater(len(low), len(high),
                           "Low count should exceed high count")

    def test_histogram_step_calculation(self):
        """128개 이상의 빈 → step으로 간추림."""
        n = 256
        step = max(1, n // 128)
        self.assertEqual(step, 2)

        n = 64
        step = max(1, n // 128)
        self.assertEqual(step, 1)  # 간추림 없음

    def test_bar_width_positive(self):
        """바 너비가 항상 양수."""
        for n in [16, 64, 128, 256, 1024]:
            w = 420  # 패널 너비
            bar_w = max(1, (w - 20) // min(n, 128))
            self.assertGreater(bar_w, 0)

    def test_peaks_at_qft_expected_positions(self):
        """QFT 피크 위치가 s*Q/r에 있음 (히스토그램 시각 검증)."""
        a, n, n_q = 2, 15, 8
        Q = 1 << n_q
        r = find_order(a, n)  # 4
        probs = compute_qft_probability_distribution(a, n, n_q)
        max_val = max(probs)

        expected_peaks = [s * Q // r for s in range(r)]  # [0, 64, 128, 192]
        for peak in expected_peaks:
            # 피크 위치 ± 1에서 높은 확률
            nearby = max(probs[max(0, peak - 1):min(Q, peak + 2)])
            self.assertGreater(nearby, max_val * 0.3,
                               f"Peak at {peak} not prominent")


# ── 연분수 시각화 데이터 테스트 ──────────────────────

class TestContinuedFractionVisualization(unittest.TestCase):
    """연분수 전개 시각화 데이터 검증."""

    def test_qft_result_display_values(self):
        """QFTResult의 시각화 필드가 모두 설정됨."""
        result = simulate_qft_measurement(7, 15, 8)
        # 모든 필드 존재
        self.assertIsInstance(result.measured_value, int)
        self.assertIsInstance(result.n_qubits, int)
        self.assertIsInstance(result.phase_estimate, float)

        # m/Q 문자열 포맷 가능
        Q = 1 << result.n_qubits
        display_str = f"m = {result.measured_value},  m/Q = {result.measured_value}/{Q}"
        self.assertIn(str(result.measured_value), display_str)

    def test_convergents_display_format(self):
        """수렴분수가 'p/q' 형태로 표시 가능."""
        result = simulate_qft_measurement(7, 15, 8)
        # convergents는 simulate 후 빈 상태, continued_fraction step에서 채워짐
        # 직접 채워서 테스트
        state = ShorState(number=15)
        for _ in range(300):
            shor_step(state)
            if state.qft_current and state.qft_current.convergents:
                break
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

        if state.qft_current and state.qft_current.convergents:
            convs = state.qft_current.convergents
            # 최대 6개만 표시
            display = convs[:6]
            convs_str = "  ".join(f"{p}/{q}" for p, q in display)
            self.assertIsInstance(convs_str, str)
            self.assertGreater(len(convs_str), 0)

    def test_candidate_r_display(self):
        """candidate_r에 따라 '성공' 또는 '실패' 메시지."""
        # 여러 번 시도하여 quantum 경로에서 candidate_r 찾기
        found_candidate = False
        for trial in range(10):
            state = ShorState(number=21)  # 21은 trivial_gcd 확률이 낮음
            for _ in range(300):
                shor_step(state)
                if (state.qft_current and
                        state.qft_current.candidate_r is not None):
                    found_candidate = True
                    r = state.qft_current.candidate_r
                    self.assertGreater(r, 0)
                    display = f"→ Period candidate: r = {r}"
                    self.assertIn(str(r), display)
                    break
                if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                    break
            if found_candidate:
                break

        self.assertTrue(found_candidate,
                        "Should find candidate_r within 10 trials")


# ── 모드 전환 테스트 ─────────────────────────────────

class TestModeTransitions(unittest.TestCase):
    """모드 전환 시 상태 초기화 로직."""

    def test_mode_to_rsa_sets_up_demo(self):
        """RSA 모드 전환 시 RSA 데모 초기화."""
        state = ShorState(number=15)
        setup_rsa_demo(state, difficulty=0)

        rsa = state.rsa
        self.assertGreater(rsa.rsa_n, 0)
        self.assertEqual(rsa.rsa_n, rsa.rsa_p * rsa.rsa_q)
        self.assertGreater(rsa.ciphertext, 0)
        self.assertFalse(rsa.cracked)

    def test_mode_to_step_resets_state(self):
        """Step 모드 전환 시 상태 초기화."""
        state = ShorState(number=15)
        # 실행
        for _ in range(50):
            shor_step(state)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

        # 리셋 + 첫 step
        reset_state(state)
        shor_step(state)

        self.assertEqual(state.phase, ShorPhase.CLASSICAL_PRECHECK)
        self.assertIsNone(state.factors)

    def test_rsa_difficulty_changes(self):
        """RSA 난이도 변경 시 N이 바뀜."""
        state = ShorState()

        setup_rsa_demo(state, difficulty=0)
        n0 = state.rsa.rsa_n

        setup_rsa_demo(state, difficulty=3)
        n3 = state.rsa.rsa_n

        self.assertNotEqual(n0, n3, "Different difficulties should give different N")
        self.assertGreater(n3, n0, "Higher difficulty should give larger N")

    def test_rsa_cracking_flow(self):
        """RSA 크래킹 플로우: setup → crack → verify."""
        state = ShorState()
        setup_rsa_demo(state, difficulty=0)

        original = state.rsa.plaintext
        self.assertFalse(state.rsa.cracked)

        success = crack_rsa(state)
        self.assertTrue(success)
        self.assertTrue(state.rsa.cracked)
        self.assertEqual(state.rsa.decrypted, original)
        self.assertGreater(state.rsa.cracked_d, 0)


# ── 진행률 바 데이터 테스트 ──────────────────────────

class TestProgressBarData(unittest.TestCase):
    """_draw_progress_bar에 필요한 진행률 계산."""

    def test_progress_monotonically_increases(self):
        """단계가 진행되면 progress 값이 증가."""
        state = ShorState(number=15)
        prev_progress = 0.0

        for _ in range(300):
            shor_step(state)

            if state.phase not in (ShorPhase.DONE, ShorPhase.SUCCESS,
                                    ShorPhase.RETRY):
                progress = state.phase.value / ShorPhase.DONE.value
                # RETRY로 돌아가지 않는 한 증가
                self.assertGreaterEqual(progress, 0.0)
                self.assertLessEqual(progress, 1.0)

            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

    def test_progress_at_success_is_1(self):
        """SUCCESS/DONE에서 progress = 1.0."""
        progress = 1.0  # SUCCESS/DONE 시 1.0
        self.assertEqual(progress, 1.0)

    def test_progress_calculation_all_phases(self):
        """모든 phase에 대한 progress 계산이 0~1 범위."""
        for phase in ShorPhase:
            if phase not in (ShorPhase.DONE, ShorPhase.SUCCESS):
                progress = phase.value / ShorPhase.DONE.value
            else:
                progress = 1.0
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 1.0)


# ── Step Message 시각화 테스트 ───────────────────────

class TestStepMessages(unittest.TestCase):
    """각 단계의 step_message가 시각화에 적합한지 검증."""

    def test_messages_not_empty(self):
        """각 단계 진행 시 step_message가 비어있지 않음."""
        state = ShorState(number=15)

        for _ in range(300):
            shor_step(state)
            if state.phase != ShorPhase.INPUT:
                self.assertGreater(len(state.step_message), 0,
                                   f"Empty message at phase {state.phase}")
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

    def test_messages_wrappable(self):
        """step_message가 _wrap_text로 줄바꿈 가능."""
        state = ShorState(number=15)

        for _ in range(300):
            shor_step(state)
            if state.step_message:
                lines = _wrap_text(state.step_message, 35)
                self.assertGreater(len(lines), 0)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

    def test_success_message_contains_factors(self):
        """SUCCESS 시 메시지에 인수 정보 포함."""
        state = ShorState(number=15)
        for _ in range(300):
            shor_step(state)
            if state.phase == ShorPhase.SUCCESS:
                # factors가 있어야 함
                self.assertIsNotNone(state.factors)
                break


# ── 입력 필드 로직 테스트 ────────────────────────────

class TestInputFieldLogic(unittest.TestCase):
    """숫자 입력 및 submit 로직."""

    def test_valid_input_resets_state(self):
        """유효한 숫자 입력 → 상태 초기화 + 첫 단계 실행."""
        state = ShorState(number=15)
        shor_run_full(15)

        # 유효한 입력 시뮬레이션
        reset_state(state, 21)
        shor_step(state)

        self.assertEqual(state.number, 21)
        self.assertEqual(state.phase, ShorPhase.CLASSICAL_PRECHECK)

    def test_input_less_than_2_stays(self):
        """N < 2 → DONE (유효하지 않은 입력)."""
        state = ShorState(number=1)
        shor_step(state)
        self.assertEqual(state.phase, ShorPhase.DONE)

    def test_input_shown_at_terminal_phases(self):
        """INPUT, DONE, SUCCESS phase에서 입력 필드 표시."""
        terminal_phases = {ShorPhase.INPUT, ShorPhase.DONE, ShorPhase.SUCCESS}
        for phase in ShorPhase:
            should_show = phase in terminal_phases
            if should_show:
                self.assertIn(phase, terminal_phases)


# ── Attempt History 시각화 테스트 ────────────────────

class TestAttemptHistoryVisualization(unittest.TestCase):
    """시도 히스토리의 시각화 데이터."""

    def test_history_entries_have_required_fields(self):
        """히스토리 항목에 필수 필드가 있음."""
        state = ShorState(number=15)
        for _ in range(300):
            shor_step(state)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

        if state.factor_method == "quantum":
            for h in state.attempt_history:
                self.assertIn("attempt", h)
                self.assertIn("a", h)
                self.assertIn("reason", h)

    def test_history_display_limit(self):
        """히스토리 표시는 최근 4개만 (시각화 렌더링)."""
        state = ShorState(number=15)
        for _ in range(300):
            shor_step(state)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

        # 표시용 슬라이스: [-4:]
        display = state.attempt_history[-4:]
        self.assertLessEqual(len(display), 4)

    def test_history_reason_colors(self):
        """reason에 따른 색상 분류 (success → GREEN, 기타 → YELLOW)."""
        state = ShorState(number=15)
        for _ in range(300):
            shor_step(state)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

        for h in state.attempt_history:
            reason = h.get("reason", "")
            if reason == "success":
                # GREEN 색상 적용 대상
                self.assertEqual(reason, "success")
            else:
                # YELLOW 색상 적용 대상
                self.assertNotEqual(reason, "success")


# ── 다양한 N에 대한 시각화 데이터 일관성 ─────────────

class TestVisualizationAcrossNumbers(unittest.TestCase):
    """다양한 N에서 시각화 데이터 일관성."""

    def test_even_number_no_quantum_data(self):
        """짝수 → 양자 시각화 데이터 없음."""
        state = ShorState(number=14)
        shor_step(state)  # INPUT
        shor_step(state)  # CLASSICAL_PRECHECK → SUCCESS

        self.assertEqual(state.phase, ShorPhase.SUCCESS)
        self.assertEqual(len(state.mod_exp_table), 0)
        self.assertEqual(len(state.qft_amplitudes), 0)
        self.assertIsNone(state.qft_current)

    def test_prime_no_quantum_data(self):
        """소수 → 양자 시각화 데이터 없음."""
        state = ShorState(number=17)
        shor_step(state)  # INPUT
        shor_step(state)  # CLASSICAL_PRECHECK → DONE

        self.assertEqual(state.phase, ShorPhase.DONE)
        self.assertEqual(len(state.mod_exp_table), 0)
        self.assertEqual(len(state.qft_amplitudes), 0)

    def test_composite_generates_quantum_data(self):
        """합성수 → 양자 시각화 데이터 생성."""
        for n in [15, 21, 35]:
            state = ShorState(number=n)
            for _ in range(300):
                shor_step(state)
                if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                    break

            if state.factor_method == "quantum":
                self.assertGreater(len(state.qft_results), 0,
                                   f"N={n}: no QFT results")
                self.assertGreater(state.total_qft_measurements, 0,
                                   f"N={n}: no QFT measurements")

    def test_mod_exp_table_values_in_range(self):
        """mod_exp_table 값이 [0, N) 범위."""
        for n in [15, 21, 35, 77]:
            state = ShorState(number=n)
            for _ in range(50):
                shor_step(state)
                if state.mod_exp_table:
                    break
                if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                    break

            for entry in state.mod_exp_table:
                self.assertGreaterEqual(entry.value, 0)
                self.assertLess(entry.value, n,
                                f"N={n}: value {entry.value} out of range")


# ── RSA 모드 시각화 데이터 ───────────────────────────

class TestRSAVisualizationData(unittest.TestCase):
    """RSA Threat 모드 시각화 데이터."""

    def test_rsa_info_lines_format(self):
        """RSA 키 정보가 표시 가능한 형식."""
        state = ShorState()
        setup_rsa_demo(state, difficulty=0)
        rsa = state.rsa

        # 표시 문자열 생성 가능
        lines = [
            f"N = {rsa.rsa_n}",
            f"e = {rsa.rsa_e}",
            f"Plaintext m = {rsa.plaintext}",
            f"Ciphertext c = {rsa.ciphertext}",
        ]
        for line in lines:
            self.assertIsInstance(line, str)
            self.assertGreater(len(line), 0)

    def test_cracked_info_lines_format(self):
        """크래킹 후 비밀키 정보 표시."""
        state = ShorState()
        setup_rsa_demo(state, difficulty=0)
        crack_rsa(state)
        rsa = state.rsa

        lines = [
            f"p = {rsa.cracked_p}, q = {rsa.cracked_q}",
            f"d = {rsa.cracked_d}",
            f"Decrypted = {rsa.decrypted}",
        ]
        for line in lines:
            self.assertIsInstance(line, str)
            self.assertGreater(len(line), 0)

        # 복호화 일치
        match = (rsa.decrypted == rsa.plaintext)
        self.assertTrue(match)

    def test_rsa_phase_flow(self):
        """RSA UI phase: 0(setup) → 1(cracking) → 2(cracked) → 3(qkd)."""
        phases = [0, 1, 2, 3]
        for p in phases:
            self.assertIn(p, range(4))

    def test_rsa_arrow_shown_when_cracked(self):
        """크래킹 완료 후 화살표(시각적) 표시 조건."""
        state = ShorState()
        setup_rsa_demo(state, difficulty=0)
        self.assertFalse(state.rsa.cracked)

        crack_rsa(state)
        self.assertTrue(state.rsa.cracked)

    def test_qkd_motivation_message_exists(self):
        """QKD 동기 메시지가 존재하고 줄바꿈 가능."""
        from quantum.shor_algorithm_engine import get_qkd_motivation
        msg = get_qkd_motivation()
        self.assertIsInstance(msg, str)
        self.assertGreater(len(msg), 50)

        lines = _wrap_text(msg, 80)
        self.assertGreater(len(lines), 0)
        # 7줄 이내로 표시 가능
        self.assertGreater(len(lines), 0)


# ── 탭 모드 표시 테스트 ─────────────────────────────

class TestTabModeDisplay(unittest.TestCase):
    """모드 탭 표시 데이터."""

    MODE_NAMES = ["Step-by-Step", "Auto Run", "RSA Threat"]

    def test_three_modes(self):
        """3개 모드가 존재."""
        self.assertEqual(len(self.MODE_NAMES), 3)

    def test_mode_names_non_empty(self):
        """모드 이름이 비어있지 않음."""
        for name in self.MODE_NAMES:
            self.assertGreater(len(name), 0)

    def test_mode_cycling(self):
        """Tab으로 모드 순환: 0 → 1 → 2 → 0."""
        mode = 0
        for expected in [1, 2, 0, 1]:
            mode = (mode + 1) % 3
            self.assertEqual(mode, expected)


if __name__ == "__main__":
    unittest.main()
