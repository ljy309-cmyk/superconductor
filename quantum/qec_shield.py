"""양자 오류 정정 (QEC 방어막) 시뮬레이션 (Pygame).

- 큐비트 네트워크에 노이즈가 지속적으로 누적
- 특정 키 입력(Q) 시 일정 시간 동안 노이즈를 절반으로 감소 (QEC 방어막)
- 방어막 없이 버티기 vs 방어막으로 수명 연장 비교
"""

import math
import random

import pygame

# ── 화면 설정 ────────────────────────────────────────
WIDTH, HEIGHT = 900, 600
FPS = 60

# ── 색상 ─────────────────────────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (203, 166, 247)
SHIELD_CLR = (137, 180, 250)   # 방어막 파랑
SHIELD_GLOW = (116, 199, 236)  # 방어막 활성 글로우
STABLE_CLR = (166, 227, 161)
WARNING_CLR = (249, 226, 175)
COLLAPSED_CLR = (243, 139, 168)
PANEL_BG = (24, 24, 37)

# ── 물리 파라미터 ────────────────────────────────────
NOISE_RATE = 5.0              # 기본 노이즈 증가율 (%/s)
QEC_REDUCTION = 0.5           # QEC 활성 시 노이즈 배율 (절반)
QEC_DURATION = 5.0            # QEC 방어막 지속 시간 (초)
QEC_COOLDOWN = 8.0            # QEC 재사용 대기 시간 (초)
STRESS_THRESHOLD = 100.0
CASCADE_DAMAGE = 15.0

NODE_RADIUS = 30
GRID_COLS, GRID_ROWS = 5, 3   # 큐비트 격자


# ── 큐비트 노드 ──────────────────────────────────────

class QECQubit:
    """QEC 보호 대상 큐비트."""

    def __init__(self, qid: int, x: float, y: float):
        self.qid = qid
        self.x = x
        self.y = y
        self.stress = 0.0
        self.collapsed = False
        self.neighbors: list["QECQubit"] = []

    @property
    def state(self) -> str:
        if self.collapsed:
            return "collapsed"
        if self.stress >= 70:
            return "warning"
        return "stable"

    def add_neighbor(self, other: "QECQubit"):
        if other not in self.neighbors:
            self.neighbors.append(other)
            other.neighbors.append(self)

    def apply_noise(self, amount: float):
        if not self.collapsed:
            self.stress = min(self.stress + amount, 150.0)

    def check_collapse(self) -> bool:
        if self.collapsed:
            return False
        if self.stress >= STRESS_THRESHOLD:
            self.collapsed = True
            for nb in self.neighbors:
                if not nb.collapsed:
                    nb.apply_noise(CASCADE_DAMAGE)
            return True
        return False

    def reset(self):
        self.stress = 0.0
        self.collapsed = False


# ── 네트워크 빌더 ────────────────────────────────────

def _build_grid() -> list[QECQubit]:
    """5x3 격자 큐비트 네트워크."""
    nodes: list[QECQubit] = []
    ox, oy = 200, 140
    gap_x, gap_y = 110, 110

    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            qid = r * GRID_COLS + c
            x = ox + c * gap_x
            y = oy + r * gap_y
            nodes.append(QECQubit(qid, x, y))

    # 인접 연결 (상하좌우)
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            idx = r * GRID_COLS + c
            if c + 1 < GRID_COLS:
                nodes[idx].add_neighbor(nodes[idx + 1])
            if r + 1 < GRID_ROWS:
                nodes[idx].add_neighbor(nodes[idx + GRID_COLS])

    return nodes


# ── 그리기 헬퍼 ──────────────────────────────────────

STATE_COLORS = {
    "stable": STABLE_CLR,
    "warning": WARNING_CLR,
    "collapsed": COLLAPSED_CLR,
}


def _draw_link(screen, a: QECQubit, b: QECQubit):
    color = (88, 91, 112)
    if a.collapsed or b.collapsed:
        color = COLLAPSED_CLR
    pygame.draw.line(screen, color, (int(a.x), int(a.y)), (int(b.x), int(b.y)), 1)


