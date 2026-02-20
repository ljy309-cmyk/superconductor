"""쿠퍼 쌍(Cooper Pair) 시각화 시뮬레이션 (Pygame).

BCS 이론의 핵심 개념을 인터랙티브하게 시각화합니다:
  - 격자 이온의 열진동 (포논 매개)
  - 전자-전자 간 쿠퍼 쌍 형성/해체
  - 온도에 따른 에너지 갭(Δ) 그래프
  - 초전도 상전이 (Tc 기준)
"""

import math
import time

import pygame

from config_loader import cfg
from font_helper import get_font
from game_base import finalize_session
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from physics.cooper_pair_physics import (
    GAP_DELTA_MAX,
    TC_KELVIN,
    TEMP_MAX,
    TEMP_MIN,
    LatticeSimulation,
    cooper_pair_density,
    energy_gap,
    resistance_factor,
)
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from sim_speed import apply_speed, cycle_sim_speed, speed_label
from sound_manager import get_sound_manager
from theme import get_pg_theme as _get_pg_theme_init
from theme import load_pg_colors, on_theme_change

_log = get_module_logger("cooper_pair")

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
ION_COLOR = (116, 199, 236)     # 격자 이온 (파랑)
ELECTRON_COLOR = (250, 179, 135)  # 자유 전자 (오렌지)
PAIR_COLOR = (166, 227, 161)      # 쿠퍼 쌍 전자 (녹색)
PAIR_LINK_COLOR = (166, 227, 161, 100)  # 쌍 연결선
PHONON_COLOR = (203, 166, 247)    # 포논 파동 (보라)
GAP_COLOR = (137, 180, 250)       # 에너지 갭 (파랑)
RESIST_COLOR = (243, 139, 168)    # 저항 (빨강)
TEMP_MARKER_SC = (166, 227, 161)  # 초전도 마커 (녹색)
TEMP_MARKER_NORM = (243, 139, 168)  # 정상 상태 마커 (빨강)

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


# ── 온도 슬라이더 파라미터 ──────────────────────────
SLIDER_X = 660
SLIDER_Y = 80
SLIDER_H = 300
SLIDER_W = 30


