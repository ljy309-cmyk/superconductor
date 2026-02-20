"""SCADA 보안 시나리오 — MITM 공격 + BB84 양자 방어 (Pygame).

- SCADA 네트워크 토폴로지 시각화 (센서 → 컨트롤러 → HMI)
- MITM 공격: 센서값 조작 → 표시 온도 vs 실제 온도 분리
- BB84 QBER 기반 공격 탐지 → 양자 인증 채널 구축 → 공격자 차단
- 4 위상 시나리오: NORMAL → ATTACK → DETECTED → PROTECTED
"""

import math

import pygame

from config_loader import cfg
from font_helper import get_font
from game_base import finalize_session
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from security.scada_security_engine import (
    CRITICAL_TEMP,
    PHASE_ATTACK,
    PHASE_DETECTED,
    PHASE_NAMES,
    PHASE_NORMAL,
    PHASE_PROTECTED,
    QBER_DETECT_THRESHOLD,
    TARGET_TEMP,
    ScadaSecurityState,
    reset_scenario,
    trigger_attack,
    trigger_defense,
    update_scenario,
)
from sound_manager import get_sound_manager
from theme import load_pg_colors, on_theme_change
from tutorial import TutorialOverlay

_log = get_module_logger("scada_security")

# ── 화면 설정 ────────────────────────────────────────
WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
FPS = cfg("display", "fps", 60)

# ── 색상 (테마에서 동적 로드) ─────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
SUBTEXT_CLR = (88, 91, 112)
ACCENT = (249, 226, 175)
GREEN = (166, 227, 161)
RED = (243, 139, 168)
BLUE = (137, 180, 250)
MAUVE = (203, 166, 247)
PEACH = (250, 179, 135)
YELLOW = (249, 226, 175)
OVERLAY = (69, 71, 90)
PANEL_BG = (24, 24, 37)
WHITE = (255, 255, 255)

_COLOR_MAP = {
    "BG": "BG",
    "TEXT_CLR": "TEXT",
    "SUBTEXT_CLR": "SUBTEXT",
    "ACCENT": "ACCENT_YELLOW",
    "GREEN": "GREEN",
    "RED": "RED",
    "BLUE": "ALICE",
    "MAUVE": "QUBIT",
    "PEACH": "PEACH",
    "YELLOW": "ACCENT_YELLOW",
    "OVERLAY": "OVERLAY",
    "PANEL_BG": "PANEL_BG",
    "WHITE": "WHITE",
}


def _load_theme_colors():
    load_pg_colors(_COLOR_MAP, globals())


# ── 네트워크 노드 위치 ────────────────────────────────
SENSOR_POS = (120, 160)
CTRL_POS = (450, 160)
HMI_POS = (750, 160)
EVE_POS = (285, 60)

# ── 그래프 영역 ──────────────────────────────────────
GRAPH_X, GRAPH_Y = 40, 310
GRAPH_W, GRAPH_H = 400, 140

QBER_X, QBER_Y = 480, 310
QBER_W, QBER_H = 180, 140

LOG_X, LOG_Y = 480, 470
LOG_W = 400

STATS_X, STATS_Y = 40, 470


# ── 그리기 헬퍼 ──────────────────────────────────────


