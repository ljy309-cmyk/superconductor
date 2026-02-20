"""BB84 양자 암호 통신 방어전 (Pygame).

- Alice → Bob 큐비트 전송 시각화
- 무작위 도청 이벤트(Eve) 발생 → 에러율 급증
- 에러율이 임계값 초과 시 "통신망 폐쇄" 알고리즘 자동 작동
- 사용자가 수동으로 통신망 폐쇄(SPACE) 가능
"""

import math

import pygame

from config_loader import cfg
from game_base import choose_difficulty_or_quit, finalize_session
from glossary import GlossaryOverlay
from help_overlay import HelpOverlay
from i18n import t, toggle_locale
from logger import get_module_logger
from preset_hud import PresetHUD
from quit_dialog import confirm_quit
from replay import ReplayRecorder

# ── 프로토콜 엔진 (순수 로직) ────────────────────────
from security.bb84_protocol import (
    ALICE_X,
    ALICE_Y,
    AUTO_BLOCK_THRESHOLD,
    BOB_X,
    BOB_Y,
    CHANNEL_Y,
    DECOY_CHANCE,
    ERROR_THRESHOLD,
    EVE_CHANCE,
    EVE_X,
    EVE_Y,
    SEND_INTERVAL,
    WARNING_THRESHOLD,
    BB84Game,
    shared_key_available,
)
from sound_manager import get_sound_manager
from theme import load_pg_colors, on_theme_change
from ui.slider import PANEL_W, SliderPanel

_log = get_module_logger("bb84_defense")

# ── 화면 설정 ────────────────────────────────────────
WIDTH = cfg("display", "width", 900)
HEIGHT = cfg("display", "height", 600)
FPS = cfg("display", "fps", 60)

# ── 색상 (테마에서 동적 로드) ─────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (249, 226, 175)
ALICE_CLR = (137, 180, 250)
BOB_CLR = (166, 227, 161)
EVE_CLR = (243, 139, 168)
QUBIT_CLR = (203, 166, 247)
DECOY_CLR = (249, 226, 175)
SAFE_CLR = (166, 227, 161)
DANGER_CLR = (243, 139, 168)
WARNING_BG = (80, 30, 30)
SHUTDOWN_CLR = (249, 226, 175)
CHANNEL_CLR = (69, 71, 90)
PANEL_BG = (24, 24, 37)


_COLOR_MAP = {
    "BG": "BG",
    "TEXT_CLR": "TEXT",
    "ALICE_CLR": "ALICE",
    "BOB_CLR": "BOB",
    "EVE_CLR": "EVE",
    "QUBIT_CLR": "QUBIT",
    "DECOY_CLR": "DECOY",
    "SAFE_CLR": "GREEN",
    "DANGER_CLR": "RED",
    "CHANNEL_CLR": "OVERLAY",
    "PANEL_BG": "PANEL_BG",
    "SUBTEXT_CLR": "SUBTEXT",
    "WARN_CLR": "ACCENT_YELLOW",
    "WHITE": "WHITE",
    "ACCENT": "ACCENT_YELLOW",
}


def _load_theme_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    load_pg_colors(_COLOR_MAP, globals())


# ── 그리기 헬퍼 ──────────────────────────────────────


