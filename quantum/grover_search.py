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
HISTORY_PAGE_SIZE = 4

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
_MODE_TAB_KEYS = ["grover_tab_step", "grover_tab_auto", "grover_tab_compare"]


# ── 레이아웃 (해상도 적응) ─────────────────────────────

class Layout:
    """해상도 기반 레이아웃 좌표 계산.

    기준 해상도 900×600에 대한 비례식으로 좌표를 산출합니다.
    """

    def __init__(self, w: int = 900, h: int = 600):
        self.W = w
        self.H = h
        sx = w / 900
        sy = h / 600

        # 마진
        self.margin = int(20 * sx)

        # 상단: 모드 탭 바
        self.tab_y = int(8 * sy)
        self.tab_h = int(28 * sy)
        tab_total = w - 2 * self.margin
        self.tab_w = tab_total // 3
        self.tab_label_offset_y = int(6 * sy)

        # 제목 / N 표시 줄
        self.title_y = int(42 * sy)
        self.n_row_y = int(70 * sy)

        # Step/Auto: 단계 인디케이터, 회로, 상태 패널
        self.indicator_x = self.margin
        self.indicator_y = int(100 * sy)

        col2_x = int(200 * sx)
        col3_x = int(600 * sx)
        panel_row_y = int(90 * sy)
        panel_row_h = int(130 * sy)

        self.circuit_x = col2_x
        self.circuit_y = panel_row_y
        self.circuit_w = col3_x - col2_x - self.margin
        self.circuit_h = panel_row_h

        self.status_x = col3_x
        self.status_y = panel_row_y
        self.status_w = w - col3_x - self.margin
        self.status_h = panel_row_h
        self.status_text_x = col3_x + int(10 * sx)
        self.status_msg_y = panel_row_y + int(25 * sy)
        self.status_desc_y = panel_row_y + int(80 * sy)

        # 그래프 영역
        graph_y = int(240 * sy)
        self.graph_x = self.margin
        self.graph_y = graph_y
        self.graph_w_step = int(420 * sx)
        self.graph_h_step = int(150 * sy)
        self.graph_w_auto = int(560 * sx)
        self.graph_h_auto = int(160 * sy)

        # 확률 변화 그래프
        self.prob_x_step = int(460 * sx)
        self.prob_w_step = int(410 * sx)
        self.prob_h = int(130 * sy)
        self.prob_x_auto = col3_x
        self.prob_w_auto = w - col3_x - self.margin

        # Auto 상태/진행률
        self.auto_status_x = int(400 * sx)
        self.prog_x = int(520 * sx)
        self.prog_w = int(200 * sx)
        self.prog_h = int(14 * sy)

        # 반복 텍스트 (Step)
        self.iter_text_x = int(500 * sx)

        # 결과
        self.result_y = int(405 * sy)
        self.speedup_y = int(432 * sy)
        self.result_y_auto = int(420 * sy)

        # 히스토리
        self.history_y = int(460 * sy)

        # 입력 필드
        self.input_y = h - int(70 * sy)

        # 하단 힌트
        self.hint_y1 = h - int(38 * sy)
        self.hint_y2 = h - int(22 * sy)
        self.notify_y = h - int(55 * sy)
        self.badge_y = h - int(16 * sy)

        # ── Compare 모드 ──
        self.cmp_track_x = int(60 * sx)
        self.cmp_track_w = w - int(120 * sx)
        self.cmp_classical_y = int(140 * sy)
        self.cmp_quantum_y = int(220 * sy)
        self.cmp_panel_h = int(60 * sy)
        self.cmp_bar_h = int(20 * sy)

        self.cmp_stats_x = int(40 * sx)
        self.cmp_stats_y = int(300 * sy)
        self.cmp_stats_w = w - int(80 * sx)
        self.cmp_stats_h = int(120 * sy)
        self.cmp_stats_text_x = int(60 * sx)
        self.cmp_stats_text_y = int(320 * sy)

        self.cmp_adv_y = int(430 * sy)
        self.cmp_adv_h = int(100 * sy)
        self.cmp_adv_text_x = int(55 * sx)
        self.cmp_adv_text_y = int(445 * sy)

        self.cmp_hint_y = h - int(55 * sy)

        # Perf overlay
        self.perf_x = w - int(250 * sx)


