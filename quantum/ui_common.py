"""quantum UI 공통 유틸리티.

모든 양자 시뮬레이션 모듈에서 공유하는 그리기·페이지네이션·알림 헬퍼.
"""

from __future__ import annotations

import pygame

from theme import get_pg_theme, is_high_contrast, is_reduced_motion

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


# ── 페이지 도트 인디케이터 ────────────────────────────


MAX_PAGE_DOTS = 9


def draw_page_dots(screen, x, cy, total_pages, current_page,
                   active_clr, inactive_clr, border_clr):
    """페이지 도트 인디케이터.

    페이지 수가 MAX_PAGE_DOTS를 초과하면 현재 페이지 주변만 표시하고
    양쪽 끝을 작은 도트(...)로 축약합니다.

    Args:
        screen: Pygame 화면.
        x: 첫 도트 시작 X 좌표.
        cy: 도트 중심 Y 좌표.
        total_pages: 전체 페이지 수.
        current_page: 현재 페이지 인덱스 (0-based).
        active_clr: 현재 페이지 도트 색상.
        inactive_clr: 비활성 도트 채움 색상.
        border_clr: 비활성 도트 테두리 색상.
    """
    if total_pages <= 1:
        return
    hc = is_high_contrast()
    dot_r = 4 if hc else 3
    small_r = max(1, dot_r - 1)
    gap = dot_r * 2 + 5

    # 페이지 수가 적으면 전부 표시
    if total_pages <= MAX_PAGE_DOTS:
        for i in range(total_pages):
            cx = x + i * gap + dot_r
            if i == current_page:
                pygame.draw.circle(screen, active_clr, (cx, cy), dot_r)
            else:
                pygame.draw.circle(screen, inactive_clr, (cx, cy), small_r)
                pygame.draw.circle(screen, border_clr, (cx, cy), small_r, 1)
        return

    # 많은 페이지: [첫] ... [현재 주변] ... [끝] 축약
    # 항상 정확히 MAX_PAGE_DOTS 슬롯을 유지하여 너비 점프 방지.
    window = MAX_PAGE_DOTS - 4  # 양쪽 끝점(2) + 줄임표(2) = 4 제외
    half = window // 2

    # 윈도우 범위 계산
    win_start = current_page - half
    win_end = current_page + half

    # 경계 클램프
    if win_start <= 1:
        win_start = 1
        win_end = win_start + window - 1
    if win_end >= total_pages - 2:
        win_end = total_pages - 2
        win_start = win_end - window + 1

    show_left_ellipsis = win_start > 1
    show_right_ellipsis = win_end < total_pages - 2

    # 줄임표가 생략된 쪽으로 윈도우를 1칸 확장하여 슬롯 수 보전
    if not show_left_ellipsis and show_right_ellipsis:
        win_end += 1
    elif show_left_ellipsis and not show_right_ellipsis:
        win_start -= 1

    # 표시할 인덱스 목록 구축
    slots: list[tuple[str, int]] = []  # ("dot"|"ellipsis", page_index)
    slots.append(("dot", 0))
    if show_left_ellipsis:
        slots.append(("ellipsis", -1))
    for i in range(win_start, win_end + 1):
        slots.append(("dot", i))
    if show_right_ellipsis:
        slots.append(("ellipsis", -1))
    slots.append(("dot", total_pages - 1))

    # 렌더링
    for si, (kind, page_idx) in enumerate(slots):
        cx = x + si * gap + dot_r
        if kind == "ellipsis":
            # 작은 도트 3개로 줄임표 표현
            for dx in (-3, 0, 3):
                pygame.draw.circle(screen, border_clr, (cx + dx, cy), 1)
        elif page_idx == current_page:
            pygame.draw.circle(screen, active_clr, (cx, cy), dot_r)
        else:
            pygame.draw.circle(screen, inactive_clr, (cx, cy), small_r)
            pygame.draw.circle(screen, border_clr, (cx, cy), small_r, 1)


def page_dots_width(total_pages):
    """도트 인디케이터의 렌더링 픽셀 너비를 반환.

    draw_page_dots가 실제로 그리는 슬롯 수 기반으로 계산하므로
    overflow 모드에서도 정확한 너비를 반환합니다.
    """
    if total_pages <= 1:
        return 0
    hc = is_high_contrast()
    dot_r = 4 if hc else 3
    gap = dot_r * 2 + 5
    n = min(total_pages, MAX_PAGE_DOTS)
    return (n - 1) * gap + 2 * dot_r


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


