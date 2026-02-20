"""마이스너 부상 & 플럭스 피닝 시뮬레이션 (Pygame).

강화된 물리 시뮬레이션:
  - 온도 연동: T > Tc 이면 초전도 상태가 깨지고 부양 무너짐
  - 2D 자유도: 수평 이동 시 자속 핀닝에 의한 잠금(locking) 효과
  - 자기장 라인 시각화 개선: 핀닝 포인트 표시, 곡선 필드라인
"""

import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Tuple

import pygame

from config_loader import cfg
from font_helper import get_font
from game_base import finalize_session
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from sim_speed import apply_speed, cycle_sim_speed, speed_label
from sound_manager import get_sound_manager
from theme import load_pg_colors, on_theme_change

_log = get_module_logger("flux_pinning")

# ── 화면 설정 ────────────────────────────────────────
WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
FPS = cfg("display", "fps", 60)

# ── 색상 (테마에서 동적 로드) ─────────────────────────
from theme import get_pg_theme as _get_pg_theme_init

_pg = _get_pg_theme_init()
BG = _pg.BG
TEXT_CLR = _pg.TEXT
MAGNET_N = _pg.MAGNET_N
MAGNET_S = _pg.MAGNET_S
SC_COLOR = _pg.SC_COLOR
SC_GLOW = _pg.SC_GLOW
FIELD_CLR = (*_pg.SUBTEXT, 60)
del _get_pg_theme_init


_COLOR_MAP = {
    "BG": "BG",
    "TEXT_CLR": "TEXT",
    "MAGNET_N": "MAGNET_N",
    "MAGNET_S": "MAGNET_S",
    "SC_COLOR": "SC_COLOR",
    "SC_GLOW": "SC_GLOW",
    "SUBTEXT_CLR": "SUBTEXT",
    "WHITE": "WHITE",
    "INACTIVE_CLR": "INACTIVE",
}


def _load_theme_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    load_pg_colors(_COLOR_MAP, globals())


# ── 물리 파라미터 (config.json에서 로드) ──────────────
EQUILIBRIUM_GAP = cfg("flux_pinning", "equilibrium_gap", 65.0)
SPRING_K = cfg("flux_pinning", "spring_k", 4.0)
DAMPING = cfg("flux_pinning", "damping", 0.88)
LEVITATION_AMP = cfg("flux_pinning", "levitation_amp", 4.0)
LEVITATION_FREQ = cfg("flux_pinning", "levitation_freq", 2.0)
GRAVITY = cfg("flux_pinning", "gravity", 480.0)
FLOOR_Y = 560.0  # 바닥 Y 좌표 (px)

# ── 온도 파라미터 ─────────────────────────────────────
TC_KELVIN = cfg("flux_pinning", "tc_kelvin", 92.0)
TEMP_MIN = cfg("flux_pinning", "temp_min", 4.0)
TEMP_MAX = cfg("flux_pinning", "temp_max", 150.0)
TEMP_STEP = cfg("flux_pinning", "temp_step", 2.0)

# ── 2D 핀닝 파라미터 ─────────────────────────────────
PIN_SPRING_K = cfg("flux_pinning", "pin_spring_k", 6.0)
PIN_DAMPING = cfg("flux_pinning", "pin_damping", 0.82)
PIN_LOCK_RADIUS = cfg("flux_pinning", "pin_lock_radius", 40.0)
NUM_PINNING_SITES = cfg("flux_pinning", "num_pinning_sites", 7)

# ── 자기장 시각화 파라미터 ────────────────────────────
FIELD_LINE_COUNT = cfg("flux_pinning", "field_line_count", 9)
FIELD_LINE_SEGMENTS = cfg("flux_pinning", "field_line_segments", 14)

# ── 오브젝트 크기 ────────────────────────────────────
MAGNET_W, MAGNET_H = 160, 50
SC_W, SC_H = 100, 30

# ── 키보드 자석 이동 속도 (px/s) ──
KB_MAGNET_SPEED = 300


