"""인게임 업적 토스트 알림 — Pygame 게임 내 업적 해금 시 팝업.

사용법:
    from achievement_toast import AchievementToast
    toast = AchievementToast()

    # 업적 해금 시:
    toast.show(achievement_dict)

    # 매 프레임:
    toast.update(dt)
    toast.draw(screen, font)
"""

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore[assignment]


class AchievementToast:
    """업적 해금 토스트 알림 (슬라이드 인/아웃 애니메이션)."""

    DISPLAY_TIME = 3.0      # 표시 시간 (초)
    SLIDE_TIME = 0.3        # 슬라이드 애니메이션 (초)
    TOAST_W = 320
    TOAST_H = 60

    def __init__(self):
        self._queue: list[dict] = []
        self._current: dict | None = None
        self._timer = 0.0
        self._phase = "idle"  # idle | slide_in | show | slide_out

    def show(self, achievement: dict):
        """업적을 토스트 큐에 추가."""
        self._queue.append(achievement)
        if self._phase == "idle":
            self._next()

    def show_many(self, achievements: list[dict]):
        """여러 업적을 큐에 추가."""
        for ach in achievements:
            self.show(ach)

    def _next(self):
        """큐에서 다음 업적 표시."""
        if self._queue:
            self._current = self._queue.pop(0)
            self._phase = "slide_in"
            self._timer = 0.0
        else:
            self._current = None
            self._phase = "idle"

    def update(self, dt: float):
        """매 프레임 호출."""
        if self._phase == "idle":
            return

        self._timer += dt

        if self._phase == "slide_in" and self._timer >= self.SLIDE_TIME:
            self._phase = "show"
            self._timer = 0.0
        elif self._phase == "show" and self._timer >= self.DISPLAY_TIME:
            self._phase = "slide_out"
            self._timer = 0.0
        elif self._phase == "slide_out" and self._timer >= self.SLIDE_TIME:
            self._next()

    def draw(self, screen, font):
        """토스트 렌더링."""
        if self._current is None or pygame is None:
            return

        sw = screen.get_width()

        # 슬라이드 오프셋 계산
        if self._phase == "slide_in":
            progress = min(self._timer / self.SLIDE_TIME, 1.0)
            offset_y = -self.TOAST_H + self.TOAST_H * progress
        elif self._phase == "slide_out":
            progress = min(self._timer / self.SLIDE_TIME, 1.0)
            offset_y = -self.TOAST_H * progress
        else:
            offset_y = 0

        x = sw - self.TOAST_W - 16
        y = int(10 + offset_y)

        # 배경
        surf = pygame.Surface((self.TOAST_W, self.TOAST_H), pygame.SRCALPHA)
        pygame.draw.rect(surf, (30, 30, 46, 230), (0, 0, self.TOAST_W, self.TOAST_H),
                         border_radius=8)
        pygame.draw.rect(surf, (249, 226, 175, 200), (0, 0, self.TOAST_W, self.TOAST_H),
                         2, border_radius=8)

        # 아이콘
        icon = self._current.get("icon", "?")
        icon_surf = font.render(f"[{icon}]", True, (249, 226, 175))
        surf.blit(icon_surf, (10, 8))

        # 타이틀
        title = self._current.get("title", "Achievement!")
        title_surf = font.render(f"Achievement: {title}", True, (166, 227, 161))
        surf.blit(title_surf, (10 + icon_surf.get_width() + 6, 8))

        # 설명
        desc = self._current.get("desc", "")
        if len(desc) > 40:
            desc = desc[:38] + ".."
        desc_surf = font.render(desc, True, (205, 214, 244))
        surf.blit(desc_surf, (10, 32))

        screen.blit(surf, (x, y))
