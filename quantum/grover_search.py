"""Grover's Search Algorithm 시각화 (Pygame).

3가지 모드:
  1. Step-by-Step: 탐색 단계를 하나씩 진행하며 시각화
  2. Auto: 자동 실행으로 전체 과정 애니메이션
  3. Compare: 고전 O(N) vs 양자 O(√N) 속도 대결
"""

import math
import random
import time
from dataclasses import dataclass, field

import pygame

from achievement_toast import AchievementToast
from config_loader import cfg
from game_base import finalize_session
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from perf_monitor import PerfMonitor
from quantum.grover_search_engine import (
    GroverPhase,
    GroverState,
    get_phase_description,
    get_quantum_advantage_message,
    grover_step,
    reset_state,
    get_probabilities,
)
from presets import get_preset
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from sound_manager import get_sound_manager
from theme import load_pg_colors, on_theme_change
from tutorial import TutorialOverlay

_log = get_module_logger("grover_search")

# ── 화면 설정 ────────────────────────────────────────
WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
FPS = cfg("display", "fps", 60)

# ── Grover UI 설정 ───────────────────────────────────
ANIMATION_SPEED = cfg("grover", "animation_speed", 0.5)
AUTO_BATCH_SIZE = cfg("grover", "auto_batch_size", 1)
DISPLAY_STATES = cfg("grover", "display_states", 32)

# ── 색상 (테마에서 동적 로드) ────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (137, 180, 250)
GREEN = (166, 227, 161)
RED = (243, 139, 168)
YELLOW = (249, 226, 175)
PURPLE = (203, 166, 247)
TEAL = (148, 226, 213)
OVERLAY_CLR = (49, 50, 68)
WHITE = (255, 255, 255)
PANEL_BG = (24, 24, 37)
SUBTEXT = (108, 112, 134)

_COLOR_MAP = {
    "BG": "BG",
    "TEXT_CLR": "TEXT",
    "ACCENT": "ACCENT_BLUE",
    "GREEN": "STABLE",
    "RED": "COLLAPSED",
    "YELLOW": "WARNING",
    "PURPLE": "ACCENT_PURPLE",
    "TEAL": "TEAL",
    "OVERLAY_CLR": "OVERLAY",
    "WHITE": "WHITE",
    "PANEL_BG": "PANEL_BG",
    "SUBTEXT": "SUBTEXT",
}


def _load_theme_colors():
    load_pg_colors(_COLOR_MAP, globals())


# ── 모드 ─────────────────────────────────────────────
MODE_STEP = 0
MODE_AUTO = 1
MODE_COMPARE = 2
MODE_NAMES = ["Step-by-Step", "Auto Run", "Classical vs Quantum"]


# ── UI 상태 ──────────────────────────────────────────

@dataclass
class UIState:
    """UI 전체 상태."""
    mode: int = MODE_STEP
    t: float = 0.0
    start_time: float = field(default_factory=time.time)

    # Grover 엔진 상태
    grover: GroverState = field(default_factory=lambda: GroverState(
        n_qubits=4, targets=[7]))

    # Auto 모드
    auto_running: bool = False
    auto_timer: float = 0.0
    auto_interval: float = ANIMATION_SPEED

    # Compare 모드
    compare_running: bool = False
    compare_classical_pos: float = 0.0    # 고전 탐색 진행 (0~1)
    compare_quantum_pos: float = 0.0      # 양자 탐색 진행 (0~1)
    compare_classical_done: bool = False
    compare_quantum_done: bool = False
    compare_timer: float = 0.0
    compare_n_qubits: int = 4

    # 입력
    input_buffer: str = "4"
    input_target_buffer: str = "7"
    input_active: int = 0          # 0=비활성, 1=큐빗, 2=대상
    input_field: int = 0

    # 난이도
    difficulty: str = "normal"

    # 통계
    searches_completed: int = 0
    total_steps: int = 0


# ── 그리기 유틸리티 ──────────────────────────────────

def _draw_panel(screen, x, y, w, h, title="", title_font=None, font=None):
    """둥근 패널."""
    pygame.draw.rect(screen, PANEL_BG, (x, y, w, h), border_radius=6)
    pygame.draw.rect(screen, OVERLAY_CLR, (x, y, w, h), 1, border_radius=6)
    if title and title_font:
        ts = title_font.render(title, True, ACCENT)
        screen.blit(ts, (x + 10, y + 6))


