"""SQUID 지뢰찾기 — 정밀 자기장 센서 미니 게임 (Pygame).

- 그리드에 숨겨진 이상 물질(지뢰)
- 마우스(SQUID 센서)가 지뢰에 가까울수록 하단 자기 선속 그래프가 크게 요동
- 클릭으로 지뢰 위치를 마킹, 모두 찾으면 승리
- 미션1: 거리 기반 경고음 (삐-삐-삐, 가까울수록 빨라짐)
- 미션2: 가장 가까운 타겟 기반 신호 + 근접 타겟 수 표시
- 미션3: 센서 민감도 ↑↓ 키 런타임 튜닝
"""

import array
import math
import random
from dataclasses import dataclass

import pygame

from config_loader import cfg
from theme import load_pg_colors, on_theme_change
from ui.slider import SliderPanel, PANEL_W
from preset_hud import PresetHUD
from help_overlay import HelpOverlay
from sound_manager import get_sound_manager
from replay import ReplayRecorder
from quit_dialog import confirm_quit
from sim_speed import apply_speed, cycle_sim_speed, speed_label
from game_base import finalize_session, choose_difficulty_or_quit
from logger import get_module_logger

_log = get_module_logger("squid_mines")

# ── 화면 설정 ────────────────────────────────────────
WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 650)
FPS = cfg("display", "fps", 60)

# ── 색상 (테마에서 동적 로드) ─────────────────────────
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


_COLOR_MAP = {
    "BG": "BG", "TEXT_CLR": "TEXT", "ACCENT": "ACCENT_BLUE",
    "GRID_CLR": "OVERLAY", "CELL_MARKED": "GREEN", "CELL_WRONG": "RED",
    "GRAPH_BG": "PANEL_BG", "GRAPH_LINE": "ACCENT_PURPLE", "GRAPH_PEAK": "RED",
    "SENSOR_CLR": "SENSOR_CLR", "WHITE": "WHITE",
}


def _load_theme_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    load_pg_colors(_COLOR_MAP, globals())

# ── 그리드 설정 (config.json에서 로드) ────────────────
GRID_COLS = cfg("squid_mines", "grid_cols", 10)
GRID_ROWS = cfg("squid_mines", "grid_rows", 8)
CELL_SIZE = 52
GRID_OX = (WIDTH - GRID_COLS * CELL_SIZE) // 2
GRID_OY = 60
NUM_MINES = cfg("squid_mines", "num_mines", 8)

# ── 그래프 설정 ──────────────────────────────────────
GRAPH_X = 50
GRAPH_Y = GRID_OY + GRID_ROWS * CELL_SIZE + 30
GRAPH_W = WIDTH - 100
GRAPH_H = 120
GRAPH_HISTORY = 200  # 샘플 수

# ── 센서 민감도 (config.json에서 로드) ────────────────
SENSITIVITY_DEFAULT = cfg("squid_mines", "sensitivity_default", 3.0)
SENSITIVITY_MIN = cfg("squid_mines", "sensitivity_min", 1.0)
SENSITIVITY_MAX = cfg("squid_mines", "sensitivity_max", 8.0)
SENSITIVITY_STEP = 0.5

# ── 사운드 (config.json에서 로드) ────────────────────
BEEP_FREQ = cfg("squid_mines", "beep_freq", 880)
BEEP_DURATION_MS = cfg("squid_mines", "beep_duration_ms", 60)
BEEP_INTERVAL_MAX = 1.0       # 최대 간격 (초, intensity=0)
BEEP_INTERVAL_MIN = 0.08      # 최소 간격 (초, intensity=1)


# ── 사운드 생성 헬퍼 (미션1) ────────────────────────

def _make_beep_sound(freq: int = BEEP_FREQ, duration_ms: int = BEEP_DURATION_MS,
                     sample_rate: int = 22050, volume: float = 0.3) -> pygame.mixer.Sound:
    """사인파 기반 경고 비프음 생성."""
    n_samples = int(sample_rate * duration_ms / 1000)
    buf = array.array("h", [0] * n_samples)
    max_amp = int(32767 * volume)
    for i in range(n_samples):
        t = i / sample_rate
        # 부드러운 엔벨로프 (페이드 인/아웃)
        env = min(i / (n_samples * 0.1 + 1), 1.0, (n_samples - i) / (n_samples * 0.1 + 1))
        buf[i] = int(max_amp * env * math.sin(2 * math.pi * freq * t))
    return pygame.mixer.Sound(buffer=buf)


