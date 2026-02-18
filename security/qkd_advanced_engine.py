"""고급 QKD 프로토콜 엔진 — E91 · 키 시프팅 · 다자간 QKD.

순수 Python 로직 (Pygame 불필요, 단위 테스트 가능):
  - E91 프로토콜: 얽힘 기반 양자 키 분배 + 벨 부등식 보안 검증
  - 키 시프팅 & 프라이버시 증폭: 원시 키 → 시프트 키 → 최종 보안 키
  - 다자간 QKD: GHZ 상태 기반 3자간 키 분배

E91 프로토콜 흐름:
  1. EPR 소스에서 |Φ+⟩ 벨 쌍 생성
  2. Alice: {0°, π/8, π/4} 기저 중 랜덤 선택하여 측정
  3. Bob: {π/8, π/4, 3π/8} 기저 중 랜덤 선택하여 측정
  4. 기저 공개 → 같은 기저: 키 비트 | 다른 기저: 벨 부등식 검증
  5. S ≈ 2√2 이면 안전 → 키 시프팅 → 프라이버시 증폭

다자간 QKD:
  GHZ 상태 |000⟩+|111⟩)/√2 로 3자간 상관 키 생성
"""

import math
import random
from dataclasses import dataclass, field

from config_loader import cfg

# QRNG 키 통합 — 모듈이 있으면 양자 난수 사용
try:
    from data_ai.qrng_logger import pop_key_bit, shared_key_available

    QRNG_AVAILABLE = True
except ImportError:
    QRNG_AVAILABLE = False

    def pop_key_bit():  # noqa: E306
        return None

    def shared_key_available() -> int:  # noqa: E306
        return 0

# ── E91 설정 ──────────────────────────────────────────
E91_ALICE_BASES = [0.0, math.pi / 8, math.pi / 4]  # a1=0, a2=π/8, a3=π/4
E91_BOB_BASES = [math.pi / 8, math.pi / 4, 3 * math.pi / 8]  # b1=π/8, b2=π/4, b3=3π/8

# 키 생성용 기저 쌍 인덱스 — 같은 각도를 공유하는 쌍:
#   (1, 0): Alice a2=π/8, Bob b1=π/8 → 같은 기저 → 키 생성
#   (2, 1): Alice a3=π/4, Bob b2=π/4 → 같은 기저 → 키 생성
# 나머지 7쌍은 CHSH 벨 부등식 검증에 사용
E91_KEY_PAIRS = [(1, 0), (2, 1)]  # (Alice idx, Bob idx) 같은 기저 쌍

CHSH_CLASSICAL_BOUND = 2.0
CHSH_QUANTUM_BOUND = 2.0 * math.sqrt(2)

# 프라이버시 증폭 설정
PA_COMPRESSION_RATIO = cfg("qkd_advanced", "pa_compression", 0.5)

# 다자간 QKD 설정
GHZ_PARTIES = 3
GHZ_MIN_PARTIES = 3
GHZ_MAX_PARTIES = 5
_GHZ_PARTY_NAMES = ["Alice", "Bob", "Charlie", "Dave", "Erin"]


def _qrng_randint(lo: int, hi: int) -> int:
    """QRNG 비트로 [lo, hi] 범위의 랜덤 정수 생성. 없으면 의사 난수."""
    n = hi - lo + 1
    bit = pop_key_bit()
    if bit is not None:
        # 추가 비트가 필요하면 폴백
        if n <= 2:
            return lo + (bit % n)
        bit2 = pop_key_bit()
        if bit2 is not None:
            combined = (bit << 1) | bit2
            return lo + (combined % n)
    return random.randint(lo, hi)


# ── E91 프로토콜 ──────────────────────────────────────


@dataclass
class E91Round:
    """E91 프로토콜 1 라운드 결과."""
    round_id: int
    alice_basis_idx: int
    bob_basis_idx: int
    alice_angle: float
    bob_angle: float
    alice_result: int  # +1 or -1
    bob_result: int    # +1 or -1
    same_basis: bool   # 키 생성에 사용
    eve_present: bool  # Eve 도청 여부
    key_bit: int | None = None  # 키 비트 (같은 기저일 때만)


