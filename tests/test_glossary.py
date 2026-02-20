"""glossary.py 종합 테스트 — 용어 사전 오버레이 데이터·필터·이벤트·i18n·통합."""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pygame mock — 다른 테스트에서 이미 설정된 mock이 있을 수 있으므로
# setdefault 후 실제 사용되는 mock에 필요한 속성을 설정한다.
_pg_mock = MagicMock()
_pg_mock.KEYDOWN = 2
_pg_mock.K_g = 103
_pg_mock.K_ESCAPE = 27
_pg_mock.K_SLASH = 47
_pg_mock.K_LEFT = 276
_pg_mock.K_RIGHT = 275
_pg_mock.K_UP = 273
_pg_mock.K_DOWN = 274
_pg_mock.K_PAGEUP = 280
_pg_mock.K_PAGEDOWN = 281
_pg_mock.K_RETURN = 13
_pg_mock.K_BACKSPACE = 8
_pg_mock.K_SPACE = 32
sys.modules.setdefault("pygame", _pg_mock)
sys.modules.setdefault("pygame.time", MagicMock())

# 실제로 glossary.py가 사용하는 pygame mock에 키 상수 보장
_actual_pg = sys.modules["pygame"]
for attr in ("KEYDOWN", "K_g", "K_ESCAPE", "K_SLASH", "K_LEFT", "K_RIGHT",
             "K_UP", "K_DOWN", "K_PAGEUP", "K_PAGEDOWN", "K_RETURN",
             "K_BACKSPACE", "K_SPACE"):
    if not isinstance(getattr(_actual_pg, attr, None), int):
        setattr(_actual_pg, attr, getattr(_pg_mock, attr))

import i18n
from glossary import (
    TERMS_PER_PAGE,
    GlossaryOverlay,
    _CATEGORY_KEYS,
    _TERMS,
)
from quantum.ui_common import wrap_text

# glossary 모듈이 참조하는 실제 pygame 을 _pg_mock 으로 재설정
import glossary as _glossary_mod
_pg_mock = _glossary_mod.pygame  # glossary가 실제 참조하는 mock 사용

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_event(key, unicode_char=""):
    """헬퍼: pygame KEYDOWN 이벤트 mock 생성."""
    ev = MagicMock()
    ev.type = _pg_mock.KEYDOWN
    ev.key = key
    ev.unicode = unicode_char
    return ev


def _reset_i18n():
    i18n._current_locale = "ko"
    i18n._strings = {}
    i18n._fallback = {}


# ── 데이터 무결성 테스트 ─────────────────────────────────