def _draw_progress_bar(screen, x, y, w, h, progress, color=ACCENT):
    """진행률 바 (0.0 ~ 1.0)."""
    pygame.draw.rect(screen, OVERLAY_CLR, (x, y, w, h), border_radius=3)
    fill_w = max(0, int(w * min(1.0, progress)))
    if fill_w > 0:
        pygame.draw.rect(screen, color, (x, y, fill_w, h), border_radius=3)
    pygame.draw.rect(screen, TEXT_CLR, (x, y, w, h), 1, border_radius=3)


def _draw_phase_indicator(screen, phase, font, x, y):
    """현재 단계 표시 (좌측 패널)."""
    phases = [
        (GroverPhase.INIT_SUPERPOSITION, t("grover_phase_superposition")),
        (GroverPhase.ORACLE, t("grover_phase_oracle")),
        (GroverPhase.DIFFUSION, t("grover_phase_diffusion")),
        (GroverPhase.ITERATE, t("grover_phase_iterate")),
        (GroverPhase.MEASURE, t("grover_phase_measure")),
    ]
    for i, (ph, label) in enumerate(phases):
        py = y + i * 22
        is_current = (phase == ph)
        is_done = (phase.value > ph.value)

        if is_current:
            clr = ACCENT
            marker = "▶"
        elif is_done:
            clr = GREEN
            marker = "✓"
        else:
            clr = SUBTEXT
            marker = "·"

        s = font.render(f" {marker} {label}", True, clr)
        screen.blit(s, (x, py))


