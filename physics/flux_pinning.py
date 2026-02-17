"""마이스너 부상 & 플럭스 피닝 시뮬레이션 (Pygame)."""

import math
import sys
import time

import pygame

from config_loader import cfg
from theme import get_pg_theme
from help_overlay import HelpOverlay
from sound_manager import get_sound_manager
from achievements import check_achievements
from replay import ReplayRecorder
from logger import get_module_logger

_log = get_module_logger("flux_pinning")

# ── 화면 설정 ────────────────────────────────────────
WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
FPS = cfg("display", "fps", 60)

# ── 색상 (테마에서 동적 로드) ─────────────────────────
_pg = get_pg_theme()
BG = _pg.BG
TEXT_CLR = _pg.TEXT
MAGNET_N = _pg.MAGNET_N
MAGNET_S = _pg.MAGNET_S
SC_COLOR = _pg.SC_COLOR
SC_GLOW = _pg.SC_GLOW
FIELD_CLR = (*_pg.SUBTEXT, 60)


def _load_theme_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    global BG, TEXT_CLR, MAGNET_N, MAGNET_S, SC_COLOR, SC_GLOW
    global SUBTEXT_CLR, WHITE, INACTIVE_CLR
    pg = get_pg_theme()
    BG = pg.BG
    TEXT_CLR = pg.TEXT
    MAGNET_N = pg.MAGNET_N
    MAGNET_S = pg.MAGNET_S
    SC_COLOR = pg.SC_COLOR
    SC_GLOW = pg.SC_GLOW
    SUBTEXT_CLR = pg.SUBTEXT
    WHITE = pg.WHITE
    INACTIVE_CLR = pg.INACTIVE

# ── 물리 파라미터 (config.json에서 로드) ──────────────
EQUILIBRIUM_GAP = cfg("flux_pinning", "equilibrium_gap", 65.0)
SPRING_K = cfg("flux_pinning", "spring_k", 4.0)
DAMPING = cfg("flux_pinning", "damping", 0.88)
LEVITATION_AMP = cfg("flux_pinning", "levitation_amp", 4.0)
LEVITATION_FREQ = cfg("flux_pinning", "levitation_freq", 2.0)
GRAVITY = cfg("flux_pinning", "gravity", 480.0)
FLOOR_Y = 560.0          # 바닥 Y 좌표 (px)

# ── 오브젝트 크기 ────────────────────────────────────
MAGNET_W, MAGNET_H = 160, 50
SC_W, SC_H = 100, 30


