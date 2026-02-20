"""조셉슨 접합(Josephson Junction) 시각화 시뮬레이션 (Pygame).

조셉슨 효과를 인터랙티브하게 시각화합니다:
  - 접합 다이어그램 (SC | 장벽 | SC)
  - 쿠퍼 쌍 터널링 애니메이션
  - 위상 차이 φ(t) 시계열 그래프
  - I-V 특성 곡선
  - 워시보드 퍼텐셜
"""

import math
import time

import pygame

from config_loader import cfg
from game_base import finalize_session
from glossary import GlossaryOverlay
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from physics.josephson_junction_physics import (
    BIAS_MAX,
    JosephsonJunction,
    iv_curve_point,
    washboard_potential,
)
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from sim_speed import apply_speed, cycle_sim_speed, speed_label
from sound_manager import get_sound_manager
from theme import get_pg_theme as _get_pg_theme_init
from theme import load_pg_colors, on_theme_change

_log = get_module_logger("josephson_junction")

# ── 화면 설정 ────────────────────────────────────────
WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
FPS = cfg("display", "fps", 60)

# ── 색상 (테마에서 동적 로드) ─────────────────────────
_pg = _get_pg_theme_init()
BG = _pg.BG
TEXT_CLR = _pg.TEXT
SUBTEXT_CLR = _pg.SUBTEXT
SC_COLOR = _pg.SC_COLOR
SC_GLOW = _pg.SC_GLOW
WHITE = _pg.WHITE
del _get_pg_theme_init

# 고유 색상
SC_BLOCK_COLOR = (137, 180, 250)   # 초전도체 블록 (파랑)
BARRIER_COLOR = (243, 139, 168)    # 장벽 (빨강)
PAIR_COLOR = (166, 227, 161)       # 쿠퍼 쌍 (녹색)
PHASE_COLOR = (250, 179, 135)      # 위상 곡선 (오렌지)
IV_COLOR = (203, 166, 247)         # I-V 곡선 (보라)
WASHBOARD_COLOR = (148, 226, 213)  # 워시보드 (시안)
ZERO_V_COLOR = (166, 227, 161)     # 제로 전압 표시 (녹색)
FINITE_V_COLOR = (243, 139, 168)   # 유한 전압 표시 (빨강)
BIAS_ARROW_COLOR = (250, 227, 135) # 바이어스 화살표 (노랑)

_COLOR_MAP = {
    "BG": "BG",
    "TEXT_CLR": "TEXT",
    "SUBTEXT_CLR": "SUBTEXT",
    "SC_COLOR": "SC_COLOR",
    "SC_GLOW": "SC_GLOW",
    "WHITE": "WHITE",
}


def _load_theme_colors():
    load_pg_colors(_COLOR_MAP, globals())


# ── 슬라이더 파라미터 ──────────────────────────────
SLIDER_X = 30
SLIDER_Y = 400
SLIDER_W = 200
SLIDER_H = 16

# 접합 다이어그램 위치
DIAG_X, DIAG_Y = 60, 50
DIAG_W, DIAG_H = 280, 160

# 터널링 애니메이션용 쿠퍼 쌍
_MAX_TUNNEL_PAIRS = 8


class _TunnelPair:
    """터널링 중인 쿠퍼 쌍 (애니메이션)."""

    def __init__(self, start_x: float, y: float, speed: float):
        self.x = start_x
        self.y = y
        self.speed = speed
        self.alive = True


