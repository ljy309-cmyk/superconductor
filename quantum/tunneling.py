"""양자 중첩 및 터널링 시뮬레이션 (Pygame).

- 블로흐 구: 큐비트가 |0⟩ / |1⟩ 사이를 확률적으로 점멸 (중첩 시각화)
- 터널링: 입자가 장벽과 충돌할 때 10 % 확률로 장벽 반대편으로 이동
"""

import math
import time
from collections import deque

import pygame

from config_loader import cfg
from game_base import choose_difficulty_or_quit, finalize_session
from glossary import GlossaryOverlay
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from preset_hud import PresetHUD

# ── 물리 엔진 (순수 로직) ────────────────────────────
from quantum.tunneling_physics import (
    BARRIER_WIDTH_DEFAULT,
    BARRIER_WIDTH_MAX,
    BARRIER_WIDTH_MIN,
    BARRIER_X,
    PARTICLE_RADIUS,
    SIM_H,
    SIM_LEFT,
    SIM_TOP,
    SIM_W,
    TRIAL_HISTORY_MAX,
    TUNNEL_PROB_BASE,
    TUNNEL_SPEED_BOOST,
    QuantumParticle,
    _calc_tunnel_prob,
)
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from sim_speed import apply_speed, cycle_sim_speed, speed_label
from sound_manager import get_sound_manager
from theme import load_pg_colors, on_theme_change
from tutorial import TutorialOverlay
from ui.slider import PANEL_W, SliderPanel

_log = get_module_logger("tunneling")

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
_BLOCH_EL_DEFAULT = 0.25  # 기본 기울기 (rad) — 약 14°
_BLOCH_EL_MIN, _BLOCH_EL_MAX = -1.0, 1.0
_BLOCH_DRAG_SENSITIVITY = 0.008  # 마우스 픽셀 → 라디안
_CIRCLE_STEPS = cfg("tunneling", "circle_steps", 48)

# ── 실시간 확률 차트 레이아웃 ─────────────────────────
_CHART_X = SIM_LEFT
_CHART_Y = SIM_TOP + SIM_H + 2  # sim 영역 바로 아래
_CHART_W = SIM_W
_CHART_H = 52
_CHART_PAD_L = 22  # y축 라벨
_CHART_PAD_T = 3
_CHART_PAD_B = 10  # x축 라벨

# ── 장벽 드래그 ──────────────────────────────────────
_BARRIER_EDGE_TOL = 8  # 장벽 가장자리 감지 허용 범위 (px)

