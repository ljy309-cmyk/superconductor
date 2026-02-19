"""Shor's Algorithm 시각화 (Pygame).

3가지 모드:
  1. Step-by-Step: 소인수분해 단계를 하나씩 진행하며 시각화
  2. Auto: 자동 실행으로 전체 과정 애니메이션
  3. RSA Threat: RSA 암호가 Shor에 의해 깨지는 과정 → QKD 필요성
"""

import math
import time
from dataclasses import dataclass, field

import pygame

from achievement_toast import AchievementToast
from config_loader import cfg
from game_base import finalize_session
from difficulty_dialog import choose_difficulty
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from perf_monitor import PerfMonitor
from presets import get_preset
from quantum.shor_algorithm_engine import (
    PHASE_DESCRIPTIONS,
    QKD_MOTIVATION_MESSAGE,
    RSA_EXAMPLES,
    ShorPhase,
    ShorState,
    finalize_rsa_crack,
    get_phase_description,
    get_qkd_motivation,
    reset_state,
    setup_rsa_demo,
    shor_run_full,
    shor_step,
)
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from sound_manager import get_sound_manager
from theme import load_pg_colors, on_theme_change
from tutorial import TutorialOverlay

_log = get_module_logger("shor_algorithm")

# ── 화면 설정 ────────────────────────────────────────
WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
FPS = cfg("display", "fps", 60)

# ── Shor UI 설정 (config.json에서 로드) ──────────────
ANIMATION_SPEED = cfg("shor", "animation_speed", 0.6)
QFT_DISPLAY_QUBITS = cfg("shor", "qft_display_qubits", 6)
AUTO_BATCH_SIZE = cfg("shor", "auto_batch_size", 1)
RSA_DEFAULT_DIFFICULTY = cfg("shor", "rsa_default_difficulty", 0)
RSA_CRACK_SPEED = cfg("shor", "rsa_crack_speed", 0.15)
BAR_ANIM_INTERVAL = cfg("shor", "bar_anim_interval", 0.03)

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
MODE_RSA = 2
MODE_NAMES = ["Step-by-Step", "Auto Run", "RSA Threat"]


# ── 레이아웃 (해상도 적응) ─────────────────────────────

class Layout:
    """해상도 기반 레이아웃 좌표 계산.

    기준 해상도 900×600에 대한 비례식으로 좌표를 산출합니다.
    """

    def __init__(self, w: int = 900, h: int = 600):
        self.W = w
        self.H = h
        sx = w / 900       # 수평 스케일
        sy = h / 600       # 수직 스케일

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

        # Step/Auto 공통: 단계 인디케이터, 회로, 상태 패널
        self.indicator_x = self.margin
        self.indicator_y = int(100 * sy)

        col2_x = int(200 * sx)              # 좌측 기둥 끝
        col3_x = int(600 * sx)              # 우측 패널 시작
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

        # 중앙 하단: 그래프 영역
        graph_y = int(240 * sy)
        graph_h = int(150 * sy)
        self.graph_x = self.margin
        self.graph_y = graph_y
        self.graph_w_step = int(420 * sx)   # Step 모드 (우측 연분수 여유)
        self.graph_w_auto = int(560 * sx)   # Auto 모드 (넓게)
        self.graph_h = graph_h
        self.graph_h_auto = int(160 * sy)

        # 연분수 위치
        self.cf_x_step = int(460 * sx)
        self.cf_x_auto = col3_x
        self.cf_y = int(250 * sy)

        # 결과 / 히스토리
        self.result_y = int(410 * sy)
        self.method_y = int(440 * sy)
        self.result_y_auto = int(420 * sy)
        self.history_y = int(470 * sy)

        # 진행률 바 (Auto)
        self.prog_x = int(300 * sx)
        self.prog_w = int(200 * sx)
        self.prog_h = int(14 * sy)

        # 입력 필드
        self.input_y = h - int(70 * sy)

        # 하단 힌트
        self.hint_y1 = h - int(38 * sy)
        self.hint_y2 = h - int(22 * sy)
        self.badge_y = h - int(16 * sy)

        # ── RSA 모드 ──
        rsa_panel_h = int(120 * sy)
        rsa_panel_y = int(95 * sy)
        self.rsa_pub_x = self.margin
        self.rsa_pub_y = rsa_panel_y
        self.rsa_pub_w = int(420 * sx)
        self.rsa_pub_h = rsa_panel_h
        self.rsa_sec_x = int(460 * sx)
        self.rsa_sec_y = rsa_panel_y
        self.rsa_sec_w = w - int(460 * sx) - self.margin
        self.rsa_sec_h = rsa_panel_h
        self.rsa_info_x = self.margin + int(10 * sx)
        self.rsa_info_y = rsa_panel_y + int(23 * sy)
        self.rsa_sec_text_x = int(470 * sx)

        self.rsa_status_y = int(240 * sy)

        # RSA 크래킹 패널
        self.rsa_crack_panel_y = int(228 * sy)
        self.rsa_crack_panel_h = int(240 * sy)
        self.rsa_crack_title_y = int(236 * sy)
        self.rsa_crack_prog_y = int(262 * sy)
        self.rsa_crack_indicator_x = int(60 * sx)
        self.rsa_crack_indicator_y = int(286 * sy)
        self.rsa_crack_msg_x = int(260 * sx)
        self.rsa_crack_msg_y = int(290 * sy)
        self.rsa_crack_attempt_y = int(345 * sy)

        # RSA 결과 / QKD
        self.rsa_cracked_y = int(242 * sy)
        self.rsa_method_y = int(268 * sy)
        self.rsa_arrow_y = int(285 * sy)
        self.rsa_qkd_y = int(300 * sy)
        self.rsa_qkd_h = int(170 * sy)
        self.rsa_qkd_text_x = int(55 * sx)
        self.rsa_qkd_text_y = int(325 * sy)
        self.rsa_hint_y = h - int(55 * sy)

        # wrap 문자 수 (해상도 비례)
        self.wrap_status = max(20, int(35 * sx))
        self.wrap_rsa_msg = max(25, int(45 * sx))
        self.wrap_qkd = max(40, int(80 * sx))


