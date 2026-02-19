"""양자 오류 정정 (QEC 방어막) 시뮬레이션 (Pygame).

- 큐비트 네트워크에 노이즈가 지속적으로 누적
- 특정 키 입력(Q) 시 일정 시간 동안 노이즈를 절반으로 감소 (QEC 방어막)
- 방어막 없이 버티기 vs 방어막으로 수명 연장 비교
"""

import math
import random

import pygame

from config_loader import cfg
from quantum.ui_common import (
    HISTORY_PAGE_SIZE,
    draw_bar_pattern as _draw_bar_pattern,
    paginate,
    render_notify,
)
from game_base import choose_difficulty_or_quit, finalize_session
from game_summary import draw_game_summary
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from preset_hud import PresetHUD

# ── 물리 엔진 (순수 로직) ────────────────────────────
from quantum.qec_physics import (
    CASCADE_DAMAGE,
    HEAL_AMOUNT,
    NODE_RADIUS,
    NOISE_RATE,
    QEC_COOLDOWN,
    QEC_DURATION,
    QEC_REDUCTION_DEFAULT,
    QEC_REDUCTION_MAX,
    QEC_REDUCTION_MIN,
    QEC_REDUCTION_STEP,
    QECQubit,
    build_grid,
)
from quantum.qubit_physics import QubitState
from quit_dialog import confirm_quit
from replay import ReplayRecorder
from sound_manager import get_sound_manager
from theme import is_reduced_motion, load_pg_colors, on_theme_change
from ui.slider import PANEL_W, SliderPanel

_log = get_module_logger("qec_shield")

# ── 화면 설정 ────────────────────────────────────────
WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
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


_COLOR_MAP = {
    "BG": "BG",
    "TEXT_CLR": "TEXT",
    "ACCENT": "ACCENT_PURPLE",
    "SHIELD_CLR": "SHIELD_CLR",
    "SHIELD_GLOW": "SHIELD_GLOW",
    "STABLE_CLR": "STABLE",
    "WARNING_CLR": "WARNING",
    "COLLAPSED_CLR": "COLLAPSED",
    "PANEL_BG": "PANEL_BG",
    "SUBTEXT_CLR": "SUBTEXT",
    "OVERLAY_CLR": "OVERLAY",
    "WHITE": "WHITE",
}


def _load_theme_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    load_pg_colors(_COLOR_MAP, globals())
    STATE_COLORS[QubitState.STABLE] = globals()["STABLE_CLR"]
    STATE_COLORS[QubitState.WARNING] = globals()["WARNING_CLR"]
    STATE_COLORS[QubitState.COLLAPSED] = globals()["COLLAPSED_CLR"]


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

        # Shield HUD
        self.hud_x = int(660 * sx)
        self.hud_y = int(120 * sy)
        self.hud_w = int(210 * sx)
        self.hud_h = int(260 * sy)

        # 스코어보드
        self.score_x = int(660 * sx)
        self.score_y = int(400 * sy)

        # 타이틀
        self.title_y = int(12 * sy)

        # 이벤트 로그
        self.log_x = int(660 * sx)
        self.log_y = int(500 * sy)

        # 알림
        self.notify_y = h - int(58 * sy)

        # 하단 힌트
        self.hint_y = h - int(40 * sy)


_layout = Layout()


def _rebuild_layout(w: int, h: int):
    """리사이즈 시 레이아웃 재계산."""
    global _layout
    _layout = Layout(w, h)


# ── 그리기 헬퍼 ──────────────────────────────────────

STATE_COLORS = {
    QubitState.STABLE: STABLE_CLR,
    QubitState.WARNING: WARNING_CLR,
    QubitState.COLLAPSED: COLLAPSED_CLR,
}




def _draw_link(screen, a: QECQubit, b: QECQubit):
    color = SUBTEXT_CLR
    if a.collapsed or b.collapsed:
        color = COLLAPSED_CLR
    pygame.draw.line(screen, color, (int(a.x), int(a.y)), (int(b.x), int(b.y)), 1)