# ── 입자 궤적 잔상 (config.json에서 로드) ──────────────
_MAX_TRAILS = cfg("tunneling", "max_trails", 30)
_TRAIL_SAMPLE = cfg("tunneling", "trail_sample", 3)
_TRAIL_DOT_R = cfg("tunneling", "trail_dot_radius", 2)


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
        w_lbl = font.render(f"{barrier_width}px", True, edge_clr)
        screen.blit(w_lbl, (BARRIER_X - w_lbl.get_width() // 2, SIM_TOP + SIM_H - 18))

    # 장벽 라벨
    label = font.render(t("tn_barrier"), True, BG)
    label_rot = pygame.transform.rotate(label, 90)
    screen.blit(label_rot, (bx - 2, SIM_TOP + SIM_H // 2 - label_rot.get_height() // 2))

    # 영역 라벨
    left_label = font.render(t("tn_classical"), True, OVERLAY_CLR)
    screen.blit(left_label, (SIM_LEFT + 10, SIM_TOP + 5))
    right_label = font.render(t("tn_tunneled"), True, OVERLAY_CLR)
    screen.blit(right_label, (BARRIER_X + 20, SIM_TOP + 5))


def _draw_trails(screen, trails, current_trail, current_result):
    """과거 입자 궤적 잔상 렌더링."""
    if not trails and not current_trail:
        return

    surf = pygame.Surface((SIM_W, SIM_H), pygame.SRCALPHA)
    n_trails = len(trails)

    # 과거 궤적 (오래될수록 투명)
    for i, (pts, result) in enumerate(trails):
        base_alpha = max(15, int(70 * (i + 1) / max(n_trails, 1)))
        clr = TUNNEL_FLASH if result else REFLECT_CLR
        rgba = (*clr[:3], base_alpha)
        for px, py in pts:
            sx, sy = px - SIM_LEFT, py - SIM_TOP
            if 0 <= sx < SIM_W and 0 <= sy < SIM_H:
                pygame.draw.circle(surf, rgba, (sx, sy), _TRAIL_DOT_R)

    # 현재 진행 중인 궤적
    if current_trail:
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
                pygame.draw.circle(surf, rgba, (sx, sy), _TRAIL_DOT_R)

    screen.blit(surf, (SIM_LEFT, SIM_TOP))


def _draw_particle(screen, p: QuantumParticle, font):
    """입자 렌더링."""
    cx, cy = int(p.x), int(p.y)
    time_ms = pygame.time.get_ticks()

    # 터널링/반사 플래시
    if p.flash_timer > 0:
        flash_r = int(PARTICLE_RADIUS + 20 * p.flash_timer)
        flash_clr = TUNNEL_FLASH if p.tunneled else REFLECT_CLR
        glow = pygame.Surface((flash_r * 2, flash_r * 2), pygame.SRCALPHA)
        alpha = int(120 * p.flash_timer)
        pygame.draw.circle(glow, (*flash_clr, alpha), (flash_r, flash_r), flash_r)
        screen.blit(glow, (cx - flash_r, cy - flash_r))

    # 입자 본체 — 터널링 성공 시 흰색, 평상시 파랑
    color = WHITE if (p.tunneled is True and p.flash_timer > 0) else PARTICLE_CLR
    pygame.draw.circle(screen, color, (cx, cy), PARTICLE_RADIUS)
    pygame.draw.circle(screen, TEXT_CLR, (cx, cy), PARTICLE_RADIUS, 1)

    # 중첩 |0⟩/|1⟩ 텍스트
    state_text = f"|{p.qubit_state(time_ms)}⟩"
    surf = font.render(state_text, True, WHITE)
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


def _draw_great_circle(screen, axis_fn, phi, el, color_front, color_back):
    """대원 그리기 — 전면/후면 색상 분리.

    Args:
        axis_fn: angle → (x, y, z) 매핑 함수.
    """
    pts = []
    for i in range(_CIRCLE_STEPS):
        a = 2 * math.pi * i / _CIRCLE_STEPS
        x3, y3, z3 = axis_fn(a)
        sx, sy, d = _project_bloch(x3, y3, z3, phi, el)
        pts.append((sx, sy, d))
    for i in range(_CIRCLE_STEPS):
        j = (i + 1) % _CIRCLE_STEPS
        behind = pts[i][2] > 0 and pts[j][2] > 0
        clr = color_back if behind else color_front
        pygame.draw.line(screen, clr, pts[i][:2], pts[j][:2], 1)


def _draw_bloch_sphere(screen, p: QuantumParticle, font, title_font, view_phi, view_el):
    """블로흐 구 시각화 (3D 회전 가능)."""
    time_ms = pygame.time.get_ticks()

    # 타이틀
    label = title_font.render(t("tn_bloch"), True, ACCENT)
    screen.blit(label, (BLOCH_CX - label.get_width() // 2, BLOCH_CY - BLOCH_R - 40))

    # 구 외곽 (실루엣)
    pygame.draw.circle(screen, BLOCH_RING, (BLOCH_CX, BLOCH_CY), BLOCH_R, 1)

    # 색상: 전면/후면
    dim = tuple(max(c // 3, 0) for c in BLOCH_RING)

    # 적도 (XY 평면, z=0)
    _draw_great_circle(screen, lambda a: (math.cos(a), math.sin(a), 0), view_phi, view_el, BLOCH_RING, dim)
    # XZ 경선 (y=0) — 상태 벡터가 위치하는 평면
    _draw_great_circle(screen, lambda a: (math.sin(a), 0, math.cos(a)), view_phi, view_el, BLOCH_RING, dim)
    # YZ 경선 (x=0)
    _draw_great_circle(screen, lambda a: (0, math.sin(a), math.cos(a)), view_phi, view_el, BLOCH_RING, dim)

    # Z축
    t0x, t0y, _ = _project_bloch(0, 0, 1.12, view_phi, view_el)
    b0x, b0y, _ = _project_bloch(0, 0, -1.12, view_phi, view_el)
    pygame.draw.line(screen, OVERLAY_CLR, (t0x, t0y), (b0x, b0y), 1)

    # |0⟩, |1⟩ 라벨
    lx0, ly0, _ = _project_bloch(0, 0, 1.22, view_phi, view_el)
    lx1, ly1, _ = _project_bloch(0, 0, -1.22, view_phi, view_el)
    z0 = font.render("|0⟩", True, TUNNEL_FLASH)
    z1 = font.render("|1⟩", True, REFLECT_CLR)
    screen.blit(z0, (lx0 + 4, ly0 - 8))
    screen.blit(z1, (lx1 + 4, ly1 - 4))

    # X축 라벨 (|+⟩)
    lxx, lxy, _ = _project_bloch(1.18, 0, 0, view_phi, view_el)
    xlab = font.render("|+⟩", True, OVERLAY_CLR)
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
    sl = font.render(state_label, True, TEXT_CLR)
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
        surf = font.render(line, True, color)
        screen.blit(surf, (stats_x, stats_y + i * 17))


# ── 수식 오버레이 레이아웃 ────────────────────────────
_FORMULA_X = BLOCH_CX - BLOCH_R  # 블로흐 구 좌측 정렬
_FORMULA_Y = 45
_FORMULA_W = BLOCH_R * 2  # 블로흐 구 직경과 동일
_FORMULA_H = 80


def _draw_formula_overlay(screen, font, barrier_width, tunnel_prob):
    """핵심 터널링 수식 오버레이."""
    fx, fy, fw, fh = _FORMULA_X, _FORMULA_Y, _FORMULA_W, _FORMULA_H

    # 반투명 배경
    bg_surf = pygame.Surface((fw, fh), pygame.SRCALPHA)
    bg_surf.fill((*BG[:3], 200))
    screen.blit(bg_surf, (fx, fy))
    pygame.draw.rect(screen, OVERLAY_CLR, (fx, fy, fw, fh), 1)

    # 타이틀
    title = font.render(t("tn_formula_title"), True, ACCENT)
    screen.blit(title, (fx + fw // 2 - title.get_width() // 2, fy + 3))

    # ① 투과 계수: T ≈ e^(−2κL)
    f1 = font.render("T ≈ e", True, BARRIER_CLR)
    screen.blit(f1, (fx + 8, fy + 20))
    # 지수 부분 (위 첨자 느낌으로 작은 오프셋)
    exp_text = font.render("(−2κL)", True, TEXT_CLR)
    screen.blit(exp_text, (fx + 8 + f1.get_width(), fy + 17))

    # ② 감쇠 상수: κ = √(2m(V−E)) / ℏ
    f2 = font.render("κ = √(2m(V−E)) / ℏ", True, BARRIER_CLR)
    screen.blit(f2, (fx + 8, fy + 37))

    # ③ 현재 시뮬레이션 값
    val_text = f"L={barrier_width}px  →  P={tunnel_prob * 100:.1f}%"
    val_surf = font.render(val_text, True, TUNNEL_FLASH)
    screen.blit(val_surf, (fx + 8, fy + 57))


def _draw_rate_chart(screen, font, trial_history, tunnel_prob):
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
    title = font.render(t("tn_rate_chart"), True, TEXT_CLR)
    screen.blit(title, (cx + cw - title.get_width(), _CHART_Y + 1))

    # y축 눈금선 + 라벨
    for frac in (1.0, 0.5, 0.0):
        gy = cy + int((1 - frac) * ch)
        pygame.draw.line(screen, OVERLAY_CLR, (cx, gy), (cx + cw, gy), 1)
    l_top = font.render("1.0", True, OVERLAY_CLR)
    l_bot = font.render("0", True, OVERLAY_CLR)
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
    tp_lbl = font.render(f"P={tp * 100:.0f}%", True, BARRIER_CLR)
    screen.blit(tp_lbl, (cx + cw - tp_lbl.get_width(), prob_y - 12))

    if not trial_history:
        msg = font.render(t("tn_no_data"), True, OVERLAY_CLR)
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
    rate_surf = font.render(f"{last_rate * 100:.1f}%", True, TUNNEL_FLASH)
    last_py = cy + int((1 - last_rate) * ch)
    screen.blit(rate_surf, (cx + cw + 2 - rate_surf.get_width() - 50, max(cy - 2, last_py - 10)))

    # 시행 횟수 (x축 우측 하단)
    n_surf = font.render(f"n={n}", True, OVERLAY_CLR)
    screen.blit(n_surf, (cx + cw - n_surf.get_width(), cy + ch + 1))


# ── 시뮬레이션 상태 번들 ──────────────────────────────


class _SimContext:
    """run_simulation 내부 상태를 하나로 묶는 컨테이너."""

    def __init__(self):
        _load_theme_colors()
        on_theme_change(_load_theme_colors)
        pygame.init()

        self.screen = pygame.display.set_mode((WIDTH + PANEL_W, HEIGHT))
        pygame.display.set_caption(t("game_title_tunneling"))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Consolas", 12)
        self.title_font = pygame.font.SysFont("Consolas", 16, bold=True)
        self.big_font = pygame.font.SysFont("Consolas", 18, bold=True)

        self.particle = QuantumParticle()
        self.paused = False

        # 블로흐 구 인터랙션
        self.bloch_phi = 0.0
        self.bloch_el = _BLOCH_EL_DEFAULT
        self.bloch_dragging = False
        self.bloch_drag_prev = (0, 0)

        # 장벽 드래그
        self.barrier_dragging = False
        self.barrier_hover = False

        # 입자 궤적 잔상
        self.trails: list[tuple[list[tuple[int, int]], bool]] = []
        self.current_trail: list[tuple[int, int]] = []
        self.trail_frame = 0
        self.prev_tunneled_state: bool | None = None

        # 슬라이더 패널
        self.panel = SliderPanel(WIDTH + 5, 40, PANEL_W - 10, "Parameters")
        self.sl_speed = self.panel.add(0.5, 5.0, 1.0, 0.5, "Speed Mult", ".1f")
        self.sl_barrier = self.panel.add(
            BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX, BARRIER_WIDTH_DEFAULT, 2, "Barrier W", ".0f"
        )
        self.sl_boost = self.panel.add(1.0, 5.0, TUNNEL_SPEED_BOOST, 0.5, "Tunnel Boost", ".1f")

        # 프리셋 HUD / 오버레이
        slider_map = {
            ("tunneling", "tunnel_prob_base"): self.sl_speed,
            ("tunneling", "barrier_width_default"): self.sl_barrier,
            ("tunneling", "tunnel_speed_boost"): self.sl_boost,
        }
        self.preset_hud = PresetHUD("tunneling", slider_map)
        self.help_overlay = HelpOverlay("tunneling")
        self.tutorial = TutorialOverlay("tunneling")
        self.glossary = GlossaryOverlay()

        # 사운드 / 리플레이
        self.snd = get_sound_manager()
        self.snd.init()
        self.recorder = ReplayRecorder("tunneling")

        # 물리 상태
        self.barrier_width = BARRIER_WIDTH_DEFAULT
        self.tunnel_prob = _calc_tunnel_prob(self.barrier_width)
        self.speed_mult = 1.0

        # 세션 통계
        self.start_time = time.monotonic()
        self.max_tunnel_barrier = 0
        self.barrier_configs_tried: set[int] = set()
        self.trial_history: deque[dict] = deque(maxlen=TRIAL_HISTORY_MAX)
        self.peak_rate = 0.0
        self.prev_attempts = 0

    def read_sliders(self):
        """슬라이더 값 → 물리 파라미터 동기화."""
        self.speed_mult = self.sl_speed.value
        self.barrier_width = int(self.sl_barrier.value)
        self.tunnel_prob = _calc_tunnel_prob(self.barrier_width)
        self.barrier_configs_tried.add(self.barrier_width)


# ── 이벤트 처리 ──────────────────────────────────────


def _handle_events(ctx: _SimContext) -> bool:
    """Pygame 이벤트 처리. False 반환 시 루프 종료."""
    running = True
    for event in pygame.event.get():
        if ctx.tutorial.handle_event(event):
            continue
        if ctx.glossary.handle_event(event):
            continue
        ctx.panel.handle_event(event)
        ctx.preset_hud.handle_event(event)
        ctx.help_overlay.handle_event(event)

        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            running = _handle_key(ctx, event.key, running)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            _handle_mouse_down(ctx, event.pos)
        elif event.type == pygame.MOUSEMOTION:
            _handle_mouse_motion(ctx, event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            ctx.barrier_dragging = False
            ctx.bloch_dragging = False
    return running


def _handle_key(ctx: _SimContext, key: int, running: bool) -> bool:
    """키보드 이벤트 분기."""
    ctx.snd.handle_key(key)
    if key == pygame.K_ESCAPE:
        if confirm_quit(ctx.screen, ctx.font):
            return False
    elif key == pygame.K_SPACE:
        ctx.paused = not ctx.paused
    elif key == pygame.K_r:
        ctx.particle = QuantumParticle()
        ctx.panel.reset_all()
        ctx.trails.clear()
        ctx.current_trail.clear()
        ctx.prev_tunneled_state = None
    elif key == pygame.K_UP:
        ctx.sl_speed.value = ctx.sl_speed.value + 0.5
    elif key == pygame.K_DOWN:
        ctx.sl_speed.value = ctx.sl_speed.value - 0.5
    elif key == pygame.K_RIGHT:
        ctx.sl_barrier.value = ctx.sl_barrier.value + 10
    elif key == pygame.K_LEFT:
        ctx.sl_barrier.value = ctx.sl_barrier.value - 10
    elif key == pygame.K_l:
        toggle_locale()
    elif key == pygame.K_LEFTBRACKET:
        cycle_sim_speed(-1)
    elif key == pygame.K_RIGHTBRACKET:
        cycle_sim_speed(1)
    return running


def _handle_mouse_down(ctx: _SimContext, pos: tuple[int, int]):
    """마우스 클릭 — 장벽 드래그 / 블로흐 구 드래그 / 입자 재발사."""
    mx, my = pos
    left_edge = BARRIER_X - ctx.barrier_width // 2
    right_edge = BARRIER_X + ctx.barrier_width // 2
    in_sim_y = SIM_TOP <= my <= SIM_TOP + SIM_H
    near_edge = in_sim_y and (abs(mx - left_edge) <= _BARRIER_EDGE_TOL or abs(mx - right_edge) <= _BARRIER_EDGE_TOL)
    if near_edge:
        ctx.barrier_dragging = True
    else:
        dx_b, dy_b = mx - BLOCH_CX, my - BLOCH_CY
        if dx_b * dx_b + dy_b * dy_b <= BLOCH_R * BLOCH_R:
            ctx.bloch_dragging = True
            ctx.bloch_drag_prev = (mx, my)
        else:
            ctx.particle.reset()


def _handle_mouse_motion(ctx: _SimContext, pos: tuple[int, int]):
    """마우스 이동 — 드래그 업데이트 / 호버 감지."""
    mx, my = pos
    if ctx.barrier_dragging:
        half_w = abs(mx - BARRIER_X)
        ctx.sl_barrier.value = max(BARRIER_WIDTH_MIN, min(BARRIER_WIDTH_MAX, half_w * 2))
    elif ctx.bloch_dragging:
        dx_m = mx - ctx.bloch_drag_prev[0]
        dy_m = my - ctx.bloch_drag_prev[1]
        ctx.bloch_phi += dx_m * _BLOCH_DRAG_SENSITIVITY
        ctx.bloch_el = max(_BLOCH_EL_MIN, min(_BLOCH_EL_MAX, ctx.bloch_el - dy_m * _BLOCH_DRAG_SENSITIVITY))
        ctx.bloch_drag_prev = (mx, my)
    else:
        left_edge = BARRIER_X - ctx.barrier_width // 2
        right_edge = BARRIER_X + ctx.barrier_width // 2
        in_sim_y = SIM_TOP <= my <= SIM_TOP + SIM_H
        ctx.barrier_hover = in_sim_y and (
            abs(mx - left_edge) <= _BARRIER_EDGE_TOL or abs(mx - right_edge) <= _BARRIER_EDGE_TOL
        )


# ── 물리 업데이트 ────────────────────────────────────


def _step_physics(ctx: _SimContext, dt: float):
    """물리 시뮬레이션 한 프레임 진행 + 시행 기록 + 궤적 + 사운드."""
    p = ctx.particle

    # 속도 배율 적용 (화면 표시용, 내부 상태는 보존)
    orig_vx = p.vx
    p.vx = orig_vx * ctx.speed_mult if orig_vx > 0 else orig_vx
    p.update(dt, ctx.barrier_width, ctx.tunnel_prob, ctx.sl_boost.value)
    p.vx = orig_vx

    # 시행별 기록
    if p.total_attempts > ctx.prev_attempts:
        ctx.prev_attempts = p.total_attempts
        trial_elapsed = time.monotonic() - ctx.start_time
        tunneled = p.tunneled is True
        ctx.trial_history.append(
            {
                "t": round(trial_elapsed, 2),
                "barrier": ctx.barrier_width,
                "prob": round(ctx.tunnel_prob, 4),
                "result": tunneled,
            }
        )
        cur_rate = p.tunnel_count / p.total_attempts
        if cur_rate > ctx.peak_rate:
            ctx.peak_rate = cur_rate
        if tunneled and ctx.barrier_width > ctx.max_tunnel_barrier:
            ctx.max_tunnel_barrier = ctx.barrier_width

    # 사운드
    if p.tunneled is True and p.flash_timer > 0.5:
        ctx.snd.play("tunnel_success")
    elif p.tunneled is False and p.flash_timer > 0.3:
        ctx.snd.play("tunnel_reflect")

    # 궤적 기록
    ctx.trail_frame += 1
    if ctx.trail_frame % _TRAIL_SAMPLE == 0:
        ctx.current_trail.append((int(p.x), int(p.y)))

    if ctx.prev_tunneled_state is not None and p.tunneled is None:
        if ctx.current_trail:
            ctx.trails.append((ctx.current_trail[:], ctx.prev_tunneled_state))
            if len(ctx.trails) > _MAX_TRAILS:
                ctx.trails.pop(0)
            ctx.current_trail.clear()
    ctx.prev_tunneled_state = p.tunneled

    ctx.preset_hud.update(dt)

    ctx.recorder.record_frame(
        {
            "x": round(p.x, 1),
            "tunneled": p.tunneled,
            "attempts": p.total_attempts,
            "tunnels": p.tunnel_count,
            "barrier_w": ctx.barrier_width,
            "rate": round(p.tunnel_count / max(p.total_attempts, 1), 3),
        }
    )


# ── 렌더링 ───────────────────────────────────────────


def _render_frame(ctx: _SimContext):
    """한 프레임 전체 렌더링."""
    ctx.screen.fill(BG)

    # 타이틀
    t_surf = ctx.big_font.render(t("game_title_tunneling"), True, ACCENT)
    ctx.screen.blit(t_surf, (WIDTH // 2 - t_surf.get_width() // 2, 12))

    _draw_sim_area(ctx.screen, ctx.font, ctx.barrier_width, ctx.barrier_hover, ctx.barrier_dragging)
    _draw_trails(ctx.screen, ctx.trails, ctx.current_trail, ctx.particle.tunneled)
    _draw_particle(ctx.screen, ctx.particle, ctx.font)
    _draw_formula_overlay(ctx.screen, ctx.font, ctx.barrier_width, ctx.tunnel_prob)
    _draw_bloch_sphere(ctx.screen, ctx.particle, ctx.font, ctx.title_font, ctx.bloch_phi, ctx.bloch_el)
    _draw_stats(ctx.screen, ctx.particle, ctx.font, ctx.tunnel_prob)
    _draw_rate_chart(ctx.screen, ctx.font, ctx.trial_history, ctx.tunnel_prob)
    ctx.panel.draw(ctx.screen, ctx.font)

    # 안내 텍스트
    hints = [
        t(
            "hint_speed_info",
            speed=ctx.speed_mult,
            sim_speed=speed_label(),
            width=ctx.barrier_width,
            prob=ctx.tunnel_prob * 100,
            pause_state=t("paused") if ctx.paused else t("running_state"),
        ),
        t("hint_click_launch"),
        t("hint_pause_reset") + f"  |  [/]: Sim Speed ({speed_label()})  |  G: {t('glossary_title')}",
    ]
    for i, h in enumerate(hints):
        surf = ctx.font.render(h, True, TEXT_CLR)
        ctx.screen.blit(surf, (SIM_LEFT, HEIGHT - 52 + i * 16))

    ctx.preset_hud.draw(ctx.screen, ctx.font)
    ctx.help_overlay.draw(ctx.screen, ctx.font)
    ctx.glossary.draw(ctx.screen, ctx.font)
    ctx.tutorial.draw(ctx.screen, ctx.font)


# ── 세션 데이터 빌드 ────────────────────────────────


def _build_session_data(ctx: _SimContext) -> dict:
    """finalize_session용 세션 요약 딕셔너리 생성."""
    p = ctx.particle
    rate = p.tunnel_count / max(p.total_attempts, 1)
    elapsed_time = time.monotonic() - ctx.start_time
    elapsed_min = elapsed_time / 60.0 if elapsed_time > 0 else 1.0
    avg_bw = (
        round(sum(tr["barrier"] for tr in ctx.trial_history) / len(ctx.trial_history), 1)
        if ctx.trial_history
        else ctx.barrier_width
    )
    return {
        "total_attempts": p.total_attempts,
        "tunnel_count": p.tunnel_count,
        "reflect_count": p.reflect_count,
        "tunnel_rate": round(rate, 3),
        "barrier_width": ctx.barrier_width,
        "tunnel_prob": round(ctx.tunnel_prob, 3),
        "elapsed_time": round(elapsed_time, 2),
        "max_tunnel_barrier": ctx.max_tunnel_barrier,
        "barrier_configs_tried": len(ctx.barrier_configs_tried),
        "peak_rate": round(ctx.peak_rate, 3),
        "avg_barrier_width": avg_bw,
        "trials_per_minute": round(p.total_attempts / elapsed_min, 1),
        "speed_mult": round(ctx.speed_mult, 1),
        "difficulty": ctx.preset_hud.current,
        "trial_history": list(ctx.trial_history),
    }


# ── 메인 시뮬레이션 ──────────────────────────────────


def run_simulation():
    """Pygame 시뮬레이션 실행."""
    ctx = _SimContext()

    if not choose_difficulty_or_quit(ctx.screen, ctx.font, ctx.preset_hud, _load_theme_colors):
        return

    running = True
    while running:
        raw_dt = ctx.clock.tick(FPS) / 1000.0
        dt = apply_speed(raw_dt)

        running = _handle_events(ctx)
        ctx.read_sliders()

        if not ctx.paused:
            _step_physics(ctx, dt)

        _render_frame(ctx)
        pygame.display.flip()

    finalize_session(
        "tunneling",
        _build_session_data(ctx),
        recorder=ctx.recorder,
        snd=ctx.snd,
        theme_callback=_load_theme_colors,
    )


def open_tunneling():
    """외부에서 호출하는 진입점."""
    run_simulation()