@dataclass
class E91State:
    """E91 프로토콜 전체 상태."""
    rounds: list[E91Round] = field(default_factory=list)
    raw_key_alice: list[int] = field(default_factory=list)
    raw_key_bob: list[int] = field(default_factory=list)
    final_key: str = ""

    # 벨 부등식 검증
    correlators: dict[tuple[int, int], list[float]] = field(default_factory=dict)
    bell_S: float = 0.0
    bell_violated: bool = False
    bell_S_history: list[tuple[int, float]] = field(default_factory=list)  # (round, S)

    # 통계
    total_rounds: int = 0
    key_rounds: int = 0
    bell_rounds: int = 0
    eve_detected: bool = False
    eve_rounds: int = 0

    # ── QKD 후처리 파이프라인 상태 ──
    # Stage 1: QBER 추정 (원시 키의 일부를 샘플링하여 에러율 추정)
    qber_sample_size: int = 0        # 샘플링한 비트 수
    qber_value: float = 0.0          # 추정된 QBER
    qber_done: bool = False

    # Stage 2: 에러 정정 (블록 패리티 기반)
    corrected_key: list[int] = field(default_factory=list)
    bob_remaining: list[int] = field(default_factory=list)  # Bob 측 남은 키 (에러 정정용)
    correction_done: bool = False
    correction_flips: int = 0        # 정정된 비트 수

    # Stage 3: 프라이버시 증폭
    sifted_key: list[int] = field(default_factory=list)   # 최종 시프트 키 (호환용)
    sift_done: bool = False
    pa_done: bool = False
    error_rate: float = 0.0
    key_match_rate: float = 0.0


def _measure_entangled(angle_a: float, angle_b: float,
                       eve_present: bool = False) -> tuple[int, int]:
    """얽힘 쌍의 측정 시뮬레이션 (광자 편광 모델).

    |Φ+⟩ 상태에서 편광 각도 a, b로 측정 시:
    P(같은 결과) = cos²(a - b)
    P(다른 결과) = sin²(a - b)

    상관 함수 E(a,b) = cos(2(a-b)) → CHSH S = 2√2 도달 가능.
    Eve가 있으면 상관관계가 약해짐.
    """
    diff = angle_a - angle_b

    if eve_present:
        # Eve 도청 → 얽힘 파괴 → 고전적 상관관계로 전락
        # 노이즈 추가로 벨 부등식 위반이 줄어듦
        noise = random.gauss(0, 0.3)
        diff += noise

    # 상관 확률 (광자 편광: cos²(θ))
    p_same = math.cos(diff) ** 2

    # Alice 결과
    alice = random.choice([+1, -1])

    # Bob 결과 (상관관계에 따라)
    if random.random() < p_same:
        bob = alice  # 같은 결과
    else:
        bob = -alice  # 다른 결과

    return alice, bob


def e91_round(state: E91State, eve_chance: float = 0.0) -> E91Round:
    """E91 프로토콜 1 라운드 실행."""
    state.total_rounds += 1
    rid = state.total_rounds

    # 기저 랜덤 선택 (QRNG 가용 시 양자 난수 사용)
    a_idx = _qrng_randint(0, 2)
    b_idx = _qrng_randint(0, 2)
    a_angle = E91_ALICE_BASES[a_idx]
    b_angle = E91_BOB_BASES[b_idx]

    # Eve 도청
    eve_present = random.random() < eve_chance
    if eve_present:
        state.eve_rounds += 1

    # 측정
    a_result, b_result = _measure_entangled(a_angle, b_angle, eve_present)

    # 같은 기저인지 확인
    same_basis = (a_idx, b_idx) in E91_KEY_PAIRS
    key_bit = None

    if same_basis:
        # 키 비트 생성 (Alice 결과 기반, +1→1, -1→0)
        key_bit = 1 if a_result == +1 else 0
        bob_key = 1 if b_result == +1 else 0
        state.raw_key_alice.append(key_bit)
        state.raw_key_bob.append(bob_key)
        state.key_rounds += 1
    else:
        # 벨 부등식 검증용 데이터 수집
        pair = (a_idx, b_idx)
        if pair not in state.correlators:
            state.correlators[pair] = []
        state.correlators[pair].append(a_result * b_result)
        state.bell_rounds += 1

    rd = E91Round(
        round_id=rid,
        alice_basis_idx=a_idx,
        bob_basis_idx=b_idx,
        alice_angle=a_angle,
        bob_angle=b_angle,
        alice_result=a_result,
        bob_result=b_result,
        same_basis=same_basis,
        eve_present=eve_present,
        key_bit=key_bit,
    )
    state.rounds.append(rd)
    if len(state.rounds) > 200:
        state.rounds.pop(0)

    return rd