def _draw_node(screen, node: QECQubit, font, shield_active: bool, t: float):
    cx, cy = int(node.x), int(node.y)
    color = STATE_COLORS[node.state]

    # QEC 방어막 글로우 (활성 상태일 때 안정 큐비트에만)
    if shield_active and not node.collapsed and not is_reduced_motion():
        pulse = int(6 + 4 * math.sin(t * 4))
        glow_surf = pygame.Surface((2 * (NODE_RADIUS + pulse), 2 * (NODE_RADIUS + pulse)), pygame.SRCALPHA)
        pygame.draw.circle(
            glow_surf, (*SHIELD_GLOW, 40), (NODE_RADIUS + pulse, NODE_RADIUS + pulse), NODE_RADIUS + pulse
        )
        screen.blit(glow_surf, (cx - NODE_RADIUS - pulse, cy - NODE_RADIUS - pulse))

    # 본체
    pygame.draw.circle(screen, color, (cx, cy), NODE_RADIUS)
    pygame.draw.circle(screen, TEXT_CLR, (cx, cy), NODE_RADIUS, 2)

    # 하중 텍스트
    txt = "X" if node.collapsed else f"{int(node.stress)}%"
    surf = font.render(txt, True, BG if not node.collapsed else WHITE)
    screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))

    # 상태 텍스트 라벨 (색상에만 의존하지 않도록)
    state_label = font.render(node.state.label, True, color)
    screen.blit(state_label, (cx - state_label.get_width() // 2, cy + NODE_RADIUS + 4))


def _draw_shield_hud(
    screen,
    shield_active: bool,
    shield_timer: float,
    cooldown_timer: float,
    qec_reduction: float,
    heal_cooldown: float,
    font,
    big_font,
):
    """QEC 방어막 상태 HUD."""
    L = _layout
    hud_x, hud_y = L.hud_x, L.hud_y
    hud_w, hud_h = L.hud_w, L.hud_h

    pygame.draw.rect(screen, PANEL_BG, (hud_x, hud_y, hud_w, hud_h), border_radius=8)
    pygame.draw.rect(screen, ACCENT, (hud_x, hud_y, hud_w, hud_h), 2, border_radius=8)

    title = big_font.render(t("qec_shield_title"), True, ACCENT)
    screen.blit(title, (hud_x + hud_w // 2 - title.get_width() // 2, hud_y + 10))

    if shield_active:
        status = big_font.render(t("qec_active"), True, SHIELD_GLOW)
        screen.blit(status, (hud_x + hud_w // 2 - status.get_width() // 2, hud_y + 40))

        # 남은 시간 바
        bar_x, bar_y = hud_x + 20, hud_y + 70
        bar_w, bar_h = hud_w - 40, 16
        ratio = max(shield_timer / QEC_DURATION, 0)
        fill_w = int(bar_w * ratio)
        pygame.draw.rect(screen, OVERLAY_CLR, (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(screen, SHIELD_GLOW, (bar_x, bar_y, fill_w, bar_h))
        _draw_bar_pattern(screen, (bar_x, bar_y, fill_w, bar_h),
                          SHIELD_GLOW, "high")
        pygame.draw.rect(screen, TEXT_CLR, (bar_x, bar_y, bar_w, bar_h), 1)

        time_txt = font.render(t("qec_remaining", time=shield_timer), True, TEXT_CLR)
        screen.blit(time_txt, (bar_x, bar_y + 20))

        # 감쇠 계수 표시 — 0.0이면 무적, 1.0이면 무효
        if qec_reduction == 0.0:
            label = t("qec_invincible")
            clr = SHIELD_GLOW
        elif qec_reduction < 0.5:
            label = t("qec_noise_strong", red=qec_reduction)
            clr = STABLE_CLR
        elif qec_reduction == 0.5:
            label = t("qec_noise_default", red=qec_reduction)
            clr = STABLE_CLR
        else:
            label = t("qec_noise_weak", red=qec_reduction)
            clr = WARNING_CLR
        effect = font.render(label, True, clr)
        screen.blit(effect, (bar_x, bar_y + 38))
    elif cooldown_timer > 0:
        status = big_font.render(t("qec_cooldown_label"), True, WARNING_CLR)
        screen.blit(status, (hud_x + hud_w // 2 - status.get_width() // 2, hud_y + 40))

        bar_x, bar_y = hud_x + 20, hud_y + 70
        bar_w, bar_h = hud_w - 40, 16
        ratio = max(1 - cooldown_timer / QEC_COOLDOWN, 0)
        fill_w = int(bar_w * ratio)
        pygame.draw.rect(screen, OVERLAY_CLR, (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(screen, WARNING_CLR, (bar_x, bar_y, fill_w, bar_h))
        _draw_bar_pattern(screen, (bar_x, bar_y, fill_w, bar_h),
                          WARNING_CLR, "mid")
        pygame.draw.rect(screen, TEXT_CLR, (bar_x, bar_y, bar_w, bar_h), 1)

        time_txt = font.render(t("qec_until_ready", time=cooldown_timer), True, TEXT_CLR)
        screen.blit(time_txt, (bar_x, bar_y + 20))
    else:
        status = big_font.render(t("qec_ready"), True, STABLE_CLR)
        screen.blit(status, (hud_x + hud_w // 2 - status.get_width() // 2, hud_y + 40))

        prompt = font.render(t("qec_activate_hint"), True, TEXT_CLR)
        screen.blit(prompt, (hud_x + hud_w // 2 - prompt.get_width() // 2, hud_y + 70))

    # ── 감쇠 계수 조절 표시 ──
    adj_y = hud_y + 140
    adj_label = font.render(t("qec_reduction_label", red=qec_reduction), True, TEXT_CLR)
    screen.blit(adj_label, (hud_x + 20, adj_y))
    adj_hint = font.render(t("qec_adjust_hint"), True, SUBTEXT_CLR)
    screen.blit(adj_hint, (hud_x + 20, adj_y + 16))

    # ── 힐링 상태 ──
    heal_y = adj_y + 40
    if heal_cooldown > 0:
        heal_txt = font.render(t("qec_heal_wait", time=heal_cooldown), True, WARNING_CLR)
    else:
        heal_txt = font.render(t("qec_heal_ready"), True, STABLE_CLR)
    screen.blit(heal_txt, (hud_x + 20, heal_y))

    heal_desc = font.render(t("qec_heal_amount", amount=int(HEAL_AMOUNT)), True, SUBTEXT_CLR)
    screen.blit(heal_desc, (hud_x + 20, heal_y + 16))


def _draw_scoreboard(screen, elapsed: float, alive_count: int, total: int, qec_uses: int, heal_uses: int, font):
    """경과 시간 · 생존 큐비트 수 · QEC/Heal 사용 횟수."""
    L = _layout
    sx, sy = L.score_x, L.score_y
    lines = [
        (t("qec_elapsed"), f"{elapsed:.1f}s"),
        (t("qec_alive_qubits"), f"{alive_count} / {total}"),
        (t("qec_uses_count"), f"{qec_uses}"),
        (t("qec_heal_uses_count"), f"{heal_uses}"),
    ]
    for i, (label, value) in enumerate(lines):
        lbl = font.render(f"{label}:", True, SUBTEXT_CLR)
        val = font.render(value, True, TEXT_CLR)
        screen.blit(lbl, (sx, sy + i * 22))
        screen.blit(val, (sx + 100, sy + i * 22))


# ── 메인 시뮬레이션 ──────────────────────────────────


def run_simulation():
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH + PANEL_W, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption(t("game_title_qec_shield"))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 12)
    big_font = pygame.font.SysFont("Consolas", 16, bold=True)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)

    nodes = build_grid()
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
    anim_t = 0.0

    # 알림 / 페이지네이션
    notify_msg = ""
    notify_timer = 0.0
    history_page = 0
    event_log: list[str] = []

    def _notify(msg: str, duration: float = 2.0):
        nonlocal notify_msg, notify_timer
        notify_msg = msg
        notify_timer = duration

    # ── 비교 모드 ──
    compare_mode = False  # QEC/Heal 비활성화 모드
    best_with_qec = 0.0  # QEC ON 최고 생존 시간
    best_without_qec = 0.0  # QEC OFF 최고 생존 시간

    # ── 시작 시 난이도 선택 ──
    if not choose_difficulty_or_quit(screen, font, preset_hud, _load_theme_colors):
        return

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        anim_t += dt

        # ── 이벤트 ───────────────────────────────────
        for event in pygame.event.get():
            spanel.handle_event(event)
            preset_hud.handle_event(event)
            help_overlay.handle_event(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (event.w, event.h), pygame.RESIZABLE)
                _rebuild_layout(event.w - PANEL_W, event.h)
            elif event.type == pygame.KEYDOWN:
                snd.handle_key(event.key)
                if event.key == pygame.K_ESCAPE:
                    if confirm_quit(screen, font):
                        running = False
                elif event.key == pygame.K_s:
                    # QEC 방어막 활성화 (S = Shield)
                    if not compare_mode and not shield_active and cooldown_timer <= 0:
                        shield_active = True
                        shield_timer = QEC_DURATION
                        qec_uses += 1
                        event_log.append(t("qec_notify_shield"))
                        _notify(t("qec_notify_shield"), 1.5)
                        snd.play("shield_on")
                elif event.key == pygame.K_h:
                    # 미션2: 힐링 — 모든 생존 큐비트 stress -20
                    if not compare_mode and heal_cooldown <= 0:
                        for n in nodes:
                            if not n.collapsed:
                                n.stress = max(n.stress - HEAL_AMOUNT, 0.0)
                        heal_uses += 1
                        heal_cooldown = HEAL_COOLDOWN_SEC
                        event_log.append(t("qec_notify_healed",
                                           amount=int(HEAL_AMOUNT)))
                        _notify(t("qec_notify_healed",
                                  amount=int(HEAL_AMOUNT)), 1.5)
                        snd.play("heal")
                elif event.key == pygame.K_c:
                    # 비교 모드 토글
                    compare_mode = not compare_mode
                elif event.key == pygame.K_LEFT:
                    sl_reduction.value = sl_reduction.value - QEC_REDUCTION_STEP
                elif event.key == pygame.K_RIGHT:
                    sl_reduction.value = sl_reduction.value + QEC_REDUCTION_STEP
                elif event.key == pygame.K_PAGEUP:
                    history_page = max(0, history_page - 1)
                elif event.key == pygame.K_PAGEDOWN:
                    history_page += 1
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
                    event_log.clear()
                    history_page = 0
                    _notify(t("notify_reset"), 1.0)
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_l:
                    toggle_locale()

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
                        event_log.append(f"Q{n.qid} COLLAPSED!")
                        snd.play("collapse")

            # ── 프리셋 HUD 업데이트 ──
            preset_hud.update(dt)

            # ── 리플레이 기록 ──
            recorder.record(
                {
                    "elapsed": round(elapsed, 2),
                    "shield_active": shield_active,
                    "alive": sum(1 for n in nodes if not n.collapsed),
                    "stresses": [round(n.stress, 1) for n in nodes],
                }
            )

        # ── 렌더링 ───────────────────────────────────
        screen.fill(BG)

        # 타이틀
        L = _layout
        title = title_font.render(t("game_title_qec_shield"), True, ACCENT)
        screen.blit(title, (L.W // 2 - title.get_width() // 2, L.title_y))

        # 방어막 활성 시 전체 배경 글로우
        if shield_active and not is_reduced_motion():
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            alpha = int(12 + 8 * math.sin(anim_t * 3))
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
            _draw_node(screen, n, font, shield_active, anim_t)

        # HUD
        _draw_shield_hud(
            screen, shield_active, shield_timer, cooldown_timer, qec_reduction, heal_cooldown, font, big_font
        )

        alive_count = sum(1 for n in nodes if not n.collapsed)
        _draw_scoreboard(screen, elapsed, alive_count, total, qec_uses, heal_uses, font)

        # 전체 붕괴
        if alive_count == 0:
            # 최고 기록 갱신
            if compare_mode:
                best_without_qec = max(best_without_qec, elapsed)
            else:
                best_with_qec = max(best_with_qec, elapsed)
            stats = [
                (t("summary_elapsed"), f"{elapsed:.1f}s"),
                (t("summary_collapsed"), f"{total - alive_count} / {total}"),
                (t("summary_qec_uses"), str(qec_uses)),
                (t("summary_heal_uses"), str(heal_uses)),
            ]
            if best_with_qec > 0 and best_without_qec > 0:
                stats.append((t("comparison_title"), f"QEC: {best_with_qec:.1f}s / NO QEC: {best_without_qec:.1f}s"))
            draw_game_summary(screen, t("summary_title_gameover"), stats, font=font, title_font=title_font)

        # 슬라이더 패널 그리기
        spanel.draw(screen, font)

        # 비교 모드 표시
        if compare_mode:
            cmp_surf = big_font.render(t("comparison_hint"), True, WARNING_CLR)
            screen.blit(cmp_surf, (L.W // 2 - cmp_surf.get_width() // 2, 8))

        # ── 이벤트 로그 (페이지네이션) ──
        if event_log:
            page_items, history_page, total_pages = paginate(event_log, history_page)
            title_text = t("qec_event_log")
            if total_pages > 1:
                title_text += f"  ({history_page + 1}/{total_pages})"
            lt = font.render(title_text, True, ACCENT)
            screen.blit(lt, (L.log_x, L.log_y))
            for li, entry in enumerate(page_items):
                clr = COLLAPSED_CLR if "COLLAPSED" in entry else TEXT_CLR
                es = font.render(f"  {entry}", True, clr)
                screen.blit(es, (L.log_x, L.log_y + 16 + li * 14))

        # 안내
        hints = [
            t(
                "hint_reduction_info",
                red=qec_reduction,
                shield_state=t("shield_on") if shield_active else "",
                pause_state=t("paused") if paused else t("running_state"),
            ),
            t("hint_qec_controls"),
            t("hint_pause_reset"),
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (L.W // 2 - surf.get_width() // 2, L.hint_y + i * 16))

        # 알림 메시지 (페이드 아웃)
        if notify_timer > 0:
            notify_timer -= dt
            render_notify(screen, notify_msg, notify_timer, font, ACCENT,
                          L.W // 2, L.notify_y)

        preset_hud.draw(screen, font, 10, 50)
        help_overlay.draw(screen, font)

        pygame.display.flip()

    # 최종미션: finalize_session으로 통합 정리
    finalize_session(
        "qec_shield",
        {
            "survival_time": round(elapsed, 1),
            "alive_count": sum(1 for n in nodes if not n.collapsed),
            "total_qubits": total,
            "qec_uses": qec_uses,
            "heal_uses": heal_uses,
            "qec_reduction": qec_reduction,
        },
        recorder=recorder,
        recorder_meta={"survival_time": round(elapsed, 1)},
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def open_qec_shield():
    """외부에서 호출하는 진입점."""
    run_simulation()
