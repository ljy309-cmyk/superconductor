"""양자 중첩 및 터널링 시뮬레이션 (Pygame).

- 블로흐 구: 큐비트가 |0⟩ / |1⟩ 사이를 확률적으로 점멸 (중첩 시각화)
- 터널링: 입자가 장벽과 충돌할 때 10 % 확률로 장벽 반대편으로 이동
"""

import math

import pygame

from achievement_toast import AchievementToast
from achievements import check_achievements
from config_loader import cfg
from quantum.ui_common import (
    HISTORY_PAGE_SIZE,
    draw_bar_pattern as _draw_bar_pattern,
    paginate,
    render_notify,
)
from game_base import choose_difficulty_or_quit, finalize_session
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from perf_monitor import PerfMonitor
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
from sound_manager import get_sound_manager
from theme import is_reduced_motion, load_pg_colors, on_theme_change
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


# ── 레이아웃 ─────────────────────────────────────────


class Layout:
    """해상도 기반 레이아웃 좌표 계산.

    기준 해상도 900×600에 대한 비례식으로 좌표를 산출합니다.
    """

    def __init__(self, w: int = 900, h: int = 600):
        self.W = w
        self.H = h
        sx = w / 900
        sy = h / 600

        # 블로흐 구
        self.bloch_cx = int(730 * sx)
        self.bloch_cy = int(280 * sy)
        self.bloch_r = int(110 * min(sx, sy))

        # 타이틀
        self.title_y = int(12 * sy)

        # 이벤트 로그
        self.log_x = int(580 * sx)
        self.log_y = int(430 * sy)

        # 알림
        self.notify_y = h - int(70 * sy)

        # 하단 힌트
        self.hint_y = h - int(52 * sy)

        # 성능 모니터
        self.perf_x = w - int(250 * sx)


_layout = Layout()


def _rebuild_layout(w: int, h: int):
    """리사이즈 시 레이아웃 재계산."""
    global _layout
    _layout = Layout(w, h)


# ── 그리기 헬퍼 ──────────────────────────────────────


