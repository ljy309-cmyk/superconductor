"""양자 오류 정정 (QEC 방어막) 시뮬레이션 (Pygame).

- 큐비트 네트워크에 노이즈가 지속적으로 누적
- 특정 키 입력(Q) 시 일정 시간 동안 노이즈를 절반으로 감소 (QEC 방어막)
- 방어막 없이 버티기 vs 방어막으로 수명 연장 비교
"""

import math
import random

import pygame

from config_loader import cfg
from theme import get_pg_theme
from ui.slider import SliderPanel, PANEL_W
from preset_hud import PresetHUD
from help_overlay import HelpOverlay
from sound_manager import get_sound_manager
from achievements import check_achievements
from replay import ReplayRecorder
from logger import get_module_logger

_log = get_module_logger("qec_shield")

# ── 화면 설정 ────────────────────────────────────────
WIDTH, HEIGHT = 900, 600
FPS = cfg("display", "fps", 60)

# ── 색상 (테마에서 동적 로드) ─────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (203, 166, 247)
SHIELD_CLR = (137, 180, 250)
SHIELD_GLOW = (116, 199, 236)
STABLE_CLR = (166, 227, 161)
WARNING_CLR = (249, 226, 175)
COLLAPSED_CLR = (243, 139, 168)
PANEL_BG = (24, 24, 37)


def _load_theme_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    global BG, TEXT_CLR, ACCENT, SHIELD_CLR, SHIELD_GLOW
    global STABLE_CLR, WARNING_CLR, COLLAPSED_CLR, PANEL_BG
    pg = get_pg_theme()
    BG = pg.BG
    TEXT_CLR = pg.TEXT
    ACCENT = pg.ACCENT_PURPLE
    SHIELD_CLR = pg.SHIELD_CLR
    SHIELD_GLOW = pg.SHIELD_GLOW
    STABLE_CLR = pg.STABLE
    WARNING_CLR = pg.WARNING
    COLLAPSED_CLR = pg.COLLAPSED
    PANEL_BG = pg.PANEL_BG
    # STATE_COLORS dict도 갱신
    STATE_COLORS["stable"] = STABLE_CLR
    STATE_COLORS["warning"] = WARNING_CLR
    STATE_COLORS["collapsed"] = COLLAPSED_CLR

# ── 물리 파라미터 (config.json에서 로드) ──────────────
NOISE_RATE = cfg("qec_shield", "noise_rate", 5.0)
QEC_REDUCTION_DEFAULT = cfg("qec_shield", "qec_reduction_default", 0.5)
QEC_REDUCTION_MIN = cfg("qec_shield", "qec_reduction_min", 0.0)
QEC_REDUCTION_MAX = cfg("qec_shield", "qec_reduction_max", 1.0)
QEC_REDUCTION_STEP = 0.1
QEC_DURATION = cfg("qec_shield", "qec_duration", 5.0)
QEC_COOLDOWN = cfg("qec_shield", "qec_cooldown", 8.0)
HEAL_AMOUNT = cfg("qec_shield", "heal_amount", 20.0)
STRESS_THRESHOLD = cfg("qec_shield", "stress_threshold", 100.0)
CASCADE_DAMAGE = cfg("qec_shield", "cascade_damage", 15.0)

NODE_RADIUS = 30
GRID_COLS = cfg("qec_shield", "grid_cols", 5)
GRID_ROWS = cfg("qec_shield", "grid_rows", 3)


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

    def check_collapse(self, damage_mult: float = 1.0, base_damage: float = 0) -> bool:
        if self.collapsed:
            return False
        if self.stress >= STRESS_THRESHOLD:
            self.collapsed = True
            dmg = (base_damage if base_damage > 0 else CASCADE_DAMAGE) * damage_mult
            for nb in self.neighbors:
                if not nb.collapsed:
                    nb.apply_noise(dmg)
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


