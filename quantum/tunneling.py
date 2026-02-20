"""양자 중첩 및 터널링 시뮬레이션 (Pygame).

- 블로흐 구: 큐비트가 |0⟩ / |1⟩ 사이를 확률적으로 점멸 (중첩 시각화)
- 터널링: 입자가 장벽과 충돌할 때 10 % 확률로 장벽 반대편으로 이동
"""

import math
import random

import pygame

from achievement_toast import AchievementToast
from achievements import check_achievements
from config_loader import cfg
from quantum.ui_common import (
    HISTORY_PAGE_SIZE,
    NotifyToast,
    draw_bar_pattern as _draw_bar_pattern,
    draw_circle_pattern as _draw_circle_pattern,
    draw_page_dots,
    draw_panel as _draw_ui_panel,
    draw_progress_bar as _draw_progress_bar,
    paginate,
    render_notify,
)
from game_base import choose_difficulty_or_quit, finalize_session
from glossary import GlossaryOverlay
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from perf_monitor import PerfMonitor
from preset_hud import PresetHUD

# ── 물리 엔진 (순수 로직) ────────────────────────────
from quantum.tunneling_physics import (
    BARRIER_WIDTH_DEFAULT,
    BARRIER_WIDTH_MAX,
    BARRIER_WIDTH_MIN,
    BARRIER_X,
    PARTICLE_RADIUS,
    SIM_H,
    SIM_LEFT,
    SIM_TOP,
    SIM_W,
    TRAIL_MAX_LENGTH,
    TUNNEL_PROB_BASE,
    TUNNEL_SPEED_BOOST,
    SHAPE_DOUBLE,
    SHAPE_NAMES,
    SHAPE_RECT,
    SHAPE_TRAPEZOID,
    SHAPE_TRIANGLE,
    _NUM_SHAPES,
    DensityAccumulator,
    QuantumParticle,
    _calc_tunnel_prob,
    barrier_potential,
    compute_potential_profile,
    compute_wavefunction,
)
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from sound_manager import get_sound_manager
from theme import get_font_scale, is_high_contrast, is_reduced_motion, load_pg_colors, on_theme_change
from tutorial import TutorialOverlay
from ui.slider import PANEL_W, SliderPanel

_log = get_module_logger("tunneling")

# ── 모드 ─────────────────────────────────────────────
MODE_STEP = 0
MODE_AUTO = 1
MODE_COMPARE = 2
MODE_QC = 3  # 양자 vs 고전 비교 분석
_NUM_MODES = 4
_MODE_TAB_KEYS = ["tn_tab_step", "tn_tab_auto", "tn_tab_compare", "tn_tab_qc"]

# 장벽 형태 상태
_barrier_shape = SHAPE_RECT
COMPARE_TARGET = 50  # 비교 모드: 각 장벽당 총 시행 횟수
QC_TARGET = 100  # QC 분석: 각 모델당 시행 횟수

# ── 화면 설정 ────────────────────────────────────────
WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
FPS = cfg("display", "fps", 60)

# ── 색상 (테마에서 동적 로드) ─────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (203, 166, 247)
BARRIER_CLR = (249, 226, 175)
PARTICLE_CLR = (137, 180, 250)
TUNNEL_FLASH = (166, 227, 161)  # 터널링 성공
REFLECT_CLR = (243, 139, 168)  # 반사
BLOCH_RING = (88, 91, 112)


_COLOR_MAP = {
    "BG": "BG",
    "TEXT_CLR": "TEXT",
    "ACCENT": "ACCENT_PURPLE",
    "BARRIER_CLR": "ACCENT_YELLOW",
    "PARTICLE_CLR": "ACCENT_BLUE",
    "TUNNEL_FLASH": "GREEN",
    "REFLECT_CLR": "RED",
    "BLOCH_RING": "SUBTEXT",
    "SURFACE_CLR": "SURFACE",
    "OVERLAY_CLR": "OVERLAY",
    "WHITE": "WHITE",
}


def _load_theme_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    load_pg_colors(_COLOR_MAP, globals())


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
        fs = min(sx, sy)  # 폰트/간격 공통 스케일

        # 탭 바
        self.margin = int(20 * sx)
        self.tab_y = int(8 * sy)
        self.tab_h = int(28 * sy)
        tab_total = SIM_W
        self.tab_w = tab_total // _NUM_MODES
        self.tab_label_offset_y = int(6 * sy)

        # 블로흐 구
        self.bloch_cx = int(730 * sx)
        self.bloch_cy = int(280 * sy)
        self.bloch_r = int(110 * fs)

        # 타이틀
        self.title_y = int(12 * sy)
        self.title_offset = int(28 * sy)

        # 이벤트 로그
        self.log_x = int(580 * sx)
        self.log_y = int(430 * sy)

        # 알림
        self.notify_y = h - int(70 * sy)

        # 하단 힌트
        self.hint_y = h - int(52 * sy)

        # 성능 모니터
        self.perf_x = w - int(250 * sx)

        # ── 폰트 비례 줄간격 ──
        self.line_h = max(12, int(17 * fs))       # 통계 줄간격
        self.line_h_sm = max(10, int(14 * fs))    # 이벤트 로그 항목
        self.line_h_md = max(12, int(16 * fs))    # 힌트 줄간격
        self.line_h_lg = max(14, int(22 * fs))    # 비교 결과 줄간격
        self.text_gap = max(10, int(16 * fs))     # 텍스트 블록 간격

        # ── 블로흐 구 오프셋 ──
        self.bloch_title_gap = int(40 * fs)       # 타이틀-구 간격
        self.bloch_axis_ext = max(4, int(8 * fs))
        self.bloch_label_x = max(4, int(8 * fs))  # |0⟩/|1⟩ 라벨 X 오프셋
        self.bloch_z0_y = int(18 * fs)
        self.bloch_z1_y = max(2, int(4 * fs))
        self.bloch_state_y = int(26 * fs)         # 상태 텍스트 Y 오프셋
        self.bloch_stats_gap = int(60 * fs)       # 구-통계 간격

        # 파동함수 그래프 (시뮬레이션 영역 하단에 오버레이)
        self.wf_y = SIM_TOP + SIM_H - int(130 * sy)   # 그래프 시작 Y
        self.wf_h = int(120 * sy)                       # 그래프 높이
        self.wf_label_x = SIM_LEFT + int(5 * sx)        # 라벨 X
        self.wf_label_y = SIM_TOP + SIM_H - int(135 * sy)  # 라벨 Y

        # 포텐셜 에너지 다이어그램 (시뮬레이션 영역 상단에 오버레이)
        self.pe_h = int(100 * sy)                        # 그래프 높이
        self.pe_y = SIM_TOP + int(22 * sy)               # 그래프 시작 Y
        self.pe_label_x = SIM_LEFT + int(5 * sx)         # 라벨 X
        self.pe_label_y = SIM_TOP + int(8 * sy)          # 라벨 Y

        # Compare 모드 레이아웃
        self.cmp_title_y = int(50 * sy)
        self.cmp_track_x = int(60 * sx)
        self.cmp_track_w = int(460 * sx)
        self.cmp_thin_y = int(120 * sy)
        self.cmp_thick_y = int(240 * sy)
        self.cmp_panel_w = int(520 * sx)
        self.cmp_panel_h = int(80 * sy)
        self.cmp_bar_h = int(20 * sy)
        self.cmp_bar_offset = int(35 * sy)        # 패널 내 진행바 오프셋
        self.cmp_text_offset = int(60 * sy)       # 패널 내 텍스트 오프셋
        self.cmp_stats_x = int(40 * sx)
        self.cmp_stats_y = int(370 * sy)
        self.cmp_stats_w = int(520 * sx)
        self.cmp_stats_h = int(100 * sy)
        self.cmp_result_pad = int(15 * sy)        # 결과 패널 내부 패딩
        self.cmp_result_indent = int(20 * sx)     # 결과 텍스트 들여쓰기
        self.cmp_result_y = int(490 * sy)

        # QC (양자 vs 고전) 모드 레이아웃
        self.qc_title_y = int(50 * sy)
        self.qc_graph_x = int(40 * sx)
        self.qc_graph_y = int(90 * sy)
        self.qc_graph_w = int(500 * sx)
        self.qc_graph_h = int(200 * sy)
        self.qc_race_y = int(320 * sy)
        self.qc_race_panel_w = int(520 * sx)
        self.qc_race_panel_h = int(80 * sy)
        self.qc_race_bar_offset = int(35 * sy)
        self.qc_race_text_offset = int(60 * sy)
        self.qc_stats_x = int(40 * sx)
        self.qc_stats_y = int(490 * sy)
        self.qc_stats_w = int(520 * sx)
        self.qc_stats_h = int(60 * sy)


_layout = Layout()

# Reduced-motion 블로흐 구 보간용 상태
_bloch_smooth_theta = math.pi / 2


def _rebuild_layout(w: int, h: int):
    """리사이즈 시 레이아웃 재계산."""
    global _layout
    _layout = Layout(w, h)


# ── 그리기 헬퍼 ──────────────────────────────────────


