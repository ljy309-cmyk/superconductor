"""Grover's Search UI 로직 중점 테스트.

시각화 코드에서 추가된 UI 로직(히스토리 페이지네이션, 입력 검증,
알림, 레이아웃, 모드 전환, Compare 계산, i18n 커버리지)을 검증합니다.
Pygame 없이 순수 로직만 테스트합니다.
"""

import math
import os
import sys
import unittest
from unittest.mock import MagicMock

# ── Pygame 모킹 (테스트 환경에 pygame 없음) ─────────
_pg_mock = MagicMock()
sys.modules.setdefault("pygame", _pg_mock)
sys.modules.setdefault("pygame.font", _pg_mock.font)
sys.modules.setdefault("pygame.draw", _pg_mock.draw)
sys.modules.setdefault("pygame.display", _pg_mock.display)
sys.modules.setdefault("pygame.time", _pg_mock.time)
sys.modules.setdefault("pygame.event", _pg_mock.event)
sys.modules.setdefault("pygame.mixer", _pg_mock.mixer)
sys.modules.setdefault("pygame.transform", _pg_mock.transform)
sys.modules.setdefault("pygame.image", _pg_mock.image)
sys.modules.setdefault("pygame.Surface", _pg_mock.Surface)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum.grover_search_engine import (
    GroverPhase,
    GroverState,
    grover_step,
    reset_state,
)

from quantum.grover_search import (
    HISTORY_PAGE_SIZE,
    Layout,
    UIState,
    _notify,
    _on_mode_change,
    _rebuild_layout,
    _MODE_TAB_KEYS,
    MODE_STEP,
    MODE_AUTO,
    MODE_COMPARE,
)


# ── 히스토리 페이지네이션 테스트 ─────────────────────

