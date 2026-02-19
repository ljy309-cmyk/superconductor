"""quantum UI 공통 유틸리티.

모든 양자 시뮬레이션 모듈에서 공유하는 그리기·페이지네이션·알림 헬퍼.
"""

import pygame

# ── 페이지네이션 ─────────────────────────────────────

HISTORY_PAGE_SIZE = 4


def paginate(items, page, page_size=HISTORY_PAGE_SIZE):
    """리스트를 페이지네이션하여 *(page_items, clamped_page, total_pages)* 반환."""
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    end = min(start + page_size, total)
    return items[start:end], page, total_pages


# ── 색맹 보조 막대 패턴 ──────────────────────────────


def draw_bar_pattern(screen, rect, clr, tier):
    """막대에 패턴을 그려 색상 외에도 시각적으로 구분 (색맹 보조).

    tier: "high" → 수평선, "mid" → 대각선, "low" → 패턴 없음
    """
    bx, by, bw, bh = rect
    if bh < 4 or bw < 2:
        return
    pc = tuple(min(255, c + 60) for c in clr[:3])
    if tier == "high":
        for ly in range(by + 2, by + bh - 1, 4):
            pygame.draw.line(screen, pc, (bx, ly), (bx + bw - 1, ly))
    elif tier == "mid":
        for offset in range(-bh, bw, 5):
            x1 = max(0, offset)
            y1 = max(0, -offset)
            diag_len = min(bw - 1 - x1, bh - 1 - y1)
            if diag_len > 0:
                pygame.draw.line(screen, pc,
                                 (bx + x1, by + y1),
                                 (bx + x1 + diag_len, by + y1 + diag_len))


# ── 알림 렌더링 ──────────────────────────────────────


def render_notify(screen, msg, timer, font, color, center_x, y):
    """페이드 아웃 알림 메시지 렌더링 (timer > 0 일 때 호출)."""
    alpha = min(255, int(255 * min(1.0, timer / 0.3)))
    ns = font.render(msg, True, color)
    ns.set_alpha(alpha)
    screen.blit(ns, (center_x - ns.get_width() // 2, y))


# ── 패널 그리기 ──────────────────────────────────────


def draw_panel(screen, x, y, w, h, bg_clr, border_clr,
               title="", title_font=None, accent_clr=None):
    """둥근 패널."""
    pygame.draw.rect(screen, bg_clr, (x, y, w, h), border_radius=6)
    pygame.draw.rect(screen, border_clr, (x, y, w, h), 1, border_radius=6)
    if title and title_font and accent_clr:
        ts = title_font.render(title, True, accent_clr)
        screen.blit(ts, (x + 10, y + 6))


# ── 진행률 바 ────────────────────────────────────────


def draw_progress_bar(screen, x, y, w, h, progress, color, bg_clr, border_clr):
    """진행률 바 (0.0 ~ 1.0)."""
    pygame.draw.rect(screen, bg_clr, (x, y, w, h), border_radius=3)
    fill_w = max(0, int(w * min(1.0, progress)))
    if fill_w > 0:
        pygame.draw.rect(screen, color, (x, y, fill_w, h), border_radius=3)
    pygame.draw.rect(screen, border_clr, (x, y, w, h), 1, border_radius=3)


# ── 텍스트 줄바꿈 ────────────────────────────────────


def wrap_text(text, max_chars):
    """텍스트를 max_chars 기준으로 줄바꿈."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > max_chars:
            if current:
                lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(current)
    return lines