def compute_bell_S(state: E91State) -> float:
    """CHSH 파라미터 S 계산.

    S = E(a1,b1) - E(a1,b3) + E(a3,b1) + E(a3,b3)

    E91 기저: a1=0, a2=π/8, a3=π/4, b1=π/8, b2=π/4, b3=3π/8
    키 쌍: (a2,b1)=(1,0), (a3,b2)=(2,1) → 이 쌍은 correlators에 없음
    CHSH 쌍: (a1,b1)=(0,0), (a1,b3)=(0,2), (a3,b1)=(2,0), (a3,b3)=(2,2)
    양자 이론: S = 2√2 ≈ 2.828 (광자 편광 모델)
    """
    def _avg(pair):
        data = state.correlators.get(pair, [])
        if not data:
            return 0.0
        return sum(data) / len(data)

    # CHSH 4개 상관 함수 (모두 키 쌍이 아니므로 correlators에 데이터 존재)
    e00 = _avg((0, 0))  # E(a1=0°, b1=π/8)
    e02 = _avg((0, 2))  # E(a1=0°, b3=3π/8)
    e20 = _avg((2, 0))  # E(a3=π/4, b1=π/8)
    e22 = _avg((2, 2))  # E(a3=π/4, b3=3π/8)

    S = e00 - e02 + e20 + e22

    state.bell_S = S
    state.bell_violated = abs(S) > CHSH_CLASSICAL_BOUND
    state.eve_detected = not state.bell_violated and state.bell_rounds > 20

    # S 수렴 히스토리 기록 (최대 200개)
    state.bell_S_history.append((state.total_rounds, S))
    if len(state.bell_S_history) > 200:
        state.bell_S_history.pop(0)

    return S


# ── QKD 후처리 파이프라인 ─────────────────────────────
#
# 실제 QKD 후처리 단계:
#   1. 기저 시프팅   — e91_round에서 이미 수행 (같은 기저만 raw_key에 추가)
#   2. QBER 추정    — 원시 키의 일부를 공개 비교하여 에러율 추정
#   3. 에러 정정    — 블록 패리티 기반으로 나머지 비트의 에러 수정
#   4. 프라이버시 증폭 — 해시 압축으로 Eve의 부분 정보 제거
#
# 주의: 교육용 단순화 시뮬레이션입니다. 실제 구현은 Cascade/LDPC
#       에러 정정과 Toeplitz 범용 해시를 사용합니다.


# QBER 추정에 사용할 샘플 비율 (공개 후 폐기)
_QBER_SAMPLE_RATIO = 0.2


