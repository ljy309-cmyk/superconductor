"""theme.py 종합 테스트 — 테마 전환, 리스너, 폰트 스케일, load_pg_colors, 설정 저장/로드."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import theme


def _reset_theme_state():
    """테스트 간 theme 모듈 상태 초기화."""
    theme._current_theme = "dark"
    theme._colorblind = False
    theme._font_scale = 1.0
    theme._listeners.clear()


class TestGetSetTheme(unittest.TestCase):
    """get_theme / set_theme / toggle_theme 기본 동작."""

    def setUp(self):
        _reset_theme_state()

    def tearDown(self):
        _reset_theme_state()

    def test_default_theme_is_dark(self):
        self.assertEqual(theme.get_theme(), "dark")

    def test_set_theme_light(self):
        theme.set_theme("light")
        self.assertEqual(theme.get_theme(), "light")

    def test_set_theme_dark(self):
        theme.set_theme("light")
        theme.set_theme("dark")
        self.assertEqual(theme.get_theme(), "dark")

    def test_set_same_theme_no_notify(self):
        """같은 테마 설정 시 리스너가 호출되지 않아야 한다."""
        calls = []
        theme.on_theme_change(lambda: calls.append(1))
        theme.set_theme("dark")  # 이미 dark → 무변경
        self.assertEqual(len(calls), 0)

    def test_toggle_theme(self):
        result = theme.toggle_theme()
        self.assertEqual(result, "light")
        self.assertEqual(theme.get_theme(), "light")
        result = theme.toggle_theme()
        self.assertEqual(result, "dark")
        self.assertEqual(theme.get_theme(), "dark")


class TestThemeListeners(unittest.TestCase):
    """on_theme_change / off_theme_change / _notify_listeners 테스트."""

    def setUp(self):
        _reset_theme_state()

    def tearDown(self):
        _reset_theme_state()

    def test_listener_called_on_set_theme(self):
        calls = []
        theme.on_theme_change(lambda: calls.append("set"))
        theme.set_theme("light")
        self.assertEqual(calls, ["set"])

    def test_listener_called_on_toggle(self):
        calls = []
        theme.on_theme_change(lambda: calls.append("toggle"))
        theme.toggle_theme()
        self.assertEqual(calls, ["toggle"])

    def test_listener_called_on_colorblind_toggle(self):
        calls = []
        theme.on_theme_change(lambda: calls.append("cb"))
        theme.set_colorblind(True)
        self.assertEqual(calls, ["cb"])

    def test_listener_called_on_font_scale(self):
        calls = []
        theme.on_theme_change(lambda: calls.append("font"))
        theme.set_font_scale(1.2)
        self.assertEqual(calls, ["font"])

    def test_off_theme_change_removes_listener(self):
        calls = []

        def fn():  # pragma: no cover
            calls.append(1)

        theme.on_theme_change(fn)
        theme.off_theme_change(fn)
        theme.toggle_theme()
        self.assertEqual(calls, [])

    def test_off_nonexistent_listener_no_error(self):
        """등록되지 않은 콜백 제거 시 에러가 나지 않아야 한다."""
        theme.off_theme_change(lambda: None)  # 에러 없이 통과

    def test_duplicate_listener_prevented(self):
        calls = []

        def fn():
            calls.append(1)

        theme.on_theme_change(fn)
        theme.on_theme_change(fn)  # 중복 등록 시도
        theme.toggle_theme()
        self.assertEqual(len(calls), 1, "중복 리스너가 등록되었음")

    def test_multiple_listeners_all_called(self):
        results = []
        theme.on_theme_change(lambda: results.append("A"))
        theme.on_theme_change(lambda: results.append("B"))
        theme.toggle_theme()
        self.assertIn("A", results)
        self.assertIn("B", results)

    def test_listener_error_does_not_block_others(self):
        """한 리스너가 예외를 던져도 나머지는 호출되어야 한다."""
        results = []

        def bad():
            raise RuntimeError("oops")

        theme.on_theme_change(bad)
        theme.on_theme_change(lambda: results.append("ok"))
        theme.toggle_theme()
        self.assertEqual(results, ["ok"])

    def test_weakmethod_auto_cleanup(self):
        """바운드 메서드 리스너는 객체 소멸 시 자동 제거되어야 한다."""
        calls = []

        class Obj:
            def on_change(self):  # pragma: no cover
                calls.append(1)

        obj = Obj()
        theme.on_theme_change(obj.on_change)
        self.assertEqual(len(theme._listeners), 1)

        del obj  # 객체 소멸 → WeakMethod 죽음
        theme.toggle_theme()  # notify → 죽은 참조 정리
        self.assertEqual(calls, [])  # 호출 안됨
        self.assertEqual(len(theme._listeners), 0)  # 정리됨


class TestUseThemeColorsContextManager(unittest.TestCase):
    """use_theme_colors 컨텍스트 매니저 테스트."""

    def setUp(self):
        _reset_theme_state()

    def tearDown(self):
        _reset_theme_state()

    def test_enter_calls_fn_and_registers(self):
        calls = []

        def loader():
            calls.append("load")

        with theme.use_theme_colors(loader):
            self.assertEqual(calls, ["load"])
            # 등록 확인 — 테마 변경 시 다시 호출
            theme.toggle_theme()
            self.assertEqual(calls, ["load", "load"])

        # 컨텍스트 종료 후 해제 확인
        theme.toggle_theme()
        self.assertEqual(len(calls), 2)


class TestLoadPgColors(unittest.TestCase):
    """load_pg_colors() 헬퍼 테스트."""

    def setUp(self):
        _reset_theme_state()

    def tearDown(self):
        _reset_theme_state()

    def test_load_dark_theme_colors(self):
        ns = {}
        mapping = {"MY_BG": "BG", "MY_TEXT": "TEXT"}
        theme.load_pg_colors(mapping, ns)
        self.assertEqual(ns["MY_BG"], theme.PG.BG)
        self.assertEqual(ns["MY_TEXT"], theme.PG.TEXT)

    def test_load_light_theme_colors(self):
        theme.set_theme("light")
        ns = {}
        mapping = {"MY_BG": "BG"}
        theme.load_pg_colors(mapping, ns)
        self.assertEqual(ns["MY_BG"], theme.PG_LIGHT.BG)

    def test_load_colorblind_theme_colors(self):
        theme.set_colorblind(True)
        ns = {}
        mapping = {"MY_GREEN": "GREEN"}
        theme.load_pg_colors(mapping, ns)
        self.assertEqual(ns["MY_GREEN"], theme.PG_CB.GREEN)

    def test_load_light_colorblind_colors(self):
        theme.set_theme("light")
        theme.set_colorblind(True)
        ns = {}
        mapping = {"MY_RED": "RED"}
        theme.load_pg_colors(mapping, ns)
        self.assertEqual(ns["MY_RED"], theme.PG_CB_LIGHT.RED)


class TestFontScale(unittest.TestCase):
    """폰트 크기 배율 관련 테스트."""

    def setUp(self):
        _reset_theme_state()

    def tearDown(self):
        _reset_theme_state()

    def test_default_scale_is_1(self):
        self.assertEqual(theme.get_font_scale(), 1.0)

    def test_set_font_scale(self):
        theme.set_font_scale(1.3)
        self.assertAlmostEqual(theme.get_font_scale(), 1.3)

    def test_set_font_scale_clamped_max(self):
        theme.set_font_scale(5.0)
        self.assertAlmostEqual(theme.get_font_scale(), 1.5)

    def test_set_font_scale_clamped_min(self):
        theme.set_font_scale(0.1)
        self.assertAlmostEqual(theme.get_font_scale(), 0.8)

    def test_increase_font_scale(self):
        theme.increase_font_scale()
        self.assertAlmostEqual(theme.get_font_scale(), 1.1)

    def test_decrease_font_scale(self):
        theme.decrease_font_scale()
        self.assertAlmostEqual(theme.get_font_scale(), 0.9)

    def test_same_scale_no_notify(self):
        calls = []
        theme.on_theme_change(lambda: calls.append(1))
        theme.set_font_scale(1.0)  # 이미 1.0
        self.assertEqual(len(calls), 0)

    def test_scaled_font_sizes(self):
        """FONTS 프로퍼티가 스케일에 따라 달라져야 한다."""
        base_body = theme.FONTS.BODY
        theme.set_font_scale(1.5)
        scaled_body = theme.FONTS.BODY
        # 스케일 적용 → 크기가 달라야 한다
        self.assertGreater(scaled_body[1], base_body[1])

    def test_scaled_min_size_is_6(self):
        """최소 폰트 크기는 6 이상이어야 한다."""
        theme.set_font_scale(0.8)
        tiny = theme.FONTS.TINY  # 기본 8 * 0.8 = 6.4 → 6
        self.assertGreaterEqual(tiny[1], 6)

    def test_fonts_title_is_bold(self):
        title = theme.FONTS.TITLE
        self.assertEqual(len(title), 3)
        self.assertEqual(title[2], "bold")

    def test_fonts_body_no_bold(self):
        body = theme.FONTS.BODY
        self.assertEqual(len(body), 2)


class TestColorFormatValidation(unittest.TestCase):
    """TK 색상이 hex 문자열이고 PG 색상이 RGB 튜플인지 검증."""

    def _check_hex(self, cls, attr_name):
        val = getattr(cls, attr_name)
        self.assertIsInstance(val, str, f"{cls.__name__}.{attr_name} should be str")
        self.assertTrue(val.startswith("#"), f"{cls.__name__}.{attr_name} should start with #")
        self.assertEqual(len(val), 7, f"{cls.__name__}.{attr_name} should be #RRGGBB")

    def _check_rgb(self, cls, attr_name):
        val = getattr(cls, attr_name)
        self.assertIsInstance(val, tuple, f"{cls.__name__}.{attr_name} should be tuple")
        self.assertEqual(len(val), 3, f"{cls.__name__}.{attr_name} should have 3 components")
        for c in val:
            self.assertIsInstance(c, int, f"{cls.__name__}.{attr_name} components should be int")
            self.assertTrue(0 <= c <= 255, f"{cls.__name__}.{attr_name} component {c} out of range")

    def test_tk_dark_colors_are_hex(self):
        for attr in ("BG", "TEXT", "RED", "GREEN", "YELLOW", "ACCENT_BLUE"):
            self._check_hex(theme.TK, attr)

    def test_tk_light_colors_are_hex(self):
        for attr in ("BG", "TEXT", "RED", "GREEN"):
            self._check_hex(theme.TK_LIGHT, attr)

    def test_pg_dark_colors_are_rgb(self):
        for attr in ("BG", "TEXT", "RED", "GREEN", "WHITE", "MAGNET_N", "STABLE"):
            self._check_rgb(theme.PG, attr)

    def test_pg_light_colors_are_rgb(self):
        for attr in ("BG", "TEXT", "RED", "GREEN", "WHITE"):
            self._check_rgb(theme.PG_LIGHT, attr)

    def test_pg_cb_colors_are_rgb(self):
        for attr in ("BG", "TEXT", "RED", "GREEN", "STABLE", "COLLAPSED"):
            self._check_rgb(theme.PG_CB, attr)


class TestThemeMappingConsistency(unittest.TestCase):
    """_TK_THEMES / _PG_THEMES 매핑이 4가지 조합 모두 커버하는지 확인."""

    def test_tk_themes_has_all_combos(self):
        for t_name in ("dark", "light"):
            for cb in (True, False):
                key = (t_name, cb)
                self.assertIn(key, theme._TK_THEMES, f"Missing TK theme: {key}")

    def test_pg_themes_has_all_combos(self):
        for t_name in ("dark", "light"):
            for cb in (True, False):
                key = (t_name, cb)
                self.assertIn(key, theme._PG_THEMES, f"Missing PG theme: {key}")


class TestLauncherAccents(unittest.TestCase):
    """LAUNCHER_ACCENTS 딕셔너리 검증."""

    def test_all_four_modules_in_tk_accents(self):
        for mod in ("physics", "quantum", "security", "data_ai"):
            self.assertIn(mod, theme.LAUNCHER_ACCENTS)

    def test_all_four_modules_in_pg_accents(self):
        for mod in ("physics", "quantum", "security", "data_ai"):
            self.assertIn(mod, theme.LAUNCHER_ACCENTS_PG)

    def test_pg_accents_are_rgb_tuples(self):
        for mod, color in theme.LAUNCHER_ACCENTS_PG.items():
            self.assertIsInstance(color, tuple, f"{mod} should be tuple")
            self.assertEqual(len(color), 3)


class TestSaveLoadPreferences(unittest.TestCase):
    """save_preferences / load_preferences 테스트 (임시 config 사용)."""

    def setUp(self):
        _reset_theme_state()
        # 원본 config.json 경로를 임시 파일로 교체
        self._tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir=os.path.dirname(theme.__file__)
        )
        self._tmp.write("{}")
        self._tmp.close()
        self._orig_file = os.path.join(os.path.dirname(os.path.abspath(theme.__file__)), "config.json")
        # 원본 백업 & 임시 파일로 교체
        self._backup = self._orig_file + ".test_bak"
        if os.path.exists(self._orig_file):
            os.rename(self._orig_file, self._backup)
        os.rename(self._tmp.name, self._orig_file)

    def tearDown(self):
        _reset_theme_state()
        # 원본 복원
        if os.path.exists(self._orig_file):
            os.remove(self._orig_file)
        if os.path.exists(self._backup):
            os.rename(self._backup, self._orig_file)

    def test_save_and_load_theme(self):
        theme.set_theme("light")
        theme.save_preferences()
        _reset_theme_state()
        self.assertEqual(theme.get_theme(), "dark")  # 리셋 확인
        theme.load_preferences()
        self.assertEqual(theme.get_theme(), "light")

    def test_save_and_load_colorblind(self):
        theme.set_colorblind(True)
        theme.save_preferences()
        _reset_theme_state()
        self.assertFalse(theme.is_colorblind())
        theme.load_preferences()
        self.assertTrue(theme.is_colorblind())

    def test_save_and_load_font_scale(self):
        theme.set_font_scale(1.3)
        theme.save_preferences()
        _reset_theme_state()
        self.assertEqual(theme.get_font_scale(), 1.0)
        theme.load_preferences()
        self.assertAlmostEqual(theme.get_font_scale(), 1.3)

    def test_load_invalid_theme_ignored(self):
        """유효하지 않은 테마 값은 무시되어야 한다."""
        with open(self._orig_file, "w") as f:
            json.dump({"theme": "neon"}, f)
        theme.load_preferences()
        self.assertEqual(theme.get_theme(), "dark")  # 변경 없음

    def test_load_invalid_colorblind_ignored(self):
        with open(self._orig_file, "w") as f:
            json.dump({"colorblind_mode": "yes"}, f)
        theme.load_preferences()
        self.assertFalse(theme.is_colorblind())  # 기본값 유지

    def test_load_font_scale_clamped(self):
        with open(self._orig_file, "w") as f:
            json.dump({"font_scale": 99.0}, f)
        theme.load_preferences()
        self.assertAlmostEqual(theme.get_font_scale(), 1.5)  # 최대값 클램핑

    def test_load_corrupt_json_no_crash(self):
        with open(self._orig_file, "w") as f:
            f.write("not json!!!")
        theme.load_preferences()  # 에러 없이 통과
        self.assertEqual(theme.get_theme(), "dark")


if __name__ == "__main__":
    unittest.main()
