"""큐비트 연쇄 붕괴 시뮬레이션 (Pygame).

하나의 큐비트가 외부 노이즈(열·자기장)로 붕괴하면,
얽힘(Entanglement) 연결된 인접 큐비트에 +20 하중이 전파되어
연쇄적으로 무너지는 폴리브릿지 스타일 시뮬레이션.
"""

import math
import random
import sys

import pygame

# ── 화면 설정 ────────────────────────────────────────
WIDTH, HEIGHT = 900, 600
FPS = 60

# ── 색상 ─────────────────────────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (137, 180, 250)
LINK_CLR = (88, 91, 112)
LINK_ENTANGLED = (203, 166, 247)  # 얽힘 연결선

# 큐비트 상태별 색상
STATE_COLORS = {
    "stable": (166, 227, 161),     # 녹색 — 안정
    "warning": (249, 226, 175),    # 노랑 — 경고
    "danger": (250, 179, 135),     # 주황 — 위험
    "collapsed": (243, 139, 168),  # 빨강 — 붕괴
}

# ── 물리 파라미터 ────────────────────────────────────
STRESS_THRESHOLD = 100.0    # 하중 임계값 (%)
CASCADE_DAMAGE = 20.0       # 붕괴 시 인접 노드에 전파되는 추가 하중
NOISE_RATE_BASE = 3.0       # 기본 노이즈 증가율 (%/s)
RECOVERY_RATE = 5.0         # 안정화 회복율 (%/s, 마우스 클릭 시)
COLLAPSE_ANIM_DURATION = 0.5  # 붕괴 애니메이션 시간 (초)

# ── QEC 방어막 (미션3: 3-3 모듈 통합) ─────────────────
QEC_REDUCTION_DEFAULT = 0.2   # 방어막 기본 감쇠 (연쇄 데미지 20% → +30 → +6)
QEC_DURATION = 5.0            # 방어막 지속 시간 (초)
QEC_COOLDOWN = 8.0            # 방어막 재사용 대기 시간 (초)
HEAL_AMOUNT = 20.0            # 힐링량
HEAL_COOLDOWN_SEC = 3.0       # 힐링 재사용 대기
SHIELD_CLR = (137, 180, 250)
SHIELD_GLOW = (116, 199, 236)

NODE_RADIUS = 28
PULSE_MAX = 8  # 글로우 펄스 최대 크기


# ── 큐비트 노드 클래스 ───────────────────────────────

class QubitNode:
    """초전도 큐비트 노드."""

    def __init__(self, qid: int, x: float, y: float):
        self.qid = qid
        self.x = x
        self.y = y
        self.stress = 0.0          # 현재 하중 (%)
        self.collapsed = False
        self.collapse_timer = 0.0  # 붕괴 애니메이션 타이머
        self.neighbors: list["QubitNode"] = []

    @property
    def state(self) -> str:
        if self.collapsed:
            return "collapsed"
        if self.stress >= 85:
            return "danger"
        if self.stress >= 50:
            return "warning"
        return "stable"

    def add_neighbor(self, other: "QubitNode"):
        if other not in self.neighbors:
            self.neighbors.append(other)
            other.neighbors.append(self)

    def apply_noise(self, amount: float):
        """외부 노이즈(열/자기장)를 하중으로 적용."""
        if not self.collapsed:
            self.stress = min(self.stress + amount, STRESS_THRESHOLD + 50)

    def stabilize(self, amount: float):
        """사용자가 클릭하여 하중 회복."""
        if not self.collapsed:
            self.stress = max(self.stress - amount, 0.0)

    def check_collapse(self, cascade_damage: float = CASCADE_DAMAGE) -> bool:
        """하중이 임계값을 넘으면 붕괴 → 인접 노드에 데미지 전파."""
        if self.collapsed:
            return False
        if self.stress >= STRESS_THRESHOLD:
            self.collapsed = True
            self.collapse_timer = COLLAPSE_ANIM_DURATION
            # 얽힘 연쇄: neighbors에 cascade_damage 부여
            for nb in self.neighbors:
                if not nb.collapsed:
                    nb.apply_noise(cascade_damage)
            return True
        return False

    def reset(self):
        self.stress = 0.0
        self.collapsed = False
        self.collapse_timer = 0.0


# ── 네트워크 빌더 ────────────────────────────────────