# ── 핀닝 사이트 ──────────────────────────────────────


@dataclass
class PinningSite:
    """자속이 고정되는 핀닝 포인트 (초전도체 내부 불순물/결함)."""

    rel_x: float  # 초전도체 중심 기준 상대 좌표
    rel_y: float
    flux_locked: bool = False
    lock_strength: float = 1.0


def _generate_pinning_sites(n: int) -> List[PinningSite]:
    """초전도체 내에 무작위 핀닝 사이트 생성."""
    sites = []
    for _ in range(n):
        rx = random.uniform(-SC_W / 2 + 8, SC_W / 2 - 8)
        ry = random.uniform(-SC_H / 2 + 4, SC_H / 2 - 4)
        strength = random.uniform(0.7, 1.0)
        sites.append(PinningSite(rel_x=rx, rel_y=ry, lock_strength=strength))
    return sites


# ── 온도-초전도 전이 물리 ─────────────────────────────


def sc_fraction(temperature: float, tc: float = TC_KELVIN) -> float:
    """온도에 따른 초전도 분율 (0~1).

    T < Tc: 1에 가까움 (BCS 근사)
    T >= Tc: 0 (정상 상태)
    """
    if temperature >= tc:
        return 0.0
    if temperature <= 0.0:
        return 1.0
    ratio = temperature / tc
    return max(0.0, 1.0 - ratio**2)


def effective_spring_k(temperature: float, base_k: float = SPRING_K) -> float:
    """온도에 따른 유효 스프링 상수 — Tc 근처에서 약해짐."""
    frac = sc_fraction(temperature)
    return base_k * frac


def pin_force(
    sc_x: float,
    sc_y: float,
    pin_anchor_x: float,
    pin_anchor_y: float,
    lock_radius: float = PIN_LOCK_RADIUS,
    k: float = PIN_SPRING_K,
) -> Tuple[float, float]:
    """핀닝 사이트가 초전도체에 가하는 잠금력.

    초전도체가 핀닝 앵커에서 lock_radius 이내일 때
    앵커 방향으로 복원력을 가한다.
    """
    dx = sc_x - pin_anchor_x
    dy = sc_y - pin_anchor_y
    dist = math.hypot(dx, dy)
    if dist < 0.1:
        return 0.0, 0.0
    # 잠금 반경 내에서만 핀닝력 발생 (거리에 비례)
    if dist > lock_radius:
        return 0.0, 0.0
    force_mag = k * dist
    fx = -force_mag * (dx / dist)
    fy = -force_mag * (dy / dist)
    return fx, fy


# ── 게임 상태 데이터클래스 ────────────────────────────


@dataclass
class FluxPinningState:
    """마이스너 부상 & 플럭스 피닝 게임 상태."""

    magnet_x: float = 0.0
    magnet_y: float = 0.0
    sc_x: float = 0.0
    sc_y: float = 0.0
    sc_vx: float = 0.0
    sc_vy: float = 0.0
    dragging: bool = False
    flipped: bool = False
    superconducting: bool = True
    prev_superconducting: bool = True
    t: float = 0.0
    start_time: float = field(default_factory=time.time)
    # ── 온도 시스템 ──
    temperature: float = 4.0  # 현재 온도 (K)
    # ── 2D 핀닝 ──
    pinning_sites: List[PinningSite] = field(default_factory=list)
    pin_anchor_x: float = 0.0  # 핀닝 잠금 시 기준 좌표
    pin_anchor_y: float = 0.0
    pinned: bool = False  # 핀닝 잠금 활성 여부