_layout = Layout(WIDTH, HEIGHT)


# ── UI 상태 ──────────────────────────────────────────

@dataclass
class UIState:
    """UI 전체 상태."""
    mode: int = MODE_STEP
    difficulty: str = "normal"
    t: float = 0.0
    start_time: float = field(default_factory=time.time)

    # Shor 엔진 상태
    shor: ShorState = field(default_factory=lambda: ShorState(number=15))

    # Auto 모드
    auto_running: bool = False
    auto_timer: float = 0.0
    auto_interval: float = ANIMATION_SPEED  # 단계 간 간격 (초)

    # RSA 모드
    rsa_difficulty: int = RSA_DEFAULT_DIFFICULTY
    rsa_phase: int = 0  # 0=setup, 1=cracking, 2=cracked, 3=qkd_message
    rsa_message: str = ""
    rsa_crack_timer: float = 0.0

    # 입력
    input_buffer: str = "15"
    input_active: bool = False

    # 통계
    numbers_factored: int = 0
    total_steps: int = 0

    # 히스토그램 선택
    show_qft_detail: bool = False

    # 진행률 (최고치 추적 — RETRY 역행 방지)
    progress_high: float = 0.0

    # 막대 애니메이션 (하나씩 나타나는 효과)
    mod_exp_anim_count: int = 0   # 현재 표시할 막대 수
    qft_anim_count: int = 0       # 현재 표시할 막대 수
    _anim_timer: float = 0.0      # 막대 추가 타이머
    _prev_mod_exp_len: int = 0    # 테이블 변경 감지
    _prev_qft_len: int = 0        # 히스토그램 변경 감지


# ── 그리기 유틸리티 ──────────────────────────────────

def _draw_panel(screen, x, y, w, h, title="", title_font=None, font=None):
    """둥근 패널."""
    pygame.draw.rect(screen, PANEL_BG, (x, y, w, h), border_radius=6)
    pygame.draw.rect(screen, OVERLAY_CLR, (x, y, w, h), 1, border_radius=6)
    if title and title_font:
        ts = title_font.render(title, True, ACCENT)
        screen.blit(ts, (x + 10, y + 6))


def _calc_shor_progress(ui):
    """Shor 알고리즘 진행률 계산 (0.0 ~ 1.0).

    RETRY 시 PICK_RANDOM_A로 돌아가도 진행률이 역행하지 않도록,
    핵심 파이프라인(INPUT→EXTRACT_FACTORS) 기준 + 최고치 추적.
    """
    phase = ui.shor.phase

    # 새 수 입력 시 리셋 (INPUT = reset_state 직후)
    if phase == ShorPhase.INPUT:
        ui.progress_high = 0.0
        return 0.0

    # 핵심 파이프라인: CLASSICAL_PRECHECK(2)~EXTRACT_FACTORS(8)
    if phase in (ShorPhase.SUCCESS, ShorPhase.DONE, ShorPhase.RETRY):
        raw = 1.0
    else:
        raw = min(1.0, phase.value / ShorPhase.EXTRACT_FACTORS.value)

    ui.progress_high = max(ui.progress_high, raw)
    return ui.progress_high


def _draw_progress_bar(screen, x, y, w, h, progress, color=None):
    """진행률 바 (0.0 ~ 1.0)."""
    if color is None:
        color = ACCENT
    pygame.draw.rect(screen, OVERLAY_CLR, (x, y, w, h), border_radius=3)
    fill_w = max(0, int(w * min(1.0, progress)))
    if fill_w > 0:
        pygame.draw.rect(screen, color, (x, y, fill_w, h), border_radius=3)
    pygame.draw.rect(screen, TEXT_CLR, (x, y, w, h), 1, border_radius=3)


