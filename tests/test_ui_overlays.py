"""Pygame UI 오버레이/위젯 모듈 테스트.

achievement_toast, help_overlay, tutorial, glossary 모듈의
모든 코드 경로를 커버하는 단위 테스트입니다.
pygame을 sys.modules에 mock으로 주입하여 디스플레이 없이 테스트합니다.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# ── pygame 모킹 ──────────────────────────────────────────────
# pygame을 import하기 전에 sys.modules에 mock을 주입
_pg_mock = MagicMock()
_pg_mock.SRCALPHA = 0x00010000
_pg_mock.KEYDOWN = 768
_pg_mock.MOUSEBUTTONDOWN = 1025
_pg_mock.QUIT = 256
_pg_mock.K_F1 = 282
_pg_mock.K_ESCAPE = 27
_pg_mock.K_g = 103
_pg_mock.K_t = 116
_pg_mock.K_RETURN = 13
_pg_mock.K_RIGHT = 275
_pg_mock.K_LEFT = 276
_pg_mock.K_SPACE = 32
_pg_mock.K_DOWN = 274
_pg_mock.K_UP = 273
_pg_mock.K_PAGEDOWN = 281
_pg_mock.K_PAGEUP = 280


# mock Surface 헬퍼
def _make_mock_surface(w=800, h=600):
    """get_width/get_height/get_size/blit 메서드를 가진 mock Surface 생성."""
    surf = MagicMock()
    surf.get_width.return_value = w
    surf.get_height.return_value = h
    surf.get_size.return_value = (w, h)
    return surf


# mock Font 헬퍼 — render()가 get_width/get_height를 가진 Surface 반환
def _make_mock_font():
    """render()가 mock Surface를 반환하는 mock Font 생성."""
    font = MagicMock()

    def fake_render(text, antialias, color, *args, **kwargs):
        s = MagicMock()
        # 텍스트 길이에 비례한 너비 (10px/char)
        s.get_width.return_value = len(str(text)) * 10
        s.get_height.return_value = 16
        return s

    font.render = MagicMock(side_effect=fake_render)
    return font


# pygame.Surface 생성자를 mock Surface 반환하도록 설정
_pg_mock.Surface = MagicMock(side_effect=lambda size, *a, **kw: _make_mock_surface(size[0], size[1]))

# pygame.draw.rect를 아무것도 하지 않는 mock으로 설정
_pg_mock.draw = MagicMock()

# pygame.event.Event를 mock
_pg_mock.event = MagicMock()

# pygame.font.Font를 mock
_pg_mock.font = MagicMock()
_pg_mock.font.Font = MagicMock(return_value=_make_mock_font())

# sys.modules에 mock pygame 주입
sys.modules["pygame"] = _pg_mock

# ── 프로젝트 경로 설정 ──────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── theme mock ───────────────────────────────────────────────
_mock_theme = MagicMock()
_mock_theme.TEXT = (205, 214, 244)
_mock_theme.GREEN = (166, 227, 161)
_mock_theme.SUBTEXT = (88, 91, 112)
_mock_theme.PANEL_BG = (30, 30, 46)
_mock_theme.OVERLAY = (49, 50, 68)
_mock_theme.ACCENT_BLUE = (137, 180, 250)
_mock_theme.ACCENT_YELLOW = (249, 226, 175)
_mock_theme.RED = (243, 139, 168)
_mock_theme.YELLOW = (249, 226, 175)


def _fake_get_pg_theme():
    return _mock_theme


# ── 모듈 import (pygame mock 후) ────────────────────────────
with patch("theme.get_pg_theme", _fake_get_pg_theme):
    from achievement_toast import AchievementToast

with patch("i18n.t", side_effect=lambda key, **kw: f"[{key}]"):
    from glossary import GlossaryOverlay, _build_lines, _GLOSSARY_ENTRIES  # noqa: I001
    from help_overlay import HelpOverlay, _HELP_TEXTS

with patch("i18n.t", side_effect=lambda key, **kw: f"[{key}]"):
    with patch("logger.get_module_logger", return_value=MagicMock()):
        from tutorial import TutorialOverlay, _load_progress, _save_progress, _TUTORIAL_STEPS  # noqa: I001


# ── mock 이벤트 헬퍼 ─────────────────────────────────────────
def _make_event(event_type, key=None):
    """간단한 mock pygame 이벤트 생성."""
    ev = MagicMock()
    ev.type = event_type
    ev.key = key
    return ev


# ================================================================
# AchievementToast 테스트
# ================================================================
class TestAchievementToastInit(unittest.TestCase):
    """AchievementToast 초기 상태 검증."""

    def test_initial_state(self):
        """생성 직후 idle 상태, 큐 비어있음."""
        toast = AchievementToast()
        self.assertEqual(toast._phase, "idle")
        self.assertIsNone(toast._current)
        self.assertEqual(toast._queue, [])
        self.assertEqual(toast._history, [])
        self.assertFalse(toast.history_visible)
        self.assertAlmostEqual(toast._timer, 0.0)


class TestAchievementToastShow(unittest.TestCase):
    """show() / show_many() 테스트."""

    def test_show_single_from_idle(self):
        """idle 상태에서 show() 호출 시 slide_in으로 전환."""
        toast = AchievementToast()
        ach = {"title": "Test", "desc": "Test desc", "icon": "T"}
        toast.show(ach)
        # _next()가 호출되어 slide_in 진입
        self.assertEqual(toast._phase, "slide_in")
        self.assertEqual(toast._current, ach)
        self.assertEqual(len(toast._queue), 0)
        self.assertEqual(len(toast._history), 1)

    def test_show_while_active(self):
        """이미 표시 중일 때 show() 호출 시 큐에 추가."""
        toast = AchievementToast()
        ach1 = {"title": "First", "icon": "1"}
        ach2 = {"title": "Second", "icon": "2"}
        toast.show(ach1)  # slide_in 진입
        toast.show(ach2)  # 큐에 추가 (phase != idle)
        self.assertEqual(toast._current, ach1)
        self.assertEqual(len(toast._queue), 1)
        self.assertEqual(toast._queue[0], ach2)

    def test_show_many(self):
        """show_many()로 여러 업적 추가."""
        toast = AchievementToast()
        achs = [
            {"title": "A", "icon": "a"},
            {"title": "B", "icon": "b"},
            {"title": "C", "icon": "c"},
        ]
        toast.show_many(achs)
        # 첫 번째는 current, 나머지는 큐에
        self.assertEqual(toast._current["title"], "A")
        self.assertEqual(len(toast._queue), 2)
        self.assertEqual(len(toast._history), 3)

    def test_history_max_limit(self):
        """히스토리가 HISTORY_MAX(20)를 초과하면 오래된 항목 제거."""
        toast = AchievementToast()
        for i in range(25):
            toast.show({"title": f"Ach{i}", "icon": str(i)})
        self.assertEqual(len(toast._history), toast.HISTORY_MAX)
        # 가장 오래된 항목이 제거되었는지 확인
        self.assertEqual(toast._history[0]["title"], "Ach5")


class TestAchievementToastUpdate(unittest.TestCase):
    """update() 애니메이션 상태 전이 테스트."""

    def test_update_idle_returns_early(self):
        """idle 상태에서 update()는 아무것도 하지 않음."""
        toast = AchievementToast()
        toast.update(1.0)
        self.assertEqual(toast._phase, "idle")
        self.assertAlmostEqual(toast._timer, 0.0)

    def test_slide_in_to_show(self):
        """slide_in → show 전환 (SLIDE_TIME 경과 후)."""
        toast = AchievementToast()
        toast.show({"title": "T", "icon": "X"})
        self.assertEqual(toast._phase, "slide_in")
        # SLIDE_TIME(0.3초) 경과
        toast.update(0.35)
        self.assertEqual(toast._phase, "show")
        self.assertAlmostEqual(toast._timer, 0.0)

    def test_show_to_slide_out(self):
        """show → slide_out 전환 (DISPLAY_TIME 경과 후)."""
        toast = AchievementToast()
        toast.show({"title": "T", "icon": "X"})
        # slide_in 완료
        toast.update(0.35)
        self.assertEqual(toast._phase, "show")
        # DISPLAY_TIME(3.0초) 경과
        toast.update(3.1)
        self.assertEqual(toast._phase, "slide_out")
        self.assertAlmostEqual(toast._timer, 0.0)

    def test_slide_out_to_idle(self):
        """slide_out → idle 전환 (큐가 비어있을 때)."""
        toast = AchievementToast()
        toast.show({"title": "T", "icon": "X"})
        toast.update(0.35)  # slide_in → show
        toast.update(3.1)  # show → slide_out
        toast.update(0.35)  # slide_out → idle (큐 비어있음)
        self.assertEqual(toast._phase, "idle")
        self.assertIsNone(toast._current)

    def test_slide_out_to_next_slide_in(self):
        """slide_out 후 큐에 다음 업적이 있으면 slide_in 재진입."""
        toast = AchievementToast()
        toast.show({"title": "First", "icon": "1"})
        toast.show({"title": "Second", "icon": "2"})
        # 첫 번째 업적 전체 사이클
        toast.update(0.35)  # slide_in → show
        toast.update(3.1)  # show → slide_out
        toast.update(0.35)  # slide_out → next (Second)
        self.assertEqual(toast._phase, "slide_in")
        self.assertEqual(toast._current["title"], "Second")

    def test_slide_in_timer_accumulates(self):
        """slide_in 중 SLIDE_TIME 미만이면 계속 slide_in."""
        toast = AchievementToast()
        toast.show({"title": "T", "icon": "X"})
        toast.update(0.1)
        self.assertEqual(toast._phase, "slide_in")
        self.assertAlmostEqual(toast._timer, 0.1)

    def test_show_timer_accumulates(self):
        """show 중 DISPLAY_TIME 미만이면 계속 show."""
        toast = AchievementToast()
        toast.show({"title": "T", "icon": "X"})
        toast.update(0.35)  # → show
        toast.update(1.0)
        self.assertEqual(toast._phase, "show")
        self.assertAlmostEqual(toast._timer, 1.0)


class TestAchievementToastDraw(unittest.TestCase):
    """draw() 렌더링 테스트."""

    def test_draw_no_current(self):
        """current가 None이면 draw()는 즉시 반환."""
        toast = AchievementToast()
        screen = _make_mock_surface()
        font = _make_mock_font()
        toast.draw(screen, font)
        # screen.blit이 호출되지 않아야 함
        screen.blit.assert_not_called()

    @patch("achievement_toast.pygame", None)
    def test_draw_pygame_none(self):
        """pygame이 None이면 draw()는 즉시 반환."""
        toast = AchievementToast()
        toast._current = {"title": "T", "icon": "X", "desc": "D"}
        screen = _make_mock_surface()
        font = _make_mock_font()
        toast.draw(screen, font)
        screen.blit.assert_not_called()

    @patch("achievement_toast.get_pg_theme", _fake_get_pg_theme)
    def test_draw_slide_in_phase(self):
        """slide_in 단계에서 오프셋 적용되어 렌더링."""
        toast = AchievementToast()
        toast.show({"title": "Test", "desc": "Short", "icon": "T"})
        toast.update(0.15)  # slide_in 중간
        screen = _make_mock_surface()
        font = _make_mock_font()
        toast.draw(screen, font)
        # screen.blit이 호출됨 (토스트 Surface)
        screen.blit.assert_called()

    @patch("achievement_toast.get_pg_theme", _fake_get_pg_theme)
    def test_draw_show_phase(self):
        """show 단계에서 offset_y=0으로 렌더링."""
        toast = AchievementToast()
        toast.show({"title": "Test", "desc": "Short", "icon": "T"})
        toast.update(0.35)  # → show
        screen = _make_mock_surface()
        font = _make_mock_font()
        toast.draw(screen, font)
        screen.blit.assert_called()

    @patch("achievement_toast.get_pg_theme", _fake_get_pg_theme)
    def test_draw_slide_out_phase(self):
        """slide_out 단계에서 음수 오프셋으로 렌더링."""
        toast = AchievementToast()
        toast.show({"title": "Test", "desc": "Short", "icon": "T"})
        toast.update(0.35)  # → show
        toast.update(3.1)  # → slide_out
        toast.update(0.1)  # slide_out 중간
        screen = _make_mock_surface()
        font = _make_mock_font()
        toast.draw(screen, font)
        screen.blit.assert_called()

    @patch("achievement_toast.get_pg_theme", _fake_get_pg_theme)
    def test_draw_long_desc_truncated(self):
        """desc가 40자 초과 시 38자+".."로 잘림."""
        toast = AchievementToast()
        long_desc = "A" * 50
        toast.show({"title": "T", "desc": long_desc, "icon": "X"})
        toast.update(0.35)  # → show
        screen = _make_mock_surface()
        font = _make_mock_font()
        toast.draw(screen, font)
        # font.render가 desc 렌더링 시 잘린 텍스트를 사용했는지 확인
        rendered_texts = [call[0][0] for call in font.render.call_args_list]
        # 잘린 desc 찾기
        truncated = [t for t in rendered_texts if t.endswith("..")]
        self.assertTrue(len(truncated) > 0, "긴 desc가 잘려야 합니다")

    @patch("achievement_toast.get_pg_theme", _fake_get_pg_theme)
    def test_draw_missing_keys_uses_defaults(self):
        """icon/title/desc 키가 없을 때 기본값 사용."""
        toast = AchievementToast()
        toast.show({})  # 빈 dict
        toast.update(0.35)  # → show
        screen = _make_mock_surface()
        font = _make_mock_font()
        toast.draw(screen, font)
        # 기본값 "?" icon, "Achievement!" title, "" desc
        rendered_texts = [call[0][0] for call in font.render.call_args_list]
        self.assertTrue(any("[?]" in t for t in rendered_texts))
        self.assertTrue(any("Achievement!" in t for t in rendered_texts))

    @patch("achievement_toast.get_pg_theme", _fake_get_pg_theme)
    def test_draw_short_desc_not_truncated(self):
        """desc가 40자 이하면 잘리지 않음."""
        toast = AchievementToast()
        short_desc = "Short description"
        toast.show({"title": "T", "desc": short_desc, "icon": "X"})
        toast.update(0.35)
        screen = _make_mock_surface()
        font = _make_mock_font()
        toast.draw(screen, font)
        rendered_texts = [call[0][0] for call in font.render.call_args_list]
        self.assertTrue(any(short_desc == t for t in rendered_texts))


class TestAchievementToastToggleHistory(unittest.TestCase):
    """toggle_history() 테스트."""

    def test_toggle_on_off(self):
        """히스토리 패널 토글."""
        toast = AchievementToast()
        self.assertFalse(toast.history_visible)
        toast.toggle_history()
        self.assertTrue(toast.history_visible)
        toast.toggle_history()
        self.assertFalse(toast.history_visible)


class TestAchievementToastDrawHistory(unittest.TestCase):
    """draw_history() 테스트."""

    @patch("achievement_toast.pygame", None)
    def test_draw_history_pygame_none(self):
        """pygame이 None이면 즉시 반환."""
        toast = AchievementToast()
        toast.history_visible = True
        screen = _make_mock_surface()
        font = _make_mock_font()
        toast.draw_history(screen, font)
        screen.blit.assert_not_called()

    def test_draw_history_not_visible(self):
        """history_visible=False이면 즉시 반환."""
        toast = AchievementToast()
        toast.history_visible = False
        screen = _make_mock_surface()
        font = _make_mock_font()
        toast.draw_history(screen, font)
        screen.blit.assert_not_called()

    @patch("achievement_toast.get_pg_theme", _fake_get_pg_theme)
    def test_draw_history_import_error(self):
        """achievements 모듈 import 실패 시 빈 리스트 사용."""
        toast = AchievementToast()
        toast.history_visible = True
        screen = _make_mock_surface()
        font = _make_mock_font()
        with patch.dict(sys.modules, {"achievements": None}):
            # ImportError 시 all_ach = [] → 즉시 반환
            toast.draw_history(screen, font)

    @patch("achievement_toast.get_pg_theme", _fake_get_pg_theme)
    def test_draw_history_empty_achievements(self):
        """전체 업적이 비어있으면 즉시 반환."""
        toast = AchievementToast()
        toast.history_visible = True
        screen = _make_mock_surface()
        font = _make_mock_font()
        mock_get_all = MagicMock(return_value=[])
        with patch.dict(sys.modules, {"achievements": MagicMock(get_all_achievements=mock_get_all)}):
            toast.draw_history(screen, font)
            # 빈 목록이면 panel 렌더링 안 함
            screen.blit.assert_not_called()

    @patch("achievement_toast.get_pg_theme", _fake_get_pg_theme)
    def test_draw_history_with_achievements(self):
        """업적 목록이 있을 때 정상 렌더링."""
        toast = AchievementToast()
        toast.history_visible = True
        screen = _make_mock_surface()
        font = _make_mock_font()
        mock_achs = [
            {"icon": "T", "title": "Test1", "unlocked": True},
            {"icon": "X", "title": "Test2", "unlocked": False},
        ]
        mock_mod = MagicMock()
        mock_mod.get_all_achievements = MagicMock(return_value=mock_achs)
        with patch.dict(sys.modules, {"achievements": mock_mod}):
            toast.draw_history(screen, font)
            # screen.blit이 호출됨 (패널 렌더링)
            screen.blit.assert_called()

    @patch("achievement_toast.get_pg_theme", _fake_get_pg_theme)
    def test_draw_history_overflow_lines(self):
        """업적이 많아서 panel_h를 초과하면 중단."""
        toast = AchievementToast()
        toast.history_visible = True
        # 작은 화면으로 오버플로 유도
        screen = _make_mock_surface(400, 100)
        font = _make_mock_font()
        mock_achs = [{"icon": str(i), "title": f"Ach{i}", "unlocked": i % 2 == 0} for i in range(50)]
        mock_mod = MagicMock()
        mock_mod.get_all_achievements = MagicMock(return_value=mock_achs)
        with patch.dict(sys.modules, {"achievements": mock_mod}):
            toast.draw_history(screen, font)
            screen.blit.assert_called()


class TestAchievementToastNext(unittest.TestCase):
    """_next() 내부 메서드 테스트."""

    def test_next_empty_queue(self):
        """큐가 비어있으면 idle로 전환."""
        toast = AchievementToast()
        toast._queue = []
        toast._next()
        self.assertEqual(toast._phase, "idle")
        self.assertIsNone(toast._current)

    def test_next_with_queue(self):
        """큐에 항목이 있으면 pop하고 slide_in 진입."""
        toast = AchievementToast()
        toast._queue = [{"title": "Next", "icon": "N"}]
        toast._next()
        self.assertEqual(toast._phase, "slide_in")
        self.assertEqual(toast._current["title"], "Next")
        self.assertEqual(len(toast._queue), 0)


# ================================================================
# HelpOverlay 테스트
# ================================================================
class TestHelpOverlayInit(unittest.TestCase):
    """HelpOverlay 초기화 테스트."""

    def test_known_module(self):
        """알려진 모듈명으로 초기화 시 해당 텍스트 로드."""
        overlay = HelpOverlay("tunneling")
        self.assertEqual(overlay.module_name, "tunneling")
        self.assertFalse(overlay.visible)
        self.assertEqual(overlay.lines, _HELP_TEXTS["tunneling"])

    def test_unknown_module(self):
        """알 수 없는 모듈명이면 기본 메시지."""
        overlay = HelpOverlay("nonexistent_module")
        self.assertEqual(overlay.lines, ["No help available."])


class TestHelpOverlayHandleEvent(unittest.TestCase):
    """handle_event() 이벤트 처리 테스트."""

    def setUp(self):
        """help_overlay 모듈의 pygame 참조가 올바른 mock을 가리키도록 보장."""
        import help_overlay as _ho_mod

        self._ho_mod = _ho_mod
        # 다른 테스트 모듈이 sys.modules["pygame"]를 교체하면
        # help_overlay.pygame 참조가 깨질 수 있으므로 강제 재설정
        _ho_mod.pygame = _pg_mock

    def test_f1_toggles_visibility(self):
        """F1 키로 visible 토글."""
        overlay = HelpOverlay("tunneling")
        self.assertFalse(overlay.visible)
        # F1 → 켜기
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_F1)
        result = overlay.handle_event(ev)
        self.assertTrue(result)
        self.assertTrue(overlay.visible)
        # F1 → 끄기
        result = overlay.handle_event(ev)
        self.assertTrue(result)
        self.assertFalse(overlay.visible)

    def test_esc_closes_when_visible(self):
        """ESC 키로 닫기 (visible일 때만)."""
        overlay = HelpOverlay("tunneling")
        overlay.visible = True
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_ESCAPE)
        result = overlay.handle_event(ev)
        self.assertTrue(result)
        self.assertFalse(overlay.visible)

    def test_esc_ignored_when_hidden(self):
        """ESC 키가 hidden일 때는 무시."""
        overlay = HelpOverlay("tunneling")
        overlay.visible = False
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_ESCAPE)
        result = overlay.handle_event(ev)
        self.assertFalse(result)

    def test_non_keydown_ignored(self):
        """KEYDOWN이 아닌 이벤트는 무시."""
        overlay = HelpOverlay("tunneling")
        ev = _make_event(_pg_mock.MOUSEBUTTONDOWN, None)
        result = overlay.handle_event(ev)
        self.assertFalse(result)

    def test_other_key_ignored(self):
        """F1/ESC 외의 키는 무시."""
        overlay = HelpOverlay("tunneling")
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_SPACE)
        result = overlay.handle_event(ev)
        self.assertFalse(result)


class TestHelpOverlayDraw(unittest.TestCase):
    """draw() 렌더링 테스트."""

    @patch("help_overlay.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_hidden_shows_hint(self, mock_t):
        """숨김 상태에서 F1 힌트만 표시."""
        overlay = HelpOverlay("tunneling")
        overlay.visible = False
        screen = _make_mock_surface()
        font = _make_mock_font()
        overlay.draw(screen, font)
        # 힌트 텍스트 렌더링 확인
        font.render.assert_called()
        screen.blit.assert_called()

    @patch("help_overlay.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_visible_renders_overlay(self, mock_t):
        """보이는 상태에서 전체 오버레이 렌더링."""
        overlay = HelpOverlay("tunneling")
        overlay.visible = True
        screen = _make_mock_surface()
        font = _make_mock_font()
        overlay.draw(screen, font)
        # 여러 번 blit 호출 (배경 + 텍스트들 + 닫기 안내)
        self.assertGreater(screen.blit.call_count, 1)

    @patch("help_overlay.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_line_colors(self, mock_t):
        """라인 종류별 색상 분기 테스트 (===, [, 수식, 일반)."""
        overlay = HelpOverlay("tunneling")
        overlay.visible = True
        screen = _make_mock_surface(800, 800)  # 큰 화면으로 모든 라인 표시
        font = _make_mock_font()
        overlay.draw(screen, font)
        # 렌더링된 색상 수집
        rendered_colors = [call[0][2] for call in font.render.call_args_list]
        # === 타이틀 (파랑)
        self.assertIn((137, 180, 250), rendered_colors)
        # [ 섹션 (노랑)
        self.assertIn((249, 226, 175), rendered_colors)
        # 일반 텍스트 (흰색)
        self.assertIn((205, 214, 244), rendered_colors)

    @patch("help_overlay.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_formula_color(self, mock_t):
        """수식 라인(수식/P ~/Phi)은 보라색으로 렌더링."""
        # tunneling 도움말에는 "  수식: P ~ exp(-2 * kappa * d)" 라인이 있음
        overlay = HelpOverlay("tunneling")
        overlay.visible = True
        screen = _make_mock_surface(800, 1200)  # 매우 큰 화면
        font = _make_mock_font()
        overlay.draw(screen, font)
        rendered_colors = [call[0][2] for call in font.render.call_args_list]
        # 보라색 수식
        self.assertIn((203, 166, 247), rendered_colors)

    @patch("help_overlay.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_empty_lines_skipped(self, mock_t):
        """빈 줄은 렌더링하지 않고 간격만 추가."""
        overlay = HelpOverlay("tunneling")
        overlay.visible = True
        screen = _make_mock_surface()
        font = _make_mock_font()
        overlay.draw(screen, font)
        # 빈 줄에 대해 font.render가 호출되지 않는지 확인
        rendered_texts = [call[0][0] for call in font.render.call_args_list]
        self.assertTrue(all(t != "" for t in rendered_texts))

    @patch("help_overlay.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_small_screen_truncates(self, mock_t):
        """작은 화면에서 텍스트가 박스를 넘으면 중단."""
        overlay = HelpOverlay("tunneling")
        overlay.visible = True
        screen = _make_mock_surface(200, 100)  # 매우 작은 화면
        font = _make_mock_font()
        overlay.draw(screen, font)
        # 잘려도 에러 없이 완료
        screen.blit.assert_called()


class TestHelpTextsData(unittest.TestCase):
    """_HELP_TEXTS 데이터 무결성 테스트."""

    def test_all_modules_have_lists(self):
        """모든 모듈의 도움말이 리스트 형태."""
        for module, lines in _HELP_TEXTS.items():
            self.assertIsInstance(lines, list, f"{module} 도움말이 리스트가 아님")
            self.assertGreater(len(lines), 0, f"{module} 도움말이 비어있음")

    def test_expected_modules_exist(self):
        """주요 모듈들의 도움말이 존재."""
        expected = ["tunneling", "qubit_chain", "bb84_defense", "gate_builder"]
        for mod in expected:
            self.assertIn(mod, _HELP_TEXTS, f"{mod} 도움말 누락")


# ================================================================
# TutorialOverlay 테스트
# ================================================================
class TestTutorialOverlayInit(unittest.TestCase):
    """TutorialOverlay 초기화 테스트."""

    def test_known_module_auto_show(self):
        """알려진 모듈, auto_show=True, 진행 상태 없을 때 → visible=True."""
        with patch("tutorial._load_progress", return_value={}):
            tut = TutorialOverlay("tunneling", auto_show=True)
        self.assertTrue(tut.visible)
        self.assertEqual(tut.current_step, 0)
        self.assertFalse(tut._completed)

    def test_known_module_already_completed(self):
        """이미 완료된 모듈 → visible=False, _completed=True."""
        progress = {"tunneling": {"completed": True, "step": 8}}
        with patch("tutorial._load_progress", return_value=progress):
            tut = TutorialOverlay("tunneling", auto_show=True)
        self.assertFalse(tut.visible)
        self.assertTrue(tut._completed)

    def test_known_module_resume_step(self):
        """이전 진행률에서 이어서 시작."""
        progress = {"tunneling": {"completed": False, "step": 3}}
        with patch("tutorial._load_progress", return_value=progress):
            tut = TutorialOverlay("tunneling", auto_show=True)
        self.assertTrue(tut.visible)
        self.assertEqual(tut.current_step, 3)

    def test_known_module_resume_step_zero(self):
        """saved_step=0이면 이어서 시작하지 않음 (조건: 0 < saved_step)."""
        progress = {"tunneling": {"completed": False, "step": 0}}
        with patch("tutorial._load_progress", return_value=progress):
            tut = TutorialOverlay("tunneling", auto_show=True)
        self.assertEqual(tut.current_step, 0)

    def test_known_module_resume_step_out_of_range(self):
        """saved_step이 steps 범위 밖이면 0에서 시작."""
        progress = {"tunneling": {"completed": False, "step": 999}}
        with patch("tutorial._load_progress", return_value=progress):
            tut = TutorialOverlay("tunneling", auto_show=True)
        self.assertEqual(tut.current_step, 0)

    def test_auto_show_false(self):
        """auto_show=False이면 visible=False."""
        tut = TutorialOverlay("tunneling", auto_show=False)
        self.assertFalse(tut.visible)

    def test_unknown_module(self):
        """알 수 없는 모듈이면 steps=[], auto_show 시에도 visible=False."""
        with patch("tutorial._load_progress", return_value={}):
            tut = TutorialOverlay("unknown_module", auto_show=True)
        self.assertFalse(tut.visible)
        self.assertEqual(tut.steps, [])

    def test_no_steps_no_autoshow(self):
        """steps가 비어있으면 auto_show=True여도 visible=False."""
        with patch("tutorial._load_progress", return_value={}):
            tut = TutorialOverlay("nonexistent", auto_show=True)
        self.assertFalse(tut.visible)


class TestTutorialOverlayHandleEvent(unittest.TestCase):
    """handle_event() 이벤트 처리 테스트."""

    def _make_tutorial(self):
        """테스트용 TutorialOverlay 생성 (파일 I/O 없이)."""
        with patch("tutorial._load_progress", return_value={}):
            with patch("tutorial._save_progress"):
                return TutorialOverlay("tunneling", auto_show=False)

    @patch("tutorial.pygame", None)
    def test_pygame_none_returns_false(self):
        """pygame이 None이면 False 반환."""
        tut = self._make_tutorial()
        ev = _make_event(768, 116)  # KEYDOWN, K_t
        result = tut.handle_event(ev)
        self.assertFalse(result)

    def test_non_keydown_ignored(self):
        """KEYDOWN이 아닌 이벤트는 무시."""
        tut = self._make_tutorial()
        ev = _make_event(_pg_mock.MOUSEBUTTONDOWN, None)
        result = tut.handle_event(ev)
        self.assertFalse(result)

    def test_t_key_opens_tutorial(self):
        """T 키로 튜토리얼 열기 (hidden일 때)."""
        tut = self._make_tutorial()
        tut.visible = False
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_t)
        result = tut.handle_event(ev)
        self.assertTrue(result)
        self.assertTrue(tut.visible)
        self.assertEqual(tut.current_step, 0)

    def test_t_key_ignored_when_visible(self):
        """T 키는 이미 visible일 때 토글하지 않음 (다른 분기로 처리)."""
        tut = self._make_tutorial()
        tut.visible = True
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_t)
        # visible=True에서 K_t → 어떤 분기에도 매치 안 됨 → False
        result = tut.handle_event(ev)
        self.assertFalse(result)

    def test_step_forward_enter(self):
        """Enter 키로 다음 스텝."""
        tut = self._make_tutorial()
        tut.visible = True
        tut.current_step = 0
        with patch("tutorial._load_progress", return_value={}):
            with patch("tutorial._save_progress"):
                ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_RETURN)
                result = tut.handle_event(ev)
        self.assertTrue(result)
        self.assertEqual(tut.current_step, 1)

    def test_step_forward_right(self):
        """Right 키로 다음 스텝."""
        tut = self._make_tutorial()
        tut.visible = True
        tut.current_step = 0
        with patch("tutorial._load_progress", return_value={}):
            with patch("tutorial._save_progress"):
                ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_RIGHT)
                result = tut.handle_event(ev)
        self.assertTrue(result)
        self.assertEqual(tut.current_step, 1)

    def test_step_forward_space(self):
        """Space 키로 다음 스텝."""
        tut = self._make_tutorial()
        tut.visible = True
        tut.current_step = 0
        with patch("tutorial._load_progress", return_value={}):
            with patch("tutorial._save_progress"):
                ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_SPACE)
                result = tut.handle_event(ev)
        self.assertTrue(result)

    def test_step_forward_past_end_finishes(self):
        """마지막 스텝 다음으로 진행하면 _finish() 호출."""
        tut = self._make_tutorial()
        tut.visible = True
        tut.current_step = len(tut.steps) - 1
        with patch("tutorial._load_progress", return_value={}):
            with patch("tutorial._save_progress"):
                ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_RETURN)
                result = tut.handle_event(ev)
        self.assertTrue(result)
        self.assertFalse(tut.visible)
        self.assertTrue(tut._completed)

    def test_step_backward_left(self):
        """Left 키로 이전 스텝."""
        tut = self._make_tutorial()
        tut.visible = True
        tut.current_step = 3
        with patch("tutorial._load_progress", return_value={}):
            with patch("tutorial._save_progress"):
                ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_LEFT)
                result = tut.handle_event(ev)
        self.assertTrue(result)
        self.assertEqual(tut.current_step, 2)

    def test_step_backward_at_zero_stays(self):
        """0번 스텝에서 Left 키 → 0 유지 (max(0, -1))."""
        tut = self._make_tutorial()
        tut.visible = True
        tut.current_step = 0
        with patch("tutorial._load_progress", return_value={}):
            with patch("tutorial._save_progress"):
                ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_LEFT)
                result = tut.handle_event(ev)
        self.assertTrue(result)
        self.assertEqual(tut.current_step, 0)

    def test_escape_finishes(self):
        """ESC 키로 튜토리얼 종료."""
        tut = self._make_tutorial()
        tut.visible = True
        with patch("tutorial._load_progress", return_value={}):
            with patch("tutorial._save_progress"):
                ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_ESCAPE)
                result = tut.handle_event(ev)
        self.assertTrue(result)
        self.assertFalse(tut.visible)
        self.assertTrue(tut._completed)

    def test_other_key_when_visible(self):
        """visible 상태에서 처리되지 않는 키 → False."""
        tut = self._make_tutorial()
        tut.visible = True
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_g)
        result = tut.handle_event(ev)
        self.assertFalse(result)

    def test_other_key_when_hidden(self):
        """hidden 상태에서 T 외의 키 → False."""
        tut = self._make_tutorial()
        tut.visible = False
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_g)
        result = tut.handle_event(ev)
        self.assertFalse(result)


class TestTutorialOverlaySaveStep(unittest.TestCase):
    """_save_step() 테스트."""

    def test_save_step_writes_progress(self):
        """현재 스텝이 진행 상태 파일에 저장됨."""
        with patch("tutorial._load_progress", return_value={}):
            with patch("tutorial._save_progress") as mock_save:
                tut = TutorialOverlay("tunneling", auto_show=False)
                tut.current_step = 5
                tut._save_step()
                mock_save.assert_called_once()
                saved_data = mock_save.call_args[0][0]
                self.assertEqual(saved_data["tunneling"]["step"], 5)
                self.assertFalse(saved_data["tunneling"]["completed"])


class TestTutorialOverlayFinish(unittest.TestCase):
    """_finish() 테스트."""

    def test_finish_sets_completed(self):
        """_finish() 호출 시 visible=False, _completed=True."""
        with patch("tutorial._load_progress", return_value={}):
            with patch("tutorial._save_progress") as mock_save:
                tut = TutorialOverlay("tunneling", auto_show=False)
                tut.visible = True
                tut._finish()
                self.assertFalse(tut.visible)
                self.assertTrue(tut._completed)
                mock_save.assert_called_once()
                saved_data = mock_save.call_args[0][0]
                self.assertTrue(saved_data["tunneling"]["completed"])
                self.assertEqual(saved_data["tunneling"]["step"], len(tut.steps))


class TestTutorialOverlayDraw(unittest.TestCase):
    """draw() 렌더링 테스트."""

    def _make_tutorial_visible(self):
        """visible=True인 TutorialOverlay 생성."""
        with patch("tutorial._load_progress", return_value={}):
            tut = TutorialOverlay("tunneling", auto_show=False)
        tut.visible = True
        tut.current_step = 0
        return tut

    def test_draw_hidden_noop(self):
        """visible=False이면 아무것도 하지 않음."""
        tut = TutorialOverlay("tunneling", auto_show=False)
        tut.visible = False
        screen = _make_mock_surface()
        font = _make_mock_font()
        screen.blit.reset_mock()
        tut.draw(screen, font)
        screen.blit.assert_not_called()

    def test_draw_no_steps_noop(self):
        """steps가 비어있으면 아무것도 하지 않음."""
        with patch("tutorial._load_progress", return_value={}):
            tut = TutorialOverlay("nonexistent", auto_show=False)
        tut.visible = True
        screen = _make_mock_surface()
        font = _make_mock_font()
        screen.blit.reset_mock()
        tut.draw(screen, font)
        screen.blit.assert_not_called()

    @patch("tutorial.pygame", None)
    def test_draw_pygame_none_noop(self):
        """pygame이 None이면 아무것도 하지 않음."""
        tut = self._make_tutorial_visible()
        screen = _make_mock_surface()
        font = _make_mock_font()
        screen.blit.reset_mock()
        tut.draw(screen, font)
        screen.blit.assert_not_called()

    @patch("tutorial.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_visible_renders(self, mock_t):
        """visible 상태에서 정상 렌더링."""
        tut = self._make_tutorial_visible()
        screen = _make_mock_surface()
        font = _make_mock_font()
        tut.draw(screen, font)
        # 배경 + 스텝 텍스트 + 타이틀 + 본문 + 네비게이션 힌트
        self.assertGreater(screen.blit.call_count, 1)
        # font.render가 여러 번 호출됨
        self.assertGreater(font.render.call_count, 0)

    @patch("tutorial.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_multiline_text(self, mock_t):
        """멀티라인 본문이 줄별로 렌더링."""
        tut = self._make_tutorial_visible()
        tut.current_step = 0
        screen = _make_mock_surface()
        font = _make_mock_font()
        tut.draw(screen, font)
        # tunneling 첫 스텝의 text에는 \n이 포함
        step_text = tut.steps[0]["text"]
        expected_lines = len(step_text.split("\n"))
        # font.render 호출 수 >= expected_lines (스텝 표시 + 타이틀 + 네비 포함)
        self.assertGreaterEqual(font.render.call_count, expected_lines)


class TestTutorialLoadSaveProgress(unittest.TestCase):
    """_load_progress() / _save_progress() 테스트."""

    def test_load_nonexistent_file(self):
        """파일이 없으면 빈 dict 반환."""
        with patch("tutorial.os.path.exists", return_value=False):
            result = _load_progress()
        self.assertEqual(result, {})

    def test_load_valid_dict(self):
        """유효한 dict JSON 파일 로드."""
        data = {"tunneling": {"completed": True, "step": 8}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            tmp_path = f.name
        try:
            with patch("tutorial._SAVE_PATH", tmp_path):
                result = _load_progress()
            self.assertEqual(result, data)
        finally:
            os.unlink(tmp_path)

    def test_load_legacy_list_format(self):
        """레거시 리스트 형식 → dict로 변환."""
        data = ["tunneling", "qubit_chain"]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            tmp_path = f.name
        try:
            with patch("tutorial._SAVE_PATH", tmp_path):
                result = _load_progress()
            self.assertIn("tunneling", result)
            self.assertTrue(result["tunneling"]["completed"])
            self.assertIn("qubit_chain", result)
        finally:
            os.unlink(tmp_path)

    def test_load_corrupted_json(self):
        """손상된 JSON → 빈 dict 반환."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{corrupted!!!")
            tmp_path = f.name
        try:
            with patch("tutorial._SAVE_PATH", tmp_path):
                with patch("tutorial._log"):
                    result = _load_progress()
            self.assertEqual(result, {})
        finally:
            os.unlink(tmp_path)

    def test_load_oserror(self):
        """파일 읽기 실패 → 빈 dict 반환."""
        with patch("tutorial.os.path.exists", return_value=True):
            with patch("builtins.open", side_effect=OSError("read error")):
                with patch("tutorial._log"):
                    result = _load_progress()
        self.assertEqual(result, {})

    def test_save_progress_success(self):
        """정상 저장."""
        data = {"tunneling": {"completed": True, "step": 5}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp_path = f.name
        try:
            with patch("tutorial._SAVE_PATH", tmp_path):
                _save_progress(data)
            with open(tmp_path) as f:
                saved = json.load(f)
            self.assertEqual(saved, data)
        finally:
            os.unlink(tmp_path)

    def test_save_progress_oserror(self):
        """저장 실패 시 로그 경고 (예외 발생 안 함)."""
        with patch("builtins.open", side_effect=OSError("write error")):
            with patch("tutorial._log") as mock_log:
                _save_progress({"test": {}})
                mock_log.warning.assert_called()


class TestTutorialStepsData(unittest.TestCase):
    """_TUTORIAL_STEPS 데이터 무결성 테스트."""

    def test_all_modules_have_steps(self):
        """등록된 모든 모듈에 스텝 리스트가 존재."""
        for module, steps in _TUTORIAL_STEPS.items():
            self.assertIsInstance(steps, list, f"{module} 스텝이 리스트가 아님")
            self.assertGreater(len(steps), 0, f"{module} 스텝이 비어있음")

    def test_step_structure(self):
        """각 스텝에 title, text, highlight 키가 있음."""
        for module, steps in _TUTORIAL_STEPS.items():
            for i, step in enumerate(steps):
                self.assertIn("title", step, f"{module}[{i}] title 누락")
                self.assertIn("text", step, f"{module}[{i}] text 누락")
                self.assertIn("highlight", step, f"{module}[{i}] highlight 누락")


# ================================================================
# GlossaryOverlay 테스트
# ================================================================
class TestGlossaryBuildLines(unittest.TestCase):
    """_build_lines() 함수 테스트."""

    def test_build_lines_returns_list(self):
        """리스트를 반환."""
        lines = _build_lines()
        self.assertIsInstance(lines, list)
        self.assertGreater(len(lines), 0)

    def test_build_lines_tuples(self):
        """각 항목이 (text, color) 튜플."""
        lines = _build_lines()
        for line in lines:
            self.assertIsInstance(line, tuple)
            self.assertEqual(len(line), 2)
            self.assertIsInstance(line[0], str)
            self.assertIsInstance(line[1], tuple)
            self.assertEqual(len(line[1]), 3)

    def test_category_headers(self):
        """카테고리 헤더가 ━━ 접두사로 생성."""
        lines = _build_lines()
        category_lines = [l for l in lines if l[0].startswith("━━")]
        # _GLOSSARY_ENTRIES에 category가 있는 항목 수만큼 존재
        categories_in_data = sum(1 for e in _GLOSSARY_ENTRIES if "category" in e)
        self.assertEqual(len(category_lines), categories_in_data)

    def test_term_lines(self):
        """용어 라인이 ▸ 접두사로 생성."""
        lines = _build_lines()
        term_lines = [l for l in lines if l[0].startswith("▸")]
        self.assertEqual(len(term_lines), len(_GLOSSARY_ENTRIES))

    def test_formula_lines(self):
        """수식이 있는 항목에 ▹ 접두사 라인 생성."""
        lines = _build_lines()
        formula_lines = [l for l in lines if "▹" in l[0]]
        formula_entries = sum(1 for e in _GLOSSARY_ENTRIES if "formula" in e)
        self.assertEqual(len(formula_lines), formula_entries)

    def test_formula_color(self):
        """수식 라인은 보라색."""
        lines = _build_lines()
        formula_lines = [l for l in lines if "▹" in l[0]]
        for line in formula_lines:
            self.assertEqual(line[1], (203, 166, 247))

    def test_category_color(self):
        """카테고리 라인은 파란색."""
        lines = _build_lines()
        category_lines = [l for l in lines if l[0].startswith("━━")]
        for line in category_lines:
            self.assertEqual(line[1], (137, 180, 250))

    def test_term_color(self):
        """용어 라인은 노란색."""
        lines = _build_lines()
        term_lines = [l for l in lines if l[0].startswith("▸")]
        for line in term_lines:
            self.assertEqual(line[1], (249, 226, 175))

    def test_def_lines_multiline(self):
        """정의 텍스트 중 \n이 포함된 항목은 여러 줄로 분리."""
        lines = _build_lines()
        # 정의 줄 (4칸 들여쓰기, ▹가 아닌 것)
        def_lines = [l for l in lines if l[0].startswith("    ") and "▹" not in l[0]]
        self.assertGreater(len(def_lines), 0)

    def test_empty_separator_lines(self):
        """빈 줄 구분자가 생성됨."""
        lines = _build_lines()
        empty_lines = [l for l in lines if l[0] == ""]
        self.assertGreater(len(empty_lines), 0)


class TestGlossaryOverlayInit(unittest.TestCase):
    """GlossaryOverlay 초기화 테스트."""

    def test_initial_state(self):
        """초기 상태 확인."""
        g = GlossaryOverlay()
        self.assertFalse(g.visible)
        self.assertEqual(g.scroll, 0)
        self.assertGreater(len(g._lines), 0)

    def test_max_scroll_property(self):
        """_max_scroll 프로퍼티 계산."""
        g = GlossaryOverlay()
        expected = max(0, len(g._lines) - 20)
        self.assertEqual(g._max_scroll, expected)


class TestGlossaryOverlayHandleEvent(unittest.TestCase):
    """handle_event() 이벤트 처리 테스트."""

    @patch("glossary.pygame", None)
    def test_pygame_none_returns_false(self):
        """pygame이 None이면 False 반환."""
        g = GlossaryOverlay()
        ev = _make_event(768, 103)
        result = g.handle_event(ev)
        self.assertFalse(result)

    def test_non_keydown_ignored(self):
        """KEYDOWN이 아닌 이벤트는 무시."""
        g = GlossaryOverlay()
        ev = _make_event(_pg_mock.MOUSEBUTTONDOWN, None)
        result = g.handle_event(ev)
        self.assertFalse(result)

    def test_g_key_opens(self):
        """G 키로 용어집 열기."""
        g = GlossaryOverlay()
        g.visible = False
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_g)
        result = g.handle_event(ev)
        self.assertTrue(result)
        self.assertTrue(g.visible)
        self.assertEqual(g.scroll, 0)

    def test_g_key_closes_when_visible(self):
        """G 키로 용어집 닫기 (visible일 때)."""
        g = GlossaryOverlay()
        g.visible = True
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_g)
        result = g.handle_event(ev)
        self.assertTrue(result)
        self.assertFalse(g.visible)

    def test_escape_closes(self):
        """ESC 키로 닫기."""
        g = GlossaryOverlay()
        g.visible = True
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_ESCAPE)
        result = g.handle_event(ev)
        self.assertTrue(result)
        self.assertFalse(g.visible)

    def test_scroll_down(self):
        """Down 키로 스크롤 다운."""
        g = GlossaryOverlay()
        g.visible = True
        g.scroll = 0
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_DOWN)
        result = g.handle_event(ev)
        self.assertTrue(result)
        self.assertEqual(g.scroll, 3)  # _SCROLL_STEP = 3

    def test_scroll_down_pagedown(self):
        """PageDown 키로 스크롤 다운."""
        g = GlossaryOverlay()
        g.visible = True
        g.scroll = 0
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_PAGEDOWN)
        result = g.handle_event(ev)
        self.assertTrue(result)
        self.assertEqual(g.scroll, 3)

    def test_scroll_up(self):
        """Up 키로 스크롤 업."""
        g = GlossaryOverlay()
        g.visible = True
        g.scroll = 6
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_UP)
        result = g.handle_event(ev)
        self.assertTrue(result)
        self.assertEqual(g.scroll, 3)

    def test_scroll_up_pageup(self):
        """PageUp 키로 스크롤 업."""
        g = GlossaryOverlay()
        g.visible = True
        g.scroll = 6
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_PAGEUP)
        result = g.handle_event(ev)
        self.assertTrue(result)
        self.assertEqual(g.scroll, 3)

    def test_scroll_down_clamped_to_max(self):
        """스크롤이 _max_scroll을 초과하지 않음."""
        g = GlossaryOverlay()
        g.visible = True
        g.scroll = g._max_scroll
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_DOWN)
        result = g.handle_event(ev)
        self.assertTrue(result)
        self.assertEqual(g.scroll, g._max_scroll)

    def test_scroll_up_clamped_to_zero(self):
        """스크롤이 0 미만으로 내려가지 않음."""
        g = GlossaryOverlay()
        g.visible = True
        g.scroll = 0
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_UP)
        result = g.handle_event(ev)
        self.assertTrue(result)
        self.assertEqual(g.scroll, 0)

    def test_other_key_when_visible(self):
        """visible 상태에서 처리되지 않는 키 → False."""
        g = GlossaryOverlay()
        g.visible = True
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_t)
        result = g.handle_event(ev)
        self.assertFalse(result)

    def test_other_key_when_hidden(self):
        """hidden 상태에서 G 외의 키 → False."""
        g = GlossaryOverlay()
        g.visible = False
        ev = _make_event(_pg_mock.KEYDOWN, _pg_mock.K_t)
        result = g.handle_event(ev)
        self.assertFalse(result)