def _draw_node(screen, node: QECQubit, font, shield_active: bool, t: float):
    cx, cy = int(node.x), int(node.y)
    color = STATE_COLORS[node.state]

    # QEC 방어막 글로우 (활성 상태일 때 안정 큐비트에만)
    if shield_active and not node.collapsed:
        pulse = int(6 + 4 * math.sin(t * 4))
        glow_surf = pygame.Surface((2 * (NODE_RADIUS + pulse), 2 * (NODE_RADIUS + pulse)), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*SHIELD_GLOW, 40), (NODE_RADIUS + pulse, NODE_RADIUS + pulse), NODE_RADIUS + pulse)
        screen.blit(glow_surf, (cx - NODE_RADIUS - pulse, cy - NODE_RADIUS - pulse))

    # 본체
    pygame.draw.circle(screen, color, (cx, cy), NODE_RADIUS)
    pygame.draw.circle(screen, TEXT_CLR, (cx, cy), NODE_RADIUS, 2)

    # 하중 텍스트
    txt = "X" if node.collapsed else f"{int(node.stress)}%"
    surf = font.render(txt, True, BG if not node.collapsed else (255, 255, 255))
    screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))


def _draw_shield_hud(screen, shield_active: bool, shield_timer: float, cooldown_timer: float, font, big_font):
    """QEC 방어막 상태 HUD."""
    hud_x, hud_y = 660, 140
    hud_w, hud_h = 210, 180

    pygame.draw.rect(screen, PANEL_BG, (hud_x, hud_y, hud_w, hud_h), border_radius=8)
    pygame.draw.rect(screen, ACCENT, (hud_x, hud_y, hud_w, hud_h), 2, border_radius=8)

    title = big_font.render("QEC Shield", True, ACCENT)
    screen.blit(title, (hud_x + hud_w // 2 - title.get_width() // 2, hud_y + 10))

    if shield_active:
        status = big_font.render("ACTIVE", True, SHIELD_GLOW)
        screen.blit(status, (hud_x + hud_w // 2 - status.get_width() // 2, hud_y + 40))

        # 남은 시간 바
        bar_x, bar_y = hud_x + 20, hud_y + 70
        bar_w, bar_h = hud_w - 40, 16
        ratio = max(shield_timer / QEC_DURATION, 0)
        pygame.draw.rect(screen, (69, 71, 90), (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(screen, SHIELD_GLOW, (bar_x, bar_y, int(bar_w * ratio), bar_h))
        pygame.draw.rect(screen, TEXT_CLR, (bar_x, bar_y, bar_w, bar_h), 1)

        time_txt = font.render(f"{shield_timer:.1f}s remaining", True, TEXT_CLR)
        screen.blit(time_txt, (bar_x, bar_y + 20))

        effect = font.render(f"Noise x{QEC_REDUCTION} (절반)", True, STABLE_CLR)
        screen.blit(effect, (bar_x, bar_y + 38))
    elif cooldown_timer > 0:
        status = big_font.render("COOLDOWN", True, WARNING_CLR)
        screen.blit(status, (hud_x + hud_w // 2 - status.get_width() // 2, hud_y + 40))

        bar_x, bar_y = hud_x + 20, hud_y + 70
        bar_w, bar_h = hud_w - 40, 16
        ratio = max(1 - cooldown_timer / QEC_COOLDOWN, 0)
        pygame.draw.rect(screen, (69, 71, 90), (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(screen, WARNING_CLR, (bar_x, bar_y, int(bar_w * ratio), bar_h))
        pygame.draw.rect(screen, TEXT_CLR, (bar_x, bar_y, bar_w, bar_h), 1)

        time_txt = font.render(f"{cooldown_timer:.1f}s until ready", True, TEXT_CLR)
        screen.blit(time_txt, (bar_x, bar_y + 20))
    else:
        status = big_font.render("READY", True, STABLE_CLR)
        screen.blit(status, (hud_x + hud_w // 2 - status.get_width() // 2, hud_y + 40))

        prompt = font.render("Q 키를 눌러 활성화", True, TEXT_CLR)
        screen.blit(prompt, (hud_x + hud_w // 2 - prompt.get_width() // 2, hud_y + 70))


def _draw_scoreboard(screen, elapsed: float, alive_count: int, total: int, qec_uses: int, font):
    """경과 시간 · 생존 큐비트 수 · QEC 사용 횟수."""
    sx, sy = 660, 350
    lines = [
        ("경과 시간", f"{elapsed:.1f}s"),
        ("생존 큐비트", f"{alive_count} / {total}"),
        ("QEC 사용", f"{qec_uses}회"),
    ]
    for i, (label, value) in enumerate(lines):
        lbl = font.render(f"{label}:", True, (88, 91, 112))
        val = font.render(value, True, TEXT_CLR)
        screen.blit(lbl, (sx, sy + i * 22))
        screen.blit(val, (sx + 100, sy + i * 22))


# ── 메인 시뮬레이션 ──────────────────────────────────

def run_simulation():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Quantum Error Correction Shield")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 12)
    big_font = pygame.font.SysFont("Consolas", 16, bold=True)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)

    nodes = _build_grid()
    total = len(nodes)

    shield_active = False
    shield_timer = 0.0
    cooldown_timer = 0.0
    qec_uses = 0
    elapsed = 0.0
    paused = False
    t = 0.0

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt

        # ── 이벤트 ───────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_q:
                    # QEC 방어막 활성화
                    if not shield_active and cooldown_timer <= 0:
                        shield_active = True
                        shield_timer = QEC_DURATION
                        qec_uses += 1
                elif event.key == pygame.K_r:
                    for n in nodes:
                        n.reset()
                    shield_active = False
                    shield_timer = 0.0
                    cooldown_timer = 0.0
                    qec_uses = 0
                    elapsed = 0.0
                elif event.key == pygame.K_SPACE:
                    paused = not paused

        # ── 물리 업데이트 ────────────────────────────
        if not paused:
            alive = [n for n in nodes if not n.collapsed]
            if alive:
                elapsed += dt

            # QEC 타이머
            if shield_active:
                shield_timer -= dt
                if shield_timer <= 0:
                    shield_active = False
                    shield_timer = 0.0
                    cooldown_timer = QEC_COOLDOWN

            if cooldown_timer > 0:
                cooldown_timer -= dt
                if cooldown_timer < 0:
                    cooldown_timer = 0.0

            # 노이즈 적용
            noise_mult = QEC_REDUCTION if shield_active else 1.0
            for n in nodes:
                if not n.collapsed:
                    noise = NOISE_RATE * dt * (0.5 + random.random()) * noise_mult
                    n.apply_noise(noise)

            # 붕괴 체크 (연쇄)
            changed = True
            while changed:
                changed = False
                for n in nodes:
                    if n.check_collapse():
                        changed = True

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        title = title_font.render("Quantum Error Correction (QEC) Shield", True, ACCENT)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 12))

        # 방어막 활성 시 전체 배경 글로우
        if shield_active:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            alpha = int(12 + 8 * math.sin(t * 3))
            overlay.fill((*SHIELD_GLOW, alpha))
            screen.blit(overlay, (0, 0))

        # 연결선
        drawn = set()
        for n in nodes:
            for nb in n.neighbors:
                pair = tuple(sorted((n.qid, nb.qid)))
                if pair not in drawn:
                    _draw_link(screen, n, nb)
                    drawn.add(pair)

        # 큐비트
        for n in nodes:
            _draw_node(screen, n, font, shield_active, t)

        # HUD
        _draw_shield_hud(screen, shield_active, shield_timer, cooldown_timer, font, big_font)

        alive_count = sum(1 for n in nodes if not n.collapsed)
        _draw_scoreboard(screen, elapsed, alive_count, total, qec_uses, font)

        # 전체 붕괴
        if alive_count == 0:
            over = title_font.render("ALL QUBITS COLLAPSED — Press R to reset", True, COLLAPSED_CLR)
            screen.blit(over, (WIDTH // 2 - over.get_width() // 2, HEIGHT // 2 - 60))
            final = big_font.render(f"생존 시간: {elapsed:.1f}s  |  QEC 사용: {qec_uses}회", True, TEXT_CLR)
            screen.blit(final, (WIDTH // 2 - final.get_width() // 2, HEIGHT // 2 - 30))

        # 안내
        hints = [
            "Q: QEC 방어막 활성화 (노이즈 절반)  |  SPACE: 일시정지",
            "R: 전체 리셋  |  ESC: 종료",
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 40 + i * 16))

        pygame.display.flip()

    pygame.quit()


def open_qec_shield():
    """외부에서 호출하는 진입점."""
    run_simulation()