def _build_network() -> list[QubitNode]:
    """큐비트 네트워크 생성 (육각형 + 중앙)."""
    cx, cy = WIDTH // 2, HEIGHT // 2 + 20
    ring_r = 150
    nodes: list[QubitNode] = []

    # 중앙 노드
    center = QubitNode(0, cx, cy)
    nodes.append(center)

    # 외곽 6개 노드
    for i in range(6):
        angle = math.radians(60 * i - 90)
        nx = cx + ring_r * math.cos(angle)
        ny = cy + ring_r * math.sin(angle)
        node = QubitNode(i + 1, nx, ny)
        nodes.append(node)

    # 연결: 중앙 ↔ 외곽, 외곽 ↔ 인접 외곽
    for i in range(1, 7):
        center.add_neighbor(nodes[i])
        next_i = (i % 6) + 1
        nodes[i].add_neighbor(nodes[next_i])

    return nodes


# ── 그리기 헬퍼 ──────────────────────────────────────

def _draw_link(screen, a: QubitNode, b: QubitNode):
    """큐비트 간 얽힘 연결선."""
    color = LINK_ENTANGLED if (a.collapsed or b.collapsed) else LINK_CLR
    width = 3 if (a.collapsed or b.collapsed) else 1
    pygame.draw.line(screen, color, (int(a.x), int(a.y)), (int(b.x), int(b.y)), width)