_layout = Layout(WIDTH, HEIGHT)


def _rebuild_layout(w: int, h: int):
    """리사이즈 시 레이아웃 재계산."""
    global _layout
    _layout = Layout(w, h)


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

    # 알림
    notify_msg: str = ""
    notify_timer: float = 0.0

    # 페이지네이션
    history_page: int = 0


def _notify(ui: UIState, msg: str, duration: float = 2.0):
    """화면 하단 알림 표시."""
    ui.notify_msg = msg
    ui.notify_timer = duration


# ── 그리기 유틸리티 ──────────────────────────────────

def _draw_panel(screen, x, y, w, h, title="", title_font=None, font=None):
    """둥근 패널."""
    pygame.draw.rect(screen, PANEL_BG, (x, y, w, h), border_radius=6)
    pygame.draw.rect(screen, OVERLAY_CLR, (x, y, w, h), 1, border_radius=6)
    if title and title_font:
        ts = title_font.render(title, True, ACCENT)
        screen.blit(ts, (x + 10, y + 6))


def _draw_progress_bar(screen, x, y, w, h, progress, color=None):
    """진행률 바 (0.0 ~ 1.0)."""
    if color is None:
        color = ACCENT
    pygame.draw.rect(screen, OVERLAY_CLR, (x, y, w, h), border_radius=3)
    fill_w = max(0, int(w * min(1.0, progress)))
    if fill_w > 0:
        pygame.draw.rect(screen, color, (x, y, fill_w, h), border_radius=3)
    pygame.draw.rect(screen, TEXT_CLR, (x, y, w, h), 1, border_radius=3)


def _draw_bar_pattern(screen, rect, clr, tier):
    """색맹 보조: 막대에 패턴 오버레이.

    tier: "target" → 수평 줄, "high" → 대각선, "normal" → 없음
    """
    bx, by, bw, bh = rect
    if bw <= 0 or bh <= 0:
        return
    pc = tuple(min(255, c + 60) for c in clr[:3])
    if tier == "target":
        for ly in range(by + 2, by + bh, 4):
            pygame.draw.line(screen, pc, (bx, ly), (bx + bw - 1, ly))
    elif tier == "high":
        diag_len = bw + bh
        for d in range(0, diag_len, 5):
            x0, y0 = bx + d, by
            x1, y1 = bx + d - bh, by + bh
            x0c = max(bx, min(bx + bw, x0))
            x1c = max(bx, min(bx + bw, x1))
            if x0c == x1c:
                continue
            frac0 = (x0c - (bx + d)) / (-bh) if bh else 0
            frac1 = (x1c - (bx + d)) / (-bh) if bh else 1
            y0c = int(by + frac0 * bh)
            y1c = int(by + frac1 * bh)
            pygame.draw.line(screen, pc, (x0c, y0c), (x1c, y1c))


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
            tag = f" [{t('grover_phase_tag_current')}]"
        elif is_done:
            clr = GREEN
            marker = "✓"
            tag = f" [{t('grover_phase_tag_done')}]"
        else:
            clr = SUBTEXT
            marker = "·"
            tag = ""

        s = font.render(f" {marker} {label}{tag}", True, clr)
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
            tier = "target"
        elif probs[i] > max_val * 0.3:
            clr = PURPLE
            tier = "high"
        else:
            clr = ACCENT
            tier = "normal"

        if bar_h > 0:
            bw_actual = max(1, bar_w - 1)
            pygame.draw.rect(screen, clr, (bx, by, bw_actual, bar_h))
            _draw_bar_pattern(screen, (bx, by, bw_actual, bar_h), clr, tier)

    # 레이블
    label = font.render(
        f"P(x)  iter={grover.current_iteration}/{grover.optimal_iterations}",
        True, TEXT_CLR)
    screen.blit(label, (x + 10, y + 2))

    # 범례 (우측 상단)
    legend = [
        (YELLOW, "target", t("grover_legend_target")),
        (PURPLE, "high", t("grover_legend_high")),
        (ACCENT, "normal", t("grover_legend_normal")),
    ]
    lx = x + w - 130
    for li, (lc, lt, ll) in enumerate(legend):
        ly = y + 4 + li * 14
        sw = 10
        pygame.draw.rect(screen, lc, (lx, ly, sw, sw))
        _draw_bar_pattern(screen, (lx, ly, sw, sw), lc, lt)
        ls = font.render(ll, True, TEXT_CLR)
        screen.blit(ls, (lx + sw + 4, ly - 1))


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


