"""양자 얽힘(Entanglement) 시뮬레이션 (Pygame).

3가지 실험 모드:
  1. Bell States: 벨 상태 4종 시각화 + 측정 통계
  2. CHSH Inequality: CHSH 부등식 위반 실험
  3. Quantum Teleportation: 양자 텔레포테이션 프로토콜 단계별 시각화
"""

import math
import random
import time
from dataclasses import dataclass, field

import pygame

from achievement_toast import AchievementToast
from quantum.ui_common import (
    HISTORY_PAGE_SIZE,
    draw_bar_pattern as _draw_bar_pattern,
    draw_page_dots,
    paginate,
    render_notify,
)
from config_loader import cfg
from difficulty_dialog import choose_difficulty
from game_base import finalize_session
from glossary import GlossaryOverlay
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from perf_monitor import PerfMonitor
from presets import get_preset
from quantum.entanglement_physics import (
    BELL_DESCRIPTIONS,
    BELL_LABELS,
    BELL_STATES,
    CHSH_CLASSICAL_BOUND,
    CHSH_QUANTUM_BOUND,
    TeleportationState,
    bell_probabilities,
    bloch_xyz,
    create_random_state,
    measure_bell,
    run_chsh_experiment,
    teleport_step,
)
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from sim_speed import apply_speed, cycle_sim_speed, speed_label
from sound_manager import get_sound_manager
from theme import is_high_contrast, is_reduced_motion, load_pg_colors, on_theme_change
from tutorial import TutorialOverlay

_log = get_module_logger("entanglement")

# ── 화면 설정 ────────────────────────────────────────
WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
FPS = cfg("display", "fps", 60)

# ── 설정값 ──────────────────────────────────────────
CHSH_SHOTS = cfg("entanglement", "chsh_shots", 200)
MEASURE_BATCH = cfg("entanglement", "measure_batch", 50)
TELEPORT_ANIM_SPEED = cfg("entanglement", "teleport_anim_speed", 1.5)

# ── 색상 (테마에서 동적 로드) ────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (137, 180, 250)
GREEN = (166, 227, 161)
RED = (243, 139, 168)
YELLOW = (249, 226, 175)
PURPLE = (203, 166, 247)
PINK = (245, 194, 231)
TEAL = (148, 226, 213)
OVERLAY_CLR = (49, 50, 68)
WHITE = (255, 255, 255)

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
}


def _load_theme_colors():
    load_pg_colors(_COLOR_MAP, globals())


# ── 게임 상태 ────────────────────────────────────────

MODE_BELL = 0
MODE_CHSH = 1
MODE_TELEPORT = 2
_MODE_TAB_KEYS = ["ent_tab_bell", "ent_tab_chsh", "ent_tab_teleport"]


# ── 레이아웃 ─────────────────────────────────────────


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

        # 상단 탭
        self.tab_y = int(8 * sy)
        self.tab_h = int(28 * sy)
        self.tab_w = (w - 2 * self.margin) // 3
        self.tab_label_y = int(14 * sy)

        # 공통 제목
        self.title_y = int(45 * sy)
        self.desc_y = int(72 * sy)

        # ── Bell 모드 ──
        self.bell_qubit_y = int(180 * sy)
        self.bell_qubit_offset = int(140 * sx)
        self.bell_qubit_r = int(35 * min(sx, sy))
        self.bell_prob_y = int(260 * sy)
        self.bell_prob_start = int(80 * sx)
        self.bell_bar_w = int(140 * sx)
        self.bell_bar_gap = int(30 * sx)
        self.bell_bar_max_h = int(80 * sy)
        self.bell_stat_y = int(400 * sy)
        self.bell_recent_x = int(550 * sx)
        self.bell_sel_y = h - int(100 * sy)
        self.bell_sel_start = int(120 * sx)
        self.bell_sel_gap = int(170 * sx)
        self.bell_sel_w = int(150 * sx)
        self.bell_sel_h = int(28 * sy)

        # ── CHSH 모드 ──
        self.chsh_alice_x = int(200 * sx)
        self.chsh_bob_x = int(700 * sx)
        self.chsh_mid_y = int(180 * sy)
        self.chsh_qubit_r = int(30 * min(sx, sy))
        self.chsh_res_y = int(270 * sy)
        self.chsh_corr_x = int(80 * sx)
        self.chsh_col_w = int(120 * sx)
        self.chsh_gauge_w = int(500 * sx)
        self.chsh_gauge_h = int(20 * sy)
        self.chsh_hist_y = int(460 * sy)
        self.chsh_hist_bar_w = int(50 * sx)

        # ── Teleport 모드 ──
        self.tp_steps_y = int(75 * sy)
        self.tp_step_start = int(60 * sx)
        self.tp_step_gap = int(138 * sx)
        self.tp_step_w = int(130 * sx)
        self.tp_step_h = int(22 * sy)
        self.tp_qubit_y = int(170 * sy)
        self.tp_input_x = int(150 * sx)
        self.tp_bob_x = w - int(150 * sx)
        self.tp_qubit_r = int(30 * min(sx, sy))
        self.tp_bloch_r = int(40 * min(sx, sy))
        self.tp_pv_y = int(310 * sy)
        self.tp_pv_start = int(60 * sx)
        self.tp_pv_gap = int(100 * sx)
        self.tp_pv_max_h = int(50 * sy)
        self.tp_log_y = int(420 * sy)
        self.tp_log_x = int(60 * sx)

        # 알림
        self.notify_y = h - int(56 * sy)

        # 하단 힌트
        self.hint_y = h - int(38 * sy)

        # 난이도 뱃지
        self.badge_y = h - int(16 * sy)

        # 퍼포먼스
        self.perf_x = w - int(250 * sx)