def _draw_node(screen, node: QubitNode, t: float, font: pygame.font.Font,
               shield_active: bool = False):
    """큐비트 노드 렌더링."""
    color = STATE_COLORS[node.state]
    cx, cy = int(node.x), int(node.y)

    # 붕괴 애니메이션: 진동
    if node.collapsed and node.collapse_timer > 0:
        shake = int(4 * math.sin(t * 40))
        cx += shake

    # QEC 방어막 글로우 (미션3)
    if shield_active and not node.collapsed:
        pulse_s = int(6 + 4 * math.sin(t * 4))
        glow_surf = pygame.Surface((2 * (NODE_RADIUS + pulse_s), 2 * (NODE_RADIUS + pulse_s)), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*SHIELD_GLOW, 40),
                           (NODE_RADIUS + pulse_s, NODE_RADIUS + pulse_s), NODE_RADIUS + pulse_s)
        screen.blit(glow_surf, (cx - NODE_RADIUS - pulse_s, cy - NODE_RADIUS - pulse_s))

    # 글로우 펄스 (stress 비례)
    if not node.collapsed:
        pulse = int(PULSE_MAX * (node.stress / STRESS_THRESHOLD))
        if pulse > 0:
            glow_surf = pygame.Surface((2 * (NODE_RADIUS + pulse), 2 * (NODE_RADIUS + pulse)), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*color, 50), (NODE_RADIUS + pulse, NODE_RADIUS + pulse), NODE_RADIUS + pulse)
            screen.blit(glow_surf, (cx - NODE_RADIUS - pulse, cy - NODE_RADIUS - pulse))

    # 본체 원
    pygame.draw.circle(screen, color, (cx, cy), NODE_RADIUS)
    pygame.draw.circle(screen, TEXT_CLR, (cx, cy), NODE_RADIUS, 2)

    # 하중 텍스트
    pct_text = "X" if node.collapsed else f"{int(node.stress)}%"
    surf = font.render(pct_text, True, BG if not node.collapsed else (255, 255, 255))
    screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))

    # ID 라벨
    id_surf = font.render(f"Q{node.qid}", True, TEXT_CLR)
    screen.blit(id_surf, (cx - id_surf.get_width() // 2, cy + NODE_RADIUS + 4))


def _draw_stress_bar(screen, node: QubitNode, font: pygame.font.Font, x: int, y: int):
    """개별 큐비트 하중 바."""
    bar_w, bar_h = 90, 10
    label = font.render(f"Q{node.qid}", True, TEXT_CLR)
    screen.blit(label, (x, y))

    bar_x = x + 30
    pygame.draw.rect(screen, (69, 71, 90), (bar_x, y + 2, bar_w, bar_h))
    fill_w = int(bar_w * min(node.stress, 100) / 100)
    color = STATE_COLORS[node.state]
    pygame.draw.rect(screen, color, (bar_x, y + 2, fill_w, bar_h))
    pygame.draw.rect(screen, TEXT_CLR, (bar_x, y + 2, bar_w, bar_h), 1)


# ── 메인 시뮬레이션 ──────────────────────────────────

def run_simulation():
    """Pygame 시뮬레이션 실행."""
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Qubit Entanglement Cascade")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 12)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)
    info_font = pygame.font.SysFont("Consolas", 11)

    nodes = _build_network()
    noise_rate = NOISE_RATE_BASE
    cascade_damage = CASCADE_DAMAGE  # 런타임 조절 가능한 연쇄 데미지
    t = 0.0
    paused = False
    cascade_log: list[str] = []  # 최근 이벤트 로그

    # ── QEC 방어막 + 힐링 (미션3: 3-3 통합) ──
    shield_active = False
    shield_timer = 0.0
    cooldown_timer = 0.0
    qec_reduction = QEC_REDUCTION_DEFAULT
    heal_cooldown = 0.0
    qec_uses = 0

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
                elif event.key == pygame.K_r:
                    # 전체 리셋
                    for n in nodes:
                        n.reset()
                    cascade_log.clear()
                    noise_rate = NOISE_RATE_BASE
                    cascade_damage = CASCADE_DAMAGE
                    shield_active = False
                    shield_timer = 0.0
                    cooldown_timer = 0.0
                    heal_cooldown = 0.0
                    qec_uses = 0
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_UP:
                    noise_rate = min(noise_rate + 1.0, 20.0)
                elif event.key == pygame.K_DOWN:
                    noise_rate = max(noise_rate - 1.0, 0.0)
                elif event.key == pygame.K_RIGHT:
                    cascade_damage = min(cascade_damage + 5.0, 80.0)
                elif event.key == pygame.K_LEFT:
                    cascade_damage = max(cascade_damage - 5.0, 0.0)
                elif event.key == pygame.K_s:
                    # QEC 방어막 활성화 (미션3)
                    if not shield_active and cooldown_timer <= 0:
                        shield_active = True
                        shield_timer = QEC_DURATION
                        qec_uses += 1
                        cascade_log.append("QEC SHIELD ON!")
                elif event.key == pygame.K_h:
                    # 힐링 (미션3)
                    if heal_cooldown <= 0:
                        for n in nodes:
                            if not n.collapsed:
                                n.stress = max(n.stress - HEAL_AMOUNT, 0.0)
                        heal_cooldown = HEAL_COOLDOWN_SEC
                        cascade_log.append(f"HEAL! All -{int(HEAL_AMOUNT)} stress")
                elif event.key == pygame.K_n:
                    # 랜덤 큐비트에 즉시 큰 노이즈 주입
                    alive = [n for n in nodes if not n.collapsed]
                    if alive:
                        target = random.choice(alive)
                        target.apply_noise(40.0)
                        cascade_log.append(f"Q{target.qid} +40 noise!")
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                for n in nodes:
                    if math.hypot(mx - n.x, my - n.y) <= NODE_RADIUS:
                        # 클릭: 오류 정정 — stress를 0으로 치료
                        if not n.collapsed:
                            n.stress = 0.0
                            cascade_log.append(f"Q{n.qid} 오류 정정! (stress → 0)")
                        break

        # ── 물리 업데이트 ────────────────────────────
        if not paused:
            # QEC 방어막 타이머 (미션3)
            if shield_active:
                shield_timer -= dt
                if shield_timer <= 0:
                    shield_active = False
                    shield_timer = 0.0
                    cooldown_timer = QEC_COOLDOWN
                    cascade_log.append("QEC SHIELD OFF")

            if cooldown_timer > 0:
                cooldown_timer -= dt
                if cooldown_timer < 0:
                    cooldown_timer = 0.0

            if heal_cooldown > 0:
                heal_cooldown -= dt
                if heal_cooldown < 0:
                    heal_cooldown = 0.0

            # 노이즈 감쇠 — 방어막이 켜져 있으면 노이즈 축소
            noise_mult = qec_reduction if shield_active else 1.0

            for n in nodes:
                if not n.collapsed:
                    # 무작위 노이즈 (열·자기장 환경)
                    noise = noise_rate * dt * (0.5 + random.random()) * noise_mult
                    n.apply_noise(noise)

                # 붕괴 애니메이션 타이머
                if n.collapse_timer > 0:
                    n.collapse_timer -= dt

            # 붕괴 체크 (연쇄 가능하므로 여러 라운드)
            # 방어막 ON → 연쇄 데미지도 감쇠 (예: +30 → +6)
            effective_cascade = cascade_damage * (qec_reduction if shield_active else 1.0)
            changed = True
            while changed:
                changed = False
                for n in nodes:
                    if n.check_collapse(effective_cascade):
                        changed = True
                        if shield_active:
                            cascade_log.append(
                                f"Q{n.qid} COLLAPSED → +{int(effective_cascade)} (shielded from +{int(cascade_damage)})")
                        else:
                            cascade_log.append(
                                f"Q{n.qid} COLLAPSED → cascade +{int(cascade_damage)} to neighbors")

        # 로그 길이 제한
        if len(cascade_log) > 8:
            cascade_log = cascade_log[-8:]

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 방어막 배경 글로우 (미션3)
        if shield_active:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            alpha = int(12 + 8 * math.sin(t * 3))
            overlay.fill((*SHIELD_GLOW, alpha))
            screen.blit(overlay, (0, 0))

        # 타이틀
        title_surf = title_font.render("Qubit Entanglement Cascade", True, ACCENT)
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 12))

        # 얽힘 연결선
        drawn_pairs = set()
        for n in nodes:
            for nb in n.neighbors:
                pair = tuple(sorted((n.qid, nb.qid)))
                if pair not in drawn_pairs:
                    _draw_link(screen, n, nb)
                    drawn_pairs.add(pair)

        # 큐비트 노드
        for n in nodes:
            _draw_node(screen, n, t, font, shield_active)

        # 하중 바 패널
        panel_x, panel_y = 15, 50
        panel_label = info_font.render("── Stress ──", True, ACCENT)
        screen.blit(panel_label, (panel_x, panel_y - 16))
        for i, n in enumerate(nodes):
            _draw_stress_bar(screen, n, font, panel_x, panel_y + i * 18)

        # 이벤트 로그
        log_x = 15
        log_y = panel_y + len(nodes) * 18 + 20
        log_label = info_font.render("── Event Log ──", True, ACCENT)
        screen.blit(log_label, (log_x, log_y - 16))
        for i, msg in enumerate(cascade_log):
            clr = (243, 139, 168) if "COLLAPSED" in msg else TEXT_CLR
            surf = info_font.render(msg, True, clr)
            screen.blit(surf, (log_x, log_y + i * 15))

        # 방어막 상태 HUD (미션3)
        hud_x, hud_y = 720, 50
        if shield_active:
            shield_txt = info_font.render(f"SHIELD ON ({shield_timer:.1f}s)", True, SHIELD_GLOW)
            screen.blit(shield_txt, (hud_x, hud_y))
            dmg_txt = info_font.render(f"cascade: +{int(cascade_damage)} → +{int(cascade_damage * qec_reduction)}", True, SHIELD_CLR)
            screen.blit(dmg_txt, (hud_x, hud_y + 16))
        elif cooldown_timer > 0:
            cd_txt = info_font.render(f"Shield CD: {cooldown_timer:.1f}s", True, (249, 226, 175))
            screen.blit(cd_txt, (hud_x, hud_y))
        else:
            ready_txt = info_font.render("Shield: READY (S)", True, (166, 227, 161))
            screen.blit(ready_txt, (hud_x, hud_y))

        if heal_cooldown > 0:
            heal_txt = info_font.render(f"Heal CD: {heal_cooldown:.1f}s", True, (249, 226, 175))
        else:
            heal_txt = info_font.render("Heal: READY (H)", True, (166, 227, 161))
        screen.blit(heal_txt, (hud_x, hud_y + 32))

        # 조작 안내
        hints = [
            f"노이즈: {noise_rate:.1f}%/s  |  연쇄: +{int(cascade_damage)}  |  {'SHIELD' if shield_active else ''}  |  {'일시정지' if paused else '실행 중'}",
            "클릭: 오류 정정  |  N: 노이즈  |  S: 방어막  |  H: 힐링(-20)",
            "↑↓: 노이즈 속도  |  ←→: 연쇄 데미지  |  SPACE: 일시정지",
            "R: 전체 리셋  |  ESC: 종료",
        ]
        for i, hint in enumerate(hints):
            surf = info_font.render(hint, True, TEXT_CLR)
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 70 + i * 16))

        # 전체 붕괴 판정
        all_collapsed = all(n.collapsed for n in nodes)
        if all_collapsed:
            over_surf = title_font.render("ALL QUBITS COLLAPSED — Press R to reset", True, (243, 139, 168))
            screen.blit(over_surf, (WIDTH // 2 - over_surf.get_width() // 2, HEIGHT // 2 - 80))

        pygame.display.flip()

    # 최종미션: 플레이 기록 저장
    try:
        from data_ai.play_logger import get_logger
        get_logger().log_session("qubit_chain", {
            "total_qubits": len(nodes),
            "collapsed_count": sum(1 for n in nodes if n.collapsed),
            "alive_count": sum(1 for n in nodes if not n.collapsed),
            "noise_rate": noise_rate,
            "cascade_damage": cascade_damage,
            "shield_uses": qec_uses,
            "max_stress": max((n.stress for n in nodes), default=0),
        })
    except Exception:
        pass

    pygame.quit()


def open_qubit_chain():
    """외부에서 호출하는 진입점."""
    run_simulation()