def _draw_sim_area(screen, font, barrier_width: int = BARRIER_WIDTH_DEFAULT):
    """시뮬레이션 영역 배경."""
    pygame.draw.rect(screen, SURFACE_CLR, (SIM_LEFT, SIM_TOP, SIM_W, SIM_H))
    pygame.draw.rect(screen, OVERLAY_CLR, (SIM_LEFT, SIM_TOP, SIM_W, SIM_H), 1)

    # 장벽
    bx = BARRIER_X - barrier_width // 2
    pygame.draw.rect(screen, BARRIER_CLR, (bx, SIM_TOP, barrier_width, SIM_H))
    _draw_bar_pattern(screen, (bx, SIM_TOP, barrier_width, SIM_H), BARRIER_CLR, "mid")

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
    if p.flash_timer > 0 and not is_reduced_motion():
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
    L = _layout
    BCX, BCY, BR = L.bloch_cx, L.bloch_cy, L.bloch_r
    time_ms = pygame.time.get_ticks()

    # 타이틀
    label = title_font.render(t("tn_bloch"), True, ACCENT)
    screen.blit(label, (BCX - label.get_width() // 2, BCY - BR - 40))

    # 구 외곽 (원)
    pygame.draw.circle(screen, BLOCH_RING, (BCX, BCY), BR, 1)

    # 적도 타원
    pygame.draw.ellipse(
        screen,
        BLOCH_RING,
        (BCX - BR, BCY - BR // 4, BR * 2, BR // 2),
        1,
    )

    # 축
    pygame.draw.line(screen, OVERLAY_CLR, (BCX, BCY - BR - 8), (BCX, BCY + BR + 8), 1)

    # |0⟩, |1⟩ 라벨
    z0 = font.render("|0⟩", True, TUNNEL_FLASH)
    z1 = font.render("|1⟩", True, REFLECT_CLR)
    screen.blit(z0, (BCX + 8, BCY - BR - 18))
    screen.blit(z1, (BCX + 8, BCY + BR + 4))

    # 상태 벡터 (θ 기반)
    theta = 0.0 if is_reduced_motion() else p.superposition_alpha(time_ms)
    tip_x = BCX + int(BR * 0.4 * math.sin(theta))
    tip_y = BCY - int(BR * math.cos(theta))

    pygame.draw.line(screen, ACCENT, (BCX, BCY), (tip_x, tip_y), 2)
    pygame.draw.circle(screen, ACCENT, (tip_x, tip_y), 6)

    # 현재 상태 텍스트
    state_label = f"|{'0' if theta < math.pi / 2 else '1'}⟩  θ={math.degrees(theta):.0f}°"
    sl = font.render(state_label, True, TEXT_CLR)
    screen.blit(sl, (BCX - sl.get_width() // 2, BCY + BR + 26))


def _draw_stats(screen, p: QuantumParticle, font, tunnel_prob: float = TUNNEL_PROB_BASE):
    """통계 패널."""
    L = _layout
    stats_x = L.bloch_cx - L.bloch_r
    stats_y = L.bloch_cy + L.bloch_r + 60

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


# ── 메인 시뮬레이션 ──────────────────────────────────


def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH + PANEL_W, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption(t("game_title_tunneling"))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 12)
    info_font = pygame.font.SysFont("Consolas", 11)
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

    # ── 업적 / 튜토리얼 / 성능 모니터 ──
    toast = AchievementToast()
    tutorial = TutorialOverlay("tunneling")
    perf = PerfMonitor(target_fps=FPS)

    barrier_width = BARRIER_WIDTH_DEFAULT
    tunnel_prob = _calc_tunnel_prob(barrier_width)

    # 알림 / 페이지네이션
    notify_msg = ""
    notify_timer = 0.0
    history_page = 0
    event_log: list[tuple[str, bool]] = []  # (message, is_tunnel)

    def _notify(msg: str, duration: float = 2.0):
        nonlocal notify_msg, notify_timer
        notify_msg = msg
        notify_timer = duration

    # ── 시작 시 난이도 선택 ──
    if not choose_difficulty_or_quit(screen, font, preset_hud, _load_theme_colors):
        return

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        perf.tick(dt)

        # ── 이벤트 ───────────────────────────────────
        for event in pygame.event.get():
            if tutorial.handle_event(event):
                continue
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
                    event_log.clear()
                    history_page = 0
                    _notify(t("notify_reset"), 1.0)
                elif event.key == pygame.K_PAGEUP:
                    history_page = max(0, history_page - 1)
                elif event.key == pygame.K_PAGEDOWN:
                    history_page += 1
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
                elif event.key == pygame.K_g:
                    toast.toggle_history()
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (event.w, event.h), pygame.RESIZABLE)
                _rebuild_layout(event.w - PANEL_W, event.h)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # 클릭으로 입자 재발사
                particle.reset()

        # ── 슬라이더 값 읽기 ─────────────────────────
        speed_mult = sl_speed.value
        barrier_width = int(sl_barrier.value)
        tunnel_prob = _calc_tunnel_prob(barrier_width)

        # ── 물리 업데이트 ────────────────────────────
        if not paused:
            prev_attempts = particle.total_attempts
            orig_vx = particle.vx
            particle.vx = orig_vx * speed_mult if orig_vx > 0 else orig_vx
            particle.update(dt, barrier_width, tunnel_prob, sl_boost.value)
            particle.vx = orig_vx  # 속도 배율은 화면용, 내부 상태 보존

            # ── 이벤트 로그 ──
            if particle.total_attempts > prev_attempts:
                n = particle.total_attempts
                if particle.tunneled is True:
                    event_log.append((t("tn_notify_tunneled", n=n), True))
                    _notify(t("tn_notify_tunneled", n=n), 1.0)
                elif particle.tunneled is False:
                    event_log.append((t("tn_notify_reflected", n=n), False))
                    _notify(t("tn_notify_reflected", n=n), 1.0)

                # 실시간 업적 체크
                try:
                    new_ach = check_achievements(
                        "tunneling",
                        {
                            "tunnel_count": particle.tunnel_count,
                            "total_attempts": particle.total_attempts,
                            "tunnel_rate": particle.tunnel_count / max(particle.total_attempts, 1),
                        },
                    )
                    toast.show_many(new_ach)
                except (KeyError, TypeError) as e:
                    _log.warning("실시간 업적 확인 실패: %s", e)

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
                }
            )

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        L = _layout
        t_surf = big_font.render(t("game_title_tunneling"), True, ACCENT)
        screen.blit(t_surf, (L.W // 2 - t_surf.get_width() // 2, L.title_y))

        # 시뮬레이션 영역
        _draw_sim_area(screen, font, barrier_width)

        # 입자
        _draw_particle(screen, particle, font)

        # 블로흐 구
        _draw_bloch_sphere(screen, particle, font, title_font)

        # 통계
        _draw_stats(screen, particle, font, tunnel_prob)

        # ── 이벤트 로그 (페이지네이션) ──
        if event_log:
            page_items, history_page, total_pages = paginate(event_log, history_page)
            title_text = t("tn_event_log")
            if total_pages > 1:
                title_text += f"  ({history_page + 1}/{total_pages})"
            lt = font.render(title_text, True, ACCENT)
            screen.blit(lt, (L.log_x, L.log_y))
            for li, (entry, is_tunnel) in enumerate(page_items):
                clr = TUNNEL_FLASH if is_tunnel else TEXT_CLR
                es = font.render(f"  {entry}", True, clr)
                screen.blit(es, (L.log_x, L.log_y + 16 + li * 14))

        # 슬라이더 패널 그리기
        panel.draw(screen, font)

        # 안내
        hints = [
            t(
                "hint_speed_info",
                speed=speed_mult,
                width=barrier_width,
                prob=tunnel_prob * 100,
                pause_state=t("paused") if paused else t("running_state"),
            ),
            t("hint_click_launch"),
            t("hint_pause_reset"),
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (SIM_LEFT, L.hint_y + i * 16))

        # 알림 메시지 (페이드 아웃)
        if notify_timer > 0:
            notify_timer -= dt
            render_notify(screen, notify_msg, notify_timer, info_font, ACCENT,
                          L.W // 2, L.notify_y)

        preset_hud.draw(screen, font)

        toast.update(dt)
        toast.draw(screen, info_font)
        toast.draw_history(screen, info_font)

        help_overlay.draw(screen, info_font)
        tutorial.draw(screen, info_font)
        perf.draw_overlay(screen, info_font, x=L.perf_x, y=4)

        pygame.display.flip()

    perf.log_summary()
    rate = particle.tunnel_count / max(particle.total_attempts, 1)
    finalize_session(
        "tunneling",
        {
            "total_attempts": particle.total_attempts,
            "tunnel_count": particle.tunnel_count,
            "reflect_count": particle.reflect_count,
            "tunnel_rate": round(rate, 3),
            "barrier_width": barrier_width,
            "tunnel_prob": round(tunnel_prob, 3),
        },
        recorder=recorder,
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def open_tunneling():
    """외부에서 호출하는 진입점."""
    run_simulation()
