"""큐비트 연쇄 붕괴 시뮬레이션 (Pygame).

하나의 큐비트가 외부 노이즈(열·자기장)로 붕괴하면,
얽힘(Entanglement) 연결된 인접 큐비트에 +20 하중이 전파되어
연쇄적으로 무너지는 폴리브릿지 스타일 시뮬레이션.
"""

import math
import random
import sys
import time

import pygame

from config_loader import cfg
from theme import get_pg_theme
from ui.slider import SliderPanel, PANEL_W
from preset_hud import PresetHUD
from help_overlay import HelpOverlay
from sound_manager import get_sound_manager
from achievements import check_achievements
from replay import ReplayRecorder
from achievement_toast import AchievementToast
from tutorial import TutorialOverlay
from logger import get_module_logger

_log = get_module_logger("qubit_chain")

# ── 화면 설정 ────────────────────────────────────────
WIDTH, HEIGHT = 900, 600
FPS = cfg("display", "fps", 60)

# ── 색상 (테마에서 동적 로드) ─────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (137, 180, 250)
LINK_CLR = (88, 91, 112)
LINK_ENTANGLED = (203, 166, 247)  # 얽힘 연결선
SHIELD_GLOW = (116, 199, 236)

# 큐비트 상태별 색상
STATE_COLORS = {
    "stable": (166, 227, 161),     # 녹색 — 안정
    "warning": (249, 226, 175),    # 노랑 — 경고
    "danger": (250, 179, 135),     # 주황 — 위험
    "collapsed": (243, 139, 168),  # 빨강 — 붕괴
}


def _load_theme_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    global BG, TEXT_CLR, ACCENT, LINK_CLR, LINK_ENTANGLED, STATE_COLORS, SHIELD_GLOW
    pg = get_pg_theme()
    BG = pg.BG
    TEXT_CLR = pg.TEXT
    ACCENT = pg.ACCENT_BLUE
    LINK_CLR = pg.SUBTEXT
    LINK_ENTANGLED = pg.ACCENT_PURPLE
    SHIELD_GLOW = pg.SHIELD_GLOW
    STATE_COLORS = {
        "stable": pg.STABLE,
        "warning": pg.WARNING,
        "danger": pg.DANGER,
        "collapsed": pg.COLLAPSED,
    }

# ── 물리 파라미터 (config.json에서 로드, 없으면 기본값) ──
STRESS_THRESHOLD = cfg("qubit_chain", "stress_threshold", 100.0)
CASCADE_DAMAGE = cfg("qubit_chain", "cascade_damage", 20.0)
NOISE_RATE_BASE = cfg("qubit_chain", "noise_rate_base", 3.0)
RECOVERY_RATE = cfg("qubit_chain", "recovery_rate", 5.0)
COLLAPSE_ANIM_DURATION = 0.5