def _draw_search_history(screen, ui, font, x, y):
    """페이지네이션된 탐색 히스토리 표시."""
    history = ui.grover.search_history
    if not history:
        return

    total = len(history)
    total_pages = max(1, (total + HISTORY_PAGE_SIZE - 1) // HISTORY_PAGE_SIZE)
    ui.history_page = max(0, min(ui.history_page, total_pages - 1))

    start = ui.history_page * HISTORY_PAGE_SIZE
    end = min(start + HISTORY_PAGE_SIZE, total)
    page_items = history[start:end]

    title_text = t("grover_search_history")
    if total_pages > 1:
        title_text += f"  ({ui.history_page + 1}/{total_pages})"
    ht = font.render(title_text, True, ACCENT)
    screen.blit(ht, (x, y))

    for i, h in enumerate(page_items):
        clr = GREEN if h["success"] else YELLOW
        hs = font.render(
            f"  {h['n_qubits']}q target={h['targets'][:3]} → "
            f"|{h['measured']}⟩ {'✓' if h['success'] else '✗'} "
            f"({h['iterations']} iters)",
            True, clr)
        screen.blit(hs, (x, y + 16 + i * 14))


# ── 모드별 렌더링 ────────────────────────────────────

def _draw_step_mode(screen, ui, font, title_font, info_font):
    """Step-by-Step 모드."""
    L = _layout
    grover = ui.grover

    title = title_font.render(t("grover_title_step"), True, ACCENT)
    screen.blit(title, (L.W // 2 - title.get_width() // 2, L.title_y))

    # 큐빗/대상 표시
    n_text = font.render(
        f"N = 2^{grover.n_qubits} = {1 << grover.n_qubits}  "
        f"target = {grover.targets}", True, TEXT_CLR)
    screen.blit(n_text, (L.margin, L.n_row_y))

    if grover.current_iteration > 0:
        att = font.render(
            f"Iteration {grover.current_iteration}/{grover.optimal_iterations}",
            True, TEAL)
        screen.blit(att, (L.iter_text_x, L.n_row_y))

    # 좌측: 단계 인디케이터
    _draw_phase_indicator(screen, grover.phase, font,
                          L.indicator_x, L.indicator_y)

    # 중앙 상단: 양자 회로 다이어그램
    _draw_circuit_diagram(screen, grover, info_font,
                          L.circuit_x, L.circuit_y,
                          L.circuit_w, L.circuit_h)

    # 우측 상단: 상태 메시지
    _draw_panel(screen, L.status_x, L.status_y, L.status_w, L.status_h,
                t("grover_status_title"), font, info_font)
    msg_lines = _wrap_text(grover.step_message, 35)
    for i, line in enumerate(msg_lines):
        clr = GREEN if grover.phase == GroverPhase.SUCCESS else TEXT_CLR
        if grover.phase == GroverPhase.FAIL:
            clr = RED
        ms = info_font.render(line, True, clr)
        screen.blit(ms, (L.status_text_x, L.status_msg_y + i * 16))
    desc_lines = _wrap_text(get_phase_description(grover.phase), 35)
    for i, line in enumerate(desc_lines[:3]):
        ds = info_font.render(line, True, SUBTEXT)
        screen.blit(ds, (L.status_text_x, L.status_desc_y + i * 14))

    # 중앙 하단: 진폭 바 차트
    if grover.amplitudes:
        _draw_amplitude_bar_chart(screen, grover, info_font,
                                  L.graph_x, L.graph_y,
                                  L.graph_w_step, L.graph_h_step)

    # 우측 하단: 확률 변화 그래프
    if len(grover.target_prob_history) >= 2:
        _draw_probability_evolution(screen, grover.target_prob_history,
                                    info_font, L.prob_x_step, L.graph_y,
                                    L.prob_w_step, L.prob_h)

    # 최종 결과
    if grover.phase == GroverPhase.SUCCESS:
        result = title_font.render(
            t("grover_result_found", result=grover.measured,
              iter=grover.current_iteration),
            True, GREEN)
        screen.blit(result, (L.W // 2 - result.get_width() // 2, L.result_y))
        if grover.comparison:
            comp = grover.comparison
            speedup = info_font.render(
                f"Classical: ~{comp.classical_expected:.0f} queries  |  "
                f"Grover: {comp.quantum_iterations} queries  |  "
                f"Speedup: {comp.speedup_ratio:.1f}×",
                True, PURPLE)
            screen.blit(speedup,
                        (L.W // 2 - speedup.get_width() // 2, L.speedup_y))
    elif grover.phase == GroverPhase.FAIL:
        result = title_font.render(
            t("grover_result_not_target", result=grover.measured),
            True, RED)
        screen.blit(result, (L.W // 2 - result.get_width() // 2, L.result_y))

    # 탐색 히스토리 (페이지네이션)
    _draw_search_history(screen, ui, info_font, L.margin, L.history_y)

    # 입력 필드
    if grover.phase in (GroverPhase.INPUT, GroverPhase.DONE,
                        GroverPhase.SUCCESS, GroverPhase.FAIL):
        _draw_input_fields(screen, ui, font, L.margin, L.input_y)


def _draw_auto_mode(screen, ui, font, title_font, info_font):
    """Auto 모드."""
    L = _layout
    grover = ui.grover

    title = title_font.render(t("grover_title_auto"), True, ACCENT)
    screen.blit(title, (L.W // 2 - title.get_width() // 2, L.title_y))

    n_text = font.render(
        f"N = 2^{grover.n_qubits} = {1 << grover.n_qubits}  "
        f"target = {grover.targets}", True, TEXT_CLR)
    screen.blit(n_text, (L.margin, L.n_row_y))

    status = t("grover_auto_running") if ui.auto_running \
        else t("grover_auto_paused")
    status_clr = GREEN if ui.auto_running else YELLOW
    st = font.render(status, True, status_clr)
    screen.blit(st, (L.auto_status_x, L.n_row_y))

    # 진행률
    if grover.phase not in (GroverPhase.DONE, GroverPhase.SUCCESS,
                            GroverPhase.FAIL):
        progress = grover.phase.value / GroverPhase.DONE.value
    else:
        progress = 1.0
    _draw_progress_bar(screen, L.prog_x, L.n_row_y + 2,
                       L.prog_w, L.prog_h, progress)

    # 단계 인디케이터
    _draw_phase_indicator(screen, grover.phase, font,
                          L.indicator_x, L.indicator_y)

    # 회로 다이어그램
    _draw_circuit_diagram(screen, grover, info_font,
                          L.circuit_x, L.circuit_y,
                          L.circuit_w, L.circuit_h)

    # 상태 메시지
    _draw_panel(screen, L.status_x, L.status_y, L.status_w, L.status_h,
                t("grover_status_title"), font, info_font)
    msg_lines = _wrap_text(grover.step_message, 35)
    for i, line in enumerate(msg_lines):
        clr = GREEN if grover.phase == GroverPhase.SUCCESS else TEXT_CLR
        ms = info_font.render(line, True, clr)
        screen.blit(ms, (L.status_text_x, L.status_msg_y + i * 16))

    # 바 차트
    if grover.amplitudes:
        _draw_amplitude_bar_chart(screen, grover, info_font,
                                  L.graph_x, L.graph_y,
                                  L.graph_w_auto, L.graph_h_auto)

    # 확률 변화
    if len(grover.target_prob_history) >= 2:
        _draw_probability_evolution(screen, grover.target_prob_history,
                                    info_font, L.prob_x_auto, L.graph_y,
                                    L.prob_w_auto, L.prob_h)

    # 결과
    if grover.phase == GroverPhase.SUCCESS:
        result = title_font.render(
            t("grover_result_found", result=grover.measured,
              iter=grover.current_iteration),
            True, GREEN)
        screen.blit(result,
                    (L.W // 2 - result.get_width() // 2, L.result_y_auto))

    # 입력 필드
    if grover.phase in (GroverPhase.INPUT, GroverPhase.DONE,
                        GroverPhase.SUCCESS, GroverPhase.FAIL):
        _draw_input_fields(screen, ui, font, L.margin, L.input_y)


def _draw_compare_mode(screen, ui, font, title_font, info_font):
    """Classical vs Quantum 비교 모드."""
    L = _layout
    title = title_font.render(t("grover_title_compare"), True, ACCENT)
    screen.blit(title, (L.W // 2 - title.get_width() // 2, L.title_y))

    n_qubits = ui.compare_n_qubits
    n_states = 1 << n_qubits
    n_text = font.render(
        f"Database: N = 2^{n_qubits} = {n_states} items  |  "
        f"Target: 1 item", True, TEXT_CLR)
    screen.blit(n_text, (L.margin, L.n_row_y))

    # 레이스 트랙
    tx = L.cmp_track_x
    tw = L.cmp_track_w
    cy = L.cmp_classical_y
    qy = L.cmp_quantum_y

    # 고전 트랙
    _draw_panel(screen, L.margin, cy - 10, L.W - 2 * L.margin,
                L.cmp_panel_h, t("grover_compare_classical"), font, info_font)
    _draw_progress_bar(screen, tx, cy + 20, tw, L.cmp_bar_h,
                       ui.compare_classical_pos, RED)
    queries_c = int(ui.compare_classical_pos * n_states)
    qc_text = info_font.render(
        f"{queries_c}/{n_states} queries", True, TEXT_CLR)
    screen.blit(qc_text, (tx + tw + 5, cy + 20))

    # 양자 트랙
    opt_iter = max(1, int(math.pi / 4 * math.sqrt(n_states)))
    _draw_panel(screen, L.margin, qy - 10, L.W - 2 * L.margin,
                L.cmp_panel_h, t("grover_compare_quantum"), font, info_font)
    _draw_progress_bar(screen, tx, qy + 20, tw, L.cmp_bar_h,
                       ui.compare_quantum_pos, GREEN)
    queries_q = int(ui.compare_quantum_pos * opt_iter)
    qq_text = info_font.render(
        f"{queries_q}/{opt_iter} queries", True, TEXT_CLR)
    screen.blit(qq_text, (tx + tw + 5, qy + 20))

    # 완료 마커
    if ui.compare_classical_done:
        done_c = font.render(t("grover_compare_found"), True, RED)
        screen.blit(done_c, (tx + tw - 55, cy + 2))
    if ui.compare_quantum_done:
        done_q = font.render(t("grover_compare_found"), True, GREEN)
        screen.blit(done_q, (tx + tw - 55, qy + 2))

    # 비교 통계
    if ui.compare_classical_done or ui.compare_quantum_done:
        _draw_panel(screen, L.cmp_stats_x, L.cmp_stats_y,
                    L.cmp_stats_w, L.cmp_stats_h, "", title_font, info_font)

        speedup = n_states / max(1, opt_iter)
        stats = [
            t("grover_compare_stat_classical", N=n_states),
            t("grover_compare_stat_quantum", N=n_states, opt=opt_iter),
            t("grover_compare_speedup", ratio=f"{speedup:.1f}"),
        ]
        for i, line in enumerate(stats):
            clr = [RED, GREEN, YELLOW][i]
            ls = info_font.render(line, True, clr)
            screen.blit(ls, (L.cmp_stats_text_x,
                             L.cmp_stats_text_y + i * 22))

    # 양자 우위 메시지
    if ui.compare_classical_done and ui.compare_quantum_done:
        _draw_panel(screen, L.cmp_stats_x, L.cmp_adv_y,
                    L.cmp_stats_w, L.cmp_adv_h, "", title_font, info_font)
        msg_lines = _wrap_text(get_quantum_advantage_message(), 90)
        for i, line in enumerate(msg_lines[:4]):
            ms = info_font.render(line, True, YELLOW)
            screen.blit(ms, (L.cmp_adv_text_x,
                             L.cmp_adv_text_y + i * 16))

    # 하단 힌트
    hint = info_font.render(
        t("grover_compare_hint_db", n=n_qubits), True, SUBTEXT)
    screen.blit(hint, (L.W // 2 - hint.get_width() // 2, L.cmp_hint_y))


# ── 메인 시뮬레이션 ──────────────────────────────────

def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
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
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (event.w, event.h), pygame.RESIZABLE)
                _rebuild_layout(event.w, event.h)
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

                elif event.key == pygame.K_PAGEUP:
                    ui.history_page = max(0, ui.history_page - 1)
                elif event.key == pygame.K_PAGEDOWN:
                    ui.history_page += 1

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
                        _notify(ui, t("grover_speed_changed",
                                      speed=f"{ui.auto_interval:.1f}"), 1.0)
                    elif event.key == pygame.K_DOWN:
                        ui.auto_interval = min(2.0,
                                               ui.auto_interval + 0.1)
                        _notify(ui, t("grover_speed_changed",
                                      speed=f"{ui.auto_interval:.1f}"), 1.0)

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
        L = _layout
        screen.fill(BG)

        # 상단: 모드 탭
        tab_start = L.margin
        for i, key in enumerate(_MODE_TAB_KEYS):
            tab_x = tab_start + i * L.tab_w
            is_sel = (i == ui.mode)
            tab_clr = ACCENT if is_sel else OVERLAY_CLR
            pygame.draw.rect(screen, tab_clr,
                             (tab_x, L.tab_y, L.tab_w - 4, L.tab_h),
                             0 if is_sel else 1, border_radius=4)
            ts_text = font.render(t(key), True, BG if is_sel else TEXT_CLR)
            screen.blit(ts_text,
                        (tab_x + (L.tab_w - 4) // 2
                         - ts_text.get_width() // 2,
                         L.tab_y + L.tab_label_offset_y))

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
            screen.blit(hs, (L.W // 2 - hs.get_width() // 2,
                             L.hint_y1 + i * 16))

        # 알림 표시
        if ui.notify_timer > 0:
            ui.notify_timer -= dt
            alpha = min(255, int(255 * min(1.0, ui.notify_timer / 0.3)))
            ns = info_font.render(ui.notify_msg, True, YELLOW)
            ns.set_alpha(alpha)
            screen.blit(ns, (L.W // 2 - ns.get_width() // 2, L.notify_y))

        # 난이도 뱃지
        diff_colors = {"easy": GREEN, "normal": YELLOW, "hard": RED}
        badge_clr = diff_colors.get(ui.difficulty, TEXT_CLR)
        badge = info_font.render(f"[{ui.difficulty.upper()}]", True, badge_clr)
        screen.blit(badge, (L.W - badge.get_width() - 8, L.badge_y))

        # 오버레이
        toast.update(dt)
        toast.draw(screen, info_font)
        toast.draw_history(screen, info_font)
        help_overlay.draw(screen, info_font)
        tutorial.draw(screen, font)
        perf.draw_overlay(screen, info_font, x=L.perf_x, y=4)

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
        ui.history_page = 0
        snd.play("click")
    except ValueError:
        _notify(ui, t("grover_input_err_invalid"))


def _on_mode_change(ui):
    """모드 전환 시 초기화."""
    ui.history_page = 0
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