# ── 게임 루프 상태 데이터클래스 ───────────────────────

@dataclass
class SQUIDMinesState:
    """SQUID 지뢰찾기 게임 루프 상태."""
    t: float = 0.0
    beep_timer: float = 0.0
    sound_enabled: bool = True
    kb_col: int = 0
    kb_row: int = 0
    kb_active: bool = False

    def reset(self):
        """게임 루프 상태 리셋."""
        self.beep_timer = 0.0


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
        self._undo_stack: list[tuple[tuple[int, int], str]] = []

    def cell_center(self, col: int, row: int) -> tuple[float, float]:
        """셀 중심 화면 좌표."""
        cx = GRID_OX + col * CELL_SIZE + CELL_SIZE / 2
        cy = GRID_OY + row * CELL_SIZE + CELL_SIZE / 2
        return cx, cy

    def flux_intensity(self, mx: float, my: float,
                       sensitivity: float = SENSITIVITY_DEFAULT) -> tuple[float, float, int]:
        """마우스 위치에서의 자기 선속 강도.

        미션2: 가장 가까운 타겟 기반 신호 + 근접 타겟 수
        미션3: sensitivity로 감지 범위/강도 조절

        Returns:
            (intensity 0~1, nearest_dist, nearby_count)
        """
        unfound = [(c, r) for (c, r) in self.mines if (c, r) not in self.marked]
        if not unfound:
            return (0.0, 9999.0, 0)

        # 미션2: 각 타겟까지 거리 계산 → 최근접 기반
        distances: list[float] = []
        for (c, r) in unfound:
            cx, cy = self.cell_center(c, r)
            distances.append(math.hypot(mx - cx, my - cy))

        nearest_dist = min(distances)
        # 근접 타겟 수 (감지 반경 내)
        detect_radius = CELL_SIZE * sensitivity
        nearby_count = sum(1 for d in distances if d < detect_radius)

        # 미션3: 민감도에 따른 강도 — 가까울수록 + 민감도 높을수록 강한 신호
        ref = CELL_SIZE * sensitivity
        intensity = (ref / max(nearest_dist, 1.0)) ** 2
        # 근접 타겟이 여러 개면 보너스 (+10% per extra)
        intensity *= 1.0 + 0.1 * max(nearby_count - 1, 0)
        intensity = min(intensity, 1.0)

        return (intensity, nearest_dist, nearby_count)

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
            self._undo_stack.append((pos, "marked"))
            # 승리 체크
            if self.marked == self.mines:
                self.won = True
                self.revealed = True
        else:
            self.wrong.add(pos)
            self._undo_stack.append((pos, "wrong"))

    def undo_mark(self) -> tuple[tuple[int, int], str] | None:
        """마지막 마킹을 실행취소. 되돌린 (pos, kind)를 반환, 없으면 None."""
        if self.revealed or not self._undo_stack:
            return None
        pos, kind = self._undo_stack.pop()
        if kind == "marked":
            self.marked.discard(pos)
        else:
            self.wrong.discard(pos)
        return (pos, kind)

    def get_hover_cell(self, mx: int, my: int) -> tuple[int, int] | None:
        """마우스 위치의 그리드 셀 반환."""
        col = (mx - GRID_OX) // CELL_SIZE
        row = (my - GRID_OY) // CELL_SIZE
        if 0 <= col < GRID_COLS and 0 <= row < GRID_ROWS:
            return (col, row)
        return None


# ── 그리기 헬퍼 ──────────────────────────────────────

