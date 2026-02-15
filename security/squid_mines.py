"""SQUID 지뢰찾기 — 정밀 자기장 센서 미니 게임 (Pygame).

- 그리드에 숨겨진 이상 물질(지뢰)
- 마우스(SQUID 센서)가 지뢰에 가까울수록 하단 자기 선속 그래프가 크게 요동
- 클릭으로 지뢰 위치를 마킹, 모두 찾으면 승리
"""

import math
import random

import pygame

# ── 화면 설정 ────────────────────────────────────────
WIDTH, HEIGHT = 900, 650
FPS = 60

# ── 색상 ─────────────────────────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (137, 180, 250)
GRID_CLR = (69, 71, 90)
CELL_SAFE = (49, 50, 68)
CELL_HOVER = (59, 60, 82)
CELL_MARKED = (166, 227, 161)   # 마킹한 셀 (초록)
CELL_WRONG = (243, 139, 168)    # 오답 마킹 (빨강)
MINE_CLR = (249, 226, 175)      # 지뢰 (노랑)
GRAPH_BG = (24, 24, 37)
GRAPH_LINE = (203, 166, 247)    # 자기 선속 그래프 (보라)
GRAPH_PEAK = (243, 139, 168)    # 피크 (빨강)
SENSOR_CLR = (116, 199, 236)    # 센서 커서 글로우

# ── 그리드 설정 ──────────────────────────────────────
GRID_COLS, GRID_ROWS = 10, 8
CELL_SIZE = 52
GRID_OX = (WIDTH - GRID_COLS * CELL_SIZE) // 2
GRID_OY = 60
NUM_MINES = 8

# ── 그래프 설정 ──────────────────────────────────────
GRAPH_X = 50
GRAPH_Y = GRID_OY + GRID_ROWS * CELL_SIZE + 30
GRAPH_W = WIDTH - 100
GRAPH_H = 120
GRAPH_HISTORY = 200  # 샘플 수


# ── 게임 로직 ────────────────────────────────────────

