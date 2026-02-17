"""게임 종료 요약 오버레이 — 모든 Pygame 모듈에서 사용 가능."""

import pygame
from theme import get_pg_theme
from i18n import t


def draw_game_summary(screen, title: str, stats: list[tuple[str, str]],
                      font=None, title_font=None):
    """게임 종료 시 반투명 오버레이에 요약 통계 표시.

    Args:
        screen: Pygame surface
        title: 제목 문자열 (e.g., t("qc_game_over_msg", ...))
        stats: [(라벨, 값), ...] 형태의 통계 목록
        font: 본문 폰트 (없으면 기본 생성)
        title_font: 제목 폰트 (없으면 기본 생성)
    """
    pg = get_pg_theme()
    W, H = screen.get_size()

    # 반투명 오버레이
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((*pg.BG, 210))
    screen.blit(overlay, (0, 0))

    if font is None:
        font = pygame.font.SysFont("Consolas", 13)
    if title_font is None:
        title_font = pygame.font.SysFont("Consolas", 20, bold=True)

    # 패널 크기 계산
    line_h = 22
    pad = 20
    panel_h = 60 + len(stats) * line_h + 40 + pad * 2
    panel_w = 360
    px = W // 2 - panel_w // 2
    py = H // 2 - panel_h // 2

    # 패널 배경
    panel_rect = pygame.Rect(px, py, panel_w, panel_h)
    pygame.draw.rect(screen, pg.PANEL_BG, panel_rect, border_radius=8)
    pygame.draw.rect(screen, pg.OVERLAY, panel_rect, 2, border_radius=8)

    # 제목
    title_surf = title_font.render(title, True, pg.RED)
    screen.blit(title_surf, (W // 2 - title_surf.get_width() // 2, py + pad))

    # 구분선
    line_y = py + pad + 36
    pygame.draw.line(screen, pg.OVERLAY,
                     (px + pad, line_y), (px + panel_w - pad, line_y))

    # 통계 행
    y = line_y + 12
    for label, value in stats:
        label_surf = font.render(label, True, pg.SUBTEXT)
        value_surf = font.render(str(value), True, pg.TEXT)
        screen.blit(label_surf, (px + pad + 8, y))
        screen.blit(value_surf, (px + panel_w - pad - 8 - value_surf.get_width(), y))
        y += line_h

    # 하단 힌트
    y += 8
    hint = t("summary_hint")
    hint_surf = font.render(hint, True, pg.SUBTEXT)
    screen.blit(hint_surf, (W // 2 - hint_surf.get_width() // 2, y))