_layout = Layout()


def _rebuild_layout(w: int, h: int):
    """리사이즈 시 레이아웃 재계산."""
    global _layout
    _layout = Layout(w, h)


@dataclass
class EntanglementState:
    """얽힘 시뮬레이션 전체 상태."""
    mode: int = MODE_BELL
    t: float = 0.0
    paused: bool = False
    difficulty: str = "normal"

    # ── Bell States ──
    bell_selected: int = 0  # 0~3 (Φ+, Φ-, Ψ+, Ψ-)
    bell_measurements: list[tuple[int, int]] = field(default_factory=list)
    bell_counts: dict[str, int] = field(default_factory=lambda: {
        "00": 0, "01": 0, "10": 0, "11": 0,
    })
    bell_total: int = 0

    # ── CHSH ──
    chsh_result: dict = field(default_factory=dict)
    chsh_running: bool = False
    chsh_history: list[float] = field(default_factory=list)

    # ── Teleportation ──
    teleport: TeleportationState = field(default_factory=TeleportationState)
    teleport_log: list[str] = field(default_factory=list)
    teleport_anim_t: float = 0.0  # 애니메이션 타이머

    # ── 통계 ──
    total_measurements: int = 0
    chsh_experiments: int = 0
    teleport_completions: int = 0
    start_time: float = field(default_factory=time.time)

    # ── 알림 / 페이지네이션 ──
    notify_msg: str = ""
    notify_timer: float = 0.0
    history_page: int = 0

    def reset_bell(self):
        self.bell_measurements.clear()
        self.bell_counts = {"00": 0, "01": 0, "10": 0, "11": 0}
        self.bell_total = 0

    def reset_chsh(self):
        self.chsh_result = {}
        self.chsh_running = False

    def reset_teleport(self):
        alpha, beta = create_random_state()
        self.teleport.reset(alpha, beta)
        self.teleport_log.clear()
        self.teleport_anim_t = 0.0


def _notify(gs: EntanglementState, msg: str, duration: float = 2.0):
    """화면 하단 알림 표시."""
    gs.notify_msg = msg
    gs.notify_timer = duration


# ── 그리기 헬퍼 ──────────────────────────────────────