def _draw_node(screen, pos, label, sublabel, color, font, big_font, radius=30, glow_color=None, glow_radius=0):
    """네트워크 노드 그리기."""
    if glow_color and glow_radius > 0:
        glow = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*glow_color, 60), (glow_radius, glow_radius), glow_radius)
        screen.blit(glow, (pos[0] - glow_radius, pos[1] - glow_radius))

    pygame.draw.circle(screen, color, pos, radius)
    pygame.draw.circle(screen, TEXT_CLR, pos, radius, 2)

    lbl = big_font.render(label, True, color)
    screen.blit(lbl, (pos[0] - lbl.get_width() // 2, pos[1] + radius + 6))

    sub = font.render(sublabel, True, SUBTEXT_CLR)
    screen.blit(sub, (pos[0] - sub.get_width() // 2, pos[1] + radius + 22))


def _draw_network_link(screen, start, end, color, width=2, dashed=False):
    """네트워크 링크 그리기."""
    if dashed:
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 1:
            return
        nx, ny = dx / dist, dy / dist
        seg = 8
        gap = 6
        pos = 0.0
        while pos < dist:
            sx = int(start[0] + nx * pos)
            sy = int(start[1] + ny * pos)
            ex = int(start[0] + nx * min(pos + seg, dist))
            ey = int(start[1] + ny * min(pos + seg, dist))
            pygame.draw.line(screen, color, (sx, sy), (ex, ey), width)
            pos += seg + gap
    else:
        pygame.draw.line(screen, color, start, end, width)


def _draw_network(screen, gs: ScadaSecurityState, anim_t, font, big_font):
    """SCADA 네트워크 토폴로지 그리기."""
    # 연결선
    link_color = GREEN if gs.phase == PHASE_PROTECTED else OVERLAY
    if gs.phase == PHASE_ATTACK:
        link_color = RED
    elif gs.phase == PHASE_DETECTED:
        # 깜빡이는 효과
        link_color = RED if int(anim_t * 4) % 2 == 0 else YELLOW

    _draw_network_link(screen, (SENSOR_POS[0] + 35, SENSOR_POS[1]), (CTRL_POS[0] - 35, CTRL_POS[1]), link_color)
    _draw_network_link(
        screen,
        (CTRL_POS[0] + 35, CTRL_POS[1]),
        (HMI_POS[0] - 35, HMI_POS[1]),
        GREEN if gs.phase == PHASE_PROTECTED else OVERLAY,
    )

    # QKD 인증 채널 (보호 모드)
    if gs.phase == PHASE_PROTECTED or gs.qkd.authenticated:
        wave_offset = math.sin(anim_t * 4) * 3
        mid_y = SENSOR_POS[1] + 45
        _draw_network_link(
            screen, (SENSOR_POS[0] + 20, mid_y + wave_offset), (CTRL_POS[0] - 20, mid_y - wave_offset), MAUVE, 2
        )
        qlbl = font.render("QKD Auth", True, MAUVE)
        screen.blit(qlbl, ((SENSOR_POS[0] + CTRL_POS[0]) // 2 - qlbl.get_width() // 2, mid_y + 8))

    # Eve 연결선 (공격 시)
    if gs.attack_active:
        eve_alpha = min(255, int(gs.attack_intensity * 255))
        eve_color = (*RED[:3], eve_alpha) if eve_alpha < 255 else RED
        mid_x = (SENSOR_POS[0] + CTRL_POS[0]) // 2
        _draw_network_link(screen, EVE_POS, (mid_x, SENSOR_POS[1] - 5), eve_color, 1, dashed=True)

    # 노드 그리기
    sensor_glow = RED if gs.attack_active and gs.attack_intensity > 0.5 else None
    _draw_node(
        screen,
        SENSOR_POS,
        t("ss_sensor"),
        t("ss_temp_sensor"),
        BLUE,
        font,
        big_font,
        glow_color=sensor_glow,
        glow_radius=40 if sensor_glow else 0,
    )

    ctrl_color = GREEN if gs.phase == PHASE_PROTECTED else BLUE
    _draw_node(screen, CTRL_POS, t("ss_controller"), "PLC/RTU", ctrl_color, font, big_font)

    _draw_node(screen, HMI_POS, "HMI", t("ss_operator"), BLUE, font, big_font)

    # Eve 노드
    if gs.attack_active or gs.attack_intensity > 0.01:
        eve_glow = int(40 + 20 * math.sin(anim_t * 8))
        glow_s = pygame.Surface((eve_glow * 2, eve_glow * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_s, (*RED, int(100 * gs.attack_intensity)), (eve_glow, eve_glow), eve_glow)
        screen.blit(glow_s, (EVE_POS[0] - eve_glow, EVE_POS[1] - eve_glow))

    eve_alpha = 255 if gs.attack_active else max(40, int(gs.attack_intensity * 200))
    eve_r = 22
    pygame.draw.circle(screen, (*RED[:3], eve_alpha) if eve_alpha < 255 else RED, EVE_POS, eve_r)
    pygame.draw.circle(screen, TEXT_CLR, EVE_POS, eve_r, 2)
    eve_lbl = big_font.render("Eve", True, RED)
    screen.blit(eve_lbl, (EVE_POS[0] - eve_lbl.get_width() // 2, EVE_POS[1] - eve_r - 16))
    eve_sub = font.render("MITM", True, SUBTEXT_CLR)
    screen.blit(eve_sub, (EVE_POS[0] - eve_sub.get_width() // 2, EVE_POS[1] - eve_r - 4))

    # HMI 표시 온도
    hmi_temp_color = GREEN if not gs.attack_active else RED
    hmi_temp = f"{gs.displayed_temp:.1f} C"
    ts = big_font.render(hmi_temp, True, hmi_temp_color)
    screen.blit(ts, (HMI_POS[0] - ts.get_width() // 2, HMI_POS[1] - 14))

    # 실제 온도 (센서 위)
    real_temp = f"{gs.real_temp:.1f} C"
    rt_color = RED if gs.real_temp > CRITICAL_TEMP else GREEN
    rts = font.render(real_temp, True, rt_color)
    screen.blit(rts, (SENSOR_POS[0] - rts.get_width() // 2, SENSOR_POS[1] - 14))


def _draw_phase_indicator(screen, gs: ScadaSecurityState, anim_t, font, big_font):
    """위상 상태 표시기."""
    phase_colors = {
        PHASE_NORMAL: GREEN,
        PHASE_ATTACK: RED,
        PHASE_DETECTED: YELLOW,
        PHASE_PROTECTED: MAUVE,
    }
    color = phase_colors.get(gs.phase, TEXT_CLR)
    name = PHASE_NAMES[gs.phase]

    # 배경 바
    bar_w = 200
    bar_h = 28
    bx = WIDTH // 2 - bar_w // 2
    by = 250

    pygame.draw.rect(screen, PANEL_BG, (bx, by, bar_w, bar_h), border_radius=6)
    pygame.draw.rect(screen, color, (bx, by, bar_w, bar_h), 2, border_radius=6)

    # 위상별 아이콘 (4개 도트)
    dot_y = by + bar_h // 2
    for i in range(4):
        dx = bx + 25 + i * 50
        dc = phase_colors[i]
        r = 6 if i == gs.phase else 4
        if i == gs.phase and int(anim_t * 3) % 2 == 0:
            # 현재 위상 깜빡임
            pygame.draw.circle(screen, dc, (dx, dot_y), r + 2)
        pygame.draw.circle(screen, dc if i <= gs.phase else OVERLAY, (dx, dot_y), r)

    # 텍스트
    phase_text = big_font.render(name, True, color)
    screen.blit(phase_text, (WIDTH // 2 - phase_text.get_width() // 2, by + bar_h + 4))


def _draw_temp_graph(screen, gs: ScadaSecurityState, font, big_font):
    """온도 그래프 (실제 vs 표시)."""
    # 배경
    pygame.draw.rect(screen, PANEL_BG, (GRAPH_X, GRAPH_Y, GRAPH_W, GRAPH_H))
    pygame.draw.rect(screen, OVERLAY, (GRAPH_X, GRAPH_Y, GRAPH_W, GRAPH_H), 1)

    # 타이틀
    title = big_font.render(t("ss_temp_graph"), True, ACCENT)
    screen.blit(title, (GRAPH_X + 4, GRAPH_Y - 18))

    if len(gs.real_temp_history) < 2:
        return

    # 범위 계산
    all_temps = gs.real_temp_history + gs.displayed_temp_history
    t_min = min(all_temps) - 2
    t_max = max(all_temps) + 2
    if t_max - t_min < 5:
        t_max = t_min + 5

    n = len(gs.real_temp_history)
    dx = GRAPH_W / max(n - 1, 1)

    def temp_to_y(temp):
        ratio = (temp - t_min) / (t_max - t_min)
        return int(GRAPH_Y + GRAPH_H - ratio * GRAPH_H)

    # 임계 온도선
    crit_y = temp_to_y(CRITICAL_TEMP)
    if GRAPH_Y < crit_y < GRAPH_Y + GRAPH_H:
        pygame.draw.line(screen, RED, (GRAPH_X, crit_y), (GRAPH_X + GRAPH_W, crit_y), 1)
        crit_lbl = font.render(f"{CRITICAL_TEMP} C", True, RED)
        screen.blit(crit_lbl, (GRAPH_X + GRAPH_W - crit_lbl.get_width() - 2, crit_y - 12))

    # 목표 온도선
    tgt_y = temp_to_y(TARGET_TEMP)
    if GRAPH_Y < tgt_y < GRAPH_Y + GRAPH_H:
        pygame.draw.line(screen, GREEN, (GRAPH_X, tgt_y), (GRAPH_X + GRAPH_W, tgt_y), 1)

    # 표시 온도 (회색)
    disp_pts = []
    for i, tmp in enumerate(gs.displayed_temp_history):
        x = int(GRAPH_X + i * dx)
        y = temp_to_y(tmp)
        disp_pts.append((x, max(GRAPH_Y, min(GRAPH_Y + GRAPH_H, y))))
    if len(disp_pts) >= 2:
        pygame.draw.lines(screen, SUBTEXT_CLR, False, disp_pts, 1)

    # 실제 온도 (컬러)
    real_pts = []
    for i, tmp in enumerate(gs.real_temp_history):
        x = int(GRAPH_X + i * dx)
        y = temp_to_y(tmp)
        real_pts.append((x, max(GRAPH_Y, min(GRAPH_Y + GRAPH_H, y))))
    if len(real_pts) >= 2:
        color = RED if gs.real_temp > CRITICAL_TEMP else BLUE
        pygame.draw.lines(screen, color, False, real_pts, 2)

    # 범례
    leg_y = GRAPH_Y + GRAPH_H + 4
    real_lbl = font.render(t("ss_real_temp"), True, BLUE)
    screen.blit(real_lbl, (GRAPH_X + 4, leg_y))
    disp_lbl = font.render(t("ss_displayed_temp"), True, SUBTEXT_CLR)
    screen.blit(disp_lbl, (GRAPH_X + 120, leg_y))

    # 스푸핑 경고
    if gs.attack_active:
        spoof_lbl = font.render(t("ss_spoofed"), True, RED)
        screen.blit(spoof_lbl, (GRAPH_X + GRAPH_W - spoof_lbl.get_width() - 4, leg_y))


def _draw_qber_meter(screen, gs: ScadaSecurityState, anim_t, font, big_font):
    """QBER 미터."""
    # 배경
    pygame.draw.rect(screen, PANEL_BG, (QBER_X, QBER_Y, QBER_W, QBER_H))
    pygame.draw.rect(screen, OVERLAY, (QBER_X, QBER_Y, QBER_W, QBER_H), 1)

    title = big_font.render("QBER", True, ACCENT)
    screen.blit(title, (QBER_X + 4, QBER_Y - 18))

    # QBER 바 (세로)
    bar_x = QBER_X + 20
    bar_w = 30
    bar_h = QBER_H - 20
    bar_y = QBER_Y + 10

    pygame.draw.rect(screen, OVERLAY, (bar_x, bar_y, bar_w, bar_h))

    # 채움
    qber_val = min(gs.qkd.qber, 0.5)
    fill_h = int(bar_h * qber_val / 0.5)
    if fill_h > 0:
        fill_color = RED if gs.qkd.qber > QBER_DETECT_THRESHOLD else GREEN
        pygame.draw.rect(screen, fill_color, (bar_x, bar_y + bar_h - fill_h, bar_w, fill_h))

    pygame.draw.rect(screen, TEXT_CLR, (bar_x, bar_y, bar_w, bar_h), 1)

    # 임계선
    thresh_ratio = QBER_DETECT_THRESHOLD / 0.5
    thresh_y = int(bar_y + bar_h - bar_h * thresh_ratio)
    pygame.draw.line(screen, YELLOW, (bar_x - 4, thresh_y), (bar_x + bar_w + 4, thresh_y), 2)
    thresh_lbl = font.render(f"{QBER_DETECT_THRESHOLD * 100:.0f}%", True, YELLOW)
    screen.blit(thresh_lbl, (bar_x + bar_w + 6, thresh_y - 6))

    # 수치 표시
    pct = font.render(f"{gs.qkd.qber * 100:.1f}%", True, TEXT_CLR)
    screen.blit(pct, (bar_x + bar_w + 6, bar_y + bar_h - 14))

    # QBER 히스토리 미니 그래프
    gx = QBER_X + 80
    gw = QBER_W - 90
    gy = QBER_Y + 10
    gh = QBER_H - 20

    if len(gs.qber_plot_history) >= 2:
        n = len(gs.qber_plot_history)
        dx = gw / max(n - 1, 1)
        pts = []
        for i, q in enumerate(gs.qber_plot_history):
            x = int(gx + i * dx)
            ratio = min(q, 0.5) / 0.5
            y = int(gy + gh - ratio * gh)
            pts.append((x, max(gy, min(gy + gh, y))))
        color = RED if gs.qkd.qber > QBER_DETECT_THRESHOLD else GREEN
        pygame.draw.lines(screen, color, False, pts, 1)

        # 임계선
        thr_y = int(gy + gh - gh * thresh_ratio)
        pygame.draw.line(screen, YELLOW, (gx, thr_y), (gx + gw, thr_y), 1)

    # 키 교환 통계
    info_y = QBER_Y + QBER_H + 4
    keys_lbl = font.render(
        t("ss_keys_info", exchanged=gs.qkd.keys_exchanged, compromised=gs.qkd.keys_compromised),
        True,
        TEXT_CLR,
    )
    screen.blit(keys_lbl, (QBER_X + 4, info_y))


def _draw_event_log(screen, gs: ScadaSecurityState, font, big_font):
    """이벤트 로그 패널."""
    title = big_font.render(t("ss_event_log"), True, ACCENT)
    screen.blit(title, (LOG_X, LOG_Y))

    for i, entry in enumerate(gs.event_log):
        if "[MITM]" in entry:
            color = RED
        elif "[QKD]" in entry:
            color = MAUVE
        elif "[ALARM]" in entry:
            color = YELLOW
        elif "[SYSTEM]" in entry:
            color = GREEN
        else:
            color = TEXT_CLR

        surf = font.render(entry, True, color)
        screen.blit(surf, (LOG_X, LOG_Y + 18 + i * 14))


def _draw_stats(screen, gs: ScadaSecurityState, font, big_font):
    """통계 패널."""
    lines = [
        (t("ss_stat_attacks", detected=gs.attacks_detected, blocked=gs.attacks_blocked), ACCENT),
        (t("ss_stat_max_temp", temp=gs.max_real_temp), RED if gs.max_real_temp > CRITICAL_TEMP else TEXT_CLR),
        (t("ss_stat_attack_time", time=gs.time_under_attack), TEXT_CLR),
        (
            t("ss_stat_qkd_state", state="Authenticated" if gs.qkd.authenticated else "Monitoring"),
            MAUVE if gs.qkd.authenticated else SUBTEXT_CLR,
        ),
        (
            t("ss_stat_cooling", state=t("emergency") if gs.emergency else (t("on") if gs.cooling_on else t("off"))),
            RED if gs.emergency else GREEN,
        ),
    ]
    for i, (text, color) in enumerate(lines):
        surf = font.render(text, True, color)
        screen.blit(surf, (STATS_X, STATS_Y + i * 16))


def _draw_attack_banner(screen, gs: ScadaSecurityState, anim_t, big_font):
    """공격/보호 배너."""
    if gs.phase == PHASE_ATTACK and int(anim_t * 3) % 2 == 0:
        banner = pygame.Surface((WIDTH, 4), pygame.SRCALPHA)
        banner.fill((*RED, 120))
        screen.blit(banner, (0, 0))
        screen.blit(banner, (0, HEIGHT - 4))

    if gs.phase == PHASE_DETECTED:
        text = big_font.render(t("ss_attack_detected"), True, YELLOW)
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, 284))

    if gs.phase == PHASE_PROTECTED:
        text = big_font.render(t("ss_channel_secured"), True, MAUVE)
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, 284))


# ── 메인 시뮬레이션 ──────────────────────────────────


def run_simulation():
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(t("game_title_scada_security"))
    clock = pygame.time.Clock()
    font = get_font(11)
    big_font = get_font(14, bold=True)
    title_font = get_font(18, bold=True)

    gs = ScadaSecurityState()
    reset_scenario(gs)
    anim_t = 0.0
    paused = False

    help_overlay = HelpOverlay("scada_security")
    tutorial = TutorialOverlay("scada_security")
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("scada_security")

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        anim_t += dt

        # ── 이벤트 ───────────────────────────────────
        for event in pygame.event.get():
            help_overlay.handle_event(event)
            if tutorial.handle_event(event):
                continue
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                snd.handle_key(event.key)
                if event.key == pygame.K_ESCAPE:
                    if confirm_quit(screen, font):
                        running = False
                elif event.key == pygame.K_SPACE:
                    # 수동 공격/방어 트리거
                    if gs.phase == PHASE_NORMAL:
                        trigger_attack(gs)
                        snd.play("eve_detected")
                    elif gs.phase in (PHASE_ATTACK, PHASE_DETECTED):
                        trigger_defense(gs)
                        snd.play("channel_shutdown")
                elif event.key == pygame.K_r:
                    reset_scenario(gs)
                elif event.key == pygame.K_p:
                    paused = not paused
                elif event.key == pygame.K_a:
                    gs.auto_scenario = not gs.auto_scenario
                elif event.key == pygame.K_q:
                    gs.qkd_enabled = not gs.qkd_enabled
                elif event.key == pygame.K_l:
                    toggle_locale()

        # ── 업데이트 ─────────────────────────────────
        if not paused:
            update_scenario(gs, dt)

            recorder.record(
                {
                    "phase": gs.phase,
                    "real_temp": gs.real_temp,
                    "displayed_temp": gs.displayed_temp,
                    "qber": gs.qkd.qber,
                    "attack_active": gs.attack_active,
                    "attack_intensity": gs.attack_intensity,
                }
            )

        # ── 렌더링 ───────────────────────────────────
        # 배경 (공격 시 약간 붉은 빛)
        if gs.phase == PHASE_ATTACK:
            flash = 0.3 + 0.2 * math.sin(anim_t * 4)
            r = int(BG[0] + (60 - BG[0]) * flash * gs.attack_intensity)
            g = int(BG[1] * (1 - flash * 0.3 * gs.attack_intensity))
            b = int(BG[2] * (1 - flash * 0.3 * gs.attack_intensity))
            screen.fill((max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))
        else:
            screen.fill(BG)

        # 타이틀
        title = title_font.render(t("game_title_scada_security"), True, ACCENT)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 8))

        # 시간 표시
        time_lbl = font.render(f"t = {gs.t:.1f}s", True, SUBTEXT_CLR)
        screen.blit(time_lbl, (WIDTH - time_lbl.get_width() - 10, 12))

        # 네트워크 토폴로지
        _draw_network(screen, gs, anim_t, font, big_font)

        # 위상 표시기
        _draw_phase_indicator(screen, gs, anim_t, font, big_font)

        # 온도 그래프
        _draw_temp_graph(screen, gs, font, big_font)

        # QBER 미터
        _draw_qber_meter(screen, gs, anim_t, font, big_font)

        # 통계
        _draw_stats(screen, gs, font, big_font)

        # 이벤트 로그
        _draw_event_log(screen, gs, font, big_font)

        # 배너
        _draw_attack_banner(screen, gs, anim_t, big_font)

        # 안내
        hints = [
            t(
                "ss_hint_line1",
                auto=t("auto_on") if gs.auto_scenario else t("auto_off"),
                pause=t("paused") if paused else t("running_state"),
            ),
            t("ss_hint_line2"),
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 36 + i * 16))

        help_overlay.draw(screen, font)
        tutorial.draw(screen, font)

        pygame.display.flip()

    finalize_session(
        "scada_security",
        {
            "attacks_detected": gs.attacks_detected,
            "attacks_blocked": gs.attacks_blocked,
            "max_real_temp": gs.max_real_temp,
            "time_under_attack": gs.time_under_attack,
            "elapsed": gs.t,
        },
        recorder=recorder,
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def open_scada_security():
    """외부에서 호출하는 진입점."""
    run_simulation()
