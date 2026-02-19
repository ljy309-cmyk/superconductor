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


class Layout:
    """해상도 기반 레이아웃 좌표 계산.

    기준 해상도 900×600에 대한 비례식으로 좌표를 산출합니다.
    """

    def __init__(self, w: int = 900, h: int = 600):
        self.W = w
        self.H = h
        sx = w / 900
        sy = h / 600

        # 게이트 팔레트
        self.palette_x = int(40 * sx)
        self.palette_y = int(30 * sy)
        self.palette_gap = int(52 * sx)
        self.gate_size = int(40 * min(sx, sy))

        # 회로
        self.circuit_x = int(40 * sx)
        self.circuit_y = int(100 * sy)
        self.wire_spacing = int(60 * sy)
        self.gate_spacing = int(55 * sx)

        # 확률 바
        self.prob_x = int(580 * sx)
        self.prob_y = int(100 * sy)
        self.prob_w = int(140 * sx)
        self.prob_h = int(180 * sy)

        # 블로흐 구
        self.bloch_cx = int(720 * sx)
        self.bloch_cy = int(400 * sy)
        self.bloch_r = int(70 * min(sx, sy))

        # 측정 히스토그램
        self.hist_x = int(580 * sx)
        self.hist_y = int(310 * sy)
        self.hist_w = int(140 * sx)
        self.hist_h = int(100 * sy)

        # 타이틀 & 하단
        self.title_y = int(6 * sy)
        self.hint_x = int(12 * sx)
        self.hint_y = h - int(36 * sy)
        self.count_offset_y = int(10 * sy)


_layout = Layout()


def _rebuild_layout(w: int, h: int):
    """리사이즈 시 레이아웃 재계산."""
    global _layout
    _layout = Layout(w, h)