def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Meissner Levitation & Flux Pinning")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 13)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)

    # ── 도움말 & 사운드 & 리플레이 ──
    help_overlay = HelpOverlay("flux_pinning")
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("flux_pinning")

    # 자석 위치 (중심 좌표)
    magnet_x = WIDTH / 2
    magnet_y = HEIGHT / 2 + 40

    # 초전도체 위치·속도 (중심 좌표)
    sc_x = magnet_x
    sc_y = magnet_y - EQUILIBRIUM_GAP
    sc_vx = 0.0
    sc_vy = 0.0

    dragging = False
    flipped = False        # 자석 뒤집힘 여부
    superconducting = True  # 초전도 상태
    prev_superconducting = True  # 상태 변화 감지용
    t = 0.0
    start_time = time.time()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt

        # ── 이벤트 처리 ──────────────────────────────
        for event in pygame.event.get():
            help_overlay.handle_event(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and not help_overlay.visible:
                    running = False
                elif event.key == pygame.K_f:
                    flipped = not flipped
                elif event.key == pygame.K_SPACE:
                    superconducting = not superconducting
                    if superconducting:
                        sc_vy = 0.0
                        sc_vx = 0.0
                        snd.play("levitate")
                    else:
                        snd.play("fall")
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if abs(mx - magnet_x) < MAGNET_W / 2 and abs(my - magnet_y) < MAGNET_H / 2:
                    dragging = True
            elif event.type == pygame.MOUSEBUTTONUP:
                dragging = False

        if dragging:
            magnet_x, magnet_y = pygame.mouse.get_pos()

        # ── 물리 연산 ────────────────────────────────
        if superconducting:
            direction = 1 if flipped else -1
            target_x = magnet_x
            target_y = magnet_y + direction * EQUILIBRIUM_GAP

            dx = sc_x - target_x
            dy = sc_y - target_y
            ax = -SPRING_K * dx
            ay = -SPRING_K * dy

            sc_vx = (sc_vx + ax * dt) * DAMPING
            sc_vy = (sc_vy + ay * dt) * DAMPING
            sc_x += sc_vx
            sc_y += sc_vy

            levitation_offset = LEVITATION_AMP * math.sin(LEVITATION_FREQ * 2 * math.pi * t)
            draw_sc_y = sc_y + levitation_offset
        else:
            sc_vy += GRAVITY * dt
            sc_y += sc_vy * dt

            if sc_y >= FLOOR_Y:
                sc_y = FLOOR_Y
                sc_vy = 0.0

            draw_sc_y = sc_y

        # 리플레이 기록
        recorder.record_frame({
            "magnet": [round(magnet_x, 1), round(magnet_y, 1)],
            "sc": [round(sc_x, 1), round(draw_sc_y, 1)],
            "flipped": flipped,
            "superconducting": superconducting,
        })

        prev_superconducting = superconducting

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        title_surf = title_font.render("Meissner Levitation & Flux Pinning", True, SC_GLOW)
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 15))

        # 자기장 라인
        _draw_field_lines(screen, magnet_x, magnet_y, flipped)

        # 자석 그리기
        _draw_magnet(screen, magnet_x, magnet_y, flipped, font)

        # 초전도체 그리기
        _draw_superconductor(screen, sc_x, draw_sc_y, t, superconducting)

        # 연결선 (스프링 시각화)
        if superconducting:
            pygame.draw.line(
                screen, SUBTEXT_CLR,
                (int(magnet_x), int(magnet_y)),
                (int(sc_x), int(draw_sc_y)),
                1,
            )

        # 안내 텍스트
        state_label = "FALLEN" if not superconducting else (
            "FLIPPED" if flipped else "LEVITATING")
        hints = [
            "Drag: Move magnet  |  F: Flip  |  SPACE: SC ON/OFF",
            f"State: {state_label}  |  ESC: Exit",
        ]
        for i, hint in enumerate(hints):
            surf = font.render(hint, True, TEXT_CLR)
            screen.blit(surf, (12, HEIGHT - 40 + i * 18))

        # 도움말 오버레이 (맨 마지막)
        help_overlay.draw(screen, font)

        pygame.display.flip()

    # ── 종료: 플레이 기록 + 보고서 + 업적 ──
    play_time = round(time.time() - start_time, 1)
    session_data = {
        "play_time": play_time,
        "superconducting": superconducting,
        "flipped": flipped,
    }

    try:
        from data_ai.play_logger import get_logger
        get_logger().log_session("flux_pinning", session_data)
    except Exception as e:
        _log.error("플레이 기록 실패: %s", e)

    try:
        from report import generate_report
        generate_report("flux_pinning", session_data)
    except Exception as e:
        _log.error("보고서 생성 실패: %s", e)

    try:
        check_achievements("flux_pinning", session_data)
    except Exception as e:
        _log.error("업적 확인 실패: %s", e)

    recorder.save({"play_time": play_time})
    snd.quit()
    pygame.quit()


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


def _draw_superconductor(screen, cx, cy, t, superconducting=True):
    """초전도체 (글로우 효과 포함)."""
    rect = pygame.Rect(cx - SC_W / 2, cy - SC_H / 2, SC_W, SC_H)

    if superconducting:
        glow_alpha = int(80 + 40 * math.sin(t * 3))
        glow_surf = pygame.Surface((SC_W + 16, SC_H + 16), pygame.SRCALPHA)
        glow_surf.fill((*SC_GLOW, glow_alpha))
        screen.blit(glow_surf, (rect.x - 8, rect.y - 8))

    body_color = SC_COLOR if superconducting else INACTIVE_CLR
    pygame.draw.rect(screen, body_color, rect, border_radius=6)
    pygame.draw.rect(screen, WHITE, rect, 1, border_radius=6)


def _draw_field_lines(screen, cx, cy, flipped):
    """자기장 라인 (곡선 점선)."""
    offsets = [-50, -25, 0, 25, 50]
    direction = 1 if flipped else -1
    for ox in offsets:
        for i in range(8):
            y_off = direction * (30 + i * 18)
            x_spread = ox * (1 + abs(i - 4) * 0.15)
            px = int(cx + x_spread)
            py = int(cy + y_off)
            if 0 <= py <= HEIGHT:
                pygame.draw.circle(screen, SUBTEXT_CLR, (px, py), 1)


def open_flux_pinning():
    """외부에서 호출하는 진입점."""
    run_simulation()