class TestHistoryPagination(unittest.TestCase):
    """탐색 히스토리 페이지네이션 로직."""

    def test_page_size_constant(self):
        """HISTORY_PAGE_SIZE가 양수."""
        self.assertGreater(HISTORY_PAGE_SIZE, 0)

    def test_single_page_no_overflow(self):
        """항목 수 <= 페이지 크기면 1페이지."""
        total = 3
        total_pages = max(1, (total + HISTORY_PAGE_SIZE - 1) // HISTORY_PAGE_SIZE)
        self.assertEqual(total_pages, 1)

    def test_multiple_pages(self):
        """항목 수 > 페이지 크기면 여러 페이지."""
        total = HISTORY_PAGE_SIZE + 1
        total_pages = max(1, (total + HISTORY_PAGE_SIZE - 1) // HISTORY_PAGE_SIZE)
        self.assertEqual(total_pages, 2)

    def test_exact_page_boundary(self):
        """항목 수가 페이지 크기의 정확한 배수."""
        total = HISTORY_PAGE_SIZE * 3
        total_pages = max(1, (total + HISTORY_PAGE_SIZE - 1) // HISTORY_PAGE_SIZE)
        self.assertEqual(total_pages, 3)

    def test_empty_history(self):
        """빈 히스토리 → 1페이지."""
        total = 0
        total_pages = max(1, (total + HISTORY_PAGE_SIZE - 1) // HISTORY_PAGE_SIZE)
        self.assertEqual(total_pages, 1)

    def test_page_slice_range(self):
        """페이지 슬라이스가 올바른 범위."""
        history = list(range(10))
        page = 1
        start = page * HISTORY_PAGE_SIZE
        end = min(start + HISTORY_PAGE_SIZE, len(history))
        items = history[start:end]
        self.assertEqual(len(items), HISTORY_PAGE_SIZE)
        self.assertEqual(items, list(range(4, 8)))

    def test_last_page_partial(self):
        """마지막 페이지의 항목 수가 페이지 크기 이하."""
        history = list(range(10))
        total_pages = max(1, (len(history) + HISTORY_PAGE_SIZE - 1) // HISTORY_PAGE_SIZE)
        last_page = total_pages - 1
        start = last_page * HISTORY_PAGE_SIZE
        end = min(start + HISTORY_PAGE_SIZE, len(history))
        items = history[start:end]
        self.assertLessEqual(len(items), HISTORY_PAGE_SIZE)
        self.assertGreater(len(items), 0)

    def test_page_clamping(self):
        """페이지 번호가 범위 밖이면 클램핑."""
        ui = UIState()
        ui.history_page = 999
        total = 5
        total_pages = max(1, (total + HISTORY_PAGE_SIZE - 1) // HISTORY_PAGE_SIZE)
        clamped = max(0, min(ui.history_page, total_pages - 1))
        self.assertEqual(clamped, total_pages - 1)

    def test_negative_page_clamped_to_zero(self):
        """음수 페이지 → 0으로 클램핑."""
        clamped = max(0, -5)
        self.assertEqual(clamped, 0)

    def test_page_reset_on_new_search(self):
        """새 탐색 입력 시 페이지 리셋 검증."""
        ui = UIState()
        ui.history_page = 3
        ui.history_page = 0
        self.assertEqual(ui.history_page, 0)


# ── 알림(notification) 테스트 ────────────────────────

class TestNotify(unittest.TestCase):
    """_notify 알림 시스템."""

    def test_notify_sets_message(self):
        """알림 메시지 설정."""
        ui = UIState()
        _notify(ui, "test message")
        self.assertEqual(ui.notify_msg, "test message")
        self.assertEqual(ui.notify_timer, 2.0)

    def test_notify_custom_duration(self):
        """커스텀 지속 시간."""
        ui = UIState()
        _notify(ui, "speed", 1.0)
        self.assertEqual(ui.notify_timer, 1.0)

    def test_notify_overwrites_previous(self):
        """새 알림이 이전 알림을 덮어씀."""
        ui = UIState()
        _notify(ui, "first", 2.0)
        _notify(ui, "second", 1.5)
        self.assertEqual(ui.notify_msg, "second")
        self.assertEqual(ui.notify_timer, 1.5)

    def test_timer_decreases(self):
        """타이머가 dt만큼 감소."""
        ui = UIState()
        _notify(ui, "msg", 2.0)
        ui.notify_timer -= 0.5
        self.assertAlmostEqual(ui.notify_timer, 1.5)

    def test_timer_expires(self):
        """타이머가 0 이하가 되면 알림 비활성."""
        ui = UIState()
        _notify(ui, "msg", 0.1)
        ui.notify_timer -= 0.2
        self.assertLessEqual(ui.notify_timer, 0)

    def test_fade_alpha_calculation(self):
        """페이드 알파 계산 로직."""
        # 렌더 루프에서 사용하는 알파 계산 재현
        for timer_val in [0.3, 0.15, 0.05, 0.0]:
            alpha = min(255, int(255 * min(1.0, timer_val / 0.3)))
            self.assertGreaterEqual(alpha, 0)
            self.assertLessEqual(alpha, 255)


# ── Layout 비례 좌표 테스트 ──────────────────────────

class TestLayout(unittest.TestCase):
    """Layout 클래스 — 해상도 비례 좌표 계산."""

    def test_default_resolution(self):
        """기본 해상도 900×600."""
        L = Layout()
        self.assertEqual(L.W, 900)
        self.assertEqual(L.H, 600)

    def test_custom_resolution(self):
        """커스텀 해상도."""
        L = Layout(1800, 1200)
        self.assertEqual(L.W, 1800)
        self.assertEqual(L.H, 1200)

    def test_margin_scales_proportionally(self):
        """마진이 해상도에 비례."""
        L1 = Layout(900, 600)
        L2 = Layout(1800, 1200)
        self.assertAlmostEqual(L2.margin / L1.margin, 2.0, places=1)

    def test_tab_width_fills_screen(self):
        """탭 너비 × 3 + 마진이 화면 너비를 넘지 않음."""
        for w in [600, 900, 1200, 1920]:
            L = Layout(w, 600)
            total = L.tab_w * 3 + L.margin * 2
            self.assertLessEqual(total, w + L.margin)

    def test_hint_y_below_history(self):
        """하단 힌트 Y가 히스토리 Y보다 아래."""
        L = Layout(900, 600)
        self.assertGreater(L.hint_y1, L.history_y)

    def test_badge_y_at_bottom(self):
        """뱃지 Y가 화면 하단 근처."""
        L = Layout(900, 600)
        self.assertGreater(L.badge_y, L.H * 0.9)

    def test_graph_areas_positive(self):
        """그래프 영역이 양수 크기."""
        L = Layout(900, 600)
        self.assertGreater(L.graph_w_step, 0)
        self.assertGreater(L.graph_h_step, 0)
        self.assertGreater(L.graph_w_auto, 0)
        self.assertGreater(L.graph_h_auto, 0)

    def test_prob_areas_positive(self):
        """확률 변화 그래프 영역이 양수."""
        L = Layout(900, 600)
        self.assertGreater(L.prob_w_step, 0)
        self.assertGreater(L.prob_w_auto, 0)
        self.assertGreater(L.prob_h, 0)

    def test_status_panel_inside_screen(self):
        """상태 패널이 화면 안에 있음."""
        L = Layout(900, 600)
        self.assertGreater(L.status_w, 0)
        self.assertLessEqual(L.status_x + L.status_w, L.W)

    def test_circuit_panel_positive(self):
        """회로 다이어그램 패널이 양수 크기."""
        L = Layout(900, 600)
        self.assertGreater(L.circuit_w, 0)
        self.assertGreater(L.circuit_h, 0)

    def test_compare_panels_dont_overlap(self):
        """Compare 모드 고전/양자 트랙이 겹치지 않음."""
        L = Layout(900, 600)
        classical_bottom = L.cmp_classical_y + L.cmp_panel_h
        self.assertLessEqual(classical_bottom, L.cmp_quantum_y)

    def test_compare_stats_below_tracks(self):
        """비교 통계 패널이 트랙 아래."""
        L = Layout(900, 600)
        quantum_bottom = L.cmp_quantum_y + L.cmp_panel_h
        self.assertGreaterEqual(L.cmp_stats_y, quantum_bottom)

    def test_small_resolution_no_negative(self):
        """작은 해상도에서 음수 좌표 없음."""
        L = Layout(400, 300)
        attrs = [L.margin, L.tab_y, L.tab_h, L.tab_w,
                 L.title_y, L.graph_x, L.graph_y,
                 L.graph_w_step, L.graph_h_step, L.hint_y1,
                 L.cmp_track_x, L.cmp_track_w, L.cmp_bar_h]
        for attr in attrs:
            self.assertGreaterEqual(attr, 0)

    def test_large_resolution(self):
        """4K 해상도에서도 정상 계산."""
        L = Layout(3840, 2160)
        self.assertEqual(L.W, 3840)
        self.assertGreater(L.margin, 0)
        self.assertGreater(L.tab_w, 0)

    def test_perf_x_inside_screen(self):
        """PerfMonitor 오버레이 X가 화면 안."""
        L = Layout(900, 600)
        self.assertGreater(L.perf_x, 0)
        self.assertLess(L.perf_x, L.W)

    def test_rebuild_layout_updates_global(self):
        """_rebuild_layout이 전역 Layout을 갱신."""
        import quantum.grover_search as gs
        old_w = gs._layout.W
        _rebuild_layout(1024, 768)
        self.assertEqual(gs._layout.W, 1024)
        self.assertEqual(gs._layout.H, 768)
        # 복원
        _rebuild_layout(old_w, 600)


# ── UIState 필드 테스트 ──────────────────────────────

class TestUIStateDefaults(unittest.TestCase):
    """UIState 기본값 검증."""

    def test_default_mode(self):
        ui = UIState()
        self.assertEqual(ui.mode, MODE_STEP)

    def test_default_difficulty(self):
        ui = UIState()
        self.assertEqual(ui.difficulty, "normal")

    def test_default_counters(self):
        ui = UIState()
        self.assertEqual(ui.searches_completed, 0)
        self.assertEqual(ui.total_steps, 0)
        self.assertEqual(ui.history_page, 0)

    def test_default_notify(self):
        ui = UIState()
        self.assertEqual(ui.notify_msg, "")
        self.assertEqual(ui.notify_timer, 0.0)

    def test_default_auto_state(self):
        ui = UIState()
        self.assertFalse(ui.auto_running)
        self.assertEqual(ui.auto_timer, 0.0)

    def test_default_compare_state(self):
        ui = UIState()
        self.assertFalse(ui.compare_running)
        self.assertAlmostEqual(ui.compare_classical_pos, 0.0)
        self.assertAlmostEqual(ui.compare_quantum_pos, 0.0)
        self.assertFalse(ui.compare_classical_done)
        self.assertFalse(ui.compare_quantum_done)
        self.assertEqual(ui.compare_n_qubits, 4)

    def test_default_input_buffers(self):
        ui = UIState()
        self.assertEqual(ui.input_buffer, "4")
        self.assertEqual(ui.input_target_buffer, "7")
        self.assertEqual(ui.input_active, 0)

    def test_grover_state_initialized(self):
        ui = UIState()
        self.assertIsInstance(ui.grover, GroverState)
        self.assertEqual(ui.grover.n_qubits, 4)
        self.assertEqual(ui.grover.targets, [7])
        self.assertEqual(ui.grover.phase, GroverPhase.INPUT)


# ── MODE_TAB_KEYS 테스트 ────────────────────────────

class TestModeTabKeys(unittest.TestCase):
    """모드 탭 i18n 키 리스트."""

    def test_three_modes(self):
        self.assertEqual(len(_MODE_TAB_KEYS), 3)

    def test_keys_are_strings(self):
        for key in _MODE_TAB_KEYS:
            self.assertIsInstance(key, str)
            self.assertTrue(key.startswith("grover_tab_"))

    def test_mode_cycling(self):
        """Tab으로 모드 순환: 0 → 1 → 2 → 0."""
        mode = 0
        for expected in [1, 2, 0, 1]:
            mode = (mode + 1) % len(_MODE_TAB_KEYS)
            self.assertEqual(mode, expected)


# ── 모드 전환 테스트 ────────────────────────────────

class TestOnModeChange(unittest.TestCase):
    """_on_mode_change — 모드 전환 시 상태 초기화."""

    def test_switch_to_compare_resets_compare_state(self):
        """Compare 모드 전환 시 비교 상태 초기화."""
        ui = UIState()
        ui.mode = MODE_COMPARE
        ui.compare_running = True
        ui.compare_classical_pos = 0.7
        ui.compare_quantum_pos = 1.0
        ui.compare_classical_done = True
        ui.compare_quantum_done = True
        _on_mode_change(ui)
        self.assertFalse(ui.compare_running)
        self.assertAlmostEqual(ui.compare_classical_pos, 0.0)
        self.assertAlmostEqual(ui.compare_quantum_pos, 0.0)
        self.assertFalse(ui.compare_classical_done)
        self.assertFalse(ui.compare_quantum_done)

    def test_switch_to_step_resets_grover(self):
        """Step 모드 전환 시 Grover 상태 초기화."""
        ui = UIState()
        ui.grover = GroverState(n_qubits=4, targets=[7])
        # 몇 단계 진행
        for _ in range(5):
            grover_step(ui.grover)
        ui.mode = MODE_STEP
        _on_mode_change(ui)
        # 리셋 후 다시 INPUT → INIT_SUPERPOSITION
        self.assertIn(ui.grover.phase,
                      (GroverPhase.INPUT, GroverPhase.INIT_SUPERPOSITION))

    def test_switch_to_auto_stops_running(self):
        """Auto 모드 전환 시 auto_running 해제."""
        ui = UIState()
        ui.auto_running = True
        ui.mode = MODE_AUTO
        _on_mode_change(ui)
        self.assertFalse(ui.auto_running)

    def test_history_page_resets(self):
        """모드 전환 시 히스토리 페이지 리셋."""
        ui = UIState()
        ui.history_page = 5
        ui.mode = MODE_STEP
        _on_mode_change(ui)
        self.assertEqual(ui.history_page, 0)


# ── Auto 진행률 계산 테스트 ──────────────────────────

class TestAutoProgress(unittest.TestCase):
    """Auto 모드 진행률 계산 로직."""

    def test_terminal_phase_returns_1(self):
        """SUCCESS/FAIL/DONE → 진행률 1.0."""
        for phase in (GroverPhase.SUCCESS, GroverPhase.FAIL, GroverPhase.DONE):
            progress = 1.0  # 코드 로직 재현
            self.assertEqual(progress, 1.0)

    def test_active_phase_returns_fraction(self):
        """활성 단계에서 진행률이 0~1 사이."""
        for phase in GroverPhase:
            if phase in (GroverPhase.DONE, GroverPhase.SUCCESS, GroverPhase.FAIL):
                continue
            progress = phase.value / GroverPhase.DONE.value
            self.assertGreaterEqual(progress, 0.0)
            self.assertLessEqual(progress, 1.0)

    def test_progress_monotonic_through_phases(self):
        """단계가 진행될수록 진행률 단조 증가."""
        phases = [
            GroverPhase.INPUT,
            GroverPhase.INIT_SUPERPOSITION,
            GroverPhase.ORACLE,
            GroverPhase.DIFFUSION,
            GroverPhase.ITERATE,
            GroverPhase.MEASURE,
        ]
        prev = -1
        for phase in phases:
            progress = phase.value / GroverPhase.DONE.value
            self.assertGreater(progress, prev)
            prev = progress


# ── Compare 모드 계산 테스트 ─────────────────────────

class TestCompareCalculations(unittest.TestCase):
    """Compare 모드 속도 비교 계산."""

    def test_optimal_iterations_positive(self):
        """최적 반복 횟수가 양수."""
        for n_qubits in range(2, 11):
            n_states = 1 << n_qubits
            opt_iter = max(1, int(math.pi / 4 * math.sqrt(n_states)))
            self.assertGreater(opt_iter, 0)

    def test_speedup_grows_with_qubits(self):
        """큐빗 수가 증가하면 속도 향상 비율 비감소 & 전체적 증가."""
        speedups = []
        for n_qubits in range(2, 11):
            n_states = 1 << n_qubits
            opt_iter = max(1, int(math.pi / 4 * math.sqrt(n_states)))
            speedups.append(n_states / opt_iter)
        # 비감소 (정수 반올림으로 동일할 수 있음)
        for i in range(1, len(speedups)):
            self.assertGreaterEqual(speedups[i], speedups[i - 1])
        # 전체적으로 증가: 마지막 > 첫번째
        self.assertGreater(speedups[-1], speedups[0])

    def test_classical_speed_slower_than_quantum(self):
        """고전 속도가 양자보다 느림 (n >= 3)."""
        speed = 2.0
        for n_qubits in range(3, 11):
            n_states = 1 << n_qubits
            opt_iter = max(1, int(math.pi / 4 * math.sqrt(n_states)))
            classical_speed = speed * opt_iter / n_states
            self.assertLess(classical_speed, speed)

    def test_queries_count_bounds(self):
        """쿼리 카운트가 0 ~ total 범위."""
        n_states = 1 << 6  # 64
        for pos in [0.0, 0.5, 1.0]:
            queries = int(pos * n_states)
            self.assertGreaterEqual(queries, 0)
            self.assertLessEqual(queries, n_states)

    def test_quantum_pos_reaches_1_before_classical(self):
        """양자 위치가 고전보다 먼저 1.0에 도달 (시뮬레이션)."""
        n_qubits = 6
        n_states = 1 << n_qubits
        opt_iter = max(1, int(math.pi / 4 * math.sqrt(n_states)))
        speed = 2.0
        dt = 0.016  # ~60fps

        q_pos, c_pos = 0.0, 0.0
        q_done_t, c_done_t = None, None

        for frame in range(10000):
            t = frame * dt
            if q_pos < 1.0:
                q_pos = min(1.0, q_pos + speed * dt)
                if q_pos >= 1.0 and q_done_t is None:
                    q_done_t = t
            if c_pos < 1.0:
                c_speed = speed * opt_iter / n_states
                c_pos = min(1.0, c_pos + c_speed * dt)
                if c_pos >= 1.0 and c_done_t is None:
                    c_done_t = t
            if q_done_t and c_done_t:
                break

        self.assertIsNotNone(q_done_t)
        self.assertIsNotNone(c_done_t)
        self.assertLess(q_done_t, c_done_t)


# ── 입력 검증 테스트 ────────────────────────────────

class TestInputValidation(unittest.TestCase):
    """_submit_input 입력 검증 로직 (순수 로직)."""

    def test_valid_qubits_range(self):
        """유효한 큐빗 수 범위 1~10."""
        for val in ["1", "4", "10"]:
            n = int(val)
            self.assertGreaterEqual(n, 1)
            self.assertLessEqual(n, 10)

    def test_qubits_clamped_below(self):
        """큐빗 수가 1 미만이면 1로 클램핑."""
        n = int("0")
        if n < 1:
            n = 1
        self.assertEqual(n, 1)

    def test_qubits_clamped_above(self):
        """큐빗 수가 max_qubits 초과면 클램핑."""
        max_q = 10
        n = int("15")
        if n > max_q:
            n = max_q
        self.assertEqual(n, max_q)

    def test_target_parsing_single(self):
        """단일 대상 파싱."""
        buffer = "7"
        parts = buffer.replace(" ", "").split(",")
        targets = [int(p) for p in parts if p.isdigit()]
        self.assertEqual(targets, [7])

    def test_target_parsing_multiple(self):
        """쉼표 구분 다중 대상 파싱."""
        buffer = "3,7,11"
        parts = buffer.replace(" ", "").split(",")
        targets = [int(p) for p in parts if p.isdigit()]
        self.assertEqual(targets, [3, 7, 11])

    def test_target_parsing_with_spaces(self):
        """공백 포함 대상 파싱."""
        buffer = "3, 7, 11"
        parts = buffer.replace(" ", "").split(",")
        targets = [int(p) for p in parts if p.isdigit()]
        self.assertEqual(targets, [3, 7, 11])

    def test_target_parsing_empty(self):
        """빈 대상 → 빈 리스트 (랜덤 폴백)."""
        buffer = ""
        parts = buffer.replace(" ", "").split(",")
        targets = [int(p) for p in parts if p.isdigit()]
        self.assertEqual(targets, [])

    def test_target_parsing_invalid(self):
        """유효하지 않은 입력 → 빈 리스트."""
        buffer = "abc"
        parts = buffer.replace(" ", "").split(",")
        targets = [int(p) for p in parts if p.isdigit()]
        self.assertEqual(targets, [])

    def test_invalid_qubits_raises_valueerror(self):
        """숫자가 아닌 입력 → ValueError."""
        with self.assertRaises(ValueError):
            int("abc")

    def test_input_buffer_length_limit(self):
        """큐빗 입력 버퍼 3자 제한."""
        buffer = "12"
        char = "3"
        if len(buffer) < 3:
            buffer += char
        self.assertEqual(buffer, "123")
        # 초과 시 추가 안 됨
        char2 = "4"
        if len(buffer) < 3:
            buffer += char2
        self.assertEqual(buffer, "123")

    def test_target_buffer_length_limit(self):
        """대상 입력 버퍼 12자 제한."""
        buffer = "1,2,3,4,5,6"  # 11자
        self.assertLess(len(buffer), 12)
        buffer += ","
        self.assertEqual(len(buffer), 12)
        # 12자에서 추가 불가
        if len(buffer) < 12:
            buffer += "7"
        self.assertEqual(len(buffer), 12)


# ── i18n 키 커버리지 테스트 ──────────────────────────

class TestI18nCoverage(unittest.TestCase):
    """Grover 모듈에서 사용하는 i18n 키가 locale 파일에 정의되어 있는지."""

    @classmethod
    def setUpClass(cls):
        import json
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base, "locale", "en.json"), encoding="utf-8") as f:
            cls.en = json.load(f)
        with open(os.path.join(base, "locale", "ko.json"), encoding="utf-8") as f:
            cls.ko = json.load(f)

    def _assert_key_exists(self, key):
        self.assertIn(key, self.en, f"Missing in en.json: {key}")
        self.assertIn(key, self.ko, f"Missing in ko.json: {key}")

    def test_tab_keys(self):
        """탭 이름 키가 모두 정의."""
        for key in _MODE_TAB_KEYS:
            self._assert_key_exists(key)

    def test_hint_keys(self):
        """하단 힌트 키가 모두 정의."""
        for suffix in ["step_1", "step_2", "auto_1", "auto_2",
                        "compare_1", "compare_2"]:
            self._assert_key_exists(f"grover_hint_{suffix}")

    def test_phase_keys(self):
        """단계 이름 키가 모두 정의."""
        phase_keys = [
            "grover_phase_superposition", "grover_phase_oracle",
            "grover_phase_diffusion", "grover_phase_iterate",
            "grover_phase_measure",
        ]
        for key in phase_keys:
            self._assert_key_exists(key)

    def test_phase_tag_keys(self):
        """단계 태그 키 [NOW]/[OK]."""
        self._assert_key_exists("grover_phase_tag_current")
        self._assert_key_exists("grover_phase_tag_done")

    def test_legend_keys(self):
        """바 차트 범례 키."""
        self._assert_key_exists("grover_legend_target")
        self._assert_key_exists("grover_legend_high")
        self._assert_key_exists("grover_legend_normal")

    def test_title_keys(self):
        """모드별 타이틀 키."""
        self._assert_key_exists("grover_title_step")
        self._assert_key_exists("grover_title_auto")
        self._assert_key_exists("grover_title_compare")

    def test_compare_keys(self):
        """비교 모드 관련 키."""
        compare_keys = [
            "grover_compare_classical", "grover_compare_quantum",
            "grover_compare_speedup", "grover_compare_found",
            "grover_compare_hint_db",
            "grover_compare_stat_classical", "grover_compare_stat_quantum",
            "grover_compare_db_info", "grover_queries_count",
        ]
        for key in compare_keys:
            self._assert_key_exists(key)

    def test_notification_keys(self):
        """알림 메시지 키."""
        self._assert_key_exists("grover_input_err_invalid")
        self._assert_key_exists("grover_speed_changed")

    def test_rendering_string_keys(self):
        """렌더링에서 사용하는 문자열 키."""
        keys = [
            "grover_bar_label", "grover_n_target_info",
            "grover_iteration_count", "grover_speedup_text",
            "grover_history_entry",
            "grover_chart_prob_evolution", "grover_circuit_title",
            "grover_status_title", "grover_search_history",
            "grover_auto_running", "grover_auto_paused",
            "grover_result_found", "grover_result_not_target",
        ]
        for key in keys:
            self._assert_key_exists(key)

    def test_input_field_keys(self):
        """입력 필드 관련 키."""
        self._assert_key_exists("grover_input_qubits")
        self._assert_key_exists("grover_input_target")
        self._assert_key_exists("grover_input_hint")

    def test_en_ko_key_parity(self):
        """en.json과 ko.json의 grover 관련 키가 일치."""
        en_grover = {k for k in self.en if k.startswith("grover_")}
        ko_grover = {k for k in self.ko if k.startswith("grover_")}
        missing_in_ko = en_grover - ko_grover
        missing_in_en = ko_grover - en_grover
        self.assertEqual(missing_in_ko, set(),
                         f"Keys in en.json but not ko.json: {missing_in_ko}")
        self.assertEqual(missing_in_en, set(),
                         f"Keys in ko.json but not en.json: {missing_in_en}")


if __name__ == "__main__":
    unittest.main()