# ── QEC 방어막 ──────────────────────────────────────
QEC_REDUCTION_DEFAULT = cfg("qubit_chain", "qec_reduction", 0.2)
QEC_DURATION = cfg("qubit_chain", "qec_duration", 5.0)
QEC_COOLDOWN = cfg("qubit_chain", "qec_cooldown", 8.0)
HEAL_AMOUNT = cfg("qubit_chain", "heal_amount", 20.0)
HEAL_COOLDOWN_SEC = cfg("qubit_chain", "heal_cooldown", 3.0)
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
    _load_theme_colors()
    pygame.init()
    screen = pygame.display.set_mode((WIDTH + PANEL_W, HEIGHT))
    pygame.display.set_caption("Qubit Entanglement Cascade")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 12)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)
    info_font = pygame.font.SysFont("Consolas", 11)

    nodes = _build_network()
    t = 0.0
    paused = False
    cascade_log: list[str] = []  # 최근 이벤트 로그

    # ── 슬라이더 패널 ─────────────────────────────────
    panel = SliderPanel(WIDTH + 5, 40, PANEL_W - 10, "Parameters")
    sl_noise = panel.add(0.0, 20.0, NOISE_RATE_BASE, 0.5, "Noise Rate", ".1f")
    sl_cascade = panel.add(0.0, 80.0, CASCADE_DAMAGE, 5.0, "Cascade Dmg", ".0f")
    sl_qec_dur = panel.add(1.0, 15.0, QEC_DURATION, 0.5, "QEC Duration", ".1f")
    sl_qec_cd = panel.add(1.0, 20.0, QEC_COOLDOWN, 0.5, "QEC Cooldown", ".1f")
    sl_heal = panel.add(5.0, 50.0, HEAL_AMOUNT, 5.0, "Heal Amount", ".0f")

    # ── 프리셋 HUD ──
    slider_map = {
        ("qubit_chain", "noise_rate_base"): sl_noise,
        ("qubit_chain", "cascade_damage"): sl_cascade,
        ("qubit_chain", "qec_duration"): sl_qec_dur,
        ("qubit_chain", "qec_cooldown"): sl_qec_cd,
        ("qubit_chain", "heal_amount"): sl_heal,
    }
    preset_hud = PresetHUD("qubit_chain", slider_map)
    help_overlay = HelpOverlay("qubit_chain")

    # ── 사운드 ──
    snd = get_sound_manager()
    snd.init()

    # ── 리플레이 ──
    recorder = ReplayRecorder("qubit_chain")

    # ── 업적 토스트 ──
    toast = AchievementToast()

    # ── 튜토리얼 ──
    tutorial = TutorialOverlay("qubit_chain")

    # ── QEC 방어막 + 힐링 (미션3: 3-3 통합) ──
    shield_active = False
    shield_timer = 0.0
    cooldown_timer = 0.0
    qec_reduction = QEC_REDUCTION_DEFAULT
    heal_cooldown = 0.0
    qec_uses = 0

    # 최종보스미션 (5-3): 생존 시간 측정 → 랭킹 서버 전송
    start_time = time.time()
    survival_time = 0.0
    game_over = False
    _ach_checked_milestones: set[int] = set()  # 실시간 업적 체크용 (30, 60초 등)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt

        # ── 이벤트 ───────────────────────────────────
        for event in pygame.event.get():
            if tutorial.handle_event(event):
                continue
            panel.handle_event(event)
            preset_hud.handle_event(event)
            help_overlay.handle_event(event)
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
                    panel.reset_all()
                    shield_active = False
                    shield_timer = 0.0
                    cooldown_timer = 0.0
                    heal_cooldown = 0.0
                    qec_uses = 0
                    start_time = time.time()
                    survival_time = 0.0
                    game_over = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_UP:
                    sl_noise.value = sl_noise.value + 1.0
                elif event.key == pygame.K_DOWN:
                    sl_noise.value = sl_noise.value - 1.0
                elif event.key == pygame.K_RIGHT:
                    sl_cascade.value = sl_cascade.value + 5.0
                elif event.key == pygame.K_LEFT:
                    sl_cascade.value = sl_cascade.value - 5.0
                elif event.key == pygame.K_s:
                    # QEC 방어막 활성화 (미션3)
                    if not shield_active and cooldown_timer <= 0:
                        shield_active = True
                        shield_timer = sl_qec_dur.value
                        qec_uses += 1
                        snd.play("shield_on")
                        cascade_log.append("QEC SHIELD ON!")
                elif event.key == pygame.K_h:
                    # 힐링 (미션3)
                    if heal_cooldown <= 0:
                        heal_amt = sl_heal.value
                        for n in nodes:
                            if not n.collapsed:
                                n.stress = max(n.stress - heal_amt, 0.0)
                        heal_cooldown = HEAL_COOLDOWN_SEC
                        snd.play("heal")
                        cascade_log.append(f"HEAL! All -{int(heal_amt)} stress")
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
                            snd.play("error_correct")
                            cascade_log.append(f"Q{n.qid} 오류 정정! (stress → 0)")
                        break

        # ── 슬라이더 값 읽기 ─────────────────────────
        noise_rate = sl_noise.value
        cascade_damage = sl_cascade.value

        preset_hud.update(dt)

        # ── 물리 업데이트 ────────────────────────────
        if not paused:
            # QEC 방어막 타이머 (미션3)
            if shield_active:
                shield_timer -= dt
                if shield_timer <= 0:
                    shield_active = False
                    shield_timer = 0.0
                    cooldown_timer = sl_qec_cd.value
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
                        snd.play("collapse")
                        if shield_active:
                            cascade_log.append(
                                f"Q{n.qid} COLLAPSED → +{int(effective_cascade)} (shielded from +{int(cascade_damage)})")
                        else:
                            cascade_log.append(
                                f"Q{n.qid} COLLAPSED → cascade +{int(cascade_damage)} to neighbors")

            recorder.record_frame({
                "stresses": [n.stress for n in nodes],
                "collapsed": [n.collapsed for n in nodes],
                "shield": shield_active,
                "t": round(survival_time, 2),
            })

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
            clr = STATE_COLORS["collapsed"] if "COLLAPSED" in msg else TEXT_CLR
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
            cd_txt = info_font.render(f"Shield CD: {cooldown_timer:.1f}s", True, STATE_COLORS["warning"])
            screen.blit(cd_txt, (hud_x, hud_y))
        else:
            ready_txt = info_font.render("Shield: READY (S)", True, STATE_COLORS["stable"])
            screen.blit(ready_txt, (hud_x, hud_y))

        if heal_cooldown > 0:
            heal_txt = info_font.render(f"Heal CD: {heal_cooldown:.1f}s", True, STATE_COLORS["warning"])
        else:
            heal_txt = info_font.render("Heal: READY (H)", True, STATE_COLORS["stable"])
        screen.blit(heal_txt, (hud_x, hud_y + 32))

        # 최종보스미션: 생존 시간 표시
        time_clr = STATE_COLORS["collapsed"] if game_over else ACCENT
        time_txt = info_font.render(f"Survival: {survival_time:.1f}s", True, time_clr)
        screen.blit(time_txt, (hud_x, hud_y + 52))

        # 슬라이더 패널 그리기
        panel.draw(screen, info_font, info_font)

        # 조작 안내
        hints = [
            f"노이즈: {noise_rate:.1f}%/s  |  연쇄: +{int(cascade_damage)}  |  {'SHIELD' if shield_active else ''}  |  {'일시정지' if paused else '실행 중'}",
            "클릭: 오류 정정  |  N: 노이즈  |  S: 방어막  |  H: 힐링",
            "↑↓/←→: 파라미터 조절  |  우측 패널: 슬라이더  |  SPACE: 일시정지",
            "R: 전체 리셋  |  ESC: 종료",
        ]
        for i, hint in enumerate(hints):
            surf = info_font.render(hint, True, TEXT_CLR)
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 70 + i * 16))

        # 최종보스미션: 생존 시간 갱신
        all_collapsed = all(n.collapsed for n in nodes)
        if not game_over and not paused:
            if all_collapsed:
                game_over = True
                survival_time = time.time() - start_time
            else:
                survival_time = time.time() - start_time

        # 실시간 업적 체크 (생존 마일스톤)
        if not game_over and not paused:
            for milestone in [30, 60]:
                if survival_time >= milestone and milestone not in _ach_checked_milestones:
                    _ach_checked_milestones.add(milestone)
                    try:
                        new_ach = check_achievements("qubit_chain", {
                            "survival_time": survival_time,
                            "collapsed_count": sum(1 for n in nodes if n.collapsed),
                            "shield_uses": qec_uses,
                        })
                        toast.show_many(new_ach)
                    except Exception:
                        pass

        if all_collapsed:
            over_surf = title_font.render(
                f"ALL QUBITS COLLAPSED  |  Survival: {survival_time:.2f}s  |  Press R to reset",
                True, STATE_COLORS["collapsed"])
            screen.blit(over_surf, (WIDTH // 2 - over_surf.get_width() // 2, HEIGHT // 2 - 80))

        preset_hud.draw(screen, info_font, hud_x, hud_y + 72)

        # 업적 토스트 업데이트/렌더링
        toast.update(dt)
        toast.draw(screen, info_font)

        help_overlay.draw(screen, info_font)
        tutorial.draw(screen, info_font)

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
            "survival_time": round(survival_time, 2),
        })
    except Exception as e:
        _log.error("플레이 기록 실패: %s", e)

    # 보고서 생성
    try:
        from report import generate_report
        generate_report("qubit_chain", {
            "total_qubits": len(nodes),
            "collapsed_count": sum(1 for n in nodes if n.collapsed),
            "survival_time": round(survival_time, 2),
            "shield_uses": qec_uses,
            "noise_rate": noise_rate,
            "cascade_damage": cascade_damage,
        })
    except Exception as e:
        _log.error("보고서 생성 실패: %s", e)

    # 업적 확인
    try:
        new_ach = check_achievements("qubit_chain", {
            "survival_time": survival_time,
            "collapsed_count": sum(1 for n in nodes if n.collapsed),
            "shield_uses": qec_uses,
        })
        for ach in new_ach:
            _log.info("Achievement unlocked: %s — %s", ach["title"], ach["desc"])
    except Exception as e:
        _log.error("업적 확인 실패: %s", e)

    # 최종보스미션 (5-3): 랭킹 서버에 생존 시간 POST
    if survival_time > 0:
        try:
            import requests
            from data_ai.ranking_server import get_base_url, start_server
            start_server()
            payload = {
                "name": "Player",
                "score": round(survival_time, 2),
                "mode": "Entanglement Cascade",
            }
            requests.post(f"{get_base_url()}/ranking", json=payload, timeout=3)
        except Exception as e:
            _log.error("랭킹 등록 실패: %s", e)

    recorder.save({"survival_time": round(survival_time, 2)})
    snd.quit()
    pygame.quit()


def open_qubit_chain():
    """외부에서 호출하는 진입점."""
    run_simulation()
