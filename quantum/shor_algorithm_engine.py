"""Shor's Algorithm 엔진 — 소인수분해 양자 알고리즘 시뮬레이션.

numpy 없이 순수 Python으로 Shor's Algorithm의 전 과정을 시뮬레이션합니다.
  - 고전 전처리: 짝수/소수/GCD 체크
  - 양자 주기 탐색: a^x mod N 의 주기 r 탐색 (QFT 시뮬레이션)
  - 고전 후처리: 연분수 전개 → r 추출 → gcd(a^(r/2) ± 1, N) 인수 도출
  - RSA 위협 데모: 작은 RSA 키를 깨는 과정 + QKD 필요성 연결

사용법:
    from quantum.shor_algorithm_engine import ShorState, shor_step
    state = ShorState(number=15)
    while state.phase != ShorPhase.DONE:
        shor_step(state)
    print(state.factors)  # (3, 5)
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto

from config_loader import cfg
from i18n import t

# ── 설정 ──────────────────────────────────────────────
MAX_NUMBER = cfg("shor", "max_number", 10000)
QFT_PRECISION_BITS = cfg("shor", "qft_precision_bits", 8)
MAX_PERIOD_ATTEMPTS = cfg("shor", "max_period_attempts", 20)
MOD_EXP_ANIMATION_STEPS = cfg("shor", "mod_exp_steps", 32)


# ── 알고리즘 단계 (Phase) ────────────────────────────
class ShorPhase(Enum):
    """Shor's Algorithm 진행 단계."""
    INPUT = auto()               # 1. 입력 대기
    CLASSICAL_PRECHECK = auto()   # 2. 고전 전처리 (짝수/소수/GCD)
    PICK_RANDOM_A = auto()        # 3. 랜덤 a 선택
    MODULAR_EXP = auto()          # 4. 모듈러 지수 테이블 생성
    QFT_SETUP = auto()            # 5. 양자 레지스터 초기화 (Hadamard)
    QFT_MEASURE = auto()          # 6. QFT 측정 시뮬레이션
    CONTINUED_FRACTION = auto()   # 7. 연분수 전개로 주기 r 추출
    EXTRACT_FACTORS = auto()      # 8. gcd(a^(r/2) ± 1, N) 인수 추출
    SUCCESS = auto()              # 9. 소인수분해 성공
    RETRY = auto()                # 10. 실패 → a 재선택
    DONE = auto()                 # 11. 완료 (성공 또는 최대 시도 초과)


# ── 상태 데이터 ──────────────────────────────────────

@dataclass
class QFTResult:
    """QFT 측정 1회 결과."""
    measured_value: int          # 측정된 정수 (0 ~ 2^n - 1)
    n_qubits: int                # 큐빗 수
    phase_estimate: float        # measured_value / 2^n ≈ s/r
    convergents: list[tuple[int, int]]  # 연분수 수렴분수 [(p0,q0), (p1,q1), ...]
    candidate_r: int | None      # 후보 주기 r


@dataclass
class ModExpEntry:
    """모듈러 지수 테이블의 한 행: a^x mod N."""
    x: int
    value: int   # a^x mod N


@dataclass
class RSAThreat:
    """RSA 위협 데모 상태."""
    rsa_n: int = 0               # RSA 공개키 N = p*q
    rsa_e: int = 65537           # 공개 지수 (표준)
    rsa_p: int = 0               # 비밀 소인수 p
    rsa_q: int = 0               # 비밀 소인수 q
    plaintext: int = 0           # 평문
    ciphertext: int = 0          # 암호문
    cracked_p: int = 0           # Shor로 찾은 p
    cracked_q: int = 0           # Shor로 찾은 q
    cracked_d: int = 0           # 복원된 비밀키 d
    decrypted: int = 0           # 복호화된 평문
    cracked: bool = False