class TestGlossaryData(unittest.TestCase):
    """용어 목록, 카테고리, 상수 검증."""

    def test_term_count(self):
        """38개 용어가 등록되어야 한다."""
        self.assertEqual(len(_TERMS), 38)

    def test_category_count(self):
        """5개 카테고리(All 포함)가 등록되어야 한다."""
        self.assertEqual(len(_CATEGORY_KEYS), 5)
        self.assertEqual(_CATEGORY_KEYS[0], "glossary_cat_all")

    def test_all_terms_have_valid_category(self):
        """모든 용어가 유효한 카테고리에 속해야 한다."""
        valid_cats = set(_CATEGORY_KEYS[1:])  # 'all' 제외
        for tid, tcat in _TERMS:
            self.assertIn(tcat, valid_cats, f"Term '{tid}' has invalid category '{tcat}'")

    def test_term_ids_unique(self):
        """용어 ID가 중복 없어야 한다."""
        ids = [tid for tid, _ in _TERMS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_terms_per_page_positive(self):
        self.assertGreater(TERMS_PER_PAGE, 0)

    def test_category_distribution(self):
        """각 카테고리에 용어가 최소 5개 이상 있어야 한다."""
        from collections import Counter
        counts = Counter(tcat for _, tcat in _TERMS)
        for cat_key in _CATEGORY_KEYS[1:]:
            self.assertGreaterEqual(counts[cat_key], 5,
                                    f"Category {cat_key} has only {counts[cat_key]} terms")

    def test_quantum_category_terms(self):
        """양자역학 카테고리에 핵심 용어가 포함되어야 한다."""
        quantum_ids = {tid for tid, tcat in _TERMS if tcat == "glossary_cat_quantum"}
        for expected in ["superposition", "entanglement", "tunneling", "measurement"]:
            self.assertIn(expected, quantum_ids)

    def test_superconductor_category_terms(self):
        """초전도 카테고리에 핵심 용어가 포함되어야 한다."""
        sc_ids = {tid for tid, tcat in _TERMS if tcat == "glossary_cat_superconductor"}
        for expected in ["cooper_pair", "meissner", "josephson"]:
            self.assertIn(expected, sc_ids)

    def test_computing_category_terms(self):
        """양자 컴퓨팅 카테고리에 핵심 용어가 포함되어야 한다."""
        comp_ids = {tid for tid, tcat in _TERMS if tcat == "glossary_cat_computing"}
        for expected in ["qubit", "shor", "grover", "qec"]:
            self.assertIn(expected, comp_ids)

    def test_crypto_category_terms(self):
        """양자 암호 카테고리에 핵심 용어가 포함되어야 한다."""
        crypto_ids = {tid for tid, tcat in _TERMS if tcat == "glossary_cat_crypto"}
        for expected in ["qkd", "bb84", "e91"]:
            self.assertIn(expected, crypto_ids)


# ── i18n 키 무결성 테스트 ────────────────────────────────


class TestGlossaryLocaleKeys(unittest.TestCase):
    """모든 glossary 용어의 i18n 키가 ko.json과 en.json에 존재하는지 검증."""

    @classmethod
    def setUpClass(cls):
        ko_path = os.path.join(_PROJECT_ROOT, "locale", "ko.json")
        en_path = os.path.join(_PROJECT_ROOT, "locale", "en.json")
        with open(ko_path, encoding="utf-8") as f:
            cls.ko_data = json.load(f)
        with open(en_path, encoding="utf-8") as f:
            cls.en_data = json.load(f)

    def test_all_term_names_in_ko(self):
        for tid, _ in _TERMS:
            key = f"gl_{tid}"
            self.assertIn(key, self.ko_data, f"Missing ko key: {key}")
            self.assertIsInstance(self.ko_data[key], str)
            self.assertGreater(len(self.ko_data[key]), 0)

    def test_all_term_names_in_en(self):
        for tid, _ in _TERMS:
            key = f"gl_{tid}"
            self.assertIn(key, self.en_data, f"Missing en key: {key}")
            self.assertIsInstance(self.en_data[key], str)
            self.assertGreater(len(self.en_data[key]), 0)

    def test_all_term_defs_in_ko(self):
        for tid, _ in _TERMS:
            key = f"gl_{tid}_def"
            self.assertIn(key, self.ko_data, f"Missing ko def key: {key}")
            self.assertGreater(len(self.ko_data[key]), 10,
                               f"Definition too short for {key}")

    def test_all_term_defs_in_en(self):
        for tid, _ in _TERMS:
            key = f"gl_{tid}_def"
            self.assertIn(key, self.en_data, f"Missing en def key: {key}")
            self.assertGreater(len(self.en_data[key]), 10,
                               f"Definition too short for {key}")

    def test_formula_keys_consistent(self):
        """수식 키가 ko/en 양쪽에 모두 있거나 모두 없어야 한다."""
        for tid, _ in _TERMS:
            key = f"gl_{tid}_formula"
            has_ko = key in self.ko_data
            has_en = key in self.en_data
            self.assertEqual(has_ko, has_en,
                             f"Formula key mismatch for '{tid}': ko={has_ko}, en={has_en}")

    def test_at_least_half_have_formulas(self):
        """용어의 절반 이상이 수식을 가져야 한다."""
        formula_count = sum(1 for tid, _ in _TERMS if f"gl_{tid}_formula" in self.en_data)
        self.assertGreaterEqual(formula_count, len(_TERMS) // 2,
                                f"Only {formula_count}/{len(_TERMS)} terms have formulas")

    def test_category_keys_in_both_locales(self):
        for ck in _CATEGORY_KEYS:
            self.assertIn(ck, self.ko_data, f"Missing ko category key: {ck}")
            self.assertIn(ck, self.en_data, f"Missing en category key: {ck}")

    def test_ui_keys_in_both_locales(self):
        """글로서리 UI 키가 양쪽 로케일에 모두 존재해야 한다."""
        ui_keys = [
            "glossary_title", "glossary_search_placeholder", "glossary_no_results",
            "glossary_hint", "glossary_close", "glossary_nav", "glossary_page",
        ]
        for key in ui_keys:
            self.assertIn(key, self.ko_data, f"Missing ko UI key: {key}")
            self.assertIn(key, self.en_data, f"Missing en UI key: {key}")

    def test_ko_definitions_contain_korean(self):
        """한국어 정의에 한글이 포함되어야 한다."""
        import re
        hangul_re = re.compile(r"[가-힣]")
        for tid, _ in _TERMS:
            defn = self.ko_data[f"gl_{tid}_def"]
            self.assertTrue(hangul_re.search(defn),
                            f"Korean def for '{tid}' has no Hangul: {defn[:30]}...")

    def test_en_definitions_ascii_readable(self):
        """영어 정의에 기본 ASCII 문자가 포함되어야 한다."""
        for tid, _ in _TERMS:
            defn = self.en_data[f"gl_{tid}_def"]
            ascii_count = sum(1 for c in defn if c.isascii() and c.isalpha())
            self.assertGreater(ascii_count, 10,
                               f"English def for '{tid}' lacks ASCII: {defn[:30]}...")


# ── GlossaryOverlay 초기화 테스트 ────────────────────────


class TestGlossaryOverlayInit(unittest.TestCase):

    def test_default_state(self):
        g = GlossaryOverlay()
        self.assertFalse(g.visible)
        self.assertEqual(g._cat_idx, 0)
        self.assertEqual(g._page, 0)
        self.assertEqual(g._search_text, "")
        self.assertFalse(g._search_active)

    def test_initial_filtered_is_all_terms(self):
        g = GlossaryOverlay()
        self.assertEqual(len(g._filtered), len(_TERMS))

    def test_multiple_instances_independent(self):
        g1 = GlossaryOverlay()
        g2 = GlossaryOverlay()
        g1.visible = True
        g1._cat_idx = 3
        self.assertFalse(g2.visible)
        self.assertEqual(g2._cat_idx, 0)


# ── 카테고리 필터 테스트 ─────────────────────────────────


class TestGlossaryCategoryFilter(unittest.TestCase):

    def setUp(self):
        _reset_i18n()
        i18n.set_locale("ko")
        self.g = GlossaryOverlay()

    def tearDown(self):
        _reset_i18n()

    def test_all_category_returns_all(self):
        self.g._cat_idx = 0  # All
        self.g._apply_filter()
        self.assertEqual(len(self.g._filtered), len(_TERMS))

    def test_quantum_category_filter(self):
        self.g._cat_idx = 1  # Quantum
        self.g._apply_filter()
        expected = sum(1 for _, c in _TERMS if c == "glossary_cat_quantum")
        self.assertEqual(len(self.g._filtered), expected)
        for tid, tcat in self.g._filtered:
            self.assertEqual(tcat, "glossary_cat_quantum")

    def test_superconductor_category_filter(self):
        self.g._cat_idx = 2  # Superconductor
        self.g._apply_filter()
        expected = sum(1 for _, c in _TERMS if c == "glossary_cat_superconductor")
        self.assertEqual(len(self.g._filtered), expected)

    def test_computing_category_filter(self):
        self.g._cat_idx = 3  # Computing
        self.g._apply_filter()
        expected = sum(1 for _, c in _TERMS if c == "glossary_cat_computing")
        self.assertEqual(len(self.g._filtered), expected)

    def test_crypto_category_filter(self):
        self.g._cat_idx = 4  # Crypto
        self.g._apply_filter()
        expected = sum(1 for _, c in _TERMS if c == "glossary_cat_crypto")
        self.assertEqual(len(self.g._filtered), expected)

    def test_category_switch_resets_page(self):
        self.g._page = 5
        self.g._cat_idx = 2
        self.g._apply_filter()
        self.assertLessEqual(self.g._page, self.g._total_pages() - 1)


# ── 검색 필터 테스트 ─────────────────────────────────────


class TestGlossarySearchFilter(unittest.TestCase):

    def setUp(self):
        _reset_i18n()
        i18n.set_locale("en")
        self.g = GlossaryOverlay()

    def tearDown(self):
        _reset_i18n()

    def test_search_narrows_results(self):
        self.g._search_text = "Cooper"
        self.g._apply_filter()
        self.assertGreater(len(self.g._filtered), 0)
        self.assertLess(len(self.g._filtered), len(_TERMS))

    def test_search_case_insensitive(self):
        self.g._search_text = "cooper"
        self.g._apply_filter()
        lower_count = len(self.g._filtered)
        self.g._search_text = "COOPER"
        self.g._apply_filter()
        upper_count = len(self.g._filtered)
        self.assertEqual(lower_count, upper_count)

    def test_search_matches_name(self):
        self.g._search_text = "Superposition"
        self.g._apply_filter()
        ids = [tid for tid, _ in self.g._filtered]
        self.assertIn("superposition", ids)

    def test_search_matches_definition(self):
        """정의 텍스트에서도 검색이 되어야 한다."""
        self.g._search_text = "phonon"
        self.g._apply_filter()
        ids = [tid for tid, _ in self.g._filtered]
        self.assertIn("cooper_pair", ids)

    def test_search_no_match(self):
        self.g._search_text = "xyznonexistent"
        self.g._apply_filter()
        self.assertEqual(len(self.g._filtered), 0)

    def test_search_empty_returns_all(self):
        self.g._search_text = ""
        self.g._apply_filter()
        self.assertEqual(len(self.g._filtered), len(_TERMS))

    def test_search_with_category_combined(self):
        """카테고리 + 검색 조합 필터링."""
        self.g._cat_idx = 1  # Quantum
        self.g._search_text = "Bell"
        self.g._apply_filter()
        for tid, tcat in self.g._filtered:
            self.assertEqual(tcat, "glossary_cat_quantum")
        ids = [tid for tid, _ in self.g._filtered]
        self.assertIn("bell_state", ids)

    def test_search_korean(self):
        """한국어 검색."""
        i18n.set_locale("ko")
        self.g._search_text = "쿠퍼"
        self.g._apply_filter()
        ids = [tid for tid, _ in self.g._filtered]
        self.assertIn("cooper_pair", ids)

    def test_search_clamps_page(self):
        """검색으로 결과가 줄면 페이지가 유효 범위로 클램프되어야 한다."""
        self.g._page = 100
        self.g._search_text = "qubit"
        self.g._apply_filter()
        self.assertLess(self.g._page, self.g._total_pages())
        self.assertGreaterEqual(self.g._page, 0)

    def test_search_typing_resets_page_to_zero(self):
        """이벤트 핸들러를 통한 검색 타이핑은 페이지를 0으로 리셋해야 한다."""
        self.g.visible = True
        self.g._page = 5
        self.g._search_active = True
        ev = _make_event(ord("q"), "q")
        self.g.handle_event(ev)
        self.assertEqual(self.g._page, 0)


# ── 페이지네이션 테스트 ──────────────────────────────────


class TestGlossaryPagination(unittest.TestCase):

    def setUp(self):
        _reset_i18n()
        i18n.set_locale("en")
        self.g = GlossaryOverlay()
        self.g._apply_filter()

    def tearDown(self):
        _reset_i18n()

    def test_total_pages_correct(self):
        expected = max(1, (len(_TERMS) + TERMS_PER_PAGE - 1) // TERMS_PER_PAGE)
        self.assertEqual(self.g._total_pages(), expected)

    def test_page_items_count(self):
        items = self.g._page_items()
        self.assertEqual(len(items), TERMS_PER_PAGE)

    def test_last_page_items(self):
        self.g._page = self.g._total_pages() - 1
        items = self.g._page_items()
        expected = len(_TERMS) % TERMS_PER_PAGE or TERMS_PER_PAGE
        self.assertEqual(len(items), expected)

    def test_page_clamped_on_filter(self):
        self.g._page = 100
        self.g._apply_filter()
        self.assertLess(self.g._page, self.g._total_pages())

    def test_page_clamped_minimum_zero(self):
        self.g._page = -5
        self.g._apply_filter()
        self.assertGreaterEqual(self.g._page, 0)

    def test_empty_results_single_page(self):
        self.g._search_text = "xyznonexistent"
        self.g._apply_filter()
        self.assertEqual(self.g._total_pages(), 1)
        self.assertEqual(self.g._page, 0)


# ── 이벤트 핸들링 테스트 ─────────────────────────────────


class TestGlossaryEventHandling(unittest.TestCase):

    def setUp(self):
        _reset_i18n()
        i18n.set_locale("en")
        self.g = GlossaryOverlay()

    def tearDown(self):
        _reset_i18n()

    def test_g_key_opens(self):
        ev = _make_event(_pg_mock.K_g)
        consumed = self.g.handle_event(ev)
        self.assertTrue(consumed)
        self.assertTrue(self.g.visible)

    def test_g_key_closes(self):
        self.g.visible = True
        ev = _make_event(_pg_mock.K_g)
        consumed = self.g.handle_event(ev)
        self.assertTrue(consumed)
        self.assertFalse(self.g.visible)

    def test_esc_closes(self):
        self.g.visible = True
        ev = _make_event(_pg_mock.K_ESCAPE)
        consumed = self.g.handle_event(ev)
        self.assertTrue(consumed)
        self.assertFalse(self.g.visible)

    def test_esc_cancels_search_first(self):
        """ESC는 검색 모드를 먼저 취소하고, 오버레이는 열려 있어야 한다."""
        self.g.visible = True
        self.g._search_active = True
        self.g._search_text = "test"
        ev = _make_event(_pg_mock.K_ESCAPE)
        self.g.handle_event(ev)
        self.assertFalse(self.g._search_active)
        self.assertEqual(self.g._search_text, "")
        self.assertTrue(self.g.visible)  # 아직 열려 있음

    def test_slash_activates_search(self):
        self.g.visible = True
        ev = _make_event(_pg_mock.K_SLASH, "/")
        self.g.handle_event(ev)
        self.assertTrue(self.g._search_active)

    def test_search_typing(self):
        self.g.visible = True
        self.g._search_active = True
        for char in "abc":
            ev = _make_event(ord(char), char)
            self.g.handle_event(ev)
        self.assertEqual(self.g._search_text, "abc")

    def test_search_backspace(self):
        self.g.visible = True
        self.g._search_active = True
        self.g._search_text = "abc"
        ev = _make_event(_pg_mock.K_BACKSPACE)
        self.g.handle_event(ev)
        self.assertEqual(self.g._search_text, "ab")

    def test_search_backspace_empty(self):
        self.g.visible = True
        self.g._search_active = True
        self.g._search_text = ""
        ev = _make_event(_pg_mock.K_BACKSPACE)
        self.g.handle_event(ev)
        self.assertEqual(self.g._search_text, "")

    def test_search_enter_exits_search_mode(self):
        self.g.visible = True
        self.g._search_active = True
        self.g._search_text = "test"
        ev = _make_event(_pg_mock.K_RETURN)
        self.g.handle_event(ev)
        self.assertFalse(self.g._search_active)
        self.assertEqual(self.g._search_text, "test")  # 검색어는 유지

    def test_left_right_cycle_category(self):
        self.g.visible = True
        self.g._cat_idx = 0
        ev = _make_event(_pg_mock.K_RIGHT)
        self.g.handle_event(ev)
        self.assertEqual(self.g._cat_idx, 1)

        ev = _make_event(_pg_mock.K_LEFT)
        self.g.handle_event(ev)
        self.assertEqual(self.g._cat_idx, 0)

    def test_category_wraps_around(self):
        self.g.visible = True
        self.g._cat_idx = 0
        ev = _make_event(_pg_mock.K_LEFT)
        self.g.handle_event(ev)
        self.assertEqual(self.g._cat_idx, len(_CATEGORY_KEYS) - 1)

    def test_down_increments_page(self):
        self.g.visible = True
        self.g._apply_filter()
        self.g._page = 0
        ev = _make_event(_pg_mock.K_DOWN)
        self.g.handle_event(ev)
        self.assertEqual(self.g._page, 1)

    def test_up_decrements_page(self):
        self.g.visible = True
        self.g._apply_filter()
        self.g._page = 2
        ev = _make_event(_pg_mock.K_UP)
        self.g.handle_event(ev)
        self.assertEqual(self.g._page, 1)

    def test_up_at_zero_stays(self):
        self.g.visible = True
        self.g._page = 0
        ev = _make_event(_pg_mock.K_UP)
        self.g.handle_event(ev)
        self.assertEqual(self.g._page, 0)

    def test_down_at_last_page_stays(self):
        self.g.visible = True
        self.g._apply_filter()
        self.g._page = self.g._total_pages() - 1
        ev = _make_event(_pg_mock.K_DOWN)
        self.g.handle_event(ev)
        self.assertEqual(self.g._page, self.g._total_pages() - 1)

    def test_pagedown_advances(self):
        self.g.visible = True
        self.g._apply_filter()
        self.g._page = 0
        ev = _make_event(_pg_mock.K_PAGEDOWN)
        self.g.handle_event(ev)
        self.assertEqual(self.g._page, 1)

    def test_non_keydown_ignored(self):
        """KEYDOWN 이외의 이벤트는 무시해야 한다."""
        ev = MagicMock()
        ev.type = 999  # not KEYDOWN
        consumed = self.g.handle_event(ev)
        self.assertFalse(consumed)

    def test_other_keys_consumed_when_visible(self):
        """오버레이 열린 상태에서 다른 키도 소비해야 한다."""
        self.g.visible = True
        ev = _make_event(_pg_mock.K_SPACE)
        consumed = self.g.handle_event(ev)
        self.assertTrue(consumed)

    def test_other_keys_not_consumed_when_hidden(self):
        """오버레이 닫힌 상태에서 G 이외의 키는 소비하지 않아야 한다."""
        self.g.visible = False
        ev = _make_event(_pg_mock.K_SPACE)
        consumed = self.g.handle_event(ev)
        self.assertFalse(consumed)

    def test_g_key_ignored_during_search(self):
        """검색 중 G키는 토글하지 않아야 한다."""
        self.g.visible = True
        self.g._search_active = True
        ev = _make_event(_pg_mock.K_g, "g")
        self.g.handle_event(ev)
        self.assertTrue(self.g.visible)  # 여전히 열려 있음
        self.assertEqual(self.g._search_text, "g")  # 검색어에 추가됨

    def test_slash_ignored_during_search(self):
        """검색 중 / 키는 검색 모드 재활성화하지 않아야 한다."""
        self.g.visible = True
        self.g._search_active = True
        self.g._search_text = "test"
        ev = _make_event(_pg_mock.K_SLASH, "/")
        self.g.handle_event(ev)
        # / is filtered out (unicode == "/"), so text stays same
        self.assertEqual(self.g._search_text, "test")


# ── i18n 통합 테스트 ─────────────────────────────────────


class TestGlossaryI18n(unittest.TestCase):
    """t() 함수를 통한 실제 번역 조회."""

    def setUp(self):
        _reset_i18n()

    def tearDown(self):
        _reset_i18n()

    def test_ko_term_lookup(self):
        i18n.set_locale("ko")
        name = i18n.t("gl_superposition")
        self.assertIn("중첩", name)

    def test_en_term_lookup(self):
        i18n.set_locale("en")
        name = i18n.t("gl_superposition")
        self.assertIn("Superposition", name)

    def test_ko_definition_lookup(self):
        i18n.set_locale("ko")
        defn = i18n.t("gl_tunneling_def")
        self.assertIn("장벽", defn)

    def test_en_definition_lookup(self):
        i18n.set_locale("en")
        defn = i18n.t("gl_tunneling_def")
        self.assertIn("barrier", defn.lower())

    def test_formula_lookup(self):
        i18n.set_locale("en")
        formula = i18n.t("gl_tunneling_formula")
        self.assertIn("exp", formula)

    def test_missing_formula_returns_key(self):
        """존재하지 않는 수식 키는 키 자체를 반환해야 한다."""
        i18n.set_locale("en")
        result = i18n.t("gl_nonexistent_term_formula")
        self.assertEqual(result, "gl_nonexistent_term_formula")

    def test_page_format_string(self):
        i18n.set_locale("en")
        result = i18n.t("glossary_page", page=1, total=5)
        self.assertIn("1", result)
        self.assertIn("5", result)

    def test_search_all_terms_both_locales(self):
        """모든 용어가 양쪽 로케일에서 유효한 문자열을 반환하는지 확인."""
        for locale in ("ko", "en"):
            i18n.set_locale(locale)
            for tid, _ in _TERMS:
                name = i18n.t(f"gl_{tid}")
                defn = i18n.t(f"gl_{tid}_def")
                self.assertNotEqual(name, f"gl_{tid}",
                                    f"Missing {locale} name for {tid}")
                self.assertNotEqual(defn, f"gl_{tid}_def",
                                    f"Missing {locale} def for {tid}")


# ── _wrap_text 유틸리티 테스트 ────────────────────────────


class TestWrapText(unittest.TestCase):

    def test_short_text_no_wrap(self):
        lines = wrap_text("hello world", 50)
        self.assertEqual(lines, ["hello world"])

    def test_long_text_wraps(self):
        text = "a " * 50
        lines = wrap_text(text.strip(), 20)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(len(line), 21)  # word boundary 허용

    def test_empty_text(self):
        lines = wrap_text("", 50)
        self.assertEqual(lines, [])

    def test_single_long_word(self):
        lines = wrap_text("supercalifragilisticexpialidocious", 10)
        self.assertEqual(len(lines), 1)  # 한 단어는 자르지 않음

    def test_exact_fit(self):
        lines = wrap_text("12345 67890", 11)
        self.assertEqual(lines, ["12345 67890"])


# ── 모듈 통합 테스트 ─────────────────────────────────────


class TestGlossaryModuleIntegration(unittest.TestCase):
    """모든 게임 모듈에 GlossaryOverlay가 통합되었는지 확인."""

    MODULES_WITH_GLOSSARY = [
        "quantum/tunneling.py",
        "quantum/entanglement.py",
        "quantum/gate_builder.py",
        "quantum/qec_shield.py",
        "quantum/qubit_chain.py",
        "quantum/shor_algorithm.py",
        "quantum/grover_search.py",
        "physics/josephson_junction.py",
        "physics/flux_pinning.py",
        "physics/cooper_pair.py",
        "physics/phase_transition_sim.py",
        "security/bb84_defense.py",
        "security/squid_mines.py",
        "security/scada_security.py",
        "security/qkd_advanced.py",
    ]

    def test_import_in_all_modules(self):
        for mod in self.MODULES_WITH_GLOSSARY:
            path = os.path.join(_PROJECT_ROOT, mod)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("from glossary import GlossaryOverlay", content,
                          f"Missing import in {mod}")

    def test_init_in_all_modules(self):
        for mod in self.MODULES_WITH_GLOSSARY:
            path = os.path.join(_PROJECT_ROOT, mod)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("glossary = GlossaryOverlay()", content,
                          f"Missing init in {mod}")

    def test_handle_event_in_all_modules(self):
        for mod in self.MODULES_WITH_GLOSSARY:
            path = os.path.join(_PROJECT_ROOT, mod)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("glossary.handle_event(event)", content,
                          f"Missing handle_event in {mod}")

    def test_draw_in_all_modules(self):
        for mod in self.MODULES_WITH_GLOSSARY:
            path = os.path.join(_PROJECT_ROOT, mod)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("glossary.draw(screen,", content,
                          f"Missing draw in {mod}")


# ── 상태 전이 시나리오 테스트 ────────────────────────────


class TestGlossaryStateScenarios(unittest.TestCase):
    """실제 사용 흐름을 모사하는 시나리오 테스트."""

    def setUp(self):
        _reset_i18n()
        i18n.set_locale("en")
        self.g = GlossaryOverlay()

    def tearDown(self):
        _reset_i18n()

    def test_open_search_navigate_close(self):
        """열기 → 검색 → 페이지 이동 → 닫기 전체 흐름."""
        # 열기
        self.g.handle_event(_make_event(_pg_mock.K_g))
        self.assertTrue(self.g.visible)

        # 카테고리 이동
        self.g.handle_event(_make_event(_pg_mock.K_RIGHT))
        self.assertEqual(self.g._cat_idx, 1)

        # 검색 시작
        self.g.handle_event(_make_event(_pg_mock.K_SLASH, "/"))
        self.assertTrue(self.g._search_active)

        # 타이핑
        for c in "qubit":
            self.g.handle_event(_make_event(ord(c), c))
        self.assertEqual(self.g._search_text, "qubit")

        # 검색 확인
        self.g.handle_event(_make_event(_pg_mock.K_RETURN))
        self.assertFalse(self.g._search_active)

        # 닫기
        self.g.handle_event(_make_event(_pg_mock.K_ESCAPE))
        self.assertFalse(self.g.visible)

    def test_open_browse_categories(self):
        """모든 카테고리 순회 후 원점 복귀."""
        self.g.handle_event(_make_event(_pg_mock.K_g))
        for _ in range(len(_CATEGORY_KEYS)):
            self.g.handle_event(_make_event(_pg_mock.K_RIGHT))
        self.assertEqual(self.g._cat_idx, 0)  # 순환 완료 → 원점

    def test_search_clear_restores_all(self):
        """검색 후 ESC로 취소하면 전체 목록이 복원되어야 한다."""
        self.g.handle_event(_make_event(_pg_mock.K_g))

        # 검색
        self.g.handle_event(_make_event(_pg_mock.K_SLASH, "/"))
        for c in "xyz":
            self.g.handle_event(_make_event(ord(c), c))
        self.assertEqual(len(self.g._filtered), 0)

        # ESC로 검색 취소
        self.g.handle_event(_make_event(_pg_mock.K_ESCAPE))
        self.assertEqual(len(self.g._filtered), len(_TERMS))

    def test_reopen_preserves_defaults(self):
        """닫았다 다시 열면 기본 상태로 필터가 적용되어야 한다."""
        self.g.handle_event(_make_event(_pg_mock.K_g))  # 열기
        self.g._cat_idx = 3
        self.g._search_text = "test"
        self.g.handle_event(_make_event(_pg_mock.K_g))  # 닫기
        self.g.handle_event(_make_event(_pg_mock.K_g))  # 다시 열기
        # _apply_filter가 호출되어 현재 상태로 필터가 적용됨
        self.assertTrue(self.g.visible)


if __name__ == "__main__":
    unittest.main()
