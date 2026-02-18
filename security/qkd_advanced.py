"""고급 QKD 프로토콜 시뮬레이션 (Pygame).

4 모드:
  Mode 1 — E91: 얽힘 기반 양자 키 분배 + 벨 부등식 보안 검증
  Mode 2 — Key Sifting: BB84/E91 키 시프팅 & 프라이버시 증폭 시각화
  Mode 3 — Multi-Party: GHZ 기반 3자간 QKD 네트워크
  Mode 4 — Compare: BB84 vs E91 동일 Eve 조건 비교
"""

import math

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
)
from sound_manager import get_sound_manager
from theme import load_pg_colors, on_theme_change
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

# ── 노드 위치 ────────────────────────────────────────
ALICE_POS = (140, 140)
BOB_POS = (760, 140)
EPR_POS = (450, 90)
EVE_POS = (450, 40)


# ── E91 모드 ─────────────────────────────────────────

def _draw_e91_mode(screen, e91: E91State, anim_t, font, big_font):
    """E91 프로토콜 시각화."""
    # EPR 소스
    pygame.draw.circle(screen, MAUVE, EPR_POS, 22)
    pygame.draw.circle(screen, TEXT_CLR, EPR_POS, 22, 2)
    lbl = big_font.render("EPR", True, MAUVE)
    screen.blit(lbl, (EPR_POS[0] - lbl.get_width() // 2, EPR_POS[1] - 8))
    sub = font.render("|Φ+⟩", True, SUBTEXT_CLR)
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

    # Bell S 시계열 수렴 그래프
    _draw_bell_s_graph(screen, e91.bell_S_history, 480, 340, 390, 170,
                       font, big_font)


def _draw_correlator_table(screen, e91: E91State, font, big_font):
    """E91 상관 함수 테이블."""
    tx, ty = 500, 200
    header = big_font.render(t("qa_correlators"), True, ACCENT)
    screen.blit(header, (tx, ty))

    base_labels_a = ["0°", "π/8", "π/4"]
    base_labels_b = ["π/8", "π/4", "3π/8"]

    # 헤더
    for j, bl in enumerate(base_labels_b):
        surf = font.render(bl, True, GREEN)
        screen.blit(surf, (tx + 60 + j * 70, ty + 18))

    for i, al in enumerate(base_labels_a):
        y = ty + 36 + i * 18
        surf = font.render(al, True, BLUE)
        screen.blit(surf, (tx, y))

        for j in range(3):
            pair = (i, j)
            data = e91.correlators.get(pair, [])
            if data:
                avg = sum(data) / len(data)
                val_txt = f"{avg:+.2f}"
                # 키 쌍은 하이라이트
                is_key = pair in [(1, 0), (2, 1)]
                clr = YELLOW if is_key else TEXT_CLR
            else:
                val_txt = "  —"
                clr = SUBTEXT_CLR
            surf = font.render(val_txt, True, clr)
            screen.blit(surf, (tx + 60 + j * 70, y))

    # 범례
    leg_y = ty + 36 + 3 * 18 + 8
    leg = font.render(t("qa_key_pair_legend"), True, YELLOW)
    screen.blit(leg, (tx, leg_y))


# ── Key Sift & PA 모드 ──────────────────────────────

def _draw_sift_mode(screen, e91: E91State, anim_t, font, big_font):
    """QKD 후처리 파이프라인 시각화 (4단계)."""
    sy = 68

    # 4단계 파이프라인
    corrected_bits = len(e91.corrected_key)
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

    for i, (label, size, clr, done) in enumerate(stages):
        bx = start_x + i * (box_w + gap)
        by = sy

        pygame.draw.rect(screen, PANEL_BG, (bx, by, box_w, box_h), border_radius=8)
        border_clr = clr if done else OVERLAY
        pygame.draw.rect(screen, border_clr, (bx, by, box_w, box_h), 2, border_radius=8)

        lbl = big_font.render(label, True, clr if done else SUBTEXT_CLR)
        screen.blit(lbl, (bx + box_w // 2 - lbl.get_width() // 2, by + 8))

        size_txt = font.render(f"{size} bits", True, TEXT_CLR if done else SUBTEXT_CLR)
        screen.blit(size_txt, (bx + box_w // 2 - size_txt.get_width() // 2, by + 30))

        # 화살표
        if i < 3:
            ax = bx + box_w + 3
            ay = by + box_h // 2
            pygame.draw.line(screen, SUBTEXT_CLR, (ax, ay), (ax + gap - 8, ay), 2)
            pygame.draw.polygon(screen, SUBTEXT_CLR,
                                [(ax + gap - 8, ay - 3), (ax + gap - 2, ay), (ax + gap - 8, ay + 3)])

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

    # 최종 키
    if e91.pa_done and e91.final_key:
        fy = ky + 140
        header = big_font.render(t("qa_final_key_hdr"), True, ACCENT)
        screen.blit(header, (40, fy))
        key = e91.final_key
        for i in range(0, len(key), 32):
            chunk = key[i:i + 32]
            screen.blit(font.render(chunk, True, MAUVE), (40, fy + 16 + (i // 32) * 14))

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

def _draw_ghz_mode(screen, ghz: GHZState, anim_t, font, big_font):
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
    ghz_lbl = big_font.render("GHZ", True, MAUVE)
    screen.blit(ghz_lbl, (cx - ghz_lbl.get_width() // 2, cy - 8))

    # 얽힘 링크 (물결)
    for pos in positions:
        wave = math.sin(anim_t * 3) * 3
        mid_x = (cx + pos[0]) // 2 + int(wave)
        mid_y = (cy + pos[1]) // 2 + int(wave)
        pygame.draw.lines(screen, MAUVE, False, [(cx, cy), (mid_x, mid_y), pos], 1)

    # 노드
    for i, (pos, name, clr) in enumerate(zip(positions, ghz.party_names, colors)):
        pygame.draw.circle(screen, clr, pos, 24)
        pygame.draw.circle(screen, TEXT_CLR, pos, 24, 2)
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

    help_overlay = HelpOverlay("qkd_advanced")
    tutorial = TutorialOverlay("qkd_advanced")
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("qkd_advanced")

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
                    if confirm_quit(screen, font):
                        running = False
                elif event.key == pygame.K_TAB:
                    mode = (mode + 1) % NUM_MODES
                elif event.key == pygame.K_SPACE:
                    if mode == MODE_E91:
                        # 배치 실행 (config: e91_batch_size)
                        for _ in range(E91_BATCH):
                            e91_round(e91, eve_chance)
                        compute_bell_S(e91)
                    elif mode == MODE_SIFT:
                        # 4단계 파이프라인 순차 실행
                        if len(e91.raw_key_alice) == 0:
                            # Stage 0: 라운드 생성 (config: chsh_shots)
                            for _ in range(CHSH_SHOTS):
                                e91_round(e91, eve_chance)
                            compute_bell_S(e91)
                        elif not e91.qber_done:
                            # Stage 1: QBER 추정
                            estimate_qber(e91)
                        elif not e91.correction_done:
                            # Stage 2: 에러 정정
                            error_correct(e91)
                        elif not e91.pa_done:
                            # Stage 3: 프라이버시 증폭
                            privacy_amplification(e91)
                        else:
                            # 리셋 후 새 파이프라인
                            reset_e91(e91)
                    elif mode == MODE_GHZ:
                        for _ in range(GHZ_BATCH):
                            ghz_round(ghz, eve_chance)
                    elif mode == MODE_COMPARE:
                        # 두 프로토콜 동시 실행 (동일 Eve 조건)
                        for _ in range(E91_BATCH):
                            bb84_round(bb84_cmp, eve_chance)
                            e91_round(e91_cmp, eve_chance)
                        compute_bell_S(e91_cmp)
                elif event.key == pygame.K_s:
                    # 전체 파이프라인 한번에 실행
                    if mode in (MODE_E91, MODE_SIFT):
                        if len(e91.raw_key_alice) > 0:
                            key_sift(e91)
                            privacy_amplification(e91)
                    elif mode == MODE_GHZ:
                        ghz_key_sift(ghz)
                        ghz_privacy_amplification(ghz)
                    elif mode == MODE_COMPARE:
                        # Compare 모드 양쪽 파이프라인 실행
                        if len(e91_cmp.raw_key_alice) > 0:
                            key_sift(e91_cmp)
                            privacy_amplification(e91_cmp)
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
                elif event.key == pygame.K_e:
                    # Eve 단계별 순환: 0→10→30→50→80→100→0%
                    _EVE_LEVELS = [0.0, 0.1, 0.3, 0.5, 0.8, 1.0]
                    _cur = min(range(len(_EVE_LEVELS)),
                               key=lambda i: abs(_EVE_LEVELS[i] - eve_chance))
                    eve_chance = _EVE_LEVELS[(_cur + 1) % len(_EVE_LEVELS)]
                elif event.key == pygame.K_UP and mode == MODE_GHZ:
                    if ghz.n_parties < GHZ_MAX_PARTIES:
                        resize_ghz(ghz, ghz.n_parties + 1)
                elif event.key == pygame.K_DOWN and mode == MODE_GHZ:
                    if ghz.n_parties > GHZ_MIN_PARTIES:
                        resize_ghz(ghz, ghz.n_parties - 1)
                elif event.key == pygame.K_l:
                    toggle_locale()
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
            if auto_timer >= 0.05:
                auto_timer = 0.0
                if mode == MODE_E91:
                    e91_round(e91, eve_chance)
                    if e91.total_rounds % 10 == 0:
                        compute_bell_S(e91)
                elif mode == MODE_SIFT:
                    e91_round(e91, eve_chance)
                    if e91.total_rounds % 10 == 0:
                        compute_bell_S(e91)
                    # 자동 파이프라인: 충분한 키가 쌓이면 순차 실행
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
                    # 자동 파이프라인: 충분한 키가 쌓이면 시프팅→PA
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
                    # 자동 파이프라인: E91 측 시프팅→PA
                    if (e91_cmp.total_rounds > 0
                            and e91_cmp.total_rounds % CHSH_SHOTS == 0
                            and not e91_cmp.pa_done):
                        if not e91_cmp.qber_done:
                            estimate_qber(e91_cmp)
                        elif not e91_cmp.correction_done:
                            error_correct(e91_cmp)
                        elif not e91_cmp.pa_done:
                            privacy_amplification(e91_cmp)

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
            _draw_ghz_mode(screen, ghz, anim_t, font, big_font)
        elif mode == MODE_COMPARE:
            _draw_compare_mode(screen, bb84_cmp, e91_cmp, font, big_font)

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
