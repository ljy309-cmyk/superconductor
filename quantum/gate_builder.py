"""양자 게이트 빌더 (Quantum Gate Builder) — Pygame 시각화.

양자 회로를 시각적으로 구성하고 시뮬레이션합니다:
  - 게이트 팔레트에서 선택 → 큐비트 와이어에 배치
  - 실시간 상태 벡터 확률 막대 그래프
  - 블로흐 구 시각화 (큐비트별)
  - 측정 히스토그램
"""

import math
import time

import pygame

from config_loader import cfg
from font_helper import get_font
from game_base import finalize_session
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from quantum.gate_builder_engine import (
    ALL_GATES,
    GATE_INFO,
    MAX_GATES,
    SINGLE_GATES,
    QuantumCircuit,
)
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from sim_speed import speed_label
from sound_manager import get_sound_manager
from theme import get_pg_theme as _get_pg_theme_init
from theme import load_pg_colors, on_theme_change

_log = get_module_logger("gate_builder")

WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
FPS = cfg("display", "fps", 60)
NUM_QUBITS = cfg("gate_builder", "num_qubits", 2)

_pg = _get_pg_theme_init()
BG = _pg.BG
TEXT_CLR = _pg.TEXT
SUBTEXT_CLR = _pg.SUBTEXT
SC_COLOR = _pg.SC_COLOR
SC_GLOW = _pg.SC_GLOW
WHITE = _pg.WHITE
del _get_pg_theme_init

# 고유 색상
WIRE_COLOR = (88, 91, 112)
GATE_BG = (69, 71, 90)
GATE_BORDER = (137, 180, 250)
GATE_TEXT = (205, 214, 244)
GATE_HOVER = (203, 166, 247)
PROB_BAR = (166, 227, 161)
PROB_ZERO = (69, 71, 90)
BLOCH_RING = (88, 91, 112)
BLOCH_VEC = (250, 179, 135)
BLOCH_XY = (137, 180, 250)
MEASURE_COLOR = (243, 139, 168)

_COLOR_MAP = {
    "BG": "BG", "TEXT_CLR": "TEXT", "SUBTEXT_CLR": "SUBTEXT",
    "SC_COLOR": "SC_COLOR", "SC_GLOW": "SC_GLOW", "WHITE": "WHITE",
}


def _load_theme_colors():
    load_pg_colors(_COLOR_MAP, globals())


# ── 레이아웃 ─────────────────────────────────────────
CIRCUIT_X = 40
CIRCUIT_Y = 100
WIRE_SPACING = 60
GATE_SIZE = 40
GATE_SPACING = 55

PALETTE_X = 40
PALETTE_Y = 30
PALETTE_GAP = 52

PROB_X = 580
PROB_Y = 100
PROB_W = 140
PROB_H = 180

BLOCH_CX = 720
BLOCH_CY = 400
BLOCH_R = 70

HIST_X = 580
HIST_Y = 310
HIST_W = 140
HIST_H = 100


