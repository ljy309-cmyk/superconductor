"""Pygame 슬라이더 위젯 — 실시간 파라미터 조절용.

사용법:
    panel = SliderPanel(x=910, y=50, w=200, title="Parameters")
    s_noise = panel.add(0, 20, 3.0, 0.5, "Noise Rate", ".1f")

    # 이벤트 루프에서:
    panel.handle_event(event)

    # 값 읽기:
    noise = s_noise.value

    # 렌더링:
    panel.draw(screen, font)
"""

import math

import pygame

from theme import get_pg_theme

# 슬라이더 패널 기본 폭 (window 확장용)
PANEL_W = 220


def _colors():
    """현재 테마에서 슬라이더 색상을 가져온다."""
    pg = get_pg_theme()
    return {
        "text": pg.TEXT,
        "green": pg.GREEN,
        "surface": pg.SURFACE,
        "accent": pg.ACCENT_BLUE,
        "subtext": pg.SUBTEXT,
        "panel_bg": pg.PANEL_BG,
    }


class Slider:
    """수평 슬라이더 한 개."""

    BAR_H = 12
    TOTAL_H = 42  # 라벨 + 바 + 여백

    def __init__(self, x: int, y: int, w: int,
                 min_val: float, max_val: float, val: float,
                 step: float, label: str, fmt: str = ".1f"):
        self.x = x
        self.y = y
        self.w = w
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.label = label
        self.fmt = fmt
        self.dragging = False
        self.default_val = val

        self.bar_y = y + 20
        self.bar_rect = pygame.Rect(x, self.bar_y, w, self.BAR_H)

        # 초기값 설정
        self._val = val
        self.value = val  # snap to step

    # ── 값 접근 ──────────────────────────────────────

    @property
    def value(self) -> float:
        return self._val

    @value.setter
    def value(self, v: float):
        v = max(self.min_val, min(self.max_val, v))
        n = round((v - self.min_val) / self.step)
        raw = self.min_val + n * self.step
        # 부동소수점 정밀도 보정
        if self.step >= 1 and self.min_val == int(self.min_val):
            self._val = int(round(raw))
        else:
            dec = max(0, -int(math.floor(math.log10(abs(self.step))))) if self.step > 0 else 2
            self._val = round(raw, dec)

    def reset(self):
        """기본값으로 되돌리기."""
        self.value = self.default_val

    # ── 이벤트 처리 ──────────────────────────────────

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.bar_rect.collidepoint(event.pos):
                self.dragging = True
                self._update_from_mouse(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._update_from_mouse(event.pos[0])

    def _update_from_mouse(self, mx: int):
        ratio = (mx - self.x) / self.w
        ratio = max(0.0, min(1.0, ratio))
        raw = self.min_val + ratio * (self.max_val - self.min_val)
        self.value = raw

    # ── 렌더링 ───────────────────────────────────────

    def draw(self, screen: pygame.Surface, font: pygame.font.Font):
        c = _colors()
        # 라벨 + 현재 값
        val_str = f"{self._val:{self.fmt}}"
        label_surf = font.render(f"{self.label}", True, c["text"])
        val_surf = font.render(val_str, True, c["green"])
        screen.blit(label_surf, (self.x, self.y))
        screen.blit(val_surf, (self.x + self.w - val_surf.get_width(), self.y))

        # 바 배경
        pygame.draw.rect(screen, c["surface"], self.bar_rect, border_radius=4)

        # 채움
        ratio = self._ratio()
        fill_w = int(self.w * ratio)
        if fill_w > 0:
            fill_rect = pygame.Rect(self.x, self.bar_y, fill_w, self.BAR_H)
            pygame.draw.rect(screen, c["accent"], fill_rect, border_radius=4)

        # 핸들 (원형)
        handle_x = self.x + fill_w
        handle_y = self.bar_y + self.BAR_H // 2
        pygame.draw.circle(screen, c["text"], (handle_x, handle_y), 7)
        pygame.draw.circle(screen, c["subtext"], (handle_x, handle_y), 7, 1)

        # 바 테두리
        pygame.draw.rect(screen, c["subtext"], self.bar_rect, 1, border_radius=4)

    def _ratio(self) -> float:
        if self.max_val <= self.min_val:
            return 0.0
        return (self._val - self.min_val) / (self.max_val - self.min_val)


class SliderPanel:
    """슬라이더 여러 개를 묶는 패널."""

    def __init__(self, x: int, y: int, w: int, title: str = "Parameters"):
        self.x = x
        self.y = y
        self.w = w
        self.title = title
        self.sliders: list[Slider] = []

    def add(self, min_val: float, max_val: float, val: float,
            step: float, label: str, fmt: str = ".1f") -> Slider:
        """슬라이더 추가. 반환된 Slider 객체의 .value로 현재 값을 읽는다."""
        sy = self.y + 28 + len(self.sliders) * Slider.TOTAL_H
        s = Slider(self.x + 10, sy, self.w - 20, min_val, max_val, val, step, label, fmt)
        self.sliders.append(s)
        return s

    def handle_event(self, event: pygame.event.Event):
        for s in self.sliders:
            s.handle_event(event)

    def reset_all(self):
        """모든 슬라이더를 기본값으로 되돌리기."""
        for s in self.sliders:
            s.reset()

    def panel_height(self) -> int:
        return 28 + len(self.sliders) * Slider.TOTAL_H + 10

    def draw(self, screen: pygame.Surface, font: pygame.font.Font,
             title_font: pygame.font.Font | None = None):
        h = self.panel_height()
        panel_rect = pygame.Rect(self.x, self.y, self.w, h)

        c = _colors()
        # 배경
        pygame.draw.rect(screen, c["panel_bg"], panel_rect, border_radius=6)
        pygame.draw.rect(screen, c["subtext"], panel_rect, 1, border_radius=6)

        # 타이틀
        tf = title_font or font
        title_surf = tf.render(self.title, True, c["accent"])
        screen.blit(title_surf, (self.x + self.w // 2 - title_surf.get_width() // 2, self.y + 6))

        # 슬라이더들
        for s in self.sliders:
            s.draw(screen, font)
