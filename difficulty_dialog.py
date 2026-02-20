"""시작 시 난이도 선택 대화상자 — Pygame 모듈 공통.

시뮬레이션 시작 전에 Easy / Normal / Hard를 선택하는 UI를 표시합니다.
quit_dialog.py와 같은 패턴으로, 각 모듈의 run_simulation()에서 호출합니다.

사용법::

    from difficulty_dialog import choose_difficulty
    chosen = choose_difficulty(screen)       # "easy" | "normal" | "hard" | None
    if chosen is None:                       # ESC → 시뮬레이션 취소
        return
    preset_hud.apply(chosen)
"""

import pygame

from font_helper import get_font
from i18n import t
from theme import get_pg_theme

# 선택지 정의
_DIFFICULTIES = [
    ("easy", "1"),
    ("normal", "2"),
    ("hard", "3"),
]


def choose_difficulty(screen: pygame.Surface, font: pygame.font.Font | None = None) -> str | None:
    """난이도 선택 대화상자를 표시하고 결과를 반환.

    Returns:
        "easy", "normal", "hard" — 또는 ESC/창 닫기 시 None.
    """
    pg = get_pg_theme()
    W, H = screen.get_size()

    if font is None:
        font = get_font(14)
    title_font = get_font(18, bold=True)
    key_font = get_font(14, bold=True)

    # 색상 매핑
    diff_colors = {
        "easy": pg.GREEN,
        "normal": pg.YELLOW,
        "hard": pg.RED,
    }

    selected = 1  # 기본 선택: normal (인덱스 1)

    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key == pygame.K_1:
                    return "easy"
                if event.key == pygame.K_2:
                    return "normal"
                if event.key == pygame.K_3:
                    return "hard"
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(_DIFFICULTIES)
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(_DIFFICULTIES)
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return _DIFFICULTIES[selected][0]
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                for i, (name, _key) in enumerate(_DIFFICULTIES):
                    btn_rect = _btn_rect(W, H, i)
                    if btn_rect.collidepoint(mx, my):
                        return name
            if event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                for i in range(len(_DIFFICULTIES)):
                    if _btn_rect(W, H, i).collidepoint(mx, my):
                        selected = i

        # ── 렌더링 ──
        # 반투명 오버레이
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((*pg.BG, 200))
        screen.blit(overlay, (0, 0))

        # 패널
        panel_w, panel_h = 340, 220
        px = W // 2 - panel_w // 2
        py = H // 2 - panel_h // 2
        panel_rect = pygame.Rect(px, py, panel_w, panel_h)
        pygame.draw.rect(screen, pg.PANEL_BG, panel_rect, border_radius=10)
        pygame.draw.rect(screen, pg.OVERLAY, panel_rect, 2, border_radius=10)

        # 타이틀
        title_surf = title_font.render(t("difficulty_title"), True, pg.TEXT)
        screen.blit(title_surf, (W // 2 - title_surf.get_width() // 2, py + 16))

        # 버튼들
        for i, (name, shortcut) in enumerate(_DIFFICULTIES):
            btn_rect = _btn_rect(W, H, i)
            color = diff_colors.get(name, pg.TEXT)
            is_selected = i == selected

            # 버튼 배경
            bg_color = (*color[:3], 40) if not is_selected else (*color[:3], 80)
            btn_surf = pygame.Surface((btn_rect.width, btn_rect.height), pygame.SRCALPHA)
            btn_surf.fill(bg_color)
            screen.blit(btn_surf, btn_rect.topleft)

            # 버튼 테두리
            border_width = 2 if is_selected else 1
            pygame.draw.rect(screen, color, btn_rect, border_width, border_radius=6)

            # 선택 화살표
            if is_selected:
                arrow = key_font.render(">", True, color)
                screen.blit(arrow, (btn_rect.x - 16, btn_rect.centery - arrow.get_height() // 2))

            # 라벨
            label = t(f"preset_{name}")
            label_surf = font.render(f"[{shortcut}]  {label}", True, color)
            screen.blit(label_surf, (btn_rect.x + 12, btn_rect.centery - label_surf.get_height() // 2))

        # 하단 힌트
        hint_surf = font.render(t("difficulty_hint"), True, pg.SUBTEXT)
        screen.blit(hint_surf, (W // 2 - hint_surf.get_width() // 2, py + panel_h - 30))

        pygame.display.flip()
        clock.tick(30)


def _btn_rect(screen_w: int, screen_h: int, index: int) -> pygame.Rect:
    """버튼 위치 계산."""
    panel_w = 340
    btn_w, btn_h = 260, 36
    screen_w // 2 - panel_w // 2
    py = screen_h // 2 - 220 // 2
    bx = screen_w // 2 - btn_w // 2
    by = py + 54 + index * (btn_h + 8)
    return pygame.Rect(bx, by, btn_w, btn_h)
