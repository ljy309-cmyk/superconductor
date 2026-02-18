"""config_loader 단위 테스트."""

import json
import os
import sys
import tempfile
import unittest

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfigLoader(unittest.TestCase):
    def test_cfg_returns_default_for_missing_key(self):
        from config_loader import cfg

        result = cfg("nonexistent_section", "nonexistent_key", 42)
        self.assertEqual(result, 42)

    def test_cfg_returns_correct_value(self):
        from config_loader import cfg

        fps = cfg("display", "fps", 30)
        self.assertIsInstance(fps, int)
        self.assertGreater(fps, 0)

    def test_cfg_validates_type(self):
        from config_loader import cfg

        port = cfg("server", "port", 18084)
        self.assertIsInstance(port, int)

    def test_cfg_string_value(self):
        from config_loader import cfg

        host = cfg("server", "host", "localhost")
        self.assertIsInstance(host, str)

    def test_cfg_returns_default_for_missing_section(self):
        from config_loader import cfg

        val = cfg("does_not_exist", "key", "fallback")
        self.assertEqual(val, "fallback")

    def test_section_returns_dict(self):
        from config_loader import section

        result = section("display")
        self.assertIsInstance(result, dict)

    def test_section_missing_returns_empty(self):
        from config_loader import section

        result = section("nonexistent")
        self.assertEqual(result, {})

    def test_validate_range(self):
        from config_loader import _validate

        # 유효한 값
        self.assertEqual(_validate("display", "fps", 60), 60)
        # 범위 초과
        self.assertIsNone(_validate("display", "fps", 999))
        # 범위 미달
        self.assertIsNone(_validate("display", "fps", 0))

    def test_validate_unknown_key_passes(self):
        from config_loader import _validate

        # 스키마에 없는 키는 그대로 통과
        self.assertEqual(_validate("display", "unknown", "hello"), "hello")

    def test_reload_config(self):
        from config_loader import cfg, reload_config

        reload_config()
        fps = cfg("display", "fps", 60)
        self.assertIsInstance(fps, int)