def _draw_amplitude_bar_chart(screen, grover, font, x, y, w, h):
    """진폭/확률 바 차트 — 핵심 시각화."""
    if not grover.amplitudes:
        return

    n = len(grover.amplitudes)
    probs = get_probabilities(grover.amplitudes)
    max_val = max(probs) or 1.0
    display_n = min(n, DISPLAY_STATES)
    step = max(1, n // display_n)
    bar_w = max(1, (w - 20) // display_n)

    for i in range(0, n, step):
        idx = i // step
        bx = x + 10 + idx * bar_w
        bar_h = int((h - 35) * probs[i] / max_val)
        by = y + h - 10 - bar_h

        if i in grover.targets:
            clr = YELLOW
        elif probs[i] > max_val * 0.3:
            clr = PURPLE
        else:
            clr = ACCENT

        if bar_h > 0:
            pygame.draw.rect(screen, clr,
                             (bx, by, max(1, bar_w - 1), bar_h))

    # 레이블
    label = font.render(
        f"P(x)  iter={grover.current_iteration}/{grover.optimal_iterations}",
        True, TEXT_CLR)
    screen.blit(label, (x + 10, y + 2))


def _draw_probability_evolution(screen, prob_history, font, x, y, w, h):
    """반복별 목표 확률 변화 라인 차트."""
    if len(prob_history) < 2:
        return

    _draw_panel(screen, x, y, w, h)

    n = len(prob_history)
    max_p = max(max(prob_history), 0.01)
    points = []

    for i, p in enumerate(prob_history):
        px = x + 10 + int((w - 20) * i / max(1, n - 1))
        py_val = y + h - 10 - int((h - 30) * p / max_p)
        points.append((px, py_val))

    if len(points) >= 2:
        pygame.draw.lines(screen, GREEN, False, points, 2)

    # 점 표시
    for px, py_val in points:
        pygame.draw.circle(screen, YELLOW, (px, py_val), 3)

    label = font.render(t("grover_chart_prob_evolution"), True, TEXT_CLR)
    screen.blit(label, (x + 10, y + 2))


def _draw_circuit_diagram(screen, grover, font, x, y, w, h):
    """양자 회로 다이어그램 (간략화)."""
    n_qubits = grover.n_qubits
    display_qubits = min(n_qubits, 6)

    pygame.draw.rect(screen, PANEL_BG, (x, y, w, h), border_radius=4)
    pygame.draw.rect(screen, OVERLAY_CLR, (x, y, w, h), 1, border_radius=4)

    line_start_x = x + 60
    line_end_x = x + w - 20
    line_y_start = y + 30
    line_spacing = max(16, (h - 50) // max(1, display_qubits))

    for i in range(display_qubits):
        ly = line_y_start + i * line_spacing
        ql = font.render("|0⟩", True, TEXT_CLR)
        screen.blit(ql, (x + 10, ly - 6))
        pygame.draw.line(screen, SUBTEXT, (line_start_x, ly),
                         (line_end_x, ly), 1)

    gate_positions = [
        (line_start_x + 30, "H", ACCENT),
        (line_start_x + 100, "O_f", RED),
        (line_start_x + 170, "D", PURPLE),
        (line_start_x + 240, "M", GREEN),
    ]

    phase = grover.phase
    gate_phase_map = {
        "H": GroverPhase.INIT_SUPERPOSITION,
        "O_f": GroverPhase.ORACLE,
        "D": GroverPhase.DIFFUSION,
        "M": GroverPhase.MEASURE,
    }

    for gx, gate_name, color in gate_positions:
        active_phase = gate_phase_map.get(gate_name)
        is_active = (phase == active_phase)
        is_done = phase.value > active_phase.value if active_phase else False

        box_color = color if (is_active or is_done) else OVERLAY_CLR
        border = 2 if is_active else 1

        for i in range(display_qubits):
            ly = line_y_start + i * line_spacing
            bw = 36 if len(gate_name) <= 2 else 44
            rect = pygame.Rect(gx - bw // 2, ly - 10, bw, 20)
            pygame.draw.rect(screen, box_color, rect, border, border_radius=3)

        gs_text = font.render(gate_name, True,
                              WHITE if is_active else box_color)
        screen.blit(gs_text, (gx - gs_text.get_width() // 2,
                              line_y_start - 20))

    # 반복 화살표 (Oracle → Diffusion)
    if grover.current_iteration > 0 and phase.value <= GroverPhase.ITERATE.value:
        arrow_y = line_y_start + display_qubits * line_spacing + 5
        o_x = line_start_x + 100
        d_x = line_start_x + 170
        pygame.draw.line(screen, YELLOW, (d_x, arrow_y), (o_x, arrow_y), 1)
        pygame.draw.polygon(screen, YELLOW, [
            (o_x, arrow_y), (o_x + 6, arrow_y - 4), (o_x + 6, arrow_y + 4)])
        iter_text = font.render(
            f"×{grover.current_iteration}", True, YELLOW)
        screen.blit(iter_text, ((o_x + d_x) // 2 - 8, arrow_y - 14))

    title = font.render(t("grover_circuit_title"), True, ACCENT)
    screen.blit(title, (x + 10, y + 4))


def _draw_input_fields(screen, ui, font, x, y):
    """큐빗/대상 입력 필드."""
    # 큐빗 수
    label1 = font.render(t("grover_input_qubits"), True, TEXT_CLR)
    screen.blit(label1, (x, y))

    box1_x = x + label1.get_width() + 5
    box1_clr = ACCENT if ui.input_active == 1 else OVERLAY_CLR
    pygame.draw.rect(screen, PANEL_BG, (box1_x, y - 2, 50, 22),
                     border_radius=3)
    pygame.draw.rect(screen, box1_clr, (box1_x, y - 2, 50, 22), 2,
                     border_radius=3)
    txt1 = font.render(ui.input_buffer, True, WHITE)
    screen.blit(txt1, (box1_x + 5, y))

    # 대상
    label2 = font.render(t("grover_input_target"), True, TEXT_CLR)
    box2_x = box1_x + 70
    screen.blit(label2, (box2_x, y))

    box2_start = box2_x + label2.get_width() + 5
    box2_clr = ACCENT if ui.input_active == 2 else OVERLAY_CLR
    pygame.draw.rect(screen, PANEL_BG, (box2_start, y - 2, 80, 22),
                     border_radius=3)
    pygame.draw.rect(screen, box2_clr, (box2_start, y - 2, 80, 22), 2,
                     border_radius=3)
    txt2 = font.render(ui.input_target_buffer, True, WHITE)
    screen.blit(txt2, (box2_start + 5, y))

    # 힌트
    hint = font.render(t("grover_input_hint"), True, SUBTEXT)
    screen.blit(hint, (box2_start + 90, y))


def _wrap_text(text, max_chars):
    """텍스트를 max_chars 기준으로 줄바꿈."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > max_chars:
            if current:
                lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(current)
    return lines


# ── 모드별 렌더링 ────────────────────────────────────

def _draw_step_mode(screen, ui, font, title_font, info_font):
    """Step-by-Step 모드."""
    grover = ui.grover

    title = title_font.render(t("grover_title_step"), True, ACCENT)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 42))

    # 큐빗/대상 표시
    n_text = font.render(
        f"N = 2^{grover.n_qubits} = {1 << grover.n_qubits}  "
        f"target = {grover.targets}", True, TEXT_CLR)
    screen.blit(n_text, (20, 70))

    if grover.current_iteration > 0:
        att = font.render(
            f"Iteration {grover.current_iteration}/{grover.optimal_iterations}",
            True, TEAL)
        screen.blit(att, (500, 70))

    # 좌측: 단계 인디케이터
    _draw_phase_indicator(screen, grover.phase, font, 20, 100)

    # 중앙 상단: 양자 회로 다이어그램
    _draw_circuit_diagram(screen, grover, info_font, 200, 90, 380, 130)

    # 우측 상단: 상태 메시지
    _draw_panel(screen, 600, 90, 280, 130, "Status", font, info_font)
    msg_lines = _wrap_text(grover.step_message, 35)
    for i, line in enumerate(msg_lines):
        clr = GREEN if grover.phase == GroverPhase.SUCCESS else TEXT_CLR
        if grover.phase == GroverPhase.FAIL:
            clr = RED
        ms = info_font.render(line, True, clr)
        screen.blit(ms, (610, 115 + i * 16))
    desc_lines = _wrap_text(get_phase_description(grover.phase), 35)
    for i, line in enumerate(desc_lines[:3]):
        ds = info_font.render(line, True, SUBTEXT)
        screen.blit(ds, (610, 170 + i * 14))

    # 중앙 하단: 진폭 바 차트
    if grover.amplitudes:
        _draw_amplitude_bar_chart(screen, grover, info_font,
                                  20, 240, 420, 150)

    # 우측 하단: 확률 변화 그래프
    if len(grover.target_prob_history) >= 2:
        _draw_probability_evolution(screen, grover.target_prob_history,
                                    info_font, 460, 240, 410, 130)

    # 최종 결과
    if grover.phase == GroverPhase.SUCCESS:
        result = title_font.render(
            t("grover_result_found", result=grover.measured,
              iter=grover.current_iteration),
            True, GREEN)
        screen.blit(result, (WIDTH // 2 - result.get_width() // 2, 405))
        if grover.comparison:
            comp = grover.comparison
            speedup = info_font.render(
                f"Classical: ~{comp.classical_expected:.0f} queries  |  "
                f"Grover: {comp.quantum_iterations} queries  |  "
                f"Speedup: {comp.speedup_ratio:.1f}×",
                True, PURPLE)
            screen.blit(speedup,
                        (WIDTH // 2 - speedup.get_width() // 2, 432))
    elif grover.phase == GroverPhase.FAIL:
        result = title_font.render(
            t("grover_result_not_target", result=grover.measured),
            True, RED)
        screen.blit(result, (WIDTH // 2 - result.get_width() // 2, 405))

    # 탐색 히스토리
    if grover.search_history:
        hy = 460
        hist_title = info_font.render(t("grover_search_history"), True, ACCENT)
        screen.blit(hist_title, (20, hy))
        for i, h in enumerate(grover.search_history[-4:]):
            clr = GREEN if h["success"] else YELLOW
            hs = info_font.render(
                f"  {h['n_qubits']}q target={h['targets'][:3]} → "
                f"|{h['measured']}⟩ {'✓' if h['success'] else '✗'} "
                f"({h['iterations']} iters)",
                True, clr)
            screen.blit(hs, (20, hy + 16 + i * 14))

    # 입력 필드
    if grover.phase in (GroverPhase.INPUT, GroverPhase.DONE,
                        GroverPhase.SUCCESS, GroverPhase.FAIL):
        _draw_input_fields(screen, ui, font, 20, HEIGHT - 70)


def _draw_auto_mode(screen, ui, font, title_font, info_font):
    """Auto 모드."""
    grover = ui.grover

    title = title_font.render(t("grover_title_auto"), True, ACCENT)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 42))

    n_text = font.render(
        f"N = 2^{grover.n_qubits} = {1 << grover.n_qubits}  "
        f"target = {grover.targets}", True, TEXT_CLR)
    screen.blit(n_text, (20, 70))

    status = t("grover_auto_running") if ui.auto_running \
        else t("grover_auto_paused")
    status_clr = GREEN if ui.auto_running else YELLOW
    st = font.render(status, True, status_clr)
    screen.blit(st, (400, 70))

    # 진행률
    if grover.phase not in (GroverPhase.DONE, GroverPhase.SUCCESS,
                            GroverPhase.FAIL):
        progress = grover.phase.value / GroverPhase.DONE.value
    else:
        progress = 1.0
    _draw_progress_bar(screen, 520, 72, 200, 14, progress)

    # 단계 인디케이터
    _draw_phase_indicator(screen, grover.phase, font, 20, 100)

    # 회로 다이어그램
    _draw_circuit_diagram(screen, grover, info_font, 200, 90, 380, 130)

    # 상태 메시지
    _draw_panel(screen, 600, 90, 280, 130, "Status", font, info_font)
    msg_lines = _wrap_text(grover.step_message, 35)
    for i, line in enumerate(msg_lines):
        clr = GREEN if grover.phase == GroverPhase.SUCCESS else TEXT_CLR
        ms = info_font.render(line, True, clr)
        screen.blit(ms, (610, 115 + i * 16))

    # 바 차트
    if grover.amplitudes:
        _draw_amplitude_bar_chart(screen, grover, info_font,
                                  20, 240, 560, 160)

    # 확률 변화
    if len(grover.target_prob_history) >= 2:
        _draw_probability_evolution(screen, grover.target_prob_history,
                                    info_font, 600, 240, 280, 130)

    # 결과
    if grover.phase == GroverPhase.SUCCESS:
        result = title_font.render(
            t("grover_result_found", result=grover.measured,
              iter=grover.current_iteration),
            True, GREEN)
        screen.blit(result, (WIDTH // 2 - result.get_width() // 2, 420))

    # 입력 필드
    if grover.phase in (GroverPhase.INPUT, GroverPhase.DONE,
                        GroverPhase.SUCCESS, GroverPhase.FAIL):
        _draw_input_fields(screen, ui, font, 20, HEIGHT - 70)


def _draw_compare_mode(screen, ui, font, title_font, info_font):
    """Classical vs Quantum 비교 모드."""
    title = title_font.render(t("grover_title_compare"), True, ACCENT)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 42))

    n_qubits = ui.compare_n_qubits
    n_states = 1 << n_qubits
    n_text = font.render(
        f"Database: N = 2^{n_qubits} = {n_states} items  |  "
        f"Target: 1 item", True, TEXT_CLR)
    screen.blit(n_text, (20, 70))

    # 레이스 트랙
    track_x = 60
    track_w = WIDTH - 120
    track_y_classical = 140
    track_y_quantum = 220

    # 고전 트랙
    _draw_panel(screen, 20, track_y_classical - 10, WIDTH - 40, 60,
                t("grover_compare_classical"), font, info_font)
    _draw_progress_bar(screen, track_x, track_y_classical + 20,
                       track_w, 20, ui.compare_classical_pos, RED)
    queries_c = int(ui.compare_classical_pos * n_states)
    qc_text = info_font.render(
        f"{queries_c}/{n_states} queries", True, TEXT_CLR)
    screen.blit(qc_text, (track_x + track_w + 5, track_y_classical + 20))

    # 양자 트랙
    opt_iter = max(1, int(math.pi / 4 * math.sqrt(n_states)))
    _draw_panel(screen, 20, track_y_quantum - 10, WIDTH - 40, 60,
                t("grover_compare_quantum"), font, info_font)
    _draw_progress_bar(screen, track_x, track_y_quantum + 20,
                       track_w, 20, ui.compare_quantum_pos, GREEN)
    queries_q = int(ui.compare_quantum_pos * opt_iter)
    qq_text = info_font.render(
        f"{queries_q}/{opt_iter} queries", True, TEXT_CLR)
    screen.blit(qq_text, (track_x + track_w + 5, track_y_quantum + 20))

    # 완료 마커
    if ui.compare_classical_done:
        done_c = font.render(t("grover_compare_found"), True, RED)
        screen.blit(done_c, (track_x + track_w - 55,
                             track_y_classical + 2))
    if ui.compare_quantum_done:
        done_q = font.render(t("grover_compare_found"), True, GREEN)
        screen.blit(done_q, (track_x + track_w - 55,
                             track_y_quantum + 2))

    # 비교 통계
    if ui.compare_classical_done or ui.compare_quantum_done:
        _draw_panel(screen, 40, 300, WIDTH - 80, 120, "", title_font,
                    info_font)

        speedup = n_states / max(1, opt_iter)
        stats = [
            t("grover_compare_stat_classical", N=n_states),
            t("grover_compare_stat_quantum", N=n_states, opt=opt_iter),
            t("grover_compare_speedup", ratio=f"{speedup:.1f}"),
        ]
        for i, line in enumerate(stats):
            clr = [RED, GREEN, YELLOW][i]
            ls = info_font.render(line, True, clr)
            screen.blit(ls, (60, 320 + i * 22))

    # 양자 우위 메시지
    if ui.compare_classical_done and ui.compare_quantum_done:
        _draw_panel(screen, 40, 430, WIDTH - 80, 100, "", title_font,
                    info_font)
        msg_lines = _wrap_text(get_quantum_advantage_message(), 90)
        for i, line in enumerate(msg_lines[:4]):
            ms = info_font.render(line, True, YELLOW)
            screen.blit(ms, (55, 445 + i * 16))

    # 하단 힌트
    hint = info_font.render(
        t("grover_compare_hint_db", n=n_qubits), True, SUBTEXT)
    screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 55))


# ── 메인 시뮬레이션 ──────────────────────────────────

def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(t("game_title_grover"))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 13)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)
    info_font = pygame.font.SysFont("Consolas", 11)

    # 난이도 선택
    from difficulty_dialog import choose_difficulty

    chosen = choose_difficulty(screen, font)
    if chosen is None:
        on_theme_change(_load_theme_colors)  # cleanup
        pygame.quit()
        return
    preset = get_preset(chosen)
    grover_preset = preset.get("grover", {})
    default_qubits = grover_preset.get("default_qubits", 4)
    anim_speed = grover_preset.get("animation_speed", ANIMATION_SPEED)

    ui = UIState()
    ui.grover = GroverState(n_qubits=default_qubits,
                            targets=[random.randint(0, (1 << default_qubits) - 1)])
    ui.input_buffer = str(default_qubits)
    ui.input_target_buffer = str(ui.grover.targets[0])
    ui.auto_interval = anim_speed
    ui.difficulty = chosen
    grover_step(ui.grover)  # INPUT → INIT_SUPERPOSITION

    help_overlay = HelpOverlay("grover_search")
    tutorial = TutorialOverlay("grover_search")
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("grover_search")
    toast = AchievementToast()
    perf = PerfMonitor(target_fps=FPS)

    running = True
    while running:
        raw_dt = clock.tick(FPS) / 1000.0
        dt = raw_dt
        perf.tick(raw_dt)
        ui.t += dt

        # ── Auto 모드 타이머 ──
        if ui.mode == MODE_AUTO and ui.auto_running:
            ui.auto_timer += dt
            if ui.auto_timer >= ui.auto_interval:
                ui.auto_timer = 0.0
                for _ in range(AUTO_BATCH_SIZE):
                    if ui.grover.phase not in (GroverPhase.SUCCESS,
                                               GroverPhase.FAIL,
                                               GroverPhase.DONE):
                        grover_step(ui.grover)
                        ui.total_steps += 1
                        if ui.grover.phase == GroverPhase.SUCCESS:
                            ui.searches_completed += 1
                            snd.play("achievement")
                            ui.auto_running = False
                            break
                        if ui.grover.phase == GroverPhase.FAIL:
                            ui.auto_running = False
                            break
                    else:
                        ui.auto_running = False
                        break

        # ── Compare 모드 타이머 ──
        if ui.mode == MODE_COMPARE and ui.compare_running:
            ui.compare_timer += dt
            n_states = 1 << ui.compare_n_qubits
            opt_iter = max(1, int(math.pi / 4 * math.sqrt(n_states)))
            speed = 2.0  # 초당 진행 비율

            # 양자: 빠르게 완료
            if not ui.compare_quantum_done:
                ui.compare_quantum_pos += speed * dt
                if ui.compare_quantum_pos >= 1.0:
                    ui.compare_quantum_pos = 1.0
                    ui.compare_quantum_done = True
                    snd.play("achievement")

            # 고전: 느리게 진행 (speedup 비율만큼)
            if not ui.compare_classical_done:
                classical_speed = speed * opt_iter / n_states
                ui.compare_classical_pos += classical_speed * dt
                if ui.compare_classical_pos >= 1.0:
                    ui.compare_classical_pos = 1.0
                    ui.compare_classical_done = True

            if ui.compare_classical_done and ui.compare_quantum_done:
                ui.compare_running = False

        # ── 이벤트 ──
        for event in pygame.event.get():
            if tutorial.handle_event(event):
                continue
            help_overlay.handle_event(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                snd.handle_key(event.key)

                # 입력 모드 처리
                if ui.input_active > 0:
                    if event.key == pygame.K_RETURN:
                        _submit_input(ui, snd)
                    elif event.key == pygame.K_TAB:
                        # 필드 전환
                        ui.input_active = 2 if ui.input_active == 1 else 1
                    elif event.key == pygame.K_BACKSPACE:
                        if ui.input_active == 1:
                            ui.input_buffer = ui.input_buffer[:-1]
                        else:
                            ui.input_target_buffer = \
                                ui.input_target_buffer[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        ui.input_active = 0
                    elif (event.unicode.isdigit()
                          or event.unicode == ','):
                        if ui.input_active == 1 and \
                                len(ui.input_buffer) < 3:
                            ui.input_buffer += event.unicode
                        elif ui.input_active == 2 and \
                                len(ui.input_target_buffer) < 12:
                            ui.input_target_buffer += event.unicode
                    continue

                if event.key == pygame.K_ESCAPE:
                    if confirm_quit(screen, info_font):
                        running = False

                elif event.key == pygame.K_TAB:
                    ui.mode = (ui.mode + 1) % 3
                    _on_mode_change(ui)
                    snd.play("click")

                elif event.key == pygame.K_l:
                    toggle_locale()

                elif event.key == pygame.K_n:
                    ui.input_active = 1

                # ── Step 모드 키 ──
                elif ui.mode == MODE_STEP:
                    if event.key == pygame.K_SPACE:
                        if ui.grover.phase not in (GroverPhase.SUCCESS,
                                                   GroverPhase.FAIL,
                                                   GroverPhase.DONE):
                            grover_step(ui.grover)
                            ui.total_steps += 1
                            snd.play("click")
                            if ui.grover.phase == GroverPhase.SUCCESS:
                                ui.searches_completed += 1
                                snd.play("achievement")
                        else:
                            ui.input_active = 1
                    elif event.key == pygame.K_r:
                        reset_state(ui.grover)
                        grover_step(ui.grover)
                        snd.play("click")

                # ── Auto 모드 키 ──
                elif ui.mode == MODE_AUTO:
                    if event.key == pygame.K_SPACE:
                        if ui.grover.phase in (GroverPhase.SUCCESS,
                                               GroverPhase.FAIL,
                                               GroverPhase.DONE):
                            ui.input_active = 1
                        else:
                            ui.auto_running = not ui.auto_running
                            snd.play("click")
                    elif event.key == pygame.K_r:
                        ui.auto_running = False
                        reset_state(ui.grover)
                        grover_step(ui.grover)
                        snd.play("click")
                    elif event.key == pygame.K_UP:
                        ui.auto_interval = max(0.1,
                                               ui.auto_interval - 0.1)
                    elif event.key == pygame.K_DOWN:
                        ui.auto_interval = min(2.0,
                                               ui.auto_interval + 0.1)

                # ── Compare 모드 키 ──
                elif ui.mode == MODE_COMPARE:
                    if event.key == pygame.K_SPACE:
                        if not ui.compare_running:
                            ui.compare_running = True
                            ui.compare_classical_pos = 0.0
                            ui.compare_quantum_pos = 0.0
                            ui.compare_classical_done = False
                            ui.compare_quantum_done = False
                            ui.compare_timer = 0.0
                            snd.play("click")
                    elif event.key == pygame.K_UP:
                        ui.compare_n_qubits = min(10,
                                                  ui.compare_n_qubits + 1)
                        ui.compare_running = False
                        ui.compare_classical_pos = 0.0
                        ui.compare_quantum_pos = 0.0
                        ui.compare_classical_done = False
                        ui.compare_quantum_done = False
                        snd.play("click")
                    elif event.key == pygame.K_DOWN:
                        ui.compare_n_qubits = max(2,
                                                  ui.compare_n_qubits - 1)
                        ui.compare_running = False
                        ui.compare_classical_pos = 0.0
                        ui.compare_quantum_pos = 0.0
                        ui.compare_classical_done = False
                        ui.compare_quantum_done = False
                        snd.play("click")

        # ── 레코딩 ──
        recorder.record_frame({
            "mode": ui.mode,
            "phase": ui.grover.phase.name,
            "n_qubits": ui.grover.n_qubits,
            "iteration": ui.grover.current_iteration,
        })

        # ── 렌더링 ──
        screen.fill(BG)

        # 상단: 모드 탭
        tab_total_w = len(MODE_NAMES) * 280
        tab_start = max(5, (WIDTH - tab_total_w) // 2)
        for i, name in enumerate(MODE_NAMES):
            tab_x = tab_start + i * 280
            is_sel = (i == ui.mode)
            tab_clr = ACCENT if is_sel else OVERLAY_CLR
            pygame.draw.rect(screen, tab_clr,
                             (tab_x, 8, 260, 28), 0 if is_sel else 1,
                             border_radius=4)
            ts_text = font.render(name, True, BG if is_sel else TEXT_CLR)
            screen.blit(ts_text,
                        (tab_x + 130 - ts_text.get_width() // 2, 14))

        # 모드별 렌더링
        if ui.mode == MODE_STEP:
            _draw_step_mode(screen, ui, font, title_font, info_font)
        elif ui.mode == MODE_AUTO:
            _draw_auto_mode(screen, ui, font, title_font, info_font)
        elif ui.mode == MODE_COMPARE:
            _draw_compare_mode(screen, ui, font, title_font, info_font)

        # 하단 힌트 (공통)
        if ui.mode == MODE_STEP:
            hints = [t("grover_hint_step_1"), t("grover_hint_step_2")]
        elif ui.mode == MODE_AUTO:
            hints = [t("grover_hint_auto_1"), t("grover_hint_auto_2")]
        else:
            hints = [t("grover_hint_compare_1"),
                     t("grover_hint_compare_2")]
        for i, hint in enumerate(hints):
            hs = info_font.render(hint, True, TEXT_CLR)
            screen.blit(hs, (WIDTH // 2 - hs.get_width() // 2,
                             HEIGHT - 38 + i * 16))

        # 난이도 뱃지
        diff_colors = {"easy": GREEN, "normal": YELLOW, "hard": RED}
        badge_clr = diff_colors.get(ui.difficulty, TEXT_CLR)
        badge = info_font.render(f"[{ui.difficulty.upper()}]", True, badge_clr)
        screen.blit(badge, (WIDTH - badge.get_width() - 8, HEIGHT - 16))

        # 오버레이
        toast.update(dt)
        toast.draw(screen, info_font)
        toast.draw_history(screen, info_font)
        help_overlay.draw(screen, info_font)
        tutorial.draw(screen, font)
        perf.draw_overlay(screen, info_font, x=WIDTH - 250, y=4)

        pygame.display.flip()

    perf.log_summary()

    best_prob = max(
        (h.get("target_prob", 0) for h in ui.grover.search_history),
        default=0.0)
    session_data = {
        "play_time": round(time.time() - ui.start_time, 1),
        "searches_completed": ui.searches_completed,
        "total_steps": ui.total_steps,
        "last_n_qubits": ui.grover.n_qubits,
        "largest_db": max(
            (h["n_qubits"] for h in ui.grover.search_history),
            default=ui.grover.n_qubits),
        "best_target_prob": round(best_prob, 4),
    }

    finalize_session(
        "grover_search",
        session_data,
        recorder=recorder,
        recorder_meta={"play_time": session_data["play_time"]},
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def _submit_input(ui, snd):
    """입력 확인."""
    ui.input_active = 0
    try:
        n_qubits = int(ui.input_buffer)
        if n_qubits < 1:
            n_qubits = 1
        max_q = cfg("grover", "max_qubits", 10)
        if n_qubits > max_q:
            n_qubits = max_q

        # 대상 파싱 (쉼표 구분)
        parts = ui.input_target_buffer.replace(" ", "").split(",")
        targets = []
        for p in parts:
            if p.isdigit():
                targets.append(int(p))
        if not targets:
            targets = [random.randint(0, (1 << n_qubits) - 1)]

        reset_state(ui.grover, n_qubits, targets)
        grover_step(ui.grover)
        snd.play("click")
    except ValueError:
        pass


def _on_mode_change(ui):
    """모드 전환 시 초기화."""
    if ui.mode == MODE_COMPARE:
        ui.compare_running = False
        ui.compare_classical_pos = 0.0
        ui.compare_quantum_pos = 0.0
        ui.compare_classical_done = False
        ui.compare_quantum_done = False
    elif ui.mode in (MODE_STEP, MODE_AUTO):
        reset_state(ui.grover)
        grover_step(ui.grover)
        ui.auto_running = False


def open_grover_search():
    """외부에서 호출하는 진입점."""
    run_simulation()
