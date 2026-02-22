"""i18n.py 종합 테스트 — 로케일 전환, t() 조회, fallback, 리스너."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import i18n

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _reset_i18n_state():
    """테스트 간 i18n 모듈 상태 초기화."""
    i18n._current_locale = "ko"
    i18n._strings = {}
    i18n._fallback = {}
    i18n._locale_listeners.clear()


class TestSetGetLocale(unittest.TestCase):
    """set_locale / get_locale 기본 동작."""

    def setUp(self):
        _reset_i18n_state()

    def tearDown(self):
        _reset_i18n_state()

    def test_default_locale_is_ko(self):
        self.assertEqual(i18n.get_locale(), "ko")

    def test_set_locale_en(self):
        i18n.set_locale("en")
        self.assertEqual(i18n.get_locale(), "en")

    def test_set_locale_ko(self):
        i18n.set_locale("en")
        i18n.set_locale("ko")
        self.assertEqual(i18n.get_locale(), "ko")

    def test_set_same_locale_when_loaded_no_reload(self):
        """이미 로드된 동일 로케일 재설정 시 중복 로드하지 않아야 한다."""
        i18n.set_locale("ko")
        original_strings = i18n._strings
        i18n.set_locale("ko")  # 같은 로케일 + _strings 이미 있음
        self.assertIs(i18n._strings, original_strings)


class TestToggleLocale(unittest.TestCase):
    """toggle_locale 테스트."""

    def setUp(self):
        _reset_i18n_state()
        i18n.set_locale("ko")

    def tearDown(self):
        _reset_i18n_state()

    def test_toggle_ko_to_en(self):
        result = i18n.toggle_locale()
        self.assertEqual(result, "en")
        self.assertEqual(i18n.get_locale(), "en")

    def test_toggle_en_to_ko(self):
        i18n.set_locale("en")
        result = i18n.toggle_locale()
        self.assertEqual(result, "ko")
        self.assertEqual(i18n.get_locale(), "ko")

    def test_toggle_round_trip(self):
        i18n.toggle_locale()  # ko → en
        i18n.toggle_locale()  # en → ko
        self.assertEqual(i18n.get_locale(), "ko")


class TestTranslationLookup(unittest.TestCase):
    """t() 함수 — 키 조회, 포맷 변수, fallback."""

    def setUp(self):
        _reset_i18n_state()

    def tearDown(self):
        _reset_i18n_state()

    def test_t_returns_korean_by_default(self):
        i18n.set_locale("ko")
        result = i18n.t("menu_title")
        self.assertIn("메뉴", result)

    def test_t_returns_english(self):
        i18n.set_locale("en")
        result = i18n.t("menu_title")
        self.assertIn("Select", result)

    def test_t_missing_key_returns_key(self):
        """존재하지 않는 키는 키 자체를 반환해야 한다."""
        i18n.set_locale("ko")
        result = i18n.t("this_key_does_not_exist_xyz")
        self.assertEqual(result, "this_key_does_not_exist_xyz")

    def test_t_fallback_to_ko(self):
        """영어 로케일에서 키가 없으면 한국어 fallback을 사용해야 한다."""
        i18n.set_locale("en")
        # en.json에 없고 ko.json에만 있는 키를 찾기 위해 직접 확인
        ko_path = os.path.join(_PROJECT_ROOT, "locale", "ko.json")
        en_path = os.path.join(_PROJECT_ROOT, "locale", "en.json")
        with open(ko_path, encoding="utf-8") as f:
            ko_data = json.load(f)
        with open(en_path, encoding="utf-8") as f:
            en_data = json.load(f)
        # ko에만 있는 키 찾기
        ko_only_keys = set(ko_data.keys()) - set(en_data.keys())
        if ko_only_keys:  # pragma: no cover
            key = next(iter(ko_only_keys))
            result = i18n.t(key)
            self.assertEqual(result, ko_data[key])
        else:
            # 모든 키가 양쪽에 있으면 — fallback 메커니즘 직접 테스트
            i18n._strings.pop("menu_title", None)
            result = i18n.t("menu_title")
            # fallback (ko)에서 가져와야 함
            self.assertIn("메뉴", result)

    def test_t_no_fallback_for_ko_locale(self):
        """ko 로케일일 때는 fallback이 비어 있어야 한다."""
        i18n.set_locale("ko")
        self.assertEqual(i18n._fallback, {})

    def test_t_format_kwargs(self):
        """포맷 변수 치환이 작동해야 한다."""
        i18n.set_locale("ko")
        # _strings에 직접 테스트 키 추가
        i18n._strings["_test_fmt"] = "결과: {score}점"
        result = i18n.t("_test_fmt", score=100)
        self.assertEqual(result, "결과: 100점")

    def test_t_format_missing_kwarg_no_crash(self):
        """포맷 변수가 부족해도 에러 없이 원문을 반환해야 한다."""
        i18n.set_locale("ko")
        i18n._strings["_test_fmt2"] = "이름: {name}, 점수: {score}"
        result = i18n.t("_test_fmt2", name="홍길동")
        # KeyError 때문에 포맷 실패 → 원본 반환
        self.assertEqual(result, "이름: {name}, 점수: {score}")

    def test_t_format_extra_kwarg_ignored(self):
        """불필요한 kwarg는 무시되어야 한다."""
        i18n.set_locale("ko")
        i18n._strings["_test_fmt3"] = "값: {v}"
        result = i18n.t("_test_fmt3", v=42, extra="ignored")
        self.assertEqual(result, "값: 42")

    def test_t_auto_loads_when_strings_empty(self):
        """_strings가 비어 있으면 t()가 자동으로 set_locale을 호출해야 한다."""
        i18n._strings = {}
        i18n._current_locale = "ko"
        result = i18n.t("menu_title")
        self.assertNotEqual(result, "menu_title")  # 키가 아닌 번역 반환


class TestLocaleListeners(unittest.TestCase):
    """on_locale_change / off_locale_change 리스너 테스트."""

    def setUp(self):
        _reset_i18n_state()

    def tearDown(self):
        _reset_i18n_state()

    def test_listener_called_on_set_locale(self):
        calls = []
        i18n.on_locale_change(lambda: calls.append("called"))
        i18n.set_locale("en")
        self.assertEqual(calls, ["called"])

    def test_listener_called_on_toggle(self):
        calls = []
        i18n.set_locale("ko")
        i18n.on_locale_change(lambda: calls.append("toggled"))
        i18n.toggle_locale()
        self.assertEqual(calls, ["toggled"])

    def test_off_locale_change_removes_listener(self):
        calls = []

        def fn():  # pragma: no cover
            calls.append(1)

        i18n.on_locale_change(fn)
        i18n.off_locale_change(fn)
        i18n.set_locale("en")
        self.assertEqual(calls, [])

    def test_off_nonexistent_no_error(self):
        """등록되지 않은 콜백 제거 시 에러 없이 통과."""
        i18n.off_locale_change(lambda: None)

    def test_duplicate_listener_prevented(self):
        calls = []

        def fn():
            calls.append(1)

        i18n.on_locale_change(fn)
        i18n.on_locale_change(fn)  # 중복
        i18n.set_locale("en")
        self.assertEqual(len(calls), 1)

    def test_multiple_listeners(self):
        results = []
        i18n.on_locale_change(lambda: results.append("A"))
        i18n.on_locale_change(lambda: results.append("B"))
        i18n.set_locale("en")
        self.assertIn("A", results)
        self.assertIn("B", results)

    def test_listener_error_does_not_block_others(self):
        """한 리스너가 실패해도 나머지가 호출되어야 한다."""
        results = []

        def bad():
            raise RuntimeError("fail")

        i18n.on_locale_change(bad)
        i18n.on_locale_change(lambda: results.append("ok"))
        i18n.set_locale("en")
        self.assertEqual(results, ["ok"])


class TestLocaleFileIntegrity(unittest.TestCase):
    """로케일 JSON 파일의 구조적 무결성 검증."""

    def test_ko_json_is_valid(self):
        path = os.path.join(_PROJECT_ROOT, "locale", "ko.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)
        self.assertGreater(len(data), 0)

    def test_en_json_is_valid(self):
        path = os.path.join(_PROJECT_ROOT, "locale", "en.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)
        self.assertGreater(len(data), 0)

    def test_en_covers_most_ko_keys(self):
        """영어 번역이 한국어 키의 대부분을 커버해야 한다."""
        ko_path = os.path.join(_PROJECT_ROOT, "locale", "ko.json")
        en_path = os.path.join(_PROJECT_ROOT, "locale", "en.json")
        with open(ko_path, encoding="utf-8") as f:
            ko_keys = set(json.load(f).keys())
        with open(en_path, encoding="utf-8") as f:
            en_keys = set(json.load(f).keys())
        coverage = len(en_keys & ko_keys) / len(ko_keys)
        self.assertGreater(coverage, 0.8, f"영어 번역 커버리지 {coverage:.0%} < 80%")

    def test_all_values_are_strings(self):
        """모든 로케일 값이 문자열이어야 한다."""
        for locale in ("ko", "en"):
            path = os.path.join(_PROJECT_ROOT, "locale", f"{locale}.json")
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                self.assertIsInstance(v, str, f"{locale}.json[{k}] is {type(v).__name__}, not str")

    def test_supported_locales_list(self):
        self.assertIn("ko", i18n.SUPPORTED_LOCALES)
        self.assertIn("en", i18n.SUPPORTED_LOCALES)


class TestLoadLocaleEdgeCases(unittest.TestCase):
    """_load_locale 엣지 케이스."""

    def test_nonexistent_locale_returns_empty(self):
        result = i18n._load_locale("zz_nonexistent")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