@dataclass
class ShorState:
    """Shor's Algorithm 전체 상태."""
    # 입력
    number: int = 15             # 소인수분해할 수 N

    # 현재 단계
    phase: ShorPhase = ShorPhase.INPUT
    step_message: str = ""       # 현재 단계 설명 메시지

    # 고전 전처리 결과
    is_even: bool = False
    is_prime: bool = False
    trivial_factor: int = 0      # gcd(a, N) > 1 인 경우

    # 랜덤 a
    a: int = 0                   # 선택된 랜덤 a (1 < a < N, gcd(a,N)=1)
    attempt: int = 0             # 현재 시도 횟수
    max_attempts: int = MAX_PERIOD_ATTEMPTS

    # 모듈러 지수 테이블 (시각화용)
    mod_exp_table: list[ModExpEntry] = field(default_factory=list)
    mod_exp_period_visual: int = 0  # 테이블에서 관측된 주기 (시각용)

    # QFT 결과
    qft_n_qubits: int = QFT_PRECISION_BITS
    qft_amplitudes: list[float] = field(default_factory=list)  # 확률 분포
    qft_results: list[QFTResult] = field(default_factory=list)
    qft_current: QFTResult | None = None

    # 주기 r
    period: int | None = None

    # 최종 결과
    factors: tuple[int, int] | None = None
    factor_method: str = ""      # "quantum", "trivial_even", "trivial_gcd", "trivial_prime"

    # 히스토리 (모든 시도 기록)
    attempt_history: list[dict] = field(default_factory=list)

    # RSA 위협 데모
    rsa: RSAThreat = field(default_factory=RSAThreat)

    # 통계
    total_qft_measurements: int = 0


# ── 수론 유틸리티 ────────────────────────────────────