class TestConfigLoaderEdgeCases(unittest.TestCase):
    """config_loader 엣지 케이스 — 파일 누락, 잘못된 JSON, 타입 불일치 등."""

    def setUp(self):
        """각 테스트마다 _cache를 초기화하여 격리."""
        import config_loader

        self._orig_cache = config_loader._cache
        self._orig_path = config_loader._CONFIG_PATH

    def tearDown(self):
        import config_loader

        config_loader._cache = self._orig_cache
        config_loader._CONFIG_PATH = self._orig_path

    # ── 파일 누락 ──

    def test_missing_file_returns_default(self):
        """config.json이 없으면 default 반환."""
        import config_loader

        config_loader._cache = None
        config_loader._CONFIG_PATH = "/tmp/_nonexistent_config_12345.json"
        result = config_loader.cfg("display", "fps", 99)
        self.assertEqual(result, 99)

    def test_missing_file_section_returns_empty(self):
        """config.json이 없으면 section()은 빈 dict."""
        import config_loader

        config_loader._cache = None
        config_loader._CONFIG_PATH = "/tmp/_nonexistent_config_12345.json"
        result = config_loader.section("display")
        self.assertEqual(result, {})

    # ── 잘못된 JSON ──

    def test_invalid_json_returns_default(self):
        """JSON 파싱 오류 시 default 반환."""
        import config_loader

        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            os.write(fd, b"{broken json!!")
            os.close(fd)
            config_loader._cache = None
            config_loader._CONFIG_PATH = path
            result = config_loader.cfg("display", "fps", 77)
            self.assertEqual(result, 77)
        finally:
            os.unlink(path)

    def test_empty_file_returns_default(self):
        """빈 파일은 JSON 파싱 실패 → default 반환."""
        import config_loader

        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            os.close(fd)
            config_loader._cache = None
            config_loader._CONFIG_PATH = path
            result = config_loader.cfg("display", "fps", 55)
            self.assertEqual(result, 55)
        finally:
            os.unlink(path)

    # ── 타입 불일치 ──

    def test_string_where_int_expected_returns_default(self):
        """int 필드에 문자열이 들어있으면 default 반환."""
        import config_loader

        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            data = {"display": {"fps": "not_a_number"}}
            os.write(fd, json.dumps(data).encode())
            os.close(fd)
            config_loader._cache = None
            config_loader._CONFIG_PATH = path
            result = config_loader.cfg("display", "fps", 60)
            self.assertEqual(result, 60)
        finally:
            os.unlink(path)

    def test_int_where_bool_expected_returns_default(self):
        """bool 필드에 int(1)이 들어있으면 default 반환 (strict bool)."""
        import config_loader

        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            data = {"accessibility": {"colorblind_mode": 1}}
            os.write(fd, json.dumps(data).encode())
            os.close(fd)
            config_loader._cache = None
            config_loader._CONFIG_PATH = path
            result = config_loader.cfg("accessibility", "colorblind_mode", False)
            self.assertFalse(result)
        finally:
            os.unlink(path)

    def test_bool_true_passes_validation(self):
        """bool 필드에 True가 들어있으면 정상 반환."""
        import config_loader

        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            data = {"accessibility": {"colorblind_mode": True}}
            os.write(fd, json.dumps(data).encode())
            os.close(fd)
            config_loader._cache = None
            config_loader._CONFIG_PATH = path
            result = config_loader.cfg("accessibility", "colorblind_mode", False)
            self.assertTrue(result)
        finally:
            os.unlink(path)

    def test_int_where_str_expected_returns_default(self):
        """str 필드에 int가 들어있으면 default 반환."""
        import config_loader

        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            data = {"server": {"host": 12345}}
            os.write(fd, json.dumps(data).encode())
            os.close(fd)
            config_loader._cache = None
            config_loader._CONFIG_PATH = path
            result = config_loader.cfg("server", "host", "localhost")
            self.assertEqual(result, "localhost")
        finally:
            os.unlink(path)

    def test_float_coerced_to_int(self):
        """int 필드에 float(60.0)이 들어있으면 int로 변환."""
        import config_loader

        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            data = {"display": {"fps": 60.0}}
            os.write(fd, json.dumps(data).encode())
            os.close(fd)
            config_loader._cache = None
            config_loader._CONFIG_PATH = path
            result = config_loader.cfg("display", "fps", 30)
            self.assertEqual(result, 60)
            self.assertIsInstance(result, int)
        finally:
            os.unlink(path)

    # ── 범위 경계값 ──

    def test_value_at_min_boundary_passes(self):
        """정확히 min 값은 통과해야 함."""
        from config_loader import _validate

        self.assertEqual(_validate("display", "fps", 1), 1)

    def test_value_at_max_boundary_passes(self):
        """정확히 max 값은 통과해야 함."""
        from config_loader import _validate

        self.assertEqual(_validate("display", "fps", 240), 240)

    def test_value_below_min_returns_none(self):
        from config_loader import _validate

        self.assertIsNone(_validate("display", "fps", 0))

    def test_value_above_max_returns_none(self):
        from config_loader import _validate

        self.assertIsNone(_validate("display", "fps", 241))

    def test_negative_float_in_range(self):
        """음수 float 범위 검증 (phase_transition.t_range_min)."""
        from config_loader import _validate

        self.assertEqual(_validate("phase_transition", "t_range_min", -200.0), -200.0)
        self.assertIsNone(_validate("phase_transition", "t_range_min", -301.0))
        self.assertIsNone(_validate("phase_transition", "t_range_min", -99.0))

    def test_schema_with_none_max(self):
        """max가 None인 스키마 (ml.random_state) — 상한 없음."""
        from config_loader import _validate

        self.assertEqual(_validate("ml", "random_state", 999999), 999999)
        self.assertIsNone(_validate("ml", "random_state", -1))

    # ── None 값 ──

    def test_null_value_in_json_returns_default(self):
        """JSON에서 null 값이면 default 반환."""
        import config_loader

        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            data = {"display": {"fps": None}}
            os.write(fd, json.dumps(data).encode())
            os.close(fd)
            config_loader._cache = None
            config_loader._CONFIG_PATH = path
            result = config_loader.cfg("display", "fps", 60)
            self.assertEqual(result, 60)
        finally:
            os.unlink(path)

    # ── reload ──

    def test_reload_picks_up_new_values(self):
        """reload_config() 후 변경된 값을 읽어야 함."""
        import config_loader

        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            # 첫 번째 로드
            data = {"display": {"fps": 30}}
            os.write(fd, json.dumps(data).encode())
            os.close(fd)
            config_loader._cache = None
            config_loader._CONFIG_PATH = path
            self.assertEqual(config_loader.cfg("display", "fps", 60), 30)

            # 파일 변경
            with open(path, "w") as f:
                json.dump({"display": {"fps": 120}}, f)
            config_loader.reload_config()
            self.assertEqual(config_loader.cfg("display", "fps", 60), 120)
        finally:
            os.unlink(path)

    # ── 스키마에 없는 섹션/키 ──

    def test_unknown_section_passes_through(self):
        """스키마에 없는 섹션의 값은 검증 없이 그대로 반환."""
        import config_loader

        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            data = {"custom_section": {"my_key": "my_value"}}
            os.write(fd, json.dumps(data).encode())
            os.close(fd)
            config_loader._cache = None
            config_loader._CONFIG_PATH = path
            result = config_loader.cfg("custom_section", "my_key", "fallback")
            self.assertEqual(result, "my_value")
        finally:
            os.unlink(path)

    def test_nested_section_not_dict_returns_default(self):
        """섹션 값이 dict가 아닌 경우 default 반환."""
        import config_loader

        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            data = {"display": "not_a_dict"}
            os.write(fd, json.dumps(data).encode())
            os.close(fd)
            config_loader._cache = None
            config_loader._CONFIG_PATH = path
            result = config_loader.cfg("display", "fps", 60)
            self.assertEqual(result, 60)
        finally:
            os.unlink(path)