class SQUIDGame:
    """SQUID 지뢰찾기 게임 상태."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.mines: set[tuple[int, int]] = set()
        while len(self.mines) < NUM_MINES:
            c = random.randint(0, GRID_COLS - 1)
            r = random.randint(0, GRID_ROWS - 1)
            self.mines.add((c, r))

        self.marked: set[tuple[int, int]] = set()
        self.wrong: set[tuple[int, int]] = set()
        self.revealed = False  # 게임 종료 시 전체 공개
        self.graph_history: list[float] = [0.0] * GRAPH_HISTORY
        self.won = False
        self.t = 0.0

    def cell_center(self, col: int, row: int) -> tuple[float, float]:
        """셀 중심 화면 좌표."""
        cx = GRID_OX + col * CELL_SIZE + CELL_SIZE / 2
        cy = GRID_OY + row * CELL_SIZE + CELL_SIZE / 2
        return cx, cy

    def flux_intensity(self, mx: float, my: float) -> float:
        """마우스 위치에서의 자기 선속 강도 (0~1).

        모든 지뢰까지의 거리 역수 합 기반.
        """
        total = 0.0
        for (c, r) in self.mines:
            if (c, r) in self.marked:
                continue  # 이미 찾은 지뢰는 제외
            cx, cy = self.cell_center(c, r)
            dist = max(math.hypot(mx - cx, my - cy), 1.0)
            # 가까울수록 기여도 ↑ (역제곱)
            total += (CELL_SIZE * 3) ** 2 / dist ** 2
        return min(total, 1.0)

    def update_graph(self, intensity: float, dt: float):
        """자기 선속 그래프에 새 샘플 추가."""
        self.t += dt
        # 노이즈 + 강도 비례 요동
        noise = random.gauss(0, 0.03 + intensity * 0.15)
        value = intensity * 0.7 + noise + 0.05 * math.sin(self.t * 8)
        value = max(-0.3, min(value, 1.2))
        self.graph_history.append(value)
        if len(self.graph_history) > GRAPH_HISTORY:
            self.graph_history.pop(0)

    def mark_cell(self, col: int, row: int):
        """셀 마킹 (지뢰 예상 위치)."""
        if self.revealed:
            return
        pos = (col, row)
        if pos in self.marked or pos in self.wrong:
            return
        if pos in self.mines:
            self.marked.add(pos)
            # 승리 체크
            if self.marked == self.mines:
                self.won = True
                self.revealed = True
        else:
            self.wrong.add(pos)

    def get_hover_cell(self, mx: int, my: int) -> tuple[int, int] | None:
        """마우스 위치의 그리드 셀 반환."""
        col = (mx - GRID_OX) // CELL_SIZE
        row = (my - GRID_OY) // CELL_SIZE
        if 0 <= col < GRID_COLS and 0 <= row < GRID_ROWS:
            return (col, row)
        return None


# ── 그리기 헬퍼 ──────────────────────────────────────

def _draw_grid(screen, game: SQUIDGame, hover_cell, font):
    """그리드 렌더링."""
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            x = GRID_OX + c * CELL_SIZE
            y = GRID_OY + r * CELL_SIZE
            rect = pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)

            # 셀 배경
            pos = (c, r)
            if pos in game.marked:
                color = CELL_MARKED
            elif pos in game.wrong:
                color = CELL_WRONG
            elif hover_cell == pos:
                color = CELL_HOVER
            else:
                color = CELL_SAFE

            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, GRID_CLR, rect, 1)

            # 게임 종료 시 지뢰 공개
            if game.revealed and pos in game.mines and pos not in game.marked:
                pygame.draw.circle(screen, MINE_CLR, rect.center, CELL_SIZE // 4)

            # 마킹 표시
            if pos in game.marked:
                flag = font.render("M", True, (30, 30, 46))
                screen.blit(flag, (rect.centerx - flag.get_width() // 2, rect.centery - flag.get_height() // 2))
            elif pos in game.wrong:
                x_mark = font.render("X", True, (255, 255, 255))
                screen.blit(x_mark, (rect.centerx - x_mark.get_width() // 2, rect.centery - x_mark.get_height() // 2))


def _draw_sensor_glow(screen, mx: int, my: int, intensity: float, t: float):
    """마우스 주위 센서 글로우."""
    radius = int(20 + 30 * intensity + 5 * math.sin(t * 6))
    alpha = int(30 + 80 * intensity)
    glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(glow, (*SENSOR_CLR, alpha), (radius, radius), radius)
    screen.blit(glow, (mx - radius, my - radius))


def _draw_flux_graph(screen, game: SQUIDGame, intensity: float, font):
    """하단 자기 선속 그래프."""
    # 배경
    pygame.draw.rect(screen, GRAPH_BG, (GRAPH_X, GRAPH_Y, GRAPH_W, GRAPH_H))
    pygame.draw.rect(screen, GRID_CLR, (GRAPH_X, GRAPH_Y, GRAPH_W, GRAPH_H), 1)

    # 제로 라인
    zero_y = GRAPH_Y + GRAPH_H // 2
    pygame.draw.line(screen, GRID_CLR, (GRAPH_X, zero_y), (GRAPH_X + GRAPH_W, zero_y), 1)

    # 그래프 선
    history = game.graph_history
    if len(history) < 2:
        return

    step = GRAPH_W / (GRAPH_HISTORY - 1)
    points = []
    for i, val in enumerate(history):
        px = GRAPH_X + i * step
        py = zero_y - val * (GRAPH_H * 0.45)
        py = max(GRAPH_Y + 2, min(GRAPH_Y + GRAPH_H - 2, py))
        points.append((px, py))

    # 선 색상: 강도에 따라 보라→빨강
    line_color = GRAPH_PEAK if intensity > 0.4 else GRAPH_LINE
    pygame.draw.lines(screen, line_color, False, points, 2)

    # 라벨
    label = font.render("Magnetic Flux (Φ)", True, ACCENT)
    screen.blit(label, (GRAPH_X + 4, GRAPH_Y - 16))

    intensity_txt = font.render(f"Intensity: {intensity:.2f}", True, GRAPH_PEAK if intensity > 0.4 else TEXT_CLR)
    screen.blit(intensity_txt, (GRAPH_X + GRAPH_W - intensity_txt.get_width() - 4, GRAPH_Y - 16))


def _draw_status(screen, game: SQUIDGame, font, big_font):
    """상태 표시."""
    remaining = len(game.mines) - len(game.marked)
    wrong_count = len(game.wrong)

    info = f"남은 지뢰: {remaining}  |  오답: {wrong_count}"
    surf = font.render(info, True, TEXT_CLR)
    screen.blit(surf, (GRID_OX, GRID_OY - 20))

    if game.won:
        win_surf = big_font.render("ALL MINES FOUND — SQUID Scan Complete!", True, CELL_MARKED)
        screen.blit(win_surf, (WIDTH // 2 - win_surf.get_width() // 2, GRAPH_Y + GRAPH_H + 10))
    elif game.revealed and not game.won:
        pass  # 미래 확장: 실패 조건


# ── 메인 시뮬레이션 ──────────────────────────────────

def run_simulation():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("SQUID Minesweeper — Magnetic Flux Sensor")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 12)
    big_font = pygame.font.SysFont("Consolas", 16, bold=True)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)

    game = SQUIDGame()
    t = 0.0

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt
        mx, my = pygame.mouse.get_pos()

        # ── 이벤트 ───────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    game.reset()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                cell = game.get_hover_cell(mx, my)
                if cell:
                    game.mark_cell(*cell)

        # ── 그래프 업데이트 ──────────────────────────
        intensity = game.flux_intensity(mx, my)
        game.update_graph(intensity, dt)

        hover_cell = game.get_hover_cell(mx, my)

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        title = title_font.render("SQUID Minesweeper — Magnetic Flux Sensor", True, ACCENT)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 12))

        # 상태
        _draw_status(screen, game, font, big_font)

        # 그리드
        _draw_grid(screen, game, hover_cell, font)

        # 센서 글로우 (그리드 영역 위에서만)
        if GRID_OY <= my <= GRID_OY + GRID_ROWS * CELL_SIZE:
            _draw_sensor_glow(screen, mx, my, intensity, t)

        # 자기 선속 그래프
        _draw_flux_graph(screen, game, intensity, font)

        # 안내
        hints = [
            "마우스: SQUID 센서 이동  |  클릭: 지뢰 마킹  |  R: 리셋  |  ESC: 종료",
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 22 + i * 16))

        pygame.display.flip()

    pygame.quit()


def open_squid_mines():
    """외부에서 호출하는 진입점."""
    run_simulation()