def _draw_sim_area(screen, font, barrier_width: int = BARRIER_WIDTH_DEFAULT):
    """시뮬레이션 영역 배경."""
    hc = is_high_contrast()
    shape = _barrier_shape
    pygame.draw.rect(screen, SURFACE_CLR, (SIM_LEFT, SIM_TOP, SIM_W, SIM_H))
    border_w = 2 if hc else 1
    pygame.draw.rect(screen, OVERLAY_CLR, (SIM_LEFT, SIM_TOP, SIM_W, SIM_H), border_w)

    # 장벽 — 형태별 렌더링
    bx = BARRIER_X - barrier_width // 2
    half_w = barrier_width / 2.0

    if shape == SHAPE_RECT:
        pygame.draw.rect(screen, BARRIER_CLR, (bx, SIM_TOP, barrier_width, SIM_H))
        _draw_bar_pattern(screen, (bx, SIM_TOP, barrier_width, SIM_H), BARRIER_CLR, "mid")
        if hc:
            pygame.draw.rect(screen, TEXT_CLR, (bx, SIM_TOP, barrier_width, SIM_H), 1)

    elif shape == SHAPE_TRIANGLE:
        # 삼각형: 중앙 꼭짓점, 양 끝 바닥
        mid_x = BARRIER_X
        pts = [
            (bx, SIM_TOP + SIM_H),
            (mid_x, SIM_TOP),
            (bx + barrier_width, SIM_TOP + SIM_H),
        ]
        pygame.draw.polygon(screen, BARRIER_CLR, pts)
        outline_w = 2 if hc else 1
        pygame.draw.polygon(screen, TEXT_CLR if hc else BARRIER_CLR, pts, outline_w)

    elif shape == SHAPE_TRAPEZOID:
        # 사다리꼴: 양쪽 경사 + 중앙 평탄
        ramp_w = int(barrier_width * 0.3)
        pts = [
            (bx, SIM_TOP + SIM_H),
            (bx + ramp_w, SIM_TOP),
            (bx + barrier_width - ramp_w, SIM_TOP),
            (bx + barrier_width, SIM_TOP + SIM_H),
        ]
        pygame.draw.polygon(screen, BARRIER_CLR, pts)
        outline_w = 2 if hc else 1
        pygame.draw.polygon(screen, TEXT_CLR if hc else BARRIER_CLR, pts, outline_w)

    elif shape == SHAPE_DOUBLE:
        # 이중장벽: 두 벽 + 사이 빈 공간
        wall_w = max(int(barrier_width * 0.3), 2)
        gap_start = bx + wall_w
        gap_end = bx + barrier_width - wall_w
        # 왼쪽 벽
        pygame.draw.rect(screen, BARRIER_CLR, (bx, SIM_TOP, wall_w, SIM_H))
        _draw_bar_pattern(screen, (bx, SIM_TOP, wall_w, SIM_H), BARRIER_CLR, "mid")
        # 오른쪽 벽
        pygame.draw.rect(screen, BARRIER_CLR, (gap_end, SIM_TOP, wall_w, SIM_H))
        _draw_bar_pattern(screen, (gap_end, SIM_TOP, wall_w, SIM_H), BARRIER_CLR, "mid")
        # 우물 영역 표시 (연한 배경)
        well_w = max(gap_end - gap_start, 1)
        well_surf = pygame.Surface((well_w, SIM_H), pygame.SRCALPHA)
        well_surf.fill((*TUNNEL_FLASH[:3], 25))
        screen.blit(well_surf, (gap_start, SIM_TOP))
        if hc:
            pygame.draw.rect(screen, TEXT_CLR, (bx, SIM_TOP, wall_w, SIM_H), 1)
            pygame.draw.rect(screen, TEXT_CLR, (gap_end, SIM_TOP, wall_w, SIM_H), 1)

    # 장벽 라벨
    shape_key = f"tn_shape_{SHAPE_NAMES[shape]}"
    label_text = t("tn_barrier") + f" ({t(shape_key)})"
    label = font.render(label_text, True, BG)
    label_rot = pygame.transform.rotate(label, 90)
    screen.blit(label_rot, (bx - 2, SIM_TOP + SIM_H // 2 - label_rot.get_height() // 2))

    # 영역 라벨
    left_label = font.render(t("tn_classical"), True, OVERLAY_CLR)
    screen.blit(left_label, (SIM_LEFT + 10, SIM_TOP + 5))
    right_label = font.render(t("tn_tunneled"), True, OVERLAY_CLR)
    screen.blit(right_label, (BARRIER_X + 20, SIM_TOP + 5))


def _draw_particle(screen, p: QuantumParticle, font):
    """입자 렌더링."""
    cx, cy = int(p.x), int(p.y)
    time_ms = pygame.time.get_ticks()
    hc = is_high_contrast()

    # 터널링/반사 플래시
    if p.flash_timer > 0 and not is_reduced_motion():
        flash_r = int(PARTICLE_RADIUS + 20 * p.flash_timer)
        flash_clr = TUNNEL_FLASH if p.tunneled else REFLECT_CLR
        glow = pygame.Surface((flash_r * 2, flash_r * 2), pygame.SRCALPHA)
        alpha = int(120 * p.flash_timer)
        pygame.draw.circle(glow, (*flash_clr, alpha), (flash_r, flash_r), flash_r)
        screen.blit(glow, (cx - flash_r, cy - flash_r))
        # 플래시 원에 색맹 보조 패턴
        tier = "high" if p.tunneled else "mid"
        _draw_circle_pattern(screen, cx, cy, flash_r, flash_clr, tier)

    # 입자 본체 — 터널링 성공 시 흰색, 평상시 파랑
    color = WHITE if (p.tunneled is True and p.flash_timer > 0) else PARTICLE_CLR
    pygame.draw.circle(screen, color, (cx, cy), PARTICLE_RADIUS)
    outline_w = 2 if hc else 1
    pygame.draw.circle(screen, TEXT_CLR, (cx, cy), PARTICLE_RADIUS, outline_w)

    # 색맹 보조: 입자 상태별 패턴 (터널링=수평선, 반사=대각선)
    if p.tunneled is True and p.flash_timer > 0:
        _draw_circle_pattern(screen, cx, cy, PARTICLE_RADIUS, color, "high")
    elif p.tunneled is False and p.flash_timer > 0:
        _draw_circle_pattern(screen, cx, cy, PARTICLE_RADIUS, REFLECT_CLR, "mid")

    # 중첩 |0⟩/|1⟩ 텍스트
    state_text = f"|{p.qubit_state(time_ms)}⟩"
    surf = font.render(state_text, True, WHITE)
    screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))


# ── 입자 궤적 잔상 ────────────────────────────────────

_trail_visible = False


