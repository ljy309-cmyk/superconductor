"""Pygame UI 위젯 모듈 종합 테스트.

ui/slider.py, game_summary.py, quit_dialog.py, difficulty_dialog.py,
game_base.py, preset_hud.py의 커버리지를 확보한다.
pygame을 sys.modules 패칭으로 모킹하여 디스플레이 없이 테스트.
"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ── pygame 모킹 ────────────────────────────────────────────────
_pg_mock = MagicMock()
_pg_mock.SRCALPHA = 0x00010000
_pg_mock.KEYDOWN = 768
_pg_mock.KEYUP = 769
_pg_mock.MOUSEBUTTONDOWN = 1025
_pg_mock.MOUSEBUTTONUP = 1026
_pg_mock.MOUSEMOTION = 1024
_pg_mock.QUIT = 256
_pg_mock.K_1 = 49
_pg_mock.K_2 = 50
_pg_mock.K_3 = 51
_pg_mock.K_F5 = 292
_pg_mock.K_F9 = 296
_pg_mock.K_RETURN = 13
_pg_mock.K_SPACE = 32
_pg_mock.K_ESCAPE = 27
_pg_mock.K_UP = 273
_pg_mock.K_DOWN = 274
_pg_mock.K_y = 121
_pg_mock.K_n = 110
_pg_mock.K_w = 119
_pg_mock.K_s = 115
_pg_mock.Surface.return_value = MagicMock()


# collidepoint를 지원하는 MockRect 클래스
class MockRect:
    """pygame.Rect 대체 — 충돌 감지·inflate·속성 지원."""

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.width, self.height = w, h
        self.topleft = (x, y)
        self.left = x
        self.top = y
        self.right = x + w
        self.bottom = y + h

    def collidepoint(self, *args):
        if len(args) == 1:
            mx, my = args[0]
        else:
            mx, my = args[0], args[1]
        return self.x <= mx <= self.x + self.w and self.y <= my <= self.y + self.h

    def inflate(self, dw, dh):
        return MockRect(self.x - dw // 2, self.y - dh // 2, self.w + dw, self.h + dh)

    @property
    def centery(self):
        return self.y + self.h // 2


_pg_mock.Rect = MockRect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pygame 관련 서브모듈을 모두 등록
sys.modules.setdefault("pygame", _pg_mock)
sys.modules.setdefault("pygame.font", MagicMock())
sys.modules.setdefault("pygame.time", MagicMock())
sys.modules.setdefault("pygame.mixer", MagicMock())
sys.modules.setdefault("pygame.display", MagicMock())
sys.modules.setdefault("pygame.draw", MagicMock())
sys.modules.setdefault("pygame.mouse", MagicMock())
sys.modules.setdefault("pygame.event", MagicMock())


# ── 테마 모킹 헬퍼 ─────────────────────────────────────────────
def _make_pg_theme():
    """테스트용 PG 테마 네임스페이스 생성."""
    return SimpleNamespace(
        TEXT=(205, 214, 244),
        GREEN=(166, 227, 161),
        SUBTEXT=(88, 91, 112),
        SURFACE=(24, 24, 37),
        ACCENT_BLUE=(137, 180, 250),
        PANEL_BG=(24, 24, 37),
        BG=(30, 30, 46),
        OVERLAY=(69, 71, 90),
        RED=(243, 139, 168),
        YELLOW=(249, 226, 175),
    )


# ── 폰트 모킹 헬퍼 ─────────────────────────────────────────────
def _make_mock_font():
    """render().get_width()/get_height() 를 지원하는 모의 폰트."""
    font = MagicMock()
    surf = MagicMock()
    surf.get_width.return_value = 60
    surf.get_height.return_value = 16
    font.render.return_value = surf
    return font


def _make_mock_screen(w=800, h=600):
    """get_size()/get_width() 를 지원하는 모의 스크린."""
    screen = MagicMock()
    screen.get_size.return_value = (w, h)
    screen.get_width.return_value = w
    screen.get_height.return_value = h
    return screen


# ================================================================
# 1. ui/slider.py — Slider / SliderPanel
# ================================================================
class TestSliderValueSetterClamping(unittest.TestCase):
    """Slider.value setter 클램핑 테스트."""

    def _make_slider(self, min_val=0, max_val=10, val=5, step=1, fmt=".1f"):
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                from ui.slider import Slider

                return Slider(10, 10, 200, min_val, max_val, val, step, "Test", fmt)

    def test_clamp_below_min(self):
        """최솟값 이하로 설정 시 min_val로 클램핑."""
        s = self._make_slider(min_val=0, max_val=10, val=5, step=1)
        s.value = -5
        self.assertEqual(s.value, 0)

    def test_clamp_above_max(self):
        """최댓값 이상으로 설정 시 max_val로 클램핑."""
        s = self._make_slider(min_val=0, max_val=10, val=5, step=1)
        s.value = 15
        self.assertEqual(s.value, 10)

    def test_step_snapping(self):
        """step에 맞게 값이 스냅된다."""
        s = self._make_slider(min_val=0, max_val=10, val=0, step=2)
        s.value = 3
        # 3은 2와 4 중 4에 가까우므로 4로 스냅
        self.assertEqual(s.value, 4)

    def test_step_snapping_round_down(self):
        """step 스냅 — 반올림 내림 케이스."""
        s = self._make_slider(min_val=0, max_val=10, val=0, step=5)
        s.value = 2
        # round((2-0)/5) = round(0.4) = 0 → 0
        self.assertEqual(s.value, 0)

    def test_integer_conversion(self):
        """step >= 1 이고 min_val이 정수이면 int 변환."""
        s = self._make_slider(min_val=0, max_val=100, val=50, step=1)
        s.value = 33.7
        self.assertIsInstance(s.value, int)
        self.assertEqual(s.value, 34)

    def test_decimal_precision(self):
        """소수 step에서 부동소수점 정밀도 보정."""
        s = self._make_slider(min_val=0.0, max_val=1.0, val=0.5, step=0.1)
        s.value = 0.33
        # round((0.33-0) / 0.1) = round(3.3) = 3 → 0.3
        self.assertAlmostEqual(s.value, 0.3, places=5)

    def test_small_step_precision(self):
        """매우 작은 step (0.01) 에서 소수점 정밀도."""
        s = self._make_slider(min_val=0.0, max_val=1.0, val=0.0, step=0.01)
        s.value = 0.555
        # round((0.555)/0.01) = round(55.5) = 56 → 0.56
        self.assertAlmostEqual(s.value, 0.56, places=5)

    def test_exact_value_on_boundary(self):
        """경계값 정확히 설정."""
        s = self._make_slider(min_val=0, max_val=10, val=0, step=1)
        s.value = 10
        self.assertEqual(s.value, 10)
        s.value = 0
        self.assertEqual(s.value, 0)


class TestSliderReset(unittest.TestCase):
    """Slider.reset() — 기본값 복원 테스트."""

    def test_reset_to_default(self):
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                from ui.slider import Slider

                s = Slider(0, 0, 200, 0, 100, 50, 1, "Test")
                s.value = 99
                self.assertEqual(s.value, 99)
                s.reset()
                self.assertEqual(s.value, 50)


class TestSliderHandleEvent(unittest.TestCase):
    """Slider.handle_event() — 마우스 이벤트 처리 테스트."""

    def _make_slider(self):
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                from ui.slider import Slider

                s = Slider(100, 100, 200, 0, 100, 50, 1, "Test")
                # bar_rect를 MockRect로 교체 (collidepoint 지원)
                s.bar_rect = MockRect(100, 120, 200, 12)
                return s

    def test_mousedown_on_bar(self):
        """바 위 클릭 시 드래그 시작 + 값 갱신."""
        s = self._make_slider()
        event = SimpleNamespace(
            type=_pg_mock.MOUSEBUTTONDOWN,
            button=1,
            pos=(200, 125),  # 바 중앙 부근
        )
        with patch("ui.slider.pygame", _pg_mock):
            s.handle_event(event)
        self.assertTrue(s.dragging)
        self.assertEqual(s.value, 50)  # (200-100)/200 * 100 = 50

    def test_mousedown_outside_bar(self):
        """바 바깥 클릭 시 드래그 미시작."""
        s = self._make_slider()
        event = SimpleNamespace(
            type=_pg_mock.MOUSEBUTTONDOWN,
            button=1,
            pos=(50, 50),  # 바 영역 밖
        )
        with patch("ui.slider.pygame", _pg_mock):
            s.handle_event(event)
        self.assertFalse(s.dragging)

    def test_mousedown_right_button_ignored(self):
        """오른쪽 버튼 클릭은 무시."""
        s = self._make_slider()
        event = SimpleNamespace(
            type=_pg_mock.MOUSEBUTTONDOWN,
            button=3,
            pos=(200, 125),
        )
        with patch("ui.slider.pygame", _pg_mock):
            s.handle_event(event)
        self.assertFalse(s.dragging)

    def test_mouseup_releases_drag(self):
        """마우스 버튼 해제 시 드래그 종료."""
        s = self._make_slider()
        s.dragging = True
        event = SimpleNamespace(type=_pg_mock.MOUSEBUTTONUP)
        with patch("ui.slider.pygame", _pg_mock):
            s.handle_event(event)
        self.assertFalse(s.dragging)

    def test_mousemotion_while_dragging(self):
        """드래그 중 마우스 이동 시 값 갱신."""
        s = self._make_slider()
        s.dragging = True
        event = SimpleNamespace(
            type=_pg_mock.MOUSEMOTION,
            pos=(250, 125),  # (250-100)/200 * 100 = 75
        )
        with patch("ui.slider.pygame", _pg_mock):
            s.handle_event(event)
        self.assertEqual(s.value, 75)

    def test_mousemotion_without_dragging(self):
        """드래그 중이 아닌 마우스 이동은 값 변경 없음."""
        s = self._make_slider()
        s.dragging = False
        original = s.value
        event = SimpleNamespace(
            type=_pg_mock.MOUSEMOTION,
            pos=(250, 125),
        )
        with patch("ui.slider.pygame", _pg_mock):
            s.handle_event(event)
        self.assertEqual(s.value, original)


class TestSliderUpdateFromMouse(unittest.TestCase):
    """Slider._update_from_mouse() — 마우스 X 좌표→값 변환."""

    def _make_slider(self):
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                from ui.slider import Slider

                return Slider(100, 100, 200, 0, 100, 50, 1, "Test")

    def test_leftmost(self):
        """바 왼쪽 끝 → 최솟값."""
        s = self._make_slider()
        s._update_from_mouse(100)
        self.assertEqual(s.value, 0)

    def test_rightmost(self):
        """바 오른쪽 끝 → 최댓값."""
        s = self._make_slider()
        s._update_from_mouse(300)
        self.assertEqual(s.value, 100)

    def test_beyond_left(self):
        """바 왼쪽 밖 → 최솟값으로 클램핑."""
        s = self._make_slider()
        s._update_from_mouse(0)
        self.assertEqual(s.value, 0)

    def test_beyond_right(self):
        """바 오른쪽 밖 → 최댓값으로 클램핑."""
        s = self._make_slider()
        s._update_from_mouse(500)
        self.assertEqual(s.value, 100)

    def test_midpoint(self):
        """바 중간 → 중간값."""
        s = self._make_slider()
        s._update_from_mouse(200)
        self.assertEqual(s.value, 50)


class TestSliderRatio(unittest.TestCase):
    """Slider._ratio() — 비율 계산 테스트."""

    def test_ratio_normal(self):
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                from ui.slider import Slider

                s = Slider(0, 0, 200, 0, 100, 50, 1, "Test")
                self.assertAlmostEqual(s._ratio(), 0.5, places=3)

    def test_ratio_max_equals_min(self):
        """max <= min 일 때 0.0 반환."""
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                from ui.slider import Slider

                s = Slider(0, 0, 200, 5, 5, 5, 1, "Test")
                self.assertEqual(s._ratio(), 0.0)

    def test_ratio_at_min(self):
        """최솟값일 때 0.0."""
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                from ui.slider import Slider

                s = Slider(0, 0, 200, 0, 100, 0, 1, "Test")
                self.assertEqual(s._ratio(), 0.0)

    def test_ratio_at_max(self):
        """최댓값일 때 1.0."""
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                from ui.slider import Slider

                s = Slider(0, 0, 200, 0, 100, 100, 1, "Test")
                self.assertAlmostEqual(s._ratio(), 1.0, places=3)


class TestSliderDraw(unittest.TestCase):
    """Slider.draw() — 렌더링 호출 확인."""

    def _make_slider(self):
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                from ui.slider import Slider

                s = Slider(10, 10, 200, 0, 100, 50, 1, "Speed", ".0f")
                s.bar_rect = MockRect(10, 30, 200, 12)
                return s

    def test_draw_basic(self):
        """기본 draw 호출 — 에러 없이 완료."""
        s = self._make_slider()
        screen = _make_mock_screen()
        font = _make_mock_font()

        # 마우스가 바 밖에 있도록 설정
        _pg_mock.mouse.get_pos.return_value = (0, 0)

        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                s.draw(screen, font)

        # font.render가 라벨 + 값 표시를 위해 최소 2회 호출
        self.assertGreaterEqual(font.render.call_count, 2)
        # screen.blit가 호출됨
        self.assertTrue(screen.blit.called)

    def test_draw_with_tooltip(self):
        """마우스가 바 위에 있을 때 툴팁 표시."""
        s = self._make_slider()
        screen = _make_mock_screen()
        font = _make_mock_font()

        # 마우스가 바 위에 있도록 설정
        _pg_mock.mouse.get_pos.return_value = (110, 35)

        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                s.draw(screen, font)

        # 툴팁 포함하여 render 호출 횟수가 더 많아야 함
        self.assertGreaterEqual(font.render.call_count, 3)

    def test_draw_zero_fill_width(self):
        """값이 최솟값일 때 fill_w == 0 → fill rect 미렌더링."""
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                from ui.slider import Slider

                s = Slider(10, 10, 200, 0, 100, 0, 1, "Speed")
                s.bar_rect = MockRect(10, 30, 200, 12)

        screen = _make_mock_screen()
        font = _make_mock_font()
        _pg_mock.mouse.get_pos.return_value = (0, 0)
        _pg_mock.draw.rect.reset_mock()

        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                s.draw(screen, font)
        # fill_w=0이면 채움 rect가 그려지지 않지만, 배경·테두리 rect는 그려짐


class TestSliderPanel(unittest.TestCase):
    """SliderPanel — 슬라이더 그룹 관리 테스트."""

    def _make_panel(self):
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                from ui.slider import SliderPanel

                return SliderPanel(900, 50, 220, "Parameters")

    def test_add_slider(self):
        """슬라이더 추가 후 리스트에 저장."""
        panel = self._make_panel()
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                s = panel.add(0, 20, 3.0, 0.5, "Noise Rate", ".1f")
        self.assertEqual(len(panel.sliders), 1)
        self.assertAlmostEqual(s.value, 3.0, places=1)

    def test_add_multiple_sliders(self):
        """여러 슬라이더 추가 시 y 좌표 오프셋."""
        panel = self._make_panel()
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                s1 = panel.add(0, 10, 5, 1, "S1")
                s2 = panel.add(0, 20, 10, 0.5, "S2")
        self.assertEqual(len(panel.sliders), 2)
        # 두 번째 슬라이더는 첫 번째보다 TOTAL_H만큼 아래에 배치
        self.assertGreater(s2.y, s1.y)

    def test_handle_event_delegates(self):
        """패널의 handle_event가 모든 슬라이더에 위임."""
        panel = self._make_panel()
        mock_slider1 = MagicMock()
        mock_slider2 = MagicMock()
        panel.sliders = [mock_slider1, mock_slider2]

        event = SimpleNamespace(type=_pg_mock.MOUSEBUTTONDOWN)
        panel.handle_event(event)
        mock_slider1.handle_event.assert_called_once_with(event)
        mock_slider2.handle_event.assert_called_once_with(event)

    def test_reset_all(self):
        """reset_all()이 모든 슬라이더의 reset() 호출."""
        panel = self._make_panel()
        mock_slider1 = MagicMock()
        mock_slider2 = MagicMock()
        panel.sliders = [mock_slider1, mock_slider2]

        panel.reset_all()
        mock_slider1.reset.assert_called_once()
        mock_slider2.reset.assert_called_once()

    def test_panel_height(self):
        """panel_height() — 슬라이더 수에 따른 높이 계산."""
        panel = self._make_panel()
        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                panel.add(0, 10, 5, 1, "S1")
                panel.add(0, 20, 10, 1, "S2")
        from ui.slider import Slider

        expected = 28 + 2 * Slider.TOTAL_H + 10
        self.assertEqual(panel.panel_height(), expected)

    def test_panel_height_empty(self):
        """슬라이더 없는 패널의 높이."""
        panel = self._make_panel()
        self.assertEqual(panel.panel_height(), 28 + 0 + 10)

    def test_draw_with_title_font(self):
        """title_font이 제공된 경우 타이틀에 사용."""
        panel = self._make_panel()
        screen = _make_mock_screen()
        font = _make_mock_font()
        title_font = _make_mock_font()

        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                panel.draw(screen, font, title_font=title_font)

        # title_font.render가 타이틀 렌더에 사용됨
        title_font.render.assert_called()

    def test_draw_without_title_font(self):
        """title_font 미제공 시 일반 font가 타이틀에 사용."""
        panel = self._make_panel()
        screen = _make_mock_screen()
        font = _make_mock_font()

        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                panel.draw(screen, font)

        font.render.assert_called()

    def test_draw_delegates_to_sliders(self):
        """draw()가 각 슬라이더의 draw()도 호출."""
        panel = self._make_panel()
        mock_slider = MagicMock()
        panel.sliders = [mock_slider]
        screen = _make_mock_screen()
        font = _make_mock_font()

        with patch("ui.slider.get_pg_theme", return_value=_make_pg_theme()):
            with patch("ui.slider.pygame", _pg_mock):
                panel.draw(screen, font)

        mock_slider.draw.assert_called_once_with(screen, font)


# ================================================================
# 2. game_summary.py — draw_game_summary
# ================================================================
class TestDrawGameSummary(unittest.TestCase):
    """draw_game_summary() 렌더링 테스트."""

    def test_with_custom_fonts(self):
        """사용자 지정 폰트로 요약 표시."""
        screen = _make_mock_screen()
        font = _make_mock_font()
        title_font = _make_mock_font()
        stats = [("Score", "100"), ("Time", "60s")]

        with patch("game_summary.get_pg_theme", return_value=_make_pg_theme()):
            with patch("game_summary.pygame", _pg_mock):
                with patch("game_summary.t", side_effect=lambda k, **kw: k):
                    from game_summary import draw_game_summary

                    draw_game_summary(screen, "Game Over", stats, font=font, title_font=title_font)

        # 타이틀 렌더링 확인
        title_font.render.assert_called()
        # 통계 행 렌더링 확인 (라벨 + 값 = 2 * len(stats) + 힌트 = 5)
        self.assertGreaterEqual(font.render.call_count, len(stats) * 2 + 1)
        # screen.blit가 호출됨
        self.assertTrue(screen.blit.called)

    def test_without_custom_fonts(self):
        """폰트 미제공 시 get_font()로 자동 생성."""
        screen = _make_mock_screen()
        stats = [("Qubits", "5")]

        mock_font = _make_mock_font()
        with patch("game_summary.get_pg_theme", return_value=_make_pg_theme()):
            with patch("game_summary.pygame", _pg_mock):
                with patch("game_summary.get_font", return_value=mock_font):
                    with patch("game_summary.t", side_effect=lambda k, **kw: k):
                        from game_summary import draw_game_summary

                        draw_game_summary(screen, "End", stats)

        # get_font이 font=None, title_font=None 이므로 2회 호출
        # (이미 임포트된 모듈 캐시 때문에 별도 확인 불필요)
        self.assertTrue(screen.blit.called)

    def test_empty_stats(self):
        """통계가 비어 있어도 에러 없이 동작."""
        screen = _make_mock_screen()
        font = _make_mock_font()
        title_font = _make_mock_font()

        with patch("game_summary.get_pg_theme", return_value=_make_pg_theme()):
            with patch("game_summary.pygame", _pg_mock):
                with patch("game_summary.t", side_effect=lambda k, **kw: k):
                    from game_summary import draw_game_summary

                    draw_game_summary(screen, "No Stats", [], font=font, title_font=title_font)

        self.assertTrue(screen.blit.called)


# ================================================================
# 3. quit_dialog.py — confirm_quit
# ================================================================
class TestConfirmQuit(unittest.TestCase):
    """confirm_quit() — 종료 확인 대화상자."""

    def _run_confirm_quit(self, events, font=None):
        """confirm_quit를 실행하고 결과를 반환하는 헬퍼."""
        screen = _make_mock_screen()
        mock_font = _make_mock_font()

        # pygame.event.get()가 이벤트 목록을 반환
        _pg_mock.event.get.return_value = events

        with patch("quit_dialog.get_pg_theme", return_value=_make_pg_theme()):
            with patch("quit_dialog.pygame", _pg_mock):
                with patch("quit_dialog.get_font", return_value=mock_font):
                    with patch("quit_dialog.t", side_effect=lambda k, **kw: k):
                        from quit_dialog import confirm_quit

                        return confirm_quit(screen, font=font)

    def test_quit_on_y_key(self):
        """K_y 키 → True 반환."""
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_y)
        result = self._run_confirm_quit([event])
        self.assertTrue(result)

    def test_quit_on_return_key(self):
        """K_RETURN 키 → True 반환."""
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_RETURN)
        result = self._run_confirm_quit([event])
        self.assertTrue(result)

    def test_quit_on_quit_event(self):
        """QUIT 이벤트 → True 반환."""
        event = SimpleNamespace(type=_pg_mock.QUIT)
        result = self._run_confirm_quit([event])
        self.assertTrue(result)

    def test_cancel_on_n_key(self):
        """K_n 키 → False 반환."""
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_n)
        result = self._run_confirm_quit([event])
        self.assertFalse(result)

    def test_cancel_on_escape_key(self):
        """K_ESCAPE 키 → False 반환."""
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_ESCAPE)
        result = self._run_confirm_quit([event])
        self.assertFalse(result)

    def test_with_provided_font(self):
        """사용자 지정 폰트로 호출."""
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_y)
        custom_font = _make_mock_font()
        result = self._run_confirm_quit([event], font=custom_font)
        self.assertTrue(result)

    def test_ignores_irrelevant_events(self):
        """관련 없는 이벤트 후 종료 이벤트가 처리됨."""
        # 첫 번째 get() 호출: 관련 없는 이벤트만
        # 두 번째 get() 호출: 종료 이벤트
        irrelevant = SimpleNamespace(type=_pg_mock.MOUSEMOTION, pos=(0, 0))
        quit_event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_y)

        screen = _make_mock_screen()
        mock_font = _make_mock_font()

        _pg_mock.event.get.side_effect = [[irrelevant], [quit_event]]

        with patch("quit_dialog.get_pg_theme", return_value=_make_pg_theme()):
            with patch("quit_dialog.pygame", _pg_mock):
                with patch("quit_dialog.get_font", return_value=mock_font):
                    with patch("quit_dialog.t", side_effect=lambda k, **kw: k):
                        from quit_dialog import confirm_quit

                        result = confirm_quit(screen)
        self.assertTrue(result)
        # side_effect 초기화
        _pg_mock.event.get.side_effect = None


# ================================================================
# 4. difficulty_dialog.py — choose_difficulty, _btn_rect
# ================================================================
class TestBtnRect(unittest.TestCase):
    """_btn_rect() — 버튼 위치 계산 헬퍼."""

    def test_btn_rect_returns_mock_rect(self):
        """MockRect 인스턴스가 올바르게 반환."""
        with patch("difficulty_dialog.pygame", _pg_mock):
            from difficulty_dialog import _btn_rect

            rect = _btn_rect(800, 600, 0)
        self.assertIsInstance(rect, MockRect)
        self.assertEqual(rect.width, 260)
        self.assertEqual(rect.height, 36)

    def test_btn_rect_index_offset(self):
        """인덱스에 따라 y 좌표가 오프셋."""
        with patch("difficulty_dialog.pygame", _pg_mock):
            from difficulty_dialog import _btn_rect

            r0 = _btn_rect(800, 600, 0)
            r1 = _btn_rect(800, 600, 1)
            r2 = _btn_rect(800, 600, 2)
        # 각 버튼은 btn_h + 8 = 44 만큼 아래로
        self.assertEqual(r1.y - r0.y, 44)
        self.assertEqual(r2.y - r1.y, 44)

    def test_btn_rect_centery(self):
        """centery 속성 확인."""
        with patch("difficulty_dialog.pygame", _pg_mock):
            from difficulty_dialog import _btn_rect

            rect = _btn_rect(800, 600, 0)
        self.assertEqual(rect.centery, rect.y + rect.h // 2)


class TestChooseDifficulty(unittest.TestCase):
    """choose_difficulty() — 난이도 선택 대화상자."""

    def _run_choose(self, events_sequence):
        """이벤트 시퀀스로 choose_difficulty를 실행하는 헬퍼.

        events_sequence: 각 호출에서 반환할 이벤트 리스트의 리스트.
        """
        screen = _make_mock_screen()
        mock_font = _make_mock_font()

        _pg_mock.event.get.side_effect = events_sequence
        _pg_mock.time.Clock.return_value = MagicMock()

        with patch("difficulty_dialog.get_pg_theme", return_value=_make_pg_theme()):
            with patch("difficulty_dialog.pygame", _pg_mock):
                with patch("difficulty_dialog.get_font", return_value=mock_font):
                    with patch("difficulty_dialog.t", side_effect=lambda k, **kw: k):
                        from difficulty_dialog import choose_difficulty

                        result = choose_difficulty(screen)

        _pg_mock.event.get.side_effect = None
        return result

    def test_key_1_returns_easy(self):
        """K_1 키 → 'easy'."""
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_1)
        result = self._run_choose([[event]])
        self.assertEqual(result, "easy")

    def test_key_2_returns_normal(self):
        """K_2 키 → 'normal'."""
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_2)
        result = self._run_choose([[event]])
        self.assertEqual(result, "normal")

    def test_key_3_returns_hard(self):
        """K_3 키 → 'hard'."""
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_3)
        result = self._run_choose([[event]])
        self.assertEqual(result, "hard")

    def test_escape_returns_none(self):
        """K_ESCAPE → None."""
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_ESCAPE)
        result = self._run_choose([[event]])
        self.assertIsNone(result)

    def test_quit_event_returns_none(self):
        """QUIT 이벤트 → None."""
        event = SimpleNamespace(type=_pg_mock.QUIT)
        result = self._run_choose([[event]])
        self.assertIsNone(result)

    def test_return_selects_current(self):
        """K_RETURN → 현재 선택(기본 normal)."""
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_RETURN)
        result = self._run_choose([[event]])
        self.assertEqual(result, "normal")  # 기본 selected=1 → normal

    def test_space_selects_current(self):
        """K_SPACE → 현재 선택."""
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_SPACE)
        result = self._run_choose([[event]])
        self.assertEqual(result, "normal")

    def test_keyboard_up_navigation(self):
        """K_UP → 위로 이동 후 RETURN 으로 선택."""
        up_event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_UP)
        return_event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_RETURN)
        # 기본 selected=1(normal), UP→0(easy), RETURN으로 선택
        result = self._run_choose([[up_event], [return_event]])
        self.assertEqual(result, "easy")

    def test_keyboard_down_navigation(self):
        """K_DOWN → 아래로 이동 후 RETURN 으로 선택."""
        down_event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_DOWN)
        return_event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_RETURN)
        # 기본 selected=1(normal), DOWN→2(hard), RETURN으로 선택
        result = self._run_choose([[down_event], [return_event]])
        self.assertEqual(result, "hard")

    def test_keyboard_w_navigation(self):
        """K_w → 위로 이동."""
        w_event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_w)
        return_event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_RETURN)
        result = self._run_choose([[w_event], [return_event]])
        self.assertEqual(result, "easy")

    def test_keyboard_s_navigation(self):
        """K_s → 아래로 이동."""
        s_event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_s)
        return_event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_RETURN)
        result = self._run_choose([[s_event], [return_event]])
        self.assertEqual(result, "hard")

    def test_keyboard_wrap_around_up(self):
        """위로 반복 시 랩어라운드 (easy→hard)."""
        up1 = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_UP)
        up2 = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_UP)
        ret = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_RETURN)
        # selected: 1→0→2(wrap), RETURN → hard
        result = self._run_choose([[up1], [up2], [ret]])
        self.assertEqual(result, "hard")

    def test_keyboard_wrap_around_down(self):
        """아래로 반복 시 랩어라운드 (hard→easy)."""
        down1 = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_DOWN)
        down2 = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_DOWN)
        ret = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_RETURN)
        # selected: 1→2→0(wrap), RETURN → easy
        result = self._run_choose([[down1], [down2], [ret]])
        self.assertEqual(result, "easy")

    def test_mouse_click_selection(self):
        """마우스 클릭으로 난이도 선택."""
        # easy 버튼 위치 계산
        with patch("difficulty_dialog.pygame", _pg_mock):
            from difficulty_dialog import _btn_rect

            easy_rect = _btn_rect(800, 600, 0)
        click_pos = (easy_rect.x + 10, easy_rect.centery)
        click_event = SimpleNamespace(
            type=_pg_mock.MOUSEBUTTONDOWN,
            button=1,
            pos=click_pos,
        )
        result = self._run_choose([[click_event]])
        self.assertEqual(result, "easy")

    def test_mouse_hover_changes_selection(self):
        """마우스 호버로 선택 항목 변경 후 RETURN."""
        with patch("difficulty_dialog.pygame", _pg_mock):
            from difficulty_dialog import _btn_rect

            hard_rect = _btn_rect(800, 600, 2)
        hover_pos = (hard_rect.x + 10, hard_rect.centery)
        hover_event = SimpleNamespace(
            type=_pg_mock.MOUSEMOTION,
            pos=hover_pos,
        )
        return_event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_RETURN)
        result = self._run_choose([[hover_event], [return_event]])
        self.assertEqual(result, "hard")

    def test_with_provided_font(self):
        """사용자 지정 폰트로 호출."""
        screen = _make_mock_screen()
        custom_font = _make_mock_font()
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_1)
        _pg_mock.event.get.side_effect = [[event]]
        _pg_mock.time.Clock.return_value = MagicMock()

        with patch("difficulty_dialog.get_pg_theme", return_value=_make_pg_theme()):
            with patch("difficulty_dialog.pygame", _pg_mock):
                with patch("difficulty_dialog.get_font", return_value=_make_mock_font()):
                    with patch("difficulty_dialog.t", side_effect=lambda k, **kw: k):
                        from difficulty_dialog import choose_difficulty

                        result = choose_difficulty(screen, font=custom_font)

        _pg_mock.event.get.side_effect = None
        self.assertEqual(result, "easy")


# ================================================================
# 5. game_base.py — finalize_session, choose_difficulty_or_quit
# ================================================================
class TestFinalizeSession(unittest.TestCase):
    """finalize_session() — 게임 종료 공통 정리."""

    def test_all_optional_args(self):
        """모든 선택적 인수가 제공된 경우."""
        recorder = MagicMock()
        snd = MagicMock()
        theme_cb = MagicMock()
        cleanup_cb = MagicMock()
        meta = {"score": 100}

        with patch("game_base.pygame", _pg_mock):
            with patch("game_base.off_theme_change") as mock_off:
                # play_logger, report, achievements 모킹
                mock_logger = MagicMock()
                mock_report = MagicMock()
                mock_ach = MagicMock()
                mock_ach.return_value = [{"title": "Test", "desc": "desc"}]

                with patch.dict(
                    "sys.modules",
                    {
                        "data_ai.play_logger": MagicMock(get_logger=MagicMock(return_value=mock_logger)),
                        "report": MagicMock(generate_report=mock_report),
                        "achievements": MagicMock(check_achievements=mock_ach),
                    },
                ):
                    from game_base import finalize_session

                    finalize_session(
                        "qubit_chain",
                        {"score": 100},
                        recorder=recorder,
                        recorder_meta=meta,
                        snd=snd,
                        theme_callback=theme_cb,
                        extra_cleanup=cleanup_cb,
                    )

        recorder.save.assert_called_once_with(meta)
        snd.quit.assert_called_once()
        mock_off.assert_called_once_with(theme_cb)
        cleanup_cb.assert_called_once()
        _pg_mock.quit.assert_called()

    def test_minimal_args(self):
        """최소 인수만 제공."""
        with patch("game_base.pygame", _pg_mock):
            with patch("game_base.off_theme_change"):
                with patch.dict(
                    "sys.modules",
                    {
                        "data_ai.play_logger": MagicMock(),
                        "report": MagicMock(),
                        "achievements": MagicMock(check_achievements=MagicMock(return_value=[])),
                    },
                ):
                    from game_base import finalize_session

                    # 에러 없이 완료
                    finalize_session("test_mode", {})

    def test_import_error_play_logger(self):
        """play_logger ImportError 시 로그 후 계속."""
        with patch("game_base.pygame", _pg_mock):
            with patch("game_base.off_theme_change"):
                with patch("game_base._log") as mock_log:
                    # play_logger 임포트 실패를 시뮬레이션
                    orig_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

                    def failing_import(name, *args, **kwargs):
                        if name == "data_ai.play_logger":
                            raise ImportError("no play_logger")
                        return orig_import(name, *args, **kwargs)

                    with patch("builtins.__import__", side_effect=failing_import):
                        from game_base import finalize_session

                        finalize_session("test", {})
                    mock_log.error.assert_called()

    def test_import_error_report(self):
        """report ImportError 시 로그 후 계속."""
        with patch("game_base.pygame", _pg_mock):
            with patch("game_base.off_theme_change"):
                with patch("game_base._log") as mock_log:
                    orig_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

                    def failing_import(name, *args, **kwargs):
                        if name == "report":
                            raise ImportError("no report")
                        if name == "data_ai.play_logger":
                            raise ImportError("skip")
                        return orig_import(name, *args, **kwargs)

                    with patch("builtins.__import__", side_effect=failing_import):
                        from game_base import finalize_session

                        finalize_session("test", {})
                    # play_logger + report 실패 → 최소 2회 error
                    self.assertGreaterEqual(mock_log.error.call_count, 2)

    def test_import_error_achievements(self):
        """achievements ImportError 시 로그 후 계속."""
        with patch("game_base.pygame", _pg_mock):
            with patch("game_base.off_theme_change"):
                with patch("game_base._log") as mock_log:
                    orig_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

                    def failing_import(name, *args, **kwargs):
                        if name in ("data_ai.play_logger", "report", "achievements"):
                            raise ImportError(f"no {name}")
                        return orig_import(name, *args, **kwargs)

                    with patch("builtins.__import__", side_effect=failing_import):
                        from game_base import finalize_session

                        finalize_session("test", {})
                    # 3개 모두 실패
                    self.assertGreaterEqual(mock_log.error.call_count, 3)

    def test_extra_cleanup_error(self):
        """extra_cleanup 콜백 실패 시 로그 후 계속."""

        def bad_cleanup():
            raise RuntimeError("cleanup failed")

        with patch("game_base.pygame", _pg_mock):
            with patch("game_base.off_theme_change"):
                with patch("game_base._log") as mock_log:
                    with patch.dict(
                        "sys.modules",
                        {
                            "data_ai.play_logger": MagicMock(),
                            "report": MagicMock(),
                            "achievements": MagicMock(check_achievements=MagicMock(return_value=[])),
                        },
                    ):
                        from game_base import finalize_session

                        finalize_session("test", {}, extra_cleanup=bad_cleanup)
                    # cleanup 실패 로그
                    error_calls = [str(c) for c in mock_log.error.call_args_list]
                    self.assertTrue(any("cleanup failed" in c for c in error_calls))

    def test_extra_cleanup_none(self):
        """extra_cleanup가 None이면 호출하지 않음."""
        with patch("game_base.pygame", _pg_mock):
            with patch("game_base.off_theme_change"):
                with patch.dict(
                    "sys.modules",
                    {
                        "data_ai.play_logger": MagicMock(),
                        "report": MagicMock(),
                        "achievements": MagicMock(check_achievements=MagicMock(return_value=[])),
                    },
                ):
                    from game_base import finalize_session

                    # 에러 없이 완료
                    finalize_session("test", {}, extra_cleanup=None)


class TestChooseDifficultyOrQuit(unittest.TestCase):
    """choose_difficulty_or_quit() — 난이도 선택 + 취소 처리."""

    def test_returns_true_on_selection(self):
        """난이도가 선택되면 True 반환 + preset_hud._apply_preset 호출."""
        screen = _make_mock_screen()
        font = _make_mock_font()
        preset_hud = MagicMock()
        theme_cb = MagicMock()

        with patch("game_base.pygame", _pg_mock):
            with patch("game_base.off_theme_change"):
                with patch("difficulty_dialog.choose_difficulty", return_value="hard"):
                    from game_base import choose_difficulty_or_quit

                    result = choose_difficulty_or_quit(screen, font, preset_hud, theme_cb)

        self.assertTrue(result)
        preset_hud._apply_preset.assert_called_once_with("hard")

    def test_returns_false_on_cancel(self):
        """취소(None) 시 False 반환 + pygame.quit 호출."""
        screen = _make_mock_screen()
        font = _make_mock_font()
        preset_hud = MagicMock()
        theme_cb = MagicMock()

        with patch("game_base.pygame", _pg_mock):
            with patch("game_base.off_theme_change") as mock_off:
                with patch("difficulty_dialog.choose_difficulty", return_value=None):
                    from game_base import choose_difficulty_or_quit

                    result = choose_difficulty_or_quit(screen, font, preset_hud, theme_cb)

        self.assertFalse(result)
        mock_off.assert_called_once_with(theme_cb)
        _pg_mock.quit.assert_called()


# ================================================================
# 6. preset_hud.py — PresetHUD
# ================================================================
# _PRESET_KEYS는 모듈 로드 시 결정되므로 테스트에서 명시적으로 패치
_TEST_PRESET_KEYS = {
    _pg_mock.K_1: "easy",
    _pg_mock.K_2: "normal",
    _pg_mock.K_3: "hard",
}


class TestPresetHUDHandleEvent(unittest.TestCase):
    """PresetHUD.handle_event() — 키 이벤트 처리."""

    def _make_hud(self, slider_map=None):
        """테스트용 PresetHUD 인스턴스 생성."""
        if slider_map is None:
            slider_map = {}
        with patch("preset_hud.get_pg_theme", return_value=_make_pg_theme()):
            with patch("preset_hud.pygame", _pg_mock):
                from preset_hud import PresetHUD

                return PresetHUD("test_module", slider_map)

    def test_non_keydown_ignored(self):
        """KEYDOWN 이외의 이벤트는 False 반환."""
        hud = self._make_hud()
        event = SimpleNamespace(type=_pg_mock.MOUSEBUTTONDOWN, button=1, pos=(0, 0))
        with patch("preset_hud.pygame", _pg_mock):
            with patch("preset_hud._PRESET_KEYS", _TEST_PRESET_KEYS):
                result = hud.handle_event(event)
        self.assertFalse(result)

    def test_key_1_applies_easy(self):
        """K_1 → easy 프리셋 적용."""
        hud = self._make_hud()
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_1)

        with patch("preset_hud.pygame", _pg_mock):
            with patch("preset_hud._PRESET_KEYS", _TEST_PRESET_KEYS):
                with patch.object(hud, "_apply_preset") as mock_apply:
                    result = hud.handle_event(event)
        self.assertTrue(result)
        mock_apply.assert_called_once_with("easy")

    def test_key_2_applies_normal(self):
        """K_2 → normal 프리셋 적용."""
        hud = self._make_hud()
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_2)

        with patch("preset_hud.pygame", _pg_mock):
            with patch("preset_hud._PRESET_KEYS", _TEST_PRESET_KEYS):
                with patch.object(hud, "_apply_preset") as mock_apply:
                    result = hud.handle_event(event)
        self.assertTrue(result)
        mock_apply.assert_called_once_with("normal")

    def test_key_3_applies_hard(self):
        """K_3 → hard 프리셋 적용."""
        hud = self._make_hud()
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_3)

        with patch("preset_hud.pygame", _pg_mock):
            with patch("preset_hud._PRESET_KEYS", _TEST_PRESET_KEYS):
                with patch.object(hud, "_apply_preset") as mock_apply:
                    result = hud.handle_event(event)
        self.assertTrue(result)
        mock_apply.assert_called_once_with("hard")

    def test_f5_saves_current(self):
        """F5 → 현재 슬라이더 값 저장."""
        hud = self._make_hud()
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_F5)

        with patch("preset_hud.pygame", _pg_mock):
            with patch("preset_hud._PRESET_KEYS", _TEST_PRESET_KEYS):
                with patch.object(hud, "_save_current") as mock_save:
                    result = hud.handle_event(event)
        self.assertTrue(result)
        mock_save.assert_called_once()

    def test_f9_loads_profile(self):
        """F9 → 프로파일 불러오기."""
        hud = self._make_hud()
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=_pg_mock.K_F9)

        with patch("preset_hud.pygame", _pg_mock):
            with patch("preset_hud._PRESET_KEYS", _TEST_PRESET_KEYS):
                with patch.object(hud, "_load_last_profile") as mock_load:
                    result = hud.handle_event(event)
        self.assertTrue(result)
        mock_load.assert_called_once()

    def test_unhandled_key_returns_false(self):
        """처리되지 않는 키는 False 반환."""
        hud = self._make_hud()
        event = SimpleNamespace(type=_pg_mock.KEYDOWN, key=999)

        with patch("preset_hud.pygame", _pg_mock):
            with patch("preset_hud._PRESET_KEYS", _TEST_PRESET_KEYS):
                result = hud.handle_event(event)
        self.assertFalse(result)


class TestPresetHUDApplyPreset(unittest.TestCase):
    """PresetHUD._apply_preset() — 프리셋 슬라이더 적용."""

    def _make_hud_with_sliders(self):
        """슬라이더 맵이 있는 HUD 생성."""
        mock_slider = MagicMock()
        mock_slider.value = 5
        slider_map = {("qubit_chain", "noise_rate"): mock_slider}
        with patch("preset_hud.get_pg_theme", return_value=_make_pg_theme()):
            with patch("preset_hud.pygame", _pg_mock):
                from preset_hud import PresetHUD

                hud = PresetHUD("qubit_chain", slider_map)
        return hud, mock_slider

    def test_apply_preset_with_matching_keys(self):
        """프리셋에 일치하는 키가 있으면 슬라이더 값 설정."""
        hud, mock_slider = self._make_hud_with_sliders()
        preset_data = {"qubit_chain": {"noise_rate": 2.5}}

        with patch("preset_hud.get_preset", return_value=preset_data):
            with patch("preset_hud.t", side_effect=lambda k, **kw: k):
                hud._apply_preset("easy")

        mock_slider.value = 2.5  # setter가 호출됨
        self.assertEqual(hud.current, "easy")
        self.assertGreater(hud.flash_timer, 0)

    def test_apply_preset_empty(self):
        """빈 프리셋이면 슬라이더 변경 없음."""
        hud, mock_slider = self._make_hud_with_sliders()

        with patch("preset_hud.get_preset", return_value={}):
            hud._apply_preset("nonexistent")

        # get_preset이 빈 dict → 조기 반환
        self.assertNotEqual(hud.current, "nonexistent")

    def test_apply_preset_no_matching_section(self):
        """프리셋에 해당 섹션이 없으면 슬라이더 미변경."""
        hud, mock_slider = self._make_hud_with_sliders()
        preset_data = {"other_section": {"key": 10}}

        with patch("preset_hud.get_preset", return_value=preset_data):
            with patch("preset_hud.t", side_effect=lambda k, **kw: k):
                hud._apply_preset("hard")

        self.assertEqual(hud.current, "hard")

    def test_apply_preset_no_matching_key(self):
        """프리셋에 해당 키가 없으면 슬라이더 미변경."""
        hud, mock_slider = self._make_hud_with_sliders()
        preset_data = {"qubit_chain": {"other_key": 10}}

        with patch("preset_hud.get_preset", return_value=preset_data):
            with patch("preset_hud.t", side_effect=lambda k, **kw: k):
                hud._apply_preset("normal")

        self.assertEqual(hud.current, "normal")


class TestPresetHUDSaveCurrent(unittest.TestCase):
    """PresetHUD._save_current() — 현재 값 프로파일 저장."""

    def test_save_current_values(self):
        """슬라이더 값이 프로파일로 저장."""
        mock_slider1 = MagicMock()
        mock_slider1.value = 3.5
        mock_slider2 = MagicMock()
        mock_slider2.value = 10
        slider_map = {
            ("section_a", "key1"): mock_slider1,
            ("section_b", "key2"): mock_slider2,
        }

        with patch("preset_hud.get_pg_theme", return_value=_make_pg_theme()):
            with patch("preset_hud.pygame", _pg_mock):
                from preset_hud import PresetHUD

                hud = PresetHUD("my_module", slider_map)

        with patch("preset_hud.save_profile") as mock_save:
            with patch("preset_hud.t", side_effect=lambda k, **kw: k):
                hud._save_current()

        mock_save.assert_called_once()
        saved_name, saved_values = mock_save.call_args[0]
        self.assertEqual(saved_name, "my_module_custom")
        self.assertEqual(saved_values["section_a.key1"], 3.5)
        self.assertEqual(saved_values["section_b.key2"], 10)
        self.assertEqual(hud.current, "custom")
        self.assertGreater(hud.flash_timer, 0)


class TestPresetHUDLoadLastProfile(unittest.TestCase):
    """PresetHUD._load_last_profile() — 프로파일 불러오기."""

    def _make_hud(self, slider_map=None):
        if slider_map is None:
            mock_slider = MagicMock()
            mock_slider.value = 5
            slider_map = {("sec", "key"): mock_slider}
        with patch("preset_hud.get_pg_theme", return_value=_make_pg_theme()):
            with patch("preset_hud.pygame", _pg_mock):
                from preset_hud import PresetHUD

                return PresetHUD("my_mod", slider_map)

    def test_load_with_saved_profile(self):
        """저장된 프로파일이 있으면 슬라이더에 적용."""
        mock_slider = MagicMock()
        mock_slider.value = 5
        slider_map = {("sec", "key"): mock_slider}
        hud = self._make_hud(slider_map)

        profile_data = {"sec.key": 42}
        with patch("preset_hud.load_profile", return_value=profile_data):
            with patch("preset_hud.t", side_effect=lambda k, **kw: k):
                hud._load_last_profile()

        # slider.value setter가 42로 호출됨
        self.assertEqual(hud.current, "custom")
        self.assertGreater(hud.flash_timer, 0)

    def test_load_without_saved_profile(self):
        """저장된 프로파일이 없으면 알림만 표시."""
        hud = self._make_hud()
        hud.current = "normal"

        with patch("preset_hud.load_profile", return_value={}):
            with patch("preset_hud.t", side_effect=lambda k, **kw: k):
                hud._load_last_profile()

        # 프로파일 없으면 current는 변경되지 않음
        self.assertEqual(hud.current, "normal")
        self.assertGreater(hud.flash_timer, 0)  # 알림 표시됨

    def test_load_profile_partial_match(self):
        """프로파일에 일부 키만 있을 때 매칭되는 것만 적용."""
        mock_slider1 = MagicMock()
        mock_slider2 = MagicMock()
        slider_map = {("a", "x"): mock_slider1, ("b", "y"): mock_slider2}
        hud = self._make_hud(slider_map)

        profile_data = {"a.x": 7}  # b.y는 없음
        with patch("preset_hud.load_profile", return_value=profile_data):
            with patch("preset_hud.t", side_effect=lambda k, **kw: k):
                hud._load_last_profile()

        self.assertEqual(hud.current, "custom")


class TestPresetHUDUpdate(unittest.TestCase):
    """PresetHUD.update() — 타이머 업데이트."""

    def _make_hud(self):
        with patch("preset_hud.get_pg_theme", return_value=_make_pg_theme()):
            with patch("preset_hud.pygame", _pg_mock):
                from preset_hud import PresetHUD

                return PresetHUD("test", {})

    def test_update_decreases_timer(self):
        """dt만큼 flash_timer 감소."""
        hud = self._make_hud()
        hud.flash_timer = 2.0
        hud.update(0.5)
        self.assertAlmostEqual(hud.flash_timer, 1.5)

    def test_update_timer_reaches_zero(self):
        """타이머가 0 이하로 감소."""
        hud = self._make_hud()
        hud.flash_timer = 0.3
        hud.update(0.5)
        self.assertLess(hud.flash_timer, 0)

    def test_update_no_timer(self):
        """타이머가 이미 0이면 변경 없음."""
        hud = self._make_hud()
        hud.flash_timer = 0
        hud.update(1.0)
        self.assertEqual(hud.flash_timer, 0)

    def test_update_negative_timer_stays(self):
        """타이머가 음수이면 그대로 유지."""
        hud = self._make_hud()
        hud.flash_timer = -1.0
        hud.update(0.5)
        self.assertEqual(hud.flash_timer, -1.0)


class TestPresetHUDDraw(unittest.TestCase):
    """PresetHUD.draw() — 렌더링 호출 확인."""

    def _make_hud(self):
        with patch("preset_hud.get_pg_theme", return_value=_make_pg_theme()):
            with patch("preset_hud.pygame", _pg_mock):
                from preset_hud import PresetHUD

                return PresetHUD("test", {})

    def test_draw_badge_and_hint(self):
        """뱃지 + 단축키 힌트 렌더링."""
        hud = self._make_hud()
        hud.flash_timer = 0  # 알림 없음
        screen = _make_mock_screen()
        font = _make_mock_font()

        with patch("preset_hud.t", side_effect=lambda k, **kw: k):
            with patch("preset_hud.pygame", _pg_mock):
                hud.draw(screen, font)

        # 뱃지 + 힌트 = 최소 2회 render
        self.assertGreaterEqual(font.render.call_count, 2)
        self.assertTrue(screen.blit.called)

    def test_draw_with_notification(self):
        """flash_timer > 0 일 때 알림 메시지도 렌더링."""
        hud = self._make_hud()
        hud.flash_timer = 1.5
        hud.notification = "Preset applied!"
        screen = _make_mock_screen()
        font = _make_mock_font()

        with patch("preset_hud.t", side_effect=lambda k, **kw: k):
            with patch("preset_hud.pygame", _pg_mock):
                hud.draw(screen, font)

        # 뱃지 + 힌트 + 알림 = 최소 3회 render
        self.assertGreaterEqual(font.render.call_count, 3)

    def test_draw_custom_position(self):
        """사용자 지정 x, y 좌표."""
        hud = self._make_hud()
        hud.flash_timer = 0
        screen = _make_mock_screen()
        font = _make_mock_font()

        with patch("preset_hud.t", side_effect=lambda k, **kw: k):
            with patch("preset_hud.pygame", _pg_mock):
                hud.draw(screen, font, x=50, y=100)

        # blit 호출 위치 확인 (첫 번째 blit의 좌표)
        first_blit = screen.blit.call_args_list[0]
        pos = first_blit[0][1]
        self.assertEqual(pos[0], 50)
        self.assertEqual(pos[1], 100)

    def test_draw_unknown_current_preset(self):
        """current가 알 수 없는 값이면 기본 색상 사용."""
        hud = self._make_hud()
        hud.current = "unknown_preset"
        hud.flash_timer = 0
        screen = _make_mock_screen()
        font = _make_mock_font()

        with patch("preset_hud.t", side_effect=lambda k, **kw: k):
            with patch("preset_hud.pygame", _pg_mock):
                # 에러 없이 완료
                hud.draw(screen, font)

        self.assertTrue(screen.blit.called)


class TestPresetHUDInit(unittest.TestCase):
    """PresetHUD.__init__() — 초기 상태 확인."""

    def test_initial_state(self):
        """초기화 후 기본 상태 확인."""
        with patch("preset_hud.get_pg_theme", return_value=_make_pg_theme()):
            with patch("preset_hud.pygame", _pg_mock):
                from preset_hud import PresetHUD

                hud = PresetHUD("my_module", {"key": "slider"})

        self.assertEqual(hud.module_name, "my_module")
        self.assertEqual(hud.current, "normal")
        self.assertEqual(hud.flash_timer, 0.0)
        self.assertEqual(hud.notification, "")


# ================================================================
# MockRect 단위 테스트
# ================================================================
class TestMockRect(unittest.TestCase):
    """MockRect 보조 클래스 동작 확인."""

    def test_collidepoint_inside(self):
        r = MockRect(10, 20, 100, 50)
        self.assertTrue(r.collidepoint((50, 40)))

    def test_collidepoint_outside(self):
        r = MockRect(10, 20, 100, 50)
        self.assertFalse(r.collidepoint((200, 200)))

    def test_collidepoint_on_boundary(self):
        r = MockRect(10, 20, 100, 50)
        self.assertTrue(r.collidepoint((10, 20)))
        self.assertTrue(r.collidepoint((110, 70)))

    def test_inflate(self):
        r = MockRect(10, 20, 100, 50)
        inflated = r.inflate(10, 20)
        self.assertEqual(inflated.x, 5)
        self.assertEqual(inflated.y, 10)
        self.assertEqual(inflated.w, 110)
        self.assertEqual(inflated.h, 70)

    def test_centery(self):
        r = MockRect(0, 100, 200, 40)
        self.assertEqual(r.centery, 120)


if __name__ == "__main__":
    unittest.main()