def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(t("game_title_flux_pinning"))
    clock = pygame.time.Clock()
    font = get_font(13)
    title_font = get_font(18, bold=True)

    # ── 도움말 & 사운드 & 리플레이 ──
    help_overlay = HelpOverlay("flux_pinning")
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("flux_pinning")

    gs = FluxPinningState(
        magnet_x=WIDTH / 2,
        magnet_y=HEIGHT / 2 + 40,
        sc_x=WIDTH / 2,
        sc_y=HEIGHT / 2 + 40 - EQUILIBRIUM_GAP,
        pinning_sites=_generate_pinning_sites(NUM_PINNING_SITES),
    )

    running = True
    while running:
        raw_dt = clock.tick(FPS) / 1000.0
        dt = apply_speed(raw_dt)
        gs.t += dt

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
                elif event.key == pygame.K_f:
                    gs.flipped = not gs.flipped
                elif event.key == pygame.K_SPACE:
                    # SPACE는 이제 핀닝 잠금 토글
                    if gs.superconducting:
                        gs.pinned = not gs.pinned
                        if gs.pinned:
                            gs.pin_anchor_x = gs.sc_x
                            gs.pin_anchor_y = gs.sc_y
                            for site in gs.pinning_sites:
                                site.flux_locked = True
                            snd.play("levitate")
                        else:
                            for site in gs.pinning_sites:
                                site.flux_locked = False
                elif event.key == pygame.K_l:
                    toggle_locale()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if abs(mx - gs.magnet_x) < MAGNET_W / 2 and abs(my - gs.magnet_y) < MAGNET_H / 2:
                    gs.dragging = True
            elif event.type == pygame.MOUSEBUTTONUP:
                gs.dragging = False

        if gs.dragging:
            gs.magnet_x, gs.magnet_y = pygame.mouse.get_pos()

        # ── 키보드: 온도 조절 (W/S) & 자석 이동 (화살표) ──
        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            gs.temperature = min(TEMP_MAX, gs.temperature + TEMP_STEP * dt * 30)
        if keys[pygame.K_s]:
            gs.temperature = max(TEMP_MIN, gs.temperature - TEMP_STEP * dt * 30)

        if not gs.dragging:
            if keys[pygame.K_LEFT]:
                gs.magnet_x -= KB_MAGNET_SPEED * dt
            if keys[pygame.K_RIGHT]:
                gs.magnet_x += KB_MAGNET_SPEED * dt
            if keys[pygame.K_UP]:
                gs.magnet_y -= KB_MAGNET_SPEED * dt
            if keys[pygame.K_DOWN]:
                gs.magnet_y += KB_MAGNET_SPEED * dt
            # 화면 경계 제한
            gs.magnet_x = max(MAGNET_W / 2, min(WIDTH - MAGNET_W / 2, gs.magnet_x))
            gs.magnet_y = max(MAGNET_H / 2, min(HEIGHT - MAGNET_H / 2, gs.magnet_y))

        # ── 온도에 따른 초전도 상태 결정 ──────────────
        frac = sc_fraction(gs.temperature)
        was_sc = gs.superconducting
        gs.superconducting = frac > 0.0

        if was_sc and not gs.superconducting:
            # Tc 초과 → 초전도 상태 붕괴
            gs.pinned = False
            for site in gs.pinning_sites:
                site.flux_locked = False
            snd.play("fall")
        elif not was_sc and gs.superconducting:
            # 다시 냉각 → 초전도 복원
            gs.sc_vy = 0.0
            gs.sc_vx = 0.0
            snd.play("levitate")

        # ── 물리 연산 ────────────────────────────────
        if gs.superconducting:
            direction = 1 if gs.flipped else -1
            target_x = gs.magnet_x
            target_y = gs.magnet_y + direction * EQUILIBRIUM_GAP

            # 온도에 따른 유효 스프링 상수 (Tc 근처에서 약화)
            eff_k = effective_spring_k(gs.temperature)

            dx = gs.sc_x - target_x
            dy = gs.sc_y - target_y
            ax = -eff_k * dx
            ay = -eff_k * dy

            # 2D 핀닝 잠금력 추가
            if gs.pinned:
                pfx, pfy = pin_force(gs.sc_x, gs.sc_y, gs.pin_anchor_x, gs.pin_anchor_y)
                pin_frac = frac  # 온도가 높을수록 핀닝력 약화
                ax += pfx * pin_frac
                ay += pfy * pin_frac

            gs.sc_vx = (gs.sc_vx + ax * dt) * DAMPING
            gs.sc_vy = (gs.sc_vy + ay * dt) * DAMPING

            # Tc 근처에서 미세 진동 추가 (열요동)
            if frac < 0.5:
                thermal_noise = (1.0 - frac) * 2.0
                gs.sc_vx += random.gauss(0, thermal_noise)
                gs.sc_vy += random.gauss(0, thermal_noise)

            gs.sc_x += gs.sc_vx
            gs.sc_y += gs.sc_vy

            levitation_offset = LEVITATION_AMP * frac * math.sin(LEVITATION_FREQ * 2 * math.pi * gs.t)
            draw_sc_y = gs.sc_y + levitation_offset
        else:
            gs.sc_vy += GRAVITY * dt
            gs.sc_y += gs.sc_vy * dt

            if gs.sc_y >= FLOOR_Y:
                gs.sc_y = FLOOR_Y
                gs.sc_vy = 0.0

            draw_sc_y = gs.sc_y

        # 리플레이 기록
        recorder.record_frame(
            {
                "magnet": [round(gs.magnet_x, 1), round(gs.magnet_y, 1)],
                "sc": [round(gs.sc_x, 1), round(draw_sc_y, 1)],
                "flipped": gs.flipped,
                "superconducting": gs.superconducting,
                "temperature": round(gs.temperature, 1),
                "pinned": gs.pinned,
            }
        )

        gs.prev_superconducting = gs.superconducting

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        title_surf = title_font.render(t("game_title_flux_pinning"), True, SC_GLOW)
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 15))

        # 자기장 라인 (개선된 버전)
        _draw_field_lines(screen, gs.magnet_x, gs.magnet_y, gs.flipped, gs.superconducting, frac)

        # 자석 그리기
        _draw_magnet(screen, gs.magnet_x, gs.magnet_y, gs.flipped, font)

        # 초전도체 그리기
        _draw_superconductor(screen, gs.sc_x, draw_sc_y, gs.t, gs.superconducting, frac)

        # 핀닝 포인트 표시
        if gs.superconducting:
            _draw_pinning_sites(screen, gs.sc_x, draw_sc_y, gs.pinning_sites, gs.pinned, frac)

        # 핀닝 잠금 표시 (앵커↔초전도체 연결선)
        if gs.pinned and gs.superconducting:
            _draw_pin_lock_indicator(screen, gs.sc_x, draw_sc_y, gs.pin_anchor_x, gs.pin_anchor_y, frac)

        # 연결선 (스프링 시각화)
        if gs.superconducting:
            alpha = max(30, int(200 * frac))
            line_color = (*SUBTEXT_CLR[:3], alpha) if len(SUBTEXT_CLR) >= 3 else SUBTEXT_CLR
            spring_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.line(
                spring_surf,
                line_color,
                (int(gs.magnet_x), int(gs.magnet_y)),
                (int(gs.sc_x), int(draw_sc_y)),
                1,
            )
            screen.blit(spring_surf, (0, 0))

        # 온도 게이지 (우측)
        _draw_temperature_gauge(screen, font, gs.temperature, frac)

        # 안내 텍스트
        if not gs.superconducting:
            state_label = t("flux_state_fallen")
        elif gs.pinned:
            state_label = t("fp_state_pinned")
        elif gs.flipped:
            state_label = t("flux_state_flipped")
        else:
            state_label = t("flux_state_levitating")
        hints = [
            t("fp_hint_line1_v2"),
            t("fp_hint_line2_v2", state=state_label, speed=speed_label(), temp=round(gs.temperature, 1)),
        ]
        for i, hint in enumerate(hints):
            surf = font.render(hint, True, TEXT_CLR)
            screen.blit(surf, (12, HEIGHT - 40 + i * 18))

        # 도움말 오버레이 (맨 마지막)
        help_overlay.draw(screen, font)

        pygame.display.flip()

    play_time = round(time.time() - gs.start_time, 1)
    finalize_session(
        "flux_pinning",
        {
            "play_time": play_time,
            "superconducting": gs.superconducting,
            "flipped": gs.flipped,
            "temperature": round(gs.temperature, 1),
            "pinned": gs.pinned,
        },
        recorder=recorder,
        recorder_meta={"play_time": play_time},
        snd=snd,
        theme_callback=_load_theme_colors,
    )