def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(t("game_title_cooper_pair"))
    clock = pygame.time.Clock()
    font = get_font(13)
    title_font = get_font(18, bold=True)
    small_font = get_font(11)

    help_overlay = HelpOverlay("cooper_pair")
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("cooper_pair")

    sim = LatticeSimulation(
        cols=10, rows=6,
        width=500, height=300,
        offset_x=80, offset_y=120,
    )

    dragging_slider = False
    start_time = time.time()
    running = True

    while running:
        raw_dt = clock.tick(FPS) / 1000.0
        dt = apply_speed(raw_dt)

        # ── 이벤트 처리 ──────────────────────────────
        for event in pygame.event.get():
            help_overlay.handle_event(event)
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
                    sim.set_temperature(sim.temperature - 5)
                elif event.key == pygame.K_DOWN:
                    sim.set_temperature(sim.temperature + 5)
                elif event.key == pygame.K_l:
                    toggle_locale()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if SLIDER_X <= mx <= SLIDER_X + SLIDER_W and SLIDER_Y <= my <= SLIDER_Y + SLIDER_H:
                    dragging_slider = True
            elif event.type == pygame.MOUSEBUTTONUP:
                dragging_slider = False

        if dragging_slider:
            _, my = pygame.mouse.get_pos()
            ratio = (my - SLIDER_Y) / SLIDER_H
            ratio = max(0.0, min(1.0, ratio))
            # 위 = 고온, 아래 = 저온 (직관적)
            temp = TEMP_MAX - ratio * (TEMP_MAX - TEMP_MIN)
            sim.set_temperature(temp)

        # ── 물리 업데이트 ────────────────────────────
        sim.update(dt)

        # 리플레이 기록
        recorder.record_frame({
            "temp": round(sim.temperature, 1),
            "gap": round(sim.gap, 3),
            "pairs": sim.pair_count,
            "sc": sim.is_superconducting,
        })

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        title_surf = title_font.render(t("game_title_cooper_pair"), True, SC_GLOW)
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2 - 60, 12))

        # 격자 이온 그리기
        for ion in sim.ions:
            pygame.draw.circle(screen, ION_COLOR, (int(ion.x), int(ion.y)), 6)
            # 포논 파동 시각화 (진동 중이면)
            amp = abs(ion.x - ion.eq_x) + abs(ion.y - ion.eq_y)
            if amp > 1.0:
                pygame.draw.circle(screen, PHONON_COLOR, (int(ion.x), int(ion.y)), int(6 + amp), 1)

        # 쿠퍼 쌍 연결선
        drawn_pairs = set()
        for e in sim.electrons:
            if e.paired and e.partner and id(e) not in drawn_pairs:
                drawn_pairs.add(id(e))
                drawn_pairs.add(id(e.partner))
                pygame.draw.line(
                    screen, PAIR_COLOR,
                    (int(e.x), int(e.y)),
                    (int(e.partner.x), int(e.partner.y)),
                    2,
                )

        # 전자 그리기
        for e in sim.electrons:
            color = PAIR_COLOR if e.paired else ELECTRON_COLOR
            radius = 5 if e.paired else 4
            pygame.draw.circle(screen, color, (int(e.x), int(e.y)), radius)
            if e.paired:
                # 쿠퍼 쌍 글로우
                glow = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*PAIR_COLOR, 50), (radius * 2, radius * 2), radius * 2)
                screen.blit(glow, (int(e.x) - radius * 2, int(e.y) - radius * 2))

        # ── 온도 슬라이더 ────────────────────────────
        _draw_temp_slider(screen, font, small_font, sim.temperature)

        # ── 우측 패널: 정보 표시 ─────────────────────
        _draw_info_panel(screen, font, small_font, sim)

        # ── 하단: 에너지 갭 그래프 ───────────────────
        _draw_gap_graph(screen, small_font, sim.temperature)

        # ── 상태 표시 ────────────────────────────────
        state_text = t("cp_state_sc") if sim.is_superconducting else t("cp_state_normal")
        state_color = TEMP_MARKER_SC if sim.is_superconducting else TEMP_MARKER_NORM
        state_surf = font.render(state_text, True, state_color)
        screen.blit(state_surf, (80, 440))

        # 안내 텍스트
        hints = [
            t("cp_hint_line1"),
            t("cp_hint_line2", speed=speed_label()),
        ]
        for i, hint in enumerate(hints):
            surf = small_font.render(hint, True, SUBTEXT_CLR)
            screen.blit(surf, (12, HEIGHT - 36 + i * 16))

        help_overlay.draw(screen, font)
        pygame.display.flip()

    play_time = round(time.time() - start_time, 1)
    finalize_session(
        "cooper_pair",
        {
            "play_time": play_time,
            "final_temp": round(sim.temperature, 1),
            "max_pairs": sim.pair_count,
        },
        recorder=recorder,
        recorder_meta={"play_time": play_time},
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def _draw_temp_slider(screen, font, small_font, temp):
    """온도 슬라이더 렌더링."""
    # 배경 트랙
    pygame.draw.rect(screen, (69, 71, 90), (SLIDER_X, SLIDER_Y, SLIDER_W, SLIDER_H), border_radius=4)

    # Tc 라인
    tc_ratio = 1.0 - (TC_KELVIN - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)
    tc_y = int(SLIDER_Y + tc_ratio * SLIDER_H)
    pygame.draw.line(screen, RESIST_COLOR, (SLIDER_X - 5, tc_y), (SLIDER_X + SLIDER_W + 5, tc_y), 2)
    tc_label = small_font.render(f"Tc={TC_KELVIN:.0f}K", True, RESIST_COLOR)
    screen.blit(tc_label, (SLIDER_X + SLIDER_W + 8, tc_y - 6))

    # 초전도 영역 하이라이트
    sc_rect = pygame.Rect(SLIDER_X + 2, tc_y, SLIDER_W - 4, SLIDER_Y + SLIDER_H - tc_y)
    sc_surf = pygame.Surface((sc_rect.width, sc_rect.height), pygame.SRCALPHA)
    sc_surf.fill((*TEMP_MARKER_SC, 30))
    screen.blit(sc_surf, sc_rect.topleft)

    # 현재 온도 마커
    ratio = 1.0 - (temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)
    marker_y = int(SLIDER_Y + ratio * SLIDER_H)
    marker_color = TEMP_MARKER_SC if temp < TC_KELVIN else TEMP_MARKER_NORM
    pygame.draw.circle(screen, marker_color, (SLIDER_X + SLIDER_W // 2, marker_y), 8)
    pygame.draw.circle(screen, WHITE, (SLIDER_X + SLIDER_W // 2, marker_y), 8, 2)

    # 온도 텍스트
    temp_text = font.render(f"{temp:.0f} K", True, marker_color)
    screen.blit(temp_text, (SLIDER_X - temp_text.get_width() - 8, marker_y - 7))

    # 라벨
    top_label = small_font.render(f"{TEMP_MAX:.0f}K", True, SUBTEXT_CLR)
    bot_label = small_font.render(f"{TEMP_MIN:.0f}K", True, SUBTEXT_CLR)
    screen.blit(top_label, (SLIDER_X + SLIDER_W // 2 - top_label.get_width() // 2, SLIDER_Y - 16))
    screen.blit(bot_label, (SLIDER_X + SLIDER_W // 2 - bot_label.get_width() // 2, SLIDER_Y + SLIDER_H + 4))

    title = small_font.render(t("cp_temp_label"), True, TEXT_CLR)
    screen.blit(title, (SLIDER_X + SLIDER_W // 2 - title.get_width() // 2, SLIDER_Y - 30))


def _draw_info_panel(screen, font, small_font, sim):
    """우측 정보 패널."""
    px = 720
    py = 80

    labels = [
        (t("cp_info_temp"), f"{sim.temperature:.0f} K ({sim.temperature - 273.15:.0f} °C)"),
        (t("cp_info_tc"), f"{TC_KELVIN:.0f} K"),
        (t("cp_info_gap"), f"Δ = {sim.gap:.3f}"),
        (t("cp_info_density"), f"{sim.pair_density:.1%}"),
        (t("cp_info_pairs"), f"{sim.pair_count}"),
        (t("cp_info_resist"), t("cp_zero") if sim.is_superconducting else t("cp_normal_r")),
    ]

    for label, value in labels:
        surf = small_font.render(f"{label}: {value}", True, TEXT_CLR)
        screen.blit(surf, (px, py))
        py += 18


def _draw_gap_graph(screen, small_font, current_temp):
    """하단 에너지 갭 그래프."""
    gx, gy, gw, gh = 80, 470, 500, 100

    # 배경
    pygame.draw.rect(screen, (30, 30, 46), (gx, gy, gw, gh), border_radius=4)
    pygame.draw.rect(screen, (69, 71, 90), (gx, gy, gw, gh), 1, border_radius=4)

    # 갭 곡선 Δ(T)
    points = []
    for i in range(gw):
        temp = TEMP_MIN + (TEMP_MAX - TEMP_MIN) * i / gw
        gap = energy_gap(temp)
        y = gy + gh - (gap / GAP_DELTA_MAX) * (gh - 10) - 5
        points.append((gx + i, int(y)))

    if len(points) > 1:
        pygame.draw.lines(screen, GAP_COLOR, False, points, 2)

    # 현재 온도 마커
    tx = gx + int((current_temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN) * gw)
    cur_gap = energy_gap(current_temp)
    ty = gy + gh - (cur_gap / GAP_DELTA_MAX) * (gh - 10) - 5
    marker_color = TEMP_MARKER_SC if current_temp < TC_KELVIN else TEMP_MARKER_NORM
    pygame.draw.circle(screen, marker_color, (tx, int(ty)), 5)

    # Tc 수직선
    tc_x = gx + int((TC_KELVIN - TEMP_MIN) / (TEMP_MAX - TEMP_MIN) * gw)
    pygame.draw.line(screen, RESIST_COLOR, (tc_x, gy), (tc_x, gy + gh), 1)

    # 축 라벨
    title = small_font.render(t("cp_graph_title"), True, GAP_COLOR)
    screen.blit(title, (gx + gw // 2 - title.get_width() // 2, gy - 14))
    x_label = small_font.render(f"T (K): {TEMP_MIN:.0f} — {TEMP_MAX:.0f}", True, SUBTEXT_CLR)
    screen.blit(x_label, (gx, gy + gh + 4))
    tc_text = small_font.render(f"Tc", True, RESIST_COLOR)
    screen.blit(tc_text, (tc_x - 6, gy + gh + 4))


def open_cooper_pair():
    """외부에서 호출하는 진입점."""
    run_simulation()
