"""색맹 친화 모드(Colorblind Mode) 테스트."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestColorblindThemeToggle(unittest.TestCase):
    """theme.py 색맹 모드 토글 API 테스트."""

    def setUp(self):
        from theme import set_colorblind, set_theme
        set_colorblind(False)
        set_theme("dark")

    def tearDown(self):
        from theme import set_colorblind, set_theme
        set_colorblind(False)
        set_theme("dark")

    def test_default_colorblind_off(self):
        from theme import is_colorblind
        self.assertFalse(is_colorblind())

    def test_set_colorblind_on(self):
        from theme import set_colorblind, is_colorblind
        set_colorblind(True)
        self.assertTrue(is_colorblind())

    def test_toggle_colorblind(self):
        from theme import toggle_colorblind, is_colorblind
        result = toggle_colorblind()
        self.assertTrue(result)
        self.assertTrue(is_colorblind())
        result = toggle_colorblind()
        self.assertFalse(result)
        self.assertFalse(is_colorblind())

    def test_get_tk_theme_dark_normal(self):
        from theme import get_tk_theme, TK
        self.assertIs(get_tk_theme(), TK)

    def test_get_tk_theme_dark_colorblind(self):
        from theme import set_colorblind, get_tk_theme, TK_CB
        set_colorblind(True)
        self.assertIs(get_tk_theme(), TK_CB)

    def test_get_tk_theme_light_normal(self):
        from theme import set_theme, get_tk_theme, TK_LIGHT
        set_theme("light")
        self.assertIs(get_tk_theme(), TK_LIGHT)

    def test_get_tk_theme_light_colorblind(self):
        from theme import set_theme, set_colorblind, get_tk_theme, TK_CB_LIGHT
        set_theme("light")
        set_colorblind(True)
        self.assertIs(get_tk_theme(), TK_CB_LIGHT)

    def test_get_pg_theme_dark_normal(self):
        from theme import get_pg_theme, PG
        self.assertIs(get_pg_theme(), PG)

    def test_get_pg_theme_dark_colorblind(self):
        from theme import set_colorblind, get_pg_theme, PG_CB
        set_colorblind(True)
        self.assertIs(get_pg_theme(), PG_CB)

    def test_get_pg_theme_light_colorblind(self):
        from theme import set_theme, set_colorblind, get_pg_theme, PG_CB_LIGHT
        set_theme("light")
        set_colorblind(True)
        self.assertIs(get_pg_theme(), PG_CB_LIGHT)


class TestColorblindPaletteDistinctness(unittest.TestCase):
    """색맹 팔레트의 RED/GREEN이 기본 테마와 다른지 확인."""

    def test_cb_dark_green_differs_from_normal(self):
        from theme import TK, TK_CB
        self.assertNotEqual(TK.GREEN, TK_CB.GREEN)

    def test_cb_dark_red_differs_from_normal(self):
        from theme import TK, TK_CB
        self.assertNotEqual(TK.RED, TK_CB.RED)

    def test_cb_dark_green_is_blue_family(self):
        """색맹 모드 GREEN은 blue 계열이어야 한다."""
        from theme import PG_CB
        r, g, b = PG_CB.GREEN
        self.assertGreater(b, r, "Blue channel should dominate for colorblind green")

    def test_cb_dark_red_is_orange_family(self):
        """색맹 모드 RED는 orange 계열이어야 한다."""
        from theme import PG_CB
        r, g, b = PG_CB.RED
        self.assertGreater(r, b, "Red channel should dominate for colorblind red")

    def test_cb_dark_stable_collapsed_distinguishable(self):
        """STABLE과 COLLAPSED가 충분히 다른 색이어야 한다."""
        from theme import PG_CB
        sr, sg, sb = PG_CB.STABLE
        cr, cg, cb = PG_CB.COLLAPSED
        # 유클리드 거리가 최소 100 이상
        dist = ((sr - cr) ** 2 + (sg - cg) ** 2 + (sb - cb) ** 2) ** 0.5
        self.assertGreater(dist, 100, "STABLE and COLLAPSED must be visually distinct")

    def test_cb_light_green_differs_from_normal(self):
        from theme import TK_LIGHT, TK_CB_LIGHT
        self.assertNotEqual(TK_LIGHT.GREEN, TK_CB_LIGHT.GREEN)

    def test_cb_light_red_differs_from_normal(self):
        from theme import TK_LIGHT, TK_CB_LIGHT
        self.assertNotEqual(TK_LIGHT.RED, TK_CB_LIGHT.RED)

    def test_all_four_qubit_states_distinct(self):
        """4개 큐비트 상태 색상이 모두 서로 다른지 확인."""
        from theme import PG_CB
        states = [PG_CB.STABLE, PG_CB.WARNING, PG_CB.DANGER, PG_CB.COLLAPSED]
        for i, a in enumerate(states):
            for j, b in enumerate(states):
                if i != j:
                    self.assertNotEqual(a, b, f"State {i} and {j} should differ")


class TestColorblindPGAttributes(unittest.TestCase):
    """색맹 PG 클래스가 필수 속성을 모두 가지고 있는지 확인."""

    def test_pg_cb_has_all_pg_attributes(self):
        from theme import PG, PG_CB
        for attr in dir(PG):
            if not attr.startswith("_"):
                self.assertTrue(
                    hasattr(PG_CB, attr),
                    f"PG_CB is missing attribute: {attr}"
                )

    def test_pg_cb_light_has_all_pg_light_attributes(self):
        from theme import PG_LIGHT, PG_CB_LIGHT
        for attr in dir(PG_LIGHT):
            if not attr.startswith("_"):
                self.assertTrue(
                    hasattr(PG_CB_LIGHT, attr),
                    f"PG_CB_LIGHT is missing attribute: {attr}"
                )

    def test_tk_cb_has_all_tk_attributes(self):
        from theme import TK, TK_CB
        for attr in dir(TK):
            if not attr.startswith("_"):
                self.assertTrue(
                    hasattr(TK_CB, attr),
                    f"TK_CB is missing attribute: {attr}"
                )

    def test_tk_cb_light_has_all_tk_light_attributes(self):
        from theme import TK_LIGHT, TK_CB_LIGHT
        for attr in dir(TK_LIGHT):
            if not attr.startswith("_"):
                self.assertTrue(
                    hasattr(TK_CB_LIGHT, attr),
                    f"TK_CB_LIGHT is missing attribute: {attr}"
                )


class TestConfigColorblindMode(unittest.TestCase):
    """config.json의 colorblind_mode 설정 테스트."""

    def test_config_has_accessibility_section(self):
        import json
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.json"
        )
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        self.assertIn("accessibility", config)
        self.assertIn("colorblind_mode", config["accessibility"])
        self.assertIsInstance(config["accessibility"]["colorblind_mode"], bool)

    def test_config_loader_reads_colorblind(self):
        from config_loader import cfg
        result = cfg("accessibility", "colorblind_mode", False)
        self.assertIsInstance(result, bool)


class TestI18nColorblindKeys(unittest.TestCase):
    """i18n 색맹 모드 키가 존재하는지 확인."""

    def test_ko_has_colorblind_keys(self):
        import json
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "locale", "ko.json"
        )
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("colorblind_on", data)
        self.assertIn("colorblind_off", data)

    def test_en_has_colorblind_keys(self):
        import json
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "locale", "en.json"
        )
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("colorblind_on", data)
        self.assertIn("colorblind_off", data)


if __name__ == "__main__":
    unittest.main()
