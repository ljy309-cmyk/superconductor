"""터널링 시뮬레이션 렌더링 — 모든 _draw_* 함수, 캐시 클래스, 색상/레이아웃 상수.

``quantum.tunneling`` 에서 분리된 렌더링 전용 모듈.
"""

import math
import time
from collections import defaultdict

import pygame

from config_loader import cfg
from font_helper import get_font
from i18n import t
from quantum.tunneling_experiment import (
    compute_fit_stats,
    generate_theory_curve,
    get_dataset_ids,
    get_experiment_data,
    get_experiment_datasets,
)
from quantum.tunneling_physics import (
    _REFLECT_FLASH,
    _TUNNEL_DECAY,
    _TUNNEL_FLASH,
    BARRIER_WIDTH_DEFAULT,
    BARRIER_WIDTH_MAX,
    BARRIER_WIDTH_MIN,
    BARRIER_X,
    PARTICLE_RADIUS,
    SIM_H,
    SIM_LEFT,
    SIM_TOP,
    SIM_W,
    TUNNEL_PROB_BASE,
    BarrierSweeper,
    QuantumParticle,
    calc_energy_levels,
    compute_psi,
)
from sim_speed import speed_label
from theme import load_pg_colors
from ui.slider import PANEL_W

# ── 화면 설정 ────────────────────────────────────────
WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
FPS = cfg("display", "fps", 60)

# ── 색상 (테마에서 동적 로드) ─────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (203, 166, 247)
BARRIER_CLR = (249, 226, 175)
PARTICLE_CLR = (137, 180, 250)
TUNNEL_FLASH = (166, 227, 161)  # 터널링 성공
REFLECT_CLR = (243, 139, 168)  # 반사
BLOCH_RING = (88, 91, 112)


_COLOR_MAP = {
    "BG": "BG",
    "TEXT_CLR": "TEXT",
    "ACCENT": "ACCENT_PURPLE",
    "BARRIER_CLR": "ACCENT_YELLOW",
    "PARTICLE_CLR": "ACCENT_BLUE",
    "TUNNEL_FLASH": "GREEN",
    "REFLECT_CLR": "RED",
    "BLOCH_RING": "SUBTEXT",
    "SURFACE_CLR": "SURFACE",
    "OVERLAY_CLR": "OVERLAY",
    "WHITE": "WHITE",
}


def _load_theme_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    load_pg_colors(_COLOR_MAP, globals())


# ── 블로흐 구 레이아웃 (config.json에서 로드) ──────────
BLOCH_CX = cfg("tunneling", "bloch_cx", 730)
BLOCH_CY = cfg("tunneling", "bloch_cy", 280)
BLOCH_R = cfg("tunneling", "bloch_r", 110)
_CIRCLE_STEPS = cfg("tunneling", "circle_steps", 48)

# ── 실시간 확률 차트 레이아웃 ─────────────────────────
_CHART_X = SIM_LEFT
_CHART_Y = SIM_TOP + SIM_H + 2  # sim 영역 바로 아래
_CHART_W = SIM_W
_CHART_H = 52
_CHART_PAD_L = 22  # y축 라벨
_CHART_PAD_T = 3
_CHART_PAD_B = 10  # x축 라벨

# ── 플래시 이징 (#22) ─────────────────────────────────


def _ease_out(t_norm: float) -> float:
    """ease-out 커브: 1-(1-t)^2. t_norm 은 0→1 (시작→끝)."""
    clamped = max(0.0, min(1.0, t_norm))
    inv = 1.0 - clamped
    return 1.0 - inv * inv


def _flash_ease(flash_timer: float, flash_duration: float) -> float:
    """flash_timer(남은 시간) → ease-out 적용된 0~1 세기 반환."""
    if flash_duration <= 0.0:
        return 0.0
    # 진행률: 0(방금 시작) → 1(거의 끝)
    progress = 1.0 - max(0.0, flash_timer) / flash_duration
    # ease-out 적용 후 반전 → 시작에 밝고 끝에 빠르게 사라짐
    return 1.0 - _ease_out(progress)


# ── 입자 궤적 잔상 (config.json에서 로드) ──────────────
_MAX_TRAILS = cfg("tunneling", "max_trails", 30)
_TRAIL_SAMPLE = cfg("tunneling", "trail_sample", 3)
_TRAIL_DOT_R = cfg("tunneling", "trail_dot_radius", 2)

# ── 업적 진행도 레이아웃 ──────────────────────────────
_ACH_X = WIDTH + 10
_ACH_Y = 210  # 슬라이더 패널 아래
_ACH_LINE_H = 16

# ── 업적 임계값 (config에서 로드) ─────────────────────
_ACH_STREAK = cfg("achievements", "tn_tunnel_streak", 10)
_ACH_RATE_THR = cfg("achievements", "tn_rate_threshold", 0.5)
_ACH_RATE_MIN = cfg("achievements", "tn_rate_min_attempts", 10)
_ACH_RATE_HIGH = cfg("achievements", "tn_rate_high", 0.75)
_ACH_SPEED_COUNT = cfg("achievements", "tn_speed_run_count", 20)
_ACH_SPEED_TIME = cfg("achievements", "tn_speed_run_time", 30)
_ACH_QA_MIN = cfg("achievements", "tn_qa_min_attempts", 20)
_ACH_COMPARE = cfg("achievements", "tn_compare_configs", 3)
_ACH_BARRIER_W = cfg("achievements", "tn_barrier_master_width", 100)


# ── 텍스트 캐시 (#19) ─────────────────────────────────


