"""BB84 양자 암호 통신 방어전 (Pygame).

- Alice → Bob 큐비트 전송 시각화
- 무작위 도청 이벤트(Eve) 발생 → 에러율 급증
- 에러율이 임계값 초과 시 "통신망 폐쇄" 알고리즘 자동 작동
- 사용자가 수동으로 통신망 폐쇄(SPACE) 가능
"""

import math
import random

import pygame

# 미션3 (5-2): QRNG 키 통합 — 모듈이 있으면 양자 해시 키 사용
try:
    from data_ai.qrng_logger import pop_key_bit, shared_key_available
    _QRNG_AVAILABLE = True
except ImportError:
    _QRNG_AVAILABLE = False

# ── 화면 설정 ────────────────────────────────────────
WIDTH, HEIGHT = 900, 600
FPS = 60

# ── 색상 ─────────────────────────────────────────────
BG = (30, 30, 46)
TEXT_CLR = (205, 214, 244)
ACCENT = (249, 226, 175)
ALICE_CLR = (137, 180, 250)    # Alice 파랑
BOB_CLR = (166, 227, 161)      # Bob 초록
EVE_CLR = (243, 139, 168)      # Eve 빨강
QUBIT_CLR = (203, 166, 247)    # 큐비트 보라
DECOY_CLR = (249, 226, 175)    # 미션3: 디코이 노랑
SAFE_CLR = (166, 227, 161)
DANGER_CLR = (243, 139, 168)
WARNING_BG = (80, 30, 30)      # 미션2: 경고 배경 (짙은 빨강)
SHUTDOWN_CLR = (249, 226, 175)
CHANNEL_CLR = (69, 71, 90)
PANEL_BG = (24, 24, 37)

# ── 레이아웃 ─────────────────────────────────────────
ALICE_X, ALICE_Y = 100, 250
BOB_X, BOB_Y = 800, 250
CHANNEL_Y = 250
EVE_X, EVE_Y = 450, 100

# ── 프로토콜 파라미터 ────────────────────────────────
BASES = ["+", "×"]           # 직선 / 대각선 기저
BITS = ["0", "1"]
SEND_INTERVAL = 1.2          # 큐비트 전송 간격 (초)
EVE_CHANCE = 0.25            # 도청 이벤트 발생 확률 (라운드당)
EVE_ERROR_INJECT = 0.50      # Eve 도청 시 에러 주입 확률
ERROR_THRESHOLD = 0.25       # 에러율 임계값 → 자동 폐쇄
HISTORY_WINDOW = 20          # 에러율 계산 최근 N 라운드

# ── 미션1: 자동 차단 시스템 ────────────────────────
AUTO_BLOCK_THRESHOLD = 0.15  # 에러율 15% 초과 시 자동 차단
AUTO_BLOCK_SCORE = 50        # 자동 차단 성공 시 획득 점수
MANUAL_BLOCK_SCORE = 100     # 수동 차단 보너스 (사람 판단)

# ── 미션2: 경고 알람 ──────────────────────────────
WARNING_THRESHOLD = 0.10     # 에러율 10% 초과 시 배경 경고

# ── 미션3: 디코이 상태 ─────────────────────────────
DECOY_CHANCE = 0.15          # 디코이 패킷 발생 확률 (15%)
DECOY_ERROR_MULT = 2.0       # 디코이 도청 시 에러 기여 2배


# ── 큐비트 패킷 ──────────────────────────────────────

class QubitPacket:
    """전송 중인 큐비트 패킷."""

    def __init__(self, bit: str, basis: str, round_id: int, is_decoy: bool = False):
        self.bit = bit
        self.basis = basis
        self.round_id = round_id
        self.is_decoy = is_decoy          # 미션3: 디코이 여부
        self.x = float(ALICE_X + 40)
        self.y = float(CHANNEL_Y)
        self.speed = 180.0
        self.intercepted = False
        self.corrupted = False
        self.arrived = False

    @property
    def display(self) -> str:
        arrows = {
            ("+", "0"): "↑", ("+", "1"): "→",
            ("×", "0"): "↗", ("×", "1"): "↘",
        }
        return arrows.get((self.basis, self.bit), "?")

    def update(self, dt: float):
        if not self.arrived:
            self.x += self.speed * dt
            if self.x >= BOB_X - 40:
                self.x = BOB_X - 40
                self.arrived = True


# ── 게임 상태 ────────────────────────────────────────

