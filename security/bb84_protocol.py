"""BB84 프로토콜 엔진 — bb84_defense에서 분리된 순수 프로토콜 로직.

렌더링(Pygame)에 의존하지 않으며, 단위 테스트가 가능합니다.

사용법:
    from security.bb84_protocol import BB84Game, QubitPacket

    game = BB84Game()
    game.new_round(eve_chance=0.25)
"""

import random

from config_loader import cfg

# QRNG 키 통합 — 모듈이 있으면 양자 해시 키 사용
try:
    from data_ai.qrng_logger import pop_key_bit, shared_key_available
    QRNG_AVAILABLE = True
except ImportError:
    QRNG_AVAILABLE = False

    def pop_key_bit():          # noqa: E306
        return None

    def shared_key_available() -> int:  # noqa: E306
        return 0

# ── 레이아웃 ─────────────────────────────────────────
ALICE_X, ALICE_Y = 100, 250
BOB_X, BOB_Y = 800, 250
CHANNEL_Y = 250
EVE_X, EVE_Y = 450, 100

# ── 프로토콜 파라미터 (config.json에서 로드) ─────────
BASES = ["+", "×"]
BITS = ["0", "1"]
SEND_INTERVAL = cfg("bb84", "send_interval", 1.2)
EVE_CHANCE = cfg("bb84", "eve_chance", 0.25)
EVE_ERROR_INJECT = cfg("bb84", "eve_error_inject", 0.50)
ERROR_THRESHOLD = cfg("bb84", "error_threshold", 0.25)
HISTORY_WINDOW = cfg("bb84", "history_window", 20)

# ── 자동 차단 시스템 ────────────────────────────────
AUTO_BLOCK_THRESHOLD = cfg("bb84", "auto_block_threshold", 0.15)
AUTO_BLOCK_SCORE = cfg("bb84", "auto_block_score", 50)
MANUAL_BLOCK_SCORE = cfg("bb84", "manual_block_score", 100)

# ── 경고 알람 ───────────────────────────────────────
WARNING_THRESHOLD = cfg("bb84", "warning_threshold", 0.10)

# ── 디코이 상태 ─────────────────────────────────────
DECOY_CHANCE = cfg("bb84", "decoy_chance", 0.15)
DECOY_ERROR_MULT = cfg("bb84", "decoy_error_mult", 2.0)


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

    def new_round(self, eve_chance: float = EVE_CHANCE,
                  decoy_chance: float = DECOY_CHANCE):
        """새 큐비트 전송 라운드."""
        if not self.channel_open:
            return

        self.round_id += 1

        # 미션3 (5-2): QRNG 키가 있으면 양자 해시 비트를 Alice가 전송
        qrng_bit = pop_key_bit()
        if qrng_bit is not None:
            alice_bit = str(qrng_bit)
            self.qrng_bits_used += 1
        else:
            alice_bit = random.choice(BITS)

        alice_basis = random.choice(BASES)

        # 미션3: 디코이 패킷 — Alice가 가끔 가짜 데이터 삽입
        is_decoy = random.random() < decoy_chance
        pkt = QubitPacket(alice_bit, alice_basis, self.round_id, is_decoy=is_decoy)
        if is_decoy:
            self.decoy_sent += 1

        # Eve 도청 여부
        eve_present = random.random() < eve_chance
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

    def process_arrival(self, pkt: QubitPacket,
                        auto_block_thresh: float = AUTO_BLOCK_THRESHOLD):
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

        # 미션1: 자동 차단 시스템
        if (self.auto_block_enabled
                and self.error_rate > auto_block_thresh
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