class TestGlossaryOverlayDraw(unittest.TestCase):
    """draw() 렌더링 테스트."""

    @patch("glossary.pygame", None)
    def test_draw_pygame_none(self):
        """pygame이 None이면 즉시 반환."""
        g = GlossaryOverlay()
        g.visible = True
        screen = _make_mock_surface()
        font = _make_mock_font()
        screen.blit.reset_mock()
        g.draw(screen, font)
        screen.blit.assert_not_called()

    def test_draw_hidden_noop(self):
        """hidden 상태면 아무것도 하지 않음."""
        g = GlossaryOverlay()
        g.visible = False
        screen = _make_mock_surface()
        font = _make_mock_font()
        screen.blit.reset_mock()
        g.draw(screen, font)
        screen.blit.assert_not_called()

    @patch("glossary.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_visible_renders(self, mock_t):
        """visible 상태에서 정상 렌더링."""
        g = GlossaryOverlay()
        g.visible = True
        screen = _make_mock_surface()
        font = _make_mock_font()
        g.draw(screen, font)
        # 배경 + 타이틀 + 인디케이터 + 본문 + 네비게이션 힌트
        self.assertGreater(screen.blit.call_count, 1)

    @patch("glossary.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_scroll_indicator(self, mock_t):
        """스크롤 인디케이터가 렌더링."""
        g = GlossaryOverlay()
        g.visible = True
        g.scroll = 5
        screen = _make_mock_surface()
        font = _make_mock_font()
        g.draw(screen, font)
        # 인디케이터 텍스트가 렌더링되었는지 확인
        rendered_texts = [call[0][0] for call in font.render.call_args_list]
        indicator_texts = [t for t in rendered_texts if t.startswith("(")]
        self.assertGreater(len(indicator_texts), 0)

    @patch("glossary.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_scrolled_content(self, mock_t):
        """스크롤 후 다른 내용 렌더링."""
        g = GlossaryOverlay()
        g.visible = True
        g.scroll = 10
        screen = _make_mock_surface()
        font = _make_mock_font()
        g.draw(screen, font)
        # 에러 없이 렌더링 완료
        screen.blit.assert_called()

    @patch("glossary.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_small_screen(self, mock_t):
        """작은 화면에서도 에러 없이 렌더링."""
        g = GlossaryOverlay()
        g.visible = True
        screen = _make_mock_surface(200, 100)
        font = _make_mock_font()
        g.draw(screen, font)
        screen.blit.assert_called()

    @patch("glossary.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_empty_text_lines_skipped(self, mock_t):
        """빈 텍스트 줄은 렌더링하지 않음 (간격만)."""
        g = GlossaryOverlay()
        g.visible = True
        screen = _make_mock_surface()
        font = _make_mock_font()
        g.draw(screen, font)
        # font.render에 빈 문자열이 전달되지 않아야 함
        # (인디케이터, 타이틀 등은 빈 문자열 아님)
        rendered_texts = [call[0][0] for call in font.render.call_args_list]
        # 빈 줄은 렌더링하지 않으므로 ""가 포함되면 안 됨
        non_empty_only = [t for t in rendered_texts if t == ""]
        self.assertEqual(len(non_empty_only), 0)

    @patch("glossary.t", side_effect=lambda key, **kw: f"[{key}]")
    def test_draw_overflow_lines_stop(self, mock_t):
        """박스 하단을 넘는 라인은 중단."""
        g = GlossaryOverlay()
        g.visible = True
        # 매우 작은 화면으로 오버플로 유도
        screen = _make_mock_surface(300, 120)
        font = _make_mock_font()
        g.draw(screen, font)
        # 에러 없이 완료
        screen.blit.assert_called()


class TestGlossaryOverlayMaxScrollEdge(unittest.TestCase):
    """_max_scroll 엣지 케이스."""

    def test_max_scroll_with_few_lines(self):
        """라인이 20개 미만이면 _max_scroll=0."""
        g = GlossaryOverlay()
        original_lines = g._lines
        g._lines = [("test", (255, 255, 255))] * 10
        self.assertEqual(g._max_scroll, 0)
        g._lines = original_lines

    def test_max_scroll_exactly_20(self):
        """라인이 정확히 20개면 _max_scroll=0."""
        g = GlossaryOverlay()
        original_lines = g._lines
        g._lines = [("test", (255, 255, 255))] * 20
        self.assertEqual(g._max_scroll, 0)
        g._lines = original_lines

    def test_max_scroll_21_lines(self):
        """라인이 21개면 _max_scroll=1."""
        g = GlossaryOverlay()
        original_lines = g._lines
        g._lines = [("test", (255, 255, 255))] * 21
        self.assertEqual(g._max_scroll, 1)
        g._lines = original_lines


# ================================================================
# GlossaryOverlay 데이터 무결성 테스트
# ================================================================
class TestGlossaryEntriesData(unittest.TestCase):
    """_GLOSSARY_ENTRIES 데이터 무결성 테스트."""

    def test_all_entries_have_term(self):
        """모든 항목에 term 키 존재."""
        for i, entry in enumerate(_GLOSSARY_ENTRIES):
            self.assertIn("term", entry, f"항목 {i}에 term 누락")

    def test_all_entries_have_def(self):
        """모든 항목에 def 키 존재."""
        for i, entry in enumerate(_GLOSSARY_ENTRIES):
            self.assertIn("def", entry, f"항목 {i}에 def 누락")

    def test_categories_are_strings(self):
        """카테고리 값이 문자열."""
        for entry in _GLOSSARY_ENTRIES:
            if "category" in entry:
                self.assertIsInstance(entry["category"], str)


if __name__ == "__main__":
    unittest.main()