def _draw_actors(screen, game: BB84Game, anim_t: float, font, big_font):
    """Alice, Bob, Eve 캐릭터."""
    # Alice
    pygame.draw.circle(screen, ALICE_CLR, (ALICE_X, ALICE_Y), 30)
    pygame.draw.circle(screen, TEXT_CLR, (ALICE_X, ALICE_Y), 30, 2)
    label = big_font.render("Alice", True, ALICE_CLR)
    screen.blit(label, (ALICE_X - label.get_width() // 2, ALICE_Y + 38))
    role = font.render(t("bb84_sender"), True, SUBTEXT_CLR)
    screen.blit(role, (ALICE_X - role.get_width() // 2, ALICE_Y + 56))

    # Bob
    pygame.draw.circle(screen, BOB_CLR, (BOB_X, BOB_Y), 30)
    pygame.draw.circle(screen, TEXT_CLR, (BOB_X, BOB_Y), 30, 2)
    label = big_font.render("Bob", True, BOB_CLR)
    screen.blit(label, (BOB_X - label.get_width() // 2, BOB_Y + 38))
    role = font.render(t("bb84_receiver"), True, SUBTEXT_CLR)
    screen.blit(role, (BOB_X - role.get_width() // 2, BOB_Y + 56))

    # Eve (항상 표시, 도청 시 강조)
    eve_alpha = 255 if game.eve_active else 80
    if game.eve_flash > 0:
        # 플래시 글로우
        glow_r = int(40 + 20 * math.sin(anim_t * 10))
        glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*EVE_CLR, int(100 * game.eve_flash)), (glow_r, glow_r), glow_r)
        screen.blit(glow, (EVE_X - glow_r, EVE_Y - glow_r))

    pygame.draw.circle(screen, (*EVE_CLR, eve_alpha) if eve_alpha < 255 else EVE_CLR, (EVE_X, EVE_Y), 24)
    pygame.draw.circle(screen, TEXT_CLR, (EVE_X, EVE_Y), 24, 2)
    label = big_font.render("Eve", True, EVE_CLR)
    screen.blit(label, (EVE_X - label.get_width() // 2, EVE_Y - 42))
    role = font.render(t("bb84_eavesdropper"), True, SUBTEXT_CLR)
    screen.blit(role, (EVE_X - role.get_width() // 2, EVE_Y - 28))


def _draw_channel(screen, game: BB84Game):
    """양자 채널."""
    color = DANGER_CLR if not game.channel_open else CHANNEL_CLR
    width = 3 if not game.channel_open else 1
    pygame.draw.line(screen, color, (ALICE_X + 40, CHANNEL_Y), (BOB_X - 40, CHANNEL_Y), width)

    if not game.channel_open:
        # 차단 X 표시
        mid_x = (ALICE_X + BOB_X) // 2
        pygame.draw.line(screen, DANGER_CLR, (mid_x - 15, CHANNEL_Y - 15), (mid_x + 15, CHANNEL_Y + 15), 3)
        pygame.draw.line(screen, DANGER_CLR, (mid_x - 15, CHANNEL_Y + 15), (mid_x + 15, CHANNEL_Y - 15), 3)

    # Eve 도청선 (점선)
    if game.eve_active:
        for i in range(0, 80, 8):
            pygame.draw.line(screen, EVE_CLR, (EVE_X, EVE_Y + 24 + i), (EVE_X, EVE_Y + 28 + i), 1)


def _draw_packets(screen, game: BB84Game, font):
    """전송 중인 큐비트 패킷."""
    for pkt in game.packets:
        if pkt.arrived:
            continue
        cx, cy = int(pkt.x), int(pkt.y)
        # 미션3: 디코이=노란색, 오염=빨강, 일반=보라
        if pkt.corrupted:
            color = EVE_CLR
        elif pkt.is_decoy:
            color = DECOY_CLR
        else:
            color = QUBIT_CLR
        pygame.draw.circle(screen, color, (cx, cy), 12)
        pygame.draw.circle(screen, TEXT_CLR, (cx, cy), 12, 1)
        # 디코이 표시: D, 일반: 편광 화살표
        label = "D" if pkt.is_decoy and not pkt.corrupted else pkt.display
        sym = font.render(label, True, WHITE)
        screen.blit(sym, (cx - sym.get_width() // 2, cy - sym.get_height() // 2))


def _draw_error_meter(screen, game: BB84Game, font, big_font):
    """에러율 미터."""
    mx, my = 50, 380
    mw, mh = 260, 20

    label = big_font.render(t("bb84_error_rate_label"), True, ACCENT)
    screen.blit(label, (mx, my - 24))

    # 배경
    pygame.draw.rect(screen, PANEL_BG, (mx, my, mw, mh))

    # 미션2: 10% 경고선
    warn_x = mx + int(mw * WARNING_THRESHOLD)
    pygame.draw.line(screen, WARN_CLR, (warn_x, my - 2), (warn_x, my + mh + 2), 1)
    warn_label = font.render(f"{WARNING_THRESHOLD * 100:.0f}%", True, WARN_CLR)
    screen.blit(warn_label, (warn_x - 12, my + mh + 6))

    # 미션1: 15% 자동 차단선
    auto_x = mx + int(mw * AUTO_BLOCK_THRESHOLD)
    pygame.draw.line(screen, ALICE_CLR, (auto_x, my - 4), (auto_x, my + mh + 4), 2)
    auto_label = font.render(f"{AUTO_BLOCK_THRESHOLD * 100:.0f}%", True, ALICE_CLR)
    screen.blit(auto_label, (auto_x - 8, my + mh + 6))

    # 25% 임계선
    thresh_x = mx + int(mw * ERROR_THRESHOLD)
    pygame.draw.line(screen, DANGER_CLR, (thresh_x, my - 4), (thresh_x, my + mh + 4), 2)
    thresh_label = font.render(f"{ERROR_THRESHOLD * 100:.0f}%", True, DANGER_CLR)
    screen.blit(thresh_label, (thresh_x - 8, my + mh + 6))

    # 채움
    fill_w = int(mw * min(game.error_rate, 1.0))
    if game.error_rate >= AUTO_BLOCK_THRESHOLD:
        fill_clr = DANGER_CLR
    elif game.error_rate >= WARNING_THRESHOLD:
        fill_clr = WARN_CLR
    else:
        fill_clr = SAFE_CLR
    pygame.draw.rect(screen, fill_clr, (mx, my, fill_w, mh))
    pygame.draw.rect(screen, TEXT_CLR, (mx, my, mw, mh), 1)

    # 수치
    pct = font.render(f"{game.error_rate * 100:.1f}%", True, TEXT_CLR)
    screen.blit(pct, (mx + mw + 8, my))


def _draw_stats(screen, game: BB84Game, font, big_font):
    """통계 패널."""
    sx, sy = 50, 440

    # 미션1: 점수 표시
    score_surf = big_font.render(f"SCORE: {game.score}", True, ACCENT)
    screen.blit(score_surf, (sx, sy - 20))

    # 미션3 (5-2): QRNG 키 잔량 표시
    qrng_remain = shared_key_available()

    lines = [
        (t("bb84_sent", count=game.total_sent), TEXT_CLR),
        (t("bb84_safe", count=game.total_safe), SAFE_CLR),
        (t("bb84_errors", count=game.total_errors), DANGER_CLR),
        (t("bb84_eve_count", count=game.eve_intercept_count), EVE_CLR),
        (t("bb84_decoy_stats", sent=game.decoy_sent, trapped=game.decoy_trapped), DECOY_CLR),
        (t("bb84_block_stats", auto=game.auto_blocks, manual=game.manual_blocks), ALICE_CLR),
        (
            t("bb84_qrng_stats", used=game.qrng_bits_used, remain=qrng_remain),
            ACCENT if qrng_remain > 0 else SUBTEXT_CLR,
        ),
        (
            t(
                "bb84_channel_status",
                status="OPEN" if game.channel_open else "SHUTDOWN",
                auto_state=t("auto_on") if game.auto_block_enabled else t("auto_off"),
            ),
            SAFE_CLR if game.channel_open else DANGER_CLR,
        ),
    ]
    for i, (text, color) in enumerate(lines):
        surf = font.render(text, True, color)
        screen.blit(surf, (sx, sy + i * 16))


def _draw_log(screen, game: BB84Game, font):
    """프로토콜 로그."""
    lx, ly = 380, 340
    header = font.render(t("bb84_protocol_log"), True, ACCENT)
    screen.blit(header, (lx, ly))

    for i, entry in enumerate(game.log):
        r = entry["round"]
        ab = entry["alice_basis"]
        bb = entry["bob_basis"]
        match = "=" if entry["match"] else "≠"
        eve = " [EVE]" if entry["intercepted"] else ""
        decoy = " [DECOY]" if entry.get("decoy") else ""
        err = " ERROR" if entry["error"] else ""

        if entry["error"]:
            color = DANGER_CLR
        elif entry.get("decoy"):
            color = DECOY_CLR
        elif entry["intercepted"]:
            color = EVE_CLR
        else:
            color = TEXT_CLR
        text = f"R{r:03d} A:{ab} B:{bb} {match}{eve}{decoy}{err}"
        surf = font.render(text, True, color)
        screen.blit(surf, (lx, ly + 18 + i * 15))


def _draw_shutdown_banner(screen, game: BB84Game, big_font, anim_t: float):
    """통신망 폐쇄 배너."""
    if game.shutdown_flash > 0:
        alpha = int(200 * min(game.shutdown_flash, 1.0))
        banner = pygame.Surface((WIDTH, 50), pygame.SRCALPHA)
        banner.fill((*DANGER_CLR, alpha // 3))
        screen.blit(banner, (0, CHANNEL_Y - 25))

        blink = int(anim_t * 4) % 2 == 0
        if blink:
            msg = t("bb84_channel_shutdown_msg") if game.auto_shutdown else t("bb84_manual_shutdown_msg")
            reason = t("bb84_error_exceeded") if game.auto_shutdown else ""
            text = big_font.render(f"⚠ {msg}{reason}", True, DANGER_CLR)
            screen.blit(text, (WIDTH // 2 - text.get_width() // 2, CHANNEL_Y + 60))


# ── 메인 시뮬레이션 ──────────────────────────────────


def run_simulation():
    _load_theme_colors()
    on_theme_change(_load_theme_colors)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH + PANEL_W, HEIGHT))
    pygame.display.set_caption(t("game_title_bb84"))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 11)
    big_font = pygame.font.SysFont("Consolas", 14, bold=True)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)

    game = BB84Game()
    anim_t = 0.0
    paused = False

    # ── 슬라이더 패널 ─────────────────────────────────
    panel = SliderPanel(WIDTH + 5, 40, PANEL_W - 10, "Parameters")
    sl_interval = panel.add(0.3, 3.0, SEND_INTERVAL, 0.1, "Send Interval", ".1f")
    sl_eve = panel.add(0.0, 1.0, EVE_CHANCE, 0.05, "Eve Chance", ".2f")
    sl_decoy = panel.add(0.0, 0.5, DECOY_CHANCE, 0.05, "Decoy Chance", ".2f")
    sl_autoblock = panel.add(0.05, 0.5, AUTO_BLOCK_THRESHOLD, 0.05, "Auto Block", ".2f")

    slider_map = {
        ("bb84", "send_interval"): sl_interval,
        ("bb84", "eve_chance"): sl_eve,
        ("bb84", "decoy_chance"): sl_decoy,
        ("bb84", "auto_block_threshold"): sl_autoblock,
    }
    preset_hud = PresetHUD("bb84_defense", slider_map)
    help_overlay = HelpOverlay("bb84_defense")
    glossary = GlossaryOverlay()
    snd = get_sound_manager()
    snd.init()
    recorder = ReplayRecorder("bb84_defense")

    # ── 시작 시 난이도 선택 ──
    if not choose_difficulty_or_quit(screen, font, preset_hud, _load_theme_colors):
        return

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        anim_t += dt

        # ── 이벤트 ───────────────────────────────────
        for event in pygame.event.get():
            panel.handle_event(event)
            preset_hud.handle_event(event)
            help_overlay.handle_event(event)
            glossary.handle_event(event)
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                snd.handle_key(event.key)
                if event.key == pygame.K_ESCAPE:
                    if confirm_quit(screen, font):
                        running = False
                elif event.key == pygame.K_SPACE:
                    if game.channel_open:
                        game.manual_shutdown()
                        snd.play("channel_shutdown")
                    else:
                        game.reopen()
                elif event.key == pygame.K_r:
                    game.reset()
                    panel.reset_all()
                elif event.key == pygame.K_p:
                    paused = not paused
                elif event.key == pygame.K_a:
                    # 미션1: 자동 차단 토글
                    game.auto_block_enabled = not game.auto_block_enabled
                elif event.key == pygame.K_l:
                    toggle_locale()

        # ── 업데이트 ─────────────────────────────────
        preset_hud.update(dt)

        if not paused:
            # 전송 타이머 (슬라이더 값 사용)
            cur_interval = sl_interval.value
            game.send_timer += dt
            if game.send_timer >= cur_interval:
                game.send_timer = 0.0
                prev_decoy_trapped = game.decoy_trapped
                game.new_round(eve_chance=sl_eve.value, decoy_chance=sl_decoy.value)
                if game.eve_active:
                    snd.play("eve_detected")
                if game.decoy_trapped > prev_decoy_trapped:
                    snd.play("decoy_trap")

            # 패킷 이동
            for pkt in game.packets:
                pkt.update(dt)
                if pkt.arrived:
                    game.process_arrival(pkt, auto_block_thresh=sl_autoblock.value)

            # 도착한 패킷 제거
            game.packets = [p for p in game.packets if not p.arrived]

            # 리플레이 기록
            recorder.record(
                {
                    "round": game.round_id,
                    "error_rate": game.error_rate,
                    "eve_active": game.eve_active,
                    "channel_open": game.channel_open,
                    "score": game.score,
                }
            )

            # 플래시 타이머
            if game.eve_flash > 0:
                game.eve_flash -= dt
            if game.shutdown_flash > 0:
                game.shutdown_flash -= dt

        # ── 렌더링 ───────────────────────────────────

        # 미션2: 에러율 10% 초과 시 배경을 짙은 빨강으로 번쩍
        if game.error_rate > WARNING_THRESHOLD and game.channel_open:
            # 번쩍거리는 효과 — sin으로 강도 변조
            flash_intensity = 0.5 + 0.5 * math.sin(anim_t * 6)
            r = int(BG[0] + (WARNING_BG[0] - BG[0]) * flash_intensity)
            g = int(BG[1] + (WARNING_BG[1] - BG[1]) * flash_intensity)
            b = int(BG[2] + (WARNING_BG[2] - BG[2]) * flash_intensity)
            screen.fill((r, g, b))
        else:
            screen.fill(BG)

        # 타이틀
        title = title_font.render(t("game_title_bb84"), True, ACCENT)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 12))

        # 채널
        _draw_channel(screen, game)

        # 패킷
        _draw_packets(screen, game, font)

        # 캐릭터
        _draw_actors(screen, game, anim_t, font, big_font)

        # 에러 미터
        _draw_error_meter(screen, game, font, big_font)

        # 통계
        _draw_stats(screen, game, font, big_font)

        # 로그
        _draw_log(screen, game, font)

        # 폐쇄 배너
        _draw_shutdown_banner(screen, game, big_font, anim_t)

        # 슬라이더 패널 그리기
        panel.draw(screen, font)

        # 안내
        hints = [
            t(
                "hint_bb84_info",
                score=game.score,
                auto_state=t("auto_on") if game.auto_block_enabled else t("auto_off"),
                pause_state=t("paused") if paused else t("running_state"),
            ),
            t("hint_bb84_controls"),
            t("hint_bb84_pause"),
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 52 + i * 16))

        preset_hud.draw(screen)
        glossary.draw(screen, font)
        help_overlay.draw(screen)

        pygame.display.flip()

    finalize_session(
        "bb84_defense",
        {
            "score": game.score,
            "total_sent": game.total_sent,
            "total_errors": game.total_errors,
            "total_safe": game.total_safe,
            "eve_intercepts": game.eve_intercept_count,
            "auto_blocks": game.auto_blocks,
            "manual_blocks": game.manual_blocks,
            "decoy_sent": game.decoy_sent,
            "decoy_trapped": game.decoy_trapped,
            "qrng_bits_used": game.qrng_bits_used,
        },
        recorder=recorder,
        snd=snd,
        theme_callback=_load_theme_colors,
    )


def open_bb84_defense():
    """외부에서 호출하는 진입점."""
    run_simulation()
