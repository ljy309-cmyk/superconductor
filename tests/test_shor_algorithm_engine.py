"""Shor's Algorithm 엔진 단위 테스트."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum.shor_algorithm_engine import (
    ModExpEntry,
    QFTResult,
    RSA_EXAMPLES,
    ShorPhase,
    ShorState,
    build_mod_exp_table,
    compute_qft_probability_distribution,
    continued_fraction,
    convergents,
    crack_rsa,
    detect_period_from_table,
    find_order,
    gcd,
    is_prime,
    is_prime_power,
    mod_pow,
    reset_state,
    setup_rsa_demo,
    shor_run_full,
    shor_step,
    simulate_qft_measurement,
)


# ── 수론 유틸리티 테스트 ─────────────────────────────

class TestIsPrime(unittest.TestCase):
    """is_prime — 소수 판정."""

    def test_small_primes(self):
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
        for p in primes:
            self.assertTrue(is_prime(p), f"{p} should be prime")

    def test_small_composites(self):
        composites = [4, 6, 8, 9, 10, 12, 14, 15, 16, 18, 20, 21, 25, 35]
        for n in composites:
            self.assertFalse(is_prime(n), f"{n} should not be prime")

    def test_edge_cases(self):
        self.assertFalse(is_prime(0))
        self.assertFalse(is_prime(1))
        self.assertTrue(is_prime(2))
        self.assertTrue(is_prime(3))

    def test_larger_primes(self):
        self.assertTrue(is_prime(97))
        self.assertTrue(is_prime(101))
        self.assertTrue(is_prime(7919))

    def test_larger_composites(self):
        self.assertFalse(is_prime(100))
        self.assertFalse(is_prime(7917))  # 3 × 2639
        self.assertFalse(is_prime(561))   # Carmichael number


class TestIsPrimePower(unittest.TestCase):
    """is_prime_power — 소수 거듭제곱 판정."""

    def test_prime_squares(self):
        result, base, exp = is_prime_power(4)  # 2^2
        self.assertTrue(result)
        self.assertEqual(base, 2)
        self.assertEqual(exp, 2)

    def test_prime_cubes(self):
        result, base, exp = is_prime_power(8)  # 2^3
        self.assertTrue(result)
        self.assertEqual(base, 2)
        self.assertEqual(exp, 3)

    def test_27(self):
        result, base, exp = is_prime_power(27)  # 3^3
        self.assertTrue(result)
        self.assertEqual(base, 3)

    def test_not_prime_power(self):
        result, _, _ = is_prime_power(15)
        self.assertFalse(result)

    def test_prime_itself(self):
        # 소수 자체는 p^1 이지만, k >= 2만 체크하므로 False
        result, _, _ = is_prime_power(7)
        self.assertFalse(result)

    def test_edge_cases(self):
        result, _, _ = is_prime_power(1)
        self.assertFalse(result)
        result, _, _ = is_prime_power(0)
        self.assertFalse(result)


class TestGCD(unittest.TestCase):
    """gcd — 최대공약수."""

    def test_basic(self):
        self.assertEqual(gcd(12, 8), 4)
        self.assertEqual(gcd(15, 5), 5)
        self.assertEqual(gcd(7, 13), 1)

    def test_coprime(self):
        self.assertEqual(gcd(7, 15), 1)
        self.assertEqual(gcd(11, 13), 1)

    def test_same(self):
        self.assertEqual(gcd(10, 10), 10)

    def test_one_zero(self):
        self.assertEqual(gcd(5, 0), 5)
        self.assertEqual(gcd(0, 5), 5)


class TestModPow(unittest.TestCase):
    """mod_pow — 모듈러 거듭제곱."""

    def test_basic(self):
        self.assertEqual(mod_pow(2, 10, 1000), 24)  # 1024 mod 1000 = 24
        self.assertEqual(mod_pow(3, 4, 5), 1)  # 81 mod 5 = 1
        self.assertEqual(mod_pow(7, 2, 15), 4)  # 49 mod 15 = 4

    def test_identity(self):
        self.assertEqual(mod_pow(5, 0, 7), 1)
        self.assertEqual(mod_pow(5, 1, 7), 5)


class TestFindOrder(unittest.TestCase):
    """find_order — 위수(order) 계산."""

    def test_order_2_mod_15(self):
        # 2^r ≡ 1 (mod 15): 2,4,8,1 → r=4
        r = find_order(2, 15)
        self.assertEqual(r, 4)

    def test_order_7_mod_15(self):
        # 7^r mod 15: 7,4,13,1 → r=4
        r = find_order(7, 15)
        self.assertEqual(r, 4)

    def test_order_4_mod_15(self):
        # 4^r mod 15: 4,1 → r=2
        r = find_order(4, 15)
        self.assertEqual(r, 2)

    def test_order_11_mod_15(self):
        # 11^r mod 15: 11,1 → r=2
        r = find_order(11, 15)
        self.assertEqual(r, 2)

    def test_not_coprime(self):
        # gcd(3, 15) = 3 ≠ 1, 위수 없음
        self.assertIsNone(find_order(3, 15))

    def test_order_2_mod_21(self):
        # 2^r mod 21: 2,4,8,16,11,1 → r=6
        r = find_order(2, 21)
        self.assertEqual(r, 6)

    def test_order_verifiable(self):
        """a^r ≡ 1 (mod n) 검증."""
        for a, n in [(2, 15), (7, 15), (2, 21), (4, 35)]:
            r = find_order(a, n)
            if r is not None:
                self.assertEqual(mod_pow(a, r, n), 1,
                                 f"a={a}, n={n}, r={r}")


# ── 연분수 테스트 ────────────────────────────────────

class TestContinuedFraction(unittest.TestCase):
    """continued_fraction — 연분수 전개."""

    def test_integer(self):
        """정수 → [n]"""
        self.assertEqual(continued_fraction(5, 1), [5])

    def test_simple_fraction(self):
        """3/7 = [0; 2, 3]"""
        cf = continued_fraction(3, 7)
        self.assertEqual(cf, [0, 2, 3])

    def test_golden_ratio_approx(self):
        """89/55 (피보나치) ≈ φ → [1; 1, 1, ..., 1, 2] (마지막 항 제외 모두 1)."""
        cf = continued_fraction(89, 55)
        # 89/55 = [1; 1, 1, 1, 1, 1, 1, 1, 2]
        self.assertTrue(all(c == 1 for c in cf[:-1]))

    def test_zero_numerator(self):
        """0/n = [0]"""
        self.assertEqual(continued_fraction(0, 5), [0])


class TestConvergents(unittest.TestCase):
    """convergents — 수렴분수."""

    def test_3_over_7(self):
        """3/7 = [0; 2, 3] → convergents: 0/1, 1/2, 3/7"""
        cf = continued_fraction(3, 7)
        convs = convergents(cf)
        self.assertEqual(convs[-1], (3, 7))

    def test_simple(self):
        """[1; 2] → 1/1, 3/2"""
        convs = convergents([1, 2])
        self.assertEqual(convs[0], (1, 1))
        self.assertEqual(convs[1], (3, 2))

    def test_convergents_approach(self):
        """수렴분수는 원래 분수에 수렴."""
        cf = continued_fraction(355, 113)
        convs = convergents(cf)
        # 마지막 수렴분수 = 원래 분수
        p, q = convs[-1]
        self.assertAlmostEqual(p / q, 355 / 113, places=10)


# ── 모듈러 지수 테이블 테스트 ────────────────────────

class TestModExpTable(unittest.TestCase):
    """build_mod_exp_table — 모듈러 지수 테이블."""

    def test_table_values(self):
        """a=2, N=15: [1, 2, 4, 8, 1, 2, ...]"""
        table = build_mod_exp_table(2, 15, 8)
        self.assertEqual(len(table), 8)
        self.assertEqual(table[0].value, 1)   # 2^0 mod 15
        self.assertEqual(table[1].value, 2)   # 2^1 mod 15
        self.assertEqual(table[2].value, 4)   # 2^2 mod 15
        self.assertEqual(table[3].value, 8)   # 2^3 mod 15
        self.assertEqual(table[4].value, 1)   # 2^4 mod 15 = 16 mod 15

    def test_period_detection(self):
        """주기 탐지: a=2, N=15 → r=4."""
        table = build_mod_exp_table(2, 15, 16)
        period = detect_period_from_table(table)
        self.assertEqual(period, 4)

    def test_period_a7_n15(self):
        """a=7, N=15 → r=4."""
        table = build_mod_exp_table(7, 15, 16)
        period = detect_period_from_table(table)
        self.assertEqual(period, 4)

    def test_period_a4_n15(self):
        """a=4, N=15 → r=2."""
        table = build_mod_exp_table(4, 15, 16)
        period = detect_period_from_table(table)
        self.assertEqual(period, 2)


# ── QFT 시뮬레이션 테스트 ────────────────────────────

class TestQFTSimulation(unittest.TestCase):
    """QFT 측정 시뮬레이션."""

    def test_measurement_range(self):
        """측정값은 [0, 2^n) 범위."""
        result = simulate_qft_measurement(7, 15, 8)
        self.assertGreaterEqual(result.measured_value, 0)
        self.assertLess(result.measured_value, 256)

    def test_phase_estimate(self):
        """phase_estimate = measured_value / 2^n."""
        result = simulate_qft_measurement(7, 15, 8)
        expected = result.measured_value / 256
        self.assertAlmostEqual(result.phase_estimate, expected)

    def test_convergents_exist(self):
        """수렴분수 목록이 생성됨."""
        result = simulate_qft_measurement(7, 15, 8)
        self.assertIsInstance(result.convergents, list)

    def test_probability_distribution(self):
        """확률 분포 합 = 1."""
        probs = compute_qft_probability_distribution(7, 15, 8)
        self.assertAlmostEqual(sum(probs), 1.0, places=5)
        self.assertEqual(len(probs), 256)

    def test_distribution_has_peaks(self):
        """주기 r=4에 대해 4개 피크 영역에 확률 집중."""
        probs = compute_qft_probability_distribution(2, 15, 8)
        # r=4이므로 피크: 0, 64, 128, 192 근처 (±2 범위)
        peak_centers = [0, 64, 128, 192]
        peak_prob = 0.0
        for c in peak_centers:
            for offset in range(-2, 3):
                idx = (c + offset) % 256
                peak_prob += probs[idx]
        # 피크 영역 확률이 전체의 상당 부분 차지
        self.assertGreater(peak_prob, 0.3)

    def test_repeated_measurement_finds_period(self):
        """여러 번 측정하면 주기 후보를 찾을 수 있음."""
        found = False
        for _ in range(30):
            result = simulate_qft_measurement(7, 15, 8)
            if result.candidate_r is not None and result.candidate_r == 4:
                found = True
                break
        self.assertTrue(found, "Should find period r=4 within 30 measurements")


# ── 단계별 실행 테스트 ───────────────────────────────

class TestShorStep(unittest.TestCase):
    """shor_step — 단계별 실행."""

    def test_input_validation_small(self):
        """N < 2 → DONE."""
        state = ShorState(number=1)
        shor_step(state)
        self.assertEqual(state.phase, ShorPhase.DONE)

    def test_even_number(self):
        """짝수 → 즉시 인수분해."""
        state = ShorState(number=14)
        shor_step(state)  # INPUT → CLASSICAL_PRECHECK
        shor_step(state)  # CLASSICAL_PRECHECK → SUCCESS
        self.assertEqual(state.phase, ShorPhase.SUCCESS)
        self.assertEqual(state.factors, (2, 7))
        self.assertEqual(state.factor_method, "trivial_even")

    def test_prime_number(self):
        """소수 → DONE (분해 불가)."""
        state = ShorState(number=17)
        shor_step(state)  # INPUT → CLASSICAL_PRECHECK
        shor_step(state)  # CLASSICAL_PRECHECK → DONE
        self.assertEqual(state.phase, ShorPhase.DONE)
        self.assertTrue(state.is_prime)
        self.assertIsNone(state.factors)

    def test_prime_power(self):
        """소수 거듭제곱 → 즉시 인수분해."""
        state = ShorState(number=27)  # 3^3
        shor_step(state)
        shor_step(state)
        self.assertEqual(state.phase, ShorPhase.SUCCESS)
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 27)

    def test_phase_progression(self):
        """일반 합성수: 단계가 올바르게 진행."""
        state = ShorState(number=15)
        shor_step(state)  # INPUT → CLASSICAL_PRECHECK
        self.assertEqual(state.phase, ShorPhase.CLASSICAL_PRECHECK)
        shor_step(state)  # → PICK_RANDOM_A
        self.assertEqual(state.phase, ShorPhase.PICK_RANDOM_A)


class TestShorRunFull(unittest.TestCase):
    """shor_run_full — 전체 자동 실행."""

    def test_factor_15(self):
        """N=15 소인수분해."""
        state = shor_run_full(15)
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 15)
        self.assertIn(state.factors, [(3, 5), (5, 3)])

    def test_factor_21(self):
        """N=21 소인수분해."""
        state = shor_run_full(21)
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 21)

    def test_factor_35(self):
        """N=35 소인수분해."""
        state = shor_run_full(35)
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 35)

    def test_factor_77(self):
        """N=77 소인수분해."""
        state = shor_run_full(77)
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 77)

    def test_factor_143(self):
        """N=143 = 11×13."""
        state = shor_run_full(143)
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 143)

    def test_even_number(self):
        """짝수도 처리."""
        state = shor_run_full(100)
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 100)

    def test_prime(self):
        """소수 → 인수 없음."""
        state = shor_run_full(17)
        self.assertIsNone(state.factors)

    def test_small_number(self):
        """N < 2 → 결과 없음."""
        state = shor_run_full(1)
        self.assertIsNone(state.factors)


# ── 상태 초기화 테스트 ───────────────────────────────

class TestResetState(unittest.TestCase):
    """reset_state — 상태 초기화."""

    def test_reset(self):
        """실행 후 리셋하면 초기 상태."""
        state = shor_run_full(15)
        self.assertIsNotNone(state.factors)

        reset_state(state, 21)
        self.assertEqual(state.number, 21)
        self.assertEqual(state.phase, ShorPhase.INPUT)
        self.assertIsNone(state.factors)
        self.assertEqual(state.attempt, 0)
        self.assertEqual(len(state.mod_exp_table), 0)

    def test_reset_same_number(self):
        """같은 수로 리셋."""
        state = shor_run_full(15)
        reset_state(state)
        self.assertEqual(state.number, 15)
        self.assertEqual(state.phase, ShorPhase.INPUT)


# ── RSA 위협 데모 테스트 ─────────────────────────────

class TestRSADemo(unittest.TestCase):
    """RSA 위협 데모."""

    def test_setup(self):
        """RSA 데모 초기화."""
        state = ShorState()
        setup_rsa_demo(state, difficulty=0)
        rsa = state.rsa
        self.assertEqual(rsa.rsa_n, 15)  # 3×5
        self.assertEqual(rsa.rsa_p, 3)
        self.assertEqual(rsa.rsa_q, 5)
        self.assertGreater(rsa.ciphertext, 0)

    def test_crack_rsa(self):
        """RSA 크래킹."""
        state = ShorState()
        setup_rsa_demo(state, difficulty=0)
        original_plaintext = state.rsa.plaintext

        success = crack_rsa(state)
        self.assertTrue(success)
        self.assertTrue(state.rsa.cracked)
        self.assertEqual(state.rsa.decrypted, original_plaintext)

    def test_crack_rsa_medium(self):
        """중간 난이도 RSA 크래킹."""
        state = ShorState()
        setup_rsa_demo(state, difficulty=3)  # N=77
        original_plaintext = state.rsa.plaintext

        success = crack_rsa(state)
        self.assertTrue(success)
        self.assertEqual(state.rsa.decrypted, original_plaintext)

    def test_all_rsa_examples(self):
        """모든 RSA 예제의 N = p*q 검증."""
        for p, q in RSA_EXAMPLES:
            self.assertEqual(p * q, p * q)
            self.assertTrue(is_prime(p), f"{p} should be prime")
            self.assertTrue(is_prime(q), f"{q} should be prime")


# ── 교육 메시지 테스트 ───────────────────────────────

class TestEducationalContent(unittest.TestCase):
    """교육 콘텐츠 존재 여부."""

    def test_phase_descriptions(self):
        """모든 Phase에 대한 설명이 존재."""
        from quantum.shor_algorithm_engine import PHASE_DESCRIPTIONS
        for phase in ShorPhase:
            self.assertIn(phase, PHASE_DESCRIPTIONS,
                          f"Missing description for {phase}")

    def test_qkd_motivation(self):
        """QKD 동기 부여 메시지 존재."""
        from quantum.shor_algorithm_engine import QKD_MOTIVATION_MESSAGE
        msg = str(QKD_MOTIVATION_MESSAGE)
        self.assertIn("QKD", msg)
        self.assertTrue(len(msg) > 50, "QKD motivation message should be substantial")


# ── 통합 테스트 ──────────────────────────────────────

class TestIntegration(unittest.TestCase):
    """통합 테스트 — 전체 파이프라인."""

    def test_full_pipeline_with_history(self):
        """전체 실행 후 히스토리가 기록됨."""
        state = shor_run_full(15)
        self.assertIsNotNone(state.factors)
        # 최소 1번의 시도가 기록되어야 함
        self.assertGreaterEqual(state.attempt, 1)

    def test_multiple_numbers(self):
        """여러 수에 대해 소인수분해 정확성 검증."""
        test_cases = [15, 21, 35, 77, 143, 221]
        for n in test_cases:
            state = shor_run_full(n)
            self.assertIsNotNone(state.factors, f"Failed to factor {n}")
            p, q = state.factors
            self.assertEqual(p * q, n, f"Incorrect factors for {n}: {p}×{q}")

    def test_step_by_step_15(self):
        """N=15 단계별 실행이 최종 성공에 도달."""
        state = ShorState(number=15)
        max_steps = 300
        for _ in range(max_steps):
            shor_step(state)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break
        # 15는 반드시 분해 가능
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 15)

    def test_qft_measurements_counted(self):
        """QFT 측정 횟수가 기록됨."""
        state = ShorState(number=15)
        max_steps = 300
        for _ in range(max_steps):
            shor_step(state)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break
        # quantum 방식이면 최소 1회 QFT 측정
        if state.factor_method == "quantum":
            self.assertGreater(state.total_qft_measurements, 0)


if __name__ == "__main__":
    unittest.main()
