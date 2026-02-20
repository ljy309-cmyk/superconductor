"""양자 중첩 및 터널링 시뮬레이션 (Pygame).

- 블로흐 구: 큐비트가 |0⟩ / |1⟩ 사이를 확률적으로 점멸 (중첩 시각화)
- 터널링: 입자가 장벽과 충돌할 때 10 % 확률로 장벽 반대편으로 이동
"""

import math
import time

import pygame

from config_loader import cfg
from game_base import choose_difficulty_or_quit, finalize_session
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


# ── 블로흐 구 레이아웃 ────────────────────────────────
BLOCH_CX, BLOCH_CY = 730, 280
BLOCH_R = 110
_BLOCH_EL_DEFAULT = 0.25  # 기본 기울기 (rad) — 약 14°
_BLOCH_EL_MIN, _BLOCH_EL_MAX = -1.0, 1.0
_BLOCH_DRAG_SENSITIVITY = 0.008  # 마우스 픽셀 → 라디안
_CIRCLE_STEPS = 48  # 대원 그리기 해상도

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


# ── 메인 시뮬레이션 ──────────────────────────────────


def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH + PANEL_W, HEIGHT))
    pygame.display.set_caption(t("game_title_tunneling"))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 12)
    title_font = pygame.font.SysFont("Consolas", 16, bold=True)
    big_font = pygame.font.SysFont("Consolas", 18, bold=True)

    particle = QuantumParticle()
    paused = False

    # ── 블로흐 구 인터랙션 ──
    bloch_phi = 0.0
    bloch_el = _BLOCH_EL_DEFAULT
    bloch_dragging = False
    bloch_drag_prev = (0, 0)

    # ── 장벽 드래그 ──
    barrier_dragging = False
    barrier_hover = False

    # ── 슬라이더 패널 ─────────────────────────────────
    panel = SliderPanel(WIDTH + 5, 40, PANEL_W - 10, "Parameters")
    sl_speed = panel.add(0.5, 5.0, 1.0, 0.5, "Speed Mult", ".1f")
    sl_barrier = panel.add(BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX, BARRIER_WIDTH_DEFAULT, 2, "Barrier W", ".0f")
    sl_boost = panel.add(1.0, 5.0, TUNNEL_SPEED_BOOST, 0.5, "Tunnel Boost", ".1f")

    # ── 프리셋 HUD ──
    slider_map = {
        ("tunneling", "tunnel_prob_base"): sl_speed,
        ("tunneling", "barrier_width_default"): sl_barrier,
        ("tunneling", "tunnel_speed_boost"): sl_boost,
    }
    preset_hud = PresetHUD("tunneling", slider_map)
    help_overlay = HelpOverlay("tunneling")

    # ── 사운드 ──
    snd = get_sound_manager()
    snd.init()

    # ── 리플레이 ──
    recorder = ReplayRecorder("tunneling")

    barrier_width = BARRIER_WIDTH_DEFAULT
    tunnel_prob = _calc_tunnel_prob(barrier_width)

    # ── 세션 통계 추적 ──
    start_time = time.monotonic()
    max_tunnel_barrier = 0
    barrier_configs_tried: set[int] = set()
    trial_history: list[dict] = []
    peak_rate = 0.0
    prev_attempts = 0

    # ── 시작 시 난이도 선택 ──
    if not choose_difficulty_or_quit(screen, font, preset_hud, _load_theme_colors):
        return

    running = True
    while running:
        raw_dt = clock.tick(FPS) / 1000.0
        dt = apply_speed(raw_dt)

        # ── 이벤트 ───────────────────────────────────
        for event in pygame.event.get():
            panel.handle_event(event)
            preset_hud.handle_event(event)
            help_overlay.handle_event(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                snd.handle_key(event.key)
                if event.key == pygame.K_ESCAPE:
                    if confirm_quit(screen, font):
                        running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    particle = QuantumParticle()
                    panel.reset_all()
                elif event.key == pygame.K_UP:
                    sl_speed.value = sl_speed.value + 0.5
                elif event.key == pygame.K_DOWN:
                    sl_speed.value = sl_speed.value - 0.5
                elif event.key == pygame.K_RIGHT:
                    sl_barrier.value = sl_barrier.value + 10
                elif event.key == pygame.K_LEFT:
                    sl_barrier.value = sl_barrier.value - 10
                elif event.key == pygame.K_l:
                    toggle_locale()
                elif event.key == pygame.K_LEFTBRACKET:
                    cycle_sim_speed(-1)
                elif event.key == pygame.K_RIGHTBRACKET:
                    cycle_sim_speed(1)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                # 장벽 가장자리 드래그 감지
                left_edge = BARRIER_X - barrier_width // 2
                right_edge = BARRIER_X + barrier_width // 2
                in_sim_y = SIM_TOP <= my <= SIM_TOP + SIM_H
                near_edge = in_sim_y and (
                    abs(mx - left_edge) <= _BARRIER_EDGE_TOL or abs(mx - right_edge) <= _BARRIER_EDGE_TOL
                )
                if near_edge:
                    barrier_dragging = True
                else:
                    dx_b, dy_b = mx - BLOCH_CX, my - BLOCH_CY
                    if dx_b * dx_b + dy_b * dy_b <= BLOCH_R * BLOCH_R:
                        bloch_dragging = True
                        bloch_drag_prev = (mx, my)
                    else:
                        particle.reset()
            elif event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                if barrier_dragging:
                    half_w = abs(mx - BARRIER_X)
                    new_w = max(BARRIER_WIDTH_MIN, min(BARRIER_WIDTH_MAX, half_w * 2))
                    sl_barrier.value = new_w
                elif bloch_dragging:
                    dx_m = mx - bloch_drag_prev[0]
                    dy_m = my - bloch_drag_prev[1]
                    bloch_phi += dx_m * _BLOCH_DRAG_SENSITIVITY
                    bloch_el = max(_BLOCH_EL_MIN, min(_BLOCH_EL_MAX, bloch_el - dy_m * _BLOCH_DRAG_SENSITIVITY))
                    bloch_drag_prev = (mx, my)
                else:
                    # 호버 감지
                    left_edge = BARRIER_X - barrier_width // 2
                    right_edge = BARRIER_X + barrier_width // 2
                    in_sim_y = SIM_TOP <= my <= SIM_TOP + SIM_H
                    barrier_hover = in_sim_y and (
                        abs(mx - left_edge) <= _BARRIER_EDGE_TOL or abs(mx - right_edge) <= _BARRIER_EDGE_TOL
                    )
            elif event.type == pygame.MOUSEBUTTONUP:
                barrier_dragging = False
                bloch_dragging = False

        # ── 슬라이더 값 읽기 ─────────────────────────
        speed_mult = sl_speed.value
        barrier_width = int(sl_barrier.value)
        tunnel_prob = _calc_tunnel_prob(barrier_width)
        barrier_configs_tried.add(barrier_width)

        # ── 물리 업데이트 ────────────────────────────
        if not paused:
            orig_vx = particle.vx
            particle.vx = orig_vx * speed_mult if orig_vx > 0 else orig_vx
            particle.update(dt, barrier_width, tunnel_prob, sl_boost.value)
            particle.vx = orig_vx  # 속도 배율은 화면용, 내부 상태 보존

            # ── 시행별 기록 ──
            if particle.total_attempts > prev_attempts:
                prev_attempts = particle.total_attempts
                trial_elapsed = time.monotonic() - start_time
                tunneled = particle.tunneled is True
                trial_history.append(
                    {
                        "t": round(trial_elapsed, 2),
                        "barrier": barrier_width,
                        "prob": round(tunnel_prob, 4),
                        "result": tunneled,
                    }
                )
                cur_rate = particle.tunnel_count / particle.total_attempts
                if cur_rate > peak_rate:
                    peak_rate = cur_rate
                if tunneled and barrier_width > max_tunnel_barrier:
                    max_tunnel_barrier = barrier_width

            # ── 사운드 ──
            if particle.tunneled is True and particle.flash_timer > 0.5:
                snd.play("tunnel_success")
            elif particle.tunneled is False and particle.flash_timer > 0.3:
                snd.play("tunnel_reflect")

            preset_hud.update(dt)

            recorder.record_frame(
                {
                    "x": round(particle.x, 1),
                    "tunneled": particle.tunneled,
                    "attempts": particle.total_attempts,
                    "tunnels": particle.tunnel_count,
                    "barrier_w": barrier_width,
                    "rate": round(particle.tunnel_count / max(particle.total_attempts, 1), 3),
                }
            )

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        t_surf = big_font.render(t("game_title_tunneling"), True, ACCENT)
        screen.blit(t_surf, (WIDTH // 2 - t_surf.get_width() // 2, 12))

        # 시뮬레이션 영역
        _draw_sim_area(screen, font, barrier_width, barrier_hover, barrier_dragging)

        # 입자
        _draw_particle(screen, particle, font)

        # 블로흐 구
        _draw_bloch_sphere(screen, particle, font, title_font, bloch_phi, bloch_el)

        # 통계
        _draw_stats(screen, particle, font, tunnel_prob)

        # 실시간 확률 차트
        _draw_rate_chart(screen, font, trial_history, tunnel_prob)

        # 슬라이더 패널 그리기
        panel.draw(screen, font)

        # 안내
        hints = [
            t(
                "hint_speed_info",
                speed=speed_mult,
                sim_speed=speed_label(),
                width=barrier_width,
                prob=tunnel_prob * 100,
                pause_state=t("paused") if paused else t("running_state"),
            ),
            t("hint_click_launch"),
            t("hint_pause_reset") + f"  |  [/]: Sim Speed ({speed_label()})",
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (SIM_LEFT, HEIGHT - 52 + i * 16))

        preset_hud.draw(screen, font)
        help_overlay.draw(screen, font)

        pygame.display.flip()

    rate = particle.tunnel_count / max(particle.total_attempts, 1)
    elapsed_time = time.monotonic() - start_time
    elapsed_min = elapsed_time / 60.0 if elapsed_time > 0 else 1.0
    avg_bw = round(sum(t["barrier"] for t in trial_history) / len(trial_history), 1) if trial_history else barrier_width
    finalize_session(
        "tunneling",
        {
            "total_attempts": particle.total_attempts,
            "tunnel_count": particle.tunnel_count,
            "reflect_count": particle.reflect_count,
            "tunnel_rate": round(rate, 3),
            "barrier_width": barrier_width,
            "tunnel_prob": round(tunnel_prob, 3),
            "elapsed_time": round(elapsed_time, 2),
            "max_tunnel_barrier": max_tunnel_barrier,
            "barrier_configs_tried": len(barrier_configs_tried),
            "peak_rate": round(peak_rate, 3),
            "avg_barrier_width": avg_bw,
            "trials_per_minute": round(particle.total_attempts / elapsed_min, 1),
            "speed_mult": round(speed_mult, 1),
            "difficulty": preset_hud.current,
            "trial_history": trial_history,
        },
        recorder=recorder,
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def open_tunneling():
    """외부에서 호출하는 진입점."""
    run_simulation()