def estimate_qber(state: E91State) -> float:
    """Stage 1: QBER 추정 — 원시 키의 일부를 공개 비교.

    실제 프로토콜에서는 Alice와 Bob이 원시 키의 무작위 부분집합을
    공개 채널로 비교하여 QBER(양자 비트 에러율)을 추정합니다.
    공개된 비트는 보안이 깨지므로 폐기합니다.

    QBER > 11%이면 도청이 의심되어 키를 폐기해야 합니다.
    """
    if not state.raw_key_alice:
        state.qber_done = True
        return 0.0

    n = len(state.raw_key_alice)
    sample_n = max(2, int(n * _QBER_SAMPLE_RATIO))

    # 무작위 인덱스 샘플링
    indices = list(range(n))
    random.shuffle(indices)
    sample_indices = set(indices[:sample_n])
    remaining_indices = [i for i in range(n) if i not in sample_indices]

    # 샘플 비교 → QBER 추정
    errors = sum(
        1 for i in sample_indices
        if state.raw_key_alice[i] != state.raw_key_bob[i]
    )
    state.qber_sample_size = sample_n
    state.qber_value = errors / sample_n if sample_n > 0 else 0.0
    state.qber_done = True

    # 샘플 제외한 나머지를 sifted_key로 보존 (아직 에러 포함)
    state.sifted_key = [state.raw_key_alice[i] for i in remaining_indices]
    # Bob 측 키도 에러 정정용으로 보관
    state.bob_remaining = [state.raw_key_bob[i] for i in remaining_indices]

    state.error_rate = state.qber_value
    state.key_match_rate = 1.0 - state.qber_value

    return state.qber_value


def error_correct(state: E91State) -> list[int]:
    """Stage 2: 에러 정정 — 블록 패리티 기반 (교육용 단순화).

    실제 프로토콜: Cascade 또는 LDPC 코드를 사용하여
    Alice/Bob 키의 불일치 비트를 수정합니다.
    여기서는 교육 목적으로 블록 단위 패리티 검사를 시뮬레이션합니다:
      1. 키를 4비트 블록으로 분할
      2. 각 블록의 패리티를 공개 비교
      3. 패리티 불일치 블록에서 이진 탐색으로 에러 비트 특정
    """
    if not state.qber_done:
        return []

    alice_key = state.sifted_key
    bob_key = state.bob_remaining

    if not alice_key or not bob_key:
        state.corrected_key = list(alice_key)
        state.correction_done = True
        state.correction_flips = 0
        return state.corrected_key

    corrected = list(alice_key)
    flips = 0
    block_size = 4

    for start in range(0, len(corrected), block_size):
        end = min(start + block_size, len(corrected))
        a_parity = sum(corrected[start:end]) % 2
        b_parity = sum(bob_key[start:end]) % 2

        if a_parity != b_parity:
            # 블록 내 이진 탐색으로 에러 비트 찾기
            lo, hi = start, end
            while hi - lo > 1:
                mid = (lo + hi) // 2
                a_sub = sum(corrected[lo:mid]) % 2
                b_sub = sum(bob_key[lo:mid]) % 2
                if a_sub != b_sub:
                    hi = mid
                else:
                    lo = mid
            # lo 위치의 비트 수정
            corrected[lo] = bob_key[lo]
            flips += 1

    state.corrected_key = corrected
    state.correction_done = True
    state.correction_flips = flips
    state.sift_done = True

    return corrected


def key_sift(state: E91State) -> list[int]:
    """전체 키 시프팅 파이프라인 실행 (QBER 추정 + 에러 정정).

    편의 함수: estimate_qber → error_correct 를 순차 실행합니다.
    """
    if not state.raw_key_alice:
        state.sift_done = True
        return []

    estimate_qber(state)
    error_correct(state)

    return state.corrected_key


