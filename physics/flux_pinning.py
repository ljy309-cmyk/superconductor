"""마이스너 부상 & 플럭스 피닝 시뮬레이션 (Pygame)."""

import math
import sys

import pygame

# ── 화면 설정 ────────────────────────────────────────
WIDTH, HEIGHT = 800, 500
FPS = 60

# ── 색상 ─────────────────────────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
MAGNET_N = (235, 90, 90)   # 빨강 (N극)
MAGNET_S = (100, 130, 235)  # 파랑 (S극)
SC_COLOR = (166, 227, 161)  # 초전도체 (초록)
SC_GLOW = (137, 180, 250)   # 부상 글로우
FIELD_CLR = (88, 91, 112, 60)

# ── 물리 파라미터 ────────────────────────────────────
EQUILIBRIUM_GAP = 65.0   # 자석-초전도체 평형 거리 (px)
SPRING_K = 4.0           # 스프링 상수 k
DAMPING = 0.88           # 감쇠 계수
LEVITATION_AMP = 4.0     # sin 부상 진폭 (px)
LEVITATION_FREQ = 2.0    # sin 부상 주파수 (Hz)

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
    flipped = False  # 자석 뒤집힘 여부
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
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if abs(mx - magnet_x) < MAGNET_W / 2 and abs(my - magnet_y) < MAGNET_H / 2:
                    dragging = True
            elif event.type == pygame.MOUSEBUTTONUP:
                dragging = False

        if dragging:
            magnet_x, magnet_y = pygame.mouse.get_pos()

        # ── 물리 연산 ────────────────────────────────
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
        _draw_superconductor(screen, sc_x, draw_sc_y, t)

        # 연결선 (스프링 시각화)
        pygame.draw.line(
            screen, (88, 91, 112),
            (int(magnet_x), int(magnet_y)),
            (int(sc_x), int(draw_sc_y)),
            1,
        )

        # 안내 텍스트
        hints = [
            "마우스 드래그: 자석 이동",
            "F 키: 자석 뒤집기 (플럭스 피닝 확인)",
            "ESC: 종료",
            f"상태: {'FLIPPED (뒤집힘)' if flipped else 'NORMAL'}",
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


def _draw_superconductor(screen, cx, cy, t):
    """초전도체 (글로우 효과 포함)."""
    rect = pygame.Rect(cx - SC_W / 2, cy - SC_H / 2, SC_W, SC_H)

    # 글로우 (반투명 사각형 확장)
    glow_alpha = int(80 + 40 * math.sin(t * 3))
    glow_surf = pygame.Surface((SC_W + 16, SC_H + 16), pygame.SRCALPHA)
    glow_surf.fill((*SC_GLOW, glow_alpha))
    screen.blit(glow_surf, (rect.x - 8, rect.y - 8))

    # 본체
    pygame.draw.rect(screen, SC_COLOR, rect, border_radius=6)
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
