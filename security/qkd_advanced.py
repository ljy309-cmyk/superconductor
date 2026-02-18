"""고급 QKD 프로토콜 시뮬레이션 (Pygame).

3 모드:
  Mode 1 — E91: 얽힘 기반 양자 키 분배 + 벨 부등식 보안 검증
  Mode 2 — Key Sifting: BB84/E91 키 시프팅 & 프라이버시 증폭 시각화
  Mode 3 — Multi-Party: GHZ 기반 3자간 QKD 네트워크
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
    CHSH_CLASSICAL_BOUND,
    CHSH_QUANTUM_BOUND,
    E91State,
    GHZState,
    compute_bell_S,
    e91_round,
    error_correct,
    estimate_qber,
    ghz_key_sift,
    ghz_privacy_amplification,
    ghz_round,
    key_sift,
    privacy_amplification,
    reset_e91,
    reset_ghz,
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
MODE_NAMES = ["E91", "Key Sift & PA", "Multi-Party (GHZ)"]

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
    lbl = big_font.render("Alice", True, BLUE)
    screen.blit(lbl, (ALICE_POS[0] - lbl.get_width() // 2, ALICE_POS[1] + 32))
    bases_a = font.render("0°, π/8, π/4", True, SUBTEXT_CLR)
    screen.blit(bases_a, (ALICE_POS[0] - bases_a.get_width() // 2, ALICE_POS[1] + 48))

    # Bob
    pygame.draw.circle(screen, GREEN, BOB_POS, 28)
    pygame.draw.circle(screen, TEXT_CLR, BOB_POS, 28, 2)
    lbl = big_font.render("Bob", True, GREEN)
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
    lbl = font.render("Eve", True, RED)
    screen.blit(lbl, (EVE_POS[0] - lbl.get_width() // 2, EVE_POS[1] - 28))

    # 통계 패널
    sy = 200
    stats = [
        (f"Rounds: {e91.total_rounds}  (Key: {e91.key_rounds}  Bell: {e91.bell_rounds})", TEXT_CLR),
        (f"Raw Key Length: {len(e91.raw_key_alice)} bits", BLUE),
        (f"Bell S = {e91.bell_S:.3f}  (Classical ≤ {CHSH_CLASSICAL_BOUND}, Quantum ≤ {CHSH_QUANTUM_BOUND:.3f})", ACCENT),
    ]
    if e91.bell_violated:
        stats.append(("Bell Inequality VIOLATED — Quantum Secure!", GREEN))
    elif e91.bell_rounds > 20:
        stats.append(("Bell Inequality NOT violated — Possible Eavesdropping!", RED))

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
        txt = f"R{rd.round_id:03d} A:{a_deg} B:{b_deg} [{basis_match}] A={rd.alice_result:+d} B={rd.bob_result:+d}{eve}"
        surf = font.render(txt, True, clr)
        screen.blit(surf, (40, log_y + 18 + i * 14))

    # 상관 함수 테이블
    _draw_correlator_table(screen, e91, font, big_font)


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
        ("Raw Key", len(e91.raw_key_alice), BLUE,
         len(e91.raw_key_alice) > 0),
        ("QBER Est.", e91.qber_sample_size, YELLOW,
         e91.qber_done),
        ("Error Corr.", corrected_bits, GREEN,
         e91.correction_done),
        ("Privacy Amp", len(e91.final_key) * 4, MAUVE,
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
    _draw_key_bits(screen, "Alice Raw", e91.raw_key_alice[:64], BLUE, 40, ky, font, big_font)
    _draw_key_bits(screen, "Bob Raw", e91.raw_key_bob[:64], GREEN, 40, ky + 30, font, big_font)

    # QBER 추정 결과
    if e91.qber_done:
        qber_y = ky + 65
        qber_pct = e91.qber_value * 100
        qber_clr = RED if e91.qber_value > 0.11 else GREEN
        qber_txt = f"QBER = {qber_pct:.1f}%  (sampled {e91.qber_sample_size} bits)"
        screen.blit(font.render(qber_txt, True, qber_clr), (40, qber_y))
        # QBER 해석
        if e91.qber_value > 0.11:
            warn = font.render("QBER > 11% — Eve suspected! Key may be compromised.", True, RED)
            screen.blit(warn, (40, qber_y + 14))
        else:
            safe = font.render("QBER < 11% — Channel secure, proceeding.", True, GREEN)
            screen.blit(safe, (40, qber_y + 14))

    # 에러 정정 결과
    if e91.correction_done:
        ec_y = ky + 100
        _draw_key_bits(screen, "Corrected", e91.corrected_key[:64], GREEN, 40, ec_y, font, big_font)
        ec_txt = f"Error correction: {e91.correction_flips} bits flipped (block parity)"
        screen.blit(font.render(ec_txt, True, TEXT_CLR), (40, ec_y + 18))

    # 최종 키
    if e91.pa_done and e91.final_key:
        fy = ky + 140
        header = big_font.render("Final Key (Toeplitz universal hash):", True, ACCENT)
        screen.blit(header, (40, fy))
        key = e91.final_key
        for i in range(0, len(key), 32):
            chunk = key[i:i + 32]
            screen.blit(font.render(chunk, True, MAUVE), (40, fy + 16 + (i // 32) * 14))

    # 통계
    stats_y = 420
    raw_n = len(e91.raw_key_alice)
    corr_n = len(e91.corrected_key)
    final_n = len(e91.final_key) * 4
    stats = [
        (f"E91 Rounds: {e91.total_rounds}  (Key: {e91.key_rounds}  Bell: {e91.bell_rounds})", TEXT_CLR),
        (f"Pipeline: Raw {raw_n} → QBER sample {e91.qber_sample_size} → Corrected {corr_n} → Final {final_n} bits", ACCENT),
        (f"QBER: {e91.qber_value * 100:.1f}%  |  Corrected flips: {e91.correction_flips}", TEXT_CLR),
        (f"Bell S = {e91.bell_S:.3f}  {'SECURE' if e91.bell_violated else 'WARNING'}", GREEN if e91.bell_violated else RED),
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


# ── GHZ Multi-Party 모드 ────────────────────────────

def _draw_ghz_mode(screen, ghz: GHZState, anim_t, font, big_font):
    """GHZ 다자간 QKD 시각화."""
    # 3자 네트워크 토폴로지 (삼각형)
    cx, cy = WIDTH // 2, 160
    radius = 100
    positions = []
    colors = [BLUE, GREEN, PEACH]

    for i in range(3):
        angle = -math.pi / 2 + i * 2 * math.pi / 3
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
        pygame.draw.circle(screen, clr, pos, 26)
        pygame.draw.circle(screen, TEXT_CLR, pos, 26, 2)
        lbl = big_font.render(name, True, clr)
        screen.blit(lbl, (pos[0] - lbl.get_width() // 2, pos[1] + 30))

    # GHZ 상태 표시
    state_lbl = font.render("|GHZ⟩ = (|000⟩ + |111⟩) / √2", True, MAUVE)
    screen.blit(state_lbl, (cx - state_lbl.get_width() // 2, cy + 22))

    # 통계
    sy = 290
    stats = [
        (f"Rounds: {ghz.total_rounds}  (Key: {ghz.key_rounds}  Check: {ghz.consistency_checks})", TEXT_CLR),
        (f"Raw Key Length: {len(ghz.raw_keys[0])} bits", BLUE),
    ]

    if ghz.consistency_checks > 0:
        pass_rate = ghz.consistency_pass / ghz.consistency_checks
        stats.append((f"Consistency: {ghz.consistency_pass}/{ghz.consistency_checks} ({pass_rate * 100:.1f}%)",
                       GREEN if pass_rate > 0.85 else RED))

    if ghz.sift_done:
        stats.append((f"Sifted Key: {len(ghz.sifted_key)} bits  |  Error: {ghz.error_rate * 100:.1f}%",
                       MAUVE))

    if ghz.pa_done and ghz.final_key:
        stats.append((f"Final Key: {ghz.final_key[:40]}...", ACCENT))

    for i, (txt, clr) in enumerate(stats):
        surf = font.render(txt, True, clr)
        screen.blit(surf, (40, sy + i * 16))

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
              t("qa_tag_chk") if is_chk else "---"
        eve = f" [{t('qa_tag_eve')}]" if rd.eve_present else ""

        if rd.eve_present:
            clr = RED
        elif is_key:
            clr = GREEN
        elif is_chk:
            clr = YELLOW
        else:
            clr = SUBTEXT_CLR

        txt = f"R{rd.round_id:03d} Bases:{bases} Results:{results} [{tag}]{eve}"
        surf = font.render(txt, True, clr)
        screen.blit(surf, (40, log_y + 18 + i * 14))


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
                    mode = (mode + 1) % 3
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
                elif event.key == pygame.K_s:
                    # 전체 파이프라인 한번에 실행
                    if mode in (MODE_E91, MODE_SIFT):
                        if len(e91.raw_key_alice) > 0:
                            key_sift(e91)
                            privacy_amplification(e91)
                    elif mode == MODE_GHZ:
                        ghz_key_sift(ghz)
                        ghz_privacy_amplification(ghz)
                elif event.key == pygame.K_r:
                    reset_e91(e91)
                    reset_ghz(ghz)
                elif event.key == pygame.K_p:
                    paused = not paused
                elif event.key == pygame.K_a:
                    auto_run = not auto_run
                elif event.key == pygame.K_e:
                    # Eve 토글
                    eve_chance = 0.3 if eve_chance < 0.01 else 0.0
                elif event.key == pygame.K_l:
                    toggle_locale()

        # 자동 실행
        if auto_run and not paused:
            auto_timer += dt
            if auto_timer >= 0.05:
                auto_timer = 0.0
                if mode == MODE_E91 or mode == MODE_SIFT:
                    e91_round(e91, eve_chance)
                    if e91.total_rounds % 10 == 0:
                        compute_bell_S(e91)
                elif mode == MODE_GHZ:
                    ghz_round(ghz, eve_chance)

        # 리플레이 기록
        if not paused:
            recorder.record({
                "mode": mode,
                "e91_rounds": e91.total_rounds,
                "e91_bell_S": e91.bell_S,
                "ghz_rounds": ghz.total_rounds,
                "eve_chance": eve_chance,
            })

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        title = title_font.render(t("game_title_qkd_advanced"), True, ACCENT)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 8))

        # 모드 탭
        tab_y = 32
        for i, name in enumerate(MODE_NAMES):
            tx = 40 + i * 200
            active = i == mode
            clr = ACCENT if active else SUBTEXT_CLR
            pygame.draw.rect(screen, PANEL_BG if active else BG,
                             (tx, tab_y, 180, 22), border_radius=4)
            if active:
                pygame.draw.rect(screen, clr, (tx, tab_y, 180, 22), 2, border_radius=4)
            tab_lbl = big_font.render(name, True, clr)
            screen.blit(tab_lbl, (tx + 90 - tab_lbl.get_width() // 2, tab_y + 3))

        # Eve 상태
        eve_txt = f"Eve: {'ON ({:.0f}%)'.format(eve_chance * 100) if eve_chance > 0 else 'OFF'}"
        eve_surf = font.render(eve_txt, True, RED if eve_chance > 0 else SUBTEXT_CLR)
        screen.blit(eve_surf, (WIDTH - eve_surf.get_width() - 10, 36))

        # 모드별 렌더링
        if mode == MODE_E91:
            _draw_e91_mode(screen, e91, anim_t, font, big_font)
        elif mode == MODE_SIFT:
            _draw_sift_mode(screen, e91, anim_t, font, big_font)
        elif mode == MODE_GHZ:
            _draw_ghz_mode(screen, ghz, anim_t, font, big_font)

        # 안내
        hints = [
            t("qa_hint_line1",
              auto=t("auto_on") if auto_run else t("auto_off"),
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
        },
        recorder=recorder,
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def open_qkd_advanced():
    """외부에서 호출하는 진입점."""
    run_simulation()
