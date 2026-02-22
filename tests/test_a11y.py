"""접근성(a11y) 린트 테스트 — 테마 색상 대비 및 i18n 사용 검증.

WCAG 2.0 AA 기준으로 색상 대비를 검사하고,
UI 파일에서 i18n t() 사용 패턴과 키보드 접근성을 검증합니다.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.a11y_lint import (
    _hex_to_rgb,
    _relative_luminance,
    check_color_contrast,
    check_focus_indicator,
    check_keyboard_accessibility,
    check_shortcut_hints,
    contrast_ratio,
    run_a11y_lint,
)


class TestColorContrast(unittest.TestCase):
    """WCAG 색상 대비 비율 계산 검증."""

    def test_hex_to_rgb(self):
        self.assertEqual(_hex_to_rgb("#ffffff"), (255, 255, 255))
        self.assertEqual(_hex_to_rgb("#000000"), (0, 0, 0))
        self.assertEqual(_hex_to_rgb("#1e1e2e"), (30, 30, 46))

    def test_relative_luminance_black(self):
        """검정색의 상대 휘도는 0."""
        self.assertAlmostEqual(_relative_luminance(0, 0, 0), 0.0)

    def test_relative_luminance_white(self):
        """흰색의 상대 휘도는 1."""
        self.assertAlmostEqual(_relative_luminance(255, 255, 255), 1.0, places=3)

    def test_contrast_ratio_black_white(self):
        """흑백 대비는 21:1."""
        ratio = contrast_ratio((0, 0, 0), (255, 255, 255))
        self.assertAlmostEqual(ratio, 21.0, places=0)

    def test_contrast_ratio_same_color(self):
        """같은 색의 대비는 1:1."""
        ratio = contrast_ratio((128, 128, 128), (128, 128, 128))
        self.assertAlmostEqual(ratio, 1.0)

    def test_theme_text_on_bg_passes_aa(self):
        """TEXT (#cdd6f4) on BG (#1e1e2e)는 WCAG AA (4.5:1) 통과."""
        ratio = contrast_ratio((205, 214, 244), (30, 30, 46))
        self.assertGreaterEqual(ratio, 4.5, f"TEXT/BG 대비 {ratio:.2f}:1 < 4.5:1")

    def test_theme_green_on_bg_passes_aa(self):
        """GREEN (#a6e3a1) on BG (#1e1e2e)는 WCAG AA 통과."""
        ratio = contrast_ratio((166, 227, 161), (30, 30, 46))
        self.assertGreaterEqual(ratio, 4.5, f"GREEN/BG 대비 {ratio:.2f}:1 < 4.5:1")

    def test_theme_accent_blue_on_bg(self):
        """ACCENT_BLUE (#89b4fa) on BG (#1e1e2e) 대비 확인."""
        ratio = contrast_ratio((137, 180, 250), (30, 30, 46))
        self.assertGreaterEqual(ratio, 4.5, f"ACCENT_BLUE/BG 대비 {ratio:.2f}:1 < 4.5:1")

    def test_check_color_contrast_no_errors(self):
        """테마 색상 조합에 critical 에러가 없어야 함."""
        violations = []
        check_color_contrast(violations)
        errors = [v for v in violations if v.severity == "error"]
        for e in errors:
            print(f"  {e}")
        self.assertEqual(len(errors), 0, f"색상 대비 에러 {len(errors)}건 발견")


class TestKeyboardAccessibility(unittest.TestCase):
    """키보드 접근성 패턴 검사."""

    def test_source_with_keydown(self):
        """KEYDOWN 처리가 있는 코드는 A002 위반 없음."""
        violations = []
        source = "if event.type == pygame.KEYDOWN:\n    pass"
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quantum/tunneling.py")
        check_keyboard_accessibility(filepath, source, violations)
        keydown_errors = [v for v in violations if "키보드 이벤트 처리 없음" in v.message]
        self.assertEqual(len(keydown_errors), 0)

    def test_source_without_keydown(self):
        """KEYDOWN 없는 게임 모듈은 A002 위반."""
        violations = []
        source = "def run():\n    pass"
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quantum/tunneling.py")
        check_keyboard_accessibility(filepath, source, violations)
        keydown_errors = [v for v in violations if "키보드 이벤트 처리 없음" in v.message]
        self.assertEqual(len(keydown_errors), 1)

    def test_non_ui_file_skipped(self):
        """UI가 아닌 파일은 검사 제외."""
        violations = []
        source = "def pure_func(): return 42"
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config_loader.py")
        check_keyboard_accessibility(filepath, source, violations)
        self.assertEqual(len(violations), 0)


class TestShortcutHints(unittest.TestCase):
    """단축키 힌트 검사."""

    def test_file_with_help_overlay(self):
        """HelpOverlay가 있는 파일은 A004 통과."""
        violations = []
        source = "from help_overlay import HelpOverlay\noverlay = HelpOverlay('tunneling')"
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quantum/tunneling.py")
        check_shortcut_hints(filepath, source, violations)
        self.assertEqual(len(violations), 0)

    def test_file_without_help(self):
        """도움말이 없는 게임 파일은 A004 위반."""
        violations = []
        source = "def run(): pass"
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quantum/tunneling.py")
        check_shortcut_hints(filepath, source, violations)
        hint_warnings = [v for v in violations if "A004" in v.code]
        self.assertEqual(len(hint_warnings), 1)


class TestFocusIndicator(unittest.TestCase):
    """포커스 인디케이터 검사."""

    def test_file_with_selected(self):
        """selected 변수가 있는 파일은 통과."""
        violations = []
        source = "selected = 0\nif selected == idx: draw_highlight()"
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quantum/tunneling.py")
        check_focus_indicator(filepath, source, violations)
        self.assertEqual(len(violations), 0)

    def test_file_without_focus(self):
        """포커스 표시가 없는 파일은 A005 위반."""
        violations = []
        source = "def run(): pass"
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "quantum/tunneling.py")
        check_focus_indicator(filepath, source, violations)
        focus_warnings = [v for v in violations if "A005" in v.code]
        self.assertEqual(len(focus_warnings), 1)


class TestFullA11yLint(unittest.TestCase):
    """전체 a11y 린트 실행 통합 테스트."""

    def test_run_a11y_lint_completes(self):
        """전체 린트가 에러 없이 완료되어야 함."""
        violations = run_a11y_lint(verbose=False)
        # 결과가 리스트인지 확인
        self.assertIsInstance(violations, list)
        # 모든 위반 항목이 올바른 형식인지 확인
        for v in violations:
            self.assertIn(v.code, ("A001", "A002", "A003", "A004", "A005"))
            self.assertIn(v.severity, ("warning", "error"))

    def test_no_critical_contrast_errors(self):
        """테마 색상에 critical 대비 에러가 없어야 함."""
        violations = run_a11y_lint()
        contrast_errors = [v for v in violations if v.code == "A003" and v.severity == "error"]
        self.assertEqual(len(contrast_errors), 0, f"A003 에러: {[str(v) for v in contrast_errors]}")


if __name__ == "__main__":
    unittest.main()
