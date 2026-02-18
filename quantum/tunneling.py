"""양자 중첩 및 터널링 시뮬레이션 (Pygame).

- 블로흐 구: 큐비트가 |0⟩ / |1⟩ 사이를 확률적으로 점멸 (중첩 시각화)
- 터널링: 입자가 장벽과 충돌할 때 10 % 확률로 장벽 반대편으로 이동
"""

import math

import pygame

from config_loader import cfg
from i18n import t, toggle_locale
from theme import load_pg_colors, on_theme_change
from ui.slider import SliderPanel, PANEL_W
from preset_hud import PresetHUD
from help_overlay import HelpOverlay
from sound_manager import get_sound_manager
from replay import ReplayRecorder
from quit_dialog import confirm_quit
from game_base import finalize_session, choose_difficulty_or_quit
from logger import get_module_logger

# ── 물리 엔진 (순수 로직) ────────────────────────────
from quantum.tunneling_physics import (
    TUNNEL_PROB_BASE, PARTICLE_SPEED, PARTICLE_RADIUS,
    BARRIER_WIDTH_DEFAULT, BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX,
    SUPERPOSITION_HZ, TUNNEL_SPEED_BOOST,
    _TUNNEL_DECAY, _VY_RANGE, _TUNNEL_FLASH, _REFLECT_FLASH,
    SIM_LEFT, SIM_TOP, SIM_W, SIM_H, BARRIER_X,
    _calc_tunnel_prob, QuantumParticle,
)

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
REFLECT_CLR = (243, 139, 168)   # 반사
BLOCH_RING = (88, 91, 112)


_COLOR_MAP = {
    "BG": "BG", "TEXT_CLR": "TEXT", "ACCENT": "ACCENT_PURPLE",
    "BARRIER_CLR": "ACCENT_YELLOW", "PARTICLE_CLR": "ACCENT_BLUE",
    "TUNNEL_FLASH": "GREEN", "REFLECT_CLR": "RED",
    "BLOCH_RING": "SUBTEXT", "SURFACE_CLR": "SURFACE",
    "OVERLAY_CLR": "OVERLAY", "WHITE": "WHITE",
}


def _load_theme_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    load_pg_colors(_COLOR_MAP, globals())

# ── 블로흐 구 레이아웃 ────────────────────────────────
BLOCH_CX, BLOCH_CY = 730, 280
BLOCH_R = 110


# ── 그리기 헬퍼 ──────────────────────────────────────

def _draw_sim_area(screen, font, barrier_width: int = BARRIER_WIDTH_DEFAULT):
    """시뮬레이션 영역 배경."""
    pygame.draw.rect(screen, SURFACE_CLR, (SIM_LEFT, SIM_TOP, SIM_W, SIM_H))
    pygame.draw.rect(screen, OVERLAY_CLR, (SIM_LEFT, SIM_TOP, SIM_W, SIM_H), 1)

    # 장벽
    bx = BARRIER_X - barrier_width // 2
    pygame.draw.rect(screen, BARRIER_CLR, (bx, SIM_TOP, barrier_width, SIM_H))

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


