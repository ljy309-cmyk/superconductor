"""상전이(Phase Transition) Pygame 시각화 — 원자 격자 진동 + 쿠퍼쌍 애니메이션.

온도를 변화시키면 격자 원자의 진동 폭이 줄어들고,
Tc 이하에서 쿠퍼쌍(Cooper pair)이 형성되며 저항이 0으로 떨어지는
과정을 실시간으로 보여줍니다.

조작:
    Up/Down: 온도 조절
    SPACE: 자동 냉각/가열 토글
    R: 리셋
    ESC: 종료
"""

import math
import random
import sys
import time

import pygame

from config_loader import cfg
from theme import get_pg_theme
from help_overlay import HelpOverlay
from sound_manager import get_sound_manager
from replay import ReplayRecorder
from logger import get_module_logger

_log = get_module_logger("phase_transition_sim")

WIDTH, HEIGHT = 900, 600
FPS = cfg("display", "fps", 60)

BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (137, 180, 250)

# 물리 파라미터
TC_KELVIN = 77.0   # YBCO 임계 온도 (K)
TC_CELSIUS = TC_KELVIN - 273.15

# 격자 설정
GRID_COLS, GRID_ROWS = 12, 8
CELL_SIZE = 50
GRID_OFFSET_X = (WIDTH - GRID_COLS * CELL_SIZE) // 2
GRID_OFFSET_Y = 80

# 색상 (테마에서 동적 로드)
ATOM_NORMAL = (205, 214, 244)
ATOM_SC = (166, 227, 161)       # 초전도 상태
COOPER_CLR = (137, 180, 250)    # 쿠퍼쌍 연결
RESISTANCE_CLR = (243, 139, 168)


def _load_theme_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    global BG, TEXT_CLR, ACCENT, ATOM_NORMAL, ATOM_SC, COOPER_CLR, RESISTANCE_CLR
    global OVERLAY_CLR, SUBTEXT_CLR
    pg = get_pg_theme()
    BG = pg.BG
    TEXT_CLR = pg.TEXT
    ACCENT = pg.ACCENT_BLUE
    ATOM_NORMAL = pg.TEXT
    ATOM_SC = pg.GREEN            # 초전도 = safe color
    COOPER_CLR = pg.ACCENT_BLUE
    RESISTANCE_CLR = pg.RED       # 저항 = danger color
    OVERLAY_CLR = pg.OVERLAY
    SUBTEXT_CLR = pg.SUBTEXT


class Atom:
    """격자 원자."""
    __slots__ = ("base_x", "base_y", "x", "y", "phase")

    def __init__(self, base_x: float, base_y: float):
        self.base_x = base_x
        self.base_y = base_y
        self.x = base_x
        self.y = base_y
        self.phase = random.uniform(0, 2 * math.pi)  # 진동 위상


class CooperPair:
    """쿠퍼쌍 (두 원자 연결)."""
    __slots__ = ("a", "b", "alpha")

    def __init__(self, a: Atom, b: Atom):
        self.a = a
        self.b = b
        self.alpha = 0.0  # 표시 투명도 (0~1)