def _toeplitz_hash(key_bits: list[int], output_len: int,
                   seed: list[int] | None = None) -> tuple[list[int], list[int]]:
    """Toeplitz 범용 해시 (2-universal hash family).

    Toeplitz 행렬은 대각선이 일정한 행렬로, 첫 행과 첫 열만으로
    전체 행렬을 정의할 수 있습니다.

    구조:
      - 입력: n-bit 키 벡터 x
      - 시드: (m + n - 1) 랜덤 비트 r (공개 — Eve도 알지만 보안에 영향 없음)
      - Toeplitz 행렬 T: m×n, T[i][j] = r[i + j]
      - 출력: y = T · x (mod 2), m-bit 압축 키

    보안 보장 (Leftover Hash Lemma):
      m ≤ n - t 이면, Eve의 정보 t 비트를 완전히 제거 가능.
      즉 출력 키는 균등 분포에 통계적으로 가까움.

    Returns:
        (output_bits, seed): 압축된 비트 리스트와 사용된 시드
    """
    n = len(key_bits)
    m = output_len

    if n == 0 or m == 0:
        return [], seed or []

    # 시드 생성 (m + n - 1 랜덤 비트)
    seed_len = m + n - 1
    if seed is None:
        seed = [random.randint(0, 1) for _ in range(seed_len)]
    elif len(seed) < seed_len:
        # 시드가 짧으면 확장
        seed = seed + [random.randint(0, 1) for _ in range(seed_len - len(seed))]

    # T · x (mod 2) — 행렬 곱을 직접 계산
    # T[i][j] = seed[i + j], 출력 y[i] = Σ_j T[i][j] · x[j] (mod 2)
    output = []
    for i in range(m):
        bit_sum = 0
        for j in range(n):
            bit_sum ^= seed[i + j] & key_bits[j]
        output.append(bit_sum)

    return output, seed


def privacy_amplification(state: E91State) -> str:
    """Stage 3: 프라이버시 증폭 — Toeplitz 범용 해시로 최종 보안 키 생성.

    Eve가 QBER 추정/에러 정정 과정에서 노출된 패리티 정보를 통해
    부분 키 정보를 가질 수 있습니다. Toeplitz 범용 해시로 키를 압축하여
    Eve의 정보를 정보이론적으로 제거합니다.

    Toeplitz 해시는 2-universal hash family의 구성원으로,
    Leftover Hash Lemma에 의해 출력 키가 균등 분포에 가까워짐을 보장합니다.
    """
    # 에러 정정된 키 또는 시프트 키 사용
    key_source = state.corrected_key if state.corrected_key else state.sifted_key

    if not key_source:
        state.final_key = ""
        state.pa_done = True
        return ""

    # 출력 길이 결정: 입력의 PA_COMPRESSION_RATIO 배 (Eve 정보량만큼 단축)
    n = len(key_source)
    output_bits = max(8, int(n * PA_COMPRESSION_RATIO))

    # Toeplitz 해시 적용
    hashed_bits, _seed = _toeplitz_hash(key_source, output_bits)

    # 비트 → 16진수 문자열 변환
    hex_chars = []
    for i in range(0, len(hashed_bits) - 3, 4):
        nibble = (hashed_bits[i] << 3 | hashed_bits[i + 1] << 2 |
                  hashed_bits[i + 2] << 1 | hashed_bits[i + 3])
        hex_chars.append(f"{nibble:x}")
    final = "".join(hex_chars)

    state.final_key = final
    state.pa_done = True

    return final


# ── OTP 암호화 데모 (QKD 키 활용) ─────────────────────
#
# QKD로 생성된 키를 One-Time Pad (XOR)로 사용하여
# 메시지를 암호화/복호화하는 교육용 데모.
# OTP는 키 길이 ≥ 메시지 길이일 때 정보이론적으로 안전합니다.

_DEMO_PLAINTEXT = "QUANTUM OK"


def xor_encrypt(plaintext: str, key_hex: str) -> str:
    """OTP(XOR) 암호화 — 평문 + 키(hex) → 암호문(hex).

    키가 평문보다 짧으면 사용 가능한 길이만큼만 암호화합니다.
    """
    if not key_hex:
        return ""
    try:
        key_bytes = bytes.fromhex(key_hex.ljust(len(key_hex) + len(key_hex) % 2, "0"))
    except ValueError:
        return ""
    plain_bytes = plaintext.encode("utf-8")
    # 키 길이 제한
    n = min(len(plain_bytes), len(key_bytes))
    cipher = bytes(p ^ k for p, k in zip(plain_bytes[:n], key_bytes[:n]))
    return cipher.hex()