def _draw_phase_indicator(screen, phase, font, x, y):
    """현재 단계 표시 (좌측 패널)."""
    phases = [
        (ShorPhase.CLASSICAL_PRECHECK, t("shor_phase_classical")),
        (ShorPhase.PICK_RANDOM_A, t("shor_phase_pick_a")),
        (ShorPhase.MODULAR_EXP, t("shor_phase_mod_exp")),
        (ShorPhase.QFT_SETUP, t("shor_phase_qft_setup")),
        (ShorPhase.QFT_MEASURE, t("shor_phase_qft_measure")),
        (ShorPhase.CONTINUED_FRACTION, t("shor_phase_cf")),
        (ShorPhase.EXTRACT_FACTORS, t("shor_phase_extract")),
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


def _draw_mod_exp_graph(screen, table, period, font, x, y, w, h,
                        visible_count=0):
    """a^x mod N 주기 그래프 (막대가 하나씩 나타나는 애니메이션)."""
    if not table:
        return

    n = len(table)
    show = min(visible_count, n) if visible_count > 0 else n
    max_val = max(e.value for e in table) or 1
    bar_w = max(1, (w - 20) // n)

    for i in range(show):
        entry = table[i]
        bx = x + 10 + i * bar_w
        bar_h = int((h - 30) * entry.value / max_val)
        by = y + h - 10 - bar_h

        # 주기 강조: 주기 시작점마다 다른 색
        if period > 0 and i % period == 0:
            clr = YELLOW
        else:
            clr = ACCENT

        pygame.draw.rect(screen, clr, (bx, by, max(1, bar_w - 1), bar_h))

    # 주기 구분선 (전체 표시 후에만)
    if period > 0 and show >= n:
        for k in range(1, n // period + 1):
            lx = x + 10 + k * period * bar_w
            if lx < x + w:
                pygame.draw.line(screen, RED, (lx, y + 5), (lx, y + h - 10), 1)

    # 레이블
    if show >= n and period > 0:
        label = font.render(f"a^x mod N  (period={period})", True, TEXT_CLR)
    else:
        label = font.render(f"a^x mod N  ({show}/{n})", True, TEXT_CLR)
    screen.blit(label, (x + 10, y + 2))


def _draw_qft_histogram(screen, amplitudes, font, x, y, w, h,
                        visible_count=0):
    """QFT 확률 분포 히스토그램 (막대가 하나씩 나타나는 애니메이션)."""
    if not amplitudes:
        return

    n = len(amplitudes)
    max_val = max(amplitudes) or 1

    # 너무 많으면 간추림
    step = max(1, n // 128)
    total_bars = (n + step - 1) // step
    bar_w = max(1, (w - 20) // min(n, 128))
    show = min(visible_count, total_bars) if visible_count > 0 else total_bars

    bar_idx = 0
    for i in range(0, n, step):
        if bar_idx >= show:
            break
        bx = x + 10 + bar_idx * bar_w
        bar_h = int((h - 30) * amplitudes[i] / max_val)
        by = y + h - 10 - bar_h

        if amplitudes[i] > max_val * 0.5:
            clr = YELLOW
        elif amplitudes[i] > max_val * 0.1:
            clr = PURPLE
        else:
            clr = OVERLAY_CLR

        pygame.draw.rect(screen, clr, (bx, by, max(1, bar_w - 1), bar_h))
        bar_idx += 1

    label = font.render("QFT Probability Distribution", True, TEXT_CLR)
    screen.blit(label, (x + 10, y + 2))


def _draw_continued_fraction(screen, qft_result, font, x, y):
    """연분수 전개 시각화."""
    if qft_result is None:
        return

    Q = 1 << qft_result.n_qubits
    m = qft_result.measured_value

    # 측정값
    line1 = font.render(f"m = {m},  m/Q = {m}/{Q} ≈ {qft_result.phase_estimate:.4f}",
                        True, TEXT_CLR)
    screen.blit(line1, (x, y))

    # 수렴분수
    if qft_result.convergents:
        convs_str = "  ".join(f"{p}/{q}" for p, q in qft_result.convergents[:6])
        line2 = font.render(f"Convergents: {convs_str}", True, PURPLE)
        screen.blit(line2, (x, y + 18))

    # 후보 주기
    if qft_result.candidate_r is not None:
        line3 = font.render(f"→ Period candidate: r = {qft_result.candidate_r}",
                            True, GREEN)
    else:
        line3 = font.render("→ No valid period found", True, RED)
    screen.blit(line3, (x, y + 36))


def _draw_circuit_diagram(screen, shor, font, x, y, w, h):
    """양자 회로 다이어그램 (간략화)."""
    n_qubits = shor.qft_n_qubits if shor.qft_n_qubits > 0 else 8
    display_qubits = min(n_qubits, QFT_DISPLAY_QUBITS)

    # 배경 패널
    pygame.draw.rect(screen, PANEL_BG, (x, y, w, h), border_radius=4)
    pygame.draw.rect(screen, OVERLAY_CLR, (x, y, w, h), 1, border_radius=4)

    line_start_x = x + 60
    line_end_x = x + w - 20
    line_y_start = y + 30
    line_spacing = max(16, (h - 50) // display_qubits)

    # 큐빗 라인
    for i in range(display_qubits):
        ly = line_y_start + i * line_spacing
        # |0⟩ 라벨
        ql = font.render(f"|0⟩", True, TEXT_CLR)
        screen.blit(ql, (x + 10, ly - 6))
        # 수평선
        pygame.draw.line(screen, SUBTEXT, (line_start_x, ly),
                         (line_end_x, ly), 1)

    # 게이트 박스들
    gate_positions = [
        (line_start_x + 30, "H", ACCENT),
        (line_start_x + 90, "U_f", PURPLE),
        (line_start_x + 160, "QFT†", YELLOW),
        (line_start_x + 240, "M", GREEN),
    ]

    phase = shor.phase
    for gx, gate_name, color in gate_positions:
        # 현재 단계에 따라 강조
        gate_phase_map = {
            "H": ShorPhase.QFT_SETUP,
            "U_f": ShorPhase.MODULAR_EXP,
            "QFT†": ShorPhase.QFT_MEASURE,
            "M": ShorPhase.CONTINUED_FRACTION,
        }
        is_active = (phase == gate_phase_map.get(gate_name))
        is_done = phase.value > gate_phase_map.get(gate_name, ShorPhase.DONE).value

        box_color = color if (is_active or is_done) else OVERLAY_CLR
        border = 2 if is_active else 1

        for i in range(display_qubits):
            ly = line_y_start + i * line_spacing
            bw = 36 if len(gate_name) <= 2 else 44
            rect = pygame.Rect(gx - bw // 2, ly - 10, bw, 20)
            pygame.draw.rect(screen, box_color, rect, border, border_radius=3)

        # 게이트 이름 (상단에 한 번)
        gs_text = font.render(gate_name, True,
                              WHITE if is_active else box_color)
        screen.blit(gs_text, (gx - gs_text.get_width() // 2,
                              line_y_start - 20))

    title = font.render(t("shor_circuit_title"), True, ACCENT)
    screen.blit(title, (x + 10, y + 4))


# ── 모드별 렌더링 ────────────────────────────────────

def _draw_step_mode(screen, ui, font, title_font, info_font):
    """Step-by-Step 모드."""
    L = _layout
    shor = ui.shor

    # 제목
    title = title_font.render(t("shor_title_step"), True, ACCENT)
    screen.blit(title, (L.W // 2 - title.get_width() // 2, L.title_y))

    # N 표시
    n_text = font.render(f"N = {shor.number}", True, TEXT_CLR)
    screen.blit(n_text, (L.margin, L.n_row_y))

    # 시도 횟수
    if shor.attempt > 0:
        att = font.render(f"Attempt #{shor.attempt}  a = {shor.a}", True, TEAL)
        screen.blit(att, (L.margin + 130, L.n_row_y))

    # 좌측: 단계 인디케이터
    _draw_phase_indicator(screen, shor.phase, font, L.indicator_x, L.indicator_y)

    # 중앙 상단: 양자 회로 다이어그램
    _draw_circuit_diagram(screen, shor, info_font,
                          L.circuit_x, L.circuit_y, L.circuit_w, L.circuit_h)

    # 우측 상단: 상태 메시지
    _draw_panel(screen, L.status_x, L.status_y, L.status_w, L.status_h,
                "Status", font, info_font)
    msg_lines = _wrap_text(shor.step_message, L.wrap_status)
    for i, line in enumerate(msg_lines):
        clr = GREEN if shor.phase == ShorPhase.SUCCESS else TEXT_CLR
        ms = info_font.render(line, True, clr)
        screen.blit(ms, (L.status_text_x, L.status_msg_y + i * 16))
    desc_lines = _wrap_text(get_phase_description(shor.phase), L.wrap_status)
    for i, line in enumerate(desc_lines[:3]):
        ds = info_font.render(line, True, SUBTEXT)
        screen.blit(ds, (L.status_text_x, L.status_desc_y + i * 14))

    # 중앙 하단: 모듈러 지수 그래프 / QFT 히스토그램
    if shor.qft_amplitudes:
        _draw_qft_histogram(screen, shor.qft_amplitudes, info_font,
                            L.graph_x, L.graph_y, L.graph_w_step, L.graph_h,
                            visible_count=ui.qft_anim_count)
    elif shor.mod_exp_table:
        _draw_mod_exp_graph(screen, shor.mod_exp_table,
                            shor.mod_exp_period_visual, info_font,
                            L.graph_x, L.graph_y, L.graph_w_step, L.graph_h,
                            visible_count=ui.mod_exp_anim_count)

    # 우측 하단: 연분수 / 결과
    if shor.qft_current:
        _draw_continued_fraction(screen, shor.qft_current, info_font,
                                 L.cf_x_step, L.cf_y)

    # 최종 결과
    if shor.factors:
        p, q = shor.factors
        result = title_font.render(f"{shor.number} = {p} × {q}", True, GREEN)
        screen.blit(result, (L.W // 2 - result.get_width() // 2, L.result_y))
        method = info_font.render(f"Method: {shor.factor_method}", True, PURPLE)
        screen.blit(method, (L.W // 2 - method.get_width() // 2, L.method_y))
    elif shor.is_prime:
        result = title_font.render(f"{shor.number} is PRIME", True, RED)
        screen.blit(result, (L.W // 2 - result.get_width() // 2, L.result_y))

    # 시도 히스토리
    if shor.attempt_history:
        hy = L.history_y
        hist_title = info_font.render(t("shor_attempt_history"), True, ACCENT)
        screen.blit(hist_title, (L.margin, hy))
        for i, h in enumerate(shor.attempt_history[-4:]):
            reason = h.get("reason", "")
            clr = GREEN if reason == "success" else YELLOW
            hs = info_font.render(
                f"  #{h['attempt']}: a={h['a']}, r={h.get('r','?')} → {reason}",
                True, clr)
            screen.blit(hs, (L.margin, hy + 16 + i * 14))

    # 입력 필드 (DONE 또는 INPUT 상태일 때)
    if shor.phase in (ShorPhase.INPUT, ShorPhase.DONE, ShorPhase.SUCCESS):
        _draw_input_field(screen, ui, font, L.margin, L.input_y)


def _draw_auto_mode(screen, ui, font, title_font, info_font):
    """Auto 모드."""
    L = _layout
    shor = ui.shor

    # 제목
    title = title_font.render(t("shor_title_auto"), True, ACCENT)
    screen.blit(title, (L.W // 2 - title.get_width() // 2, L.title_y))

    # N 표시 + 진행 상태
    n_text = font.render(f"N = {shor.number}", True, TEXT_CLR)
    screen.blit(n_text, (L.margin, L.n_row_y))

    status = t("shor_auto_running") if ui.auto_running else t("shor_auto_paused")
    status_clr = GREEN if ui.auto_running else YELLOW
    st = font.render(status, True, status_clr)
    screen.blit(st, (L.margin + 130, L.n_row_y))

    # 진행률
    _draw_progress_bar(screen, L.prog_x, L.n_row_y + 2,
                       L.prog_w, L.prog_h, _calc_shor_progress(ui))

    # 단계 인디케이터
    _draw_phase_indicator(screen, shor.phase, font, L.indicator_x, L.indicator_y)

    # 회로 다이어그램
    _draw_circuit_diagram(screen, shor, info_font,
                          L.circuit_x, L.circuit_y, L.circuit_w, L.circuit_h)

    # 상태 메시지
    _draw_panel(screen, L.status_x, L.status_y, L.status_w, L.status_h,
                "Status", font, info_font)
    msg_lines = _wrap_text(shor.step_message, L.wrap_status)
    for i, line in enumerate(msg_lines):
        clr = GREEN if shor.phase == ShorPhase.SUCCESS else TEXT_CLR
        ms = info_font.render(line, True, clr)
        screen.blit(ms, (L.status_text_x, L.status_msg_y + i * 16))

    # 그래프
    if shor.qft_amplitudes:
        _draw_qft_histogram(screen, shor.qft_amplitudes, info_font,
                            L.graph_x, L.graph_y, L.graph_w_auto, L.graph_h_auto,
                            visible_count=ui.qft_anim_count)
    elif shor.mod_exp_table:
        _draw_mod_exp_graph(screen, shor.mod_exp_table,
                            shor.mod_exp_period_visual, info_font,
                            L.graph_x, L.graph_y, L.graph_w_auto, L.graph_h_auto,
                            visible_count=ui.mod_exp_anim_count)

    # 연분수
    if shor.qft_current:
        _draw_continued_fraction(screen, shor.qft_current, info_font,
                                 L.cf_x_auto, L.cf_y)

    # 결과
    if shor.factors:
        p, q = shor.factors
        result = title_font.render(f"{shor.number} = {p} × {q}", True, GREEN)
        screen.blit(result, (L.W // 2 - result.get_width() // 2, L.result_y_auto))

    # 입력 필드
    if shor.phase in (ShorPhase.INPUT, ShorPhase.DONE, ShorPhase.SUCCESS):
        _draw_input_field(screen, ui, font, L.margin, L.input_y)


def _draw_rsa_mode(screen, ui, font, title_font, info_font):
    """RSA Threat 모드."""
    L = _layout
    shor = ui.shor
    rsa = shor.rsa

    # 제목
    title = title_font.render(t("shor_title_rsa"), True, RED)
    screen.blit(title, (L.W // 2 - title.get_width() // 2, L.title_y))

    # 난이도 표시
    diff_keys = ["shor_rsa_diff_easy", "shor_rsa_diff_medium",
                  "shor_rsa_diff_hard", "shor_rsa_diff_expert"]
    dk = diff_keys[min(ui.rsa_difficulty, len(diff_keys) - 1)]
    diff = font.render(t("shor_rsa_difficulty", name=t(dk), n=rsa.rsa_n),
                       True, YELLOW)
    screen.blit(diff, (L.margin, L.n_row_y))

    # RSA 키 정보 패널
    _draw_panel(screen, L.rsa_pub_x, L.rsa_pub_y, L.rsa_pub_w, L.rsa_pub_h,
                t("shor_rsa_public_key"), title_font, info_font)
    info_lines = [
        t("shor_rsa_n_line", n=rsa.rsa_n),
        t("shor_rsa_e_line", e=rsa.rsa_e),
        t("shor_rsa_plain_line", m=rsa.plaintext),
        t("shor_rsa_cipher_line", c=rsa.ciphertext),
    ]
    for i, line in enumerate(info_lines):
        ls = info_font.render(line, True, TEXT_CLR)
        screen.blit(ls, (L.rsa_info_x, L.rsa_info_y + i * 18))

    # 비밀키 (크랙 전 숨김)
    _draw_panel(screen, L.rsa_sec_x, L.rsa_sec_y, L.rsa_sec_w, L.rsa_sec_h,
                t("shor_rsa_secret_key"), title_font, info_font)
    if rsa.cracked:
        match_str = t("shor_rsa_match_yes") if rsa.decrypted == rsa.plaintext \
            else t("shor_rsa_match_no")
        secret_lines = [
            t("shor_rsa_p_q_line", p=rsa.cracked_p, q=rsa.cracked_q),
            t("shor_rsa_d_line", d=rsa.cracked_d),
            t("shor_rsa_decrypt_line", m=rsa.decrypted),
            match_str,
        ]
        for i, line in enumerate(secret_lines):
            clr = GREEN if i == 3 and rsa.decrypted == rsa.plaintext else TEXT_CLR
            ls = info_font.render(line, True, clr)
            screen.blit(ls, (L.rsa_sec_text_x, L.rsa_info_y + i * 18))
    else:
        for i in range(4):
            ls = info_font.render("? ? ? ? ? ? ? ?", True, SUBTEXT)
            screen.blit(ls, (L.rsa_sec_text_x, L.rsa_info_y + i * 18))

    # 크래킹 상태
    if ui.rsa_phase == 0:
        msg = title_font.render(t("shor_rsa_press_space"), True, YELLOW)
        screen.blit(msg, (L.W // 2 - msg.get_width() // 2, L.rsa_status_y))
    elif ui.rsa_phase == 1:
        # 크래킹 중 — Shor 알고리즘 진행 표시
        _draw_panel(screen, L.margin * 2, L.rsa_crack_panel_y,
                    L.W - L.margin * 4, L.rsa_crack_panel_h,
                    "", title_font, info_font)

        msg = title_font.render(t("shor_rsa_cracking"), True, RED)
        screen.blit(msg, (L.W // 2 - msg.get_width() // 2,
                          L.rsa_crack_title_y))

        _draw_progress_bar(screen, L.prog_x, L.rsa_crack_prog_y,
                           L.W - L.prog_x * 2, 12,
                           _calc_shor_progress(ui), RED)

        _draw_phase_indicator(screen, shor.phase, info_font,
                              L.rsa_crack_indicator_x, L.rsa_crack_indicator_y)

        if shor.step_message:
            msg_lines = _wrap_text(shor.step_message, L.wrap_rsa_msg)
            for i, line in enumerate(msg_lines[:3]):
                ms = info_font.render(line, True, TEXT_CLR)
                screen.blit(ms, (L.rsa_crack_msg_x,
                                 L.rsa_crack_msg_y + i * 16))

        if shor.attempt > 0:
            att = info_font.render(
                f"Attempt #{shor.attempt}  a = {shor.a}", True, TEAL)
            screen.blit(att, (L.rsa_crack_msg_x, L.rsa_crack_attempt_y))
    elif ui.rsa_phase >= 2:
        _draw_panel(screen, L.margin * 2, L.rsa_crack_panel_y,
                    L.W - L.margin * 4, 50, "", title_font, info_font)
        cracked = title_font.render(
            t("shor_rsa_cracked", n=rsa.rsa_n, p=rsa.cracked_p,
              q=rsa.cracked_q),
            True, GREEN)
        screen.blit(cracked, (L.W // 2 - cracked.get_width() // 2,
                               L.rsa_cracked_y))

        if shor.factors:
            method = info_font.render(
                t("shor_rsa_method", method=shor.factor_method,
                  attempts=shor.attempt),
                True, PURPLE)
            screen.blit(method, (L.W // 2 - method.get_width() // 2,
                                 L.rsa_method_y))

    # QKD 동기 메시지
    if ui.rsa_phase >= 3:
        _draw_panel(screen, L.margin * 2, L.rsa_qkd_y,
                    L.W - L.margin * 4, L.rsa_qkd_h,
                    t("shor_rsa_why_qkd"), title_font, info_font)
        msg_lines = _wrap_text(get_qkd_motivation(), L.wrap_qkd)
        for i, line in enumerate(msg_lines[:7]):
            ms = info_font.render(line, True, YELLOW)
            screen.blit(ms, (L.rsa_qkd_text_x, L.rsa_qkd_text_y + i * 18))

    # 화살표 (시각적)
    if rsa.cracked:
        ax = L.W // 2
        ay = L.rsa_arrow_y
        for i in range(3):
            pygame.draw.polygon(screen, RED, [
                (ax - 8, ay + i * 6), (ax + 8, ay + i * 6),
                (ax, ay + 5 + i * 6)])

    # 하단 힌트: 난이도 변경
    hint = info_font.render(t("shor_rsa_hint"), True, SUBTEXT)
    screen.blit(hint, (L.W // 2 - hint.get_width() // 2, L.rsa_hint_y))


def _draw_input_field(screen, ui, font, x, y):
    """숫자 입력 필드."""
    label = font.render(t("shor_input_label"), True, TEXT_CLR)
    screen.blit(label, (x, y))

    # 입력 박스
    box_x = x + label.get_width() + 10
    box_w = 120
    box_clr = ACCENT if ui.input_active else OVERLAY_CLR
    pygame.draw.rect(screen, PANEL_BG, (box_x, y - 2, box_w, 22),
                     border_radius=3)
    pygame.draw.rect(screen, box_clr, (box_x, y - 2, box_w, 22), 2,
                     border_radius=3)

    # 입력 텍스트
    txt = font.render(ui.input_buffer, True, WHITE)
    screen.blit(txt, (box_x + 5, y))

    # 커서
    if ui.input_active and int(ui.t * 2) % 2 == 0:
        cx = box_x + 5 + txt.get_width()
        pygame.draw.line(screen, ACCENT, (cx, y), (cx, y + 16), 1)

    # 힌트
    hint = font.render(t("shor_input_hint"), True, SUBTEXT)
    screen.blit(hint, (box_x + box_w + 10, y))


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


# ── 메인 시뮬레이션 ──────────────────────────────────

def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(t("game_title_shor"))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 13)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)
    info_font = pygame.font.SysFont("Consolas", 11)

    # 난이도 선택
    chosen = choose_difficulty(screen, font)
    if chosen is None:
        on_theme_change(_load_theme_colors)  # cleanup
        pygame.quit()
        return
    preset = get_preset(chosen)
    shor_preset = preset.get("shor", {})
    default_number = shor_preset.get("default_number", 15)
    anim_speed = shor_preset.get("animation_speed", ANIMATION_SPEED)
    rsa_diff = shor_preset.get("rsa_default_difficulty", RSA_DEFAULT_DIFFICULTY)

    ui = UIState()
    ui.difficulty = chosen
    ui.shor = ShorState(number=default_number)
    ui.input_buffer = str(default_number)
    ui.auto_interval = anim_speed
    ui.rsa_difficulty = rsa_diff
    # 초기 상태 시작
    shor_step(ui.shor)  # INPUT → CLASSICAL_PRECHECK

    help_overlay = HelpOverlay("shor_algorithm")
    tutorial = TutorialOverlay("shor_algorithm")
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("shor_algorithm")
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
                    if ui.shor.phase not in (ShorPhase.SUCCESS, ShorPhase.DONE):
                        shor_step(ui.shor)
                        ui.total_steps += 1
                        if ui.shor.phase == ShorPhase.SUCCESS:
                            ui.numbers_factored += 1
                            snd.play("achievement")
                            ui.auto_running = False
                            break
                    else:
                        ui.auto_running = False
                        break

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
                if ui.input_active:
                    if event.key == pygame.K_RETURN:
                        _submit_input(ui, snd)
                    elif event.key == pygame.K_BACKSPACE:
                        ui.input_buffer = ui.input_buffer[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        ui.input_active = False
                    elif event.unicode.isdigit() and len(ui.input_buffer) < 6:
                        ui.input_buffer += event.unicode
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
                    # 숫자 입력 활성화
                    ui.input_active = True

                # ── 프리셋 키 (1/2/3) ──
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    _apply_difficulty(ui, {
                        pygame.K_1: "easy",
                        pygame.K_2: "normal",
                        pygame.K_3: "hard",
                    }[event.key], snd)

                # ── Step 모드 키 ──
                elif ui.mode == MODE_STEP:
                    if event.key == pygame.K_SPACE:
                        if ui.shor.phase not in (ShorPhase.SUCCESS,
                                                 ShorPhase.DONE):
                            shor_step(ui.shor)
                            ui.total_steps += 1
                            snd.play("click")
                            if ui.shor.phase == ShorPhase.SUCCESS:
                                ui.numbers_factored += 1
                                snd.play("achievement")
                        else:
                            # 완료 후 → 입력 모드
                            ui.input_active = True
                    elif event.key == pygame.K_r:
                        reset_state(ui.shor)
                        shor_step(ui.shor)
                        snd.play("click")

                # ── Auto 모드 키 ──
                elif ui.mode == MODE_AUTO:
                    if event.key == pygame.K_SPACE:
                        if ui.shor.phase in (ShorPhase.SUCCESS,
                                             ShorPhase.DONE):
                            ui.input_active = True
                        else:
                            ui.auto_running = not ui.auto_running
                            snd.play("click")
                    elif event.key == pygame.K_r:
                        ui.auto_running = False
                        reset_state(ui.shor)
                        shor_step(ui.shor)
                        snd.play("click")
                    elif event.key == pygame.K_UP:
                        ui.auto_interval = max(0.1, ui.auto_interval - 0.1)
                    elif event.key == pygame.K_DOWN:
                        ui.auto_interval = min(2.0, ui.auto_interval + 0.1)

                # ── RSA 모드 키 ──
                elif ui.mode == MODE_RSA:
                    if event.key == pygame.K_SPACE:
                        if ui.rsa_phase == 0:
                            # 크래킹 시작
                            ui.rsa_phase = 1
                            ui.rsa_crack_timer = 0.0
                            shor_step(ui.shor)  # INPUT → CLASSICAL_PRECHECK
                            snd.play("click")
                        elif ui.rsa_phase == 1:
                            pass  # 진행 중
                        elif ui.rsa_phase == 2:
                            ui.rsa_phase = 3
                            snd.play("click")
                        elif ui.rsa_phase == 3:
                            # 리셋
                            ui.rsa_phase = 0
                            setup_rsa_demo(ui.shor, ui.rsa_difficulty)
                    elif event.key in (pygame.K_UP, pygame.K_RIGHT):
                        ui.rsa_difficulty = min(len(RSA_EXAMPLES) - 1,
                                                ui.rsa_difficulty + 1)
                        ui.rsa_phase = 0
                        setup_rsa_demo(ui.shor, ui.rsa_difficulty)
                        snd.play("click")
                    elif event.key in (pygame.K_DOWN, pygame.K_LEFT):
                        ui.rsa_difficulty = max(0, ui.rsa_difficulty - 1)
                        ui.rsa_phase = 0
                        setup_rsa_demo(ui.shor, ui.rsa_difficulty)
                        snd.play("click")

        # ── RSA 크래킹 단계별 실행 (이벤트 외부) ──
        if ui.mode == MODE_RSA and ui.rsa_phase == 1:
            ui.rsa_crack_timer += dt
            if ui.rsa_crack_timer >= RSA_CRACK_SPEED:
                ui.rsa_crack_timer = 0.0
                if ui.shor.phase == ShorPhase.SUCCESS:
                    # 소인수분해 성공 → RSA 비밀키 복원/복호화
                    if finalize_rsa_crack(ui.shor):
                        ui.rsa_phase = 2
                        ui.numbers_factored += 1
                        snd.play("achievement")
                    else:
                        ui.rsa_phase = 0
                elif ui.shor.phase == ShorPhase.DONE:
                    # 최대 시도 초과 → 실패 리셋
                    ui.rsa_phase = 0
                else:
                    shor_step(ui.shor)
                    ui.total_steps += 1

        # ── 레코딩 ──
        recorder.record_frame({
            "mode": ui.mode,
            "phase": ui.shor.phase.name,
            "number": ui.shor.number,
            "attempt": ui.shor.attempt,
        })

        # ── 막대 애니메이션 업데이트 ──
        _update_bar_animation(ui, dt)

        # ── 렌더링 ──
        screen.fill(BG)

        # 상단: 모드 탭
        L = _layout
        for i, name in enumerate(MODE_NAMES):
            tab_x = L.margin + i * L.tab_w
            is_sel = (i == ui.mode)
            tab_clr = ACCENT if is_sel else OVERLAY_CLR
            tw = L.tab_w - int(L.margin * 0.5)
            pygame.draw.rect(screen, tab_clr,
                             (tab_x, L.tab_y, tw, L.tab_h),
                             0 if is_sel else 1,
                             border_radius=4)
            ts_text = font.render(name, True, BG if is_sel else TEXT_CLR)
            screen.blit(ts_text, (tab_x + tw // 2 - ts_text.get_width() // 2,
                                  L.tab_y + L.tab_label_offset_y))

        # 모드별 렌더링
        if ui.mode == MODE_STEP:
            _draw_step_mode(screen, ui, font, title_font, info_font)
        elif ui.mode == MODE_AUTO:
            _draw_auto_mode(screen, ui, font, title_font, info_font)
        elif ui.mode == MODE_RSA:
            _draw_rsa_mode(screen, ui, font, title_font, info_font)

        # 하단 힌트 (공통)
        if ui.mode == MODE_STEP:
            hints = [t("shor_hint_step_1"), t("shor_hint_step_2")]
        elif ui.mode == MODE_AUTO:
            hints = [t("shor_hint_auto_1"), t("shor_hint_auto_2")]
        else:
            hints = [t("shor_hint_rsa_1"), t("shor_hint_rsa_2")]
        for i, hint in enumerate(hints):
            hs = info_font.render(hint, True, TEXT_CLR)
            screen.blit(hs, (L.W // 2 - hs.get_width() // 2,
                             L.hint_y1 + i * 16))

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
        perf.draw_overlay(screen, info_font, x=L.W - 250, y=4)

        pygame.display.flip()

    perf.log_summary()

    # 가장 큰 소인수분해 성공 수 추적
    largest = 0
    if ui.shor.factors:
        largest = ui.shor.number
    for h in ui.shor.attempt_history:
        if h.get("reason") == "success":
            n = h.get("factors", (0, 0))
            if isinstance(n, tuple) and len(n) == 2:
                largest = max(largest, n[0] * n[1])

    session_data = {
        "play_time": round(time.time() - ui.start_time, 1),
        "numbers_factored": ui.numbers_factored,
        "total_steps": ui.total_steps,
        "last_number": ui.shor.number,
        "largest_factored": largest,
    }

    finalize_session(
        "shor_algorithm",
        session_data,
        recorder=recorder,
        recorder_meta={"play_time": session_data["play_time"]},
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def _update_bar_animation(ui, dt):
    """모듈러 지수 그래프 / QFT 히스토그램 막대 애니메이션 업데이트."""
    shor = ui.shor

    # 테이블 변경 감지 → 카운터 리셋
    cur_mod_len = len(shor.mod_exp_table)
    cur_qft_len = len(shor.qft_amplitudes)

    if cur_mod_len != ui._prev_mod_exp_len:
        ui._prev_mod_exp_len = cur_mod_len
        ui.mod_exp_anim_count = 0
        ui._anim_timer = 0.0

    if cur_qft_len != ui._prev_qft_len:
        ui._prev_qft_len = cur_qft_len
        ui.qft_anim_count = 0
        ui._anim_timer = 0.0

    # 타이머 기반 막대 추가
    mod_target = cur_mod_len
    qft_target = cur_qft_len
    need_anim = (ui.mod_exp_anim_count < mod_target
                 or ui.qft_anim_count < qft_target)

    if need_anim:
        ui._anim_timer += dt
        while ui._anim_timer >= BAR_ANIM_INTERVAL:
            ui._anim_timer -= BAR_ANIM_INTERVAL
            if ui.mod_exp_anim_count < mod_target:
                ui.mod_exp_anim_count += 1
            if ui.qft_anim_count < qft_target:
                ui.qft_anim_count += 1


def _apply_difficulty(ui, name, snd):
    """프리셋 난이도 적용 (1/2/3 키)."""
    preset = get_preset(name)
    shor_preset = preset.get("shor", {})
    if not shor_preset:
        return

    default_number = shor_preset.get("default_number", 15)
    anim_speed = shor_preset.get("animation_speed", ANIMATION_SPEED)
    rsa_diff = shor_preset.get("rsa_default_difficulty", RSA_DEFAULT_DIFFICULTY)

    ui.difficulty = name
    ui.auto_interval = anim_speed
    ui.rsa_difficulty = rsa_diff
    ui.auto_running = False

    # 현재 모드에 맞게 리셋
    if ui.mode == MODE_RSA:
        setup_rsa_demo(ui.shor, ui.rsa_difficulty)
        ui.rsa_phase = 0
    else:
        ui.shor = ShorState(number=default_number)
        ui.input_buffer = str(default_number)
        reset_state(ui.shor, default_number)
        shor_step(ui.shor)

    snd.play("click")


def _submit_input(ui, snd):
    """숫자 입력 확인."""
    ui.input_active = False
    try:
        n = int(ui.input_buffer)
        if n >= 2:
            reset_state(ui.shor, n)
            shor_step(ui.shor)  # INPUT → CLASSICAL_PRECHECK
            snd.play("click")
    except ValueError:
        pass


def _on_mode_change(ui):
    """모드 전환 시 초기화."""
    if ui.mode == MODE_RSA:
        setup_rsa_demo(ui.shor, ui.rsa_difficulty)
        ui.rsa_phase = 0
    elif ui.mode in (MODE_STEP, MODE_AUTO):
        reset_state(ui.shor)
        shor_step(ui.shor)
        ui.auto_running = False


def open_shor_algorithm():
    """외부에서 호출하는 진입점."""
    run_simulation()