# ── 색맹 보조 원형 패턴 ──────────────────────────────


def draw_circle_pattern(screen, cx, cy, radius, clr, tier):
    """원 내부에 패턴을 그려 색상 외에도 시각적으로 구분 (색맹 보조).

    tier: "high" → 수평선, "mid" → 대각선, "low" → 패턴 없음
    패턴은 원형 클리핑 마스크 내에서만 렌더링됩니다.
    """
    if radius < 4 or tier == "low":
        return
    pc = tuple(min(255, c + 60) for c in clr[:3])
    if tier == "high":
        for ly in range(cy - radius + 2, cy + radius - 1, 4):
            # 원과 수평선의 교차점 계산
            dy = ly - cy
            half_w_sq = radius * radius - dy * dy
            if half_w_sq <= 0:
                continue
            half_w = int(half_w_sq ** 0.5)
            pygame.draw.line(screen, pc, (cx - half_w, ly), (cx + half_w, ly))
    elif tier == "mid":
        for offset in range(-radius * 2, radius * 2, 5):
            # 대각선 (좌상→우하) 과 원의 교차 구간
            # 대각선: y - cy = (x - cx) + offset  →  dy = dx + offset
            # 원: dx² + dy² <= r²  →  dx² + (dx+offset)² <= r²
            # 2dx² + 2*offset*dx + offset² - r² <= 0
            a = 2
            b = 2 * offset
            c_val = offset * offset - radius * radius
            det = b * b - 4 * a * c_val
            if det < 0:
                continue
            sqrt_det = det ** 0.5
            dx0 = (-b - sqrt_det) / (2 * a)
            dx1 = (-b + sqrt_det) / (2 * a)
            x0 = cx + int(dx0)
            y0 = cy + int(dx0 + offset)
            x1 = cx + int(dx1)
            y1 = cy + int(dx1 + offset)
            pygame.draw.line(screen, pc, (x0, y0), (x1, y1))


# ── 알림 렌더링 ──────────────────────────────────────