def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(t("game_title_gate_builder"))
    clock = pygame.time.Clock()
    font = get_font(13)
    title_font = get_font(18, bold=True)
    small_font = get_font(11)
    gate_font = get_font(14, bold=True)

    help_overlay = HelpOverlay("gate_builder")
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("gate_builder")

    qc = QuantumCircuit(NUM_QUBITS)
    selected_gate: str | None = None
    hover_gate: str | None = None
    measure_counts: dict[int, int] = {}
    total_measures = 0
    bloch_qubit = 0  # 블로흐 구에 표시할 큐비트
    start_time = time.time()
    running = True

    # 팔레트 버튼 위치 계산
    palette_rects: dict[str, pygame.Rect] = {}
    for i, g in enumerate(ALL_GATES):
        px = PALETTE_X + i * PALETTE_GAP
        palette_rects[g] = pygame.Rect(px, PALETTE_Y, GATE_SIZE, GATE_SIZE)

    while running:
        clock.tick(FPS)

        for event in pygame.event.get():
            help_overlay.handle_event(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                snd.handle_key(event.key)
                if event.key == pygame.K_ESCAPE and not help_overlay.visible:
                    if confirm_quit(screen, font):
                        running = False
                elif event.key == pygame.K_BACKSPACE:
                    qc.remove_last_gate()
                    qc.run()
                elif event.key == pygame.K_DELETE:
                    qc.clear()
                    measure_counts.clear()
                    total_measures = 0
                elif event.key == pygame.K_RETURN:
                    # 측정
                    qc.run()
                    result = qc.measure()
                    measure_counts[result] = measure_counts.get(result, 0) + 1
                    total_measures += 1
                elif event.key == pygame.K_TAB:
                    bloch_qubit = (bloch_qubit + 1) % qc.num_qubits
                elif event.key == pygame.K_l:
                    toggle_locale()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                # 팔레트 클릭 → 게이트 선택
                clicked_palette = False
                for g, rect in palette_rects.items():
                    if rect.collidepoint(mx, my):
                        selected_gate = g if selected_gate != g else None
                        clicked_palette = True
                        break

                # 와이어 클릭 → 게이트 배치
                if not clicked_palette and selected_gate:
                    for q in range(qc.num_qubits):
                        wy = CIRCUIT_Y + q * WIRE_SPACING
                        if abs(my - wy) < WIRE_SPACING // 2:
                            if selected_gate == "CNOT":
                                # CNOT: 첫 클릭=제어, 두번째=타겟
                                other_q = (q + 1) % qc.num_qubits
                                if qc.add_gate("CNOT", q, other_q):
                                    qc.run()
                            else:
                                if qc.add_gate(selected_gate, q):
                                    qc.run()
                            break

        # 마우스 호버
        mx, my = pygame.mouse.get_pos()
        hover_gate = None
        for g, rect in palette_rects.items():
            if rect.collidepoint(mx, my):
                hover_gate = g
                break

        # 리플레이 기록
        recorder.record_frame({
            "gates": len(qc.gates),
            "probs": [round(p, 3) for p in qc.probabilities()],
        })

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        title_surf = title_font.render(t("game_title_gate_builder"), True, SC_GLOW)
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 6))

        # ── 게이트 팔레트 ────────────────────────────
        for g, rect in palette_rects.items():
            color = GATE_HOVER if (g == selected_gate or g == hover_gate) else GATE_BG
            border = GATE_HOVER if g == selected_gate else GATE_BORDER
            pygame.draw.rect(screen, color, rect, border_radius=4)
            pygame.draw.rect(screen, border, rect, 2, border_radius=4)
            label = gate_font.render(g, True, GATE_TEXT)
            screen.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - label.get_height() // 2))

        # 선택된 게이트 설명
        desc_gate = hover_gate or selected_gate
        if desc_gate and desc_gate in GATE_INFO:
            info_surf = small_font.render(GATE_INFO[desc_gate], True, SUBTEXT_CLR)
            screen.blit(info_surf, (PALETTE_X, PALETTE_Y + GATE_SIZE + 6))

        # ── 회로 와이어 ──────────────────────────────
        wire_end_x = CIRCUIT_X + max(len(qc.gates) + 2, 8) * GATE_SPACING
        for q in range(qc.num_qubits):
            wy = CIRCUIT_Y + q * WIRE_SPACING
            pygame.draw.line(screen, WIRE_COLOR, (CIRCUIT_X, wy), (min(wire_end_x, 540), wy), 2)
            # 큐비트 라벨
            q_label = small_font.render(f"q{q}: |0⟩", True, TEXT_CLR)
            screen.blit(q_label, (CIRCUIT_X - 38, wy - 6))

        # ── 배치된 게이트 ────────────────────────────
        for i, gate in enumerate(qc.gates):
            gx = CIRCUIT_X + (i + 1) * GATE_SPACING
            if gate.name == "CNOT":
                # 제어 큐비트: 점
                cy = CIRCUIT_Y + gate.qubit * WIRE_SPACING
                ty = CIRCUIT_Y + gate.target * WIRE_SPACING
                pygame.draw.line(screen, GATE_BORDER, (gx, cy), (gx, ty), 2)
                pygame.draw.circle(screen, GATE_BORDER, (gx, cy), 5)
                # 타겟 큐비트: ⊕
                pygame.draw.circle(screen, GATE_BORDER, (gx, ty), 12, 2)
                pygame.draw.line(screen, GATE_BORDER, (gx - 8, ty), (gx + 8, ty), 2)
                pygame.draw.line(screen, GATE_BORDER, (gx, ty - 8), (gx, ty + 8), 2)
            else:
                gy = CIRCUIT_Y + gate.qubit * WIRE_SPACING
                rect = pygame.Rect(gx - GATE_SIZE // 2, gy - GATE_SIZE // 2, GATE_SIZE, GATE_SIZE)
                pygame.draw.rect(screen, GATE_BG, rect, border_radius=4)
                pygame.draw.rect(screen, GATE_BORDER, rect, 2, border_radius=4)
                label = gate_font.render(gate.name, True, GATE_TEXT)
                screen.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - label.get_height() // 2))

        # ── 확률 막대 그래프 ─────────────────────────
        probs = qc.probabilities()
        labels = qc.basis_labels()
        _draw_prob_bars(screen, small_font, probs, labels)

        # ── 측정 히스토그램 ──────────────────────────
        _draw_measure_hist(screen, small_font, measure_counts, total_measures, labels)

        # ── 블로흐 구 ────────────────────────────────
        _draw_bloch_sphere(screen, small_font, qc, bloch_qubit)

        # ── 하단 안내 ────────────────────────────────
        hints = [
            t("gb_hint_line1"),
            t("gb_hint_line2"),
        ]
        for i, hint in enumerate(hints):
            surf = small_font.render(hint, True, SUBTEXT_CLR)
            screen.blit(surf, (12, HEIGHT - 36 + i * 16))

        # 게이트 수 표시
        count_text = small_font.render(
            t("gb_gate_count", count=len(qc.gates), max=MAX_GATES), True, TEXT_CLR
        )
        screen.blit(count_text, (CIRCUIT_X, CIRCUIT_Y + qc.num_qubits * WIRE_SPACING + 10))

        help_overlay.draw(screen, font)
        pygame.display.flip()

    play_time = round(time.time() - start_time, 1)
    finalize_session(
        "gate_builder",
        {
            "play_time": play_time,
            "gates_used": len(qc.gates),
            "total_measures": total_measures,
        },
        recorder=recorder,
        recorder_meta={"play_time": play_time},
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def _draw_prob_bars(screen, font, probs, labels):
    """확률 막대 그래프."""
    x, y, w, h = PROB_X, PROB_Y, PROB_W, PROB_H
    title = font.render(t("gb_probabilities"), True, TEXT_CLR)
    screen.blit(title, (x, y - 16))

    n = len(probs)
    bar_h = max(12, (h - 10) // n)

    for i, (prob, label) in enumerate(zip(probs, labels)):
        by = y + i * bar_h
        # 배경
        pygame.draw.rect(screen, PROB_ZERO, (x, by, w, bar_h - 2), border_radius=2)
        # 채움
        fill_w = int(prob * w)
        if fill_w > 0:
            pygame.draw.rect(screen, PROB_BAR, (x, by, fill_w, bar_h - 2), border_radius=2)
        # 라벨
        lbl = font.render(f"{label} {prob:.1%}", True, TEXT_CLR)
        screen.blit(lbl, (x + 4, by + 1))


def _draw_measure_hist(screen, font, counts, total, labels):
    """측정 히스토그램."""
    x, y, w, h = HIST_X, HIST_Y, HIST_W, HIST_H
    title = font.render(t("gb_measurements", n=total), True, TEXT_CLR)
    screen.blit(title, (x, y - 16))

    pygame.draw.rect(screen, (30, 30, 46), (x, y, w, h), border_radius=4)
    pygame.draw.rect(screen, (69, 71, 90), (x, y, w, h), 1, border_radius=4)

    if total == 0:
        hint = font.render(t("gb_press_enter"), True, SUBTEXT_CLR)
        screen.blit(hint, (x + w // 2 - hint.get_width() // 2, y + h // 2 - 6))
        return

    n = len(labels)
    bar_w = max(8, (w - 20) // n)
    max_count = max(counts.values()) if counts else 1

    for i in range(n):
        c = counts.get(i, 0)
        bx = x + 10 + i * bar_w
        bar_h_val = int((c / max_count) * (h - 30)) if max_count > 0 else 0
        # 바
        if bar_h_val > 0:
            pygame.draw.rect(screen, MEASURE_COLOR, (bx, y + h - 10 - bar_h_val, bar_w - 2, bar_h_val), border_radius=2)
        # 라벨
        lbl = font.render(labels[i], True, SUBTEXT_CLR)
        screen.blit(lbl, (bx, y + h - 8))


def _draw_bloch_sphere(screen, font, qc, qubit):
    """블로흐 구 시각화."""
    cx, cy, r = BLOCH_CX, BLOCH_CY, BLOCH_R

    title = font.render(t("gb_bloch", q=qubit), True, TEXT_CLR)
    screen.blit(title, (cx - title.get_width() // 2, cy - r - 20))

    # 원 (XZ 평면 투영)
    pygame.draw.circle(screen, BLOCH_RING, (cx, cy), r, 1)
    # 축
    pygame.draw.line(screen, BLOCH_RING, (cx - r, cy), (cx + r, cy), 1)  # X
    pygame.draw.line(screen, BLOCH_RING, (cx, cy - r), (cx, cy + r), 1)  # Z
    # 타원 (Y축 깊이)
    pygame.draw.ellipse(screen, BLOCH_RING, (cx - r, cy - r // 3, r * 2, r * 2 // 3), 1)

    # 축 라벨
    lbl_0 = font.render("|0⟩", True, SUBTEXT_CLR)
    lbl_1 = font.render("|1⟩", True, SUBTEXT_CLR)
    screen.blit(lbl_0, (cx - lbl_0.get_width() // 2, cy - r - 10))
    screen.blit(lbl_1, (cx - lbl_1.get_width() // 2, cy + r + 2))

    # 블로흐 벡터
    bx, by, bz = qc.qubit_bloch(qubit)
    # 투영: x → 화면 x, z → 화면 -y
    px = cx + int(bx * r)
    py = cy - int(bz * r)

    # 벡터선
    pygame.draw.line(screen, BLOCH_VEC, (cx, cy), (px, py), 2)
    pygame.draw.circle(screen, BLOCH_VEC, (px, py), 5)

    # XY 평면 그림자
    shadow_px = cx + int(bx * r)
    shadow_py = cy
    pygame.draw.line(screen, BLOCH_XY, (cx, cy), (shadow_px, shadow_py), 1)

    # 좌표 텍스트
    coord = font.render(f"({bx:.2f}, {by:.2f}, {bz:.2f})", True, SUBTEXT_CLR)
    screen.blit(coord, (cx - coord.get_width() // 2, cy + r + 16))


def open_gate_builder():
    """외부에서 호출하는 진입점."""
    run_simulation()