def is_prime(n: int) -> bool:
    """밀러-라빈 소수 판정 (결정적, n < 3.3×10^24)."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    # 작은 소수 체크
    small_primes = [5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
    for p in small_primes:
        if n == p:
            return True
        if n % p == 0:
            return False
    # 밀러-라빈
    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1
    # 결정적 증인 (n < 3.3×10^24)
    witnesses = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
    for a in witnesses:
        if a >= n:
            continue
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def is_prime_power(n: int) -> tuple[bool, int, int]:
    """n = p^k 형태인지 확인. (is_power, base, exponent)."""
    if n < 2:
        return False, 0, 0
    for k in range(2, n.bit_length() + 1):
        # k번째 근 계산
        root = round(n ** (1.0 / k))
        for candidate in [root - 1, root, root + 1]:
            if candidate >= 2 and candidate ** k == n:
                return True, candidate, k
    return False, 0, 0


def gcd(a: int, b: int) -> int:
    """최대공약수."""
    while b:
        a, b = b, a % b
    return a


def mod_pow(base: int, exp: int, mod: int) -> int:
    """모듈러 거듭제곱 (빠른 거듭제곱)."""
    return pow(base, exp, mod)


def continued_fraction(numerator: int, denominator: int,
                       max_terms: int = 30) -> list[int]:
    """연분수 전개 — numerator/denominator = [a0; a1, a2, ...].

    Shor's Algorithm에서 QFT 측정값 m / 2^n 을 연분수 전개하여
    s/r 의 근사 분수를 구합니다. r이 주기 후보가 됩니다.
    """
    coefficients = []
    n, d = numerator, denominator
    for _ in range(max_terms):
        if d == 0:
            break
        q = n // d
        coefficients.append(q)
        n, d = d, n - q * d
    return coefficients


def convergents(cf_coefficients: list[int]) -> list[tuple[int, int]]:
    """연분수 계수로부터 수렴분수(convergent) 목록 생성.

    수렴분수 p_k/q_k:
      p_{-1}=1, p_{-2}=0, p_k = a_k * p_{k-1} + p_{k-2}
      q_{-1}=0, q_{-2}=1, q_k = a_k * q_{k-1} + q_{k-2}
    """
    result = []
    p_prev2, p_prev1 = 0, 1
    q_prev2, q_prev1 = 1, 0
    for a_k in cf_coefficients:
        p_k = a_k * p_prev1 + p_prev2
        q_k = a_k * q_prev1 + q_prev2
        result.append((p_k, q_k))
        p_prev2, p_prev1 = p_prev1, p_k
        q_prev2, q_prev1 = q_prev1, q_k
    return result


def find_order(a: int, n: int) -> int | None:
    """a의 n에 대한 위수(order) r 을 직접 계산.

    a^r ≡ 1 (mod n) 인 최소 r.
    교육/검증 목적. 양자 시뮬레이션의 정답 확인에 사용.
    """
    if gcd(a, n) != 1:
        return None
    r = 1
    current = a % n
    while current != 1:
        current = (current * a) % n
        r += 1
        if r > n:
            return None
    return r


# ── 모듈러 지수 테이블 ──────────────────────────────

def build_mod_exp_table(a: int, n: int,
                        length: int = MOD_EXP_ANIMATION_STEPS) -> list[ModExpEntry]:
    """a^x mod N 테이블 생성 (x=0, 1, ..., length-1).

    시각화에서 주기 패턴을 보여주기 위해 사용.
    """
    table = []
    for x in range(length):
        val = mod_pow(a, x, n)
        table.append(ModExpEntry(x=x, value=val))
    return table


def detect_period_from_table(table: list[ModExpEntry]) -> int:
    """모듈러 지수 테이블에서 주기를 직접 탐색 (시각화 보조)."""
    if len(table) < 2:
        return 0
    first_val = table[0].value  # a^0 mod N = 1
    for i in range(1, len(table)):
        if table[i].value == first_val:
            return i
    return 0


# ── QFT 시뮬레이션 ──────────────────────────────────

def simulate_qft_measurement(a: int, n: int,
                             n_qubits: int = QFT_PRECISION_BITS) -> QFTResult:
    """양자 주기 탐색의 QFT 측정 시뮬레이션.

    실제 양자 컴퓨터에서:
      1. |0⟩^n |1⟩ 초기 상태
      2. Hadamard → 균등 중첩
      3. U_f: |x⟩|y⟩ → |x⟩|y ⊕ a^x mod N⟩
      4. QFT on 첫 레지스터
      5. 측정 → m ≈ s * 2^n / r (s는 정수)

    이 함수는 정확한 확률 분포를 계산하고 그에 따라 샘플링합니다.
    """
    Q = 1 << n_qubits  # 2^n

    # 실제 위수 r 계산 (시뮬레이션이므로 허용)
    r = find_order(a, n)
    if r is None or r == 0:
        # 위수를 찾을 수 없으면 랜덤 결과
        m = random.randint(0, Q - 1)
        return QFTResult(
            measured_value=m,
            n_qubits=n_qubits,
            phase_estimate=m / Q,
            convergents=[],
            candidate_r=None,
        )

    # QFT 출력 확률 분포 계산 (정확한 양자 이론)
    # P(m) ∝ |Σ_{j=0}^{L-1} exp(2πi j m / Q)|^2 where L = floor(Q/r)
    # L개 등간격 위상의 합 → 피크 위치 m = s*Q/r 에서 constructive interference
    probs = _compute_qft_probs(Q, r)

    # 정규화
    total = sum(probs)
    if total > 0:
        probs = [p / total for p in probs]

    # 확률에 따라 측정값 샘플링
    m = _sample_from_distribution(probs)

    # 연분수 전개
    phase = m / Q
    cf = continued_fraction(m, Q)
    convs = convergents(cf)

    # 후보 주기 추출: 수렴분수의 분모 중 조건 만족하는 것
    candidate_r = None
    for _p, q in convs:
        if 0 < q <= n and mod_pow(a, q, n) == 1:
            candidate_r = q
            break

    return QFTResult(
        measured_value=m,
        n_qubits=n_qubits,
        phase_estimate=phase,
        convergents=convs,
        candidate_r=candidate_r,
    )


def compute_qft_probability_distribution(a: int, n: int,
                                         n_qubits: int = QFT_PRECISION_BITS) -> list[float]:
    """QFT 출력의 확률 분포 계산 (히스토그램 시각화용).

    피크 위치에서의 확률이 높아지는 간섭 패턴을 보여줍니다.
    """
    Q = 1 << n_qubits
    r = find_order(a, n)

    if r is None or r == 0:
        return [1.0 / Q] * Q  # 균등 분포

    return _compute_qft_probs(Q, r)


def _compute_qft_probs(Q: int, r: int) -> list[float]:
    """QFT 확률 분포 계산 (정확한 양자 간섭).

    양자 위상 추정에서 측정 확률:
    P(m) = (1/Q^2) * |Σ_{x=0}^{Q-1} exp(2πi x (m/Q - s/r))|^2
         = (1/Q^2) * sin^2(πQ(m/Q - s/r)) / sin^2(π(m/Q - s/r))

    피크는 m = round(s*Q/r) 에서 P ≈ 1/r 로 발생.
    """
    probs = [0.0] * Q
    for m in range(Q):
        for s in range(r):
            # 위상 차이: m/Q - s/r
            delta = m / Q - s / r
            # 주기적 sinc 함수
            if abs(delta - round(delta)) < 1e-12:
                p = 1.0  # 정확한 피크
            else:
                arg_num = math.pi * Q * delta
                arg_den = math.pi * delta
                sin_num = math.sin(arg_num)
                sin_den = math.sin(arg_den)
                if abs(sin_den) < 1e-15:
                    p = 1.0
                else:
                    p = (sin_num / (Q * sin_den)) ** 2
            probs[m] += p

    # 정규화
    total = sum(probs)
    if total > 0:
        probs = [p / total for p in probs]
    return probs


def _sample_from_distribution(probs: list[float]) -> int:
    """확률 분포에서 샘플링."""
    r = random.random()
    cumulative = 0.0
    for i, p in enumerate(probs):
        cumulative += p
        if r <= cumulative:
            return i
    return len(probs) - 1


# ── 단계별 실행 ──────────────────────────────────────

def shor_step(state: ShorState) -> ShorPhase:
    """Shor's Algorithm 한 단계 진행.

    UI에서 매 프레임/키 입력마다 호출하여 단계별 진행합니다.
    Returns: 현재 phase.
    """
    if state.phase == ShorPhase.INPUT:
        _step_input(state)
    elif state.phase == ShorPhase.CLASSICAL_PRECHECK:
        _step_classical_precheck(state)
    elif state.phase == ShorPhase.PICK_RANDOM_A:
        _step_pick_random_a(state)
    elif state.phase == ShorPhase.MODULAR_EXP:
        _step_modular_exp(state)
    elif state.phase == ShorPhase.QFT_SETUP:
        _step_qft_setup(state)
    elif state.phase == ShorPhase.QFT_MEASURE:
        _step_qft_measure(state)
    elif state.phase == ShorPhase.CONTINUED_FRACTION:
        _step_continued_fraction(state)
    elif state.phase == ShorPhase.EXTRACT_FACTORS:
        _step_extract_factors(state)
    elif state.phase == ShorPhase.RETRY:
        _step_retry(state)
    # SUCCESS, DONE → 아무 동작 안 함
    return state.phase


def shor_run_full(n: int) -> ShorState:
    """Shor's Algorithm 전체 실행 (자동 모드).

    모든 단계를 한번에 실행하고 최종 상태를 반환합니다.
    """
    state = ShorState(number=n)
    max_iterations = 200
    for _ in range(max_iterations):
        shor_step(state)
        if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
            break
    if state.phase == ShorPhase.SUCCESS:
        state.phase = ShorPhase.DONE
    return state


def reset_state(state: ShorState, new_number: int | None = None):
    """상태를 초기화합니다."""
    n = new_number if new_number is not None else state.number
    state.number = n
    state.phase = ShorPhase.INPUT
    state.step_message = ""
    state.is_even = False
    state.is_prime = False
    state.trivial_factor = 0
    state.a = 0
    state.attempt = 0
    state.mod_exp_table.clear()
    state.mod_exp_period_visual = 0
    state.qft_amplitudes.clear()
    state.qft_results.clear()
    state.qft_current = None
    state.period = None
    state.factors = None
    state.factor_method = ""
    state.attempt_history.clear()
    state.total_qft_measurements = 0


# ── 각 단계 구현 ─────────────────────────────────────

def _step_input(state: ShorState):
    """Step 1: 입력 검증 → 고전 전처리로 전환."""
    n = state.number
    if n < 2:
        state.step_message = t("shor_msg_n_too_small")
        state.phase = ShorPhase.DONE
        return
    if n > MAX_NUMBER:
        state.step_message = t("shor_msg_n_too_large", max=MAX_NUMBER)
        state.phase = ShorPhase.DONE
        return
    state.step_message = t("shor_msg_factoring", n=n)
    state.phase = ShorPhase.CLASSICAL_PRECHECK


def _step_classical_precheck(state: ShorState):
    """Step 2: 고전 전처리.

    양자 알고리즘 전에 고전적으로 처리 가능한 경우를 걸러냅니다:
    - 짝수: N/2로 바로 분해
    - 소수: 소인수분해 불가
    - 소수의 거듭제곱: p^k 형태
    """
    n = state.number

    # 짝수 체크
    if n % 2 == 0:
        state.is_even = True
        state.factors = (2, n // 2)
        state.factor_method = "trivial_even"
        state.step_message = t("shor_msg_even", n=n, half=n // 2)
        state.phase = ShorPhase.SUCCESS
        return

    # 소수 체크
    if is_prime(n):
        state.is_prime = True
        state.step_message = t("shor_msg_prime", n=n)
        state.phase = ShorPhase.DONE
        return

    # 소수 거듭제곱 체크
    is_pp, base, exp = is_prime_power(n)
    if is_pp:
        state.factors = (base, n // base)
        state.factor_method = "trivial_prime_power"
        state.step_message = t("shor_msg_prime_power", n=n, base=base,
                                exp=exp, other=n // base)
        state.phase = ShorPhase.SUCCESS
        return

    state.step_message = t("shor_msg_passed_classical", n=n)
    state.phase = ShorPhase.PICK_RANDOM_A


def _step_pick_random_a(state: ShorState):
    """Step 3: 랜덤 a 선택 (1 < a < N, gcd(a,N) = 1)."""
    n = state.number
    state.attempt += 1

    if state.attempt > state.max_attempts:
        state.step_message = t("shor_msg_max_attempts", max=state.max_attempts)
        state.phase = ShorPhase.DONE
        return

    a = random.randint(2, n - 1)
    g = gcd(a, n)

    if g > 1:
        # 우연히 공통인수 발견
        state.a = a
        state.trivial_factor = g
        state.factors = (g, n // g)
        state.factor_method = "trivial_gcd"
        state.step_message = t("shor_msg_lucky_gcd", a=a, n=n, g=g,
                                other=n // g)
        state.phase = ShorPhase.SUCCESS
        return

    state.a = a
    state.step_message = t("shor_msg_pick_a", attempt=state.attempt, a=a, n=n)
    state.phase = ShorPhase.MODULAR_EXP


def _step_modular_exp(state: ShorState):
    """Step 4: 모듈러 지수 테이블 생성.

    a^x mod N 의 값을 계산하여 주기 패턴을 시각적으로 보여줍니다.
    """
    table_len = min(MOD_EXP_ANIMATION_STEPS, state.number * 2)
    state.mod_exp_table = build_mod_exp_table(state.a, state.number, table_len)
    state.mod_exp_period_visual = detect_period_from_table(state.mod_exp_table)

    if state.mod_exp_period_visual > 0:
        state.step_message = t("shor_msg_mod_exp_period",
                                r=state.mod_exp_period_visual)
    else:
        state.step_message = t("shor_msg_mod_exp_done", n=state.number,
                                len=table_len)

    state.phase = ShorPhase.QFT_SETUP


def _step_qft_setup(state: ShorState):
    """Step 5: 양자 레지스터 초기화 + QFT 확률 분포 계산."""
    # 큐빗 수 결정: 2*ceil(log2(N)) 이상
    min_qubits = max(4, 2 * math.ceil(math.log2(state.number)))
    state.qft_n_qubits = min(min_qubits, 12)  # 시뮬레이션 한계

    # QFT 확률 분포 계산 (시각화용)
    state.qft_amplitudes = compute_qft_probability_distribution(
        state.a, state.number, state.qft_n_qubits
    )

    state.step_message = t("shor_msg_qft_setup", qubits=state.qft_n_qubits)
    state.phase = ShorPhase.QFT_MEASURE


def _step_qft_measure(state: ShorState):
    """Step 6: QFT 측정 시뮬레이션."""
    result = simulate_qft_measurement(
        state.a, state.number, state.qft_n_qubits
    )
    state.qft_current = result
    state.qft_results.append(result)
    state.total_qft_measurements += 1

    Q = 1 << state.qft_n_qubits
    state.step_message = t("shor_msg_qft_measure", m=result.measured_value,
                            Q=Q, phase=f"{result.phase_estimate:.4f}")
    state.phase = ShorPhase.CONTINUED_FRACTION


def _step_continued_fraction(state: ShorState):
    """Step 7: 연분수 전개로 주기 r 추출.

    측정값 m/Q ≈ s/r 이므로, 연분수 전개의 수렴분수 분모가
    주기 r의 후보가 됩니다.
    """
    result = state.qft_current
    if result is None:
        state.phase = ShorPhase.RETRY
        return

    Q = 1 << result.n_qubits
    cf = continued_fraction(result.measured_value, Q)
    convs = convergents(cf)

    # 결과 갱신
    result.convergents = convs

    # 후보 r 탐색: 분모 q가 0 < q < N 이고 a^q ≡ 1 (mod N) 인 것
    candidate_r = None
    for _p, q in convs:
        if 0 < q < state.number and mod_pow(state.a, q, state.number) == 1:
            candidate_r = q
            break

    result.candidate_r = candidate_r

    if candidate_r is not None:
        state.period = candidate_r
        state.step_message = t("shor_msg_cf_found", r=candidate_r,
                                check=mod_pow(state.a, candidate_r, state.number))
        state.phase = ShorPhase.EXTRACT_FACTORS
    else:
        cf_str = "[" + "; ".join(str(c) for c in cf[:6]) + "...]"
        state.step_message = t("shor_msg_cf_failed", cf=cf_str)
        state.phase = ShorPhase.RETRY


def _step_extract_factors(state: ShorState):
    """Step 8: 인수 추출.

    주기 r을 찾았으면:
    - r이 짝수인지 확인
    - gcd(a^(r/2) + 1, N) 과 gcd(a^(r/2) - 1, N) 계산
    - 둘 다 자명하지 않으면 인수!
    """
    r = state.period
    n = state.number
    a = state.a

    if r is None or r == 0:
        state.step_message = t("shor_msg_no_period")
        state.phase = ShorPhase.RETRY
        return

    # r이 홀수이면 실패
    if r % 2 != 0:
        state.step_message = t("shor_msg_r_odd", r=r)
        state.attempt_history.append({
            "attempt": state.attempt, "a": a, "r": r,
            "reason": "r is odd",
        })
        state.phase = ShorPhase.RETRY
        return

    half_r = r // 2
    a_half = mod_pow(a, half_r, n)

    # a^(r/2) ≡ -1 (mod N) 이면 실패
    if a_half == n - 1:
        state.step_message = t("shor_msg_r_minus_one")
        state.attempt_history.append({
            "attempt": state.attempt, "a": a, "r": r,
            "reason": "a^(r/2) ≡ -1",
        })
        state.phase = ShorPhase.RETRY
        return

    factor1 = gcd(a_half + 1, n)
    factor2 = gcd(a_half - 1, n)

    # 자명하지 않은 인수 찾기
    f = 0
    if 1 < factor1 < n:
        f = factor1
    elif 1 < factor2 < n:
        f = factor2

    if f > 0:
        other = n // f
        state.factors = (min(f, other), max(f, other))
        state.factor_method = "quantum"
        state.step_message = t("shor_msg_factors_found", n=n,
                                p=state.factors[0], q=state.factors[1])
        state.attempt_history.append({
            "attempt": state.attempt, "a": a, "r": r,
            "reason": "success",
            "factors": state.factors,
        })
        state.phase = ShorPhase.SUCCESS
    else:
        state.step_message = t("shor_msg_trivial_factors",
                                f1=a_half + 1, n=n, g1=factor1,
                                f2=a_half - 1, g2=factor2)
        state.attempt_history.append({
            "attempt": state.attempt, "a": a, "r": r,
            "reason": "trivial factors",
        })
        state.phase = ShorPhase.RETRY


def _step_retry(state: ShorState):
    """Step 10: 실패 시 새로운 a로 재시도."""
    state.period = None
    state.qft_current = None
    state.mod_exp_table.clear()
    state.mod_exp_period_visual = 0
    state.qft_amplitudes.clear()

    if state.attempt >= state.max_attempts:
        state.step_message = t("shor_msg_exhausted", max=state.max_attempts)
        state.phase = ShorPhase.DONE
    else:
        state.step_message = t("shor_msg_retry", next=state.attempt + 1)
        state.phase = ShorPhase.PICK_RANDOM_A


# ── RSA 위협 데모 ────────────────────────────────────

# 교육용 작은 RSA 예제 목록 (p, q)
RSA_EXAMPLES = [
    (3, 5),       # N = 15
    (3, 7),       # N = 21
    (5, 7),       # N = 35
    (7, 11),      # N = 77
    (11, 13),     # N = 143
    (13, 17),     # N = 221
    (17, 19),     # N = 323
    (23, 29),     # N = 667
    (29, 31),     # N = 899
    (31, 37),     # N = 1147
]


def _mod_inverse(e: int, phi: int) -> int | None:
    """확장 유클리드 알고리즘으로 모듈러 역원 계산.

    e * d ≡ 1 (mod phi) 인 d를 반환.
    """
    g, x, _ = _extended_gcd(e, phi)
    if g != 1:
        return None
    return x % phi


def _extended_gcd(a: int, b: int) -> tuple[int, int, int]:
    """확장 유클리드: gcd, x, y (ax + by = gcd)."""
    if a == 0:
        return b, 0, 1
    g, x, y = _extended_gcd(b % a, a)
    return g, y - (b // a) * x, x


def setup_rsa_demo(state: ShorState, difficulty: int = 0):
    """RSA 위협 데모 초기화.

    difficulty: 0=쉬움(15), 1=보통(77), 2=어려움(323), ...
    """
    idx = min(difficulty, len(RSA_EXAMPLES) - 1)
    p, q = RSA_EXAMPLES[idx]
    n = p * q
    phi = (p - 1) * (q - 1)
    e = 65537

    # e와 phi가 서로소가 아니면 e 조정
    if gcd(e, phi) != 1:
        for candidate_e in [3, 5, 7, 11, 13, 17, 19, 23, 257]:
            if gcd(candidate_e, phi) == 1:
                e = candidate_e
                break

    d = _mod_inverse(e, phi)
    if d is None:
        e = 3
        d = _mod_inverse(e, phi)

    # 평문 (작은 수)
    plaintext = random.randint(2, min(n - 1, 100))
    ciphertext = mod_pow(plaintext, e, n)

    state.rsa = RSAThreat(
        rsa_n=n,
        rsa_e=e,
        rsa_p=p,
        rsa_q=q,
        plaintext=plaintext,
        ciphertext=ciphertext,
    )

    # Shor로 N 소인수분해
    state.number = n
    reset_state(state, n)


def crack_rsa(state: ShorState) -> bool:
    """Shor's Algorithm으로 RSA 키 크래킹.

    1. N 소인수분해 (Shor)
    2. φ(N) = (p-1)(q-1) 계산
    3. d = e^(-1) mod φ(N) (비밀키 복원)
    4. plaintext = ciphertext^d mod N (복호화)
    """
    # Shor 실행
    shor_state = shor_run_full(state.rsa.rsa_n)

    if shor_state.factors is None:
        return False

    p, q = shor_state.factors
    state.rsa.cracked_p = p
    state.rsa.cracked_q = q

    # φ(N) 계산 및 비밀키 복원
    phi = (p - 1) * (q - 1)
    d = _mod_inverse(state.rsa.rsa_e, phi)
    if d is None:
        return False

    state.rsa.cracked_d = d

    # 복호화
    decrypted = mod_pow(state.rsa.ciphertext, d, state.rsa.rsa_n)
    state.rsa.decrypted = decrypted
    state.rsa.cracked = True

    # Shor 결과를 메인 상태에 복사
    state.factors = shor_state.factors
    state.factor_method = shor_state.factor_method
    state.attempt = shor_state.attempt
    state.attempt_history = shor_state.attempt_history

    return True


def finalize_rsa_crack(state: ShorState) -> bool:
    """Shor 소인수분해 완료 후 RSA 비밀키 복원 및 복호화.

    crack_rsa()의 후처리 부분만 분리한 함수.
    단계별 RSA 크래킹에서 소인수분해 성공(SUCCESS) 후 호출합니다.
    """
    if state.factors is None:
        return False

    p, q = state.factors
    state.rsa.cracked_p = p
    state.rsa.cracked_q = q

    phi = (p - 1) * (q - 1)
    d = _mod_inverse(state.rsa.rsa_e, phi)
    if d is None:
        return False

    state.rsa.cracked_d = d
    decrypted = mod_pow(state.rsa.ciphertext, d, state.rsa.rsa_n)
    state.rsa.decrypted = decrypted
    state.rsa.cracked = True
    return True


# ── 교육 메시지 ──────────────────────────────────────

_PHASE_DESC_KEYS = {
    ShorPhase.INPUT: "shor_desc_input",
    ShorPhase.CLASSICAL_PRECHECK: "shor_desc_classical",
    ShorPhase.PICK_RANDOM_A: "shor_desc_pick_a",
    ShorPhase.MODULAR_EXP: "shor_desc_mod_exp",
    ShorPhase.QFT_SETUP: "shor_desc_qft_setup",
    ShorPhase.QFT_MEASURE: "shor_desc_qft_measure",
    ShorPhase.CONTINUED_FRACTION: "shor_desc_cf",
    ShorPhase.EXTRACT_FACTORS: "shor_desc_extract",
    ShorPhase.SUCCESS: "shor_desc_success",
    ShorPhase.RETRY: "shor_desc_retry",
    ShorPhase.DONE: "shor_desc_done",
}


def get_phase_description(phase: ShorPhase) -> str:
    """현재 단계의 다국어 설명을 반환합니다."""
    key = _PHASE_DESC_KEYS.get(phase, "shor_desc_done")
    return t(key)


# 하위 호환: 기존 코드에서 dict처럼 접근할 수 있도록
class _PhaseDescProxy:
    """Dict-like proxy that returns i18n strings on access."""

    def get(self, phase, default=""):
        return get_phase_description(phase) if phase in _PHASE_DESC_KEYS else default

    def __getitem__(self, phase):
        return get_phase_description(phase)

    def __contains__(self, phase):
        return phase in _PHASE_DESC_KEYS


PHASE_DESCRIPTIONS = _PhaseDescProxy()


def get_qkd_motivation() -> str:
    """QKD 동기부여 메시지를 다국어로 반환합니다."""
    return t("shor_qkd_motivation")


# 하위 호환: 기존 문자열 상수처럼 사용 가능하도록 lazy 프로퍼티
QKD_MOTIVATION_MESSAGE = property(lambda self: get_qkd_motivation())


class _QKDMotivationStr:
    """Lazy string proxy that resolves to the current locale on access."""

    def __str__(self):
        return get_qkd_motivation()

    def __repr__(self):
        return get_qkd_motivation()

    def __contains__(self, item):
        return item in str(self)

    def __len__(self):
        return len(str(self))

    def __getattr__(self, name):
        return getattr(str(self), name)


QKD_MOTIVATION_MESSAGE = _QKDMotivationStr()