class TestI18n(unittest.TestCase):
    def test_set_locale_ko(self):
        from i18n import set_locale, t

        set_locale("ko")
        result = t("menu_title")
        self.assertEqual(result, "메뉴를 선택하세요")

    def test_set_locale_en(self):
        from i18n import set_locale, t

        set_locale("en")
        result = t("menu_title")
        self.assertEqual(result, "Select a menu")
        set_locale("ko")  # 원복

    def test_missing_key_returns_key(self):
        from i18n import t

        result = t("this_key_does_not_exist")
        self.assertEqual(result, "this_key_does_not_exist")

    def test_format_variables(self):
        from i18n import set_locale, t

        set_locale("ko")
        result = t("target_temp", temp=-196.0)
        self.assertIn("-196.00", result)

    def test_get_locale(self):
        from i18n import get_locale, set_locale

        set_locale("en")
        self.assertEqual(get_locale(), "en")
        set_locale("ko")
        self.assertEqual(get_locale(), "ko")


class TestTheme(unittest.TestCase):
    def test_tk_colors_are_hex(self):
        from theme import TK

        self.assertTrue(TK.BG.startswith("#"))
        self.assertEqual(len(TK.BG), 7)

    def test_pg_colors_are_tuples(self):
        from theme import PG

        self.assertIsInstance(PG.BG, tuple)
        self.assertEqual(len(PG.BG), 3)
        for c in PG.BG:
            self.assertIsInstance(c, int)
            self.assertGreaterEqual(c, 0)
            self.assertLessEqual(c, 255)

    def test_fonts_defined(self):
        from theme import FONTS

        self.assertEqual(FONTS.FAMILY, "Consolas")
        self.assertIsInstance(FONTS.TITLE, tuple)


class TestPresets(unittest.TestCase):
    def test_get_preset_returns_dict(self):
        from presets import get_preset

        easy = get_preset("easy")
        self.assertIsInstance(easy, dict)
        self.assertIn("qubit_chain", easy)

    def test_list_presets(self):
        from presets import list_presets

        presets = list_presets()
        self.assertIn("easy", presets)
        self.assertIn("normal", presets)
        self.assertIn("hard", presets)

    def test_preset_has_correct_structure(self):
        from presets import get_preset

        normal = get_preset("normal")
        self.assertIn("bb84", normal)
        self.assertIn("eve_chance", normal["bb84"])

    def test_save_load_profile(self):

        from presets import list_profiles, load_profile, save_profile

        test_data = {"noise_rate": 5.0, "sensitivity": 3.0}
        save_profile("_test_profile", test_data)

        loaded = load_profile("_test_profile")
        self.assertEqual(loaded["noise_rate"], 5.0)
        self.assertEqual(loaded["sensitivity"], 3.0)

        profiles = list_profiles()
        self.assertIn("_test_profile", profiles)

        # 정리
        from presets import PROFILES_DIR

        os.remove(os.path.join(PROFILES_DIR, "_test_profile.json"))


class TestCooler(unittest.TestCase):
    def test_cooler_state_initial(self):
        from scada.cooler import CoolerState

        state = CoolerState(
            temperature=25.0,
            target=-196.0,
            cooling_on=False,
            emergency=False,
            running=False,
        )
        self.assertEqual(state.temperature, 25.0)
        self.assertFalse(state.cooling_on)
        self.assertFalse(state.emergency)

    def test_cooler_state_target(self):
        from scada.cooler import CoolerState

        state = CoolerState(
            temperature=25.0,
            target=-196.0,
            cooling_on=False,
            emergency=False,
            running=False,
        )
        self.assertAlmostEqual(state.target, -196.0)


class TestReport(unittest.TestCase):
    def test_text_report_generation(self):
        import shutil
        import tempfile

        from report import _generate_text_report

        tmpdir = tempfile.mkdtemp()
        try:
            data = {"score": 100, "total_sent": 50, "accuracy": 0.85}
            path = _generate_text_report("bb84_defense", data, output_dir=tmpdir)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("BB84", content)
            self.assertIn("100", content)
        finally:
            shutil.rmtree(tmpdir)


if __name__ == "__main__":
    unittest.main()