# ── 그리기 헬퍼 ──────────────────────────────────────


def _draw_magnet(screen, cx, cy, flipped, font):
    """자석 (N/S 극 분리 표시)."""
    left = cx - MAGNET_W / 2
    top = cy - MAGNET_H / 2

    n_color, s_color = (MAGNET_S, MAGNET_N) if flipped else (MAGNET_N, MAGNET_S)

    pygame.draw.rect(screen, n_color, (left, top, MAGNET_W / 2, MAGNET_H), border_radius=4)
    pygame.draw.rect(screen, s_color, (left + MAGNET_W / 2, top, MAGNET_W / 2, MAGNET_H), border_radius=4)
    pygame.draw.rect(screen, TEXT_CLR, (left, top, MAGNET_W, MAGNET_H), 2, border_radius=4)

    n_label = "S" if flipped else "N"
    s_label = "N" if flipped else "S"
    n_surf = font.render(n_label, True, WHITE)
    s_surf = font.render(s_label, True, WHITE)
    screen.blit(n_surf, (left + MAGNET_W / 4 - n_surf.get_width() / 2, cy - n_surf.get_height() / 2))
    screen.blit(s_surf, (left + 3 * MAGNET_W / 4 - s_surf.get_width() / 2, cy - s_surf.get_height() / 2))