def xor_decrypt(ciphertext_hex: str, key_hex: str) -> str:
    """OTP(XOR) 복호화 — 암호문(hex) + 키(hex) → 평문."""
    if not ciphertext_hex or not key_hex:
        return ""
    try:
        cipher_bytes = bytes.fromhex(ciphertext_hex)
        key_bytes = bytes.fromhex(key_hex.ljust(len(key_hex) + len(key_hex) % 2, "0"))
    except ValueError:
        return ""
    n = min(len(cipher_bytes), len(key_bytes))
    plain = bytes(c ^ k for c, k in zip(cipher_bytes[:n], key_bytes[:n]))
    return plain.decode("utf-8", errors="replace")


# ── 다자간 QKD (GHZ 기반) ────────────────────────────


@dataclass
class GHZRound:
    """GHZ N자간 QKD 1 라운드."""
    round_id: int
    bases: list[str]       # 각 파티의 기저 ("X" 또는 "Z")
    results: list[int]     # 각 파티의 측정 결과 (0 or 1)
    all_same_basis: bool   # 모든 파티가 같은 기저
    key_bit: int | None    # 키 비트 (Z 기저 일치 시)
    eve_present: bool


@dataclass
class GHZState:
    """GHZ 다자간 QKD 상태."""
    n_parties: int = GHZ_PARTIES
    party_names: list[str] = field(default_factory=lambda: list(_GHZ_PARTY_NAMES[:GHZ_PARTIES]))
    rounds: list[GHZRound] = field(default_factory=list)

    # 키
    raw_keys: list[list[int]] = field(default_factory=lambda: [[] for _ in range(GHZ_PARTIES)])
    sifted_key: list[int] = field(default_factory=list)
    final_key: str = ""

    # 통계
    total_rounds: int = 0
    key_rounds: int = 0
    consistency_checks: int = 0
    consistency_pass: int = 0
    eve_rounds: int = 0
    error_rate: float = 0.0
    # 일관성 패스율 히스토리 (수렴 그래프용)
    consistency_history: list[tuple[int, float]] = field(default_factory=list)

    # 상태
    sift_done: bool = False
    pa_done: bool = False


def _ghz_measure(bases: list[str], eve_present: bool = False) -> list[int]:
    """GHZ 상태 |0...0⟩+|1...1⟩)/√2 측정 시뮬레이션 (N자간).

    Z 기저: 0...0 또는 1...1 (50:50) → 모든 파티 같은 결과
    X 기저: GHZ 상관관계 → 짝수 패리티
    """
    n = len(bases)
    all_z = all(b == "Z" for b in bases)
    all_x = all(b == "X" for b in bases)

    if all_z:
        # Z 기저: 모든 파티가 같은 결과
        bit = random.randint(0, 1)
        results = [bit] * n
        if eve_present:
            # Eve 도청 → 상관관계 파괴
            for i in range(n):
                if random.random() < 0.3:
                    results[i] = 1 - results[i]
    elif all_x:
        # X 기저: GHZ 상관관계 (짝수 패리티)
        results = [random.randint(0, 1) for _ in range(n)]
        # 짝수 패리티 보장
        parity = sum(results) % 2
        if parity != 0:
            idx = random.randint(0, n - 1)
            results[idx] = 1 - results[idx]
        if eve_present:
            # Eve → 패리티 깨짐
            if random.random() < 0.4:
                idx = random.randint(0, n - 1)
                results[idx] = 1 - results[idx]
    else:
        # 혼합 기저: 무작위 (키에 사용 불가)
        results = [random.randint(0, 1) for _ in range(n)]

    return results