def run_simulation():
    """Pygame 상전이 시뮬레이션."""
    _load_theme_colors()
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Phase Transition — Lattice Vibration & Cooper Pairs")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 12)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)
    big_font = pygame.font.SysFont("Consolas", 28, bold=True)

    help_overlay = HelpOverlay("flux_pinning")  # flux_pinning 도움말 재사용
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("phase_transition_sim")

    # 격자 원자 생성
    atoms: list[Atom] = []
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            ax = GRID_OFFSET_X + col * CELL_SIZE + CELL_SIZE // 2
            ay = GRID_OFFSET_Y + row * CELL_SIZE + CELL_SIZE // 2
            atoms.append(Atom(ax, ay))

    # 쿠퍼쌍 후보 (인접 원자 쌍)
    cooper_pairs: list[CooperPair] = []
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            idx = row * GRID_COLS + col
            # 수평 쌍
            if col + 1 < GRID_COLS:
                cooper_pairs.append(CooperPair(atoms[idx], atoms[idx + 1]))
            # 수직 쌍
            if row + 1 < GRID_ROWS:
                cooper_pairs.append(CooperPair(atoms[idx], atoms[idx + GRID_COLS]))

    # 상태
    temperature = 300.0  # 현재 온도 (K)
    auto_cool = False
    auto_direction = -1  # -1: 냉각, +1: 가열
    t = 0.0
    start_time = time.time()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt

        for event in pygame.event.get():
            help_overlay.handle_event(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_UP:
                    temperature = min(temperature + 5, 400)
                elif event.key == pygame.K_DOWN:
                    temperature = max(temperature - 5, 1)
                elif event.key == pygame.K_SPACE:
                    auto_cool = not auto_cool
                    if auto_cool and temperature <= TC_KELVIN:
                        auto_direction = 1
                    else:
                        auto_direction = -1
                elif event.key == pygame.K_r:
                    temperature = 300.0
                    auto_cool = False

        # 자동 냉각/가열
        if auto_cool:
            temperature += auto_direction * 30 * dt
            temperature = max(1, min(400, temperature))
            if temperature <= 1:
                auto_direction = 1
            elif temperature >= 400:
                auto_direction = -1

        # 물리 계산
        is_superconducting = temperature <= TC_KELVIN
        vibration_amp = max(0.0, (temperature / 300.0)) * 12  # 온도 비례 진동
        resistance_val = 0.0 if is_superconducting else min(1.0, (temperature - TC_KELVIN) / 200.0)

        # 원자 진동 업데이트
        for atom in atoms:
            if vibration_amp > 0.1:
                atom.x = atom.base_x + vibration_amp * math.sin(t * 8 + atom.phase)
                atom.y = atom.base_y + vibration_amp * math.cos(t * 6 + atom.phase * 1.3)
            else:
                atom.x = atom.base_x
                atom.y = atom.base_y

        # 쿠퍼쌍 alpha 업데이트
        target_alpha = 1.0 if is_superconducting else 0.0
        for cp in cooper_pairs:
            cp.alpha += (target_alpha - cp.alpha) * dt * 3

        # 리플레이 기록
        recorder.record_frame({
            "temperature": round(temperature, 1),
            "superconducting": is_superconducting,
            "resistance": round(resistance_val, 3),
        })

        # ── 렌더링 ──────────────────────
        screen.fill(BG)

        # 타이틀
        title_surf = title_font.render("Superconducting Phase Transition", True, ACCENT)
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 12))

        # 쿠퍼쌍 연결선
        for cp in cooper_pairs:
            if cp.alpha > 0.05:
                surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                alpha = int(cp.alpha * 100)
                pygame.draw.line(surf, (*COOPER_CLR, alpha),
                                 (int(cp.a.x), int(cp.a.y)),
                                 (int(cp.b.x), int(cp.b.y)), 2)
                screen.blit(surf, (0, 0))

        # 원자 그리기
        atom_color = ATOM_SC if is_superconducting else ATOM_NORMAL
        atom_radius = 8 if is_superconducting else 6
        for atom in atoms:
            # 글로우 (초전도 상태)
            if is_superconducting:
                glow_r = atom_radius + 4 + int(2 * math.sin(t * 3 + atom.phase))
                glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, (*ATOM_SC, 40), (glow_r, glow_r), glow_r)
                screen.blit(glow_surf, (int(atom.x) - glow_r, int(atom.y) - glow_r))
            pygame.draw.circle(screen, atom_color, (int(atom.x), int(atom.y)), atom_radius)

        # 온도 표시
        temp_c = temperature - 273.15
        temp_color = ATOM_SC if is_superconducting else RESISTANCE_CLR
        temp_surf = big_font.render(f"{temperature:.0f} K  ({temp_c:.0f} °C)", True, temp_color)
        screen.blit(temp_surf, (WIDTH // 2 - temp_surf.get_width() // 2, HEIGHT - 160))

        # 상태 표시
        state_text = "SUPERCONDUCTING (R = 0)" if is_superconducting else f"NORMAL (R = {resistance_val:.2f})"
        state_color = ATOM_SC if is_superconducting else RESISTANCE_CLR
        state_surf = title_font.render(state_text, True, state_color)
        screen.blit(state_surf, (WIDTH // 2 - state_surf.get_width() // 2, HEIGHT - 125))

        # Tc 표시
        tc_surf = font.render(f"Tc = {TC_KELVIN:.0f} K ({TC_CELSIUS:.0f} °C)  |  Material: YBCO", True, TEXT_CLR)
        screen.blit(tc_surf, (WIDTH // 2 - tc_surf.get_width() // 2, HEIGHT - 100))

        # 저항 바
        bar_x, bar_w, bar_h = 50, 30, 400
        bar_y = 100
        pygame.draw.rect(screen, OVERLAY_CLR, (bar_x, bar_y, bar_w, bar_h))
        fill_h = int(bar_h * resistance_val)
        if fill_h > 0:
            pygame.draw.rect(screen, RESISTANCE_CLR, (bar_x, bar_y + bar_h - fill_h, bar_w, fill_h))
        pygame.draw.rect(screen, TEXT_CLR, (bar_x, bar_y, bar_w, bar_h), 1)
        r_label = font.render("R", True, TEXT_CLR)
        screen.blit(r_label, (bar_x + bar_w // 2 - r_label.get_width() // 2, bar_y - 16))

        # 온도 바
        tbar_x = WIDTH - 80
        pygame.draw.rect(screen, OVERLAY_CLR, (tbar_x, bar_y, bar_w, bar_h))
        t_fill = int(bar_h * min(temperature / 400.0, 1.0))
        t_color = RESISTANCE_CLR if temperature > TC_KELVIN else ATOM_SC
        if t_fill > 0:
            pygame.draw.rect(screen, t_color, (tbar_x, bar_y + bar_h - t_fill, bar_w, t_fill))
        pygame.draw.rect(screen, TEXT_CLR, (tbar_x, bar_y, bar_w, bar_h), 1)
        t_label = font.render("T", True, TEXT_CLR)
        screen.blit(t_label, (tbar_x + bar_w // 2 - t_label.get_width() // 2, bar_y - 16))

        # Tc 마크
        tc_ratio = TC_KELVIN / 400.0
        tc_mark_y = bar_y + bar_h - int(bar_h * tc_ratio)
        pygame.draw.line(screen, RESISTANCE_CLR, (tbar_x - 5, tc_mark_y), (tbar_x + bar_w + 5, tc_mark_y), 2)
        tc_mark_label = font.render("Tc", True, RESISTANCE_CLR)
        screen.blit(tc_mark_label, (tbar_x + bar_w + 8, tc_mark_y - 6))

        # 조작법
        auto_txt = "ON" if auto_cool else "OFF"
        hints = [
            f"Up/Down: Temp  |  SPACE: Auto ({auto_txt})  |  R: Reset  |  ESC: Exit",
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 70 + i * 16))

        # 물리 설명
        if is_superconducting:
            desc = "Cooper pairs formed — zero resistance — Meissner effect active"
        else:
            desc = "Lattice vibrations scatter electrons — finite resistance"
        desc_surf = font.render(desc, True, SUBTEXT_CLR)
        screen.blit(desc_surf, (WIDTH // 2 - desc_surf.get_width() // 2, 48))

        help_overlay.draw(screen, font)
        pygame.display.flip()

    # 종료 처리
    play_time = round(time.time() - start_time, 1)
    try:
        from data_ai.play_logger import get_logger
        get_logger().log_session("phase_transition_sim", {
            "play_time": play_time,
            "final_temp": round(temperature, 1),
        })
    except Exception as e:
        _log.warning("세션 로깅 실패: %s", e)

    recorder.save({"play_time": play_time})
    snd.quit()
    pygame.quit()


def open_phase_transition_sim():
    """외부에서 호출하는 진입점."""
    run_simulation()
