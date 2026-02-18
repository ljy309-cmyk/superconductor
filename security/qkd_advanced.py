"""고급 QKD 프로토콜 시뮬레이션 (Pygame).

4 모드:
  Mode 1 — E91: 얽힘 기반 양자 키 분배 + 벨 부등식 보안 검증
  Mode 2 — Key Sifting: BB84/E91 키 시프팅 & 프라이버시 증폭 시각화
  Mode 3 — Multi-Party: GHZ 기반 3자간 QKD 네트워크
  Mode 4 — Compare: BB84 vs E91 동일 Eve 조건 비교
"""

import math
import os

import pygame

from config_loader import cfg
from game_base import finalize_session
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from security.qkd_advanced_engine import (
    BB84State,
    CHSH_CLASSICAL_BOUND,
    CHSH_QUANTUM_BOUND,
    E91State,
    GHZ_MAX_PARTIES,
    GHZ_MIN_PARTIES,
    GHZState,
    _DEMO_PLAINTEXT,
    bb84_error_correct,
    bb84_estimate_qber,
    bb84_privacy_amplification,
    bb84_round,
    compute_bell_S,
    e91_round,
    error_correct,
    estimate_qber,
    ghz_key_sift,
    ghz_privacy_amplification,
    ghz_round,
    key_sift,
    privacy_amplification,
    reset_bb84,
    reset_e91,
    reset_ghz,
    resize_ghz,
    xor_decrypt,
    xor_encrypt,
    NOISE_MODELS,
    cycle_noise_model,
    get_noise_model,
)
from sound_manager import get_sound_manager
from theme import load_pg_colors, on_theme_change, toggle_theme
from tutorial import TutorialOverlay

_log = get_module_logger("qkd_advanced")

WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
FPS = cfg("display", "fps", 60)
E91_BATCH = cfg("qkd_advanced", "e91_batch_size", 50)
GHZ_BATCH = cfg("qkd_advanced", "ghz_batch_size", 50)
CHSH_SHOTS = cfg("entanglement", "chsh_shots", 200)

# ── 색상 ─────────────────────────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
SUBTEXT_CLR = (88, 91, 112)
ACCENT = (249, 226, 175)
GREEN = (166, 227, 161)
RED = (243, 139, 168)
BLUE = (137, 180, 250)
MAUVE = (203, 166, 247)
PEACH = (250, 179, 135)
YELLOW = (249, 226, 175)
OVERLAY = (69, 71, 90)
PANEL_BG = (24, 24, 37)
WHITE = (255, 255, 255)


_COLOR_MAP = {
    "BG": "BG", "TEXT_CLR": "TEXT", "SUBTEXT_CLR": "SUBTEXT",
    "ACCENT": "ACCENT_YELLOW", "GREEN": "GREEN", "RED": "RED",
    "BLUE": "ALICE", "MAUVE": "QUBIT", "PEACH": "ACCENT_PEACH",
    "YELLOW": "ACCENT_YELLOW", "OVERLAY": "OVERLAY",
    "PANEL_BG": "PANEL_BG", "WHITE": "WHITE",
}


def _load_theme_colors():
    load_pg_colors(_COLOR_MAP, globals())


# ── 모드 상수 ────────────────────────────────────────
MODE_E91 = 0
MODE_SIFT = 1
MODE_GHZ = 2
MODE_COMPARE = 3
_MODE_KEYS = ["qa_mode_e91", "qa_mode_sift", "qa_mode_ghz", "qa_mode_compare"]
NUM_MODES = len(_MODE_KEYS)


class _TextCache:
    """정적 텍스트 렌더링 캐시 (동일 텍스트/색상 재사용)."""

    def __init__(self, max_size: int = 256):
        self._cache: dict[tuple, "pygame.Surface"] = {}
        self._max = max_size

    def render(self, font, text: str, color: tuple) -> "pygame.Surface":
        key = (id(font), text, color)
        surf = self._cache.get(key)
        if surf is None:
            if len(self._cache) >= self._max:
                self._cache.pop(next(iter(self._cache)))
            surf = font.render(text, True, color)
            self._cache[key] = surf
        return surf

    def clear(self):
        self._cache.clear()


_tcache = _TextCache()

# ── 노드 위치 ────────────────────────────────────────
ALICE_POS = (140, 140)
BOB_POS = (760, 140)
EPR_POS = (450, 90)
EVE_POS = (450, 40)


def _draw_key_ticker(screen, bits: list[int], x, y, width, font, anim_t):
    """최근 키 비트 스크롤링 티커."""
    if not bits:
        return
    last = bits[-32:]
    # 비트를 문자열로 연결, 색상 번갈아
    tx = x
    for i, b in enumerate(last):
        clr = GREEN if b == 0 else BLUE
        ch = font.render(str(b), True, clr)
        if tx + 8 > x + width:
            break
        screen.blit(ch, (tx, y))
        tx += 8


# ── E91 모드 ─────────────────────────────────────────