def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(t("game_title_josephson"))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 13)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)
    small_font = pygame.font.SysFont("Consolas", 11)

    help_overlay = HelpOverlay("josephson_junction")
    glossary = GlossaryOverlay()
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("josephson_junction")

    jj = JosephsonJunction()
    tunnel_pairs: list[_TunnelPair] = []
    _spawn_timer = 0.0

    dragging_slider = False
    start_time = time.time()
    running = True

    while running:
        raw_dt = clock.tick(FPS) / 1000.0
        dt = apply_speed(raw_dt)

        # ── 이벤트 처리 ──────────────────────────────
        for event in pygame.event.get():
            help_overlay.handle_event(event)
            glossary.handle_event(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                snd.handle_key(event.key)
                if event.key == pygame.K_ESCAPE and not help_overlay.visible:
                    if confirm_quit(screen, font):
                        running = False
                elif event.key == pygame.K_LEFTBRACKET:
                    cycle_sim_speed(-1)
                elif event.key == pygame.K_RIGHTBRACKET:
                    cycle_sim_speed(1)
                elif event.key == pygame.K_UP:
                    jj.set_bias(jj.bias_current + 0.1)
                elif event.key == pygame.K_DOWN:
                    jj.set_bias(jj.bias_current - 0.1)
                elif event.key == pygame.K_r:
                    jj.reset()
                    tunnel_pairs.clear()
                elif event.key == pygame.K_l:
                    toggle_locale()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if SLIDER_X <= mx <= SLIDER_X + SLIDER_W and SLIDER_Y - 8 <= my <= SLIDER_Y + SLIDER_H + 8:
                    dragging_slider = True
            elif event.type == pygame.MOUSEBUTTONUP:
                dragging_slider = False

        if dragging_slider:
            mx, _ = pygame.mouse.get_pos()
            ratio = (mx - SLIDER_X) / SLIDER_W
            ratio = max(0.0, min(1.0, ratio))
            bias = -BIAS_MAX + ratio * (2 * BIAS_MAX)
            jj.set_bias(bias)

        # ── 물리 업데이트 ────────────────────────────
        jj.update(dt)

        # 터널링 쌍 생성/업데이트
        _spawn_timer += dt
        if not jj.is_zero_voltage and _spawn_timer > 0.08:
            _spawn_timer = 0.0
            if len(tunnel_pairs) < _MAX_TUNNEL_PAIRS:
                import random
                barrier_cx = DIAG_X + DIAG_W // 2
                y = DIAG_Y + 30 + random.randint(0, DIAG_H - 60)
                speed = 80 + abs(jj.voltage) * 40
                tunnel_pairs.append(_TunnelPair(DIAG_X + 40, y, speed))
        elif jj.is_zero_voltage and _spawn_timer > 0.2:
            _spawn_timer = 0.0
            if len(tunnel_pairs) < 4:
                import random
                y = DIAG_Y + 30 + random.randint(0, DIAG_H - 60)
                tunnel_pairs.append(_TunnelPair(DIAG_X + 40, y, 30))

        for tp in tunnel_pairs:
            tp.x += tp.speed * dt
            if tp.x > DIAG_X + DIAG_W - 20:
                tp.alive = False
        tunnel_pairs = [tp for tp in tunnel_pairs if tp.alive]

        # 리플레이 기록
        recorder.record_frame({
            "bias": round(jj.bias_current, 3),
            "phi": round(jj.phi, 3),
            "voltage": round(jj.voltage, 3),
            "supercurrent": round(jj.supercurrent, 3),
            "zero_v": jj.is_zero_voltage,
        })

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        title_surf = title_font.render(t("game_title_josephson"), True, SC_GLOW)
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 8))

        # 접합 다이어그램
        _draw_junction_diagram(screen, font, small_font, jj, tunnel_pairs)

        # 위상 시계열 그래프
        _draw_phase_graph(screen, small_font, jj)

        # I-V 곡선
        _draw_iv_curve(screen, small_font, jj)

        # 워시보드 퍼텐셜
        _draw_washboard(screen, small_font, jj)

        # 바이어스 슬라이더
        _draw_bias_slider(screen, font, small_font, jj)

        # 정보 패널
        _draw_info_panel(screen, font, small_font, jj)

        # 안내 텍스트
        hints = [
            t("jj_hint_line1"),
            t("jj_hint_line2", speed=speed_label()),
        ]
        for i, hint in enumerate(hints):
            surf = small_font.render(hint, True, SUBTEXT_CLR)
            screen.blit(surf, (12, HEIGHT - 36 + i * 16))

        glossary.draw(screen, font)
        help_overlay.draw(screen, font)
        pygame.display.flip()

    play_time = round(time.time() - start_time, 1)
    finalize_session(
        "josephson_junction",
        {"play_time": play_time, "final_bias": round(jj.bias_current, 3)},
        recorder=recorder,
        recorder_meta={"play_time": play_time},
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def _draw_junction_diagram(screen, font, small_font, jj, tunnel_pairs):
    """접합 다이어그램: SC | 장벽 | SC + 터널링 애니메이션."""
    x, y, w, h = DIAG_X, DIAG_Y, DIAG_W, DIAG_H
    barrier_w = 20
    barrier_x = x + w // 2 - barrier_w // 2

    # 좌측 초전도체
    pygame.draw.rect(screen, SC_BLOCK_COLOR, (x, y, barrier_x - x, h), border_radius=4)
    # 장벽
    pygame.draw.rect(screen, BARRIER_COLOR, (barrier_x, y, barrier_w, h))
    # 우측 초전도체
    right_x = barrier_x + barrier_w
    pygame.draw.rect(screen, SC_BLOCK_COLOR, (right_x, y, x + w - right_x, h), border_radius=4)

    # 라벨
    sc1 = small_font.render("SC₁", True, BG)
    screen.blit(sc1, (x + (barrier_x - x) // 2 - sc1.get_width() // 2, y + h + 4))
    bar = small_font.render(t("jj_barrier"), True, BARRIER_COLOR)
    screen.blit(bar, (barrier_x + barrier_w // 2 - bar.get_width() // 2, y + h + 4))
    sc2 = small_font.render("SC₂", True, BG)
    screen.blit(sc2, (right_x + (x + w - right_x) // 2 - sc2.get_width() // 2, y + h + 4))

    # 터널링 쿠퍼 쌍
    for tp in tunnel_pairs:
        alpha = 200 if barrier_x <= tp.x <= barrier_x + barrier_w else 255
        radius = 4
        glow = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*PAIR_COLOR, alpha // 2), (radius * 2, radius * 2), radius * 2)
        screen.blit(glow, (int(tp.x) - radius * 2, int(tp.y) - radius * 2))
        pygame.draw.circle(screen, PAIR_COLOR, (int(tp.x), int(tp.y)), radius)

    # 위상 차 표시
    state_color = ZERO_V_COLOR if jj.is_zero_voltage else FINITE_V_COLOR
    state_text = t("jj_zero_voltage") if jj.is_zero_voltage else t("jj_finite_voltage")
    state_surf = font.render(state_text, True, state_color)
    screen.blit(state_surf, (x + w // 2 - state_surf.get_width() // 2, y - 18))

    # 바이어스 전류 화살표
    if abs(jj.bias_current) > 0.05:
        arrow_y = y + h // 2
        arrow_len = min(50, abs(jj.bias_current) * 20)
        arrow_dir = 1 if jj.bias_current > 0 else -1
        start_x = x + w // 2 - arrow_dir * arrow_len
        end_x = x + w // 2 + arrow_dir * arrow_len
        pygame.draw.line(screen, BIAS_ARROW_COLOR, (start_x, arrow_y - 20), (end_x, arrow_y - 20), 2)
        # 화살표 머리
        pygame.draw.polygon(screen, BIAS_ARROW_COLOR, [
            (end_x, arrow_y - 20),
            (end_x - arrow_dir * 6, arrow_y - 25),
            (end_x - arrow_dir * 6, arrow_y - 15),
        ])


def _draw_phase_graph(screen, small_font, jj):
    """위상 φ(t) 시계열 그래프."""
    gx, gy, gw, gh = 370, 50, 260, 120

    pygame.draw.rect(screen, (30, 30, 46), (gx, gy, gw, gh), border_radius=4)
    pygame.draw.rect(screen, (69, 71, 90), (gx, gy, gw, gh), 1, border_radius=4)

    history = jj.phi_history
    if len(history) < 2:
        return

    # φ 범위 자동 조절
    phi_min = min(history)
    phi_max = max(history)
    phi_range = max(phi_max - phi_min, 0.1)

    points = []
    for i, phi in enumerate(history):
        x = gx + int(i / len(history) * gw)
        y = gy + gh - int((phi - phi_min) / phi_range * (gh - 10)) - 5
        points.append((x, max(gy + 2, min(gy + gh - 2, y))))

    pygame.draw.lines(screen, PHASE_COLOR, False, points, 2)

    title = small_font.render(t("jj_phase_graph"), True, PHASE_COLOR)
    screen.blit(title, (gx + gw // 2 - title.get_width() // 2, gy - 14))

    # 현재 φ 값
    phi_label = small_font.render(f"φ = {jj.phi:.2f} rad", True, TEXT_CLR)
    screen.blit(phi_label, (gx + gw - phi_label.get_width() - 4, gy + gh + 4))


def _draw_iv_curve(screen, small_font, jj):
    """I-V 특성 곡선."""
    gx, gy, gw, gh = 650, 50, 220, 120

    pygame.draw.rect(screen, (30, 30, 46), (gx, gy, gw, gh), border_radius=4)
    pygame.draw.rect(screen, (69, 71, 90), (gx, gy, gw, gh), 1, border_radius=4)

    cx = gx + gw // 2
    cy = gy + gh // 2

    # 축
    pygame.draw.line(screen, (69, 71, 90), (gx + 5, cy), (gx + gw - 5, cy), 1)
    pygame.draw.line(screen, (69, 71, 90), (cx, gy + 5), (cx, gy + gh - 5), 1)

    # I-V 곡선
    v_scale = gw / (2 * BIAS_MAX * jj.r_normal + 0.1)
    i_scale = gh / (2 * BIAS_MAX + 0.1)

    points = []
    for i in range(gw):
        bias = -BIAS_MAX + 2 * BIAS_MAX * i / gw
        v = iv_curve_point(bias, jj.ic, jj.r_normal)
        px = cx + int(v * v_scale)
        py = cy - int(bias * i_scale)
        px = max(gx + 2, min(gx + gw - 2, px))
        py = max(gy + 2, min(gy + gh - 2, py))
        points.append((px, py))

    if len(points) > 1:
        pygame.draw.lines(screen, IV_COLOR, False, points, 2)

    # 현재 점
    cur_v = jj.voltage
    cur_bias = jj.bias_current
    cpx = cx + int(cur_v * v_scale)
    cpy = cy - int(cur_bias * i_scale)
    cpx = max(gx + 4, min(gx + gw - 4, cpx))
    cpy = max(gy + 4, min(gy + gh - 4, cpy))
    state_color = ZERO_V_COLOR if jj.is_zero_voltage else FINITE_V_COLOR
    pygame.draw.circle(screen, state_color, (cpx, cpy), 5)

    title = small_font.render(t("jj_iv_curve"), True, IV_COLOR)
    screen.blit(title, (gx + gw // 2 - title.get_width() // 2, gy - 14))

    # 축 라벨
    v_label = small_font.render("V", True, SUBTEXT_CLR)
    screen.blit(v_label, (gx + gw - 12, cy + 2))
    i_label = small_font.render("I", True, SUBTEXT_CLR)
    screen.blit(i_label, (cx + 4, gy + 2))


def _draw_washboard(screen, small_font, jj):
    """워시보드 퍼텐셜."""
    gx, gy, gw, gh = 370, 200, 260, 120

    pygame.draw.rect(screen, (30, 30, 46), (gx, gy, gw, gh), border_radius=4)
    pygame.draw.rect(screen, (69, 71, 90), (gx, gy, gw, gh), 1, border_radius=4)

    # 퍼텐셜 곡선
    phi_range = 4 * math.pi
    points = []
    u_values = []
    for i in range(gw):
        phi = -phi_range / 2 + phi_range * i / gw
        u = washboard_potential(phi, jj.bias_current, jj.ic)
        u_values.append(u)

    if u_values:
        u_min = min(u_values)
        u_max = max(u_values)
        u_range = max(u_max - u_min, 0.1)

        for i, u in enumerate(u_values):
            x = gx + i
            y = gy + gh - int((u - u_min) / u_range * (gh - 10)) - 5
            points.append((x, max(gy + 2, min(gy + gh - 2, y))))

        if len(points) > 1:
            pygame.draw.lines(screen, WASHBOARD_COLOR, False, points, 2)

    # 현재 위상 위치 (주기적으로 맵핑)
    phi_norm = ((jj.phi + phi_range / 2) % phi_range)
    marker_x = gx + int(phi_norm / phi_range * gw)
    marker_u = washboard_potential(jj.phi, jj.bias_current, jj.ic)
    if u_values:
        marker_y = gy + gh - int((marker_u - u_min) / u_range * (gh - 10)) - 5
        marker_y = max(gy + 4, min(gy + gh - 4, marker_y))
        marker_x = max(gx + 4, min(gx + gw - 4, marker_x))
        state_color = ZERO_V_COLOR if jj.is_zero_voltage else FINITE_V_COLOR
        pygame.draw.circle(screen, state_color, (marker_x, marker_y), 5)

    title = small_font.render(t("jj_washboard"), True, WASHBOARD_COLOR)
    screen.blit(title, (gx + gw // 2 - title.get_width() // 2, gy - 14))


def _draw_bias_slider(screen, font, small_font, jj):
    """바이어스 전류 슬라이더."""
    x, y, w, h = SLIDER_X, SLIDER_Y, SLIDER_W, SLIDER_H

    # 트랙
    pygame.draw.rect(screen, (69, 71, 90), (x, y, w, h), border_radius=4)

    # Ic 마커
    ic_left = x + int((jj.ic + BIAS_MAX) / (2 * BIAS_MAX) * w)
    ic_right = x + int((-jj.ic + BIAS_MAX) / (2 * BIAS_MAX) * w)
    pygame.draw.line(screen, ZERO_V_COLOR, (ic_left, y - 3), (ic_left, y + h + 3), 1)
    pygame.draw.line(screen, ZERO_V_COLOR, (ic_right, y - 3), (ic_right, y + h + 3), 1)

    # 초전류 영역 하이라이트
    sc_left = min(ic_right, ic_left)
    sc_right = max(ic_right, ic_left)
    sc_surf = pygame.Surface((sc_right - sc_left, h), pygame.SRCALPHA)
    sc_surf.fill((*ZERO_V_COLOR, 30))
    screen.blit(sc_surf, (sc_left, y))

    # 마커
    ratio = (jj.bias_current + BIAS_MAX) / (2 * BIAS_MAX)
    marker_x = x + int(ratio * w)
    state_color = ZERO_V_COLOR if jj.is_zero_voltage else FINITE_V_COLOR
    pygame.draw.circle(screen, state_color, (marker_x, y + h // 2), 8)
    pygame.draw.circle(screen, WHITE, (marker_x, y + h // 2), 8, 2)

    # 라벨
    bias_text = font.render(f"I_bias = {jj.bias_current:.2f}", True, state_color)
    screen.blit(bias_text, (x + w + 12, y - 2))
    title = small_font.render(t("jj_bias_label"), True, TEXT_CLR)
    screen.blit(title, (x, y - 18))
    left_label = small_font.render(f"-{BIAS_MAX:.1f}", True, SUBTEXT_CLR)
    right_label = small_font.render(f"+{BIAS_MAX:.1f}", True, SUBTEXT_CLR)
    screen.blit(left_label, (x, y + h + 4))
    screen.blit(right_label, (x + w - right_label.get_width(), y + h + 4))
    ic_label = small_font.render(f"±Ic={jj.ic:.1f}", True, ZERO_V_COLOR)
    screen.blit(ic_label, (x + w + 12, y + 16))


def _draw_info_panel(screen, font, small_font, jj):
    """우측 하단 정보 패널."""
    px = 650
    py = 200

    labels = [
        (t("jj_info_bias"), f"{jj.bias_current:.2f}"),
        (t("jj_info_ic"), f"{jj.ic:.2f}"),
        (t("jj_info_supercurrent"), f"Is = {jj.supercurrent:.3f}"),
        (t("jj_info_voltage"), f"V = {jj.voltage:.3f}"),
        (t("jj_info_phase"), f"φ = {jj.phi:.2f} rad"),
        (t("jj_info_power"), f"P = {jj.power:.3f}"),
        (t("jj_info_state"), t("jj_zero_voltage") if jj.is_zero_voltage else t("jj_finite_voltage")),
    ]

    for label, value in labels:
        surf = small_font.render(f"{label}: {value}", True, TEXT_CLR)
        screen.blit(surf, (px, py))
        py += 18

    # DC/AC 효과 설명
    py += 6
    if jj.is_zero_voltage:
        desc = t("jj_dc_desc")
    else:
        desc = t("jj_ac_desc")
    desc_surf = small_font.render(desc, True, SUBTEXT_CLR)
    screen.blit(desc_surf, (px, py))


def open_josephson_junction():
    """외부에서 호출하는 진입점."""
    run_simulation()