class BB84Game:
    """BB84 프로토콜 시뮬레이션 상태."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.round_id = 0
        self.packets: list[QubitPacket] = []
        self.send_timer = 0.0

        # 로그
        self.log: list[dict] = []

        # 에러 추적
        self.error_history: list[bool] = []  # True = 에러 발생
        self.error_rate = 0.0

        # Eve 상태
        self.eve_active = False
        self.eve_flash = 0.0
        self.eve_intercept_count = 0

        # 채널 상태
        self.channel_open = True
        self.auto_shutdown = False
        self.shutdown_flash = 0.0

        # 미션1: 점수 시스템
        self.score = 0
        self.auto_blocks = 0           # 자동 차단 횟수
        self.manual_blocks = 0         # 수동 차단 횟수
        self.auto_block_enabled = True # 자동 차단 ON/OFF

        # 미션3: 디코이 통계
        self.decoy_sent = 0
        self.decoy_trapped = 0         # Eve가 디코이를 건드린 횟수

        # 미션3 (5-2): QRNG 키 사용 추적
        self.qrng_bits_used = 0

        # 통계
        self.total_sent = 0
        self.total_errors = 0
        self.total_safe = 0

    def new_round(self):
        """새 큐비트 전송 라운드."""
        if not self.channel_open:
            return

        self.round_id += 1

        # 미션3 (5-2): QRNG 키가 있으면 양자 해시 비트를 Alice가 전송
        qrng_bit = None
        if _QRNG_AVAILABLE:
            qrng_bit = pop_key_bit()
        if qrng_bit is not None:
            alice_bit = str(qrng_bit)
            self.qrng_bits_used += 1
        else:
            alice_bit = random.choice(BITS)

        alice_basis = random.choice(BASES)

        # 미션3: 디코이 패킷 — Alice가 가끔 가짜 데이터 삽입
        is_decoy = random.random() < DECOY_CHANCE
        pkt = QubitPacket(alice_bit, alice_basis, self.round_id, is_decoy=is_decoy)
        if is_decoy:
            self.decoy_sent += 1

        # Eve 도청 여부
        eve_present = random.random() < EVE_CHANCE
        if eve_present:
            self.eve_active = True
            self.eve_flash = 0.8
            self.eve_intercept_count += 1
            pkt.intercepted = True

            # Eve가 다른 기저로 측정하면 큐비트 파괴
            eve_basis = random.choice(BASES)
            if eve_basis != alice_basis or random.random() < EVE_ERROR_INJECT:
                pkt.corrupted = True

            # 미션3: 디코이를 건드리면 트랩 발동!
            if is_decoy:
                pkt.corrupted = True  # 디코이는 무조건 오염
                self.decoy_trapped += 1
        else:
            self.eve_active = False

        self.packets.append(pkt)
        self.total_sent += 1

    def process_arrival(self, pkt: QubitPacket):
        """Bob이 큐비트 수신 처리."""
        bob_basis = random.choice(BASES)
        basis_match = (bob_basis == pkt.basis)

        # 에러 판정: 기저 일치인데 비트가 다르면 에러 (도청 때문)
        has_error = False
        if basis_match and pkt.corrupted:
            has_error = True
            self.total_errors += 1
        elif basis_match:
            self.total_safe += 1

        if basis_match:
            # 미션3: 디코이가 도청당한 경우 에러 기여 2배 (에러 2개 추가)
            if has_error and pkt.is_decoy and pkt.intercepted:
                self.error_history.append(True)
                self.error_history.append(True)  # 2배 기여
            else:
                self.error_history.append(has_error)
            while len(self.error_history) > HISTORY_WINDOW:
                self.error_history.pop(0)

        # 에러율 계산
        if self.error_history:
            self.error_rate = sum(self.error_history) / len(self.error_history)

        # 미션1: 자동 차단 시스템 (15% 초과)
        if (self.auto_block_enabled
                and self.error_rate > AUTO_BLOCK_THRESHOLD
                and len(self.error_history) >= 5
                and self.channel_open):
            self.channel_open = False
            self.auto_shutdown = True
            self.shutdown_flash = 2.0
            self.auto_blocks += 1
            self.score += AUTO_BLOCK_SCORE

        # 기존 임계값 폐쇄 (25%) — 자동 차단 꺼져 있을 때 대비
        elif self.error_rate >= ERROR_THRESHOLD and len(self.error_history) >= 5:
            if self.channel_open:
                self.channel_open = False
                self.auto_shutdown = True
                self.shutdown_flash = 2.0

        # 로그 기록
        decoy_tag = " [DECOY]" if pkt.is_decoy else ""
        self.log.append({
            "round": pkt.round_id,
            "alice_basis": pkt.basis,
            "bob_basis": bob_basis,
            "match": basis_match,
            "intercepted": pkt.intercepted,
            "error": has_error,
            "decoy": pkt.is_decoy,
        })
        if len(self.log) > 12:
            self.log.pop(0)

    def manual_shutdown(self):
        """사용자 수동 통신망 폐쇄 — 미션1: 수동 차단 보너스."""
        if self.channel_open:
            self.channel_open = False
            self.shutdown_flash = 2.0
            self.manual_blocks += 1
            # 해킹 중일 때 수동 차단하면 높은 점수
            if self.error_rate > WARNING_THRESHOLD:
                self.score += MANUAL_BLOCK_SCORE

    def reopen(self):
        """통신망 재개통 (리셋 없이)."""
        self.channel_open = True
        self.auto_shutdown = False
        self.error_history.clear()
        self.error_rate = 0.0


# ── 그리기 헬퍼 ──────────────────────────────────────

def _draw_actors(screen, game: BB84Game, t: float, font, big_font):
    """Alice, Bob, Eve 캐릭터."""
    # Alice
    pygame.draw.circle(screen, ALICE_CLR, (ALICE_X, ALICE_Y), 30)
    pygame.draw.circle(screen, TEXT_CLR, (ALICE_X, ALICE_Y), 30, 2)
    label = big_font.render("Alice", True, ALICE_CLR)
    screen.blit(label, (ALICE_X - label.get_width() // 2, ALICE_Y + 38))
    role = font.render("Sender", True, (88, 91, 112))
    screen.blit(role, (ALICE_X - role.get_width() // 2, ALICE_Y + 56))

    # Bob
    pygame.draw.circle(screen, BOB_CLR, (BOB_X, BOB_Y), 30)
    pygame.draw.circle(screen, TEXT_CLR, (BOB_X, BOB_Y), 30, 2)
    label = big_font.render("Bob", True, BOB_CLR)
    screen.blit(label, (BOB_X - label.get_width() // 2, BOB_Y + 38))
    role = font.render("Receiver", True, (88, 91, 112))
    screen.blit(role, (BOB_X - role.get_width() // 2, BOB_Y + 56))

    # Eve (항상 표시, 도청 시 강조)
    eve_alpha = 255 if game.eve_active else 80
    if game.eve_flash > 0:
        # 플래시 글로우
        glow_r = int(40 + 20 * math.sin(t * 10))
        glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*EVE_CLR, int(100 * game.eve_flash)), (glow_r, glow_r), glow_r)
        screen.blit(glow, (EVE_X - glow_r, EVE_Y - glow_r))

    pygame.draw.circle(screen, (*EVE_CLR, eve_alpha) if eve_alpha < 255 else EVE_CLR, (EVE_X, EVE_Y), 24)
    pygame.draw.circle(screen, TEXT_CLR, (EVE_X, EVE_Y), 24, 2)
    label = big_font.render("Eve", True, EVE_CLR)
    screen.blit(label, (EVE_X - label.get_width() // 2, EVE_Y - 42))
    role = font.render("Eavesdropper", True, (88, 91, 112))
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
        sym = font.render(label, True, (255, 255, 255))
        screen.blit(sym, (cx - sym.get_width() // 2, cy - sym.get_height() // 2))


def _draw_error_meter(screen, game: BB84Game, font, big_font):
    """에러율 미터."""
    mx, my = 50, 380
    mw, mh = 260, 20

    label = big_font.render("Error Rate (QBER)", True, ACCENT)
    screen.blit(label, (mx, my - 24))

    # 배경
    pygame.draw.rect(screen, PANEL_BG, (mx, my, mw, mh))

    # 미션2: 10% 경고선
    warn_x = mx + int(mw * WARNING_THRESHOLD)
    pygame.draw.line(screen, (249, 226, 175), (warn_x, my - 2), (warn_x, my + mh + 2), 1)
    warn_label = font.render(f"{WARNING_THRESHOLD * 100:.0f}%", True, (249, 226, 175))
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
        fill_clr = (249, 226, 175)  # 경고색
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
    qrng_remain = shared_key_available() if _QRNG_AVAILABLE else 0
    qrng_tag = f"QRNG: {game.qrng_bits_used}bit 사용 (잔여 {qrng_remain})"

    lines = [
        (f"전송: {game.total_sent}", TEXT_CLR),
        (f"안전 수신: {game.total_safe}", SAFE_CLR),
        (f"에러 감지: {game.total_errors}", DANGER_CLR),
        (f"Eve 도청: {game.eve_intercept_count}", EVE_CLR),
        (f"디코이 발사: {game.decoy_sent}  트랩: {game.decoy_trapped}", DECOY_CLR),
        (f"자동차단: {game.auto_blocks}회  수동: {game.manual_blocks}회", ALICE_CLR),
        (qrng_tag, ACCENT if qrng_remain > 0 else (88, 91, 112)),
        (f"채널: {'OPEN' if game.channel_open else 'SHUTDOWN'}  |  자동: {'ON' if game.auto_block_enabled else 'OFF'}", SAFE_CLR if game.channel_open else DANGER_CLR),
    ]
    for i, (text, color) in enumerate(lines):
        surf = font.render(text, True, color)
        screen.blit(surf, (sx, sy + i * 16))


def _draw_log(screen, game: BB84Game, font):
    """프로토콜 로그."""
    lx, ly = 380, 340
    header = font.render("── Protocol Log ──", True, ACCENT)
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


def _draw_shutdown_banner(screen, game: BB84Game, big_font, t: float):
    """통신망 폐쇄 배너."""
    if game.shutdown_flash > 0:
        alpha = int(200 * min(game.shutdown_flash, 1.0))
        banner = pygame.Surface((WIDTH, 50), pygame.SRCALPHA)
        banner.fill((*DANGER_CLR, alpha // 3))
        screen.blit(banner, (0, CHANNEL_Y - 25))

        blink = int(t * 4) % 2 == 0
        if blink:
            msg = "CHANNEL SHUTDOWN" if game.auto_shutdown else "MANUAL SHUTDOWN"
            reason = " — Error rate exceeded threshold!" if game.auto_shutdown else ""
            text = big_font.render(f"⚠ {msg}{reason}", True, DANGER_CLR)
            screen.blit(text, (WIDTH // 2 - text.get_width() // 2, CHANNEL_Y + 60))


# ── 메인 시뮬레이션 ──────────────────────────────────

def run_simulation():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("BB84 Quantum Key Distribution Defense")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Consolas", 11)
    big_font = pygame.font.SysFont("Consolas", 14, bold=True)
    title_font = pygame.font.SysFont("Consolas", 18, bold=True)

    game = BB84Game()
    t = 0.0
    paused = False

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
                elif event.key == pygame.K_SPACE:
                    if game.channel_open:
                        game.manual_shutdown()
                    else:
                        game.reopen()
                elif event.key == pygame.K_r:
                    game.reset()
                elif event.key == pygame.K_p:
                    paused = not paused
                elif event.key == pygame.K_a:
                    # 미션1: 자동 차단 토글
                    game.auto_block_enabled = not game.auto_block_enabled

        # ── 업데이트 ─────────────────────────────────
        if not paused:
            # 전송 타이머
            game.send_timer += dt
            if game.send_timer >= SEND_INTERVAL:
                game.send_timer = 0.0
                game.new_round()

            # 패킷 이동
            for pkt in game.packets:
                pkt.update(dt)
                if pkt.arrived:
                    game.process_arrival(pkt)

            # 도착한 패킷 제거
            game.packets = [p for p in game.packets if not p.arrived]

            # 플래시 타이머
            if game.eve_flash > 0:
                game.eve_flash -= dt
            if game.shutdown_flash > 0:
                game.shutdown_flash -= dt

        # ── 렌더링 ───────────────────────────────────

        # 미션2: 에러율 10% 초과 시 배경을 짙은 빨강으로 번쩍
        if game.error_rate > WARNING_THRESHOLD and game.channel_open:
            # 번쩍거리는 효과 — sin으로 강도 변조
            flash_intensity = 0.5 + 0.5 * math.sin(t * 6)
            r = int(BG[0] + (WARNING_BG[0] - BG[0]) * flash_intensity)
            g = int(BG[1] + (WARNING_BG[1] - BG[1]) * flash_intensity)
            b = int(BG[2] + (WARNING_BG[2] - BG[2]) * flash_intensity)
            screen.fill((r, g, b))
        else:
            screen.fill(BG)

        # 타이틀
        title = title_font.render("BB84 Quantum Key Distribution Defense", True, ACCENT)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 12))

        # 채널
        _draw_channel(screen, game)

        # 패킷
        _draw_packets(screen, game, font)

        # 캐릭터
        _draw_actors(screen, game, t, font, big_font)

        # 에러 미터
        _draw_error_meter(screen, game, font, big_font)

        # 통계
        _draw_stats(screen, game, font, big_font)

        # 로그
        _draw_log(screen, game, font)

        # 폐쇄 배너
        _draw_shutdown_banner(screen, game, big_font, t)

        # 안내
        hints = [
            f"SCORE: {game.score}  |  자동차단: {'ON' if game.auto_block_enabled else 'OFF'}  |  {'일시정지' if paused else '실행 중'}",
            "SPACE: 폐쇄/재개  |  A: 자동차단 토글  |  P: 일시정지",
            "R: 리셋  |  ESC: 종료",
        ]
        for i, h in enumerate(hints):
            surf = font.render(h, True, TEXT_CLR)
            screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 52 + i * 16))

        pygame.display.flip()

    # 최종미션: 플레이 기록 저장
    try:
        from data_ai.play_logger import get_logger
        get_logger().log_session("bb84_defense", {
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
        })
    except Exception:
        pass

    pygame.quit()


def open_bb84_defense():
    """외부에서 호출하는 진입점."""
    run_simulation()