def _draw_e91_mode(screen, e91: E91State, anim_t, font, big_font):
    """E91 프로토콜 시각화."""
    # EPR 소스
    pygame.draw.circle(screen, MAUVE, EPR_POS, 22)
    pygame.draw.circle(screen, TEXT_CLR, EPR_POS, 22, 2)
    lbl = _tcache.render(big_font, "EPR", MAUVE)
    screen.blit(lbl, (EPR_POS[0] - lbl.get_width() // 2, EPR_POS[1] - 8))
    sub = _tcache.render(font, "|Φ+⟩", SUBTEXT_CLR)
    screen.blit(sub, (EPR_POS[0] - sub.get_width() // 2, EPR_POS[1] + 26))

    # 얽힘 링크 (물결 — 중점을 사인파로 이동하여 곡선 효과)
    for pos, clr in [(ALICE_POS, BLUE), (BOB_POS, GREEN)]:
        wave = math.sin(anim_t * 3) * 4
        sx, sy_ = EPR_POS[0], EPR_POS[1] + 22
        ex, ey = pos[0], pos[1] - 32
        mid_x = (sx + ex) // 2
        mid_y = (sy_ + ey) // 2 + int(wave)
        pygame.draw.lines(screen, clr, False, [(sx, sy_), (mid_x, mid_y), (ex, ey)], 1)

    # Alice
    pygame.draw.circle(screen, BLUE, ALICE_POS, 28)
    pygame.draw.circle(screen, TEXT_CLR, ALICE_POS, 28, 2)
    lbl = big_font.render(t("qa_alice"), True, BLUE)
    screen.blit(lbl, (ALICE_POS[0] - lbl.get_width() // 2, ALICE_POS[1] + 32))
    bases_a = font.render("0°, π/8, π/4", True, SUBTEXT_CLR)
    screen.blit(bases_a, (ALICE_POS[0] - bases_a.get_width() // 2, ALICE_POS[1] + 48))

    # Bob
    pygame.draw.circle(screen, GREEN, BOB_POS, 28)
    pygame.draw.circle(screen, TEXT_CLR, BOB_POS, 28, 2)
    lbl = big_font.render(t("qa_bob"), True, GREEN)
    screen.blit(lbl, (BOB_POS[0] - lbl.get_width() // 2, BOB_POS[1] + 32))
    bases_b = font.render("π/8, π/4, 3π/8", True, SUBTEXT_CLR)
    screen.blit(bases_b, (BOB_POS[0] - bases_b.get_width() // 2, BOB_POS[1] + 48))

    # 기저 각도 아크 시각화 (최근 라운드 기반)
    if e91.rounds:
        last = e91.rounds[-1]
        arc_r = 36
        for pos, angle, clr in [
            (ALICE_POS, last.alice_angle, BLUE),
            (BOB_POS, last.bob_angle, GREEN),
        ]:
            rect = pygame.Rect(pos[0] - arc_r, pos[1] - arc_r,
                               arc_r * 2, arc_r * 2)
            pygame.draw.arc(screen, clr, rect,
                            -0.1, angle + 0.1, 2)
            # 각도 끝점에 작은 원
            end_x = pos[0] + int(arc_r * math.cos(angle))
            end_y = pos[1] - int(arc_r * math.sin(angle))
            pygame.draw.circle(screen, clr, (end_x, end_y), 3)

    # Eve (도청 표시)
    eve_alpha = 80
    if e91.eve_rounds > 0 and e91.total_rounds > 0:
        eve_ratio = e91.eve_rounds / e91.total_rounds
        eve_alpha = max(80, min(255, int(eve_ratio * 500)))
    pygame.draw.circle(screen, (*RED[:3], min(255, eve_alpha)),
                       EVE_POS, 18)
    pygame.draw.circle(screen, TEXT_CLR, EVE_POS, 18, 2)
    lbl = font.render(t("qa_eve"), True, RED)
    screen.blit(lbl, (EVE_POS[0] - lbl.get_width() // 2, EVE_POS[1] - 28))

    # 통계 패널
    sy = 200
    key_rate = (e91.key_rounds / e91.total_rounds * 100) if e91.total_rounds > 0 else 0.0
    stats = [
        (t("qa_e91_rounds", total=e91.total_rounds, key=e91.key_rounds, bell=e91.bell_rounds), TEXT_CLR),
        (t("qa_raw_key_len", bits=len(e91.raw_key_alice)), BLUE),
        (t("qa_key_rate", rate=key_rate, bits=e91.key_rounds, rounds=e91.total_rounds), PEACH),
        (t("qa_bell_s_detail", s=e91.bell_S, cl=CHSH_CLASSICAL_BOUND, ql=CHSH_QUANTUM_BOUND), ACCENT),
    ]
    if e91.bell_violated:
        stats.append((t("qa_bell_violated"), GREEN))
    elif e91.bell_rounds > 20:
        stats.append((t("qa_bell_not_violated"), RED))

    for i, (txt, clr) in enumerate(stats):
        surf = font.render(txt, True, clr)
        screen.blit(surf, (40, sy + i * 16))

    # 벨 S 미터
    meter_x, meter_y = 40, 280
    meter_w, meter_h = 300, 18
    pygame.draw.rect(screen, PANEL_BG, (meter_x, meter_y, meter_w, meter_h))

    # 고전 한계 마커
    cl_x = meter_x + int(meter_w * CHSH_CLASSICAL_BOUND / 3.0)
    pygame.draw.line(screen, YELLOW, (cl_x, meter_y - 2), (cl_x, meter_y + meter_h + 2), 2)
    cl_lbl = font.render("2.0", True, YELLOW)
    screen.blit(cl_lbl, (cl_x - 8, meter_y + meter_h + 4))

    # 양자 한계 마커
    ql_x = meter_x + int(meter_w * CHSH_QUANTUM_BOUND / 3.0)
    pygame.draw.line(screen, MAUVE, (ql_x, meter_y - 2), (ql_x, meter_y + meter_h + 2), 2)
    ql_lbl = font.render("2√2", True, MAUVE)
    screen.blit(ql_lbl, (ql_x - 10, meter_y + meter_h + 4))

    # S 값 채움
    s_ratio = min(abs(e91.bell_S) / 3.0, 1.0)
    fill_w = int(meter_w * s_ratio)
    fill_clr = GREEN if e91.bell_violated else RED
    if fill_w > 0:
        pygame.draw.rect(screen, fill_clr, (meter_x, meter_y, fill_w, meter_h))
    pygame.draw.rect(screen, TEXT_CLR, (meter_x, meter_y, meter_w, meter_h), 1)

    s_lbl = big_font.render(f"S = {abs(e91.bell_S):.3f}", True, TEXT_CLR)
    screen.blit(s_lbl, (meter_x + meter_w + 10, meter_y))

    # Bell S 보안 상태 뱃지
    if e91.bell_rounds > 10:
        abs_s = abs(e91.bell_S)
        if abs_s > CHSH_QUANTUM_BOUND * 0.95:
            badge_clr, badge_txt = GREEN, t("qa_bell_badge_secure")
        elif abs_s > CHSH_CLASSICAL_BOUND:
            badge_clr, badge_txt = YELLOW, t("qa_bell_badge_caution")
        else:
            badge_clr, badge_txt = RED, t("qa_bell_badge_danger")
        badge_x = meter_x + meter_w + 14 + s_lbl.get_width()
        pygame.draw.rect(screen, badge_clr,
                         (badge_x, meter_y + 1, 50, 14), border_radius=3)
        bt = font.render(badge_txt, True, BG)
        screen.blit(bt, (badge_x + 25 - bt.get_width() // 2, meter_y + 1))

    # 키 비트 티커
    if len(e91.raw_key_alice) > 0:
        ticker_hdr = font.render("Key bits:", True, SUBTEXT_CLR)
        screen.blit(ticker_hdr, (40, 304))
        _draw_key_ticker(screen, e91.raw_key_alice, 108, 304, 200, font, anim_t)

    # 최근 라운드 로그
    log_y = 320
    header = big_font.render(t("qa_round_log"), True, ACCENT)
    screen.blit(header, (40, log_y))

    for i, rd in enumerate(e91.rounds[-12:]):
        basis_match = t("qa_tag_key") if rd.same_basis else t("qa_tag_bell")
        eve = f" [{t('qa_tag_eve')}]" if rd.eve_present else ""
        a_deg = f"{math.degrees(rd.alice_angle):.0f}°"
        b_deg = f"{math.degrees(rd.bob_angle):.0f}°"
        clr = GREEN if rd.same_basis else SUBTEXT_CLR
        if rd.eve_present:
            clr = RED
        txt = t("qa_e91_log_entry", rid=rd.round_id, a_angle=a_deg, b_angle=b_deg,
                tag=basis_match, a_res=rd.alice_result, b_res=rd.bob_result, eve=eve)
        surf = font.render(txt, True, clr)
        screen.blit(surf, (40, log_y + 18 + i * 14))

    # 상관 함수 테이블
    _draw_correlator_table(screen, e91, font, big_font)

    # 얽힘 증인 게이지
    _draw_witness_gauge(screen, e91, font, big_font)

    # Bell S 시계열 수렴 그래프
    _draw_bell_s_graph(screen, e91.bell_S_history, 480, 340, 390, 170,
                       font, big_font)


def _draw_witness_gauge(screen, e91: E91State, font, big_font):
    """얽힘 증인 (Entanglement Witness) 아크 게이지."""
    gx, gy = 770, 68
    gr = 32  # arc radius
    W = e91.witness_value

    # 배경 아크 (회색)
    arc_rect = pygame.Rect(gx - gr, gy - gr, gr * 2, gr * 2)
    pygame.draw.arc(screen, OVERLAY, arc_rect, 0.2, math.pi - 0.2, 3)

    # 값 아크 (W 비율에 따른 색상)
    if W > 0.7:
        arc_clr = GREEN
    elif W > 0.5:
        arc_clr = YELLOW
    else:
        arc_clr = RED
    arc_end = 0.2 + (math.pi - 0.4) * min(W, 1.0)
    if W > 0.01:
        pygame.draw.arc(screen, arc_clr, arc_rect, 0.2, arc_end, 3)

    # 0.5 임계선 마커
    thresh_angle = 0.2 + (math.pi - 0.4) * 0.5
    tx = gx + int(gr * math.cos(thresh_angle))
    ty = gy - int(gr * math.sin(thresh_angle))
    pygame.draw.circle(screen, YELLOW, (tx, ty), 2)

    # 중앙 텍스트
    w_txt = f"W={W:.2f}"
    w_surf = font.render(w_txt, True, arc_clr)
    screen.blit(w_surf, (gx - w_surf.get_width() // 2, gy - 4))

    # 상태 뱃지
    if e91.bell_rounds > 5:
        if W > 0.7:
            badge = t("qa_witness_entangled")
        elif W > 0.5:
            badge = t("qa_witness_border")
        else:
            badge = t("qa_witness_separable")
        b_surf = font.render(badge, True, arc_clr)
        screen.blit(b_surf, (gx - b_surf.get_width() // 2, gy + gr + 4))

    # 라벨
    lbl = font.render(t("qa_witness_title"), True, SUBTEXT_CLR)
    screen.blit(lbl, (gx - lbl.get_width() // 2, gy - gr - 14))


def _draw_correlator_table(screen, e91: E91State, font, big_font):
    """E91 상관 함수 테이블."""
    tx, ty = 500, 200
    header = big_font.render(t("qa_correlators"), True, ACCENT)
    screen.blit(header, (tx, ty))

    base_labels_a = ["0°", "π/8", "π/4"]
    base_labels_b = ["π/8", "π/4", "3π/8"]

    # 헤더 (캐시 사용)
    for j, bl in enumerate(base_labels_b):
        surf = _tcache.render(font, bl, GREEN)
        screen.blit(surf, (tx + 60 + j * 70, ty + 18))

    for i, al in enumerate(base_labels_a):
        y = ty + 36 + i * 18
        surf = _tcache.render(font, al, BLUE)
        screen.blit(surf, (tx, y))

        for j in range(3):
            pair = (i, j)
            data = e91.correlators.get(pair, [])
            if len(data) > 0:
                avg = sum(data) / len(data)
                val_txt = f"{avg:+.2f}"
                # 키 쌍은 하이라이트
                is_key = pair in [(1, 0), (2, 1)]
                clr = YELLOW if is_key else TEXT_CLR
            else:
                val_txt = t("qa_cmp_no_data")
                clr = SUBTEXT_CLR
            surf = font.render(val_txt, True, clr)
            screen.blit(surf, (tx + 60 + j * 70, y))

    # 범례
    leg_y = ty + 36 + 3 * 18 + 8
    leg = font.render(t("qa_key_pair_legend"), True, YELLOW)
    screen.blit(leg, (tx, leg_y))

    # 얽힘 충실도 미터 (키 쌍 상관값 기반)
    fid_y = leg_y + 18
    key_corr_data = []
    for kp in [(1, 0), (2, 1)]:
        vals = e91.correlators.get(kp, [])
        if vals:
            key_corr_data.append(abs(sum(vals) / len(vals)))
    if key_corr_data:
        avg_corr = sum(key_corr_data) / len(key_corr_data)
        fidelity = min(avg_corr / 0.707, 1.0) * 100  # 이상적 |E|≈0.707
        fid_clr = GREEN if fidelity > 85 else (YELLOW if fidelity > 60 else RED)
        fid_txt = font.render(t("qa_fidelity", f=fidelity), True, fid_clr)
        screen.blit(fid_txt, (tx, fid_y))
        # 바
        bar_x, bar_w, bar_h = tx, 180, 5
        pygame.draw.rect(screen, OVERLAY, (bar_x, fid_y + 14, bar_w, bar_h),
                         border_radius=2)
        fill_w = int(bar_w * fidelity / 100)
        if fill_w > 0:
            pygame.draw.rect(screen, fid_clr, (bar_x, fid_y + 14, fill_w, bar_h),
                             border_radius=2)

    # 누적 키 생성 차트 (E91 우하단)
    if len(e91.key_accumulation) >= 2:
        _draw_key_accumulation(screen, e91.key_accumulation,
                               500, 340, 380, 80, font, big_font)


# ── Key Sift & PA 모드 ──────────────────────────────

def _draw_sift_mode(screen, e91: E91State, anim_t, font, big_font):
    """QKD 후처리 파이프라인 시각화 (4단계)."""
    sy = 68

    # 4단계 파이프라인
    corrected_bits = len(e91.corrected_key)
    _stage_tips = [
        t("qa_tip_raw_key"), t("qa_tip_qber"),
        t("qa_tip_ec"), t("qa_tip_pa"),
    ]
    stages = [
        (t("qa_sift_raw_key"), len(e91.raw_key_alice), BLUE,
         len(e91.raw_key_alice) > 0),
        (t("qa_sift_qber_est"), e91.qber_sample_size, YELLOW,
         e91.qber_done),
        (t("qa_sift_err_corr"), corrected_bits, GREEN,
         e91.correction_done),
        (t("qa_sift_priv_amp"), len(e91.final_key) * 4, MAUVE,
         e91.pa_done),
    ]

    box_w = 130
    box_h = 50
    gap = 32
    start_x = (WIDTH - (box_w * 4 + gap * 3)) // 2
    mx, my = pygame.mouse.get_pos()
    stage_tooltip = None

    for i, (label, size, clr, done) in enumerate(stages):
        bx = start_x + i * (box_w + gap)
        by = sy
        hovered = bx <= mx <= bx + box_w and by <= my <= by + box_h

        pygame.draw.rect(screen, PANEL_BG, (bx, by, box_w, box_h), border_radius=8)
        border_clr = clr if done else (TEXT_CLR if hovered else OVERLAY)
        pygame.draw.rect(screen, border_clr, (bx, by, box_w, box_h), 2, border_radius=8)

        lbl = big_font.render(label, True, clr if done else SUBTEXT_CLR)
        screen.blit(lbl, (bx + box_w // 2 - lbl.get_width() // 2, by + 8))

        size_txt = font.render(f"{size} bits", True, TEXT_CLR if done else SUBTEXT_CLR)
        screen.blit(size_txt, (bx + box_w // 2 - size_txt.get_width() // 2, by + 30))

        if hovered:
            stage_tooltip = (bx, by + box_h + 4, _stage_tips[i])

        # 화살표
        if i < 3:
            ax = bx + box_w + 3
            ay = by + box_h // 2
            pygame.draw.line(screen, SUBTEXT_CLR, (ax, ay), (ax + gap - 8, ay), 2)
            pygame.draw.polygon(screen, SUBTEXT_CLR,
                                [(ax + gap - 8, ay - 3), (ax + gap - 2, ay), (ax + gap - 8, ay + 3)])

    # 파이프라인 스테이지 툴팁
    if stage_tooltip:
        tip_x, tip_y, tip_text = stage_tooltip
        tip_surf = font.render(tip_text, True, TEXT_CLR)
        tip_bg = pygame.Rect(tip_x - 2, tip_y, tip_surf.get_width() + 8, 14)
        pygame.draw.rect(screen, PANEL_BG, tip_bg, border_radius=3)
        pygame.draw.rect(screen, OVERLAY, tip_bg, 1, border_radius=3)
        screen.blit(tip_surf, (tip_x + 2, tip_y + 1))

    # 원시 키 비트 시각화
    ky = 140
    _draw_key_bits(screen, t("qa_sift_alice_raw"), e91.raw_key_alice[:64], BLUE, 40, ky, font, big_font)
    _draw_key_bits(screen, t("qa_sift_bob_raw"), e91.raw_key_bob[:64], GREEN, 40, ky + 30, font, big_font)

    # QBER 추정 결과
    if e91.qber_done:
        qber_y = ky + 65
        qber_pct = e91.qber_value * 100
        qber_clr = RED if e91.qber_value > 0.11 else GREEN
        qber_txt = t("qa_qber_display", pct=qber_pct, n=e91.qber_sample_size)
        screen.blit(font.render(qber_txt, True, qber_clr), (40, qber_y))
        # QBER 해석
        if e91.qber_value > 0.11:
            warn = font.render(t("qa_qber_warning"), True, RED)
            screen.blit(warn, (40, qber_y + 14))
        else:
            safe = font.render(t("qa_qber_safe"), True, GREEN)
            screen.blit(safe, (40, qber_y + 14))

    # 에러 정정 결과
    if e91.correction_done:
        ec_y = ky + 100
        _draw_key_bits(screen, t("qa_sift_corrected"), e91.corrected_key[:64], GREEN, 40, ec_y, font, big_font)
        ec_txt = t("qa_sift_ec_msg", flips=e91.correction_flips)
        screen.blit(font.render(ec_txt, True, TEXT_CLR), (40, ec_y + 18))

        # 에러 패턴 히트맵 (블록 기반)
        if e91.error_positions:
            _draw_error_heatmap(screen, e91, 460, ec_y - 10, font, big_font)

    # 최종 키 + 키 합의 검증
    if e91.pa_done and e91.final_key:
        fy = ky + 140
        header = big_font.render(t("qa_final_key_hdr"), True, ACCENT)
        screen.blit(header, (40, fy))
        key = e91.final_key
        for i in range(0, len(key), 32):
            chunk = key[i:i + 32]
            screen.blit(font.render(chunk, True, MAUVE), (40, fy + 16 + (i // 32) * 14))

        # 키 합의 검증 패널
        vfy = fy + 16 + ((len(key) - 1) // 32 + 1) * 14 + 4
        match_pct = e91.key_match_rate * 100
        match_clr = GREEN if match_pct > 95 else (YELLOW if match_pct > 80 else RED)
        vfy_txt = t("qa_key_verify", pct=match_pct)
        vfy_badge = "[OK]" if match_pct > 95 else "[!!]"
        screen.blit(font.render(f"{vfy_txt} {vfy_badge}", True, match_clr), (40, vfy))

        # OTP 암호화 데모
        _draw_otp_demo(screen, e91.final_key, 460, ky + 68, font, big_font)

    # 통계
    stats_y = 420
    raw_n = len(e91.raw_key_alice)
    corr_n = len(e91.corrected_key)
    final_n = len(e91.final_key) * 4
    stats = [
        (t("qa_e91_rounds", total=e91.total_rounds, key=e91.key_rounds, bell=e91.bell_rounds), TEXT_CLR),
        (t("qa_sift_pipeline", raw=raw_n, sample=e91.qber_sample_size, corr=corr_n, final=final_n), ACCENT),
        (t("qa_sift_qber_stat", pct=e91.qber_value * 100, flips=e91.correction_flips), TEXT_CLR),
        (t("qa_sift_bell_stat", s=e91.bell_S, verdict=t('qa_sift_stat_secure') if e91.bell_violated else t('qa_sift_stat_warning')), GREEN if e91.bell_violated else RED),
    ]
    for i, (txt, clr) in enumerate(stats):
        screen.blit(font.render(txt, True, clr), (40, stats_y + i * 16))


def _draw_error_heatmap(screen, e91: E91State, x, y, font, big_font):
    """에러 패턴 히트맵 — 블록별 에러 분포 시각화."""
    key_len = len(e91.sifted_key)
    if key_len == 0:
        return
    # 8블록으로 나눔
    n_blocks = min(8, max(1, key_len // 4))
    block_size = key_len // n_blocks if n_blocks > 0 else key_len

    hdr = big_font.render(t("qa_error_heatmap"), True, ACCENT)
    screen.blit(hdr, (x, y))

    cell_w, cell_h = 28, 18
    hy = y + 16
    error_set = set(e91.error_positions)
    for bi in range(n_blocks):
        start = bi * block_size
        end = start + block_size
        errs = sum(1 for p in error_set if start <= p < end)
        # 열강도: 0=deep blue, high=red
        if block_size > 0:
            ratio = min(errs / max(block_size * 0.3, 1), 1.0)
        else:
            ratio = 0
        r = int(RED[0] * ratio + BLUE[0] * (1 - ratio))
        g = int(RED[1] * ratio + BLUE[1] * (1 - ratio))
        b = int(RED[2] * ratio + BLUE[2] * (1 - ratio))
        cell_clr = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

        cx = x + bi * (cell_w + 2)
        pygame.draw.rect(screen, cell_clr, (cx, hy, cell_w, cell_h), border_radius=2)
        pygame.draw.rect(screen, OVERLAY, (cx, hy, cell_w, cell_h), 1, border_radius=2)
        # 에러 수 표시
        etxt = font.render(str(errs), True, WHITE if ratio > 0.3 else TEXT_CLR)
        screen.blit(etxt, (cx + cell_w // 2 - etxt.get_width() // 2,
                           hy + 3))

    # 범례
    leg_txt = font.render(t("qa_error_legend", n=len(e91.error_positions),
                             total=key_len), True, SUBTEXT_CLR)
    screen.blit(leg_txt, (x, hy + cell_h + 3))


def _draw_key_bits(screen, label, bits, color, x, y, font, big_font):
    """키 비트 시각화."""
    lbl = big_font.render(label + ":", True, color)
    screen.blit(lbl, (x, y))

    bx = x + lbl.get_width() + 8
    for i, bit in enumerate(bits):
        if bx + 8 > WIDTH - 40:
            break
        clr = color if bit == 1 else OVERLAY
        pygame.draw.rect(screen, clr, (bx, y + 2, 6, 12))
        bx += 8


def _draw_otp_demo(screen, final_key, x, y, font, big_font):
    """OTP(XOR) 암호화 데모 패널."""
    w, h = 400, 150
    pygame.draw.rect(screen, PANEL_BG, (x, y, w, h), border_radius=8)
    pygame.draw.rect(screen, ACCENT, (x, y, w, h), 1, border_radius=8)

    # 제목
    title = big_font.render(t("qa_otp_title"), True, ACCENT)
    screen.blit(title, (x + 8, y + 6))

    # 평문
    py = y + 26
    pt_lbl = font.render(t("qa_otp_plain"), True, TEXT_CLR)
    screen.blit(pt_lbl, (x + 8, py))
    pt_val = big_font.render(f'"{_DEMO_PLAINTEXT}"', True, GREEN)
    screen.blit(pt_val, (x + 8 + pt_lbl.get_width() + 6, py))

    # 키 (사용 부분)
    key_len_needed = len(_DEMO_PLAINTEXT.encode("utf-8")) * 2  # hex chars
    used_key = final_key[:key_len_needed] if len(final_key) >= key_len_needed else final_key
    ky = py + 16
    k_lbl = font.render(t("qa_otp_key"), True, TEXT_CLR)
    screen.blit(k_lbl, (x + 8, ky))
    k_val = font.render(used_key, True, MAUVE)
    screen.blit(k_val, (x + 8 + k_lbl.get_width() + 6, ky))

    # 암호화
    ciphertext = xor_encrypt(_DEMO_PLAINTEXT, final_key)
    cy = ky + 16
    c_lbl = font.render(t("qa_otp_cipher"), True, TEXT_CLR)
    screen.blit(c_lbl, (x + 8, cy))
    c_val = font.render(ciphertext if ciphertext else "---", True, RED)
    screen.blit(c_val, (x + 8 + c_lbl.get_width() + 6, cy))

    # 복호화
    decrypted = xor_decrypt(ciphertext, final_key)
    dy = cy + 16
    d_lbl = font.render(t("qa_otp_decrypt"), True, TEXT_CLR)
    screen.blit(d_lbl, (x + 8, dy))
    d_val = big_font.render(f'"{decrypted}"', True, GREEN)
    screen.blit(d_val, (x + 8 + d_lbl.get_width() + 6, dy))

    # XOR 수식 표시
    fy = dy + 20
    formula = font.render(t("qa_otp_xor_formula"), True, SUBTEXT_CLR)
    screen.blit(formula, (x + 8, fy))

    # OTP 보안 노트
    ny = fy + 14
    note = font.render(t("qa_otp_note"), True, SUBTEXT_CLR)
    screen.blit(note, (x + 8, ny))


# ── GHZ Multi-Party 모드 ────────────────────────────

def _draw_ghz_mode(screen, ghz: GHZState, anim_t, font, big_font,
                   flash_timer: float = 0.0):
    """GHZ N자간 QKD 시각화."""
    n = ghz.n_parties
    node_colors = [BLUE, GREEN, PEACH, YELLOW, RED]

    # 파티 수 슬라이더 표시
    slider_x, slider_y = WIDTH - 180, 62
    slider_lbl = big_font.render(t("qa_ghz_parties"), True, ACCENT)
    screen.blit(slider_lbl, (slider_x, slider_y))
    # 버튼 스타일 숫자 표시 (호버 하이라이트 포함)
    mx, my = pygame.mouse.get_pos()
    for pn in range(GHZ_MIN_PARTIES, GHZ_MAX_PARTIES + 1):
        bx = slider_x + (pn - GHZ_MIN_PARTIES) * 36
        by = slider_y + 18
        active = pn == n
        hovered = bx <= mx <= bx + 30 and by <= my <= by + 20
        btn_clr = ACCENT if active else (TEXT_CLR if hovered else SUBTEXT_CLR)
        bg_clr = PANEL_BG if active else (OVERLAY if hovered else BG)
        pygame.draw.rect(screen, bg_clr, (bx, by, 30, 20), border_radius=4)
        if active or hovered:
            pygame.draw.rect(screen, btn_clr, (bx, by, 30, 20), 2, border_radius=4)
        num = big_font.render(str(pn), True, btn_clr)
        screen.blit(num, (bx + 15 - num.get_width() // 2, by + 2))
    hint = font.render(t("qa_ghz_updown"), True, SUBTEXT_CLR)
    screen.blit(hint, (slider_x, slider_y + 42))

    # N자 네트워크 토폴로지 (정다각형)
    cx, cy = WIDTH // 2, 170
    radius = 80 + n * 8
    positions = []
    colors = node_colors[:n]

    for i in range(n):
        angle = -math.pi / 2 + i * 2 * math.pi / n
        px = int(cx + radius * math.cos(angle))
        py = int(cy + radius * math.sin(angle))
        positions.append((px, py))

    # GHZ 소스 (중앙)
    pygame.draw.circle(screen, MAUVE, (cx, cy), 20)
    pygame.draw.circle(screen, TEXT_CLR, (cx, cy), 20, 2)
    ghz_lbl = _tcache.render(big_font, "GHZ", MAUVE)
    screen.blit(ghz_lbl, (cx - ghz_lbl.get_width() // 2, cy - 8))

    # 얽힘 링크 (물결 — Eve 비율에 따라 MAUVE→RED)
    if ghz.total_rounds > 0:
        eve_ratio = ghz.eve_rounds / ghz.total_rounds
        link_r = int(MAUVE[0] + (RED[0] - MAUVE[0]) * eve_ratio)
        link_g = int(MAUVE[1] + (RED[1] - MAUVE[1]) * eve_ratio)
        link_b = int(MAUVE[2] + (RED[2] - MAUVE[2]) * eve_ratio)
        link_clr = (max(0, min(255, link_r)),
                    max(0, min(255, link_g)),
                    max(0, min(255, link_b)))
    else:
        link_clr = MAUVE
    for pos in positions:
        wave = math.sin(anim_t * 3) * 3
        mid_x = (cx + pos[0]) // 2 + int(wave)
        mid_y = (cy + pos[1]) // 2 + int(wave)
        pygame.draw.lines(screen, link_clr, False, [(cx, cy), (mid_x, mid_y), pos], 1)

    # 노드 (활성 파티 펄스 효과)
    pulse = (math.sin(anim_t * 4) + 1) * 0.5  # 0~1 oscillation
    for i, (pos, name, clr) in enumerate(zip(positions, ghz.party_names, colors)):
        # Z-basis 라운드 가장 최근 측정 기저가 Z면 빛나기
        is_active = ghz.total_rounds > 0 and (ghz.total_rounds % n == i)
        if is_active:
            glow_r = int(24 + 6 * pulse)
            glow_surf = pygame.Surface((glow_r * 2 + 4, glow_r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*clr, int(60 * pulse)),
                               (glow_r + 2, glow_r + 2), glow_r + 2)
            screen.blit(glow_surf, (pos[0] - glow_r - 2, pos[1] - glow_r - 2))
        pygame.draw.circle(screen, clr, pos, 24)
        pygame.draw.circle(screen, TEXT_CLR, pos, 24, 2)
        # 측정 플래시 효과
        if flash_timer > 0 and ghz.rounds:
            last_rd = ghz.rounds[-1]
            flash_alpha = int((flash_timer / 0.3) * 180)
            result_bit = last_rd.results[i] if i < len(last_rd.results) else 0
            flash_clr = WHITE if result_bit == 0 else YELLOW
            flash_surf = pygame.Surface((56, 56), pygame.SRCALPHA)
            pygame.draw.circle(flash_surf, (*flash_clr[:3], flash_alpha),
                               (28, 28), 28)
            screen.blit(flash_surf, (pos[0] - 28, pos[1] - 28))
            # 측정값 표시
            bit_lbl = big_font.render(str(result_bit), True, BG)
            screen.blit(bit_lbl, (pos[0] - bit_lbl.get_width() // 2,
                                  pos[1] - 7))
        lbl = big_font.render(name, True, clr)
        screen.blit(lbl, (pos[0] - lbl.get_width() // 2, pos[1] + 28))

    # GHZ 상태 표시 (N자간)
    zeros = "0" * n
    ones = "1" * n
    state_lbl = font.render(f"|GHZ⟩ = (|{zeros}⟩ + |{ones}⟩) / √2", True, MAUVE)
    screen.blit(state_lbl, (cx - state_lbl.get_width() // 2, cy + 22))

    # 통계
    sy = 300
    ghz_key_rate = (ghz.key_rounds / ghz.total_rounds * 100) if ghz.total_rounds > 0 else 0.0
    stats = [
        (t("qa_ghz_rounds", total=ghz.total_rounds, key=ghz.key_rounds, chk=ghz.consistency_checks), TEXT_CLR),
        (t("qa_raw_key_len", bits=len(ghz.raw_keys[0])), BLUE),
        (t("qa_key_rate", rate=ghz_key_rate, bits=ghz.key_rounds, rounds=ghz.total_rounds), PEACH),
    ]

    if ghz.consistency_checks > 0:
        pass_rate = ghz.consistency_pass / ghz.consistency_checks
        c_sym = "OK" if pass_rate > 0.85 else "!!"
        stats.append((t("qa_ghz_consistency", **{"pass": ghz.consistency_pass},
                        total=ghz.consistency_checks, pct=pass_rate * 100)
                       + f" [{c_sym}]",
                       GREEN if pass_rate > 0.85 else RED))

    if ghz.sift_done:
        stats.append((t("qa_ghz_sifted", bits=len(ghz.sifted_key), err=ghz.error_rate * 100),
                       MAUVE))

    if ghz.pa_done and ghz.final_key:
        stats.append((t("qa_ghz_final_key", key=ghz.final_key[:40]), ACCENT))

    for i, (txt, clr) in enumerate(stats):
        surf = font.render(txt, True, clr)
        screen.blit(surf, (40, sy + i * 16))

    # GHZ OTP 암호화 데모 (PA 완료 후)
    if ghz.pa_done and ghz.final_key:
        _draw_otp_demo(screen, ghz.final_key, 460, sy, font, big_font)

    # GHZ 일관성 수렴 그래프 (오른쪽)
    if not (ghz.pa_done and ghz.final_key):
        _draw_consistency_graph(screen, ghz.consistency_history,
                                460, sy, 400, 140, font, big_font)

    # 라운드 로그
    log_y = sy + len(stats) * 16 + 20
    header = big_font.render(t("qa_round_log"), True, ACCENT)
    screen.blit(header, (40, log_y))

    for i, rd in enumerate(ghz.rounds[-14:]):
        bases = "/".join(rd.bases)
        results = "/".join(str(r) for r in rd.results)
        is_key = rd.all_same_basis and rd.bases[0] == "Z"
        is_chk = rd.all_same_basis and rd.bases[0] == "X"
        tag = t("qa_tag_key") if is_key else \
              t("qa_tag_chk") if is_chk else t("qa_tag_mix")
        eve = f" [{t('qa_tag_eve')}]" if rd.eve_present else ""

        if rd.eve_present:
            clr = RED
        elif is_key:
            clr = GREEN
        elif is_chk:
            clr = YELLOW
        else:
            clr = SUBTEXT_CLR

        txt = t("qa_ghz_log_entry", rid=rd.round_id, bases=bases, results=results,
                tag=tag, eve=eve)
        surf = font.render(txt, True, clr)
        screen.blit(surf, (40, log_y + 18 + i * 14))

    # X-기저 패리티 검사 시각화 블록
    if ghz.consistency_checks > 0:
        parity_y = log_y + 18 + min(len(ghz.rounds), 14) * 14 + 8
        p_hdr = font.render(t("qa_ghz_parity_title"), True, ACCENT)
        screen.blit(p_hdr, (40, parity_y))
        blk_x = 40
        blk_size = 8
        blk_gap = 2
        # X-기저 라운드의 패리티 결과 (최근 60개)
        x_rounds = [rd for rd in ghz.rounds if rd.all_same_basis and rd.bases[0] == "X"]
        for bi, rd in enumerate(x_rounds[-60:]):
            parity = sum(rd.results) % 2
            blk_clr = GREEN if parity == 0 else RED
            bx = blk_x + bi * (blk_size + blk_gap)
            by = parity_y + 14
            if bx + blk_size > WIDTH - 40:
                break
            pygame.draw.rect(screen, blk_clr, (bx, by, blk_size, blk_size))


# ── BB84 vs E91 비교 모드 ──────────────────────────


def _draw_compare_mode(screen, bb84: BB84State, e91: E91State,
                       font, big_font):
    """BB84 vs E91 비교 시각화 — 동일 Eve 조건 나란히 표시."""
    half_w = WIDTH // 2 - 20
    left_x = 20
    right_x = WIDTH // 2 + 10

    # ── 구분선 ──
    pygame.draw.line(screen, OVERLAY, (WIDTH // 2, 62), (WIDTH // 2, HEIGHT - 50), 1)

    # ── 헤더 ──
    bb84_hdr = big_font.render(t("qa_cmp_bb84_title"), True, BLUE)
    screen.blit(bb84_hdr, (left_x + half_w // 2 - bb84_hdr.get_width() // 2, 62))

    e91_hdr = big_font.render(t("qa_cmp_e91_title"), True, MAUVE)
    screen.blit(e91_hdr, (right_x + half_w // 2 - e91_hdr.get_width() // 2, 62))

    # ── BB84 (왼쪽) ──
    by = 84
    bb84_key_rate = (bb84.basis_match_rounds / bb84.total_rounds * 100) if bb84.total_rounds > 0 else 0.0
    bb84_stats = [
        (t("qa_cmp_bb84_rounds", total=bb84.total_rounds), TEXT_CLR),
        (t("qa_cmp_bb84_basis", match=bb84.basis_match_rounds, pct=bb84.basis_match_rounds / max(bb84.total_rounds, 1) * 100), TEXT_CLR),
        (t("qa_cmp_bb84_rawkey", bits=bb84.raw_key_bits), BLUE),
        (t("qa_key_rate", rate=bb84_key_rate, bits=bb84.basis_match_rounds, rounds=bb84.total_rounds), PEACH),
        (t("qa_cmp_bb84_eve", count=bb84.eve_rounds), RED if bb84.eve_rounds > 0 else SUBTEXT_CLR),
        ("", TEXT_CLR),
        (t("qa_cmp_detection"), ACCENT),
        (t("qa_cmp_bb84_qber", pct=bb84.qber * 100), RED if bb84.qber > 0.11 else GREEN),
    ]
    if bb84.eve_detected:
        bb84_stats.append((t("qa_cmp_eve_detected"), RED))
    elif bb84.total_rounds > 20:
        bb84_stats.append((t("qa_cmp_secure"), GREEN))

    for i, (txt, clr) in enumerate(bb84_stats):
        surf = font.render(txt, True, clr)
        screen.blit(surf, (left_x, by + i * 16))

    # QBER 미터 (BB84)
    bb84_meter_y = by + len(bb84_stats) * 16 + 8
    _draw_qber_meter(screen, bb84.qber, left_x, bb84_meter_y,
                     half_w, font, big_font)

    # QBER 수렴 그래프 (BB84 왼쪽 패널 하단)
    bb84_graph_y = bb84_meter_y + 28
    _draw_qber_graph(screen, bb84.qber_history,
                     left_x, bb84_graph_y, half_w, 100, font, big_font)

    # BB84 미니 파이프라인 (Compare 모드)
    bb84_pipe_y = bb84_graph_y + 108
    bb84_stages = [
        (t("qa_sift_raw_key"), len(bb84.raw_key), BLUE, len(bb84.raw_key) > 0),
        (t("qa_sift_qber_est"), bb84.qber_sample_size, YELLOW, bb84.qber_done),
        (t("qa_sift_err_corr"), len(bb84.corrected_key), GREEN, bb84.correction_done),
        (t("qa_sift_priv_amp"), len(bb84.final_key) * 4, MAUVE, bb84.pa_done),
    ]
    mini_w = (half_w - 16) // 4
    for si, (slbl, ssize, sclr, sdone) in enumerate(bb84_stages):
        sx = left_x + si * (mini_w + 2)
        pygame.draw.rect(screen, PANEL_BG, (sx, bb84_pipe_y, mini_w - 2, 28), border_radius=4)
        bdr = sclr if sdone else OVERLAY
        pygame.draw.rect(screen, bdr, (sx, bb84_pipe_y, mini_w - 2, 28), 1, border_radius=4)
        ls = font.render(slbl, True, sclr if sdone else SUBTEXT_CLR)
        screen.blit(ls, (sx + (mini_w - 2) // 2 - ls.get_width() // 2, bb84_pipe_y + 2))
        bs = font.render(f"{ssize}b", True, TEXT_CLR if sdone else SUBTEXT_CLR)
        screen.blit(bs, (sx + (mini_w - 2) // 2 - bs.get_width() // 2, bb84_pipe_y + 15))

    if bb84.pa_done and bb84.final_key:
        fk_y = bb84_pipe_y + 30
        fk_txt = font.render(f"Key: {bb84.final_key[:16]}...", True, GREEN)
        screen.blit(fk_txt, (left_x, fk_y))

    # ── E91 (오른쪽) ──
    e91_key_rate = (e91.key_rounds / e91.total_rounds * 100) if e91.total_rounds > 0 else 0.0
    e91_stats = [
        (t("qa_cmp_e91_rounds", total=e91.total_rounds, key=e91.key_rounds, bell=e91.bell_rounds), TEXT_CLR),
        (t("qa_cmp_e91_keypairs", key=e91.key_rounds, pct=e91.key_rounds / max(e91.total_rounds, 1) * 100), TEXT_CLR),
        (t("qa_cmp_e91_rawkey", bits=len(e91.raw_key_alice)), MAUVE),
        (t("qa_key_rate", rate=e91_key_rate, bits=e91.key_rounds, rounds=e91.total_rounds), PEACH),
        (t("qa_cmp_e91_eve", count=e91.eve_rounds), RED if e91.eve_rounds > 0 else SUBTEXT_CLR),
        ("", TEXT_CLR),
        (t("qa_cmp_detection"), ACCENT),
        (t("qa_cmp_e91_bell", s=e91.bell_S, bound=CHSH_CLASSICAL_BOUND), GREEN if e91.bell_violated else RED),
    ]
    if e91.bell_violated:
        e91_stats.append((t("qa_cmp_bell_secure"), GREEN))
    elif e91.bell_rounds > 20:
        e91_stats.append((t("qa_cmp_bell_warning"), RED))

    for i, (txt, clr) in enumerate(e91_stats):
        surf = font.render(txt, True, clr)
        screen.blit(surf, (right_x, by + i * 16))

    # Bell S 미터 (E91)
    meter_y = by + len(e91_stats) * 16 + 8
    _draw_bell_meter(screen, e91.bell_S, right_x, meter_y,
                     half_w, font, big_font)

    # Bell S 수렴 그래프 (E91 오른쪽 패널 하단)
    graph_y = meter_y + 28
    _draw_bell_s_graph(screen, e91.bell_S_history,
                       right_x, graph_y, half_w, 100, font, big_font)

    # E91 미니 파이프라인 (Compare 모드)
    e91_pipe_y = graph_y + 108
    corrected_e91 = len(e91.corrected_key)
    e91_stages = [
        (t("qa_sift_raw_key"), len(e91.raw_key_alice), BLUE, len(e91.raw_key_alice) > 0),
        (t("qa_sift_qber_est"), e91.qber_sample_size, YELLOW, e91.qber_done),
        (t("qa_sift_err_corr"), corrected_e91, GREEN, e91.correction_done),
        (t("qa_sift_priv_amp"), len(e91.final_key) * 4, MAUVE, e91.pa_done),
    ]
    mini_w = (half_w - 16) // 4
    for si, (slbl, ssize, sclr, sdone) in enumerate(e91_stages):
        sx = right_x + si * (mini_w + 2)
        pygame.draw.rect(screen, PANEL_BG, (sx, e91_pipe_y, mini_w - 2, 28), border_radius=4)
        bdr = sclr if sdone else OVERLAY
        pygame.draw.rect(screen, bdr, (sx, e91_pipe_y, mini_w - 2, 28), 1, border_radius=4)
        ls = font.render(slbl, True, sclr if sdone else SUBTEXT_CLR)
        screen.blit(ls, (sx + (mini_w - 2) // 2 - ls.get_width() // 2, e91_pipe_y + 2))
        bs = font.render(f"{ssize}b", True, TEXT_CLR if sdone else SUBTEXT_CLR)
        screen.blit(bs, (sx + (mini_w - 2) // 2 - bs.get_width() // 2, e91_pipe_y + 15))

    if e91.pa_done and e91.final_key:
        fk_y = e91_pipe_y + 30
        fk_txt = font.render(f"Key: {e91.final_key[:16]}...", True, GREEN)
        screen.blit(fk_txt, (right_x, fk_y))

    # ── 하단 비교 요약 패널 ──
    panel_y = max(graph_y + 108, 340)
    pygame.draw.rect(screen, PANEL_BG, (20, panel_y, WIDTH - 40, 170), border_radius=8)
    pygame.draw.rect(screen, OVERLAY, (20, panel_y, WIDTH - 40, 170), 1, border_radius=8)

    title = big_font.render(t("qa_cmp_summary"), True, ACCENT)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, panel_y + 6))

    # 비교 행
    rows = [
        (t("qa_cmp_row_method"), t("qa_cmp_bb84_method"), t("qa_cmp_e91_method")),
        (t("qa_cmp_row_resource"), t("qa_cmp_bb84_resource"), t("qa_cmp_e91_resource")),
        (t("qa_cmp_row_detect"),
         t("qa_cmp_qber_thresh", pct=bb84.qber * 100, warn="> 11% !" if bb84.qber > 0.11 else "< 11%")
            if bb84.total_rounds > 0 else t("qa_cmp_no_data"),
         t("qa_cmp_bell_thresh", s=e91.bell_S, warn="> 2.0 !" if e91.bell_violated else "≤ 2.0")
            if e91.bell_rounds > 0 else t("qa_cmp_no_data")),
        (t("qa_cmp_row_result"),
         t("qa_cmp_eve_detected") if bb84.eve_detected else t("qa_cmp_secure"),
         t("qa_cmp_bell_secure") if e91.bell_violated else (
             t("qa_cmp_bell_warning") if e91.bell_rounds > 20 else t("qa_cmp_no_data"))),
        (t("qa_cmp_row_keybits"),
         f"{bb84.raw_key_bits}",
         f"{len(e91.raw_key_alice)}"),
    ]

    col_w = (WIDTH - 60) // 3
    ry = panel_y + 26
    for i, (label, bb84_val, e91_val) in enumerate(rows):
        y = ry + i * 16
        screen.blit(font.render(label, True, ACCENT), (30, y))
        screen.blit(font.render(bb84_val, True, BLUE), (30 + col_w, y))
        screen.blit(font.render(e91_val, True, MAUVE), (30 + col_w * 2, y))

    # 프로토콜 특성 비교 메모
    note_y = ry + len(rows) * 16 + 8
    notes = [
        t("qa_cmp_note_bb84"),
        t("qa_cmp_note_e91"),
    ]
    for i, note in enumerate(notes):
        screen.blit(font.render(note, True, SUBTEXT_CLR), (30, note_y + i * 14))

    # 프로토콜 스펙트럼 레이더 차트 (충분한 데이터 후)
    if e91.total_rounds > 50 and bb84.total_rounds > 50:
        _draw_spectrum_chart(screen, bb84, e91, font, big_font)

    # 프로토콜 승자 하이라이트 (충분한 라운드 후)
    min_rounds = 100
    if e91.total_rounds > min_rounds and bb84.total_rounds > min_rounds:
        if e91.bell_violated and not bb84.eve_detected:
            winner_txt = t("qa_toast_winner_e91")
            winner_clr = MAUVE
        else:
            winner_txt = t("qa_toast_winner_tie")
            winner_clr = GREEN
        win_y = note_y + len(notes) * 14 + 6
        win_surf = big_font.render(winner_txt, True, winner_clr)
        wx = WIDTH // 2 - win_surf.get_width() // 2
        pygame.draw.rect(screen, PANEL_BG, (wx - 8, win_y - 2,
                         win_surf.get_width() + 16, 20), border_radius=4)
        pygame.draw.rect(screen, winner_clr, (wx - 8, win_y - 2,
                         win_surf.get_width() + 16, 20), 2, border_radius=4)
        screen.blit(win_surf, (wx, win_y))


def _draw_spectrum_chart(screen, bb84: BB84State, e91: E91State,
                         font, big_font):
    """BB84 vs E91 레이더 차트 — 5축 비교."""
    cx, cy = WIDTH // 2, 530
    radius = 42
    n_axes = 5

    # 5축 메트릭 계산 (0~100 스케일)
    bb84_qber_score = max(0, 100 * (1 - bb84.qber / 0.25)) if bb84.total_rounds > 0 else 50
    e91_qber_score = max(0, 100 * (1 - e91.qber_value / 0.25)) if e91.qber_done else 50

    bb84_key_rate = (bb84.basis_match_rounds / max(bb84.total_rounds, 1)) * 100
    e91_key_rate = (e91.key_rounds / max(e91.total_rounds, 1)) * 100

    bb84_eve_resist = 100 * (1 - bb84.eve_rounds / max(bb84.total_rounds, 1))
    e91_eve_resist = 100 * (1 - e91.eve_rounds / max(e91.total_rounds, 1))

    e91_bell_score = min(100, abs(e91.bell_S) / CHSH_QUANTUM_BOUND * 100)
    bb84_detect_score = min(100, bb84.raw_key_bits / max(bb84.total_rounds, 1) * 200)
    e91_detect_score = min(100, len(e91.raw_key_alice) / max(e91.total_rounds, 1) * 200)

    labels = ["QBER", "Key Rate", "Eve Resist", "Detection", "Security"]
    bb84_vals = [bb84_qber_score, bb84_key_rate, bb84_eve_resist,
                 bb84_detect_score, 80 if bb84.eve_detected else 50]
    e91_vals = [e91_qber_score, e91_key_rate, e91_eve_resist,
                e91_detect_score, e91_bell_score]

    # 축 그리기
    angles = []
    for i in range(n_axes):
        angle = -math.pi / 2 + i * 2 * math.pi / n_axes
        angles.append(angle)
        ex = cx + int(radius * math.cos(angle))
        ey = cy + int(radius * math.sin(angle))
        pygame.draw.line(screen, OVERLAY, (cx, cy), (ex, ey), 1)
        # 축 라벨
        lx = cx + int((radius + 14) * math.cos(angle))
        ly = cy + int((radius + 14) * math.sin(angle))
        lbl = font.render(labels[i], True, SUBTEXT_CLR)
        screen.blit(lbl, (lx - lbl.get_width() // 2, ly - 5))

    # 외곽 오각형
    outer_pts = [(cx + int(radius * math.cos(a)),
                  cy + int(radius * math.sin(a))) for a in angles]
    pygame.draw.polygon(screen, OVERLAY, outer_pts, 1)

    # BB84 폴리곤 (BLUE)
    bb84_pts = []
    for i, a in enumerate(angles):
        r = radius * min(bb84_vals[i], 100) / 100
        bb84_pts.append((cx + int(r * math.cos(a)), cy + int(r * math.sin(a))))
    if len(bb84_pts) >= 3:
        bb84_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.polygon(bb84_surf, (*BLUE[:3], 50), bb84_pts)
        pygame.draw.polygon(bb84_surf, BLUE, bb84_pts, 2)
        screen.blit(bb84_surf, (0, 0))

    # E91 폴리곤 (MAUVE)
    e91_pts = []
    for i, a in enumerate(angles):
        r = radius * min(e91_vals[i], 100) / 100
        e91_pts.append((cx + int(r * math.cos(a)), cy + int(r * math.sin(a))))
    if len(e91_pts) >= 3:
        e91_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.polygon(e91_surf, (*MAUVE[:3], 50), e91_pts)
        pygame.draw.polygon(e91_surf, MAUVE, e91_pts, 2)
        screen.blit(e91_surf, (0, 0))

    # 범례
    pygame.draw.line(screen, BLUE, (cx - 50, cy + radius + 22),
                     (cx - 36, cy + radius + 22), 2)
    screen.blit(font.render("BB84", True, BLUE),
                (cx - 34, cy + radius + 17))
    pygame.draw.line(screen, MAUVE, (cx + 10, cy + radius + 22),
                     (cx + 24, cy + radius + 22), 2)
    screen.blit(font.render("E91", True, MAUVE),
                (cx + 26, cy + radius + 17))


def _draw_qber_meter(screen, qber, x, y, w, font, big_font):
    """QBER 바 미터."""
    h = 14
    pygame.draw.rect(screen, PANEL_BG, (x, y, w, h))
    # 11% 임계선
    thresh_x = x + int(w * 0.11)
    pygame.draw.line(screen, YELLOW, (thresh_x, y - 2), (thresh_x, y + h + 2), 2)
    lbl = font.render("11%", True, YELLOW)
    screen.blit(lbl, (thresh_x - 8, y + h + 3))
    # 채움
    fill_w = min(int(w * min(qber, 1.0)), w)
    fill_clr = RED if qber > 0.11 else GREEN
    if fill_w > 0:
        pygame.draw.rect(screen, fill_clr, (x, y, fill_w, h))
    pygame.draw.rect(screen, TEXT_CLR, (x, y, w, h), 1)
    # 값 표시 + 색각 보조 마커
    status_sym = "!!" if qber > 0.11 else "OK"
    val = big_font.render(f"QBER {qber * 100:.1f}% [{status_sym}]", True, TEXT_CLR)
    screen.blit(val, (x + w + 8, y))


def _draw_bell_meter(screen, bell_s, x, y, w, font, big_font):
    """Bell S 바 미터."""
    h = 14
    pygame.draw.rect(screen, PANEL_BG, (x, y, w, h))
    # 고전 한계 마커 (S=2)
    cl_x = x + int(w * CHSH_CLASSICAL_BOUND / 3.0)
    pygame.draw.line(screen, YELLOW, (cl_x, y - 2), (cl_x, y + h + 2), 2)
    lbl = font.render("2.0", True, YELLOW)
    screen.blit(lbl, (cl_x - 8, y + h + 3))
    # 채움
    s_ratio = min(abs(bell_s) / 3.0, 1.0)
    fill_w = int(w * s_ratio)
    fill_clr = GREEN if abs(bell_s) > CHSH_CLASSICAL_BOUND else RED
    if fill_w > 0:
        pygame.draw.rect(screen, fill_clr, (x, y, fill_w, h))
    pygame.draw.rect(screen, TEXT_CLR, (x, y, w, h), 1)
    # 값 표시 + 색각 보조 마커
    status_sym = "OK" if abs(bell_s) > CHSH_CLASSICAL_BOUND else "!!"
    val = big_font.render(f"S = {abs(bell_s):.3f} [{status_sym}]", True, TEXT_CLR)
    screen.blit(val, (x + w + 8, y))


def _draw_qber_graph(screen, history, x, y, w, h, font, big_font):
    """BB84 QBER 시계열 수렴 그래프.

    Args:
        history: list of (round_number, qber_value) tuples.
    """
    # 패널 배경
    pygame.draw.rect(screen, PANEL_BG, (x, y, w, h), border_radius=6)
    pygame.draw.rect(screen, OVERLAY, (x, y, w, h), 1, border_radius=6)

    # 제목
    title = big_font.render(t("qa_qber_graph"), True, ACCENT)
    screen.blit(title, (x + 6, y + 4))

    # 그래프 영역
    pad_l, pad_r, pad_t, pad_b = 38, 8, 22, 18
    gx = x + pad_l
    gy = y + pad_t
    gw = w - pad_l - pad_r
    gh = h - pad_t - pad_b

    if gw < 10 or gh < 10:
        return

    # Y축 범위: 0 ~ 0.5 (50%)
    y_min, y_max = 0.0, 0.5

    def _val_to_py(val):
        ratio = (val - y_min) / (y_max - y_min)
        return gy + gh - int(ratio * gh)

    def _round_to_px(rd_idx, total):
        if total <= 1:
            return gx + gw // 2
        return gx + int(rd_idx / (total - 1) * gw)

    # Y축 그리드 & 라벨
    for val in (0.0, 0.1, 0.2, 0.3, 0.5):
        py = _val_to_py(val)
        pygame.draw.line(screen, OVERLAY, (gx, py), (gx + gw, py), 1)
        lbl = font.render(f"{val * 100:.0f}%", True, SUBTEXT_CLR)
        screen.blit(lbl, (gx - lbl.get_width() - 3, py - 5))

    # 11% 임계선 (빨강 점선)
    thresh_py = _val_to_py(0.11)
    for dx in range(0, gw, 8):
        x1 = gx + dx
        x2 = min(gx + dx + 4, gx + gw)
        pygame.draw.line(screen, YELLOW, (x1, thresh_py), (x2, thresh_py), 1)
    lbl = font.render("11%", True, YELLOW)
    screen.blit(lbl, (gx + gw - lbl.get_width(), thresh_py - 12))

    # 데이터가 없으면 안내
    if not history:
        msg = font.render(t("qa_qber_nodata"), True, SUBTEXT_CLR)
        screen.blit(msg, (gx + gw // 2 - msg.get_width() // 2,
                          gy + gh // 2 - 5))
        return

    # 데이터 포인트를 픽셀로 변환
    n = len(history)
    points = []
    for i, (_rd, q_val) in enumerate(history):
        px = _round_to_px(i, n)
        py = _val_to_py(min(q_val, y_max))
        points.append((px, py))

    # 라인 플롯
    if len(points) >= 2:
        pygame.draw.lines(screen, BLUE, False, points, 2)

    # 최신 포인트 강조
    if points:
        last = points[-1]
        pygame.draw.circle(screen, WHITE, last, 3)

    # X축 라벨
    first_rd = history[0][0]
    last_rd = history[-1][0]
    fl = font.render(f"R{first_rd}", True, SUBTEXT_CLR)
    screen.blit(fl, (gx, gy + gh + 3))
    ll = font.render(f"R{last_rd}", True, SUBTEXT_CLR)
    screen.blit(ll, (gx + gw - ll.get_width(), gy + gh + 3))


def _draw_bell_s_graph(screen, history, x, y, w, h, font, big_font):
    """Bell S 시계열 수렴 그래프.

    Args:
        history: list of (round_number, S_value) tuples.
    """
    # 패널 배경
    pygame.draw.rect(screen, PANEL_BG, (x, y, w, h), border_radius=6)
    pygame.draw.rect(screen, OVERLAY, (x, y, w, h), 1, border_radius=6)

    # 제목
    title = big_font.render(t("qa_bell_s_graph"), True, ACCENT)
    screen.blit(title, (x + 6, y + 4))

    # 그래프 영역 (패딩)
    pad_l, pad_r, pad_t, pad_b = 38, 8, 22, 18
    gx = x + pad_l
    gy = y + pad_t
    gw = w - pad_l - pad_r
    gh = h - pad_t - pad_b

    if gw < 10 or gh < 10:
        return

    # Y축 범위: 0 ~ 3.0
    y_min, y_max = 0.0, 3.0

    def _val_to_py(val):
        """S 값 → 픽셀 Y 좌표."""
        ratio = (val - y_min) / (y_max - y_min)
        return gy + gh - int(ratio * gh)

    def _round_to_px(rd_idx, total):
        """히스토리 인덱스 → 픽셀 X 좌표."""
        if total <= 1:
            return gx + gw // 2
        return gx + int(rd_idx / (total - 1) * gw)

    # Y축 그리드 & 라벨
    for val in (0.0, 1.0, 2.0, 3.0):
        py = _val_to_py(val)
        pygame.draw.line(screen, OVERLAY, (gx, py), (gx + gw, py), 1)
        lbl = font.render(f"{val:.0f}", True, SUBTEXT_CLR)
        screen.blit(lbl, (gx - lbl.get_width() - 3, py - 5))

    # 고전 한계선 S = 2.0 (빨강 점선 느낌)
    cl_py = _val_to_py(CHSH_CLASSICAL_BOUND)
    for dx in range(0, gw, 8):
        x1 = gx + dx
        x2 = min(gx + dx + 4, gx + gw)
        pygame.draw.line(screen, YELLOW, (x1, cl_py), (x2, cl_py), 1)
    lbl = font.render("S=2", True, YELLOW)
    screen.blit(lbl, (gx + gw - lbl.get_width(), cl_py - 12))

    # 양자 한계선 S = 2√2 ≈ 2.828
    ql_py = _val_to_py(CHSH_QUANTUM_BOUND)
    for dx in range(0, gw, 8):
        x1 = gx + dx
        x2 = min(gx + dx + 4, gx + gw)
        pygame.draw.line(screen, MAUVE, (x1, ql_py), (x2, ql_py), 1)
    lbl = font.render("2√2", True, MAUVE)
    screen.blit(lbl, (gx + gw - lbl.get_width(), ql_py + 2))

    # 데이터가 없으면 안내
    if not history:
        msg = font.render(t("qa_bell_s_nodata"), True, SUBTEXT_CLR)
        screen.blit(msg, (gx + gw // 2 - msg.get_width() // 2,
                          gy + gh // 2 - 5))
        return

    # 데이터 포인트를 픽셀로 변환
    n = len(history)
    points = []
    for i, (_rd, s_val) in enumerate(history):
        px = _round_to_px(i, n)
        py = _val_to_py(min(abs(s_val), y_max))
        points.append((px, py))

    # 라인 플롯
    if len(points) >= 2:
        pygame.draw.lines(screen, GREEN, False, points, 2)

    # 최신 포인트 강조
    if points:
        last = points[-1]
        pygame.draw.circle(screen, WHITE, last, 3)

    # X축 라벨 (첫/마지막 라운드)
    first_rd = history[0][0]
    last_rd = history[-1][0]
    fl = font.render(f"R{first_rd}", True, SUBTEXT_CLR)
    screen.blit(fl, (gx, gy + gh + 3))
    ll = font.render(f"R{last_rd}", True, SUBTEXT_CLR)
    screen.blit(ll, (gx + gw - ll.get_width(), gy + gh + 3))


def _draw_consistency_graph(screen, history, x, y, w, h, font, big_font):
    """GHZ 일관성 패스율 시계열 수렴 그래프.

    Args:
        history: list of (round_number, pass_rate) tuples.
    """
    # 패널 배경
    pygame.draw.rect(screen, PANEL_BG, (x, y, w, h), border_radius=6)
    pygame.draw.rect(screen, OVERLAY, (x, y, w, h), 1, border_radius=6)

    # 제목
    title = big_font.render(t("qa_ghz_consistency_graph"), True, ACCENT)
    screen.blit(title, (x + 6, y + 4))

    # 그래프 영역
    pad_l, pad_r, pad_t, pad_b = 38, 8, 22, 18
    gx = x + pad_l
    gy = y + pad_t
    gw = w - pad_l - pad_r
    gh = h - pad_t - pad_b

    if gw < 10 or gh < 10:
        return

    # Y축 범위: 0 ~ 1.0 (100%)
    y_min, y_max = 0.0, 1.0

    def _val_to_py(val):
        ratio = (val - y_min) / (y_max - y_min)
        return gy + gh - int(ratio * gh)

    def _round_to_px(rd_idx, total):
        if total <= 1:
            return gx + gw // 2
        return gx + int(rd_idx / (total - 1) * gw)

    # Y축 그리드 & 라벨
    for val in (0.0, 0.25, 0.5, 0.75, 1.0):
        py = _val_to_py(val)
        pygame.draw.line(screen, OVERLAY, (gx, py), (gx + gw, py), 1)
        lbl = font.render(f"{val * 100:.0f}%", True, SUBTEXT_CLR)
        screen.blit(lbl, (gx - lbl.get_width() - 3, py - 5))

    # 85% 임계선 (안전 기준)
    thresh_py = _val_to_py(0.85)
    for dx in range(0, gw, 8):
        x1 = gx + dx
        x2 = min(gx + dx + 4, gx + gw)
        pygame.draw.line(screen, YELLOW, (x1, thresh_py), (x2, thresh_py), 1)
    lbl = font.render("85%", True, YELLOW)
    screen.blit(lbl, (gx + gw - lbl.get_width(), thresh_py - 12))

    # 데이터가 없으면 안내
    if not history:
        msg = font.render(t("qa_ghz_consistency_nodata"), True, SUBTEXT_CLR)
        screen.blit(msg, (gx + gw // 2 - msg.get_width() // 2,
                          gy + gh // 2 - 5))
        return

    # 데이터 포인트를 픽셀로 변환
    n = len(history)
    points = []
    for i, (_rd, p_val) in enumerate(history):
        px = _round_to_px(i, n)
        py = _val_to_py(min(p_val, y_max))
        points.append((px, py))

    # 라인 플롯
    if len(points) >= 2:
        pygame.draw.lines(screen, GREEN, False, points, 2)

    # 최신 포인트 강조
    if points:
        last = points[-1]
        pygame.draw.circle(screen, WHITE, last, 3)

    # X축 라벨
    first_rd = history[0][0]
    last_rd = history[-1][0]
    fl = font.render(f"R{first_rd}", True, SUBTEXT_CLR)
    screen.blit(fl, (gx, gy + gh + 3))
    ll = font.render(f"R{last_rd}", True, SUBTEXT_CLR)
    screen.blit(ll, (gx + gw - ll.get_width(), gy + gh + 3))


def _draw_key_accumulation(screen, history, x, y, w, h, font, big_font):
    """누적 키 생성 차트."""
    title = _tcache.render(font, "Key Accumulation", ACCENT)
    screen.blit(title, (x, y))
    gx, gy = x, y + 16
    gw, gh = w, h - 16
    pygame.draw.rect(screen, PANEL_BG, (gx, gy, gw, gh), border_radius=4)
    pygame.draw.rect(screen, OVERLAY, (gx, gy, gw, gh), 1, border_radius=4)

    if len(history) < 2:
        return

    max_bits = max(h[1] for h in history)
    if max_bits == 0:
        return

    points = []
    for rd, bits in history:
        px = gx + int((rd - history[0][0]) / max(history[-1][0] - history[0][0], 1) * gw)
        py = gy + gh - int(bits / max_bits * (gh - 4)) - 2
        points.append((px, py))

    if len(points) >= 2:
        pygame.draw.lines(screen, GREEN, False, points, 2)

    cnt = font.render(f"{max_bits}b", True, GREEN)
    screen.blit(cnt, (gx + gw - cnt.get_width() - 4, gy + 2))


# ── 통계 내보내기 ─────────────────────────────────────

def _export_stats(mode, e91, ghz, bb84_cmp, e91_cmp):
    """현재 시뮬레이션 통계를 JSON 파일로 내보내기."""
    import json
    import os
    from datetime import datetime

    data = {
        "timestamp": datetime.now().isoformat(),
        "mode": ["E91", "Sift", "GHZ", "Compare"][mode],
        "e91": {
            "total_rounds": e91.total_rounds,
            "key_rounds": e91.key_rounds,
            "bell_rounds": e91.bell_rounds,
            "bell_S": round(e91.bell_S, 4),
            "raw_key_len": len(e91.raw_key_alice),
            "final_key": e91.final_key[:32] if e91.final_key else "",
            "qber_value": round(e91.qber_value, 4),
            "pa_done": e91.pa_done,
        },
        "ghz": {
            "n_parties": ghz.n_parties,
            "total_rounds": ghz.total_rounds,
            "consistency_rate": round(ghz.consistency_pass / max(ghz.consistency_checks, 1), 4),
            "final_key": ghz.final_key[:32] if ghz.final_key else "",
            "pa_done": ghz.pa_done,
        },
        "compare_bb84": {
            "total_rounds": bb84_cmp.total_rounds,
            "raw_key_bits": bb84_cmp.raw_key_bits,
            "qber": round(bb84_cmp.qber, 4),
            "final_key": bb84_cmp.final_key[:32] if bb84_cmp.final_key else "",
            "pa_done": bb84_cmp.pa_done,
        },
        "compare_e91": {
            "total_rounds": e91_cmp.total_rounds,
            "bell_S": round(e91_cmp.bell_S, 4),
            "raw_key_len": len(e91_cmp.raw_key_alice),
            "final_key": e91_cmp.final_key[:32] if e91_cmp.final_key else "",
            "pa_done": e91_cmp.pa_done,
        },
    }
    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "exports")
    os.makedirs(export_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(export_dir, f"qkd_stats_{ts}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _show_session_summary(screen, font, big_font, mode, e91, ghz, bb84_cmp, e91_cmp):
    """세션 요약 표시. True=종료, False=계속."""
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))

    pw, ph = 340, 200
    px = WIDTH // 2 - pw // 2
    py = HEIGHT // 2 - ph // 2
    pygame.draw.rect(screen, PANEL_BG, (px, py, pw, ph), border_radius=8)
    pygame.draw.rect(screen, ACCENT, (px, py, pw, ph), 2, border_radius=8)

    title = big_font.render(t("qa_summary_title"), True, ACCENT)
    screen.blit(title, (px + pw // 2 - title.get_width() // 2, py + 10))

    mode_name = t(_MODE_KEYS[mode])
    cur_e91 = e91 if mode in (MODE_E91, MODE_SIFT) else e91_cmp
    lines = [
        (f"Mode: {mode_name}", TEXT_CLR),
        (t("qa_summary_rounds", n=cur_e91.total_rounds + (ghz.total_rounds if mode == MODE_GHZ else 0)), TEXT_CLR),
        (t("qa_summary_keybits", n=len(cur_e91.raw_key_alice) if mode != MODE_GHZ else len(ghz.raw_keys[0])), BLUE),
        (t("qa_summary_bells", s=cur_e91.bell_S), GREEN if cur_e91.bell_violated else RED),
        (t("qa_summary_qber", pct=cur_e91.qber_value * 100), GREEN if cur_e91.qber_value < 0.11 else RED),
    ]
    if cur_e91.final_key:
        lines.append((f"Final Key: {cur_e91.final_key[:20]}...", MAUVE))

    for i, (txt, clr) in enumerate(lines):
        s = font.render(txt, True, clr)
        screen.blit(s, (px + 20, py + 36 + i * 18))

    hint = font.render(t("qa_summary_exit"), True, SUBTEXT_CLR)
    screen.blit(hint, (px + pw // 2 - hint.get_width() // 2, py + ph - 22))

    pygame.display.flip()

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return True
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN:
                    return True
                if ev.key == pygame.K_ESCAPE:
                    return False
        pygame.time.wait(30)


# ── 메인 시뮬레이션 ──────────────────────────────────

def run_simulation():
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(t("game_title_qkd_advanced"))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 11)
    big_font = pygame.font.SysFont("Consolas", 14, bold=True)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)

    mode = MODE_E91
    e91 = E91State()
    ghz = GHZState()
    bb84_cmp = BB84State()
    e91_cmp = E91State()
    anim_t = 0.0
    paused = False
    auto_run = False
    auto_timer = 0.0
    eve_chance = 0.0

    show_shortcuts = False
    show_fps = False
    auto_speed = 1.0  # 0.5x, 1x, 2x, 4x
    _AUTO_SPEEDS = [0.5, 1.0, 2.0, 4.0]
    _fade_timer = 0.0  # 모드 전환 페이드 (0=없음, >0=진행중)
    _ghz_flash_timer = 0.0  # GHZ 측정 플래시 타이머
    _ghz_prev_rounds = 0  # GHZ 라운드 변화 감지용
    noise_model = "depolarizing"  # 양자 노이즈 모델
    step_mode = False  # 단계별 학습 모드
    _step_milestone = 0  # 현재 마일스톤 인덱스
    _step_waiting = False  # 마일스톤 도달 → 일시정지 대기

    help_overlay = HelpOverlay("qkd_advanced")
    tutorial = TutorialOverlay("qkd_advanced")
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("qkd_advanced")
    _engine_error: str | None = None  # 엔진 오류 표시용
    _toasts: list[list] = []  # [[text, color, timer], ...]
    _prev_bell_violated = False
    _prev_pa_done = False
    _prev_eve_detected = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        anim_t += dt

        for event in pygame.event.get():
            help_overlay.handle_event(event)
            if tutorial.handle_event(event):
                continue
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                snd.handle_key(event.key)
                if event.key == pygame.K_ESCAPE:
                    if _show_session_summary(screen, font, big_font,
                                             mode, e91, ghz, bb84_cmp, e91_cmp):
                        running = False
                elif event.key == pygame.K_TAB:
                    mode = (mode + 1) % NUM_MODES
                    _fade_timer = 0.15
                elif event.key == pygame.K_SPACE:
                    if _step_waiting:
                        _step_waiting = False
                        paused = False
                    _engine_error = None
                    try:
                        if mode == MODE_E91:
                            for _ in range(E91_BATCH):
                                e91_round(e91, eve_chance)
                            compute_bell_S(e91)
                        elif mode == MODE_SIFT:
                            if len(e91.raw_key_alice) == 0:
                                for _ in range(CHSH_SHOTS):
                                    e91_round(e91, eve_chance)
                                compute_bell_S(e91)
                            elif not e91.qber_done:
                                estimate_qber(e91)
                            elif not e91.correction_done:
                                error_correct(e91)
                            elif not e91.pa_done:
                                privacy_amplification(e91)
                            else:
                                reset_e91(e91)
                        elif mode == MODE_GHZ:
                            for _ in range(GHZ_BATCH):
                                ghz_round(ghz, eve_chance)
                        elif mode == MODE_COMPARE:
                            for _ in range(E91_BATCH):
                                bb84_round(bb84_cmp, eve_chance)
                                e91_round(e91_cmp, eve_chance)
                            compute_bell_S(e91_cmp)
                    except Exception as exc:
                        _engine_error = str(exc)
                    else:
                        snd.play("preset_change")
                elif event.key == pygame.K_s:
                    _engine_error = None
                    try:
                        if mode in (MODE_E91, MODE_SIFT):
                            if len(e91.raw_key_alice) > 0:
                                key_sift(e91)
                                privacy_amplification(e91)
                        elif mode == MODE_GHZ:
                            ghz_key_sift(ghz)
                            ghz_privacy_amplification(ghz)
                        elif mode == MODE_COMPARE:
                            if len(e91_cmp.raw_key_alice) > 0:
                                key_sift(e91_cmp)
                                privacy_amplification(e91_cmp)
                            if len(bb84_cmp.raw_key) > 0:
                                bb84_estimate_qber(bb84_cmp)
                                bb84_error_correct(bb84_cmp)
                                bb84_privacy_amplification(bb84_cmp)
                    except Exception as exc:
                        _engine_error = str(exc)
                    else:
                        snd.play("achievement")
                elif event.key == pygame.K_r:
                    reset_e91(e91)
                    reset_ghz(ghz)
                    reset_bb84(bb84_cmp)
                    reset_e91(e91_cmp)
                    auto_run = False
                elif event.key == pygame.K_p:
                    paused = not paused
                elif event.key == pygame.K_a:
                    auto_run = not auto_run
                elif event.key == pygame.K_h:
                    step_mode = not step_mode
                    _step_milestone = 0
                    _step_waiting = False
                    if step_mode:
                        auto_run = True
                        _toasts.append([t("qa_step_on"), ACCENT, 2.0])
                    else:
                        _toasts.append([t("qa_step_off"), SUBTEXT_CLR, 2.0])
                elif event.key == pygame.K_RIGHTBRACKET:
                    idx = _AUTO_SPEEDS.index(auto_speed) if auto_speed in _AUTO_SPEEDS else 1
                    auto_speed = _AUTO_SPEEDS[min(idx + 1, len(_AUTO_SPEEDS) - 1)]
                elif event.key == pygame.K_LEFTBRACKET:
                    idx = _AUTO_SPEEDS.index(auto_speed) if auto_speed in _AUTO_SPEEDS else 1
                    auto_speed = _AUTO_SPEEDS[max(idx - 1, 0)]
                elif event.key == pygame.K_F10:
                    show_fps = not show_fps
                elif event.key == pygame.K_F12:
                    _screenshot_dir = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)), "..", "screenshots")
                    os.makedirs(_screenshot_dir, exist_ok=True)
                    from datetime import datetime as _dt
                    _ss_name = f"qkd_{_dt.now().strftime('%Y%m%d_%H%M%S')}.png"
                    _ss_path = os.path.join(_screenshot_dir, _ss_name)
                    pygame.image.save(screen, _ss_path)
                    _toasts.append([t("qa_screenshot", path=_ss_name), GREEN, 2.5])
                elif event.key == pygame.K_e:
                    # Eve 단계별 순환: 0→10→30→50→80→100→0%
                    _EVE_LEVELS = [0.0, 0.1, 0.3, 0.5, 0.8, 1.0]
                    _cur = min(range(len(_EVE_LEVELS)),
                               key=lambda i: abs(_EVE_LEVELS[i] - eve_chance))
                    eve_chance = _EVE_LEVELS[(_cur + 1) % len(_EVE_LEVELS)]
                    snd.play("eve_detected" if eve_chance > 0 else "channel_open")
                elif event.key == pygame.K_n:
                    noise_model = cycle_noise_model()
                    _toasts.append([t("qa_noise_model", model=noise_model), PEACH, 2.0])
                elif event.key == pygame.K_UP and mode == MODE_GHZ:
                    if ghz.n_parties < GHZ_MAX_PARTIES:
                        resize_ghz(ghz, ghz.n_parties + 1)
                elif event.key == pygame.K_DOWN and mode == MODE_GHZ:
                    if ghz.n_parties > GHZ_MIN_PARTIES:
                        resize_ghz(ghz, ghz.n_parties - 1)
                elif event.key == pygame.K_l:
                    toggle_locale()
                    _tcache.clear()
                elif event.key == pygame.K_t:
                    toggle_theme()
                    _load_theme_colors()
                    _tcache.clear()
                elif event.key == pygame.K_SLASH or event.key == pygame.K_QUESTION:
                    show_shortcuts = not show_shortcuts
                elif event.key == pygame.K_x and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    _export_stats(mode, e91, ghz, bb84_cmp, e91_cmp)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # 모드 탭 클릭 처리
                mx, my = event.pos
                tab_y_ = 32
                tab_w_ = min(180, (WIDTH - 60) // NUM_MODES - 8)
                tab_gap_ = (WIDTH - 40 - tab_w_ * NUM_MODES) // max(NUM_MODES - 1, 1)
                if tab_y_ <= my <= tab_y_ + 22:
                    for i in range(NUM_MODES):
                        tx_ = 20 + i * (tab_w_ + tab_gap_)
                        if tx_ <= mx <= tx_ + tab_w_:
                            mode = i
                            _fade_timer = 0.15
                            break
                if mode == MODE_GHZ:
                    # GHZ 파티 수 버튼 클릭 처리
                    mx, my = event.pos
                    btn_x0 = WIDTH - 180
                    btn_y0 = 62 + 18
                    for pn in range(GHZ_MIN_PARTIES, GHZ_MAX_PARTIES + 1):
                        bx = btn_x0 + (pn - GHZ_MIN_PARTIES) * 36
                        if bx <= mx <= bx + 30 and btn_y0 <= my <= btn_y0 + 20:
                            if pn != ghz.n_parties:
                                resize_ghz(ghz, pn)
                            break

        # 자동 실행
        if auto_run and not paused:
            auto_timer += dt
            if auto_timer >= 0.05 / auto_speed:
                auto_timer = 0.0
                try:
                    if mode == MODE_E91:
                        e91_round(e91, eve_chance)
                        if e91.total_rounds % 10 == 0:
                            compute_bell_S(e91)
                    elif mode == MODE_SIFT:
                        e91_round(e91, eve_chance)
                        if e91.total_rounds % 10 == 0:
                            compute_bell_S(e91)
                        if (e91.total_rounds > 0
                                and e91.total_rounds % CHSH_SHOTS == 0
                                and not e91.pa_done):
                            if not e91.qber_done:
                                estimate_qber(e91)
                            elif not e91.correction_done:
                                error_correct(e91)
                            elif not e91.pa_done:
                                privacy_amplification(e91)
                    elif mode == MODE_GHZ:
                        ghz_round(ghz, eve_chance)
                        if (ghz.total_rounds > 0
                                and ghz.total_rounds % GHZ_BATCH == 0
                                and not ghz.pa_done):
                            if not ghz.sift_done:
                                ghz_key_sift(ghz)
                            elif not ghz.pa_done:
                                ghz_privacy_amplification(ghz)
                    elif mode == MODE_COMPARE:
                        bb84_round(bb84_cmp, eve_chance)
                        e91_round(e91_cmp, eve_chance)
                        if e91_cmp.total_rounds % 10 == 0:
                            compute_bell_S(e91_cmp)
                        # E91 자동 파이프라인
                        if (e91_cmp.total_rounds > 0
                                and e91_cmp.total_rounds % CHSH_SHOTS == 0
                                and not e91_cmp.pa_done):
                            if not e91_cmp.qber_done:
                                estimate_qber(e91_cmp)
                            elif not e91_cmp.correction_done:
                                error_correct(e91_cmp)
                            elif not e91_cmp.pa_done:
                                privacy_amplification(e91_cmp)
                        # BB84 자동 파이프라인
                        if (bb84_cmp.total_rounds > 0
                                and bb84_cmp.total_rounds % CHSH_SHOTS == 0
                                and not bb84_cmp.pa_done):
                            if not bb84_cmp.qber_done:
                                bb84_estimate_qber(bb84_cmp)
                            elif not bb84_cmp.correction_done:
                                bb84_error_correct(bb84_cmp)
                            elif not bb84_cmp.pa_done:
                                bb84_privacy_amplification(bb84_cmp)
                except Exception as exc:
                    _engine_error = str(exc)
                    auto_run = False

        # GHZ 측정 플래시 타이머 갱신
        if ghz.total_rounds != _ghz_prev_rounds:
            _ghz_flash_timer = 0.3
            _ghz_prev_rounds = ghz.total_rounds
        if _ghz_flash_timer > 0:
            _ghz_flash_timer = max(0, _ghz_flash_timer - dt)

        # 토스트 이벤트 감지
        _cur_state = e91 if mode in (MODE_E91, MODE_SIFT) else e91_cmp
        _cur_bb84 = bb84_cmp
        if _cur_state.bell_violated and not _prev_bell_violated:
            _toasts.append([t("qa_toast_bell"), GREEN, 2.0])
        _prev_bell_violated = _cur_state.bell_violated
        if _cur_state.pa_done and not _prev_pa_done:
            _toasts.append([t("qa_toast_pa"), MAUVE, 2.0])
        _prev_pa_done = _cur_state.pa_done
        if mode == MODE_COMPARE and _cur_bb84.eve_detected and not _prev_eve_detected:
            _toasts.append([t("qa_toast_eve"), RED, 2.0])
        _prev_eve_detected = _cur_bb84.eve_detected if mode == MODE_COMPARE else False

        # 토스트 타이머 감소
        for toast in _toasts:
            toast[2] -= dt
        _toasts = [t_ for t_ in _toasts if t_[2] > 0]

        # 단계별 모드 마일스톤 감지
        if step_mode and not _step_waiting:
            _milestones = [
                (0, lambda: e91.key_rounds >= 1, "qa_step_first_key"),
                (1, lambda: e91.bell_violated, "qa_step_bell_violated"),
                (2, lambda: e91.qber_done, "qa_step_qber_done"),
                (3, lambda: e91.correction_done, "qa_step_ec_done"),
                (4, lambda: e91.pa_done, "qa_step_pa_done"),
            ]
            for mi, (idx, cond, key) in enumerate(_milestones):
                if mi == _step_milestone and cond():
                    paused = True
                    _step_waiting = True
                    _step_milestone = mi + 1
                    _toasts.append([t(key), ACCENT, 4.0])
                    break

        # SPACE가 눌리면 step_waiting 해제 (이미 핸들러에서 처리)
        # _step_waiting은 SPACE 처리 후 자동 해제

        # 리플레이 기록
        if not paused:
            frame = {
                "mode": mode,
                "e91_rounds": e91.total_rounds,
                "e91_bell_S": e91.bell_S,
                "e91_eve_rounds": e91.eve_rounds,
                "e91_key_rounds": e91.key_rounds,
                "ghz_rounds": ghz.total_rounds,
                "ghz_sift_done": ghz.sift_done,
                "ghz_pa_done": ghz.pa_done,
                "eve_chance": eve_chance,
            }
            if mode == MODE_COMPARE:
                frame["bb84_rounds"] = bb84_cmp.total_rounds
                frame["bb84_qber"] = bb84_cmp.qber
                frame["bb84_eve_detected"] = bb84_cmp.eve_detected
                frame["bb84_basis_match"] = bb84_cmp.basis_match_rounds
                frame["bb84_raw_key_bits"] = bb84_cmp.raw_key_bits
                frame["e91_cmp_rounds"] = e91_cmp.total_rounds
                frame["e91_cmp_bell_S"] = e91_cmp.bell_S
                frame["e91_cmp_bell_violated"] = e91_cmp.bell_violated
                frame["e91_cmp_key_rounds"] = e91_cmp.key_rounds
                frame["e91_cmp_eve_rounds"] = e91_cmp.eve_rounds
            recorder.record(frame)

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        title = title_font.render(t("game_title_qkd_advanced"), True, ACCENT)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 8))

        # 모드 탭
        tab_y = 32
        tab_w = min(180, (WIDTH - 60) // NUM_MODES - 8)
        tab_gap = (WIDTH - 40 - tab_w * NUM_MODES) // max(NUM_MODES - 1, 1)
        for i, mk in enumerate(_MODE_KEYS):
            name = t(mk)
            tx = 20 + i * (tab_w + tab_gap)
            active = i == mode
            clr = ACCENT if active else SUBTEXT_CLR
            pygame.draw.rect(screen, PANEL_BG if active else BG,
                             (tx, tab_y, tab_w, 22), border_radius=4)
            if active:
                pygame.draw.rect(screen, clr, (tx, tab_y, tab_w, 22), 2, border_radius=4)
            tab_lbl = big_font.render(name, True, clr)
            screen.blit(tab_lbl, (tx + tab_w // 2 - tab_lbl.get_width() // 2, tab_y + 3))

        # Eve 상태 + 레벨 표시
        eve_txt = t("qa_eve_on", pct=eve_chance * 100) if eve_chance > 0 else t("qa_eve_off")
        eve_surf = font.render(eve_txt, True, RED if eve_chance > 0 else SUBTEXT_CLR)
        eve_tx = WIDTH - eve_surf.get_width() - 10
        screen.blit(eve_surf, (eve_tx, 36))
        # 레벨 스텝 인디케이터 (E 키 순환 가이드 + 호버 툴팁)
        _eve_steps = [0.0, 0.1, 0.3, 0.5, 0.8, 1.0]
        _eve_labels = ["0%", "10%", "30%", "50%", "80%", "100%"]
        step_x = eve_tx - len(_eve_steps) * 8 - 6
        mx, my = pygame.mouse.get_pos()
        eve_tooltip = None
        for si, sv in enumerate(_eve_steps):
            sx = step_x + si * 8
            active = abs(eve_chance - sv) < 0.01
            hovered = sx <= mx <= sx + 6 and 34 <= my <= 52
            clr = RED if active else (TEXT_CLR if hovered else OVERLAY)
            pygame.draw.rect(screen, clr, (sx, 40, 6, 6), 0 if active else 1)
            if hovered:
                eve_tooltip = (sx, _eve_labels[si])
        if eve_tooltip:
            tip_surf = font.render(f"Eve {eve_tooltip[1]}", True, TEXT_CLR)
            tip_bg = pygame.Rect(eve_tooltip[0] - 4, 50, tip_surf.get_width() + 8, 14)
            pygame.draw.rect(screen, PANEL_BG, tip_bg, border_radius=3)
            pygame.draw.rect(screen, OVERLAY, tip_bg, 1, border_radius=3)
            screen.blit(tip_surf, (eve_tooltip[0], 51))

        # 모드별 렌더링
        if mode == MODE_E91:
            _draw_e91_mode(screen, e91, anim_t, font, big_font)
        elif mode == MODE_SIFT:
            _draw_sift_mode(screen, e91, anim_t, font, big_font)
        elif mode == MODE_GHZ:
            _draw_ghz_mode(screen, ghz, anim_t, font, big_font, _ghz_flash_timer)
        elif mode == MODE_COMPARE:
            _draw_compare_mode(screen, bb84_cmp, e91_cmp, font, big_font)

        # 모드 전환 페이드
        if _fade_timer > 0:
            _fade_timer = max(0, _fade_timer - dt)
            alpha = int((_fade_timer / 0.15) * 120)
            fade_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fade_surf.fill((0, 0, 0, alpha))
            screen.blit(fade_surf, (0, 0))

        # 자동 실행 단계 표시
        auto_stage = ""
        if auto_run and not paused:
            if mode == MODE_SIFT:
                if e91.pa_done:
                    auto_stage = t("qa_stage_done")
                elif e91.correction_done:
                    auto_stage = t("qa_stage_pa")
                elif e91.qber_done:
                    auto_stage = t("qa_stage_ec")
                else:
                    auto_stage = t("qa_stage_rounds")
            elif mode == MODE_GHZ:
                if ghz.pa_done:
                    auto_stage = t("qa_stage_done")
                elif ghz.sift_done:
                    auto_stage = t("qa_stage_pa")
                else:
                    auto_stage = t("qa_stage_rounds")
            elif mode == MODE_COMPARE:
                if e91_cmp.pa_done:
                    auto_stage = t("qa_stage_done")
                elif e91_cmp.correction_done:
                    auto_stage = t("qa_stage_pa")
                elif e91_cmp.qber_done:
                    auto_stage = t("qa_stage_ec")
                else:
                    auto_stage = t("qa_stage_rounds")
            else:
                auto_stage = t("qa_stage_rounds")

        auto_label = t("auto_on") if auto_run else t("auto_off")
        if auto_stage:
            auto_label = f"{auto_label} [{auto_stage}]"

        # 자동 파이프라인 진행 바
        if auto_run and not paused and mode in (MODE_SIFT, MODE_GHZ, MODE_COMPARE):
            bar_w, bar_h = 200, 6
            bar_x = WIDTH // 2 - bar_w // 2
            bar_y = HEIGHT - 52
            pygame.draw.rect(screen, OVERLAY, (bar_x, bar_y, bar_w, bar_h), border_radius=3)
            seg_w = bar_w // 4
            if mode == MODE_SIFT:
                _steps = [len(e91.raw_key_alice) > 0, e91.qber_done,
                          e91.correction_done, e91.pa_done]
            elif mode == MODE_GHZ:
                _steps = [len(ghz.raw_keys[0]) > 0, ghz.sift_done,
                          ghz.pa_done, ghz.pa_done]
            else:
                _steps = [len(e91_cmp.raw_key_alice) > 0, e91_cmp.qber_done,
                          e91_cmp.correction_done, e91_cmp.pa_done]
            _seg_clrs = [BLUE, YELLOW, GREEN, MAUVE]
            for si, (done, clr) in enumerate(zip(_steps, _seg_clrs)):
                if done:
                    sx = bar_x + si * seg_w
                    pygame.draw.rect(screen, clr,
                                     (sx, bar_y, seg_w - 2, bar_h), border_radius=3)

        # 안내
        hints = [
            t("qa_hint_line1",
              auto=auto_label,
              pause=t("paused") if paused else t("running_state")),
            t("qa_hint_line2"),
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 36 + i * 16))

        # 자동 실행 속도 표시 (1x 이외일 때)
        if auto_speed != 1.0:
            spd_txt = font.render(t("qa_auto_speed", speed=auto_speed), True, PEACH)
            screen.blit(spd_txt, (10, HEIGHT - 14))

        # 노이즈 모델 표시
        nm = get_noise_model()
        nm_txt = font.render(t("qa_noise_label", model=nm), True, PEACH)
        screen.blit(nm_txt, (10, 10))

        # 단계별 모드 표시
        if step_mode:
            step_txt = font.render(t("qa_step_active"), True, ACCENT)
            screen.blit(step_txt, (10, 22))

        # FPS 카운터
        if show_fps:
            fps_val = int(clock.get_fps())
            fps_surf = font.render(t("qa_fps_counter", fps=fps_val), True, SUBTEXT_CLR)
            screen.blit(fps_surf, (WIDTH - fps_surf.get_width() - 10, HEIGHT - 14))

        # 일시정지 오버레이
        if paused:
            pause_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pause_overlay.fill((0, 0, 0, 80))
            screen.blit(pause_overlay, (0, 0))
            pause_txt = big_font.render(t("qa_paused_banner"), True, ACCENT)
            ptx = WIDTH // 2 - pause_txt.get_width() // 2
            pty = HEIGHT // 2 - 10
            pause_bg = pygame.Rect(ptx - 16, pty - 4,
                                   pause_txt.get_width() + 32, 24)
            pygame.draw.rect(screen, PANEL_BG, pause_bg, border_radius=6)
            pygame.draw.rect(screen, ACCENT, pause_bg, 2, border_radius=6)
            screen.blit(pause_txt, (ptx, pty))

        # 엔진 오류 배너
        if _engine_error:
            err_surf = font.render(f"Engine error: {_engine_error[:60]}", True, BG)
            err_bg = pygame.Rect(WIDTH // 2 - err_surf.get_width() // 2 - 6,
                                 HEIGHT // 2 - 12, err_surf.get_width() + 12, 20)
            pygame.draw.rect(screen, RED, err_bg, border_radius=4)
            screen.blit(err_surf, (err_bg.x + 6, err_bg.y + 3))

        # 키보드 단축키 치트시트 (? 토글)
        if show_shortcuts:
            _sc_lines = [
                t("qa_sc_title"),
                "",
                f"SPACE   {t('qa_sc_space')}",
                f"S       {t('qa_sc_sift')}",
                f"A       {t('qa_sc_auto')}",
                f"E       {t('qa_sc_eve')}",
                f"P       {t('qa_sc_pause')}",
                f"R       {t('qa_sc_reset')}",
                f"Tab     {t('qa_sc_tab')}",
                f"L       {t('qa_sc_locale')}",
                f"T       {t('qa_sc_theme')}",
                f"N       {t('qa_sc_noise')}",
                f"H       {t('qa_sc_step')}",
                f"Up/Down {t('qa_sc_updown')}",
                f"[ / ]   {t('qa_sc_speed')}",
                f"F1      {t('qa_sc_help')}",
                f"F10     {t('qa_sc_fps')}",
                f"F12     {t('qa_sc_screenshot')}",
                f"?       {t('qa_sc_shortcuts')}",
                f"Ctrl+X  {t('qa_sc_export')}",
                f"ESC     {t('qa_sc_exit')}",
            ]
            sc_w, sc_h = 280, len(_sc_lines) * 15 + 16
            sc_x = WIDTH // 2 - sc_w // 2
            sc_y = HEIGHT // 2 - sc_h // 2
            overlay_bg = pygame.Surface((sc_w, sc_h), pygame.SRCALPHA)
            overlay_bg.fill((*PANEL_BG, 230))
            screen.blit(overlay_bg, (sc_x, sc_y))
            pygame.draw.rect(screen, ACCENT, (sc_x, sc_y, sc_w, sc_h), 2, border_radius=6)
            for si, line in enumerate(_sc_lines):
                clr = ACCENT if si == 0 else TEXT_CLR
                ls = font.render(line, True, clr)
                screen.blit(ls, (sc_x + 12, sc_y + 8 + si * 15))

        # 토스트 알림 렌더링 (우하단)
        for ti, toast in enumerate(_toasts):
            t_txt, t_clr, t_time = toast
            alpha = min(int(t_time / 0.3 * 255), 255)
            t_surf = font.render(t_txt, True, t_clr)
            t_bg = pygame.Surface((t_surf.get_width() + 16, 18), pygame.SRCALPHA)
            t_bg.fill((*PANEL_BG, min(alpha, 200)))
            tx = WIDTH - t_surf.get_width() - 26
            ty = HEIGHT - 80 - ti * 22
            screen.blit(t_bg, (tx - 4, ty - 2))
            pygame.draw.rect(screen, t_clr, (tx - 4, ty - 2,
                             t_surf.get_width() + 16, 18), 1, border_radius=3)
            screen.blit(t_surf, (tx + 4, ty))

        help_overlay.draw(screen, font)
        tutorial.draw(screen, font)

        pygame.display.flip()

    ghz_cons_rate = (
        ghz.consistency_pass / ghz.consistency_checks
        if ghz.consistency_checks > 0 else 0.0
    )
    finalize_session(
        "qkd_advanced",
        {
            "e91_rounds": e91.total_rounds,
            "e91_bell_S": round(e91.bell_S, 3),
            "e91_bell_violated": e91.bell_violated,
            "e91_key_bits": len(e91.raw_key_alice),
            "ghz_rounds": ghz.total_rounds,
            "ghz_key_bits": len(ghz.raw_keys[0]),
            "ghz_consistency_rate": round(ghz_cons_rate, 3),
            "bb84_cmp_rounds": bb84_cmp.total_rounds,
            "bb84_cmp_qber": round(bb84_cmp.qber, 3),
            "bb84_cmp_eve_detected": bb84_cmp.eve_detected,
        },
        recorder=recorder,
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def open_qkd_advanced():
    """외부에서 호출하는 진입점."""
    run_simulation()