def _draw_particle_trail(screen, p: QuantumParticle):
    """입자의 이전 경로를 반투명 잔상으로 렌더링.

    각 잔상 점은 시간이 지남에 따라 투명도가 증가하며,
    터널링 상태에 따라 색상이 변화하여 확률 분포를 직관적으로 표현한다.
    """
    trail = p.trail
    n = len(trail)
    if n < 2:
        return

    reduced = is_reduced_motion()
    trail_surf = pygame.Surface((SIM_W, SIM_H), pygame.SRCALPHA)
    ox, oy = SIM_LEFT, SIM_TOP

    for i in range(n - 1):
        x0, y0, st0 = trail[i]
        x1, y1, st1 = trail[i + 1]

        # 오래된 점일수록 투명 (0→거의 투명, n-1→가장 진함)
        frac = (i + 1) / n
        alpha = int(20 + 100 * frac)

        # 터널링 상태에 따른 색상 결정
        if st1 is True:
            color = TUNNEL_FLASH
        elif st1 is False:
            color = REFLECT_CLR
        else:
            color = PARTICLE_CLR

        sx0 = int(x0) - ox
        sy0 = int(y0) - oy
        sx1 = int(x1) - ox
        sy1 = int(y1) - oy

        # 선분 잔상
        line_w = max(1, int(3 * frac))
        pygame.draw.line(trail_surf, (*color[:3], alpha), (sx0, sy0), (sx1, sy1), line_w)

        # 잔상 점 (reduced-motion에서는 점 생략)
        if not reduced and i % 2 == 0:
            dot_r = max(1, int(PARTICLE_RADIUS * 0.4 * frac))
            pygame.draw.circle(trail_surf, (*color[:3], alpha // 2), (sx1, sy1), dot_r)

    screen.blit(trail_surf, (ox, oy))


def _draw_bloch_sphere(screen, p: QuantumParticle, font, title_font):
    """블로흐 구 시각화."""
    L = _layout
    BCX, BCY, BR = L.bloch_cx, L.bloch_cy, L.bloch_r
    time_ms = pygame.time.get_ticks()
    hc = is_high_contrast()

    # 타이틀
    label = title_font.render(t("tn_bloch"), True, ACCENT)
    screen.blit(label, (BCX - label.get_width() // 2, BCY - BR - L.bloch_title_gap))

    # 구 외곽 (원) — 고대비: 두꺼운 선
    ring_w = 2 if hc else 1
    pygame.draw.circle(screen, BLOCH_RING, (BCX, BCY), BR, ring_w)

    # 적도 타원
    pygame.draw.ellipse(
        screen,
        BLOCH_RING,
        (BCX - BR, BCY - BR // 4, BR * 2, BR // 2),
        ring_w,
    )

    # 축 — 고대비: 두꺼운 선
    axis_w = 2 if hc else 1
    ae = L.bloch_axis_ext
    pygame.draw.line(screen, OVERLAY_CLR, (BCX, BCY - BR - ae), (BCX, BCY + BR + ae), axis_w)

    # |0⟩ 극점 마커 — 색맹 보조: 수평선 패턴 (터널링=성공과 동일)
    pole0_y = BCY - BR
    pole0_r = 5
    pygame.draw.circle(screen, TUNNEL_FLASH, (BCX, pole0_y), pole0_r)
    _draw_circle_pattern(screen, BCX, pole0_y, pole0_r, TUNNEL_FLASH, "high")

    # |1⟩ 극점 마커 — 색맹 보조: 대각선 패턴 (반사와 동일)
    pole1_y = BCY + BR
    pole1_r = 5
    pygame.draw.circle(screen, REFLECT_CLR, (BCX, pole1_y), pole1_r)
    _draw_circle_pattern(screen, BCX, pole1_y, pole1_r, REFLECT_CLR, "mid")

    # |0⟩, |1⟩ 라벨
    z0 = font.render("|0⟩", True, TUNNEL_FLASH)
    z1 = font.render("|1⟩", True, REFLECT_CLR)
    screen.blit(z0, (BCX + L.bloch_label_x, BCY - BR - L.bloch_z0_y))
    screen.blit(z1, (BCX + L.bloch_label_x, BCY + BR + L.bloch_z1_y))

    # 상태 벡터 (θ 기반) — reduced motion 시 부드러운 보간
    global _bloch_smooth_theta
    if is_reduced_motion():
        target = math.pi / 2  # 등확률 중첩 위치 (적도)
        lerp = 0.05
    else:
        target = p.superposition_alpha(time_ms)
        lerp = 0.3
    _bloch_smooth_theta += (target - _bloch_smooth_theta) * lerp
    theta = _bloch_smooth_theta
    tip_x = BCX + int(BR * 0.4 * math.sin(theta))
    tip_y = BCY - int(BR * math.cos(theta))

    vec_w = 3 if hc else 2
    pygame.draw.line(screen, ACCENT, (BCX, BCY), (tip_x, tip_y), vec_w)
    tip_r = 7 if hc else 6
    pygame.draw.circle(screen, ACCENT, (tip_x, tip_y), tip_r)
    # 색맹 보조: 상태 벡터 끝점에 θ 기반 패턴
    tip_tier = "high" if theta < math.pi / 2 else "mid"
    _draw_circle_pattern(screen, tip_x, tip_y, tip_r, ACCENT, tip_tier)

    # 현재 상태 텍스트
    state_label = f"|{'0' if theta < math.pi / 2 else '1'}⟩  θ={math.degrees(theta):.0f}°"
    sl = font.render(state_label, True, TEXT_CLR)
    screen.blit(sl, (BCX - sl.get_width() // 2, BCY + BR + L.bloch_state_y))


def _draw_stats(screen, p: QuantumParticle, font, tunnel_prob: float = TUNNEL_PROB_BASE):
    """통계 패널."""
    L = _layout
    stats_x = L.bloch_cx - L.bloch_r
    stats_y = L.bloch_cy + L.bloch_r + L.bloch_stats_gap

    lines = [
        (t("tn_attempts", count=p.total_attempts), TEXT_CLR),
        (t("tn_tunnel_stat", count=p.tunnel_count, pct=p.tunnel_count / max(p.total_attempts, 1) * 100), TUNNEL_FLASH),
        (
            t("tn_reflect_stat", count=p.reflect_count, pct=p.reflect_count / max(p.total_attempts, 1) * 100),
            REFLECT_CLR,
        ),
        (t("tn_current_prob", prob=tunnel_prob * 100), TEXT_CLR),
    ]
    for i, (line, color) in enumerate(lines):
        surf = font.render(line, True, color)
        screen.blit(surf, (stats_x, stats_y + i * L.line_h))


# ── 파동함수 시각화 ────────────────────────────────────

# 파동함수 오버레이 전역 상태
_wf_visible = False
_WF_N_POINTS = 200
_WF_ANIM_SPEED = 1.5  # 파동 진행 속도 (rad/s)


def _draw_wavefunction(screen, font, barrier_width: int, time_ms: float):
    """파동함수 |ψ(x)|² 오버레이를 시뮬레이션 영역 하단에 그린다.

    영역별 색상:
    - 입사측(Region I): PARTICLE_CLR (파란색) — 정재파 패턴
    - 장벽 내부(Region II): BARRIER_CLR (노란색) — 지수감쇠
    - 투과측(Region III): TUNNEL_FLASH (녹색) — 투과파
    """
    L = _layout
    hc = is_high_contrast()

    # 시간 위상 (감쇠 모드에서는 고정)
    if is_reduced_motion():
        phase = 0.0
    else:
        phase = time_ms / 1000.0 * _WF_ANIM_SPEED

    xs, amps, regions = compute_wavefunction(barrier_width, _WF_N_POINTS, phase, shape=_barrier_shape)

    # 그래프 영역 배경 (반투명)
    graph_rect = (SIM_LEFT, L.wf_y, SIM_W, L.wf_h)
    bg_surf = pygame.Surface((SIM_W, L.wf_h), pygame.SRCALPHA)
    bg_surf.fill((*BG[:3], 180))
    screen.blit(bg_surf, (SIM_LEFT, L.wf_y))

    # 그래프 프레임
    frame_w = 2 if hc else 1
    pygame.draw.rect(screen, OVERLAY_CLR, graph_rect, frame_w)

    # 제로 라인 (y축 기준선)
    base_y = L.wf_y + L.wf_h - 4
    pygame.draw.line(
        screen, BLOCH_RING,
        (SIM_LEFT, base_y), (SIM_LEFT + SIM_W, base_y), 1,
    )

    # 장벽 영역 표시 (반투명 채움)
    half_w = barrier_width / 2.0
    bx_left = int(BARRIER_X - half_w)
    bx_right = int(BARRIER_X + half_w)
    b_surf = pygame.Surface((max(bx_right - bx_left, 1), L.wf_h), pygame.SRCALPHA)
    b_surf.fill((*BARRIER_CLR[:3], 40))
    screen.blit(b_surf, (bx_left, L.wf_y))

    # 영역별 색상 매핑
    region_colors = {
        0: PARTICLE_CLR,   # 입사측 (파란색)
        1: BARRIER_CLR,    # 장벽 내부 (노란색)
        2: TUNNEL_FLASH,   # 투과측 (녹색)
    }

    # 곡선 그리기 — 영역별로 분리하여 색상 적용
    usable_h = L.wf_h - 8  # 상하 패딩

    # 포인트 좌표 계산
    points_by_region: dict[int, list[tuple[int, int]]] = {0: [], 1: [], 2: []}
    all_points: list[tuple[int, int, int]] = []  # (x, y, region)

    for i in range(len(xs)):
        px = int(xs[i])
        py = int(base_y - amps[i] * usable_h)
        py = max(L.wf_y + 2, min(base_y, py))
        region = regions[i]
        points_by_region[region].append((px, py))
        all_points.append((px, py, region))

    # 채움 영역 그리기 (반투명 그라데이션 효과)
    for region_id, color in region_colors.items():
        pts = points_by_region[region_id]
        if len(pts) < 2:
            continue
        # 폴리곤: 곡선 + 베이스 라인
        fill_pts = list(pts) + [(pts[-1][0], base_y), (pts[0][0], base_y)]
        fill_surf = pygame.Surface((SIM_W, L.wf_h), pygame.SRCALPHA)
        shifted = [(p[0] - SIM_LEFT, p[1] - L.wf_y) for p in fill_pts]
        if len(shifted) >= 3:
            pygame.draw.polygon(fill_surf, (*color[:3], 45), shifted)
            screen.blit(fill_surf, (SIM_LEFT, L.wf_y))

    # 곡선 선 그리기 (영역 전환점에서 연결)
    line_w = 2 if hc else 2
    for i in range(1, len(all_points)):
        x0, y0, r0 = all_points[i - 1]
        x1, y1, r1 = all_points[i]
        # 전환 경계에서는 두 영역 모두와 잘 어울리도록 뒤쪽 영역 색상 사용
        color = region_colors[r1]
        pygame.draw.line(screen, color, (x0, y0), (x1, y1), line_w)

    # 라벨: "|ψ(x)|²"
    label = font.render(t("tn_wf_title"), True, ACCENT)
    screen.blit(label, (L.wf_label_x, L.wf_label_y))

    # 범례 (영역 설명)
    legend_x = SIM_LEFT + SIM_W - 200
    legend_y = L.wf_y + 5
    legend_items = [
        (PARTICLE_CLR, t("tn_wf_incident")),
        (BARRIER_CLR, t("tn_wf_decay")),
        (TUNNEL_FLASH, t("tn_wf_transmitted")),
    ]
    for i, (clr, txt) in enumerate(legend_items):
        lx = legend_x
        ly = legend_y + i * (L.line_h_sm + 1)
        pygame.draw.rect(screen, clr, (lx, ly + 2, 10, 8))
        ls = font.render(txt, True, TEXT_CLR)
        screen.blit(ls, (lx + 14, ly))


# ── 포텐셜 에너지 다이어그램 ──────────────────────────

_pe_visible = False
_PE_N_POINTS = 200


def _draw_potential_energy(screen, font, barrier_width: int):
    """포텐셜 에너지 V(x) 다이어그램을 시뮬레이션 영역 상단에 오버레이.

    - V(x): 장벽 영역 = V₀ (노란색), 그 외 = 0
    - E: 입자 에너지 수평 점선 (파란색)
    - E < V₀ 이므로 고전역학적으로 장벽 통과 불가능을 시각적으로 표현
    """
    L = _layout
    hc = is_high_contrast()

    xs, potentials, energy = compute_potential_profile(
        barrier_width, _PE_N_POINTS, shape=_barrier_shape
    )

    # 그래프 영역 배경 (반투명)
    graph_rect = (SIM_LEFT, L.pe_y, SIM_W, L.pe_h)
    bg_surf = pygame.Surface((SIM_W, L.pe_h), pygame.SRCALPHA)
    bg_surf.fill((*BG[:3], 180))
    screen.blit(bg_surf, (SIM_LEFT, L.pe_y))

    # 프레임
    frame_w = 2 if hc else 1
    pygame.draw.rect(screen, OVERLAY_CLR, graph_rect, frame_w)

    base_y = L.pe_y + L.pe_h - 4  # 바닥선 (V=0)
    top_y = L.pe_y + 4              # 천장 (V=V₀)
    usable_h = base_y - top_y

    # V=0 기준선
    pygame.draw.line(screen, BLOCH_RING, (SIM_LEFT, base_y),
                     (SIM_LEFT + SIM_W, base_y), 1)

    # V(x) 장벽 좌표 계산
    half_w = barrier_width / 2.0
    bx_left = int(BARRIER_X - half_w)
    bx_right = int(BARRIER_X + half_w)
    bw_px = max(bx_right - bx_left, 1)

    # V(x) 윤곽선 — 형태에 따른 곡선
    v_line_w = 2 if hc else 2
    v_points = []
    for i in range(len(xs)):
        px = int(xs[i])
        py = int(base_y - potentials[i] * usable_h)
        v_points.append((px, py))

    # 채움 영역 (반투명)
    if len(v_points) >= 2:
        fill_pts = list(v_points) + [(v_points[-1][0], base_y), (v_points[0][0], base_y)]
        fill_surf = pygame.Surface((SIM_W, L.pe_h), pygame.SRCALPHA)
        shifted = [(p[0] - SIM_LEFT, p[1] - L.pe_y) for p in fill_pts]
        if len(shifted) >= 3:
            pygame.draw.polygon(fill_surf, (*BARRIER_CLR[:3], 60), shifted)
            screen.blit(fill_surf, (SIM_LEFT, L.pe_y))

    # V(x) 윤곽선
    if len(v_points) > 1:
        pygame.draw.lines(screen, BARRIER_CLR, False, v_points, v_line_w)

    # E (입자 에너지) 수평 점선 — 파란색
    e_y = int(base_y - energy * usable_h)
    dash_len = 8
    gap_len = 5
    e_line_w = 2 if hc else 1
    x_cursor = SIM_LEFT
    while x_cursor < SIM_LEFT + SIM_W:
        x_end = min(x_cursor + dash_len, SIM_LEFT + SIM_W)
        pygame.draw.line(screen, PARTICLE_CLR, (x_cursor, e_y),
                         (x_end, e_y), e_line_w)
        x_cursor = x_end + gap_len

    # V₀ 라벨 (장벽 높이)
    v_label = font.render("V₀", True, BARRIER_CLR)
    screen.blit(v_label, (bx_left - v_label.get_width() - 4, top_y - 2))

    # E 라벨 (입자 에너지)
    e_label = font.render("E", True, PARTICLE_CLR)
    screen.blit(e_label, (SIM_LEFT + SIM_W + 4, e_y - e_label.get_height() // 2))

    # E < V₀ 영역 표시 — 장벽 내에서 E와 V₀ 사이 해칭
    if energy < 1.0:
        forbidden_h = int((1.0 - energy) * usable_h)
        forbidden_y = top_y
        hatch_surf = pygame.Surface((bw_px, forbidden_h), pygame.SRCALPHA)
        # 사선 해칭 패턴
        for y_off in range(0, forbidden_h + bw_px, 8):
            pygame.draw.line(hatch_surf, (*REFLECT_CLR[:3], 50),
                             (0, y_off), (min(y_off, bw_px), max(y_off - bw_px, 0)), 1)
        screen.blit(hatch_surf, (bx_left, forbidden_y))

    # 타이틀 라벨
    title = font.render(t("tn_pe_title"), True, ACCENT)
    screen.blit(title, (L.pe_label_x, L.pe_label_y))

    # 범례
    legend_x = SIM_LEFT + SIM_W - 180
    legend_y = L.pe_y + 5
    legend_items = [
        (BARRIER_CLR, t("tn_pe_barrier_v")),
        (PARTICLE_CLR, t("tn_pe_particle_e")),
        (REFLECT_CLR, t("tn_pe_forbidden")),
    ]
    for i, (clr, txt) in enumerate(legend_items):
        lx = legend_x
        ly = legend_y + i * (L.line_h_sm + 1)
        pygame.draw.rect(screen, clr, (lx, ly + 2, 10, 8))
        ls = font.render(txt, True, TEXT_CLR)
        screen.blit(ls, (lx + 14, ly))


# ── 확률밀도 히트맵 ────────────────────────────────────

_density_visible = False

# 히트맵 색상 그라데이션 (저밀도 → 고밀도)
_HEATMAP_COLORS = [
    (30, 30, 80),       # 극저 (진한 남색)
    (50, 50, 180),      # 저 (파란색)
    (80, 200, 200),     # 중저 (시안)
    (100, 230, 100),    # 중 (초록)
    (240, 230, 60),     # 중고 (노란)
    (240, 130, 40),     # 고 (주황)
    (230, 50, 50),      # 극고 (빨간)
]


def _heatmap_color(val: float) -> tuple[int, int, int]:
    """0.0~1.0 밀도값을 히트맵 색상으로 변환."""
    n = len(_HEATMAP_COLORS) - 1
    idx = val * n
    lo = int(idx)
    lo = min(lo, n - 1)
    hi = lo + 1
    frac = idx - lo
    c0, c1 = _HEATMAP_COLORS[lo], _HEATMAP_COLORS[hi]
    return (
        int(c0[0] + (c1[0] - c0[0]) * frac),
        int(c0[1] + (c1[1] - c0[1]) * frac),
        int(c0[2] + (c1[2] - c0[2]) * frac),
    )


def _draw_density_heatmap(screen, font, accumulator: DensityAccumulator):
    """확률밀도 히트맵을 시뮬레이션 영역 위에 오버레이.

    누적된 입자 위치를 히스토그램 바 + 컬러맵으로 표시.
    상단에 바 차트, 하단에 시뮬레이션 영역과 겹치는 반투명 히트 스트립.
    """
    L = _layout
    hc = is_high_contrast()
    density = accumulator.get_density()
    centers = accumulator.get_bin_centers()
    n_bins = accumulator.n_bins

    if accumulator.total_samples == 0:
        # 샘플이 없으면 안내 메시지만 표시
        msg = font.render(t("tn_dm_no_data"), True, OVERLAY_CLR)
        screen.blit(msg, (SIM_LEFT + SIM_W // 2 - msg.get_width() // 2,
                          SIM_TOP + SIM_H - 20))
        return

    bin_w = SIM_W / n_bins

    # 1) 시뮬레이션 영역 위에 반투명 히트 스트립
    strip_h = SIM_H
    strip_surf = pygame.Surface((SIM_W, strip_h), pygame.SRCALPHA)
    for i in range(n_bins):
        d = density[i]
        if d < 0.01:
            continue
        clr = _heatmap_color(d)
        alpha = int(40 + 80 * d)  # 40~120 알파
        bx = int(i * bin_w)
        bw = max(int(bin_w) + 1, 1)
        pygame.draw.rect(strip_surf, (*clr, alpha), (bx, 0, bw, strip_h))
    screen.blit(strip_surf, (SIM_LEFT, SIM_TOP))

    # 2) 하단 바 차트 (시뮬레이션 영역 아래쪽에 작은 히스토그램)
    bar_h_max = 50
    bar_y_base = SIM_TOP + SIM_H - 3

    # 바 차트 배경
    bar_bg = pygame.Surface((SIM_W, bar_h_max + 4), pygame.SRCALPHA)
    bar_bg.fill((*BG[:3], 160))
    screen.blit(bar_bg, (SIM_LEFT, bar_y_base - bar_h_max - 1))

    for i in range(n_bins):
        d = density[i]
        if d < 0.005:
            continue
        bx = int(SIM_LEFT + i * bin_w)
        bw = max(int(bin_w) - 1, 1)
        bh = int(d * bar_h_max)
        clr = _heatmap_color(d)
        pygame.draw.rect(screen, clr, (bx, bar_y_base - bh, bw, bh))

    # 3) 장벽 위치 마커
    half_bw = 6  # 장벽 중심 표시선
    pygame.draw.line(screen, BARRIER_CLR,
                     (BARRIER_X, bar_y_base - bar_h_max),
                     (BARRIER_X, bar_y_base), 1)

    # 4) 라벨
    title = font.render(t("tn_dm_title"), True, ACCENT)
    screen.blit(title, (SIM_LEFT + 5,
                        bar_y_base - bar_h_max - title.get_height() - 2))

    # 샘플 수 표시
    samples_txt = font.render(
        t("tn_dm_samples", n=accumulator.total_samples), True, TEXT_CLR
    )
    screen.blit(samples_txt, (SIM_LEFT + SIM_W - samples_txt.get_width() - 5,
                               bar_y_base - bar_h_max - samples_txt.get_height() - 2))

    # 5) 컬러바 범례
    cb_x = SIM_LEFT + SIM_W - 100
    cb_y = bar_y_base - 12
    cb_w = 80
    cb_h = 8
    for px in range(cb_w):
        val = px / max(cb_w - 1, 1)
        clr = _heatmap_color(val)
        pygame.draw.line(screen, clr, (cb_x + px, cb_y), (cb_x + px, cb_y + cb_h))
    frame_w = 2 if hc else 1
    pygame.draw.rect(screen, OVERLAY_CLR, (cb_x, cb_y, cb_w, cb_h), frame_w)
    lo_txt = font.render("0", True, TEXT_CLR)
    hi_txt = font.render("max", True, TEXT_CLR)
    screen.blit(lo_txt, (cb_x - lo_txt.get_width() - 2, cb_y - 1))
    screen.blit(hi_txt, (cb_x + cb_w + 3, cb_y - 1))


# ── 모드 탭 / 비교 모드 렌더링 ────────────────────────


def _draw_mode_tabs(screen, font, mode: int):
    """상단 모드 탭 바 렌더링."""
    L = _layout
    tab_start = SIM_LEFT
    for i, key in enumerate(_MODE_TAB_KEYS):
        tab_x = tab_start + i * L.tab_w
        is_sel = (i == mode)
        tab_clr = ACCENT if is_sel else OVERLAY_CLR
        pygame.draw.rect(screen, tab_clr,
                         (tab_x, L.tab_y, L.tab_w - 4, L.tab_h),
                         0 if is_sel else 1, border_radius=4)
        ts = font.render(t(key), True, BG if is_sel else TEXT_CLR)
        screen.blit(ts, (tab_x + (L.tab_w - 4) // 2 - ts.get_width() // 2,
                         L.tab_y + L.tab_label_offset_y))


def _draw_compare_mode(screen, font, title_font, info_font, cmp):
    """얇은 장벽 vs 두꺼운 장벽 — 비교 모드 렌더링.

    Args:
        cmp: dict with thin_w, thick_w, thin_tunnels, thin_attempts,
             thick_tunnels, thick_attempts, running, done.
    """
    L = _layout

    # 타이틀
    title = title_font.render(t("tn_compare_title"), True, ACCENT)
    screen.blit(title, (L.W // 2 - title.get_width() // 2, L.cmp_title_y))

    thin_w = cmp["thin_w"]
    thick_w = cmp["thick_w"]
    thin_prob = _calc_tunnel_prob(thin_w)
    thick_prob = _calc_tunnel_prob(thick_w)

    # ── 얇은 장벽 트랙 ──
    _draw_ui_panel(screen, L.margin, L.cmp_thin_y, L.cmp_panel_w, L.cmp_panel_h,
                   SURFACE_CLR, OVERLAY_CLR,
                   t("tn_compare_thin", w=thin_w), font, TUNNEL_FLASH)
    prog_thin = cmp["thin_attempts"] / max(COMPARE_TARGET, 1)
    _draw_progress_bar(screen, L.cmp_track_x, L.cmp_thin_y + L.cmp_bar_offset,
                       L.cmp_track_w, L.cmp_bar_h,
                       prog_thin, TUNNEL_FLASH, SURFACE_CLR, OVERLAY_CLR)
    # 통계 텍스트
    pct_thin = cmp["thin_tunnels"] / max(cmp["thin_attempts"], 1) * 100
    ts_thin = info_font.render(
        t("tn_compare_tunnels", count=cmp["thin_tunnels"],
          total=cmp["thin_attempts"], pct=pct_thin), True, TEXT_CLR)
    screen.blit(ts_thin, (L.cmp_track_x, L.cmp_thin_y + L.cmp_text_offset))
    prob_thin = info_font.render(
        t("tn_compare_prob", prob=thin_prob * 100), True, OVERLAY_CLR)
    screen.blit(prob_thin, (L.cmp_track_x + L.cmp_track_w - prob_thin.get_width(),
                            L.cmp_thin_y + L.cmp_text_offset))

    # ── 두꺼운 장벽 트랙 ──
    _draw_ui_panel(screen, L.margin, L.cmp_thick_y, L.cmp_panel_w, L.cmp_panel_h,
                   SURFACE_CLR, OVERLAY_CLR,
                   t("tn_compare_thick", w=thick_w), font, REFLECT_CLR)
    prog_thick = cmp["thick_attempts"] / max(COMPARE_TARGET, 1)
    _draw_progress_bar(screen, L.cmp_track_x, L.cmp_thick_y + L.cmp_bar_offset,
                       L.cmp_track_w, L.cmp_bar_h,
                       prog_thick, REFLECT_CLR, SURFACE_CLR, OVERLAY_CLR)
    pct_thick = cmp["thick_tunnels"] / max(cmp["thick_attempts"], 1) * 100
    ts_thick = info_font.render(
        t("tn_compare_tunnels", count=cmp["thick_tunnels"],
          total=cmp["thick_attempts"], pct=pct_thick), True, TEXT_CLR)
    screen.blit(ts_thick, (L.cmp_track_x, L.cmp_thick_y + L.cmp_text_offset))
    prob_thick = info_font.render(
        t("tn_compare_prob", prob=thick_prob * 100), True, OVERLAY_CLR)
    screen.blit(prob_thick, (L.cmp_track_x + L.cmp_track_w - prob_thick.get_width(),
                             L.cmp_thick_y + L.cmp_text_offset))

    # ── 결과 통계 (완료 시) ──
    if cmp["done"]:
        _draw_ui_panel(screen, L.cmp_stats_x, L.cmp_stats_y,
                       L.cmp_stats_w, L.cmp_stats_h,
                       SURFACE_CLR, OVERLAY_CLR)
        lines = [
            (t("tn_compare_thin", w=thin_w) + f":  {cmp['thin_tunnels']}/{COMPARE_TARGET}"
             f"  ({pct_thin:.1f}%)", TUNNEL_FLASH),
            (t("tn_compare_thick", w=thick_w) + f":  {cmp['thick_tunnels']}/{COMPARE_TARGET}"
             f"  ({pct_thick:.1f}%)", REFLECT_CLR),
        ]
        if cmp["thick_tunnels"] > 0:
            ratio = cmp["thin_tunnels"] / max(cmp["thick_tunnels"], 1)
            lines.append((t("tn_compare_result", ratio=ratio), ACCENT))
        elif cmp["thin_tunnels"] == cmp["thick_tunnels"]:
            lines.append((t("tn_compare_equal"), ACCENT))
        for i, (line, clr) in enumerate(lines):
            ls = info_font.render(line, True, clr)
            screen.blit(ls, (L.cmp_stats_x + L.cmp_result_indent,
                             L.cmp_stats_y + L.cmp_result_pad + i * L.line_h_lg))


# ── 양자 vs 고전 비교 분석 렌더링 ─────────────────────


def _draw_qc_analysis(screen, font, title_font, info_font, qc):
    """양자 vs 고전 터널링 확률 비교 분석 모드 렌더링.

    Args:
        qc: dict with barrier_w, q_tunnels, q_attempts,
            c_tunnels, c_attempts, running, done.
    """
    L = _layout
    hc = is_high_contrast()

    # 타이틀
    title = title_font.render(t("tn_qc_title"), True, ACCENT)
    screen.blit(title, (L.W // 2 - title.get_width() // 2, L.qc_title_y))

    bw = qc["barrier_w"]
    q_prob = _calc_tunnel_prob(bw)

    # ── 확률 그래프 ──────────────────────────────────
    gx, gy, gw, gh = L.qc_graph_x, L.qc_graph_y, L.qc_graph_w, L.qc_graph_h

    # 배경 패널
    _draw_ui_panel(screen, gx, gy, gw, gh, SURFACE_CLR, OVERLAY_CLR,
                   t("tn_qc_graph_title"), font, ACCENT)

    # 그래프 내부 영역 (여백)
    pad_l, pad_r, pad_t, pad_b = 50, 10, 25, 20
    ix, iy = gx + pad_l, gy + pad_t
    iw, ih = gw - pad_l - pad_r, gh - pad_t - pad_b

    # Y축 라벨 (확률 %)
    for pct in (0, 25, 50, 75, 100):
        yy = iy + ih - int(ih * pct / 100)
        lbl = info_font.render(f"{pct}%", True, OVERLAY_CLR)
        screen.blit(lbl, (ix - lbl.get_width() - 4, yy - lbl.get_height() // 2))
        # 그리드 선
        pygame.draw.line(screen, OVERLAY_CLR, (ix, yy), (ix + iw, yy), 1)

    # X축 라벨 (장벽 두께)
    for w_mark in range(BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX + 1, 40):
        xx = ix + int(iw * (w_mark - BARRIER_WIDTH_MIN) / max(1, BARRIER_WIDTH_MAX - BARRIER_WIDTH_MIN))
        lbl = info_font.render(str(w_mark), True, OVERLAY_CLR)
        screen.blit(lbl, (xx - lbl.get_width() // 2, iy + ih + 2))

    # 양자 확률 곡선 (녹색)
    q_points = []
    num_samples = min(iw, 100)
    for i in range(num_samples + 1):
        w_val = BARRIER_WIDTH_MIN + (BARRIER_WIDTH_MAX - BARRIER_WIDTH_MIN) * i / num_samples
        prob = _calc_tunnel_prob(int(w_val))
        px = ix + int(iw * i / num_samples)
        py = iy + ih - int(ih * min(prob, 1.0))
        q_points.append((px, py))
    if len(q_points) > 1:
        line_w = 3 if hc else 2
        pygame.draw.lines(screen, TUNNEL_FLASH, False, q_points, line_w)

    # 고전 확률 곡선 (빨강, 항상 0%)
    c_y = iy + ih
    line_w = 3 if hc else 2
    pygame.draw.line(screen, REFLECT_CLR, (ix, c_y), (ix + iw, c_y), line_w)

    # 현재 장벽 두께 마커 (수직 점선)
    marker_x = ix + int(iw * (bw - BARRIER_WIDTH_MIN) / max(1, BARRIER_WIDTH_MAX - BARRIER_WIDTH_MIN))
    for dy in range(0, ih, 6):
        pygame.draw.line(screen, ACCENT, (marker_x, iy + dy), (marker_x, iy + min(dy + 3, ih)), 1)
    # 마커 라벨
    mk_lbl = info_font.render(f"w={bw}", True, ACCENT)
    screen.blit(mk_lbl, (marker_x - mk_lbl.get_width() // 2, iy - mk_lbl.get_height() - 2))

    # 범례
    legend_y = gy + gh + 4
    q_lbl = info_font.render(t("tn_qc_quantum_label"), True, TUNNEL_FLASH)
    c_lbl = info_font.render(t("tn_qc_classical_label"), True, REFLECT_CLR)
    screen.blit(q_lbl, (gx + 10, legend_y))
    screen.blit(c_lbl, (gx + 10 + q_lbl.get_width() + 20, legend_y))

    # ── 레이스 시뮬레이션 ─────────────────────────────
    race_y = L.qc_race_y
    prob_display = info_font.render(
        t("tn_qc_barrier_prob", w=bw, prob=q_prob * 100), True, TEXT_CLR)
    screen.blit(prob_display, (L.margin, race_y - L.line_h))

    # 양자 트랙
    _draw_ui_panel(screen, L.margin, race_y, L.qc_race_panel_w, L.qc_race_panel_h,
                   SURFACE_CLR, OVERLAY_CLR,
                   t("tn_qc_quantum"), font, TUNNEL_FLASH)
    prog_q = qc["q_attempts"] / max(QC_TARGET, 1)
    _draw_progress_bar(screen, L.qc_graph_x, race_y + L.qc_race_bar_offset,
                       L.qc_graph_w, L.cmp_bar_h,
                       prog_q, TUNNEL_FLASH, SURFACE_CLR, OVERLAY_CLR)
    pct_q = qc["q_tunnels"] / max(qc["q_attempts"], 1) * 100
    ts_q = info_font.render(
        t("tn_compare_tunnels", count=qc["q_tunnels"],
          total=qc["q_attempts"], pct=pct_q), True, TEXT_CLR)
    screen.blit(ts_q, (L.qc_graph_x, race_y + L.qc_race_text_offset))

    # 고전 트랙
    c_race_y = race_y + L.qc_race_panel_h + 10
    _draw_ui_panel(screen, L.margin, c_race_y, L.qc_race_panel_w, L.qc_race_panel_h,
                   SURFACE_CLR, OVERLAY_CLR,
                   t("tn_qc_classical"), font, REFLECT_CLR)
    prog_c = qc["c_attempts"] / max(QC_TARGET, 1)
    _draw_progress_bar(screen, L.qc_graph_x, c_race_y + L.qc_race_bar_offset,
                       L.qc_graph_w, L.cmp_bar_h,
                       prog_c, REFLECT_CLR, SURFACE_CLR, OVERLAY_CLR)
    pct_c = qc["c_tunnels"] / max(qc["c_attempts"], 1) * 100
    ts_c = info_font.render(
        t("tn_compare_tunnels", count=qc["c_tunnels"],
          total=qc["c_attempts"], pct=pct_c), True, TEXT_CLR)
    screen.blit(ts_c, (L.qc_graph_x, c_race_y + L.qc_race_text_offset))

    # ── 결과 통계 (완료 시) ──
    if qc["done"]:
        _draw_ui_panel(screen, L.qc_stats_x, L.qc_stats_y,
                       L.qc_stats_w, L.qc_stats_h,
                       SURFACE_CLR, OVERLAY_CLR)
        lines = [
            (t("tn_qc_result_quantum", count=qc["q_tunnels"],
               total=QC_TARGET, pct=pct_q), TUNNEL_FLASH),
            (t("tn_qc_result_classical", count=qc["c_tunnels"],
               total=QC_TARGET, pct=pct_c), REFLECT_CLR),
        ]
        for i, (line, clr) in enumerate(lines):
            ls = info_font.render(line, True, clr)
            screen.blit(ls, (L.qc_stats_x + L.cmp_result_indent,
                             L.qc_stats_y + L.cmp_result_pad + i * L.line_h_lg))


# ── 해상도 비례 폰트 ─────────────────────────────────

_BASE_W, _BASE_H = 900, 600


def _make_fonts(w: int, h: int):
    """해상도와 테마 폰트 스케일에 비례하는 폰트 생성.

    Returns:
        (font, info_font, title_font, big_font) 튜플.
    """
    sx = w / _BASE_W
    sy = h / _BASE_H
    scale = max(min(sx, sy), 0.6) * get_font_scale()

    def sz(base):
        return max(8, int(base * scale))

    return (
        pygame.font.SysFont("Consolas", sz(13)),
        pygame.font.SysFont("Consolas", sz(11)),
        pygame.font.SysFont("Consolas", sz(16), bold=True),
        pygame.font.SysFont("Consolas", sz(18), bold=True),
    )


# ── 메인 시뮬레이션 ──────────────────────────────────


def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH + PANEL_W, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption(t("game_title_tunneling"))
    clock = pygame.time.Clock()
    font, info_font, title_font, big_font = _make_fonts(WIDTH, HEIGHT)

    particle = QuantumParticle()
    density_acc = DensityAccumulator()
    paused = False
    frame_step = False  # 일시정지 중 1프레임 전진

    # ── 슬라이더 패널 ─────────────────────────────────
    panel = SliderPanel(WIDTH + 5, 40, PANEL_W - 10, "Parameters")
    sl_speed = panel.add(0.5, 5.0, 1.0, 0.5, "Speed Mult", ".1f")
    sl_barrier = panel.add(BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX, BARRIER_WIDTH_DEFAULT, 2, "Barrier W", ".0f")
    sl_boost = panel.add(1.0, 5.0, TUNNEL_SPEED_BOOST, 0.5, "Tunnel Boost", ".1f")

    # ── 프리셋 HUD ──
    slider_map = {
        ("tunneling", "tunnel_prob_base"): sl_speed,
        ("tunneling", "barrier_width_default"): sl_barrier,
        ("tunneling", "tunnel_speed_boost"): sl_boost,
    }
    preset_hud = PresetHUD("tunneling", slider_map)
    help_overlay = HelpOverlay("tunneling")
    glossary = GlossaryOverlay()

    # ── 사운드 ──
    snd = get_sound_manager()
    snd.init()

    # ── 리플레이 ──
    recorder = ReplayRecorder("tunneling")

    # ── 업적 / 튜토리얼 / 성능 모니터 ──
    toast = AchievementToast()
    tutorial = TutorialOverlay("tunneling")
    perf = PerfMonitor(target_fps=FPS)

    barrier_width = BARRIER_WIDTH_DEFAULT
    tunnel_prob = _calc_tunnel_prob(barrier_width)

    # 알림 / 페이지네이션
    notify_toast = NotifyToast()
    history_page = 0
    event_log: list[tuple[str, bool]] = []  # (message, is_tunnel)

    def _notify(msg: str, category: str = "info", duration: float = 2.0):
        notify_toast.show(msg, category, duration)

    # ── 모드 상태 ─────────────────────────────────────
    mode = MODE_AUTO
    step_waiting = True  # Step 모드: 입자 발사 대기 중
    cmp = {
        "thin_w": BARRIER_WIDTH_MIN,
        "thick_w": 80,
        "thin_tunnels": 0, "thin_attempts": 0,
        "thick_tunnels": 0, "thick_attempts": 0,
        "running": False, "done": False,
    }
    qc = {
        "barrier_w": BARRIER_WIDTH_DEFAULT,
        "q_tunnels": 0, "q_attempts": 0,
        "c_tunnels": 0, "c_attempts": 0,
        "running": False, "done": False,
    }

    def _on_mode_change():
        nonlocal step_waiting, paused, frame_step, history_page
        history_page = 0
        frame_step = False
        if mode == MODE_STEP:
            step_waiting = True
            paused = False
        elif mode == MODE_AUTO:
            paused = False
        elif mode == MODE_COMPARE:
            cmp["thin_tunnels"] = 0
            cmp["thin_attempts"] = 0
            cmp["thick_tunnels"] = 0
            cmp["thick_attempts"] = 0
            cmp["running"] = False
            cmp["done"] = False
        elif mode == MODE_QC:
            qc["q_tunnels"] = 0
            qc["q_attempts"] = 0
            qc["c_tunnels"] = 0
            qc["c_attempts"] = 0
            qc["running"] = False
            qc["done"] = False

    # ── 시작 시 난이도 선택 ──
    if not choose_difficulty_or_quit(screen, font, preset_hud, _load_theme_colors):
        return

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        perf.tick(dt)

        # ── 이벤트 ───────────────────────────────────
        for event in pygame.event.get():
            if tutorial.handle_event(event):
                continue
            if mode not in (MODE_COMPARE, MODE_QC):
                panel.handle_event(event)
            preset_hud.handle_event(event)
            help_overlay.handle_event(event)
            glossary.handle_event(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                snd.handle_key(event.key)
                if event.key == pygame.K_ESCAPE:
                    if confirm_quit(screen, font):
                        running = False
                elif event.key == pygame.K_TAB:
                    mode = (mode + 1) % _NUM_MODES
                    _on_mode_change()
                    _notify(t(_MODE_TAB_KEYS[mode]), "info", 1.0)
                    snd.play("click")
                elif event.key == pygame.K_SPACE:
                    if mode == MODE_STEP:
                        step_waiting = False
                        paused = False
                    elif mode == MODE_AUTO:
                        paused = not paused
                        frame_step = False
                    elif mode == MODE_COMPARE:
                        if cmp["done"]:
                            cmp["thin_tunnels"] = 0
                            cmp["thin_attempts"] = 0
                            cmp["thick_tunnels"] = 0
                            cmp["thick_attempts"] = 0
                            cmp["done"] = False
                        cmp["running"] = not cmp["running"]
                    elif mode == MODE_QC:
                        if qc["done"]:
                            qc["q_tunnels"] = 0
                            qc["q_attempts"] = 0
                            qc["c_tunnels"] = 0
                            qc["c_attempts"] = 0
                            qc["done"] = False
                        qc["running"] = not qc["running"]
                elif event.key == pygame.K_r:
                    if mode in (MODE_STEP, MODE_AUTO):
                        particle = QuantumParticle()
                        density_acc.reset()
                        panel.reset_all()
                        event_log.clear()
                        history_page = 0
                        if mode == MODE_STEP:
                            step_waiting = True
                    elif mode == MODE_COMPARE:
                        cmp["thin_tunnels"] = 0
                        cmp["thin_attempts"] = 0
                        cmp["thick_tunnels"] = 0
                        cmp["thick_attempts"] = 0
                        cmp["running"] = False
                        cmp["done"] = False
                    elif mode == MODE_QC:
                        qc["q_tunnels"] = 0
                        qc["q_attempts"] = 0
                        qc["c_tunnels"] = 0
                        qc["c_attempts"] = 0
                        qc["running"] = False
                        qc["done"] = False
                    _notify(t("notify_reset"), "info", 1.0)
                elif event.key == pygame.K_PAGEUP:
                    history_page = max(0, history_page - 1)
                elif event.key == pygame.K_PAGEDOWN:
                    history_page += 1
                elif event.key == pygame.K_UP:
                    if mode == MODE_COMPARE:
                        cmp["thick_w"] = min(BARRIER_WIDTH_MAX, cmp["thick_w"] + 10)
                    elif mode == MODE_QC:
                        qc["barrier_w"] = min(BARRIER_WIDTH_MAX, qc["barrier_w"] + 10)
                    else:
                        sl_speed.value = sl_speed.value + 0.5
                elif event.key == pygame.K_DOWN:
                    if mode == MODE_COMPARE:
                        cmp["thick_w"] = max(cmp["thin_w"] + 4, cmp["thick_w"] - 10)
                    elif mode == MODE_QC:
                        qc["barrier_w"] = max(BARRIER_WIDTH_MIN, qc["barrier_w"] - 10)
                    else:
                        sl_speed.value = sl_speed.value - 0.5
                elif event.key == pygame.K_RIGHT:
                    if mode not in (MODE_COMPARE, MODE_QC):
                        sl_barrier.value = sl_barrier.value + 10
                elif event.key == pygame.K_LEFT:
                    if mode not in (MODE_COMPARE, MODE_QC):
                        sl_barrier.value = sl_barrier.value - 10
                elif event.key == pygame.K_PERIOD:
                    # 일시정지 중 1프레임 전진
                    if mode == MODE_AUTO and paused:
                        frame_step = True
                    elif mode == MODE_STEP and not step_waiting:
                        if not paused:
                            paused = True
                            _notify(t("tn_paused"), "info", 0.8)
                        frame_step = True
                elif event.key == pygame.K_p:
                    if mode in (MODE_STEP, MODE_AUTO):
                        paused = not paused
                        if paused:
                            _notify(t("tn_paused"), "info", 0.8)
                elif event.key == pygame.K_w:
                    global _wf_visible
                    _wf_visible = not _wf_visible
                    key = "tn_wf_on" if _wf_visible else "tn_wf_off"
                    _notify(t(key), "info", 1.0)
                    snd.play("click")
                elif event.key == pygame.K_e:
                    global _pe_visible
                    _pe_visible = not _pe_visible
                    key = "tn_pe_on" if _pe_visible else "tn_pe_off"
                    _notify(t(key), "info", 1.0)
                    snd.play("click")
                elif event.key == pygame.K_d:
                    global _density_visible
                    _density_visible = not _density_visible
                    key = "tn_dm_on" if _density_visible else "tn_dm_off"
                    _notify(t(key), "info", 1.0)
                    snd.play("click")
                elif event.key == pygame.K_b:
                    global _barrier_shape
                    _barrier_shape = (_barrier_shape + 1) % _NUM_SHAPES
                    shape_key = f"tn_shape_{SHAPE_NAMES[_barrier_shape]}"
                    _notify(t("tn_shape_changed", shape=t(shape_key)), "info", 1.5)
                    snd.play("click")
                elif event.key == pygame.K_t:
                    global _trail_visible
                    _trail_visible = not _trail_visible
                    key = "tn_trail_on" if _trail_visible else "tn_trail_off"
                    _notify(t(key), "info", 1.0)
                    snd.play("click")
                elif event.key == pygame.K_l:
                    toggle_locale()
                elif event.key == pygame.K_g:
                    toast.toggle_history()
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (event.w, event.h), pygame.RESIZABLE)
                _rebuild_layout(event.w - PANEL_W, event.h)
                font, info_font, title_font, big_font = _make_fonts(
                    event.w - PANEL_W, event.h)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if mode in (MODE_STEP, MODE_AUTO):
                    mx, my = event.pos
                    if mx < _layout.W:  # 슬라이더 패널 외부 클릭만
                        particle.reset()
                        if mode == MODE_STEP:
                            step_waiting = False

        # ── 슬라이더 값 읽기 (Step / Auto) ────────────
        if mode in (MODE_STEP, MODE_AUTO):
            speed_mult = sl_speed.value
            barrier_width = int(sl_barrier.value)
            tunnel_prob = _calc_tunnel_prob(barrier_width)

        # ── 물리 업데이트 ────────────────────────────
        should_update = False
        if mode == MODE_STEP:
            should_update = (not step_waiting) and (not paused or frame_step)
        elif mode == MODE_AUTO:
            should_update = not paused or frame_step

        # 프레임 단위 전진: 고정 dt 사용 (1/FPS)
        if frame_step:
            dt_phys = 1.0 / FPS
        else:
            dt_phys = dt

        if should_update:
            prev_attempts = particle.total_attempts
            prev_tunneled = particle.tunneled
            orig_vx = particle.vx
            particle.vx = orig_vx * speed_mult if orig_vx > 0 else orig_vx
            particle.update(dt_phys, barrier_width, tunnel_prob, sl_boost.value)
            particle.vx = orig_vx  # 속도 배율은 화면용, 내부 상태 보존

            # 밀도 히트맵 누적 (활성 시에만)
            if _density_visible and particle.alive:
                density_acc.record(particle.x)

            # Step 모드: 입자가 리스폰되면 다음 발사 대기
            if mode == MODE_STEP:
                if prev_tunneled is not None and particle.tunneled is None:
                    step_waiting = True

            # ── 이벤트 로그 ──
            if particle.total_attempts > prev_attempts:
                n = particle.total_attempts
                if particle.tunneled is True:
                    event_log.append((t("tn_notify_tunneled", n=n), True))
                    _notify(t("tn_notify_tunneled", n=n), "success", 1.0)
                elif particle.tunneled is False:
                    event_log.append((t("tn_notify_reflected", n=n), False))
                    _notify(t("tn_notify_reflected", n=n), "warning", 1.0)

                # 실시간 업적 체크
                try:
                    new_ach = check_achievements(
                        "tunneling",
                        {
                            "tunnel_count": particle.tunnel_count,
                            "total_attempts": particle.total_attempts,
                            "tunnel_rate": particle.tunnel_count / max(particle.total_attempts, 1),
                        },
                    )
                    toast.show_many(new_ach)
                except (KeyError, TypeError) as e:
                    _log.warning("실시간 업적 확인 실패: %s", e)

            # ── 사운드 ──
            if particle.tunneled is True and particle.flash_timer > 0.5:
                snd.play("tunnel_success")
            elif particle.tunneled is False and particle.flash_timer > 0.3:
                snd.play("tunnel_reflect")

            preset_hud.update(dt)

            recorder.record_frame(
                {
                    "x": round(particle.x, 1),
                    "tunneled": particle.tunneled,
                    "attempts": particle.total_attempts,
                    "tunnels": particle.tunnel_count,
                }
            )

        frame_step = False  # 1프레임 전진 후 리셋

        # ── Compare 모드 시뮬레이션 ──────────────────
        if mode == MODE_COMPARE and cmp["running"] and not cmp["done"]:
            thin_prob = _calc_tunnel_prob(cmp["thin_w"])
            thick_prob = _calc_tunnel_prob(cmp["thick_w"])
            batch = max(1, int(30 * dt))  # ~30 trials/sec at 60fps → ~0.5/frame
            for _ in range(batch):
                if cmp["thin_attempts"] < COMPARE_TARGET:
                    cmp["thin_attempts"] += 1
                    if random.random() < thin_prob:
                        cmp["thin_tunnels"] += 1
                if cmp["thick_attempts"] < COMPARE_TARGET:
                    cmp["thick_attempts"] += 1
                    if random.random() < thick_prob:
                        cmp["thick_tunnels"] += 1
                if (cmp["thin_attempts"] >= COMPARE_TARGET
                        and cmp["thick_attempts"] >= COMPARE_TARGET):
                    cmp["running"] = False
                    cmp["done"] = True
                    _notify(t("tn_notify_compare_done"), "success", 2.0)
                    snd.play("achievement")
                    break

        # ── QC 모드 시뮬레이션 ─────────────────────────
        if mode == MODE_QC and qc["running"] and not qc["done"]:
            q_prob = _calc_tunnel_prob(qc["barrier_w"])
            batch = max(1, int(30 * dt))
            for _ in range(batch):
                if qc["q_attempts"] < QC_TARGET:
                    qc["q_attempts"] += 1
                    if random.random() < q_prob:
                        qc["q_tunnels"] += 1
                if qc["c_attempts"] < QC_TARGET:
                    qc["c_attempts"] += 1
                    # 고전: 에너지 < 장벽이면 터널링 불가 → 항상 0%
                if (qc["q_attempts"] >= QC_TARGET
                        and qc["c_attempts"] >= QC_TARGET):
                    qc["running"] = False
                    qc["done"] = True
                    _notify(t("tn_qc_done"), "success", 2.0)
                    snd.play("achievement")
                    break

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)
        L = _layout

        # 탭 바 (항상 표시)
        _draw_mode_tabs(screen, font, mode)

        if mode in (MODE_STEP, MODE_AUTO):
            # 타이틀
            t_surf = big_font.render(t("game_title_tunneling"), True, ACCENT)
            screen.blit(t_surf, (L.W // 2 - t_surf.get_width() // 2, L.title_y + L.title_offset))

            # 시뮬레이션 영역
            _draw_sim_area(screen, font, barrier_width)

            # 확률밀도 히트맵 (시뮬레이션 영역 위에 반투명)
            if _density_visible:
                _draw_density_heatmap(screen, font, density_acc)

            # 포텐셜 에너지 다이어그램 (시뮬레이션 영역 상단)
            if _pe_visible:
                _draw_potential_energy(screen, font, barrier_width)

            # 파동함수 오버레이 (입자 아래, 시뮬레이션 영역 내)
            if _wf_visible:
                _draw_wavefunction(screen, font, barrier_width,
                                   pygame.time.get_ticks())

            # 입자 궤적 잔상
            if _trail_visible:
                _draw_particle_trail(screen, particle)

            # 입자
            _draw_particle(screen, particle, font)

            # 블로흐 구
            _draw_bloch_sphere(screen, particle, font, title_font)

            # 통계
            _draw_stats(screen, particle, font, tunnel_prob)

            # ── 이벤트 로그 (페이지네이션) ──
            if event_log:
                page_items, history_page, total_pages = paginate(event_log, history_page)
                title_text = t("tn_event_log")
                lt = font.render(title_text, True, ACCENT)
                screen.blit(lt, (L.log_x, L.log_y))

                # 도트 인디케이터
                draw_page_dots(screen,
                               L.log_x + lt.get_width() + 10,
                               L.log_y + lt.get_height() // 2,
                               total_pages, history_page,
                               ACCENT, OVERLAY_CLR, BLOCH_RING)

                for li, (entry, is_tunnel) in enumerate(page_items):
                    clr = TUNNEL_FLASH if is_tunnel else TEXT_CLR
                    es = font.render(f"  {entry}", True, clr)
                    screen.blit(es, (L.log_x, L.log_y + L.text_gap + li * L.line_h_sm))

            # 슬라이더 패널
            panel.draw(screen, font)

            # Step 모드 상태 표시
            if mode == MODE_STEP and step_waiting:
                wait_surf = info_font.render(t("tn_step_waiting"), True, ACCENT)
                screen.blit(wait_surf,
                            (SIM_LEFT + SIM_W // 2 - wait_surf.get_width() // 2,
                             SIM_TOP + SIM_H + max(3, int(5 * L.H / 600))))

            # 일시정지 배너
            if paused:
                banner = info_font.render(t("tn_paused_banner"), True, ACCENT)
                bx = SIM_LEFT + SIM_W // 2 - banner.get_width() // 2
                by = SIM_TOP + SIM_H + max(3, int(5 * L.H / 600))
                screen.blit(banner, (bx, by))

            # 힌트
            if mode == MODE_STEP:
                hints = [t("tn_hint_step_1"), t("tn_hint_step_2")]
            else:
                hints = [t("tn_hint_auto_1"), t("tn_hint_auto_2")]
            for i, h in enumerate(hints):
                surf = info_font.render(h, True, TEXT_CLR)
                screen.blit(surf, (SIM_LEFT, L.hint_y + i * L.line_h_md))

        elif mode == MODE_COMPARE:
            _draw_compare_mode(screen, font, title_font, info_font, cmp)

            # 힌트
            hints = [t("tn_hint_compare_1"), t("tn_hint_compare_2")]
            for i, h in enumerate(hints):
                surf = info_font.render(h, True, TEXT_CLR)
                screen.blit(surf, (SIM_LEFT, L.hint_y + i * L.line_h_md))

        elif mode == MODE_QC:
            _draw_qc_analysis(screen, font, title_font, info_font, qc)

            # 힌트
            hints = [t("tn_hint_qc_1"), t("tn_hint_qc_2")]
            for i, h in enumerate(hints):
                surf = info_font.render(h, True, TEXT_CLR)
                screen.blit(surf, (SIM_LEFT, L.hint_y + i * L.line_h_md))

        # 카테고리 토스트 알림
        notify_toast.update(dt)
        notify_toast.draw(screen, info_font, L.W // 2, L.notify_y)

        preset_hud.draw(screen, font)

        toast.update(dt)
        toast.draw(screen, info_font)
        toast.draw_history(screen, info_font)

        glossary.draw(screen, info_font)
        help_overlay.draw(screen, info_font)
        tutorial.draw(screen, info_font)
        perf.draw_overlay(screen, info_font, x=L.perf_x, y=4)

        pygame.display.flip()

    perf.log_summary()
    rate = particle.tunnel_count / max(particle.total_attempts, 1)
    finalize_session(
        "tunneling",
        {
            "total_attempts": particle.total_attempts,
            "tunnel_count": particle.tunnel_count,
            "reflect_count": particle.reflect_count,
            "tunnel_rate": round(rate, 3),
            "barrier_width": barrier_width,
            "tunnel_prob": round(tunnel_prob, 3),
        },
        recorder=recorder,
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def open_tunneling():
    """외부에서 호출하는 진입점."""
    run_simulation()