class _TextCache:
    """font.render() 결과 캐싱 — 동일 (font_id, text, color) 키 → Surface 재사용."""

    __slots__ = ("_cache", "_max_size")

    def __init__(self, max_size: int = 256):
        self._cache: dict = {}
        self._max_size = max_size

    def render(self, font, text: str, color) -> pygame.Surface:
        key = (id(font), text, color[0], color[1], color[2])
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        if len(self._cache) >= self._max_size:
            keys = list(self._cache.keys())
            for k in keys[: len(keys) // 2]:
                del self._cache[k]
        surf = font.render(text, True, color)
        self._cache[key] = surf
        return surf

    def clear(self):
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


_tcache = _TextCache()


# ── 대원 메시 캐시 (#20) ─────────────────────────────

# 사전 계산된 3D 기저점 (모듈 로드 시 1회 계산)
_EQUATOR_PTS = tuple(
    (math.cos(2 * math.pi * i / _CIRCLE_STEPS), math.sin(2 * math.pi * i / _CIRCLE_STEPS), 0.0)
    for i in range(_CIRCLE_STEPS)
)
_MERIDIAN_XZ = tuple(
    (math.sin(2 * math.pi * i / _CIRCLE_STEPS), 0.0, math.cos(2 * math.pi * i / _CIRCLE_STEPS))
    for i in range(_CIRCLE_STEPS)
)
_MERIDIAN_YZ = tuple(
    (0.0, math.sin(2 * math.pi * i / _CIRCLE_STEPS), math.cos(2 * math.pi * i / _CIRCLE_STEPS))
    for i in range(_CIRCLE_STEPS)
)


class _BlochMeshCache:
    """블로흐 구 대원 투영 결과 캐싱 — view 각도 변경 시에만 재계산."""

    __slots__ = ("_phi", "_el", "_projected")

    def __init__(self):
        self._phi: float | None = None
        self._el: float | None = None
        self._projected: dict[str, list[tuple[int, int, float]]] = {}

    def get(self, name: str, base_pts: tuple, phi: float, el: float) -> list[tuple[int, int, float]]:
        if phi != self._phi or el != self._el:
            self._projected.clear()
            self._phi = phi
            self._el = el
        cached = self._projected.get(name)
        if cached is not None:
            return cached
        cp, sp = math.cos(phi), math.sin(phi)
        ce, se = math.cos(el), math.sin(el)
        pts: list[tuple[int, int, float]] = []
        for x3, y3, z3 in base_pts:
            x1 = x3 * cp - y3 * sp
            y1 = x3 * sp + y3 * cp
            depth = y1 * ce + z3 * se
            z2 = -y1 * se + z3 * ce
            pts.append((BLOCH_CX + int(x1 * BLOCH_R), BLOCH_CY - int(z2 * BLOCH_R), depth))
        self._projected[name] = pts
        return pts

    def invalidate(self):
        self._phi = None
        self._el = None
        self._projected.clear()


_bloch_mesh = _BlochMeshCache()


# ── 트레일 서피스 캐시 (#21) ────────────────────────────


class _TrailCache:
    """과거 궤적 서피스 캐싱 — trails 변경 시에만 재빌드."""

    __slots__ = ("_surf", "_dirty")

    def __init__(self):
        self._surf: pygame.Surface | None = None
        self._dirty = True

    def mark_dirty(self):
        self._dirty = True

    def get_surface(self, trails) -> pygame.Surface:
        """trails 목록이 변경되지 않았으면 캐시된 서피스 반환."""
        if not self._dirty and self._surf is not None:
            return self._surf
        surf = pygame.Surface((SIM_W, SIM_H), pygame.SRCALPHA)
        n_trails = len(trails)
        for i, (pts, result) in enumerate(trails):
            base_alpha = max(15, int(70 * (i + 1) / max(n_trails, 1)))
            clr = TUNNEL_FLASH if result else REFLECT_CLR
            rgba = (*clr[:3], base_alpha)
            for px, py in pts:
                sx, sy = px - SIM_LEFT, py - SIM_TOP
                if 0 <= sx < SIM_W and 0 <= sy < SIM_H:
                    pygame.draw.circle(surf, rgba, (sx, sy), _TRAIL_DOT_R)
        self._surf = surf
        self._dirty = False
        return surf

    def clear(self):
        self._surf = None
        self._dirty = True


# ── 에너지 레벨 다이어그램 (#28) ─────────────────────
_EDIAG_W = BLOCH_R * 2  # 블로흐 구 직경과 동일
_EDIAG_H = 80
_EDIAG_X = BLOCH_CX - BLOCH_R
_EDIAG_Y = BLOCH_CY + BLOCH_R + 135  # stats 아래

# ── 수식 오버레이 레이아웃 ────────────────────────────
_FORMULA_X = BLOCH_CX - BLOCH_R  # 블로흐 구 좌측 정렬
_FORMULA_Y = 45
_FORMULA_W = BLOCH_R * 2  # 블로흐 구 직경과 동일
_FORMULA_H = 140

# ── 배리어 스위퍼 차트 (#29) ──────────────────────────
_SWEEP_CHART_H = 90  # rate chart보다 더 큰 영역

# ── 실험 데이터 비교 (#32) ────────────────────────────
_EXP_CHART_H = 120


# ── 그리기 헬퍼 ──────────────────────────────────────


def _draw_sim_area(
    screen, font, barrier_width: int = BARRIER_WIDTH_DEFAULT, barrier_hover=False, barrier_dragging=False
):
    """시뮬레이션 영역 배경."""
    pygame.draw.rect(screen, SURFACE_CLR, (SIM_LEFT, SIM_TOP, SIM_W, SIM_H))
    pygame.draw.rect(screen, OVERLAY_CLR, (SIM_LEFT, SIM_TOP, SIM_W, SIM_H), 1)

    # 장벽
    bx = BARRIER_X - barrier_width // 2
    pygame.draw.rect(screen, BARRIER_CLR, (bx, SIM_TOP, barrier_width, SIM_H))

    # 장벽 가장자리 하이라이트 (호버 또는 드래그 시)
    if barrier_hover or barrier_dragging:
        edge_clr = WHITE if barrier_dragging else ACCENT
        left_edge = BARRIER_X - barrier_width // 2
        right_edge = BARRIER_X + barrier_width // 2
        pygame.draw.line(screen, edge_clr, (left_edge, SIM_TOP), (left_edge, SIM_TOP + SIM_H), 2)
        pygame.draw.line(screen, edge_clr, (right_edge, SIM_TOP), (right_edge, SIM_TOP + SIM_H), 2)
        # 두께 표시
        w_lbl = _tcache.render(font, f"{barrier_width}px", edge_clr)
        screen.blit(w_lbl, (BARRIER_X - w_lbl.get_width() // 2, SIM_TOP + SIM_H - 18))

    # 장벽 라벨
    label = _tcache.render(font, t("tn_barrier"), BG)
    label_rot = pygame.transform.rotate(label, 90)
    screen.blit(label_rot, (bx - 2, SIM_TOP + SIM_H // 2 - label_rot.get_height() // 2))

    # 영역 라벨
    left_label = _tcache.render(font, t("tn_classical"), OVERLAY_CLR)
    screen.blit(left_label, (SIM_LEFT + 10, SIM_TOP + 5))
    right_label = _tcache.render(font, t("tn_tunneled"), OVERLAY_CLR)
    screen.blit(right_label, (BARRIER_X + 20, SIM_TOP + 5))


def _draw_wavefunction(screen, barrier_width: int, tunnel_prob: float, time_ms: float):
    """파동함수 ψ(x) 시각화 — 장벽 아래 지수 감쇠 표시 (#27)."""
    points = compute_psi(barrier_width, tunnel_prob)
    if len(points) < 2:
        return

    # 파동함수를 시뮬레이션 영역 하단 1/3에 그리기
    psi_y_center = SIM_TOP + SIM_H * 0.72
    psi_amplitude = SIM_H * 0.18

    # 시간에 따라 위상 이동 (진행파 효과)
    phase = time_ms * 0.003

    surf = pygame.Surface((SIM_W, SIM_H), pygame.SRCALPHA)

    # 영역별 색상 결정을 위한 장벽 경계 (정규화 좌표)
    b_left = 0.5 - (barrier_width / SIM_W) * 0.5
    b_right = 0.5 + (barrier_width / SIM_W) * 0.5

    prev = None
    for x_norm, psi in points:
        # 시간 진행파: 입사/투과 영역에서만 위상 이동
        if x_norm < b_left or x_norm > b_right:
            animated = psi * math.cos(phase)
        else:
            animated = psi  # 장벽 내부: 감쇠만 (진행 없음)

        sx = int(x_norm * SIM_W)
        sy = int(psi_y_center - SIM_TOP + psi_amplitude * animated)
        sy = max(0, min(SIM_H - 1, sy))

        # 영역별 색상
        if x_norm < b_left:
            clr = (*PARTICLE_CLR[:3], 100)
        elif x_norm <= b_right:
            clr = (*BARRIER_CLR[:3], 120)
        else:
            clr = (*TUNNEL_FLASH[:3], 80)

        if prev is not None:
            pygame.draw.line(surf, clr, prev, (sx, sy), 2)
        prev = (sx, sy)

    # 중심선 (ψ=0 기준선)
    base_y = int(psi_y_center - SIM_TOP)
    pygame.draw.line(surf, (*TEXT_CLR[:3], 30), (0, base_y), (SIM_W, base_y), 1)

    # ψ(x) 라벨
    lbl = _tcache.render(get_font(10), "\u03c8(x)", (*ACCENT[:3],))
    surf.blit(lbl, (4, base_y - 14))

    screen.blit(surf, (SIM_LEFT, SIM_TOP))


def _draw_trails(screen, trail_cache, trails, current_trail, current_result):
    """과거 입자 궤적 잔상 렌더링 (과거 궤적은 캐시 서피스 사용)."""
    if not trails and not current_trail:
        return

    # 과거 궤적 — 캐시된 서피스 (#21)
    if trails:
        screen.blit(trail_cache.get_surface(trails), (SIM_LEFT, SIM_TOP))

    # 현재 진행 중인 궤적 — 매 프레임 갱신
    if current_trail:
        cur_surf = pygame.Surface((SIM_W, SIM_H), pygame.SRCALPHA)
        if current_result is True:
            clr = TUNNEL_FLASH
        elif current_result is False:
            clr = REFLECT_CLR
        else:
            clr = PARTICLE_CLR
        rgba = (*clr[:3], 100)
        for px, py in current_trail:
            sx, sy = px - SIM_LEFT, py - SIM_TOP
            if 0 <= sx < SIM_W and 0 <= sy < SIM_H:
                pygame.draw.circle(cur_surf, rgba, (sx, sy), _TRAIL_DOT_R)
        screen.blit(cur_surf, (SIM_LEFT, SIM_TOP))


def _draw_particle(screen, p: QuantumParticle, font):
    """입자 렌더링."""
    cx, cy = int(p.x), int(p.y)
    time_ms = pygame.time.get_ticks()

    # 터널링/반사 플래시 (ease-out 이징, #22)
    if p.flash_timer > 0:
        duration = _TUNNEL_FLASH if p.tunneled else _REFLECT_FLASH
        eased = _flash_ease(p.flash_timer, duration)
        flash_r = int(PARTICLE_RADIUS + 20 * eased)
        flash_clr = TUNNEL_FLASH if p.tunneled else REFLECT_CLR
        glow = pygame.Surface((flash_r * 2, flash_r * 2), pygame.SRCALPHA)
        alpha = int(120 * eased)
        pygame.draw.circle(glow, (*flash_clr, alpha), (flash_r, flash_r), flash_r)
        screen.blit(glow, (cx - flash_r, cy - flash_r))

    # 입자 본체 — 터널링 성공 시 흰색, 평상시 파랑
    color = WHITE if (p.tunneled is True and p.flash_timer > 0) else PARTICLE_CLR
    pygame.draw.circle(screen, color, (cx, cy), PARTICLE_RADIUS)
    pygame.draw.circle(screen, TEXT_CLR, (cx, cy), PARTICLE_RADIUS, 1)

    # 중첩 |0⟩/|1⟩ 텍스트
    state_text = f"|{p.qubit_state(time_ms)}⟩"
    surf = _tcache.render(font, state_text, WHITE)
    screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))


def _project_bloch(x3, y3, z3, phi, el):
    """3D 블로흐 좌표 → 2D 화면 좌표 + 깊이 (직교 투영).

    Returns:
        (screen_x, screen_y, depth) — depth > 0 이면 구 뒷면.
    """
    cp, sp = math.cos(phi), math.sin(phi)
    ce, se = math.cos(el), math.sin(el)
    # Z축 회전 (방위각)
    x1 = x3 * cp - y3 * sp
    y1 = x3 * sp + y3 * cp
    # X축 회전 (기울기)
    depth = y1 * ce + z3 * se
    z2 = -y1 * se + z3 * ce
    sx = BLOCH_CX + int(x1 * BLOCH_R)
    sy = BLOCH_CY - int(z2 * BLOCH_R)
    return sx, sy, depth


def _draw_circle_cached(screen, name, base_pts, phi, el, color_front, color_back):
    """대원 그리기 — 사전 계산된 기저점 + 투영 캐시 사용."""
    pts = _bloch_mesh.get(name, base_pts, phi, el)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        behind = pts[i][2] > 0 and pts[j][2] > 0
        clr = color_back if behind else color_front
        pygame.draw.line(screen, clr, pts[i][:2], pts[j][:2], 1)


def _draw_bloch_sphere(screen, p: QuantumParticle, font, title_font, view_phi, view_el):
    """블로흐 구 시각화 (3D 회전 가능)."""
    time_ms = pygame.time.get_ticks()

    # 타이틀
    label = _tcache.render(title_font, t("tn_bloch"), ACCENT)
    screen.blit(label, (BLOCH_CX - label.get_width() // 2, BLOCH_CY - BLOCH_R - 40))

    # 구 외곽 (실루엣)
    pygame.draw.circle(screen, BLOCH_RING, (BLOCH_CX, BLOCH_CY), BLOCH_R, 1)

    # 색상: 전면/후면
    dim = tuple(max(c // 3, 0) for c in BLOCH_RING)

    # 적도 (XY 평면, z=0) — 캐시된 기저점 사용
    _draw_circle_cached(screen, "equator", _EQUATOR_PTS, view_phi, view_el, BLOCH_RING, dim)
    # XZ 경선 (y=0) — 상태 벡터가 위치하는 평면
    _draw_circle_cached(screen, "xz", _MERIDIAN_XZ, view_phi, view_el, BLOCH_RING, dim)
    # YZ 경선 (x=0)
    _draw_circle_cached(screen, "yz", _MERIDIAN_YZ, view_phi, view_el, BLOCH_RING, dim)

    # Z축
    t0x, t0y, _ = _project_bloch(0, 0, 1.12, view_phi, view_el)
    b0x, b0y, _ = _project_bloch(0, 0, -1.12, view_phi, view_el)
    pygame.draw.line(screen, OVERLAY_CLR, (t0x, t0y), (b0x, b0y), 1)

    # |0⟩, |1⟩ 라벨
    lx0, ly0, _ = _project_bloch(0, 0, 1.22, view_phi, view_el)
    lx1, ly1, _ = _project_bloch(0, 0, -1.22, view_phi, view_el)
    z0 = _tcache.render(font, "|0⟩", TUNNEL_FLASH)
    z1 = _tcache.render(font, "|1⟩", REFLECT_CLR)
    screen.blit(z0, (lx0 + 4, ly0 - 8))
    screen.blit(z1, (lx1 + 4, ly1 - 4))

    # X축 라벨 (|+⟩)
    lxx, lxy, _ = _project_bloch(1.18, 0, 0, view_phi, view_el)
    xlab = _tcache.render(font, "|+⟩", OVERLAY_CLR)
    screen.blit(xlab, (lxx - xlab.get_width() // 2, lxy - 14))

    # 상태 벡터 (θ 기반, XZ 평면)
    theta = p.superposition_alpha(time_ms)
    sv_x, sv_y, sv_z = math.sin(theta), 0.0, math.cos(theta)
    tip_sx, tip_sy, _ = _project_bloch(sv_x, sv_y, sv_z, view_phi, view_el)
    pygame.draw.line(screen, ACCENT, (BLOCH_CX, BLOCH_CY), (tip_sx, tip_sy), 2)
    pygame.draw.circle(screen, ACCENT, (tip_sx, tip_sy), 6)

    # 현재 상태 텍스트
    state_label = (
        f"|{'0' if theta < math.pi / 2 else '1'}⟩  θ={math.degrees(theta):.0f}°  φ={math.degrees(view_phi):.0f}°"
    )
    sl = _tcache.render(font, state_label, TEXT_CLR)
    screen.blit(sl, (BLOCH_CX - sl.get_width() // 2, BLOCH_CY + BLOCH_R + 26))


def _draw_stats(screen, p: QuantumParticle, font, tunnel_prob: float = TUNNEL_PROB_BASE):
    """통계 패널."""
    stats_x = BLOCH_CX - BLOCH_R
    stats_y = BLOCH_CY + BLOCH_R + 60

    lines = [
        (t("tn_attempts", count=p.total_attempts), TEXT_CLR),
        (t("tn_tunnel_stat", count=p.tunnel_count, pct=p.tunnel_count / max(p.total_attempts, 1) * 100), TUNNEL_FLASH),
        (
            t("tn_reflect_stat", count=p.reflect_count, pct=p.reflect_count / max(p.total_attempts, 1) * 100),
            REFLECT_CLR,
        ),
        (t("tn_current_prob", prob=tunnel_prob * 100), TEXT_CLR),
    ]
    for i, (line, color) in enumerate(lines):
        surf = _tcache.render(font, line, color)
        screen.blit(surf, (stats_x, stats_y + i * 17))


def _draw_energy_diagram(screen, font, barrier_width: int, tunnel_prob: float):
    """에너지 레벨 다이어그램 — 입자 에너지 vs 장벽 높이 시각 비교 (#28)."""
    levels = calc_energy_levels(barrier_width, tunnel_prob)
    ex, ey = _EDIAG_X, _EDIAG_Y
    ew, eh = _EDIAG_W, _EDIAG_H

    e_particle = levels["particle_energy"]
    v0 = levels["barrier_height"]
    ratio = levels["ratio"]

    # 반투명 배경
    bg = pygame.Surface((ew, eh), pygame.SRCALPHA)
    bg.fill((*BG[:3], 200))
    screen.blit(bg, (ex, ey))
    pygame.draw.rect(screen, OVERLAY_CLR, (ex, ey, ew, eh), 1)

    # 타이틀
    title = _tcache.render(font, t("tn_energy_title"), TEXT_CLR)
    screen.blit(title, (ex + ew // 2 - title.get_width() // 2, ey + 2))

    # 다이어그램 영역 (패딩)
    dx = ex + 40  # 좌측 라벨 여유
    dy = ey + 16
    dw = ew - 50
    dh = eh - 24

    # 장벽 높이 바
    bar_w = dw // 3
    v0_h = int(dh * v0)
    v0_y = dy + dh - v0_h
    pygame.draw.rect(screen, (*BARRIER_CLR[:3], 100), (dx, v0_y, bar_w, v0_h))
    pygame.draw.rect(screen, BARRIER_CLR, (dx, v0_y, bar_w, v0_h), 1)

    # V₀ 라벨
    v_lbl = _tcache.render(font, "V\u2080", BARRIER_CLR)
    screen.blit(v_lbl, (dx + bar_w // 2 - v_lbl.get_width() // 2, v0_y - 12))

    # 입자 에너지 수평선 (전체 너비)
    e_h = int(dh * e_particle)
    e_y = dy + dh - e_h
    pygame.draw.line(screen, PARTICLE_CLR, (dx - 4, e_y), (dx + dw, e_y), 2)

    # E 라벨
    e_lbl = _tcache.render(font, "E", PARTICLE_CLR)
    screen.blit(e_lbl, (dx - 14, e_y - 6))

    # 터널링 영역 화살표 (E < V₀ 표시)
    gap_top = e_y
    gap_bot = v0_y
    arrow_x = dx + bar_w + 20
    if gap_bot > gap_top + 6:
        # 위/아래 화살표
        mid_y = (gap_top + gap_bot) // 2
        pygame.draw.line(screen, ACCENT, (arrow_x, gap_top + 2), (arrow_x, gap_bot - 2), 1)
        pygame.draw.polygon(
            screen, ACCENT, [(arrow_x, gap_top + 2), (arrow_x - 3, gap_top + 7), (arrow_x + 3, gap_top + 7)]
        )
        pygame.draw.polygon(
            screen, ACCENT, [(arrow_x, gap_bot - 2), (arrow_x - 3, gap_bot - 7), (arrow_x + 3, gap_bot - 7)]
        )
        # V₀ - E 차이 라벨
        diff_lbl = _tcache.render(font, "V\u2080\u2212E", ACCENT)
        screen.blit(diff_lbl, (arrow_x + 5, mid_y - 6))

    # 하단: E/V₀ 비율 + 터널링 확률
    ratio_text = f"E/V\u2080={ratio:.2f}  P={tunnel_prob * 100:.1f}%"
    r_clr = TUNNEL_FLASH if tunnel_prob > 0.05 else REFLECT_CLR
    r_surf = _tcache.render(font, ratio_text, r_clr)
    screen.blit(r_surf, (ex + 4, ey + eh - 13))

    # 기준선 (E=0)
    base_y = dy + dh
    pygame.draw.line(screen, (*TEXT_CLR[:3], 60), (dx - 4, base_y), (dx + dw, base_y), 1)


def _draw_formula_overlay(screen, font, ctx):
    """핵심 터널링 수식 오버레이 — 슬라이더 값에 따른 실시간 계산 표시."""
    fx, fy, fw, fh = _FORMULA_X, _FORMULA_Y, _FORMULA_W, _FORMULA_H
    bw = ctx.barrier_width
    bp = ctx.base_prob
    tp = ctx.tunnel_prob
    p = ctx.particle

    # 반투명 배경
    bg_surf = pygame.Surface((fw, fh), pygame.SRCALPHA)
    bg_surf.fill((*BG[:3], 200))
    screen.blit(bg_surf, (fx, fy))
    pygame.draw.rect(screen, OVERLAY_CLR, (fx, fy, fw, fh), 1)

    # 타이틀
    title = _tcache.render(font, t("tn_formula_title"), ACCENT)
    screen.blit(title, (fx + fw // 2 - title.get_width() // 2, fy + 3))

    y = fy + 18

    # ① 수식: P = P₀ × e^(−κ(L−L₀))
    f1 = _tcache.render(font, "P = P\u2080 \u00d7 e", BARRIER_CLR)
    screen.blit(f1, (fx + 8, y))
    exp_text = _tcache.render(font, "(\u2212\u03ba(L\u2212L\u2080))", TEXT_CLR)
    screen.blit(exp_text, (fx + 8 + f1.get_width(), y - 3))
    y += 16

    # ② 파라미터 값 (슬라이더에서 실시간 반영)
    params = f"P\u2080={bp:.2f}  \u03ba={_TUNNEL_DECAY}  L={bw}  L\u2080={BARRIER_WIDTH_DEFAULT}"
    p_surf = _tcache.render(font, params, TEXT_CLR)
    screen.blit(p_surf, (fx + 8, y))
    y += 16

    # ③ 지수 계산 과정
    exponent = -_TUNNEL_DECAY * (bw - BARRIER_WIDTH_DEFAULT)
    exp_val = math.exp(max(-500.0, min(500.0, exponent)))
    calc = f"e^({exponent:+.2f}) = {exp_val:.4f}"
    c_surf = _tcache.render(font, calc, BARRIER_CLR)
    screen.blit(c_surf, (fx + 8, y))
    y += 16

    # ④ 최종 결과
    result = f"P = {bp:.2f} \u00d7 {exp_val:.4f} = {tp * 100:.1f}%"
    r_surf = _tcache.render(font, result, TUNNEL_FLASH)
    screen.blit(r_surf, (fx + 8, y))
    y += 18

    # ⑤ 관측 성공률 vs 이론 확률 비교
    if p.total_attempts > 0:
        observed = p.tunnel_count / p.total_attempts
        diff = observed - tp
        diff_sign = "+" if diff >= 0 else ""
        obs_clr = TUNNEL_FLASH if observed >= tp else REFLECT_CLR
        obs_text = f"Obs {observed * 100:.1f}% vs Th {tp * 100:.1f}% ({diff_sign}{diff * 100:.1f}%)"
        obs_surf = _tcache.render(font, obs_text, obs_clr)
        screen.blit(obs_surf, (fx + 8, y))
    else:
        no_data = _tcache.render(font, "(no trials yet)", OVERLAY_CLR)
        screen.blit(no_data, (fx + 8, y))


def _draw_rate_chart(screen, font, trial_history, tunnel_prob, imported_trials=None):
    """누적 터널링 확률 실시간 라인 차트."""
    # 내부 차트 영역
    cx = _CHART_X + _CHART_PAD_L
    cy = _CHART_Y + _CHART_PAD_T
    cw = _CHART_W - _CHART_PAD_L - 4
    ch = _CHART_H - _CHART_PAD_T - _CHART_PAD_B

    # 배경 (반투명)
    bg_surf = pygame.Surface((_CHART_W, _CHART_H), pygame.SRCALPHA)
    bg_surf.fill((*BG[:3], 200))
    screen.blit(bg_surf, (_CHART_X, _CHART_Y))
    pygame.draw.rect(screen, OVERLAY_CLR, (_CHART_X, _CHART_Y, _CHART_W, _CHART_H), 1)

    # 타이틀 (우상단)
    title = _tcache.render(font, t("tn_rate_chart"), TEXT_CLR)
    screen.blit(title, (cx + cw - title.get_width(), _CHART_Y + 1))

    # y축 눈금선 + 라벨
    for frac in (1.0, 0.5, 0.0):
        gy = cy + int((1 - frac) * ch)
        pygame.draw.line(screen, OVERLAY_CLR, (cx, gy), (cx + cw, gy), 1)
    l_top = _tcache.render(font, "1.0", OVERLAY_CLR)
    l_bot = _tcache.render(font, "0", OVERLAY_CLR)
    screen.blit(l_top, (_CHART_X + 1, cy - 4))
    screen.blit(l_bot, (_CHART_X + 10, cy + ch - 6))

    # 이론 확률 (노란 점선)
    tp = min(max(tunnel_prob, 0.0), 1.0)
    prob_y = cy + int((1 - tp) * ch)
    for dx in range(0, cw, 6):
        x1 = cx + dx
        x2 = min(x1 + 3, cx + cw)
        pygame.draw.line(screen, BARRIER_CLR, (x1, prob_y), (x2, prob_y), 1)
    # 이론 확률 라벨
    tp_lbl = _tcache.render(font, f"P={tp * 100:.0f}%", BARRIER_CLR)
    screen.blit(tp_lbl, (cx + cw - tp_lbl.get_width(), prob_y - 12))

    # 가져온 비교 데이터 (점선 보라색 라인)
    if imported_trials:
        _draw_imported_overlay(screen, font, imported_trials, cx, cy, cw, ch)

    if not trial_history:
        msg = _tcache.render(font, t("tn_no_data"), OVERLAY_CLR)
        screen.blit(msg, (cx + cw // 2 - msg.get_width() // 2, cy + ch // 2 - 5))
        return

    # 누적 터널링 확률 계산
    n = len(trial_history)
    tunnels = 0
    rates = []
    for i, tr in enumerate(trial_history):
        if tr["result"]:
            tunnels += 1
        rates.append(tunnels / (i + 1))

    # 라인 포인트 생성 (서브샘플링)
    max_pts = min(n, cw)
    points = []
    for i in range(max_pts):
        idx = int(i * (n - 1) / max(max_pts - 1, 1))
        px = cx + int(i * cw / max(max_pts - 1, 1))
        py = cy + int((1 - rates[idx]) * ch)
        points.append((px, py))

    if len(points) >= 2:
        pygame.draw.lines(screen, TUNNEL_FLASH, False, points, 2)
    elif len(points) == 1:
        pygame.draw.circle(screen, TUNNEL_FLASH, points[0], 3)

    # 최종 누적값 표시
    last_rate = rates[-1]
    rate_surf = _tcache.render(font, f"{last_rate * 100:.1f}%", TUNNEL_FLASH)
    last_py = cy + int((1 - last_rate) * ch)
    screen.blit(rate_surf, (cx + cw + 2 - rate_surf.get_width() - 50, max(cy - 2, last_py - 10)))

    # 시행 횟수 (x축 우측 하단)
    n_surf = _tcache.render(font, f"n={n}", OVERLAY_CLR)
    screen.blit(n_surf, (cx + cw - n_surf.get_width(), cy + ch + 1))


def _draw_imported_overlay(screen, font, trials, cx, cy, cw, ch):
    """가져온 시행 이력을 차트에 점선 보라색 라인으로 표시."""
    n = len(trials)
    if n == 0:
        return
    tunnels = 0
    rates = []
    for i, tr in enumerate(trials):
        if tr["result"]:
            tunnels += 1
        rates.append(tunnels / (i + 1))

    max_pts = min(n, cw)
    points = []
    for i in range(max_pts):
        idx = int(i * (n - 1) / max(max_pts - 1, 1))
        px = cx + int(i * cw / max(max_pts - 1, 1))
        py = cy + int((1 - rates[idx]) * ch)
        points.append((px, py))

    # 점선으로 렌더링
    for i in range(0, len(points) - 1, 2):
        j = min(i + 1, len(points) - 1)
        pygame.draw.line(screen, ACCENT, points[i], points[j], 1)

    # 라벨
    imp_rate = rates[-1]
    imp_surf = _tcache.render(font, f"imp:{imp_rate * 100:.0f}%", ACCENT)
    imp_py = cy + int((1 - imp_rate) * ch)
    screen.blit(imp_surf, (cx + 2, max(cy, imp_py - 10)))


def _draw_sweep_chart(screen, font, sweeper: BarrierSweeper):
    """배리어 스위퍼 결과를 rate chart 위치에 오버레이 렌더링."""
    # 차트 영역 (rate chart와 동일한 X, 약간 위로 확장)
    sx = _CHART_X
    sy = _CHART_Y - (_SWEEP_CHART_H - _CHART_H)
    sw = _CHART_W
    sh = _SWEEP_CHART_H

    pad_l, pad_t, pad_b = _CHART_PAD_L, _CHART_PAD_T, _CHART_PAD_B
    cx = sx + pad_l
    cy = sy + pad_t
    cw = sw - pad_l - 4
    ch = sh - pad_t - pad_b

    # 배경 (반투명)
    bg_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
    bg_surf.fill((*BG[:3], 220))
    screen.blit(bg_surf, (sx, sy))
    pygame.draw.rect(screen, OVERLAY_CLR, (sx, sy, sw, sh), 1)

    # 타이틀
    title = _tcache.render(font, t("tn_sweep_title"), TEXT_CLR)
    screen.blit(title, (cx + cw - title.get_width(), sy + 1))

    # 진행률 바 (스위프 진행 중일 때)
    if not sweeper.done:
        prog = sweeper.progress
        bar_w = int(cw * prog)
        pygame.draw.rect(screen, ACCENT, (cx, sy + 12, bar_w, 4))
        pygame.draw.rect(screen, OVERLAY_CLR, (cx, sy + 12, cw, 4), 1)
        pct_lbl = _tcache.render(font, f"{prog * 100:.0f}%  w={sweeper.current_width}px", OVERLAY_CLR)
        screen.blit(pct_lbl, (cx + bar_w + 4, sy + 9))

    results = sweeper.get_sorted_results()
    if not results:
        msg = _tcache.render(font, t("tn_sweep_running"), OVERLAY_CLR)
        screen.blit(msg, (cx + cw // 2 - msg.get_width() // 2, cy + ch // 2 - 5))
        return

    # y축: 확률 0~max, x축: 장벽 폭
    max_rate = max(max(r[1] for r in results), max(r[2] for r in results), 0.01)

    # y축 눈금
    for frac in (1.0, 0.5, 0.0):
        gy = cy + int((1 - frac) * ch)
        pygame.draw.line(screen, OVERLAY_CLR, (cx, gy), (cx + cw, gy), 1)
    l_top = _tcache.render(font, f"{max_rate * 100:.0f}%", OVERLAY_CLR)
    l_bot = _tcache.render(font, "0", OVERLAY_CLR)
    screen.blit(l_top, (sx + 1, cy - 4))
    screen.blit(l_bot, (sx + 10, cy + ch - 6))

    n = len(results)

    # 이론 곡선 (노란 점선)
    theory_pts = []
    for i, (_w, _meas, theory) in enumerate(results):
        px = cx + int(i * cw / max(n - 1, 1))
        py = cy + int((1 - theory / max_rate) * ch)
        theory_pts.append((px, py))
    if len(theory_pts) >= 2:
        for i in range(0, len(theory_pts) - 1, 2):
            j = min(i + 1, len(theory_pts) - 1)
            pygame.draw.line(screen, BARRIER_CLR, theory_pts[i], theory_pts[j], 1)

    # 측정 곡선 (녹색 실선)
    meas_pts = []
    for i, (_w, meas, _theory) in enumerate(results):
        px = cx + int(i * cw / max(n - 1, 1))
        py = cy + int((1 - meas / max_rate) * ch)
        meas_pts.append((px, py))
    if len(meas_pts) >= 2:
        pygame.draw.lines(screen, TUNNEL_FLASH, False, meas_pts, 2)
    elif len(meas_pts) == 1:
        pygame.draw.circle(screen, TUNNEL_FLASH, meas_pts[0], 3)

    # x축 라벨 (첫/끝 장벽 폭)
    x_lbl_l = _tcache.render(font, f"{results[0][0]}px", OVERLAY_CLR)
    screen.blit(x_lbl_l, (cx, cy + ch + 1))
    if n > 1:
        x_lbl_r = _tcache.render(font, f"{results[-1][0]}px", OVERLAY_CLR)
        screen.blit(x_lbl_r, (cx + cw - x_lbl_r.get_width(), cy + ch + 1))

    # 범례
    leg_y = sy + 2
    leg_meas = _tcache.render(font, t("tn_sweep_measured"), TUNNEL_FLASH)
    leg_theory = _tcache.render(font, t("tn_sweep_theory"), BARRIER_CLR)
    screen.blit(leg_meas, (cx, leg_y))
    screen.blit(leg_theory, (cx + leg_meas.get_width() + 8, leg_y))

    # F3 토글 안내
    if sweeper.done:
        hint = _tcache.render(font, "F3: " + t("tn_sweep_restart"), OVERLAY_CLR)
        screen.blit(hint, (cx + cw - hint.get_width(), cy + ch + 1))


def _update_exp_fit_stats(ctx):
    """시뮬레이션 trial_history에서 배리어별 평균 투과율을 계산하고 적합도를 갱신."""
    if not ctx.trial_history:
        ctx.exp_fit_stats = None
        return
    # 배리어 폭별 통계 집계
    bw_stats: dict[int, list[bool]] = defaultdict(list)
    for tr in ctx.trial_history:
        bw_stats[tr["barrier"]].append(tr["result"])

    sim_data = []
    for bw in sorted(bw_stats):
        results = bw_stats[bw]
        rate = sum(results) / len(results)
        sim_data.append((bw, rate))

    ref_data = get_experiment_data(ctx.exp_dataset_id)
    ctx.exp_fit_stats = compute_fit_stats(sim_data, ref_data)


def _draw_experiment_chart(screen, font, ctx):
    """실험 데이터 비교 차트 렌더링 (#32)."""
    # 블로흐 구 아래 영역에 배치
    sx = _CHART_X
    sy = _CHART_Y - (_EXP_CHART_H - _CHART_H)
    sw = _CHART_W
    sh = _EXP_CHART_H

    pad_l, pad_t, pad_b = _CHART_PAD_L, _CHART_PAD_T + 12, _CHART_PAD_B
    cx = sx + pad_l
    cy = sy + pad_t
    cw = sw - pad_l - 4
    ch = sh - pad_t - pad_b

    # 배경 (반투명)
    bg_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
    bg_surf.fill((*BG[:3], 220))
    screen.blit(bg_surf, (sx, sy))
    pygame.draw.rect(screen, OVERLAY_CLR, (sx, sy, sw, sh), 1)

    # 타이틀
    title = _tcache.render(font, t("exp_chart_title"), TEXT_CLR)
    screen.blit(title, (cx + cw - title.get_width(), sy + 1))

    datasets = get_experiment_datasets()
    ds_meta = datasets.get(ctx.exp_dataset_id, {})
    ds_name = t(ds_meta.get("name_key", ctx.exp_dataset_id))
    ds_kappa = ds_meta.get("kappa", 0.02)

    # 데이터셋 이름 + 전환 안내
    ds_lbl = _tcache.render(font, f"{ds_name}  (F7: {t('exp_switch_dataset')})", ACCENT)
    screen.blit(ds_lbl, (cx, sy + 1))

    # 실험 참조 데이터
    ref_data = get_experiment_data(ctx.exp_dataset_id)
    if not ref_data:
        return

    # 이론 곡선 (시뮬레이터 수식 기준)
    theory_data = generate_theory_curve(
        base_prob=ctx.base_prob,
        kappa=_TUNNEL_DECAY,
        ref_width=BARRIER_WIDTH_DEFAULT,
        width_min=BARRIER_WIDTH_MIN,
        width_max=BARRIER_WIDTH_MAX,
        step=4,
    )

    # y축 최대값 결정
    all_probs = [p for _, p in ref_data] + [p for _, p in theory_data]
    max_prob = max(all_probs) if all_probs else 0.01
    max_prob = max(max_prob, 0.01)

    # 좌표 변환 헬퍼
    w_min = BARRIER_WIDTH_MIN
    w_max = BARRIER_WIDTH_MAX
    w_range = max(w_max - w_min, 1)

    def to_px(bw: int, prob: float) -> tuple[int, int]:
        px = cx + int((bw - w_min) / w_range * cw)
        py = cy + int((1.0 - prob / max_prob) * ch)
        return (px, py)

    # y축 눈금
    for frac in (1.0, 0.5, 0.0):
        gy = cy + int((1 - frac) * ch)
        pygame.draw.line(screen, OVERLAY_CLR, (cx, gy), (cx + cw, gy), 1)
    l_top = _tcache.render(font, f"{max_prob * 100:.1f}%", OVERLAY_CLR)
    l_bot = _tcache.render(font, "0", OVERLAY_CLR)
    screen.blit(l_top, (sx + 1, cy - 4))
    screen.blit(l_bot, (sx + 10, cy + ch - 6))

    # ① 이론 곡선 (노란 점선)
    theory_pts = [to_px(w, p) for w, p in theory_data]
    if len(theory_pts) >= 2:
        for i in range(0, len(theory_pts) - 1, 2):
            j = min(i + 1, len(theory_pts) - 1)
            pygame.draw.line(screen, BARRIER_CLR, theory_pts[i], theory_pts[j], 1)

    # ② WKB 곡선 (실험 kappa 기준, 하늘색 점선)
    wkb_data = generate_theory_curve(
        base_prob=ctx.base_prob,
        kappa=ds_kappa,
        ref_width=BARRIER_WIDTH_DEFAULT,
        width_min=BARRIER_WIDTH_MIN,
        width_max=BARRIER_WIDTH_MAX,
        step=4,
    )
    wkb_pts = [to_px(w, p) for w, p in wkb_data]
    wkb_color = (100, 180, 255)  # 하늘색
    if len(wkb_pts) >= 2:
        for i in range(0, len(wkb_pts) - 1, 2):
            j = min(i + 1, len(wkb_pts) - 1)
            pygame.draw.line(screen, wkb_color, wkb_pts[i], wkb_pts[j], 1)

    # ③ 실험 참조 데이터 (빨간 ●)
    exp_color = (255, 100, 100)  # 빨간색
    for bw, prob in ref_data:
        px, py = to_px(bw, prob)
        pygame.draw.circle(screen, exp_color, (px, py), 3)

    # ④ 시뮬레이션 측정 데이터 (녹색 ■) — trial_history에서
    bw_stats: dict[int, list[bool]] = defaultdict(list)
    for tr in ctx.trial_history:
        bw_stats[tr["barrier"]].append(tr["result"])

    sim_pts = []
    for bw in sorted(bw_stats):
        results = bw_stats[bw]
        rate = sum(results) / len(results)
        px, py = to_px(bw, rate)
        sim_pts.append((px, py))
        pygame.draw.rect(screen, TUNNEL_FLASH, (px - 2, py - 2, 5, 5))

    if len(sim_pts) >= 2:
        pygame.draw.lines(screen, TUNNEL_FLASH, False, sim_pts, 1)

    # x축 라벨
    x_lbl_l = _tcache.render(font, f"{w_min}px", OVERLAY_CLR)
    screen.blit(x_lbl_l, (cx, cy + ch + 1))
    x_lbl_r = _tcache.render(font, f"{w_max}px", OVERLAY_CLR)
    screen.blit(x_lbl_r, (cx + cw - x_lbl_r.get_width(), cy + ch + 1))

    # 범례 (하단)
    leg_y = cy + ch + 1
    leg_x = cx + 40
    # 시뮬레이션
    pygame.draw.rect(screen, TUNNEL_FLASH, (leg_x, leg_y + 2, 6, 6))
    l1 = _tcache.render(font, t("exp_legend_sim"), TUNNEL_FLASH)
    screen.blit(l1, (leg_x + 9, leg_y))
    leg_x += l1.get_width() + 16
    # 이론
    pygame.draw.line(screen, BARRIER_CLR, (leg_x, leg_y + 5), (leg_x + 10, leg_y + 5), 1)
    l2 = _tcache.render(font, t("exp_legend_theory"), BARRIER_CLR)
    screen.blit(l2, (leg_x + 13, leg_y))
    leg_x += l2.get_width() + 16
    # 실험
    pygame.draw.circle(screen, exp_color, (leg_x + 3, leg_y + 5), 3)
    l3 = _tcache.render(font, t("exp_legend_experiment"), exp_color)
    screen.blit(l3, (leg_x + 9, leg_y))
    leg_x += l3.get_width() + 16
    # WKB
    pygame.draw.line(screen, wkb_color, (leg_x, leg_y + 5), (leg_x + 10, leg_y + 5), 1)
    l4 = _tcache.render(font, "WKB", wkb_color)
    screen.blit(l4, (leg_x + 13, leg_y))

    # 적합도 통계
    if ctx.exp_fit_stats and ctx.exp_fit_stats["n_matched"] > 0:
        st = ctx.exp_fit_stats
        stat_txt = t("exp_fit_label", r2=st["r_squared"], rmse=st["rmse"], n=st["n_matched"])
        stat_surf = _tcache.render(font, stat_txt, TEXT_CLR)
        screen.blit(stat_surf, (cx, sy + 12))


# ── 업적 진행도 ──────────────────────────────────────


def _draw_achievement_progress(screen, font, ctx):
    """업적 진행도 패널 (슬라이더 패널 아래)."""
    p = ctx.particle
    elapsed = time.monotonic() - ctx.start_time
    rate = p.tunnel_count / max(p.total_attempts, 1)

    # 타이틀
    title_surf = _tcache.render(font, "Achievements", ACCENT)
    screen.blit(title_surf, (_ACH_X, _ACH_Y))

    # 구분선
    pygame.draw.line(screen, OVERLAY_CLR, (_ACH_X, _ACH_Y + 14), (_ACH_X + PANEL_W - 20, _ACH_Y + 14), 1)

    # 업적별 진행도 데이터: (id, icon, label, progress_text, fraction)
    items = [
        (
            "tn_first_tunnel",
            "W",
            "First Tunnel",
            f"{min(p.tunnel_count, 1)}/1",
            min(p.tunnel_count, 1) / 1,
        ),
        (
            "tn_lucky_10",
            "L",
            "Lucky Streak",
            f"{min(p.tunnel_count, _ACH_STREAK)}/{_ACH_STREAK}",
            min(p.tunnel_count / _ACH_STREAK, 1.0),
        ),
        (
            "tn_rate_50",
            "B",
            "Prob. Bender",
            f"{rate * 100:.0f}%/{_ACH_RATE_THR * 100:.0f}% ({p.total_attempts}/{_ACH_RATE_MIN})",
            min(rate / _ACH_RATE_THR, 1.0) if p.total_attempts >= _ACH_RATE_MIN else 0.0,
        ),
        (
            "tn_rate_75",
            "A",
            "Quantum Ace",
            f"{rate * 100:.0f}%/{_ACH_RATE_HIGH * 100:.0f}% ({p.total_attempts}/{_ACH_RATE_MIN})",
            min(rate / _ACH_RATE_HIGH, 1.0) if p.total_attempts >= _ACH_RATE_MIN else 0.0,
        ),
        (
            "tn_speed_run",
            "R",
            "Speed Runner",
            f"{min(p.tunnel_count, _ACH_SPEED_COUNT)}/{_ACH_SPEED_COUNT} ({max(0, _ACH_SPEED_TIME - elapsed):.0f}s)",
            min(p.tunnel_count / _ACH_SPEED_COUNT, 1.0) if elapsed <= _ACH_SPEED_TIME else 0.0,
        ),
        (
            "tn_quantum_advantage",
            "Q",
            "Q. Advantage",
            f"rate {rate * 100:.0f}% vs prob {ctx.tunnel_prob * 100:.0f}% ({p.total_attempts}/{_ACH_QA_MIN})",
            1.0 if (rate > ctx.tunnel_prob and p.total_attempts >= _ACH_QA_MIN) else 0.0,
        ),
        (
            "tn_compare_master",
            "C",
            "Compare",
            f"{min(len(ctx.barrier_configs_tried), _ACH_COMPARE)}/{_ACH_COMPARE}",
            min(len(ctx.barrier_configs_tried) / _ACH_COMPARE, 1.0),
        ),
        (
            "tn_barrier_master",
            "X",
            "Barrier Break",
            f"max {ctx.max_tunnel_barrier}/{_ACH_BARRIER_W}px",
            min(ctx.max_tunnel_barrier / _ACH_BARRIER_W, 1.0),
        ),
    ]

    y = _ACH_Y + 18
    bar_w = PANEL_W - 24
    bar_h = 4

    for ach_id, icon, label, progress_text, frac in items:
        completed = ach_id in ctx.unlocked_ids or frac >= 1.0
        clr = TUNNEL_FLASH if completed else TEXT_CLR
        prefix = "[V]" if completed else "[ ]"

        # 아이콘 + 라벨
        lbl_surf = _tcache.render(font, f"{prefix}[{icon}] {label}", clr)
        screen.blit(lbl_surf, (_ACH_X, y))

        # 진행 텍스트
        prog_surf = _tcache.render(font, progress_text, OVERLAY_CLR if not completed else TUNNEL_FLASH)
        screen.blit(prog_surf, (_ACH_X, y + _ACH_LINE_H))

        # 진행 바
        bar_y = y + _ACH_LINE_H * 2 - 2
        pygame.draw.rect(screen, OVERLAY_CLR, (_ACH_X, bar_y, bar_w, bar_h))
        fill_w = int(bar_w * min(frac, 1.0))
        if fill_w > 0:
            bar_clr = TUNNEL_FLASH if completed else ACCENT
            pygame.draw.rect(screen, bar_clr, (_ACH_X, bar_y, fill_w, bar_h))

        y += _ACH_LINE_H * 2 + 6

        # 화면 하단 초과 시 중단
        if y > HEIGHT - 10:
            break