def _draw_grid(screen, game: SQUIDGame, hover_cell, font,
               kb_cell=None):
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
                flag = font.render("M", True, BG)
                screen.blit(flag, (rect.centerx - flag.get_width() // 2, rect.centery - flag.get_height() // 2))
            elif pos in game.wrong:
                x_mark = font.render("X", True, WHITE)
                screen.blit(x_mark, (rect.centerx - x_mark.get_width() // 2, rect.centery - x_mark.get_height() // 2))

            # 키보드 커서 테두리
            if kb_cell == pos:
                pygame.draw.rect(screen, ACCENT, rect, 3)


def _draw_sensor_glow(screen, mx: int, my: int, intensity: float, t: float):
    """마우스 주위 센서 글로우."""
    radius = int(20 + 30 * intensity + 5 * math.sin(t * 6))
    alpha = int(30 + 80 * intensity)
    glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(glow, (*SENSOR_CLR, alpha), (radius, radius), radius)
    screen.blit(glow, (mx - radius, my - radius))


def _draw_flux_graph(screen, game: SQUIDGame, intensity: float,
                     nearest_dist: float, nearby_count: int,
                     sensitivity: float, font):
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
    label = font.render("Magnetic Flux (\u03a6)", True, ACCENT)
    screen.blit(label, (GRAPH_X + 4, GRAPH_Y - 16))

    # 미션2: 근접 타겟 수 + 거리 표시
    info_parts = [
        f"Intensity: {intensity:.2f}",
        f"Nearest: {nearest_dist:.0f}px",
        f"Nearby: {nearby_count}",
        f"Sens: x{sensitivity:.1f}",
    ]
    info_str = "  |  ".join(info_parts)
    info_clr = GRAPH_PEAK if intensity > 0.4 else TEXT_CLR
    info_surf = font.render(info_str, True, info_clr)
    screen.blit(info_surf, (GRAPH_X + GRAPH_W - info_surf.get_width() - 4, GRAPH_Y - 16))


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
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    # 미션1: 사운드 초기화
    pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
    beep_sound = _make_beep_sound()

    screen = pygame.display.set_mode((WIDTH + PANEL_W, HEIGHT))
    pygame.display.set_caption("SQUID Minesweeper — Magnetic Flux Sensor")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 12)
    big_font = pygame.font.SysFont("Consolas", 16, bold=True)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)

    game = SQUIDGame()
    gs = SQUIDMinesState()

    # ── 슬라이더 패널 ─────────────────────────────────
    panel = SliderPanel(WIDTH + 5, 40, PANEL_W - 10, "Parameters")
    sl_sens = panel.add(SENSITIVITY_MIN, SENSITIVITY_MAX, SENSITIVITY_DEFAULT, 0.5, "Sensitivity", ".1f")

    slider_map = {
        ("squid_mines", "sensitivity_default"): sl_sens,
    }
    preset_hud = PresetHUD("squid_mines", slider_map)
    help_overlay = HelpOverlay("squid_mines")
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("squid_mines")

    # ── 시작 시 난이도 선택 ──
    if not choose_difficulty_or_quit(screen, font, preset_hud, _load_theme_colors):
        snd.quit()
        pygame.mixer.quit()
        return

    running = True
    while running:
        raw_dt = clock.tick(FPS) / 1000.0
        dt = apply_speed(raw_dt)
        gs.t += dt
        mx, my = pygame.mouse.get_pos()

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
                elif event.key == pygame.K_z and (event.mod & pygame.KMOD_CTRL):
                    if game.undo_mark():
                        snd.play("undo")
                elif event.key == pygame.K_u:
                    if game.undo_mark():
                        snd.play("undo")
                elif event.key == pygame.K_r:
                    game.reset()
                    panel.reset_all()
                    gs.reset()
                elif event.key == pygame.K_UP:
                    sl_sens.value = sl_sens.value + SENSITIVITY_STEP
                elif event.key == pygame.K_DOWN:
                    sl_sens.value = sl_sens.value - SENSITIVITY_STEP
                elif event.key == pygame.K_LEFTBRACKET:
                    cycle_sim_speed(-1)
                elif event.key == pygame.K_RIGHTBRACKET:
                    cycle_sim_speed(1)
                elif event.key == pygame.K_m:
                    # 미션1: 사운드 토글 (handle_key에서 snd.toggle 호출됨)
                    gs.sound_enabled = snd.enabled
                # ── 키보드 그리드 탐색 (WASD) ──
                elif event.key == pygame.K_w:
                    gs.kb_active = True
                    gs.kb_row = max(0, gs.kb_row - 1)
                elif event.key == pygame.K_s:
                    gs.kb_active = True
                    gs.kb_row = min(GRID_ROWS - 1, gs.kb_row + 1)
                elif event.key == pygame.K_a:
                    gs.kb_active = True
                    gs.kb_col = max(0, gs.kb_col - 1)
                elif event.key == pygame.K_d:
                    gs.kb_active = True
                    gs.kb_col = min(GRID_COLS - 1, gs.kb_col + 1)
                elif event.key == pygame.K_RETURN:
                    # 키보드: 현재 커서 위치 마킹
                    if gs.kb_active:
                        prev_marked = len(game.marked)
                        prev_wrong = len(game.wrong)
                        game.mark_cell(gs.kb_col, gs.kb_row)
                        if len(game.marked) > prev_marked:
                            snd.play("mine_found")
                            if game.won:
                                snd.play("victory")
                        elif len(game.wrong) > prev_wrong:
                            snd.play("wrong_mark")
            elif event.type == pygame.MOUSEBUTTONDOWN:
                cell = game.get_hover_cell(mx, my)
                if cell:
                    prev_marked = len(game.marked)
                    prev_wrong = len(game.wrong)
                    game.mark_cell(*cell)
                    if len(game.marked) > prev_marked:
                        snd.play("mine_found")
                        if game.won:
                            snd.play("victory")
                    elif len(game.wrong) > prev_wrong:
                        snd.play("wrong_mark")

        # ── 슬라이더 값 읽기 ─────────────────────────
        preset_hud.update(dt)
        sensitivity = sl_sens.value

        # ── 그래프 업데이트 ──────────────────────────
        intensity, nearest_dist, nearby_count = game.flux_intensity(mx, my, sensitivity)
        game.update_graph(intensity, dt)

        # ── 미션1: 거리 기반 경고음 ──────────────────
        if gs.sound_enabled and intensity > 0.05 and not game.won:
            # 가까울수록 간격 짧아짐 (선형 보간)
            interval = BEEP_INTERVAL_MAX - (BEEP_INTERVAL_MAX - BEEP_INTERVAL_MIN) * intensity
            gs.beep_timer -= dt
            if gs.beep_timer <= 0:
                beep_sound.play()
                gs.beep_timer = interval
        else:
            gs.beep_timer = 0.0

        hover_cell = game.get_hover_cell(mx, my)

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        title = title_font.render("SQUID Minesweeper — Magnetic Flux Sensor", True, ACCENT)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 12))

        # 상태
        _draw_status(screen, game, font, big_font)

        # 그리드
        kb_cell = (gs.kb_col, gs.kb_row) if gs.kb_active else None
        _draw_grid(screen, game, hover_cell, font, kb_cell=kb_cell)

        # 센서 글로우 (그리드 영역 위에서만)
        if GRID_OY <= my <= GRID_OY + GRID_ROWS * CELL_SIZE:
            _draw_sensor_glow(screen, mx, my, intensity, gs.t)

        # 자기 선속 그래프
        _draw_flux_graph(screen, game, intensity, nearest_dist, nearby_count, sensitivity, font)

        # 슬라이더 패널 그리기
        panel.draw(screen, font)

        # 안내
        hints = [
            f"민감도: x{sensitivity:.1f}  |  사운드: {'ON' if gs.sound_enabled else 'OFF'}  |  근접: {nearby_count}개",
            "마우스: SQUID 센서  |  클릭/Enter: 마킹  |  U/Ctrl+Z: 실행취소  |  WASD: 커서 이동",
            f"↑↓: 민감도  |  M: 사운드  |  [/]: 속도 ({speed_label()})  |  R: 리셋  |  ESC: 종료",
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 52 + i * 16))

        preset_hud.draw(screen)
        help_overlay.draw(screen)

        pygame.display.flip()

    finalize_session("squid_mines", {
        "mines_found": len(game.marked),
        "wrong_marks": len(game.wrong),
        "total_mines": len(game.mines),
        "sensitivity": sensitivity,
        "won": game.won,
    }, recorder=recorder, snd=snd, theme_callback=_load_theme_colors,
       extra_cleanup=pygame.mixer.quit)


def open_squid_mines():
    """외부에서 호출하는 진입점."""
    run_simulation()
