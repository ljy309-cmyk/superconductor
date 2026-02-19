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
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from perf_monitor import PerfMonitor
from quantum.shor_algorithm_engine import (
    PHASE_DESCRIPTIONS,
    QKD_MOTIVATION_MESSAGE,
    RSA_EXAMPLES,
    ShorPhase,
    ShorState,
    crack_rsa,
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


# ── UI 상태 ──────────────────────────────────────────

@dataclass
class UIState:
    """UI 전체 상태."""
    mode: int = MODE_STEP
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

    # 입력
    input_buffer: str = "15"
    input_active: bool = False

    # 통계
    numbers_factored: int = 0
    total_steps: int = 0

    # 히스토그램 선택
    show_qft_detail: bool = False


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


def _draw_mod_exp_graph(screen, table, period, font, x, y, w, h):
    """a^x mod N 주기 그래프."""
    if not table:
        return

    n = len(table)
    max_val = max(e.value for e in table) or 1
    bar_w = max(1, (w - 20) // n)

    for i, entry in enumerate(table):
        bx = x + 10 + i * bar_w
        bar_h = int((h - 30) * entry.value / max_val)
        by = y + h - 10 - bar_h

        # 주기 강조: 주기 시작점마다 다른 색
        if period > 0 and i % period == 0:
            clr = YELLOW
        else:
            clr = ACCENT

        pygame.draw.rect(screen, clr, (bx, by, max(1, bar_w - 1), bar_h))

    # 주기 구분선
    if period > 0:
        for k in range(1, n // period + 1):
            lx = x + 10 + k * period * bar_w
            if lx < x + w:
                pygame.draw.line(screen, RED, (lx, y + 5), (lx, y + h - 10), 1)

    # 레이블
    label = font.render(f"a^x mod N  (period={period})" if period > 0
                        else "a^x mod N", True, TEXT_CLR)
    screen.blit(label, (x + 10, y + 2))


def _draw_qft_histogram(screen, amplitudes, font, x, y, w, h):
    """QFT 확률 분포 히스토그램."""
    if not amplitudes:
        return

    n = len(amplitudes)
    max_val = max(amplitudes) or 1
    bar_w = max(1, (w - 20) // min(n, 128))

    # 너무 많으면 간추림
    step = max(1, n // 128)

    for i in range(0, n, step):
        bx = x + 10 + (i // step) * bar_w
        bar_h = int((h - 30) * amplitudes[i] / max_val)
        by = y + h - 10 - bar_h

        if amplitudes[i] > max_val * 0.5:
            clr = YELLOW
        elif amplitudes[i] > max_val * 0.1:
            clr = PURPLE
        else:
            clr = OVERLAY_CLR

        pygame.draw.rect(screen, clr, (bx, by, max(1, bar_w - 1), bar_h))

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
    shor = ui.shor

    # 제목
    title = title_font.render(t("shor_title_step"), True, ACCENT)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 42))

    # N 표시
    n_text = font.render(f"N = {shor.number}", True, TEXT_CLR)
    screen.blit(n_text, (20, 70))

    # 시도 횟수
    if shor.attempt > 0:
        att = font.render(f"Attempt #{shor.attempt}  a = {shor.a}", True, TEAL)
        screen.blit(att, (150, 70))

    # 좌측: 단계 인디케이터
    _draw_phase_indicator(screen, shor.phase, font, 20, 100)

    # 중앙 상단: 양자 회로 다이어그램
    _draw_circuit_diagram(screen, shor, info_font, 200, 90, 380, 130)

    # 우측 상단: 상태 메시지
    _draw_panel(screen, 600, 90, 280, 130, "Status", font, info_font)
    # 현재 메시지
    msg_lines = _wrap_text(shor.step_message, 35)
    for i, line in enumerate(msg_lines):
        clr = GREEN if shor.phase == ShorPhase.SUCCESS else TEXT_CLR
        ms = info_font.render(line, True, clr)
        screen.blit(ms, (610, 115 + i * 16))
    # 단계 설명
    desc_lines = _wrap_text(get_phase_description(shor.phase), 35)
    for i, line in enumerate(desc_lines[:3]):
        ds = info_font.render(line, True, SUBTEXT)
        screen.blit(ds, (610, 170 + i * 14))

    # 중앙 하단: 모듈러 지수 그래프 / QFT 히스토그램
    if shor.qft_amplitudes:
        _draw_qft_histogram(screen, shor.qft_amplitudes, info_font,
                            20, 240, 420, 150)
    elif shor.mod_exp_table:
        _draw_mod_exp_graph(screen, shor.mod_exp_table,
                            shor.mod_exp_period_visual, info_font,
                            20, 240, 420, 150)

    # 우측 하단: 연분수 / 결과
    if shor.qft_current:
        _draw_continued_fraction(screen, shor.qft_current, info_font,
                                 460, 250)

    # 최종 결과
    if shor.factors:
        p, q = shor.factors
        result = title_font.render(f"{shor.number} = {p} × {q}", True, GREEN)
        screen.blit(result, (WIDTH // 2 - result.get_width() // 2, 410))
        method = info_font.render(f"Method: {shor.factor_method}", True, PURPLE)
        screen.blit(method, (WIDTH // 2 - method.get_width() // 2, 440))
    elif shor.is_prime:
        result = title_font.render(f"{shor.number} is PRIME", True, RED)
        screen.blit(result, (WIDTH // 2 - result.get_width() // 2, 410))

    # 시도 히스토리
    if shor.attempt_history:
        hy = 470
        hist_title = info_font.render(t("shor_attempt_history"), True, ACCENT)
        screen.blit(hist_title, (20, hy))
        for i, h in enumerate(shor.attempt_history[-4:]):
            reason = h.get("reason", "")
            clr = GREEN if reason == "success" else YELLOW
            hs = info_font.render(
                f"  #{h['attempt']}: a={h['a']}, r={h.get('r','?')} → {reason}",
                True, clr)
            screen.blit(hs, (20, hy + 16 + i * 14))

    # 입력 필드 (DONE 또는 INPUT 상태일 때)
    if shor.phase in (ShorPhase.INPUT, ShorPhase.DONE, ShorPhase.SUCCESS):
        _draw_input_field(screen, ui, font, 20, HEIGHT - 70)


def _draw_auto_mode(screen, ui, font, title_font, info_font):
    """Auto 모드."""
    shor = ui.shor

    # 제목
    title = title_font.render(t("shor_title_auto"), True, ACCENT)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 42))

    # N 표시 + 진행 상태
    n_text = font.render(f"N = {shor.number}", True, TEXT_CLR)
    screen.blit(n_text, (20, 70))

    status = t("shor_auto_running") if ui.auto_running else t("shor_auto_paused")
    status_clr = GREEN if ui.auto_running else YELLOW
    st = font.render(status, True, status_clr)
    screen.blit(st, (150, 70))

    # 진행률
    if shor.phase != ShorPhase.DONE and shor.phase != ShorPhase.SUCCESS:
        progress = shor.phase.value / ShorPhase.DONE.value
    else:
        progress = 1.0
    _draw_progress_bar(screen, 300, 72, 200, 14, progress)

    # 단계 인디케이터
    _draw_phase_indicator(screen, shor.phase, font, 20, 100)

    # 회로 다이어그램
    _draw_circuit_diagram(screen, shor, info_font, 200, 90, 380, 130)

    # 상태 메시지
    _draw_panel(screen, 600, 90, 280, 130, "Status", font, info_font)
    msg_lines = _wrap_text(shor.step_message, 35)
    for i, line in enumerate(msg_lines):
        clr = GREEN if shor.phase == ShorPhase.SUCCESS else TEXT_CLR
        ms = info_font.render(line, True, clr)
        screen.blit(ms, (610, 115 + i * 16))

    # 그래프
    if shor.qft_amplitudes:
        _draw_qft_histogram(screen, shor.qft_amplitudes, info_font,
                            20, 240, 560, 160)
    elif shor.mod_exp_table:
        _draw_mod_exp_graph(screen, shor.mod_exp_table,
                            shor.mod_exp_period_visual, info_font,
                            20, 240, 560, 160)

    # 연분수
    if shor.qft_current:
        _draw_continued_fraction(screen, shor.qft_current, info_font,
                                 600, 250)

    # 결과
    if shor.factors:
        p, q = shor.factors
        result = title_font.render(f"{shor.number} = {p} × {q}", True, GREEN)
        screen.blit(result, (WIDTH // 2 - result.get_width() // 2, 420))

    # 입력 필드
    if shor.phase in (ShorPhase.INPUT, ShorPhase.DONE, ShorPhase.SUCCESS):
        _draw_input_field(screen, ui, font, 20, HEIGHT - 70)


def _draw_rsa_mode(screen, ui, font, title_font, info_font):
    """RSA Threat 모드."""
    shor = ui.shor
    rsa = shor.rsa

    # 제목
    title = title_font.render(t("shor_title_rsa"), True, RED)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 42))

    # 난이도 표시
    diff_keys = ["shor_rsa_diff_easy", "shor_rsa_diff_medium",
                  "shor_rsa_diff_hard", "shor_rsa_diff_expert"]
    dk = diff_keys[min(ui.rsa_difficulty, len(diff_keys) - 1)]
    diff = font.render(t("shor_rsa_difficulty", name=t(dk), n=rsa.rsa_n),
                       True, YELLOW)
    screen.blit(diff, (20, 70))

    # RSA 키 정보 패널
    _draw_panel(screen, 20, 95, 420, 120, t("shor_rsa_public_key"),
                title_font, info_font)
    info_lines = [
        t("shor_rsa_n_line", n=rsa.rsa_n),
        t("shor_rsa_e_line", e=rsa.rsa_e),
        t("shor_rsa_plain_line", m=rsa.plaintext),
        t("shor_rsa_cipher_line", c=rsa.ciphertext),
    ]
    for i, line in enumerate(info_lines):
        ls = info_font.render(line, True, TEXT_CLR)
        screen.blit(ls, (30, 118 + i * 18))

    # 비밀키 (크랙 전 숨김)
    _draw_panel(screen, 460, 95, 420, 120, t("shor_rsa_secret_key"),
                title_font, info_font)
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
            screen.blit(ls, (470, 118 + i * 18))
    else:
        for i in range(4):
            ls = info_font.render("? ? ? ? ? ? ? ?", True, SUBTEXT)
            screen.blit(ls, (470, 118 + i * 18))

    # 크래킹 상태
    if ui.rsa_phase == 0:
        # 대기
        msg = title_font.render(t("shor_rsa_press_space"), True, YELLOW)
        screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, 240))
    elif ui.rsa_phase == 1:
        # 크래킹 중
        msg = title_font.render(t("shor_rsa_cracking"), True, RED)
        screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, 240))
    elif ui.rsa_phase >= 2:
        # 크래킹 완료
        _draw_panel(screen, 40, 230, WIDTH - 80, 50, "", title_font, info_font)
        cracked = title_font.render(
            t("shor_rsa_cracked", n=rsa.rsa_n, p=rsa.cracked_p,
              q=rsa.cracked_q),
            True, GREEN)
        screen.blit(cracked, (WIDTH // 2 - cracked.get_width() // 2, 242))

        # Shor 결과
        if shor.factors:
            method = info_font.render(
                t("shor_rsa_method", method=shor.factor_method,
                  attempts=shor.attempt),
                True, PURPLE)
            screen.blit(method, (WIDTH // 2 - method.get_width() // 2, 268))

    # QKD 동기 메시지
    if ui.rsa_phase >= 3:
        _draw_panel(screen, 40, 300, WIDTH - 80, 170, t("shor_rsa_why_qkd"),
                    title_font, info_font)
        msg_lines = _wrap_text(get_qkd_motivation(), 80)
        for i, line in enumerate(msg_lines[:7]):
            ms = info_font.render(line, True, YELLOW)
            screen.blit(ms, (55, 325 + i * 18))

    # 화살표 (시각적)
    if rsa.cracked:
        # Shor → RSA broken 화살표
        ax = WIDTH // 2
        ay = 285
        for i in range(3):
            pygame.draw.polygon(screen, RED, [
                (ax - 8, ay + i * 6), (ax + 8, ay + i * 6),
                (ax, ay + 5 + i * 6)])

    # 하단 힌트: 난이도 변경
    hint = info_font.render(t("shor_rsa_hint"), True, SUBTEXT)
    screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 55))


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

    ui = UIState()
    # 초기 상태 시작
    shor_step(ui.shor)  # INPUT → CLASSICAL_PRECHECK

    help_overlay = HelpOverlay("shor_algorithm")
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

        # ── RSA 크래킹 실행 (이벤트 외부) ──
        if ui.mode == MODE_RSA and ui.rsa_phase == 1:
            success = crack_rsa(ui.shor)
            if success:
                ui.rsa_phase = 2
                ui.numbers_factored += 1
                snd.play("achievement")
            else:
                ui.rsa_phase = 0  # 실패 → 리셋

        # ── 레코딩 ──
        recorder.record_frame({
            "mode": ui.mode,
            "phase": ui.shor.phase.name,
            "number": ui.shor.number,
            "attempt": ui.shor.attempt,
        })

        # ── 렌더링 ──
        screen.fill(BG)

        # 상단: 모드 탭
        for i, name in enumerate(MODE_NAMES):
            tab_x = 20 + i * 280
            is_sel = (i == ui.mode)
            tab_clr = ACCENT if is_sel else OVERLAY_CLR
            pygame.draw.rect(screen, tab_clr,
                             (tab_x, 8, 260, 28), 0 if is_sel else 1,
                             border_radius=4)
            ts_text = font.render(name, True, BG if is_sel else TEXT_CLR)
            screen.blit(ts_text, (tab_x + 130 - ts_text.get_width() // 2, 14))

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
            screen.blit(hs, (WIDTH // 2 - hs.get_width() // 2,
                             HEIGHT - 38 + i * 16))

        # 오버레이
        toast.update(dt)
        toast.draw(screen, info_font)
        toast.draw_history(screen, info_font)
        help_overlay.draw(screen, info_font)
        perf.draw_overlay(screen, info_font, x=WIDTH - 250, y=4)

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
