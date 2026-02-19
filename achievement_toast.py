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

from theme import get_pg_theme


class AchievementToast:
    """업적 해금 토스트 알림 (슬라이드 인/아웃 애니메이션)."""

    DISPLAY_TIME = 3.0  # 표시 시간 (초)
    SLIDE_TIME = 0.3  # 슬라이드 애니메이션 (초)
    TOAST_W = 320
    TOAST_H = 60
    HISTORY_MAX = 20  # 히스토리 최대 보관 수

    def __init__(self):
        self._queue: list[dict] = []
        self._current: dict | None = None
        self._timer = 0.0
        self._phase = "idle"  # idle | slide_in | show | slide_out
        self._history: list[dict] = []
        self.history_visible = False

    def show(self, achievement: dict):
        """업적을 토스트 큐에 추가."""
        self._queue.append(achievement)
        self._history.append(achievement)
        if len(self._history) > self.HISTORY_MAX:
            self._history.pop(0)
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
        pygame.draw.rect(surf, (30, 30, 46, 230), (0, 0, self.TOAST_W, self.TOAST_H), border_radius=8)
        pygame.draw.rect(surf, (249, 226, 175, 200), (0, 0, self.TOAST_W, self.TOAST_H), 2, border_radius=8)

        # 아이콘
        icon = self._current.get("icon", "?")
        icon_surf = font.render(f"[{icon}]", True, (249, 226, 175))
        surf.blit(icon_surf, (10, 8))

        # 타이틀
        title = self._current.get("title", "Achievement!")
        title_surf = font.render(f"Achievement: {title}", True, get_pg_theme().GREEN)
        surf.blit(title_surf, (10 + icon_surf.get_width() + 6, 8))

        # 설명
        desc = self._current.get("desc", "")
        if len(desc) > 40:
            desc = desc[:38] + ".."
        desc_surf = font.render(desc, True, (205, 214, 244))
        surf.blit(desc_surf, (10, 32))

        screen.blit(surf, (x, y))

    def toggle_history(self):
        """히스토리 패널 토글."""
        self.history_visible = not self.history_visible

    def draw_history(self, screen, font):
        """업적 히스토리 패널 렌더링."""
        if not self.history_visible or pygame is None:
            return

        pg = get_pg_theme()

        # 전체 업적 목록 조회
        try:
            from achievements import get_all_achievements

            all_ach = get_all_achievements()
        except ImportError:
            all_ach = []

        if not all_ach:
            return

        sw, sh = screen.get_size()
        panel_w = 340
        line_h = 22
        panel_h = min(40 + len(all_ach) * line_h, sh - 40)
        px = sw - panel_w - 10
        py = 10

        # 반투명 배경
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (*pg.PANEL_BG, 230), (0, 0, panel_w, panel_h), border_radius=8)
        pygame.draw.rect(panel_surf, pg.OVERLAY, (0, 0, panel_w, panel_h), 2, border_radius=8)

        # 타이틀
        title_surf = font.render("Achievements (Tab to close)", True, pg.ACCENT_YELLOW)
        panel_surf.blit(title_surf, (10, 8))

        # 업적 목록
        y = 32
        for ach in all_ach:
            if y + line_h > panel_h:
                break
            icon = ach.get("icon", "?")
            title = ach.get("title", "")
            unlocked = ach.get("unlocked", False)
            clr = pg.GREEN if unlocked else pg.SUBTEXT
            prefix = "[V]" if unlocked else "[ ]"
            text = f"{prefix} [{icon}] {title}"
            text_surf = font.render(text, True, clr)
            panel_surf.blit(text_surf, (10, y))
            y += line_h

        screen.blit(panel_surf, (px, py))