def _draw_qubit_sphere(screen, cx, cy, radius, state_label, color,
                       font, glow_t=0.0):
    """큐비트 시각화 (원 + 라벨)."""
    hc = is_high_contrast()
    if not is_reduced_motion():
        pulse = int(4 * math.sin(glow_t * 3))
        if pulse > 0:
            glow_surf = pygame.Surface(
                (2 * (radius + pulse), 2 * (radius + pulse)), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*color, 40),
                               (radius + pulse, radius + pulse), radius + pulse)
            screen.blit(glow_surf, (cx - radius - pulse, cy - radius - pulse))

    pygame.draw.circle(screen, color, (cx, cy), radius)
    outline_w = 3 if hc else 2
    pygame.draw.circle(screen, TEXT_CLR, (cx, cy), radius, outline_w)
    lbl = font.render(state_label, True, BG)
    screen.blit(lbl, (cx - lbl.get_width() // 2, cy - lbl.get_height() // 2))


def _draw_entanglement_line(screen, x1, y1, x2, y2, t_val,
                            color=PURPLE):
    """얽힘 연결선 (파동 효과)."""
    hc = is_high_contrast()
    line_w = 3 if hc else 2
    if is_reduced_motion():
        pygame.draw.line(screen, color, (int(x1), int(y1)),
                         (int(x2), int(y2)), line_w)
        return
    segments = 20
    points = []
    for i in range(segments + 1):
        frac = i / segments
        x = x1 + (x2 - x1) * frac
        y = y1 + (y2 - y1) * frac
        wave = math.sin(frac * math.pi * 4 + t_val * 3) * 8
        nx = -(y2 - y1)
        ny = (x2 - x1)
        length = math.hypot(nx, ny)
        if length > 0:
            nx /= length
            ny /= length
        x += nx * wave
        y += ny * wave
        points.append((int(x), int(y)))
    if len(points) > 1:
        pygame.draw.lines(screen, color, False, points, line_w)


def _draw_bar_chart(screen, x, y, w, h, data, colors, labels,
                    font, title=""):
    """수평 바 차트."""
    if title:
        t_surf = font.render(title, True, ACCENT)
        screen.blit(t_surf, (x, y - 18))

    total = sum(data) if sum(data) > 0 else 1
    bar_h = min(20, (h - 10) // max(len(data), 1))
    for i, (val, color, label) in enumerate(zip(data, colors, labels)):
        bar_y = y + i * (bar_h + 4)
        # 라벨
        lbl = font.render(label, True, TEXT_CLR)
        screen.blit(lbl, (x, bar_y))
        # 바
        bar_x = x + 50
        bar_w = int((w - 100) * val / total) if total > 0 else 0
        pygame.draw.rect(screen, OVERLAY_CLR, (bar_x, bar_y, w - 100, bar_h))
        pygame.draw.rect(screen, color, (bar_x, bar_y, bar_w, bar_h))
        tier = "high" if i % 2 == 0 else "mid"
        _draw_bar_pattern(screen, (bar_x, bar_y, bar_w, bar_h), color, tier)
        border_w = 2 if is_high_contrast() else 1
        pygame.draw.rect(screen, TEXT_CLR, (bar_x, bar_y, w - 100, bar_h), border_w)
        # 값
        v_surf = font.render(f"{val}", True, TEXT_CLR)
        screen.blit(v_surf, (x + w - 45, bar_y))




def _draw_bloch_mini(screen, cx, cy, radius, alpha, beta, font,
                     label=""):
    """미니 블로흐 구 시각화."""
    hc = is_high_contrast()
    bx, by, bz = bloch_xyz(alpha, beta)

    # 원 (적도)
    ring_w = 2 if hc else 1
    pygame.draw.circle(screen, OVERLAY_CLR, (cx, cy), radius, ring_w)
    # 타원 (측면)
    pygame.draw.ellipse(screen, OVERLAY_CLR,
                        (cx - radius, cy - radius // 3,
                         2 * radius, 2 * radius // 3), ring_w)
    # 축
    axis_w = 2 if hc else 1
    pygame.draw.line(screen, (*TEXT_CLR, 80), (cx, cy - radius),
                     (cx, cy + radius), axis_w)
    pygame.draw.line(screen, (*TEXT_CLR, 80), (cx - radius, cy),
                     (cx + radius, cy), axis_w)

    # 상태 벡터 포인트 (3D → 2D 사영)
    px = cx + int(bx * radius * 0.9)
    py = cy - int(bz * radius * 0.9)
    vec_w = 3 if hc else 2
    pygame.draw.circle(screen, GREEN, (px, py), 5)
    pygame.draw.line(screen, GREEN, (cx, cy), (px, py), vec_w)

    if label:
        lbl = font.render(label, True, TEXT_CLR)
        screen.blit(lbl, (cx - lbl.get_width() // 2, cy + radius + 4))


# ── 모드별 렌더링 ────────────────────────────────────

def _draw_bell_mode(screen, gs, font, title_font, info_font):
    """벨 상태 모드 렌더링."""
    L = _layout
    bell_name = BELL_LABELS[gs.bell_selected]
    state = BELL_STATES[bell_name]
    probs = bell_probabilities(state)

    # 제목
    title = title_font.render(
        t("ent_bell_title", name=bell_name), True, ACCENT)
    screen.blit(title, (L.W // 2 - title.get_width() // 2, L.title_y))

    desc = info_font.render(BELL_DESCRIPTIONS[bell_name], True, PURPLE)
    screen.blit(desc, (L.W // 2 - desc.get_width() // 2, L.desc_y))

    # Alice & Bob 큐비트
    alice_x = L.W // 2 - L.bell_qubit_offset
    alice_y = L.bell_qubit_y
    bob_x = L.W // 2 + L.bell_qubit_offset
    bob_y = L.bell_qubit_y
    qr = L.bell_qubit_r

    _draw_qubit_sphere(screen, alice_x, alice_y, qr, "A", ACCENT,
                       title_font, gs.t)
    _draw_qubit_sphere(screen, bob_x, bob_y, qr, "B", PURPLE,
                       title_font, gs.t)
    _draw_entanglement_line(screen, alice_x + qr, alice_y,
                            bob_x - qr, bob_y, gs.t)

    lbl_a = info_font.render("Alice", True, ACCENT)
    lbl_b = info_font.render("Bob", True, PURPLE)
    screen.blit(lbl_a, (alice_x - lbl_a.get_width() // 2, alice_y + 42))
    screen.blit(lbl_b, (bob_x - lbl_b.get_width() // 2, bob_y + 42))

    # 확률 분포
    prob_y = L.bell_prob_y
    prob_labels = ["|00⟩", "|01⟩", "|10⟩", "|11⟩"]
    prob_colors = [GREEN, ACCENT, PURPLE, RED]
    bar_w = L.bell_bar_w
    bar_gap = L.bell_bar_gap
    max_h = L.bell_bar_max_h
    for i, (p, lbl, clr) in enumerate(zip(probs, prob_labels, prob_colors)):
        bx = L.bell_prob_start + i * (bar_w + bar_gap)
        by = prob_y

        # 라벨
        ls = info_font.render(lbl, True, TEXT_CLR)
        screen.blit(ls, (bx + bar_w // 2 - ls.get_width() // 2, by))

        # 세로 바
        bar_h = int(max_h * p)
        bar_top = by + 18 + (max_h - bar_h)
        inner_w = bar_w - 60
        pygame.draw.rect(screen, OVERLAY_CLR,
                         (bx + 30, by + 18, inner_w, max_h))
        pygame.draw.rect(screen, clr,
                         (bx + 30, bar_top, inner_w, bar_h))
        tier = "high" if i % 2 == 0 else "mid"
        _draw_bar_pattern(screen, (bx + 30, bar_top, inner_w, bar_h),
                          clr, tier)
        _bw = 2 if is_high_contrast() else 1
        pygame.draw.rect(screen, TEXT_CLR,
                         (bx + 30, by + 18, inner_w, max_h), _bw)

        # 확률값
        ps = info_font.render(f"{p:.3f}", True, clr)
        screen.blit(ps, (bx + bar_w // 2 - ps.get_width() // 2,
                         by + 18 + max_h + 4))

    # 측정 통계
    stat_y = L.bell_stat_y
    stat_title = info_font.render(
        t("ent_bell_measurements", count=gs.bell_total), True, ACCENT)
    screen.blit(stat_title, (L.bell_prob_start, stat_y))

    if gs.bell_total > 0:
        counts = [gs.bell_counts["00"], gs.bell_counts["01"],
                  gs.bell_counts["10"], gs.bell_counts["11"]]
        _draw_bar_chart(screen, L.bell_prob_start, stat_y + 22, 400, 100,
                        counts, prob_colors, prob_labels, info_font)

    # 최근 측정 결과 표시 (페이지네이션)
    if gs.bell_measurements:
        page_items, gs.history_page, total_pages = paginate(gs.bell_measurements, gs.history_page)
        rx = L.bell_recent_x
        ry = stat_y
        title_text = t("ent_bell_recent")
        r_title = info_font.render(title_text, True, YELLOW)
        screen.blit(r_title, (rx, ry))

        # 도트 인디케이터
        draw_page_dots(screen,
                       rx + r_title.get_width() + 10,
                       ry + r_title.get_height() // 2,
                       total_pages, gs.history_page,
                       YELLOW, OVERLAY_CLR, OVERLAY_CLR)
        for i, (a, b) in enumerate(page_items):
            ms = info_font.render(f"|{a}{b}⟩", True, TEXT_CLR)
            screen.blit(ms, (rx, ry + 16 + i * 14))

    # 벨 상태 선택 가이드
    sel_y = L.bell_sel_y
    for i, name in enumerate(BELL_LABELS):
        is_sel = (i == gs.bell_selected)
        clr = ACCENT if is_sel else OVERLAY_CLR
        bx = L.bell_sel_start + i * L.bell_sel_gap
        pygame.draw.rect(screen, clr,
                         (bx, sel_y, L.bell_sel_w, L.bell_sel_h),
                         0 if is_sel else 1, border_radius=4)
        key_s = info_font.render(f"[{i + 1}] |{name}⟩", True,
                                 BG if is_sel else TEXT_CLR)
        screen.blit(key_s, (bx + L.bell_sel_w // 2 - key_s.get_width() // 2,
                            sel_y + 6))


def _draw_chsh_mode(screen, gs, font, title_font, info_font):
    """CHSH 부등식 모드 렌더링."""
    L = _layout
    title = title_font.render(t("ent_chsh_title"), True, ACCENT)
    screen.blit(title, (L.W // 2 - title.get_width() // 2, L.title_y))

    # 설명
    desc_lines = [
        t("ent_chsh_desc1"),
        t("ent_chsh_desc2"),
    ]
    for i, line in enumerate(desc_lines):
        ds = info_font.render(line, True, TEXT_CLR)
        screen.blit(ds, (L.W // 2 - ds.get_width() // 2, L.desc_y + i * 16))

    # Alice & Bob
    alice_x = L.chsh_alice_x
    bob_x = L.chsh_bob_x
    mid_y = L.chsh_mid_y
    qr = L.chsh_qubit_r

    _draw_qubit_sphere(screen, alice_x, mid_y, qr, "A", ACCENT,
                       font, gs.t)
    _draw_qubit_sphere(screen, bob_x, mid_y, qr, "B", PURPLE,
                       font, gs.t)
    _draw_entanglement_line(screen, alice_x + qr, mid_y,
                            bob_x - qr, mid_y, gs.t)

    # 측정 각도 표시
    angles_a = ["0°", "45°"]
    angles_b = ["22.5°", "67.5°"]
    a_lbl = info_font.render(
        t("ent_chsh_alice_angles", angles=', '.join(angles_a)), True, ACCENT)
    b_lbl = info_font.render(
        t("ent_chsh_bob_angles", angles=', '.join(angles_b)), True, PURPLE)
    screen.blit(a_lbl, (alice_x - 60, mid_y + 40))
    screen.blit(b_lbl, (bob_x - 60, mid_y + 40))

    # 결과 표시
    res_y = L.chsh_res_y
    corr_x = L.chsh_corr_x
    col_w = L.chsh_col_w
    if gs.chsh_result:
        e_mat = gs.chsh_result["E"]
        s_val = gs.chsh_result["S"]
        violated = gs.chsh_result["violated"]

        # 상관 행렬
        e_title = info_font.render(t("ent_chsh_corr_matrix"), True, YELLOW)
        screen.blit(e_title, (corr_x, res_y))

        headers = ["", "b1=22.5°", "b2=67.5°"]
        rows = [
            ["a1=0°", f"{e_mat[0][0]:+.3f}", f"{e_mat[0][1]:+.3f}"],
            ["a2=45°", f"{e_mat[1][0]:+.3f}", f"{e_mat[1][1]:+.3f}"],
        ]
        for col_i, h in enumerate(headers):
            hs = info_font.render(h, True, TEXT_CLR)
            screen.blit(hs, (corr_x + col_i * col_w, res_y + 20))
        for row_i, row in enumerate(rows):
            for col_i, cell in enumerate(row):
                cs = info_font.render(cell, True, ACCENT if col_i > 0 else TEXT_CLR)
                screen.blit(cs, (corr_x + col_i * col_w, res_y + 40 + row_i * 18))

        # S 값
        s_y = res_y + 100
        s_clr = RED if violated else GREEN
        s_txt = title_font.render(f"S = {s_val:+.4f}", True, s_clr)
        screen.blit(s_txt, (L.W // 2 - s_txt.get_width() // 2, s_y))

        verdict = (t("ent_chsh_violated") if violated
                   else t("ent_chsh_not_violated"))
        v_clr = RED if violated else GREEN
        v_surf = info_font.render(verdict, True, v_clr)
        screen.blit(v_surf, (L.W // 2 - v_surf.get_width() // 2, s_y + 28))

        # S값 게이지
        gauge_y = s_y + 60
        gauge_w = L.chsh_gauge_w
        gauge_x = L.W // 2 - gauge_w // 2
        gauge_h = L.chsh_gauge_h

        pygame.draw.rect(screen, OVERLAY_CLR,
                         (gauge_x, gauge_y, gauge_w, gauge_h))
        # 고전 한계 마커
        _hc = is_high_contrast()
        marker_w = 3 if _hc else 2
        cl_x = gauge_x + int(gauge_w * CHSH_CLASSICAL_BOUND / 4.0)
        pygame.draw.line(screen, YELLOW, (cl_x, gauge_y - 4),
                         (cl_x, gauge_y + gauge_h + 4), marker_w)
        cl_lbl = info_font.render("2.0", True, YELLOW)
        screen.blit(cl_lbl, (cl_x - 8, gauge_y - 16))
        # 양자 한계 마커
        qm_x = gauge_x + int(gauge_w * CHSH_QUANTUM_BOUND / 4.0)
        pygame.draw.line(screen, PURPLE, (qm_x, gauge_y - 4),
                         (qm_x, gauge_y + gauge_h + 4), marker_w)
        qm_lbl = info_font.render("2√2", True, PURPLE)
        screen.blit(qm_lbl, (qm_x - 10, gauge_y - 16))
        # S 포인터
        s_clamped = min(abs(s_val), 3.9)
        sp_x = gauge_x + int(gauge_w * s_clamped / 4.0)
        fill_w = sp_x - gauge_x
        pygame.draw.rect(screen, s_clr, (gauge_x, gauge_y, fill_w, gauge_h))
        gauge_border = 2 if _hc else 1
        pygame.draw.rect(screen, TEXT_CLR,
                         (gauge_x, gauge_y, gauge_w, gauge_h), gauge_border)
        # S 마커
        pygame.draw.circle(screen, WHITE, (sp_x, gauge_y + gauge_h // 2), 6)
        pygame.draw.circle(screen, s_clr, (sp_x, gauge_y + gauge_h // 2), 4)

    elif gs.chsh_running:
        run_txt = title_font.render(t("ent_chsh_running"), True, YELLOW)
        screen.blit(run_txt, (L.W // 2 - run_txt.get_width() // 2, res_y + 40))
    else:
        hint = info_font.render(t("ent_chsh_press_space"), True, TEXT_CLR)
        screen.blit(hint, (L.W // 2 - hint.get_width() // 2, res_y + 40))

    # S 값 히스토리 (페이지네이션)
    if gs.chsh_history:
        hist_y = L.chsh_hist_y
        page_items, gs.history_page, total_pages = paginate(
            gs.chsh_history, gs.history_page, page_size=15)
        total = len(gs.chsh_history)

        title_text = t("ent_chsh_history", count=total)
        hist_title = info_font.render(title_text, True, ACCENT)
        screen.blit(hist_title, (corr_x, hist_y))

        # 도트 인디케이터
        draw_page_dots(screen,
                       corr_x + hist_title.get_width() + 10,
                       hist_y + hist_title.get_height() // 2,
                       total_pages, gs.history_page,
                       ACCENT, OVERLAY_CLR, OVERLAY_CLR)

        # 미니 히스토리 바
        hist_bar_w = L.chsh_hist_bar_w
        for i, s_val in enumerate(page_items):
            bx = corr_x + i * hist_bar_w
            by = hist_y + 20
            s_abs = abs(s_val)
            bar_h = int(40 * min(s_abs / 3.0, 1.0))
            clr = RED if s_abs > CHSH_CLASSICAL_BOUND else GREEN
            tier = "high" if s_abs > CHSH_CLASSICAL_BOUND else "mid"
            bar_top = by + 40 - bar_h
            pygame.draw.rect(screen, clr, (bx, bar_top, 40, bar_h))
            _draw_bar_pattern(screen, (bx, bar_top, 40, bar_h), clr, tier)
            _hist_bw = 2 if is_high_contrast() else 1
            pygame.draw.rect(screen, TEXT_CLR, (bx, by, 40, 40), _hist_bw)
            vs = info_font.render(f"{s_val:.1f}", True, TEXT_CLR)
            screen.blit(vs, (bx + 20 - vs.get_width() // 2, by + 42))


def _draw_teleport_mode(screen, gs, font, title_font, info_font):
    """양자 텔레포테이션 모드 렌더링."""
    L = _layout
    title = title_font.render(t("ent_tp_title"), True, ACCENT)
    screen.blit(title, (L.W // 2 - title.get_width() // 2, L.title_y))

    ts = gs.teleport
    step = ts.step
    step_name = ts.step_names[min(step, 5)]

    # 단계 표시
    steps_y = L.tp_steps_y
    step_labels = [t("ent_tp_step_prepare"), t("ent_tp_step_bell_pair"),
                   t("ent_tp_step_entangle"), t("ent_tp_step_measure"),
                   t("ent_tp_step_classical"), t("ent_tp_step_correct")]
    for i, sl in enumerate(step_labels):
        sx = L.tp_step_start + i * L.tp_step_gap
        is_current = (i == min(step, 5))
        is_done = (i < step)
        if is_done:
            clr = GREEN
            bg_clr = (*GREEN, 40)
        elif is_current:
            clr = YELLOW
            bg_clr = (*YELLOW, 40)
        else:
            clr = OVERLAY_CLR
            bg_clr = (*OVERLAY_CLR, 30)

        # 배경
        step_surf = pygame.Surface((L.tp_step_w, L.tp_step_h), pygame.SRCALPHA)
        step_surf.fill(bg_clr)
        screen.blit(step_surf, (sx, steps_y))
        _step_bw = 2 if is_high_contrast() else 1
        pygame.draw.rect(screen, clr, (sx, steps_y, L.tp_step_w, L.tp_step_h),
                         _step_bw, border_radius=3)
        ss = info_font.render(f"{i + 1}. {sl}", True, clr)
        screen.blit(ss, (sx + L.tp_step_w // 2 - ss.get_width() // 2,
                         steps_y + 3))

    # 큐비트 시각화 (3개: Input, Alice, Bob)
    q_y = L.tp_qubit_y
    input_x = L.tp_input_x
    alice_x = L.W // 2
    bob_x = L.tp_bob_x
    qr = L.tp_qubit_r
    br = L.tp_bloch_r

    # Input qubit
    if step <= 2:
        _draw_qubit_sphere(screen, input_x, q_y, qr, "ψ", YELLOW,
                           font, gs.t)
        il = info_font.render(t("ent_tp_input"), True, YELLOW)
        screen.blit(il, (input_x - il.get_width() // 2, q_y + 36))
        # 블로흐
        _draw_bloch_mini(screen, input_x, q_y + 110, br,
                         ts.alpha, ts.beta, info_font, t("ent_tp_input_state"))
    elif step >= 3:
        # 측정된 상태
        m0, m1 = ts.measurement_result
        m_lbl = f"|{m0}{m1}⟩" if step >= 3 else "?"
        _draw_qubit_sphere(screen, input_x, q_y, qr, m_lbl, RED,
                           font, gs.t if step == 3 else 0)
        il = info_font.render(t("ent_tp_measured"), True, RED)
        screen.blit(il, (input_x - il.get_width() // 2, q_y + 36))

    # Alice
    a_clr = ACCENT if step >= 1 else OVERLAY_CLR
    _draw_qubit_sphere(screen, alice_x, q_y, qr, "A", a_clr, font,
                       gs.t if step >= 1 else 0)
    al = info_font.render("Alice", True, a_clr)
    screen.blit(al, (alice_x - al.get_width() // 2, q_y + 36))

    # Bob
    b_clr = PURPLE if step >= 1 else OVERLAY_CLR
    _draw_qubit_sphere(screen, bob_x, q_y, qr, "B", b_clr, font,
                       gs.t if step >= 1 else 0)
    bl = info_font.render("Bob", True, b_clr)
    screen.blit(bl, (bob_x - bl.get_width() // 2, q_y + 36))

    # 얽힘 연결선
    if 1 <= step <= 3:
        _draw_entanglement_line(screen, alice_x + qr, q_y,
                                bob_x - qr, q_y, gs.t, PURPLE)
    if 2 <= step <= 3:
        _draw_entanglement_line(screen, input_x + qr, q_y,
                                alice_x - qr, q_y, gs.t, YELLOW)

    # 고전 채널 (파선)
    if step >= 4:
        dash_y = q_y - 10
        _rm = is_reduced_motion()
        for dx in range(0, bob_x - alice_x - 60, 15):
            px = alice_x + qr + dx
            if _rm:
                alpha = 200
            else:
                alpha = max(0, min(255, int(200 * (1 - abs(
                    math.sin(gs.t * 2 + dx * 0.05))))))
            _cc_w = 3 if is_high_contrast() else 2
            pygame.draw.line(screen, (*YELLOW, alpha),
                             (px, dash_y), (px + 8, dash_y), _cc_w)
        cc_lbl = info_font.render(t("ent_tp_classical_channel"), True, YELLOW)
        screen.blit(cc_lbl, (L.W // 2 - cc_lbl.get_width() // 2,
                              dash_y - 16))

    # Bob 최종 상태 블로흐
    if step >= 6:
        _draw_bloch_mini(screen, bob_x, q_y + 110, br,
                         ts.bob_alpha, ts.bob_beta, info_font,
                         t("ent_tp_bob_state"))
        fid_clr = GREEN if ts.fidelity > 0.99 else YELLOW
        fid = info_font.render(
            t("ent_tp_fidelity", fidelity=f"{ts.fidelity:.4f}"), True, fid_clr)
        screen.blit(fid, (bob_x - fid.get_width() // 2, q_y + 170))

    # 확률 분포 (3큐비트 상태벡터)
    if 0 < step < 6:
        pv_y = L.tp_pv_y
        pv_title = info_font.render(t("ent_tp_state_vector"), True, ACCENT)
        screen.blit(pv_title, (L.tp_pv_start, pv_y))

        probs = [abs(a) ** 2 for a in ts.state_vector]
        labels_3q = [f"|{i:03b}⟩" for i in range(8)]
        max_h = L.tp_pv_max_h
        for i, (p, lbl) in enumerate(zip(probs, labels_3q)):
            bx = L.tp_pv_start + i * L.tp_pv_gap
            by = pv_y + 20
            bar_h = int(max_h * p)

            ls = info_font.render(lbl, True, TEXT_CLR)
            screen.blit(ls, (bx + 30 - ls.get_width() // 2, by + max_h + 4))

            pygame.draw.rect(screen, OVERLAY_CLR,
                             (bx + 10, by, 40, max_h))
            if bar_h > 0:
                clr = GREEN if p > 0.01 else OVERLAY_CLR
                bar_top = by + max_h - bar_h
                pygame.draw.rect(screen, clr,
                                 (bx + 10, bar_top, 40, bar_h))
                if p > 0.01:
                    tier = "high" if p > 0.3 else "mid"
                    _draw_bar_pattern(screen, (bx + 10, bar_top, 40, bar_h),
                                      clr, tier)
            _pv_bw = 2 if is_high_contrast() else 1
            pygame.draw.rect(screen, TEXT_CLR,
                             (bx + 10, by, 40, max_h), _pv_bw)

            if p > 0.01:
                ps = info_font.render(f"{p:.2f}", True, GREEN)
                screen.blit(ps, (bx + 30 - ps.get_width() // 2,
                                 by - 14))

    # 프로토콜 로그 (페이지네이션)
    log_y = L.tp_log_y
    page_items, gs.history_page, total_pages = paginate(gs.teleport_log, gs.history_page)

    title_text = t("ent_tp_protocol_log")
    log_title = info_font.render(title_text, True, ACCENT)
    screen.blit(log_title, (L.tp_log_x, log_y))

    # 도트 인디케이터
    draw_page_dots(screen,
                   L.tp_log_x + log_title.get_width() + 10,
                   log_y + log_title.get_height() // 2,
                   total_pages, gs.history_page,
                   ACCENT, OVERLAY_CLR, OVERLAY_CLR)
    for i, msg in enumerate(page_items):
        clr = GREEN if "Fidelity" in msg else TEXT_CLR
        ms = info_font.render(msg, True, clr)
        screen.blit(ms, (L.tp_log_x, log_y + 18 + i * 15))


# ── 메인 시뮬레이션 ──────────────────────────────────

def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption(t("game_title_entanglement"))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 13)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)
    info_font = pygame.font.SysFont("Consolas", 11)

    # 난이도 선택
    chosen = choose_difficulty(screen, font)
    if chosen is None:
        on_theme_change(_load_theme_colors)
        pygame.quit()
        return
    preset = get_preset(chosen)
    ent_preset = preset.get("entanglement", {})
    measure_batch = ent_preset.get("measure_batch", MEASURE_BATCH)
    chsh_shots = ent_preset.get("chsh_shots", CHSH_SHOTS)
    teleport_anim_speed = ent_preset.get("teleport_anim_speed", TELEPORT_ANIM_SPEED)

    gs = EntanglementState()
    gs.difficulty = chosen
    gs.reset_teleport()  # 초기 랜덤 상태

    help_overlay = HelpOverlay("entanglement")
    glossary = GlossaryOverlay()
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("entanglement")
    toast = AchievementToast()
    tutorial = TutorialOverlay("entanglement")
    perf = PerfMonitor(target_fps=FPS)

    running = True
    while running:
        raw_dt = clock.tick(FPS) / 1000.0
        dt = apply_speed(raw_dt)
        perf.tick(raw_dt)
        gs.t += dt

        # ── 이벤트 ──
        for event in pygame.event.get():
            if tutorial.handle_event(event):
                continue
            help_overlay.handle_event(event)
            glossary.handle_event(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                snd.handle_key(event.key)
                if event.key == pygame.K_ESCAPE:
                    if confirm_quit(screen, info_font):
                        running = False

                elif event.key == pygame.K_TAB:
                    # 모드 전환
                    gs.mode = (gs.mode + 1) % 3
                    gs.history_page = 0
                    snd.play("click")

                elif event.key == pygame.K_PAGEUP:
                    gs.history_page = max(0, gs.history_page - 1)
                elif event.key == pygame.K_PAGEDOWN:
                    gs.history_page += 1

                elif event.key == pygame.K_r:
                    # 리셋 (현재 모드)
                    if gs.mode == MODE_BELL:
                        gs.reset_bell()
                    elif gs.mode == MODE_CHSH:
                        gs.reset_chsh()
                    elif gs.mode == MODE_TELEPORT:
                        gs.reset_teleport()
                    gs.history_page = 0
                    _notify(gs, t("notify_reset"), 1.0)
                    snd.play("click")

                elif event.key == pygame.K_l:
                    toggle_locale()

                elif event.key == pygame.K_LEFTBRACKET:
                    cycle_sim_speed(-1)
                elif event.key == pygame.K_RIGHTBRACKET:
                    cycle_sim_speed(1)

                # ── Bell 모드 키 ──
                elif gs.mode == MODE_BELL:
                    if event.key in (pygame.K_1, pygame.K_2,
                                     pygame.K_3, pygame.K_4):
                        gs.bell_selected = event.key - pygame.K_1
                        gs.reset_bell()
                        snd.play("click")
                    elif event.key == pygame.K_SPACE:
                        # 배치 측정
                        bell_name = BELL_LABELS[gs.bell_selected]
                        state = BELL_STATES[bell_name]
                        for _ in range(measure_batch):
                            a, b = measure_bell(state)
                            gs.bell_measurements.append((a, b))
                            gs.bell_counts[f"{a}{b}"] += 1
                            gs.bell_total += 1
                            gs.total_measurements += 1
                        _notify(gs, t("ent_notify_measured",
                                      count=measure_batch), 1.0)
                        snd.play("click")
                    elif event.key == pygame.K_m:
                        # 단일 측정
                        bell_name = BELL_LABELS[gs.bell_selected]
                        state = BELL_STATES[bell_name]
                        a, b = measure_bell(state)
                        gs.bell_measurements.append((a, b))
                        gs.bell_counts[f"{a}{b}"] += 1
                        gs.bell_total += 1
                        gs.total_measurements += 1
                        _notify(gs, f"|{a}{b}⟩", 1.0)
                        snd.play("collapse")

                # ── CHSH 모드 키 ──
                elif gs.mode == MODE_CHSH:
                    if event.key == pygame.K_SPACE and not gs.chsh_running:
                        gs.chsh_running = True
                        state = BELL_STATES["Φ+"]
                        result = run_chsh_experiment(
                            state, n_shots=chsh_shots)
                        gs.chsh_result = result
                        gs.chsh_history.append(result["S"])
                        gs.chsh_experiments += 1
                        gs.chsh_running = False
                        s_val = result["S"]
                        verdict = t("ent_chsh_violated") if abs(s_val) > CHSH_CLASSICAL_BOUND else t("ent_chsh_not_violated")
                        _notify(gs, t("ent_notify_chsh_done",
                                      s=f"{s_val:+.3f}",
                                      verdict=verdict), 2.0)
                        snd.play("click")

                # ── Teleportation 모드 키 ──
                elif gs.mode == MODE_TELEPORT:
                    if event.key == pygame.K_SPACE:
                        if gs.teleport.step < 6:
                            msg = teleport_step(gs.teleport)
                            gs.teleport_log.append(msg)
                            if gs.teleport.step >= 6:
                                gs.teleport_completions += 1
                                _notify(gs, t("ent_notify_tp_done"), 2.0)
                            snd.play("click")
                        else:
                            # 새로운 텔레포테이션 시작
                            gs.reset_teleport()
                            gs.history_page = 0
                            snd.play("click")
                    elif event.key == pygame.K_n:
                        # 새 랜덤 상태
                        gs.reset_teleport()
                        snd.play("click")

            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (event.w, event.h), pygame.RESIZABLE)
                _rebuild_layout(event.w, event.h)

        # ── 레코딩 ──
        if not gs.paused:
            recorder.record_frame({
                "mode": gs.mode,
                "t": round(gs.t, 2),
                "bell_total": gs.bell_total,
                "chsh_experiments": gs.chsh_experiments,
                "teleport_step": gs.teleport.step,
            })

        # ── 렌더링 ──
        L = _layout
        screen.fill(BG)

        # 상단: 모드 탭
        tab_start = L.margin
        for i, key in enumerate(_MODE_TAB_KEYS):
            tab_x = tab_start + i * L.tab_w
            is_sel = (i == gs.mode)
            tab_clr = ACCENT if is_sel else OVERLAY_CLR
            pygame.draw.rect(screen, tab_clr,
                             (tab_x, L.tab_y, L.tab_w - 4, L.tab_h),
                             0 if is_sel else 1, border_radius=4)
            ts_text = font.render(t(key), True, BG if is_sel else TEXT_CLR)
            screen.blit(ts_text, (tab_x + (L.tab_w - 4) // 2
                                  - ts_text.get_width() // 2,
                                  L.tab_label_y))

        # 모드별 렌더링
        if gs.mode == MODE_BELL:
            _draw_bell_mode(screen, gs, font, title_font, info_font)
        elif gs.mode == MODE_CHSH:
            _draw_chsh_mode(screen, gs, font, title_font, info_font)
        elif gs.mode == MODE_TELEPORT:
            _draw_teleport_mode(screen, gs, font, title_font, info_font)

        # 하단 힌트
        if gs.mode == MODE_BELL:
            hints = [
                t("ent_hint_bell_1"),
                t("ent_hint_bell_2"),
            ]
        elif gs.mode == MODE_CHSH:
            hints = [
                t("ent_hint_chsh_1"),
                t("ent_hint_chsh_2"),
            ]
        else:
            hints = [
                t("ent_hint_tp_1"),
                t("ent_hint_tp_2"),
            ]
        for i, hint in enumerate(hints):
            hs = info_font.render(hint, True, TEXT_CLR)
            screen.blit(hs, (L.W // 2 - hs.get_width() // 2,
                             L.hint_y + i * 16))

        # 알림 메시지 (페이드 아웃)
        if gs.notify_timer > 0:
            gs.notify_timer -= dt
            render_notify(screen, gs.notify_msg, gs.notify_timer, info_font,
                          ACCENT, L.W // 2, L.notify_y)

        # 난이도 뱃지
        diff_colors = {"easy": GREEN, "normal": YELLOW, "hard": RED}
        badge_clr = diff_colors.get(gs.difficulty, TEXT_CLR)
        badge = info_font.render(f"[{gs.difficulty.upper()}]", True, badge_clr)
        screen.blit(badge, (L.W - badge.get_width() - 8, L.badge_y))

        # 오버레이
        toast.update(dt)
        toast.draw(screen, info_font)
        toast.draw_history(screen, info_font)
        glossary.draw(screen, info_font)
        help_overlay.draw(screen, info_font)
        tutorial.draw(screen, info_font)
        perf.draw_overlay(screen, info_font, x=L.perf_x, y=4)

        pygame.display.flip()

    perf.log_summary()

    session_data = {
        "play_time": round(time.time() - gs.start_time, 1),
        "difficulty": gs.difficulty,
        "total_measurements": gs.total_measurements,
        "chsh_experiments": gs.chsh_experiments,
        "teleport_completions": gs.teleport_completions,
    }

    finalize_session(
        "entanglement",
        session_data,
        recorder=recorder,
        recorder_meta={"play_time": session_data["play_time"]},
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def open_entanglement():
    """외부에서 호출하는 진입점."""
    run_simulation()