def ghz_round(state: GHZState, eve_chance: float = 0.0) -> GHZRound:
    """GHZ QKD 1 라운드 실행."""
    state.total_rounds += 1
    rid = state.total_rounds

    # 각 파티 기저 랜덤 선택 (QRNG 가용 시 양자 난수 사용)
    bases = ["Z" if _qrng_randint(0, 1) == 0 else "X" for _ in range(state.n_parties)]

    eve_present = random.random() < eve_chance
    if eve_present:
        state.eve_rounds += 1

    results = _ghz_measure(bases, eve_present)

    all_same = len(set(bases)) == 1
    key_bit = None

    if all_same and bases[0] == "Z":
        # Z 기저 일치 → 키 비트 생성
        key_bit = results[0]
        for i in range(state.n_parties):
            state.raw_keys[i].append(results[i])
        state.key_rounds += 1
    elif all_same and bases[0] == "X":
        # X 기저 일치 → 일관성 검증 (짝수 패리티 확인)
        parity = sum(results) % 2
        state.consistency_checks += 1
        if parity == 0:
            state.consistency_pass += 1
        # 일관성 패스율 히스토리 기록 (10회 검증마다)
        if state.consistency_checks % 10 == 0 and state.consistency_checks > 0:
            pass_rate = state.consistency_pass / state.consistency_checks
            state.consistency_history.append((state.total_rounds, pass_rate))
            if len(state.consistency_history) > 200:
                state.consistency_history.pop(0)

    rd = GHZRound(
        round_id=rid,
        bases=bases,
        results=results,
        all_same_basis=all_same,
        key_bit=key_bit,
        eve_present=eve_present,
    )
    state.rounds.append(rd)
    if len(state.rounds) > 200:
        state.rounds.pop(0)

    return rd


def ghz_key_sift(state: GHZState) -> list[int]:
    """GHZ 키 시프팅: 모든 파티의 키가 일치하는 비트만 추출."""
    if not state.raw_keys[0]:
        state.sift_done = True
        return []

    sifted = []
    errors = 0
    n = len(state.raw_keys[0])

    for i in range(n):
        bits = [state.raw_keys[p][i] for p in range(state.n_parties)]
        if len(set(bits)) == 1:
            sifted.append(bits[0])
        else:
            errors += 1

    state.sifted_key = sifted
    state.sift_done = True
    state.error_rate = errors / n if n > 0 else 0.0

    return sifted


def ghz_privacy_amplification(state: GHZState) -> str:
    """GHZ 프라이버시 증폭 — Toeplitz 범용 해시."""
    if not state.sifted_key:
        state.final_key = ""
        state.pa_done = True
        return ""

    n = len(state.sifted_key)
    output_bits = max(8, int(n * PA_COMPRESSION_RATIO))
    hashed_bits, _seed = _toeplitz_hash(state.sifted_key, output_bits)

    hex_chars = []
    for i in range(0, len(hashed_bits) - 3, 4):
        nibble = (hashed_bits[i] << 3 | hashed_bits[i + 1] << 2 |
                  hashed_bits[i + 2] << 1 | hashed_bits[i + 3])
        hex_chars.append(f"{nibble:x}")
    final = "".join(hex_chars)

    state.final_key = final
    state.pa_done = True
    return final


# ── BB84 간이 시뮬레이션 (비교 모드용) ────────────────
#
# bb84_protocol.py의 풀 게임 로직 대신, 비교 모드에서
# E91과 동일 Eve 조건으로 순수 BB84 통계만 수집하는 경량 엔진.


BB84_BASES = ["+", "×"]


@dataclass
class BB84State:
    """BB84 프로토콜 상태 (비교 모드용)."""
    total_rounds: int = 0
    basis_match_rounds: int = 0
    error_count: int = 0
    eve_rounds: int = 0
    raw_key_bits: int = 0
    qber: float = 0.0
    eve_detected: bool = False
    # 슬라이딩 QBER
    _recent_matches: list[bool] = field(default_factory=list)
    _recent_errors: list[bool] = field(default_factory=list)
    # QBER 히스토리 (수렴 그래프용)
    qber_history: list[tuple[int, float]] = field(default_factory=list)


