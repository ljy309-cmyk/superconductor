"""종료 확인 대화상자 — Pygame 모듈 공통."""

import pygame

from i18n import t
from theme import get_pg_theme


def confirm_quit(screen, font=None) -> bool:
    """반투명 오버레이에 종료 확인 대화상자를 표시.

    Y/Enter → True(종료), N/ESC → False(계속).
    """
    pg = get_pg_theme()
    W, H = screen.get_size()

    if font is None:
        font = pygame.font.SysFont("Consolas", 14)
    bold_font = pygame.font.SysFont("Consolas", 16, bold=True)

    # 반투명 오버레이
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((*pg.BG, 180))
    screen.blit(overlay, (0, 0))

    # 패널
    panel_w, panel_h = 320, 100
    px = W // 2 - panel_w // 2
    py = H // 2 - panel_h // 2
    panel_rect = pygame.Rect(px, py, panel_w, panel_h)
    pygame.draw.rect(screen, pg.PANEL_BG, panel_rect, border_radius=8)
    pygame.draw.rect(screen, pg.OVERLAY, panel_rect, 2, border_radius=8)

    # 질문 텍스트
    q_surf = bold_font.render(t("quit_confirm"), True, pg.TEXT)
    screen.blit(q_surf, (W // 2 - q_surf.get_width() // 2, py + 20))

    # 힌트
    h_surf = font.render(t("quit_hint"), True, pg.SUBTEXT)
    screen.blit(h_surf, (W // 2 - h_surf.get_width() // 2, py + 55))

    pygame.display.flip()

    # 입력 대기 루프
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_y, pygame.K_RETURN):
                    return True
                if event.key in (pygame.K_n, pygame.K_ESCAPE):
                    return False
