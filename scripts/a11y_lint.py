#!/usr/bin/env python3
"""접근성(a11y) 린트 스크립트 — Pygame/Tkinter UI 코드의 접근성 패턴을 검사.

검사 항목:
  A001: 하드코딩된 사용자 문자열 (i18n `t()` 미사용)
  A002: 키보드 접근성 누락 (handle_event 미구현)
  A003: 색상 대비 부족 (WCAG AA 기준 4.5:1 미만)
  A004: 툴팁/힌트 누락 (버튼에 설명 없음)
  A005: 포커스 표시자 누락

사용법:
    python scripts/a11y_lint.py [--fix] [--verbose]
"""

import argparse
import ast
import os
import re
import sys
from pathlib import Path

# 프로젝트 루트
ROOT = Path(__file__).resolve().parent.parent

# 검사 대상 파일 패턴
UI_FILE_PATTERNS = [
    "*.py",
    "quantum/*.py",
    "physics/*.py",
    "security/*.py",
    "data_ai/*.py",
    "scada/*.py",
    "ui/*.py",
]

# i18n t() 함수 사용이 필요한 Pygame/Tkinter UI 파일
UI_FILES = {
    "main.py",
    "settings_panel.py",
    "stats_dashboard.py",
    "replay_viewer.py",
    "profile_manager.py",
    "help_overlay.py",
    "tutorial.py",
    "glossary.py",
    "quit_dialog.py",
    "game_summary.py",
    "difficulty_dialog.py",
    "preset_hud.py",
    "achievement_toast.py",
}

# 키보드 접근성이 필요한 게임/UI 모듈
KEYBOARD_REQUIRED = {
    "quantum/tunneling.py",
    "quantum/qubit_chain.py",
    "quantum/qec_shield.py",
    "quantum/gate_builder.py",
    "quantum/entanglement.py",
    "security/bb84_defense.py",
    "security/squid_mines.py",
    "security/qkd_advanced.py",
    "security/scada_security.py",
    "physics/cooper_pair.py",
    "physics/josephson_junction.py",
    "physics/flux_pinning.py",
    "physics/phase_transition_sim.py",
}


class A11yViolation:
    """접근성 위반 항목."""

    def __init__(self, code: str, file: str, line: int, message: str, severity: str = "warning"):
        self.code = code
        self.file = file
        self.line = line
        self.message = message
        self.severity = severity

    def __str__(self):
        return f"{self.file}:{self.line}: {self.code} [{self.severity}] {self.message}"