def render_notify(screen, msg, timer, font, color, center_x, y):
    """페이드 아웃 알림 메시지 렌더링 (timer > 0 일 때 호출)."""
    ns = font.render(msg, True, color)
    if not is_reduced_motion():
        alpha = min(255, int(255 * min(1.0, timer / 0.3)))
        ns.set_alpha(alpha)
    screen.blit(ns, (center_x - ns.get_width() // 2, y))


# ── 카테고리 토스트 알림 ──────────────────────────────

# 유효한 카테고리 목록
NOTIFY_CATEGORIES = ("success", "warning", "info", "error")

_CATEGORY_ICONS = {
    "success": "+",
    "warning": "!",
    "info": "i",
    "error": "x",
}


class NotifyToast:
    """카테고리별 큐 기반 토스트 알림.

    카테고리:
        success — 터널링, 완료 등 긍정적 이벤트 (초록)
        warning — 반사, 주의 등 경고 이벤트 (노랑)
        info    — 모드 변경, 리셋 등 정보성 알림 (파랑)
        error   — 오류 상태 (빨강)

    사용법::

        toast = NotifyToast()
        toast.show("터널링!", "success")

        # 매 프레임:
        toast.update(dt)
        toast.draw(screen, font, center_x, base_y)
    """

    DISPLAY_TIME = 2.0
    SLIDE_TIME = 0.15
    TOAST_H = 28
    MAX_VISIBLE = 3
    GAP = 4
    PAD_X = 12

    def __init__(self):
        self._active: list[dict] = []
        self._queue: list[dict] = []

    # ── public API ─────────────────────────────────────

    def show(self, msg: str, category: str = "info", duration: float = 2.0):
        """알림을 큐에 추가.

        Args:
            msg: 표시할 메시지.
            category: "success" | "warning" | "info" | "error".
            duration: 표시 시간 (초).
        """
        entry = {
            "msg": msg,
            "cat": category if category in NOTIFY_CATEGORIES else "info",
            "dur": duration,
            "timer": 0.0,
            "phase": "in",  # in → show → out → (제거)
        }
        if len(self._active) < self.MAX_VISIBLE:
            self._active.append(entry)
        else:
            self._queue.append(entry)

    def update(self, dt: float):
        """매 프레임 호출 — 타이머 진행 및 위상 전환."""
        rm: list[int] = []
        for i, t in enumerate(self._active):
            t["timer"] += dt
            if t["phase"] == "in" and t["timer"] >= self.SLIDE_TIME:
                t["phase"] = "show"
                t["timer"] = 0.0
            elif t["phase"] == "show" and t["timer"] >= t["dur"]:
                t["phase"] = "out"
                t["timer"] = 0.0
            elif t["phase"] == "out" and t["timer"] >= self.SLIDE_TIME:
                rm.append(i)
        for i in reversed(rm):
            self._active.pop(i)
            if self._queue:
                self._active.append(self._queue.pop(0))

    @property
    def active_count(self) -> int:
        """현재 표시 중인 토스트 수."""
        return len(self._active)

    @property
    def queue_count(self) -> int:
        """대기열에 있는 토스트 수."""
        return len(self._queue)

    def clear(self):
        """모든 토스트 즉시 제거."""
        self._active.clear()
        self._queue.clear()

    # ── rendering ──────────────────────────────────────

    def draw(self, screen, font, center_x: int, base_y: int):
        """토스트 렌더링 — 하단에서 위로 쌓임.

        Args:
            screen: Pygame 화면.
            font: 렌더링용 폰트.
            center_x: 토스트 수평 중심 X.
            base_y: 가장 아래 토스트의 하단 Y.
        """
        if not self._active:
            return
        pg = get_pg_theme()
        reduced = is_reduced_motion()
        hc = is_high_contrast()

        clr_map = {
            "success": pg.GREEN,
            "warning": pg.ACCENT_YELLOW,
            "info": pg.ACCENT_BLUE,
            "error": pg.RED,
        }

        for idx, toast in enumerate(self._active):
            cat = toast["cat"]
            accent = clr_map.get(cat, pg.TEXT)
            icon = _CATEGORY_ICONS.get(cat, "")
            text = f"[{icon}] {toast['msg']}"

            ts = font.render(text, True, pg.TEXT)
            tw = ts.get_width() + self.PAD_X * 2
            th = max(self.TOAST_H, ts.get_height() + self.PAD_X)

            x = center_x - tw // 2
            y = base_y - (idx + 1) * (th + self.GAP)

            # 슬라이드 + 페이드 애니메이션
            alpha = 255
            if not reduced:
                if toast["phase"] == "in":
                    p = min(toast["timer"] / self.SLIDE_TIME, 1.0)
                    alpha = int(255 * p)
                    y += int(th * 0.5 * (1 - p))
                elif toast["phase"] == "out":
                    p = min(toast["timer"] / self.SLIDE_TIME, 1.0)
                    alpha = int(255 * (1 - p))

            surf = pygame.Surface((tw, th), pygame.SRCALPHA)
            # 배경
            pygame.draw.rect(
                surf, (*pg.PANEL_BG[:3], min(alpha, 210)),
                (0, 0, tw, th), border_radius=5)
            # 테두리
            bw = 2 if hc else 1
            pygame.draw.rect(
                surf, (*accent[:3], alpha),
                (0, 0, tw, th), bw, border_radius=5)
            # 왼쪽 카테고리 색상 스트라이프
            pygame.draw.rect(
                surf, (*accent[:3], alpha),
                (0, 4, 3, th - 8), border_radius=1)

            if alpha < 255:
                ts.set_alpha(alpha)
            surf.blit(ts, (self.PAD_X, (th - ts.get_height()) // 2))

            screen.blit(surf, (x, y))


# ── 패널 그리기 ──────────────────────────────────────


def draw_panel(screen, x, y, w, h, bg_clr, border_clr,
               title="", title_font=None, accent_clr=None):
    """둥근 패널."""
    hc = is_high_contrast()
    pygame.draw.rect(screen, bg_clr, (x, y, w, h), border_radius=6)
    border_w = 2 if hc else 1
    pygame.draw.rect(screen, border_clr, (x, y, w, h), border_w, border_radius=6)
    if title and title_font and accent_clr:
        ts = title_font.render(title, True, accent_clr)
        screen.blit(ts, (x + 10, y + 6))


# ── 진행률 바 ────────────────────────────────────────


def draw_progress_bar(screen, x, y, w, h, progress, color, bg_clr, border_clr):
    """진행률 바 (0.0 ~ 1.0)."""
    hc = is_high_contrast()
    pygame.draw.rect(screen, bg_clr, (x, y, w, h), border_radius=3)
    fill_w = max(0, int(w * min(1.0, progress)))
    if fill_w > 0:
        pygame.draw.rect(screen, color, (x, y, fill_w, h), border_radius=3)
    border_w = 2 if hc else 1
    pygame.draw.rect(screen, border_clr, (x, y, w, h), border_w, border_radius=3)


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