def _draw_superconductor(screen, cx, cy, t, superconducting=True, frac=1.0):
    """초전도체 (글로우 효과 포함, 온도에 따라 변화)."""
    rect = pygame.Rect(cx - SC_W / 2, cy - SC_H / 2, SC_W, SC_H)

    if superconducting:
        glow_alpha = int((80 + 40 * math.sin(t * 3)) * frac)
        glow_surf = pygame.Surface((SC_W + 16, SC_H + 16), pygame.SRCALPHA)
        glow_surf.fill((*SC_GLOW, glow_alpha))
        screen.blit(glow_surf, (rect.x - 8, rect.y - 8))

    # 온도에 따른 색상 보간: SC_COLOR ↔ INACTIVE_CLR
    if superconducting and frac < 1.0:
        body_color = _lerp_color(INACTIVE_CLR, SC_COLOR, frac)
    elif superconducting:
        body_color = SC_COLOR
    else:
        body_color = INACTIVE_CLR

    pygame.draw.rect(screen, body_color, rect, border_radius=6)
    pygame.draw.rect(screen, WHITE, rect, 1, border_radius=6)

    # Tc 근처 경고 표시
    if superconducting and frac < 0.4:
        warn_alpha = int(180 * (1.0 - frac / 0.4) * abs(math.sin(t * 5)))
        warn_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        warn_surf.fill((255, 80, 40, warn_alpha))
        screen.blit(warn_surf, rect.topleft)