def _draw_shield_hud(screen, shield_active: bool, shield_timer: float,
                     cooldown_timer: float, qec_reduction: float,
                     heal_cooldown: float, font, big_font):
    """QEC 방어막 상태 HUD."""
    hud_x, hud_y = 660, 120
    hud_w, hud_h = 210, 260

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

        # 감쇠 계수 표시 — 0.0이면 무적, 1.0이면 무효
        if qec_reduction == 0.0:
            label = "INVINCIBLE"
            clr = SHIELD_GLOW
        elif qec_reduction < 0.5:
            label = f"Noise x{qec_reduction:.1f} (강력)"
            clr = STABLE_CLR
        elif qec_reduction == 0.5:
            label = f"Noise x{qec_reduction:.1f} (기본)"
            clr = STABLE_CLR
        else:
            label = f"Noise x{qec_reduction:.1f} (약함)"
            clr = WARNING_CLR
        effect = font.render(label, True, clr)
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

        prompt = font.render("S 키를 눌러 활성화", True, TEXT_CLR)
        screen.blit(prompt, (hud_x + hud_w // 2 - prompt.get_width() // 2, hud_y + 70))

    # ── 감쇠 계수 조절 표시 ──
    adj_y = hud_y + 140
    adj_label = font.render(f"감쇠 계수: x{qec_reduction:.1f}", True, TEXT_CLR)
    screen.blit(adj_label, (hud_x + 20, adj_y))
    adj_hint = font.render("←→ 키로 조절", True, (88, 91, 112))
    screen.blit(adj_hint, (hud_x + 20, adj_y + 16))

    # ── 힐링 상태 ──
    heal_y = adj_y + 40
    if heal_cooldown > 0:
        heal_txt = font.render(f"Heal: {heal_cooldown:.1f}s 대기", True, WARNING_CLR)
    else:
        heal_txt = font.render("Heal: READY (H키)", True, STABLE_CLR)
    screen.blit(heal_txt, (hud_x + 20, heal_y))

    heal_desc = font.render(f"회복량: -{int(HEAL_AMOUNT)} stress", True, (88, 91, 112))
    screen.blit(heal_desc, (hud_x + 20, heal_y + 16))


def _draw_scoreboard(screen, elapsed: float, alive_count: int, total: int,
                     qec_uses: int, heal_uses: int, font):
    """경과 시간 · 생존 큐비트 수 · QEC/Heal 사용 횟수."""
    sx, sy = 660, 400
    lines = [
        ("경과 시간", f"{elapsed:.1f}s"),
        ("생존 큐비트", f"{alive_count} / {total}"),
        ("QEC 사용", f"{qec_uses}회"),
        ("Heal 사용", f"{heal_uses}회"),
    ]
    for i, (label, value) in enumerate(lines):
        lbl = font.render(f"{label}:", True, (88, 91, 112))
        val = font.render(value, True, TEXT_CLR)
        screen.blit(lbl, (sx, sy + i * 22))
        screen.blit(val, (sx + 100, sy + i * 22))


# ── 메인 시뮬레이션 ──────────────────────────────────

def run_simulation():
    _load_theme_colors()
    pygame.init()
    screen = pygame.display.set_mode((WIDTH + PANEL_W, HEIGHT))
    pygame.display.set_caption("Quantum Error Correction Shield")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 12)
    big_font = pygame.font.SysFont("Consolas", 16, bold=True)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)

    nodes = _build_grid()
    total = len(nodes)

    # ── 슬라이더 패널 ─────────────────────────────────
    spanel = SliderPanel(WIDTH + 5, 40, PANEL_W - 10, "Parameters")
    sl_reduction = spanel.add(QEC_REDUCTION_MIN, QEC_REDUCTION_MAX, QEC_REDUCTION_DEFAULT, 0.1, "QEC Reduction", ".1f")
    sl_noise = spanel.add(1.0, 15.0, NOISE_RATE, 0.5, "Noise Rate", ".1f")
    sl_cascade = spanel.add(5.0, 40.0, CASCADE_DAMAGE, 5.0, "Cascade Dmg", ".0f")

    # ── 프리셋 HUD ──
    slider_map = {
        ("qec_shield", "qec_reduction_default"): sl_reduction,
        ("qec_shield", "noise_rate"): sl_noise,
        ("qec_shield", "cascade_damage"): sl_cascade,
    }
    preset_hud = PresetHUD("qec_shield", slider_map)
    help_overlay = HelpOverlay("qec_shield")

    # ── 사운드 ──
    snd = get_sound_manager()
    snd.init()

    # ── 리플레이 ──
    recorder = ReplayRecorder("qec_shield")

    shield_active = False
    shield_timer = 0.0
    cooldown_timer = 0.0
    heal_cooldown = 0.0
    HEAL_COOLDOWN_SEC = cfg("qec_shield", "heal_cooldown", 3.0)
    qec_uses = 0
    heal_uses = 0
    elapsed = 0.0
    paused = False
    t = 0.0

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt

        # ── 이벤트 ───────────────────────────────────
        for event in pygame.event.get():
            spanel.handle_event(event)
            preset_hud.handle_event(event)
            help_overlay.handle_event(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_s:
                    # QEC 방어막 활성화 (S = Shield)
                    if not shield_active and cooldown_timer <= 0:
                        shield_active = True
                        shield_timer = QEC_DURATION
                        qec_uses += 1
                        snd.play("shield_on")
                elif event.key == pygame.K_h:
                    # 미션2: 힐링 — 모든 생존 큐비트 stress -20
                    if heal_cooldown <= 0:
                        for n in nodes:
                            if not n.collapsed:
                                n.stress = max(n.stress - HEAL_AMOUNT, 0.0)
                        heal_uses += 1
                        heal_cooldown = HEAL_COOLDOWN_SEC
                        snd.play("heal")
                elif event.key == pygame.K_LEFT:
                    sl_reduction.value = sl_reduction.value - QEC_REDUCTION_STEP
                elif event.key == pygame.K_RIGHT:
                    sl_reduction.value = sl_reduction.value + QEC_REDUCTION_STEP
                elif event.key == pygame.K_r:
                    for n in nodes:
                        n.reset()
                    spanel.reset_all()
                    shield_active = False
                    shield_timer = 0.0
                    cooldown_timer = 0.0
                    heal_cooldown = 0.0
                    qec_uses = 0
                    heal_uses = 0
                    elapsed = 0.0
                elif event.key == pygame.K_SPACE:
                    paused = not paused

        # ── 슬라이더 값 읽기 ─────────────────────────
        qec_reduction = sl_reduction.value

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

            # 힐링 쿨다운
            if heal_cooldown > 0:
                heal_cooldown -= dt
                if heal_cooldown < 0:
                    heal_cooldown = 0.0

            # 노이즈 적용 — 슬라이더로 조절 가능
            noise_mult = qec_reduction if shield_active else 1.0
            cur_noise_rate = sl_noise.value
            for n in nodes:
                if not n.collapsed:
                    noise = cur_noise_rate * dt * (0.5 + random.random()) * noise_mult
                    n.apply_noise(noise)

            # 붕괴 체크 (연쇄) — 방어막 시 연쇄 데미지도 감쇠
            cascade_mult = qec_reduction if shield_active else 1.0
            cur_cascade = sl_cascade.value
            changed = True
            while changed:
                changed = False
                for n in nodes:
                    if n.check_collapse(cascade_mult, cur_cascade):
                        changed = True
                        snd.play("collapse")

            # ── 프리셋 HUD 업데이트 ──
            preset_hud.update(dt)

            # ── 리플레이 기록 ──
            recorder.record({
                "elapsed": round(elapsed, 2),
                "shield_active": shield_active,
                "alive": sum(1 for n in nodes if not n.collapsed),
                "stresses": [round(n.stress, 1) for n in nodes],
            })

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
        _draw_shield_hud(screen, shield_active, shield_timer, cooldown_timer,
                         qec_reduction, heal_cooldown, font, big_font)

        alive_count = sum(1 for n in nodes if not n.collapsed)
        _draw_scoreboard(screen, elapsed, alive_count, total, qec_uses, heal_uses, font)

        # 전체 붕괴
        if alive_count == 0:
            over = title_font.render("ALL QUBITS COLLAPSED — Press R to reset", True, COLLAPSED_CLR)
            screen.blit(over, (WIDTH // 2 - over.get_width() // 2, HEIGHT // 2 - 60))
            final = big_font.render(f"생존 시간: {elapsed:.1f}s  |  QEC 사용: {qec_uses}회", True, TEXT_CLR)
            screen.blit(final, (WIDTH // 2 - final.get_width() // 2, HEIGHT // 2 - 30))

        # 슬라이더 패널 그리기
        spanel.draw(screen, font)

        # 안내
        hints = [
            f"감쇠: x{qec_reduction:.1f}  |  {'SHIELD ON' if shield_active else 'SHIELD OFF'}  |  {'일시정지' if paused else '실행 중'}",
            "S: 방어막  |  H: 힐링  |  ←→: 감쇠  |  우측 패널: 슬라이더",
            "SPACE: 일시정지  |  R: 전체 리셋  |  ESC: 종료",
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 40 + i * 16))

        preset_hud.draw(screen, font, 10, 50)
        help_overlay.draw(screen, font)

        pygame.display.flip()

    # 최종미션: 플레이 기록 저장 + 보고서 생성 + 랭킹 자동 등록
    session_data = {
        "survival_time": round(elapsed, 1),
        "alive_count": sum(1 for n in nodes if not n.collapsed),
        "total_qubits": total,
        "qec_uses": qec_uses,
        "heal_uses": heal_uses,
        "qec_reduction": qec_reduction,
    }
    try:
        from data_ai.play_logger import get_logger
        get_logger().log_session("qec_shield", session_data)
    except Exception as e:
        _log.error("플레이 기록 실패: %s", e)

    try:
        check_achievements("qec_shield", {
            "survival_time": round(elapsed, 1),
            "qec_uses": qec_uses,
        })
    except Exception as e:
        _log.error("업적 확인 실패: %s", e)

    # 보고서 자동 생성
    try:
        from report import generate_report
        generate_report("qec_shield", session_data)
    except Exception as e:
        _log.error("보고서 생성 실패: %s", e)

    # 랭킹 자동 등록 (생존 시간 기반)
    try:
        import requests
        from data_ai.ranking_server import start_server, get_base_url
        start_server()
        requests.post(f"{get_base_url()}/ranking", json={
            "name": "QEC Player",
            "score": round(elapsed, 2),
            "mode": "QEC Shield",
        }, timeout=2)
    except Exception as e:
        _log.error("랭킹 등록 실패: %s", e)

    recorder.save({"survival_time": round(elapsed, 1)})
    snd.quit()

    pygame.quit()


def open_qec_shield():
    """외부에서 호출하는 진입점."""
    run_simulation()
