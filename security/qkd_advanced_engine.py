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

import hashlib
import math
import random
from dataclasses import dataclass, field

from config_loader import cfg

# ── E91 설정 ──────────────────────────────────────────
E91_ALICE_BASES = [0.0, math.pi / 8, math.pi / 4]  # a1=0, a2=π/8, a3=π/4
E91_BOB_BASES = [math.pi / 8, math.pi / 4, 3 * math.pi / 8]  # b1=π/8, b2=π/4, b3=3π/8

# 키 생성용 기저 쌍 인덱스 (Alice a3=π/4, Bob b1=π/8 → 같은 기저 아님!)
# 실제 E91: Alice a2=π/8, Bob b1=π/8 → 같은 기저 → 키 생성
# Alice a3=π/4, Bob b2=π/4 → 같은 기저 → 키 생성
E91_KEY_PAIRS = [(1, 0), (2, 1)]  # (Alice idx, Bob idx) 같은 기저 쌍

CHSH_CLASSICAL_BOUND = 2.0
CHSH_QUANTUM_BOUND = 2.0 * math.sqrt(2)

# 프라이버시 증폭 설정
PA_COMPRESSION_RATIO = cfg("qkd_advanced", "pa_compression", 0.5)

# 다자간 QKD 설정
GHZ_PARTIES = 3


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
    sifted_key: list[int] = field(default_factory=list)
    final_key: str = ""

    # 벨 부등식 검증
    correlators: dict[tuple[int, int], list[float]] = field(default_factory=dict)
    bell_S: float = 0.0
    bell_violated: bool = False

    # 통계
    total_rounds: int = 0
    key_rounds: int = 0
    bell_rounds: int = 0
    eve_detected: bool = False
    eve_rounds: int = 0

    # 키 시프팅/PA 단계
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

    # 기저 랜덤 선택
    a_idx = random.randint(0, 2)
    b_idx = random.randint(0, 2)
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

    return S


# ── 키 시프팅 ────────────────────────────────────────


def key_sift(state: E91State) -> list[int]:
    """키 시프팅: 기저 일치 라운드만 추출.

    Alice와 Bob의 원시 키에서 일치하는 비트만 남김.
    """
    if not state.raw_key_alice:
        return []

    sifted = []
    errors = 0
    for a_bit, b_bit in zip(state.raw_key_alice, state.raw_key_bob):
        if a_bit == b_bit:
            sifted.append(a_bit)
        else:
            errors += 1

    state.sifted_key = sifted
    state.sift_done = True

    total = len(state.raw_key_alice)
    state.error_rate = errors / total if total > 0 else 0.0
    state.key_match_rate = len(sifted) / total if total > 0 else 0.0

    return sifted


def privacy_amplification(state: E91State) -> str:
    """프라이버시 증폭: 시프트 키를 해시하여 최종 보안 키 생성.

    Eve가 부분 정보를 가질 수 있으므로, 범용 해시 함수로
    키를 압축하여 Eve의 정보를 제거합니다.
    """
    if not state.sifted_key:
        state.final_key = ""
        state.pa_done = True
        return ""

    # 시프트 키를 바이트열로 변환
    key_bits = "".join(str(b) for b in state.sifted_key)

    # SHA-256 해시로 압축 (프라이버시 증폭)
    h = hashlib.sha256(key_bits.encode()).hexdigest()

    # 압축 비율에 따라 잘라냄
    target_len = max(4, int(len(h) * PA_COMPRESSION_RATIO))
    final = h[:target_len]

    state.final_key = final
    state.pa_done = True

    return final


# ── 다자간 QKD (GHZ 기반) ────────────────────────────


@dataclass
class GHZRound:
    """GHZ 3자간 QKD 1 라운드."""
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
    party_names: list[str] = field(default_factory=lambda: ["Alice", "Bob", "Charlie"])
    rounds: list[GHZRound] = field(default_factory=list)

    # 키
    raw_keys: list[list[int]] = field(default_factory=lambda: [[], [], []])
    sifted_key: list[int] = field(default_factory=list)
    final_key: str = ""

    # 통계
    total_rounds: int = 0
    key_rounds: int = 0
    consistency_checks: int = 0
    consistency_pass: int = 0
    eve_rounds: int = 0
    error_rate: float = 0.0

    # 상태
    sift_done: bool = False
    pa_done: bool = False


def _ghz_measure(bases: list[str], eve_present: bool = False) -> list[int]:
    """GHZ 상태 |000⟩+|111⟩)/√2 측정 시뮬레이션.

    Z 기저: 000 또는 111 (50:50) → 모든 파티 같은 결과
    X 기저: GHZ 상관관계 → 짝수 개의 1 (000, 011, 101, 110)
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

    # 각 파티 기저 랜덤 선택
    bases = [random.choice(["X", "Z"]) for _ in range(state.n_parties)]

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
    """GHZ 프라이버시 증폭."""
    if not state.sifted_key:
        state.final_key = ""
        state.pa_done = True
        return ""

    key_bits = "".join(str(b) for b in state.sifted_key)
    h = hashlib.sha256(key_bits.encode()).hexdigest()
    target_len = max(4, int(len(h) * PA_COMPRESSION_RATIO))
    final = h[:target_len]

    state.final_key = final
    state.pa_done = True
    return final


# ── 리셋 ─────────────────────────────────────────────


def reset_e91(state: E91State):
    """E91 상태 리셋."""
    state.rounds.clear()
    state.raw_key_alice.clear()
    state.raw_key_bob.clear()
    state.sifted_key.clear()
    state.final_key = ""
    state.correlators.clear()
    state.bell_S = 0.0
    state.bell_violated = False
    state.total_rounds = 0
    state.key_rounds = 0
    state.bell_rounds = 0
    state.eve_detected = False
    state.eve_rounds = 0
    state.sift_done = False
    state.pa_done = False
    state.error_rate = 0.0
    state.key_match_rate = 0.0


def reset_ghz(state: GHZState):
    """GHZ 상태 리셋."""
    state.rounds.clear()
    for k in state.raw_keys:
        k.clear()
    state.sifted_key.clear()
    state.final_key = ""
    state.total_rounds = 0
    state.key_rounds = 0
    state.consistency_checks = 0
    state.consistency_pass = 0
    state.eve_rounds = 0
    state.error_rate = 0.0
    state.sift_done = False
    state.pa_done = False