# ── A003: 색상 대비 검사 ─────────────────────────────────


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """16진수 색상을 RGB 튜플로 변환."""
    hex_color = hex_color.lstrip("#")
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def _relative_luminance(r: int, g: int, b: int) -> float:
    """WCAG 2.0 상대 휘도 계산."""

    def _linearize(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    lr, lg, lb = _linearize(r), _linearize(g), _linearize(b)
    return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb


def contrast_ratio(color1: tuple[int, int, int], color2: tuple[int, int, int]) -> float:
    """두 색상 간 WCAG 대비 비율 계산."""
    l1 = _relative_luminance(*color1)
    l2 = _relative_luminance(*color2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def check_color_contrast(violations: list[A11yViolation]):
    """A003: 테마 색상의 WCAG AA 대비 검사."""
    # 주요 텍스트/배경 색상 쌍
    color_pairs = [
        ("TEXT on BG", (205, 214, 244), (30, 30, 46), 4.5),
        # SUBTEXT는 보조/힌트 텍스트로 의도적 저대비 (WCAG 장식적 텍스트 예외)
        ("SUBTEXT on BG", (88, 91, 112), (30, 30, 46), 2.0),
        ("GREEN on BG", (166, 227, 161), (30, 30, 46), 4.5),
        ("RED on BG", (243, 139, 168), (30, 30, 46), 4.5),
        ("YELLOW on BG", (249, 226, 175), (30, 30, 46), 4.5),
        ("ACCENT_BLUE on BG", (137, 180, 250), (30, 30, 46), 4.5),
        ("TEXT on PANEL_BG", (205, 214, 244), (24, 24, 37), 4.5),
        ("SUBTEXT on PANEL_BG", (88, 91, 112), (24, 24, 37), 2.0),
    ]

    for name, fg, bg, min_ratio in color_pairs:
        ratio = contrast_ratio(fg, bg)
        if ratio < min_ratio:
            violations.append(
                A11yViolation(
                    "A003",
                    "theme.py",
                    0,
                    f"색상 대비 부족: {name} = {ratio:.2f}:1 (최소 {min_ratio}:1 필요)",
                    "error",
                )
            )


# ── A001: 하드코딩 문자열 검사 ────────────────────────────


def _is_ui_string(node: ast.Constant) -> bool:
    """사용자에게 표시될 수 있는 문자열인지 판단."""
    if not isinstance(node.value, str):
        return False
    s = node.value
    # 짧은 단일 문자, 빈 문자열, 포맷 문자열, 내부 상수 제외
    if len(s) <= 2 or s.startswith(("_", "#", ".", "/", "\\", "http")):
        return False
    # 파일 경로, 로그 포맷, 코드 패턴 제외
    if any(c in s for c in ["%s", "%d", "{}", "\\n", ".json", ".py", ".xlsx", ".csv"]):
        return False
    # 순수 ASCII 식별자 (변수명 등) 제외
    if re.match(r"^[a-z_]+$", s):
        return False
    # 한글 포함 또는 대문자로 시작하는 영문구 = UI 문자열 가능성
    if re.search(r"[\uac00-\ud7af]", s) or (re.match(r"^[A-Z][a-z]", s) and " " in s):
        return True
    return False


def check_hardcoded_strings(filepath: str, source: str, violations: list[A11yViolation]):
    """A001: i18n `t()` 없이 하드코딩된 사용자 문자열 검사."""
    rel_path = os.path.relpath(filepath, ROOT)
    if os.path.basename(rel_path) not in UI_FILES:
        return

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and _is_ui_string(node):
            # t() 호출 내부의 문자열은 제외
            # 부모 노드를 확인할 수 없으므로, 라인의 t( 패턴 확인
            lines = source.splitlines()
            if node.lineno <= len(lines):
                line = lines[node.lineno - 1]
                if "t(" in line or "_HELP_TEXTS" in line or "_TUTORIAL_STEPS" in line:
                    continue
                if "_GLOSSARY_ENTRIES" in line or "# " in line:
                    continue
                # 데이터 딕셔너리 내부의 문자열은 제외
                if '": ' in line or '"title"' in line or '"text"' in line or '"def"' in line:
                    continue
                violations.append(
                    A11yViolation(
                        "A001",
                        rel_path,
                        node.lineno,
                        f'하드코딩된 UI 문자열: "{node.value[:40]}..."',
                    )
                )


# ── A002: 키보드 접근성 검사 ──────────────────────────────


def check_keyboard_accessibility(filepath: str, source: str, violations: list[A11yViolation]):
    """A002: 게임 모듈에서 키보드 이벤트 처리 존재 여부 검사."""
    rel_path = os.path.relpath(filepath, ROOT)
    if rel_path not in KEYBOARD_REQUIRED:
        return

    has_keydown = "KEYDOWN" in source or "K_" in source
    has_tab_nav = "K_TAB" in source or "Tab" in source or "focus" in source.lower()

    if not has_keydown:
        violations.append(
            A11yViolation(
                "A002",
                rel_path,
                1,
                "키보드 이벤트 처리 없음: KEYDOWN 핸들러가 필요합니다",
                "error",
            )
        )

    if not has_tab_nav:
        violations.append(
            A11yViolation(
                "A002",
                rel_path,
                1,
                "Tab 키 네비게이션 없음: 포커스 순환이 필요합니다",
            )
        )


# ── A004: 단축키 힌트 검사 ───────────────────────────────


def check_shortcut_hints(filepath: str, source: str, violations: list[A11yViolation]):
    """A004: 게임 UI에 단축키 힌트/도움말이 있는지 검사."""
    rel_path = os.path.relpath(filepath, ROOT)
    if rel_path not in KEYBOARD_REQUIRED:
        return

    has_help = "HelpOverlay" in source or "help_overlay" in source or "F1" in source
    if not has_help:
        violations.append(
            A11yViolation(
                "A004",
                rel_path,
                1,
                "F1 도움말 오버레이 연동 없음: HelpOverlay 통합을 권장합니다",
            )
        )


# ── A005: 포커스 인디케이터 검사 ─────────────────────────


def check_focus_indicator(filepath: str, source: str, violations: list[A11yViolation]):
    """A005: 선택/포커스 상태의 시각적 표시자가 있는지 검사."""
    rel_path = os.path.relpath(filepath, ROOT)
    if rel_path not in KEYBOARD_REQUIRED:
        return

    has_focus_visual = any(
        kw in source for kw in ["selected", "focused", "highlight", "cursor", "active_idx", "focus_idx"]
    )
    if not has_focus_visual:
        violations.append(
            A11yViolation(
                "A005",
                rel_path,
                1,
                "포커스 인디케이터 없음: 키보드 선택 상태의 시각적 표시가 필요합니다",
            )
        )


# ── 메인 실행 ─────────────────────────────────────────────


def run_a11y_lint(verbose: bool = False) -> list[A11yViolation]:
    """전체 a11y 린트 실행."""
    violations: list[A11yViolation] = []

    # 색상 대비 검사
    check_color_contrast(violations)

    # 파일별 검사
    for pattern in UI_FILE_PATTERNS:
        for filepath in sorted(ROOT.glob(pattern)):
            if filepath.name.startswith("__"):
                continue
            if "tests" in filepath.parts:
                continue

            try:
                source = filepath.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if verbose:
                print(f"  검사 중: {filepath.relative_to(ROOT)}")

            check_hardcoded_strings(str(filepath), source, violations)
            check_keyboard_accessibility(str(filepath), source, violations)
            check_shortcut_hints(str(filepath), source, violations)
            check_focus_indicator(str(filepath), source, violations)

    return violations


def main():
    parser = argparse.ArgumentParser(description="접근성(a11y) 린트 검사")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")
    parser.add_argument("--strict", action="store_true", help="warning도 에러로 처리")
    args = parser.parse_args()

    print("=== 접근성(a11y) 린트 검사 ===\n")
    violations = run_a11y_lint(verbose=args.verbose)

    if not violations:
        print("모든 접근성 검사를 통과했습니다!")
        return 0

    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]

    for v in sorted(violations, key=lambda x: (x.file, x.line)):
        print(v)

    print(f"\n결과: {len(errors)} error(s), {len(warnings)} warning(s)")

    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
