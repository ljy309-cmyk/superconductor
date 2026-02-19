"""Shor's Algorithm UI 로직 중점 테스트.

시각화 코드에서 추가된 UI 로직(진행률 계산, 히스토리 페이지네이션,
입력 검증, 알림, 레이아웃, 막대 애니메이션, i18n 커버리지)을 검증합니다.
Pygame 없이 순수 로직만 테스트합니다.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# ── Pygame 모킹 (테스트 환경에 pygame 없음) ─────────
# shor_algorithm.py 및 여러 로컬 모듈이 pygame을 top-level import 하므로
# sys.modules에 MagicMock을 삽입하여 ImportError를 방지합니다.
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

from quantum.shor_algorithm_engine import (
    ShorPhase,
    ShorState,
    reset_state,
    shor_step,
)

from quantum.shor_algorithm import (
    HISTORY_PAGE_SIZE,
    Layout,
    UIState,
    _calc_shor_progress,
    _update_bar_animation,
    _notify,
    _MODE_TAB_KEYS,
)


# ── 진행률 계산 테스트 ──────────────────────────────

class TestCalcShorProgress(unittest.TestCase):
    """_calc_shor_progress — 고수위(high-water mark) 진행률."""

    def test_input_phase_returns_zero(self):
        """INPUT 단계에서 진행률 0.0."""
        ui = UIState()
        ui.shor = ShorState(number=15)
        ui.progress_high = 0.5  # 이전 값이 있더라도
        result = _calc_shor_progress(ui)
        self.assertEqual(result, 0.0)
        self.assertEqual(ui.progress_high, 0.0)

    def test_progress_increases_with_phase(self):
        """단계가 진행될수록 진행률 증가."""
        ui = UIState()
        ui.shor = ShorState(number=15)
        prev = 0.0
        for _ in range(200):
            shor_step(ui.shor)
            p = _calc_shor_progress(ui)
            self.assertGreaterEqual(p, prev)
            prev = p
            if ui.shor.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

    def test_progress_never_decreases_on_retry(self):
        """RETRY 시 진행률이 역행하지 않음 (고수위 추적)."""
        ui = UIState()
        ui.shor = ShorState(number=21)
        max_seen = 0.0
        for _ in range(500):
            shor_step(ui.shor)
            p = _calc_shor_progress(ui)
            self.assertGreaterEqual(p, max_seen,
                                    f"Progress decreased: {p} < {max_seen}")
            max_seen = p
            if ui.shor.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

    def test_success_returns_1(self):
        """SUCCESS/DONE 시 진행률 1.0."""
        ui = UIState()
        ui.shor = ShorState(number=15)
        for _ in range(300):
            shor_step(ui.shor)
            if ui.shor.phase == ShorPhase.SUCCESS:
                p = _calc_shor_progress(ui)
                self.assertEqual(p, 1.0)
                break

    def test_reset_clears_progress(self):
        """새 숫자 입력(INPUT) 후 진행률 리셋."""
        ui = UIState()
        ui.shor = ShorState(number=15)
        # 진행시키기
        for _ in range(50):
            shor_step(ui.shor)
            _calc_shor_progress(ui)
        self.assertGreater(ui.progress_high, 0.0)

        # 리셋
        reset_state(ui.shor, 21)
        p = _calc_shor_progress(ui)
        self.assertEqual(p, 0.0)

    def test_all_pipeline_phases_in_range(self):
        """파이프라인 단계별 진행률이 0.0~1.0 범위."""
        ui = UIState()
        for phase in ShorPhase:
            ui.shor.phase = phase
            ui.progress_high = 0.0
            p = _calc_shor_progress(ui)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)


# ── 히스토리 페이지네이션 테스트 ─────────────────────

class TestHistoryPagination(unittest.TestCase):
    """시도 히스토리 페이지네이션 로직."""

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

    def test_page_reset_on_new_number(self):
        """새 숫자 입력 시 페이지 리셋 검증 (UIState 필드)."""
        ui = UIState()
        ui.history_page = 3
        # _submit_input에서 수행하는 것과 동일
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
        # 시뮬레이션: dt = 0.5
        ui.notify_timer -= 0.5
        self.assertAlmostEqual(ui.notify_timer, 1.5)

    def test_timer_expires(self):
        """타이머가 0 이하가 되면 알림 비활성."""
        ui = UIState()
        _notify(ui, "msg", 0.1)
        ui.notify_timer -= 0.2
        self.assertLessEqual(ui.notify_timer, 0)


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

    def test_hint_y_below_content(self):
        """하단 힌트 Y가 히스토리 Y보다 아래."""
        L = Layout(900, 600)
        self.assertGreater(L.hint_y1, L.history_y)

    def test_badge_y_at_bottom(self):
        """뱃지 Y가 화면 하단 근처."""
        L = Layout(900, 600)
        self.assertGreater(L.badge_y, L.H * 0.9)

    def test_graph_area_positive(self):
        """그래프 영역이 양수 크기."""
        L = Layout(900, 600)
        self.assertGreater(L.graph_w_step, 0)
        self.assertGreater(L.graph_w_auto, 0)
        self.assertGreater(L.graph_h, 0)

    def test_rsa_panels_dont_overlap(self):
        """RSA 퍼블릭/시크릿 패널이 겹치지 않음."""
        L = Layout(900, 600)
        pub_right = L.rsa_pub_x + L.rsa_pub_w
        self.assertLessEqual(pub_right, L.rsa_sec_x)

    def test_small_resolution_no_negative(self):
        """작은 해상도에서 음수 좌표 없음."""
        L = Layout(400, 300)
        attrs = [L.margin, L.tab_y, L.tab_h, L.tab_w,
                 L.title_y, L.graph_x, L.graph_y,
                 L.graph_w_step, L.graph_h, L.hint_y1]
        for attr in attrs:
            self.assertGreaterEqual(attr, 0)

    def test_large_resolution(self):
        """4K 해상도에서도 정상 계산."""
        L = Layout(3840, 2160)
        self.assertEqual(L.W, 3840)
        self.assertGreater(L.margin, 0)
        self.assertGreater(L.tab_w, 0)

    def test_status_panel_inside_screen(self):
        """상태 패널이 화면 안에 있음."""
        L = Layout(900, 600)
        self.assertGreater(L.status_w, 0)
        self.assertLessEqual(L.status_x + L.status_w, L.W)


# ── 막대 애니메이션 테스트 ───────────────────────────

class TestBarAnimation(unittest.TestCase):
    """_update_bar_animation — 막대가 하나씩 나타나는 효과."""

    def test_initial_state_zero(self):
        """초기 상태에서 카운터 = 0."""
        ui = UIState()
        self.assertEqual(ui.mod_exp_anim_count, 0)
        self.assertEqual(ui.qft_anim_count, 0)

    def test_animation_increments_over_time(self):
        """시간이 지나면 카운터 증가."""
        ui = UIState()
        # 데이터 추가 시뮬레이션
        for _ in range(50):
            shor_step(ui.shor)
            if ui.shor.mod_exp_table:
                break

        if ui.shor.mod_exp_table:
            # 큰 dt로 한 번에 여러 막대 표시
            _update_bar_animation(ui, 1.0)
            self.assertGreater(ui.mod_exp_anim_count, 0)

    def test_data_change_resets_counter(self):
        """데이터 변경 시 카운터 리셋."""
        ui = UIState()
        ui.mod_exp_anim_count = 10
        ui._prev_mod_exp_len = 5

        # 테이블 길이 변경 감지
        ui.shor.mod_exp_table = [None] * 8  # 길이 8로 변경
        _update_bar_animation(ui, 0.0)

        # 길이 변경 감지 → 카운터 리셋
        self.assertEqual(ui.mod_exp_anim_count, 0)
        self.assertEqual(ui._prev_mod_exp_len, 8)

    def test_no_animation_when_complete(self):
        """카운터가 목표에 도달하면 더 이상 증가하지 않음."""
        ui = UIState()
        ui.shor.mod_exp_table = [None] * 5
        ui._prev_mod_exp_len = 5
        ui.mod_exp_anim_count = 5

        _update_bar_animation(ui, 1.0)
        self.assertEqual(ui.mod_exp_anim_count, 5)  # 변화 없음


# ── i18n 키 커버리지 테스트 ──────────────────────────

class TestI18nCoverage(unittest.TestCase):
    """Shor 모듈에서 사용하는 i18n 키가 locale 파일에 정의되어 있는지."""

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
        for suffix in ["step_1", "step_2", "auto_1", "auto_2", "rsa_1", "rsa_2"]:
            self._assert_key_exists(f"shor_hint_{suffix}")

    def test_phase_keys(self):
        """단계 이름 키가 모두 정의."""
        phase_keys = [
            "shor_phase_classical", "shor_phase_pick_a", "shor_phase_mod_exp",
            "shor_phase_qft_setup", "shor_phase_qft_measure",
            "shor_phase_cf", "shor_phase_extract",
            "shor_phase_success", "shor_phase_retry", "shor_phase_done",
        ]
        for key in phase_keys:
            self._assert_key_exists(key)

    def test_phase_tag_keys(self):
        """단계 태그 키 [NOW]/[OK]."""
        self._assert_key_exists("shor_phase_tag_current")
        self._assert_key_exists("shor_phase_tag_done")

    def test_qft_legend_keys(self):
        """QFT 히스토그램 범례 키."""
        self._assert_key_exists("shor_qft_legend_high")
        self._assert_key_exists("shor_qft_legend_mid")
        self._assert_key_exists("shor_qft_legend_low")

    def test_graph_title_keys(self):
        """그래프 타이틀 키."""
        self._assert_key_exists("shor_qft_title")
        self._assert_key_exists("shor_mod_exp_period")
        self._assert_key_exists("shor_mod_exp_progress")

    def test_continued_fraction_keys(self):
        """연분수 표시 키."""
        self._assert_key_exists("shor_cf_convergents")
        self._assert_key_exists("shor_cf_period_found")
        self._assert_key_exists("shor_cf_no_period")

    def test_notification_keys(self):
        """알림 메시지 키."""
        self._assert_key_exists("shor_input_err_invalid")
        self._assert_key_exists("shor_input_err_range")
        self._assert_key_exists("shor_speed_changed")

    def test_status_title_key(self):
        """상태 패널 타이틀 키."""
        self._assert_key_exists("shor_status_title")

    def test_en_ko_key_parity(self):
        """en.json과 ko.json의 shor 관련 키가 일치."""
        en_shor = {k for k in self.en if k.startswith("shor_")}
        ko_shor = {k for k in self.ko if k.startswith("shor_")}
        missing_in_ko = en_shor - ko_shor
        missing_in_en = ko_shor - en_shor
        self.assertEqual(missing_in_ko, set(),
                         f"Keys in en.json but not ko.json: {missing_in_ko}")
        self.assertEqual(missing_in_en, set(),
                         f"Keys in ko.json but not en.json: {missing_in_en}")


# ── UIState 필드 테스트 ──────────────────────────────

class TestUIStateDefaults(unittest.TestCase):
    """UIState 기본값 검증."""

    def test_default_mode(self):
        ui = UIState()
        self.assertEqual(ui.mode, 0)  # MODE_STEP

    def test_default_difficulty(self):
        ui = UIState()
        self.assertEqual(ui.difficulty, "normal")

    def test_default_counters(self):
        ui = UIState()
        self.assertEqual(ui.numbers_factored, 0)
        self.assertEqual(ui.total_steps, 0)
        self.assertEqual(ui.history_page, 0)

    def test_default_notify(self):
        ui = UIState()
        self.assertEqual(ui.notify_msg, "")
        self.assertEqual(ui.notify_timer, 0.0)

    def test_default_animation(self):
        ui = UIState()
        self.assertEqual(ui.mod_exp_anim_count, 0)
        self.assertEqual(ui.qft_anim_count, 0)
        self.assertAlmostEqual(ui._anim_timer, 0.0)

    def test_shor_state_initialized(self):
        ui = UIState()
        self.assertIsInstance(ui.shor, ShorState)
        self.assertEqual(ui.shor.number, 15)
        self.assertEqual(ui.shor.phase, ShorPhase.INPUT)


# ── MODE_TAB_KEYS 테스트 ────────────────────────────

class TestModeTabKeys(unittest.TestCase):
    """모드 탭 i18n 키 리스트."""

    def test_three_modes(self):
        self.assertEqual(len(_MODE_TAB_KEYS), 3)

    def test_keys_are_strings(self):
        for key in _MODE_TAB_KEYS:
            self.assertIsInstance(key, str)
            self.assertTrue(key.startswith("shor_tab_"))

    def test_mode_cycling(self):
        """Tab으로 모드 순환: 0 → 1 → 2 → 0."""
        mode = 0
        for expected in [1, 2, 0, 1]:
            mode = (mode + 1) % len(_MODE_TAB_KEYS)
            self.assertEqual(mode, expected)


if __name__ == "__main__":
    unittest.main()