def _draw_field_lines(screen, cx, cy, flipped, superconducting, frac):
    """자기장 라인 — 곡선으로 개선, 초전도 시 마이스너 효과 표현."""
    direction = 1 if flipped else -1
    line_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    n_lines = FIELD_LINE_COUNT
    offsets = [(i - n_lines // 2) * 20 for i in range(n_lines)]

    for ox in offsets:
        points = []
        for seg in range(FIELD_LINE_SEGMENTS):
            t_param = seg / (FIELD_LINE_SEGMENTS - 1)  # 0 → 1
            y_off = direction * (30 + t_param * 200)

            # 기본 쌍곡선 스프레드
            spread = 1.0 + t_param * 0.8
            base_x = cx + ox * spread
            base_y = cy + y_off

            # 마이스너 효과: 초전도 상태일 때 필드라인이 초전도체를 피하는 효과
            if superconducting and frac > 0.0:
                meissner_strength = frac * 60.0
                # 필드라인이 초전도체에 가까워질수록 밀려남
                dx_from_center = abs(ox) + 1.0
                repel = meissner_strength / (dx_from_center * 0.3 + 1.0) * t_param
                if ox >= 0:
                    base_x += repel
                else:
                    base_x -= repel

            px = int(base_x)
            py = int(base_y)
            if 0 <= py <= HEIGHT and 0 <= px <= WIDTH:
                points.append((px, py))

        # 곡선 필드라인 그리기 (점선 → 실선 곡선)
        alpha = max(30, int(80 * (0.3 + 0.7 * (1.0 - frac)))) if superconducting else 80
        line_color = (*SUBTEXT_CLR[:3], alpha) if len(SUBTEXT_CLR) >= 3 else (*SUBTEXT_CLR, alpha)
        if len(points) >= 2:
            pygame.draw.lines(line_surf, line_color, False, points, 1)
            # 화살표 표시 (중간 지점)
            mid_idx = len(points) // 2
            if mid_idx > 0:
                _draw_arrow_head(line_surf, points[mid_idx - 1], points[mid_idx], line_color)

    screen.blit(line_surf, (0, 0))


def _draw_arrow_head(surface, p_from, p_to, color):
    """작은 화살표 머리를 그려서 자기장 방향 표시."""
    dx = p_to[0] - p_from[0]
    dy = p_to[1] - p_from[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return
    ux, uy = dx / length, dy / length
    # 화살표 크기
    size = 4
    px, py = p_to
    left = (int(px - size * ux - size * uy), int(py - size * uy + size * ux))
    right = (int(px - size * ux + size * uy), int(py - size * uy - size * ux))
    pygame.draw.polygon(surface, color, [p_to, left, right])


def _draw_pinning_sites(screen, sc_cx, sc_cy, sites, pinned, frac):
    """초전도체 위에 핀닝 사이트를 표시."""
    pin_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    for site in sites:
        px = int(sc_cx + site.rel_x)
        py = int(sc_cy + site.rel_y)

        if site.flux_locked and pinned:
            # 잠긴 핀닝: 밝은 원 + 십자
            alpha = int(200 * frac)
            color = (100, 220, 255, alpha)
            pygame.draw.circle(pin_surf, color, (px, py), 5)
            pygame.draw.circle(pin_surf, (255, 255, 255, alpha), (px, py), 5, 1)
            # 자속 통과 십자 표시
            pygame.draw.line(pin_surf, (255, 255, 255, alpha), (px - 3, py), (px + 3, py), 1)
            pygame.draw.line(pin_surf, (255, 255, 255, alpha), (px, py - 3), (px, py + 3), 1)
        else:
            # 미잠김: 작은 점
            alpha = int(100 * frac)
            color = (180, 180, 200, alpha)
            pygame.draw.circle(pin_surf, color, (px, py), 3)

    screen.blit(pin_surf, (0, 0))


def _draw_pin_lock_indicator(screen, sc_x, sc_y, anchor_x, anchor_y, frac):
    """핀닝 잠금 시 앵커 위치 표시 — 점선 원 + 연결선."""
    lock_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    alpha = int(160 * frac)

    # 앵커 위치 점선 원
    anchor_color = (100, 220, 255, alpha)
    radius = int(PIN_LOCK_RADIUS)
    # 점선 원 근사 (짧은 호들)
    for angle_deg in range(0, 360, 15):
        angle = math.radians(angle_deg)
        x1 = int(anchor_x + radius * math.cos(angle))
        y1 = int(anchor_y + radius * math.sin(angle))
        x2 = int(anchor_x + radius * math.cos(angle + math.radians(8)))
        y2 = int(anchor_y + radius * math.sin(angle + math.radians(8)))
        pygame.draw.line(lock_surf, anchor_color, (x1, y1), (x2, y2), 1)

    # 앵커 중심 십자
    cross_size = 6
    ax, ay = int(anchor_x), int(anchor_y)
    pygame.draw.line(lock_surf, anchor_color, (ax - cross_size, ay), (ax + cross_size, ay), 1)
    pygame.draw.line(lock_surf, anchor_color, (ax, ay - cross_size), (ax, ay + cross_size), 1)

    # 초전도체↔앵커 연결 스프링 선
    dist = math.hypot(sc_x - anchor_x, sc_y - anchor_y)
    if dist > 2:
        spring_color = (100, 200, 255, int(alpha * 0.6))
        pygame.draw.line(lock_surf, spring_color, (int(sc_x), int(sc_y)), (ax, ay), 1)

    screen.blit(lock_surf, (0, 0))


def _draw_temperature_gauge(screen, font, temperature, frac):
    """우측 온도 게이지 바 — 세로 막대 + 온도 표시."""
    gauge_x = WIDTH - 50
    gauge_top = 50
    gauge_bottom = HEIGHT - 60
    gauge_h = gauge_bottom - gauge_top
    gauge_w = 16

    # 배경 바
    bg_rect = pygame.Rect(gauge_x - gauge_w // 2, gauge_top, gauge_w, gauge_h)
    pygame.draw.rect(screen, (*SUBTEXT_CLR[:3],), bg_rect, 1, border_radius=3)

    # 온도 비율 (TEMP_MIN → TEMP_MAX)
    t_ratio = (temperature - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)
    t_ratio = max(0.0, min(1.0, t_ratio))
    fill_h = int(gauge_h * t_ratio)

    # 색상: 파랑(저온) → 빨강(고온)
    r = int(min(255, t_ratio * 2 * 255))
    g = int(max(0, (1.0 - abs(t_ratio - 0.5) * 2) * 180))
    b = int(min(255, (1.0 - t_ratio) * 2 * 255))
    fill_color = (r, g, b)

    fill_rect = pygame.Rect(
        gauge_x - gauge_w // 2 + 1,
        gauge_bottom - fill_h,
        gauge_w - 2,
        fill_h,
    )
    if fill_h > 0:
        pygame.draw.rect(screen, fill_color, fill_rect, border_radius=2)

    # Tc 마커
    tc_ratio = (TC_KELVIN - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)
    tc_y = int(gauge_bottom - gauge_h * tc_ratio)
    pygame.draw.line(
        screen,
        (255, 200, 50),
        (gauge_x - gauge_w // 2 - 6, tc_y),
        (gauge_x + gauge_w // 2 + 6, tc_y),
        2,
    )
    tc_label = font.render(f"Tc={TC_KELVIN:.0f}K", True, (255, 200, 50))
    screen.blit(tc_label, (gauge_x - gauge_w // 2 - tc_label.get_width() - 8, tc_y - tc_label.get_height() // 2))

    # 현재 온도 숫자
    temp_str = f"{temperature:.0f} K"
    temp_surf = font.render(temp_str, True, TEXT_CLR)
    screen.blit(temp_surf, (gauge_x - temp_surf.get_width() // 2, gauge_bottom + 8))

    # SC 분율 표시
    sc_str = f"SC: {frac * 100:.0f}%"
    sc_color = SC_GLOW if frac > 0 else INACTIVE_CLR
    sc_surf = font.render(sc_str, True, sc_color)
    screen.blit(sc_surf, (gauge_x - sc_surf.get_width() // 2, gauge_top - 18))


def _lerp_color(c1, c2, t):
    """두 RGB 색상을 t(0~1)로 선형 보간."""
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(min(len(c1), len(c2))))


def open_flux_pinning():
    """외부에서 호출하는 진입점."""
    run_simulation()
