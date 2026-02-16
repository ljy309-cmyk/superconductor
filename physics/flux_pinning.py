"""마이스너 부상 & 플럭스 피닝 시뮬레이션 (Pygame)."""

import math
import sys

import pygame

from config_loader import cfg
from theme import PG

# ── 화면 설정 ────────────────────────────────────────
WIDTH, HEIGHT = 800, 500
FPS = cfg("display", "fps", 60)

# ── 색상 (theme에서 가져옴) ──────────────────────────
BG = PG.BG
TEXT_CLR = PG.TEXT
MAGNET_N = PG.MAGNET_N
MAGNET_S = PG.MAGNET_S
SC_COLOR = PG.SC_COLOR
SC_GLOW = PG.SC_GLOW
FIELD_CLR = (88, 91, 112, 60)

# ── 물리 파라미터 (config.json에서 로드) ──────────────
EQUILIBRIUM_GAP = cfg("flux_pinning", "equilibrium_gap", 65.0)
SPRING_K = cfg("flux_pinning", "spring_k", 4.0)
DAMPING = cfg("flux_pinning", "damping", 0.88)
LEVITATION_AMP = cfg("flux_pinning", "levitation_amp", 4.0)
LEVITATION_FREQ = cfg("flux_pinning", "levitation_freq", 2.0)
GRAVITY = cfg("flux_pinning", "gravity", 480.0)
FLOOR_Y = 460.0          # 바닥 Y 좌표 (px)

# ── 오브젝트 크기 ────────────────────────────────────
MAGNET_W, MAGNET_H = 160, 50
SC_W, SC_H = 100, 30


def run_simulation():
    """Pygame 시뮬레이션 실행."""
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Meissner Levitation & Flux Pinning")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 13)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)

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
    t = 0.0

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt

        # ── 이벤트 처리 ──────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_f:
                    flipped = not flipped
                elif event.key == pygame.K_SPACE:
                    superconducting = not superconducting
                    if superconducting:
                        # 재냉각: 속도 초기화, 자석 위 평형 위치로 복귀
                        sc_vy = 0.0
                        sc_vx = 0.0
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
            # 평형 위치: 자석 위(또는 아래) EQUILIBRIUM_GAP 만큼 떨어진 지점
            direction = 1 if flipped else -1  # -1: 위에 부상, +1: 아래에 부상
            target_x = magnet_x
            target_y = magnet_y + direction * EQUILIBRIUM_GAP

            # 스프링 힘: F = -k * (현재 - 목표)
            dx = sc_x - target_x
            dy = sc_y - target_y
            ax = -SPRING_K * dx
            ay = -SPRING_K * dy

            sc_vx = (sc_vx + ax * dt) * DAMPING
            sc_vy = (sc_vy + ay * dt) * DAMPING
            sc_x += sc_vx
            sc_y += sc_vy

            # sin 부상 미세 진동
            levitation_offset = LEVITATION_AMP * math.sin(LEVITATION_FREQ * 2 * math.pi * t)
            draw_sc_y = sc_y + levitation_offset
        else:
            # 초전도 파괴 → 중력 낙하: v = v₀ + g·t
            sc_vy += GRAVITY * dt
            sc_y += sc_vy * dt

            # 바닥 충돌
            if sc_y >= FLOOR_Y:
                sc_y = FLOOR_Y
                sc_vy = 0.0

            draw_sc_y = sc_y

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        title_surf = title_font.render("Meissner Levitation & Flux Pinning", True, SC_GLOW)
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 15))

        # 자기장 라인 (점선으로 표현)
        _draw_field_lines(screen, magnet_x, magnet_y, flipped)

        # 자석 그리기
        _draw_magnet(screen, magnet_x, magnet_y, flipped, font)

        # 초전도체 그리기
        _draw_superconductor(screen, sc_x, draw_sc_y, t, superconducting)

        # 연결선 (스프링 시각화) — 초전도 상태에서만 표시
        if superconducting:
            pygame.draw.line(
                screen, (88, 91, 112),
                (int(magnet_x), int(magnet_y)),
                (int(sc_x), int(draw_sc_y)),
                1,
            )

        # 안내 텍스트
        state_label = "FALLEN (추락)" if not superconducting else (
            "FLIPPED (뒤집힘)" if flipped else "LEVITATING (부상)")
        hints = [
            "마우스 드래그: 자석 이동",
            "F 키: 자석 뒤집기 (플럭스 피닝 확인)",
            "SPACE: 초전도 ON/OFF (온도 변화)",
            "ESC: 종료",
            f"상태: {state_label}",
        ]
        for i, hint in enumerate(hints):
            surf = font.render(hint, True, TEXT_CLR)
            screen.blit(surf, (12, HEIGHT - 20 * len(hints) + 20 * i - 8))

        pygame.display.flip()

    pygame.quit()


# ── 그리기 헬퍼 ──────────────────────────────────────

def _draw_magnet(screen, cx, cy, flipped, font):
    """자석 (N/S 극 분리 표시)."""
    left = cx - MAGNET_W / 2
    top = cy - MAGNET_H / 2

    n_color, s_color = (MAGNET_S, MAGNET_N) if flipped else (MAGNET_N, MAGNET_S)

    # 좌측 반 (N)
    pygame.draw.rect(screen, n_color, (left, top, MAGNET_W / 2, MAGNET_H), border_radius=4)
    # 우측 반 (S)
    pygame.draw.rect(screen, s_color, (left + MAGNET_W / 2, top, MAGNET_W / 2, MAGNET_H), border_radius=4)
    # 테두리
    pygame.draw.rect(screen, TEXT_CLR, (left, top, MAGNET_W, MAGNET_H), 2, border_radius=4)

    # 극 라벨
    n_label = "S" if flipped else "N"
    s_label = "N" if flipped else "S"
    n_surf = font.render(n_label, True, (255, 255, 255))
    s_surf = font.render(s_label, True, (255, 255, 255))
    screen.blit(n_surf, (left + MAGNET_W / 4 - n_surf.get_width() / 2, cy - n_surf.get_height() / 2))
    screen.blit(s_surf, (left + 3 * MAGNET_W / 4 - s_surf.get_width() / 2, cy - s_surf.get_height() / 2))


def _draw_superconductor(screen, cx, cy, t, superconducting=True):
    """초전도체 (글로우 효과 포함)."""
    rect = pygame.Rect(cx - SC_W / 2, cy - SC_H / 2, SC_W, SC_H)

    if superconducting:
        # 글로우 (반투명 사각형 확장) — 초전도 상태에서만
        glow_alpha = int(80 + 40 * math.sin(t * 3))
        glow_surf = pygame.Surface((SC_W + 16, SC_H + 16), pygame.SRCALPHA)
        glow_surf.fill((*SC_GLOW, glow_alpha))
        screen.blit(glow_surf, (rect.x - 8, rect.y - 8))

    # 본체 — 초전도 파괴 시 색상 어둡게
    body_color = SC_COLOR if superconducting else (100, 100, 100)
    pygame.draw.rect(screen, body_color, rect, border_radius=6)
    pygame.draw.rect(screen, (255, 255, 255), rect, 1, border_radius=6)


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
                pygame.draw.circle(screen, (88, 91, 112), (px, py), 1)


def open_flux_pinning():
    """외부에서 호출하는 진입점."""
    run_simulation()