def bb84_round(state: BB84State, eve_chance: float = 0.0) -> dict:
    """BB84 프로토콜 1 라운드 (비교 모드용).

    Returns:
        dict with keys: basis_match, has_error, eve_present
    """
    state.total_rounds += 1

    alice_basis = random.choice(BB84_BASES)
    bob_basis = random.choice(BB84_BASES)
    alice_bit = random.randint(0, 1)

    eve_present = random.random() < eve_chance
    if eve_present:
        state.eve_rounds += 1

    # Eve 도청: 랜덤 기저로 측정 → 기저 불일치 시 50% 확률로 비트 오염
    # BB84 QBER 이론값: Eve 도청 시 25% (기저 불일치 50% × 비트 오류 50%)
    corrupted = False
    if eve_present:
        eve_basis = random.choice(BB84_BASES)
        if eve_basis != alice_basis and random.random() < 0.5:
            corrupted = True

    basis_match = alice_basis == bob_basis
    has_error = False

    if basis_match:
        state.basis_match_rounds += 1
        state.raw_key_bits += 1
        if corrupted:
            has_error = True
            state.error_count += 1

        state._recent_matches.append(True)
        state._recent_errors.append(has_error)
        # 슬라이딩 윈도우 (최근 50개)
        if len(state._recent_matches) > 50:
            state._recent_matches.pop(0)
            state._recent_errors.pop(0)

    # QBER 계산
    if state._recent_matches:
        n_match = len(state._recent_errors)
        n_err = sum(state._recent_errors)
        state.qber = n_err / n_match if n_match > 0 else 0.0
    state.eve_detected = state.qber > 0.11 and state.basis_match_rounds > 10

    # QBER 히스토리 기록 (10 라운드마다)
    if state.total_rounds % 10 == 0 and state.basis_match_rounds > 0:
        state.qber_history.append((state.total_rounds, state.qber))
        if len(state.qber_history) > 200:
            state.qber_history.pop(0)

    return {"basis_match": basis_match, "has_error": has_error, "eve_present": eve_present}


def reset_bb84(state: BB84State):
    """BB84 상태 리셋."""
    state.total_rounds = 0
    state.basis_match_rounds = 0
    state.error_count = 0
    state.eve_rounds = 0
    state.raw_key_bits = 0
    state.qber = 0.0
    state.eve_detected = False
    state._recent_matches.clear()
    state._recent_errors.clear()
    state.qber_history.clear()


# ── 리셋 ─────────────────────────────────────────────


def reset_e91(state: E91State):
    """E91 상태 리셋."""
    state.rounds.clear()
    state.raw_key_alice.clear()
    state.raw_key_bob.clear()
    state.sifted_key.clear()
    state.corrected_key.clear()
    state.final_key = ""
    state.correlators.clear()
    state.bell_S = 0.0
    state.bell_violated = False
    state.bell_S_history.clear()
    state.total_rounds = 0
    state.key_rounds = 0
    state.bell_rounds = 0
    state.eve_detected = False
    state.eve_rounds = 0
    # 파이프라인 상태
    state.qber_sample_size = 0
    state.qber_value = 0.0
    state.qber_done = False
    state.correction_done = False
    state.correction_flips = 0
    state.sift_done = False
    state.pa_done = False
    state.error_rate = 0.0
    state.key_match_rate = 0.0
    state.bob_remaining.clear()


def reset_ghz(state: GHZState):
    """GHZ 상태 리셋 (파티 수 유지)."""
    state.rounds.clear()
    state.raw_keys = [[] for _ in range(state.n_parties)]
    state.sifted_key.clear()
    state.final_key = ""
    state.total_rounds = 0
    state.key_rounds = 0
    state.consistency_checks = 0
    state.consistency_pass = 0
    state.eve_rounds = 0
    state.error_rate = 0.0
    state.consistency_history.clear()
    state.sift_done = False
    state.pa_done = False


def resize_ghz(state: GHZState, n_parties: int):
    """파티 수를 변경하고 상태를 리셋."""
    n_parties = max(GHZ_MIN_PARTIES, min(GHZ_MAX_PARTIES, n_parties))
    state.n_parties = n_parties
    state.party_names = list(_GHZ_PARTY_NAMES[:n_parties])
    reset_ghz(state)