def run_simulation():
    """Pygame 시뮬레이션 실행."""
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption(t("game_title_gate_builder"))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 13)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)
    small_font = pygame.font.SysFont("Consolas", 11)
    gate_font = pygame.font.SysFont("Consolas", 14, bold=True)

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
    L = _layout
    palette_rects: dict[str, pygame.Rect] = {}
    for i, g in enumerate(ALL_GATES):
        px = L.palette_x + i * L.palette_gap
        palette_rects[g] = pygame.Rect(px, L.palette_y, L.gate_size, L.gate_size)

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
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (event.w, event.h), pygame.RESIZABLE)
                _rebuild_layout(event.w, event.h)
                # 팔레트 버튼 위치 재계산
                L = _layout
                for i, g in enumerate(ALL_GATES):
                    px = L.palette_x + i * L.palette_gap
                    palette_rects[g] = pygame.Rect(
                        px, L.palette_y, L.gate_size, L.gate_size)
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
                    L = _layout
                    for q in range(qc.num_qubits):
                        wy = L.circuit_y + q * L.wire_spacing
                        if abs(my - wy) < L.wire_spacing // 2:
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
        L = _layout
        screen.fill(BG)

        # 타이틀
        title_surf = title_font.render(t("game_title_gate_builder"), True, SC_GLOW)
        screen.blit(title_surf, (L.W // 2 - title_surf.get_width() // 2, L.title_y))

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
            screen.blit(info_surf, (L.palette_x, L.palette_y + L.gate_size + 6))

        # ── 회로 와이어 ──────────────────────────────
        wire_end_x = L.circuit_x + max(len(qc.gates) + 2, 8) * L.gate_spacing
        for q in range(qc.num_qubits):
            wy = L.circuit_y + q * L.wire_spacing
            pygame.draw.line(screen, WIRE_COLOR, (L.circuit_x, wy), (min(wire_end_x, int(540 * L.W / 900)), wy), 2)
            # 큐비트 라벨
            q_label = small_font.render(f"q{q}: |0⟩", True, TEXT_CLR)
            screen.blit(q_label, (L.circuit_x - 38, wy - 6))

        # ── 배치된 게이트 ────────────────────────────
        for i, gate in enumerate(qc.gates):
            gx = L.circuit_x + (i + 1) * L.gate_spacing
            if gate.name == "CNOT":
                # 제어 큐비트: 점
                cy = L.circuit_y + gate.qubit * L.wire_spacing
                ty = L.circuit_y + gate.target * L.wire_spacing
                pygame.draw.line(screen, GATE_BORDER, (gx, cy), (gx, ty), 2)
                pygame.draw.circle(screen, GATE_BORDER, (gx, cy), 5)
                # 타겟 큐비트: ⊕
                pygame.draw.circle(screen, GATE_BORDER, (gx, ty), 12, 2)
                pygame.draw.line(screen, GATE_BORDER, (gx - 8, ty), (gx + 8, ty), 2)
                pygame.draw.line(screen, GATE_BORDER, (gx, ty - 8), (gx, ty + 8), 2)
            else:
                gy = L.circuit_y + gate.qubit * L.wire_spacing
                rect = pygame.Rect(gx - L.gate_size // 2, gy - L.gate_size // 2, L.gate_size, L.gate_size)
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
            screen.blit(surf, (L.hint_x, L.hint_y + i * 16))

        # 게이트 수 표시
        count_text = small_font.render(
            t("gb_gate_count", count=len(qc.gates), max=MAX_GATES), True, TEXT_CLR
        )
        screen.blit(count_text, (L.circuit_x, L.circuit_y + qc.num_qubits * L.wire_spacing + L.count_offset_y))

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


def _draw_bar_pattern(screen, rect, clr, tier):
    """막대에 패턴을 그려 색상 외에도 시각적으로 구분 (색맹 보조).

    tier: "high" → 수평선, "mid" → 대각선, "low" → 패턴 없음
    """
    bx, by, bw, bh = rect
    if bh < 4 or bw < 2:
        return
    pc = tuple(min(255, c + 60) for c in clr[:3])
    if tier == "high":
        for ly in range(by + 2, by + bh - 1, 4):
            pygame.draw.line(screen, pc, (bx, ly), (bx + bw - 1, ly))
    elif tier == "mid":
        for offset in range(-bh, bw, 5):
            x1 = max(0, offset)
            y1 = max(0, -offset)
            diag_len = min(bw - 1 - x1, bh - 1 - y1)
            if diag_len > 0:
                pygame.draw.line(screen, pc,
                                 (bx + x1, by + y1),
                                 (bx + x1 + diag_len, by + y1 + diag_len))


def _draw_prob_bars(screen, font, probs, labels):
    """확률 막대 그래프."""
    L = _layout
    x, y, w, h = L.prob_x, L.prob_y, L.prob_w, L.prob_h
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
            tier = "high" if prob > 0.3 else "mid" if prob > 0.05 else "low"
            _draw_bar_pattern(screen, (x, by, fill_w, bar_h - 2),
                              PROB_BAR, tier)
        # 라벨
        lbl = font.render(f"{label} {prob:.1%}", True, TEXT_CLR)
        screen.blit(lbl, (x + 4, by + 1))


def _draw_measure_hist(screen, font, counts, total, labels):
    """측정 히스토그램."""
    L = _layout
    x, y, w, h = L.hist_x, L.hist_y, L.hist_w, L.hist_h
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
            bar_top = y + h - 10 - bar_h_val
            pygame.draw.rect(screen, MEASURE_COLOR, (bx, bar_top, bar_w - 2, bar_h_val), border_radius=2)
            tier = "high" if c == max_count else "mid"
            _draw_bar_pattern(screen, (bx, bar_top, bar_w - 2, bar_h_val),
                              MEASURE_COLOR, tier)
        # 라벨
        lbl = font.render(labels[i], True, SUBTEXT_CLR)
        screen.blit(lbl, (bx, y + h - 8))


def _draw_bloch_sphere(screen, font, qc, qubit):
    """블로흐 구 시각화."""
    L = _layout
    cx, cy, r = L.bloch_cx, L.bloch_cy, L.bloch_r

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