def _draw_bloch_sphere(screen, p: QuantumParticle, font, title_font):
    """블로흐 구 시각화."""
    time_ms = pygame.time.get_ticks()

    # 타이틀
    label = title_font.render(t("tn_bloch"), True, ACCENT)
    screen.blit(label, (BLOCH_CX - label.get_width() // 2, BLOCH_CY - BLOCH_R - 40))

    # 구 외곽 (원)
    pygame.draw.circle(screen, BLOCH_RING, (BLOCH_CX, BLOCH_CY), BLOCH_R, 1)

    # 적도 타원
    pygame.draw.ellipse(
        screen, BLOCH_RING,
        (BLOCH_CX - BLOCH_R, BLOCH_CY - BLOCH_R // 4, BLOCH_R * 2, BLOCH_R // 2),
        1,
    )

    # 축
    pygame.draw.line(screen, OVERLAY_CLR, (BLOCH_CX, BLOCH_CY - BLOCH_R - 8), (BLOCH_CX, BLOCH_CY + BLOCH_R + 8), 1)

    # |0⟩, |1⟩ 라벨
    z0 = font.render("|0⟩", True, TUNNEL_FLASH)
    z1 = font.render("|1⟩", True, REFLECT_CLR)
    screen.blit(z0, (BLOCH_CX + 8, BLOCH_CY - BLOCH_R - 18))
    screen.blit(z1, (BLOCH_CX + 8, BLOCH_CY + BLOCH_R + 4))

    # 상태 벡터 (θ 기반)
    theta = p.superposition_alpha(time_ms)
    tip_x = BLOCH_CX + int(BLOCH_R * 0.4 * math.sin(theta))
    tip_y = BLOCH_CY - int(BLOCH_R * math.cos(theta))

    pygame.draw.line(screen, ACCENT, (BLOCH_CX, BLOCH_CY), (tip_x, tip_y), 2)
    pygame.draw.circle(screen, ACCENT, (tip_x, tip_y), 6)

    # 현재 상태 텍스트
    state_label = f"|{'0' if theta < math.pi / 2 else '1'}⟩  θ={math.degrees(theta):.0f}°"
    sl = font.render(state_label, True, TEXT_CLR)
    screen.blit(sl, (BLOCH_CX - sl.get_width() // 2, BLOCH_CY + BLOCH_R + 26))


def _draw_stats(screen, p: QuantumParticle, font, tunnel_prob: float = TUNNEL_PROB_BASE):
    """통계 패널."""
    stats_x = BLOCH_CX - BLOCH_R
    stats_y = BLOCH_CY + BLOCH_R + 60

    lines = [
        (t("tn_attempts", count=p.total_attempts), TEXT_CLR),
        (t("tn_tunnel_stat", count=p.tunnel_count, pct=p.tunnel_count / max(p.total_attempts, 1) * 100), TUNNEL_FLASH),
        (t("tn_reflect_stat", count=p.reflect_count, pct=p.reflect_count / max(p.total_attempts, 1) * 100), REFLECT_CLR),
        (t("tn_current_prob", prob=tunnel_prob * 100), TEXT_CLR),
    ]
    for i, (line, color) in enumerate(lines):
        surf = font.render(line, True, color)
        screen.blit(surf, (stats_x, stats_y + i * 17))


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

    # ── 시작 시 난이도 선택 ──
    if not choose_difficulty_or_quit(screen, font, preset_hud, _load_theme_colors):
        return

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

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
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # 클릭으로 입자 재발사
                particle.reset()

        # ── 슬라이더 값 읽기 ─────────────────────────
        speed_mult = sl_speed.value
        barrier_width = int(sl_barrier.value)
        tunnel_prob = _calc_tunnel_prob(barrier_width)

        # ── 물리 업데이트 ────────────────────────────
        if not paused:
            orig_vx = particle.vx
            particle.vx = orig_vx * speed_mult if orig_vx > 0 else orig_vx
            particle.update(dt, barrier_width, tunnel_prob, sl_boost.value)
            particle.vx = orig_vx  # 속도 배율은 화면용, 내부 상태 보존

            # ── 사운드 ──
            if particle.tunneled is True and particle.flash_timer > 0.5:
                snd.play("tunnel_success")
            elif particle.tunneled is False and particle.flash_timer > 0.3:
                snd.play("tunnel_reflect")

            preset_hud.update(dt)

            recorder.record_frame({
                "x": round(particle.x, 1),
                "tunneled": particle.tunneled,
                "attempts": particle.total_attempts,
                "tunnels": particle.tunnel_count,
            })

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        t_surf = big_font.render(t("game_title_tunneling"), True, ACCENT)
        screen.blit(t_surf, (WIDTH // 2 - t_surf.get_width() // 2, 12))

        # 시뮬레이션 영역
        _draw_sim_area(screen, font, barrier_width)

        # 입자
        _draw_particle(screen, particle, font)

        # 블로흐 구
        _draw_bloch_sphere(screen, particle, font, title_font)

        # 통계
        _draw_stats(screen, particle, font, tunnel_prob)

        # 슬라이더 패널 그리기
        panel.draw(screen, font)

        # 안내
        hints = [
            t("hint_speed_info", speed=speed_mult, width=barrier_width, prob=tunnel_prob*100,
              pause_state=t("paused") if paused else t("running_state")),
            t("hint_click_launch"),
            t("hint_pause_reset"),
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (SIM_LEFT, HEIGHT - 52 + i * 16))

        preset_hud.draw(screen, font)
        help_overlay.draw(screen, font)

        pygame.display.flip()

    rate = particle.tunnel_count / max(particle.total_attempts, 1)
    finalize_session("tunneling", {
        "total_attempts": particle.total_attempts,
        "tunnel_count": particle.tunnel_count,
        "reflect_count": particle.reflect_count,
        "tunnel_rate": round(rate, 3),
        "barrier_width": barrier_width,
        "tunnel_prob": round(tunnel_prob, 3),
    }, recorder=recorder, snd=snd, theme_callback=_load_theme_colors)


def open_tunneling():
    """외부에서 호출하는 진입점."""
    run_simulation()
