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
        from config_loader import reload_config, cfg
        reload_config()
        fps = cfg("display", "fps", 60)
        self.assertIsInstance(fps, int)


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
        from i18n import set_locale, get_locale
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
        from presets import save_profile, load_profile, list_profiles
        import shutil

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
            temperature=25.0, target=-196.0,
            cooling_on=False, emergency=False, running=False,
        )
        self.assertEqual(state.temperature, 25.0)
        self.assertFalse(state.cooling_on)
        self.assertFalse(state.emergency)

    def test_cooler_state_target(self):
        from scada.cooler import CoolerState
        state = CoolerState(
            temperature=25.0, target=-196.0,
            cooling_on=False, emergency=False, running=False,
        )
        self.assertAlmostEqual(state.target, -196.0)


class TestReport(unittest.TestCase):

    def test_text_report_generation(self):
        from report import _generate_text_report
        import tempfile, shutil

        tmpdir = tempfile.mkdtemp()
        try:
            data = {"score": 100, "total_sent": 50, "accuracy": 0.85}
            path = _generate_text_report("bb84_defense", data, output_dir=tmpdir)
            self.assertTrue(os.path.exists(path))
            with open(path, "r") as f:
                content = f.read()
            self.assertIn("BB84", content)
            self.assertIn("100", content)
        finally:
            shutil.rmtree(tmpdir)


if __name__ == "__main__":
    unittest.main()
