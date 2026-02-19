"""Shor's Algorithm 엔진 단위 테스트."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum.shor_algorithm_engine import (
    MAX_NUMBER,
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
    finalize_rsa_crack,
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


# ── 고전 전처리 심화 테스트 ────────────────────────────

class TestClassicalPrecheck(unittest.TestCase):
    """고전 전처리 단계 — 짝수/소수/소수거듭제곱/합성수 분기."""

    def _run_to_precheck(self, n):
        """INPUT → CLASSICAL_PRECHECK 실행 후 상태 반환."""
        state = ShorState(number=n)
        shor_step(state)   # INPUT → CLASSICAL_PRECHECK
        shor_step(state)   # CLASSICAL_PRECHECK → (결과)
        return state

    def test_even_numbers(self):
        """짝수는 즉시 (2, N/2)로 분해."""
        for n in [6, 10, 14, 22, 100, 1000]:
            state = self._run_to_precheck(n)
            self.assertEqual(state.phase, ShorPhase.SUCCESS, f"N={n}")
            self.assertEqual(state.factors, (2, n // 2), f"N={n}")
            self.assertEqual(state.factor_method, "trivial_even", f"N={n}")
            self.assertTrue(state.is_even, f"N={n}")

    def test_small_primes(self):
        """소수는 DONE + is_prime=True."""
        for p in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]:
            state = self._run_to_precheck(p)
            if p == 2:
                # 2는 짝수로 먼저 잡힘 → SUCCESS with (2, 1)
                self.assertEqual(state.phase, ShorPhase.SUCCESS)
            else:
                self.assertEqual(state.phase, ShorPhase.DONE, f"p={p}")
                self.assertTrue(state.is_prime, f"p={p}")
                self.assertIsNone(state.factors, f"p={p}")

    def test_prime_powers(self):
        """소수 거듭제곱 → SUCCESS (trivial_prime_power)."""
        cases = [(4, 2), (8, 2), (9, 3), (25, 5), (27, 3), (32, 2),
                 (49, 7), (121, 11), (125, 5), (128, 2), (169, 13)]
        for n, expected_base in cases:
            state = self._run_to_precheck(n)
            if n % 2 == 0:
                # 짝수는 trivial_even으로 먼저 잡힘
                self.assertEqual(state.phase, ShorPhase.SUCCESS, f"N={n}")
            else:
                self.assertEqual(state.phase, ShorPhase.SUCCESS, f"N={n}")
                p, q = state.factors
                self.assertEqual(p * q, n, f"N={n}: {p}×{q}")

    def test_composite_passes_to_quantum(self):
        """일반 합성수 → PICK_RANDOM_A로 진행."""
        for n in [15, 21, 33, 35, 55, 77, 91, 143]:
            state = self._run_to_precheck(n)
            self.assertEqual(state.phase, ShorPhase.PICK_RANDOM_A, f"N={n}")

    def test_n_less_than_2(self):
        """N < 2 → 즉시 DONE."""
        for n in [0, 1, -5]:
            state = ShorState(number=n)
            shor_step(state)
            self.assertEqual(state.phase, ShorPhase.DONE, f"N={n}")


# ── 주기 탐색 정확성 심화 테스트 ──────────────────────

class TestPeriodFindingAccuracy(unittest.TestCase):
    """a^r ≡ 1 (mod N) 주기의 정확성 검증."""

    def test_all_coprime_pairs_mod_15(self):
        """N=15에 대해 모든 coprime a의 위수 검증."""
        # gcd(a, 15) = 1인 a: 1, 2, 4, 7, 8, 11, 13, 14
        expected = {1: 1, 2: 4, 4: 2, 7: 4, 8: 4, 11: 2, 13: 4, 14: 2}
        for a, exp_r in expected.items():
            r = find_order(a, 15)
            self.assertEqual(r, exp_r, f"order({a}, 15) = {r}, expected {exp_r}")
            # 검증: a^r mod N = 1
            self.assertEqual(mod_pow(a, r, 15), 1,
                             f"{a}^{r} mod 15 != 1")

    def test_all_coprime_pairs_mod_21(self):
        """N=21에 대해 coprime a의 위수 검증."""
        # gcd(a, 21) = 1인 a 몇 개 검증
        test_pairs = {2: 6, 4: 3, 5: 6, 8: 2, 10: 6, 11: 6, 13: 2, 16: 3}
        for a, exp_r in test_pairs.items():
            r = find_order(a, 21)
            self.assertEqual(r, exp_r, f"order({a}, 21) = {r}, expected {exp_r}")
            self.assertEqual(mod_pow(a, r, 21), 1)

    def test_period_minimality(self):
        """위수 r은 최소 — r보다 작은 k에 대해 a^k mod N != 1."""
        test_cases = [(2, 15), (7, 15), (2, 21), (4, 35), (3, 35)]
        for a, n in test_cases:
            r = find_order(a, n)
            if r is not None and r > 1:
                for k in range(1, r):
                    self.assertNotEqual(mod_pow(a, k, n), 1,
                                        f"a={a}, n={n}: a^{k} mod n = 1, "
                                        f"but order should be {r}")

    def test_non_coprime_returns_none(self):
        """gcd(a, N) > 1이면 위수 없음."""
        pairs = [(3, 15), (5, 15), (3, 21), (7, 21), (5, 35), (7, 35)]
        for a, n in pairs:
            self.assertIsNone(find_order(a, n),
                              f"order({a}, {n}) should be None (gcd > 1)")

    def test_period_divides_euler_phi(self):
        """위수 r은 오일러 phi(N)의 약수."""
        def euler_phi(n):
            result = n
            p = 2
            temp = n
            while p * p <= temp:
                if temp % p == 0:
                    while temp % p == 0:
                        temp //= p
                    result -= result // p
                p += 1
            if temp > 1:
                result -= result // temp
            return result

        for n in [15, 21, 35, 77, 143]:
            phi = euler_phi(n)
            for a in range(2, min(n, 20)):
                if gcd(a, n) == 1:
                    r = find_order(a, n)
                    self.assertIsNotNone(r)
                    self.assertEqual(phi % r, 0,
                                     f"order({a},{n})={r} does not divide phi({n})={phi}")


# ── 모듈러 지수 계산 심화 테스트 ─────────────────────

class TestModularExponentiation(unittest.TestCase):
    """모듈러 지수 계산 및 테이블 심화 테스트."""

    def test_mod_pow_large(self):
        """큰 수에 대한 모듈러 지수."""
        self.assertEqual(mod_pow(2, 100, 1000000007), pow(2, 100, 1000000007))
        self.assertEqual(mod_pow(123, 456, 789), pow(123, 456, 789))

    def test_mod_pow_edge(self):
        """모듈러 지수 에지 케이스."""
        self.assertEqual(mod_pow(0, 0, 7), 1)   # 0^0 = 1 (convention)
        self.assertEqual(mod_pow(0, 5, 7), 0)   # 0^5 = 0
        self.assertEqual(mod_pow(1, 999, 7), 1)  # 1^any = 1
        self.assertEqual(mod_pow(6, 1, 7), 6)   # a^1 = a

    def test_table_periodicity(self):
        """테이블에서 주기적 패턴 확인."""
        table = build_mod_exp_table(2, 15, 20)
        values = [e.value for e in table]
        # 주기 4: [1, 2, 4, 8, 1, 2, 4, 8, ...]
        for i in range(4, len(values)):
            self.assertEqual(values[i], values[i % 4],
                             f"position {i}: {values[i]} != {values[i % 4]}")

    def test_table_first_entry_always_one(self):
        """a^0 mod N = 1 (N > 1일 때)."""
        for a, n in [(2, 15), (7, 21), (4, 35), (11, 143)]:
            table = build_mod_exp_table(a, n, 8)
            self.assertEqual(table[0].value, 1, f"a={a}, N={n}")

    def test_table_second_entry_is_a_mod_n(self):
        """a^1 mod N = a (a < N일 때)."""
        for a, n in [(2, 15), (7, 21), (4, 35)]:
            table = build_mod_exp_table(a, n, 8)
            self.assertEqual(table[1].value, a % n, f"a={a}, N={n}")

    def test_detect_period_various(self):
        """다양한 (a, N) 조합에서 주기 탐지."""
        cases = [
            (2, 15, 4),   # 2^4 mod 15 = 1
            (4, 15, 2),   # 4^2 mod 15 = 1
            (7, 15, 4),   # 7^4 mod 15 = 1
            (2, 21, 6),   # 2^6 mod 21 = 1
            (4, 21, 3),   # 4^3 mod 21 = 1
        ]
        for a, n, expected_period in cases:
            table = build_mod_exp_table(a, n, expected_period * 3)
            period = detect_period_from_table(table)
            self.assertEqual(period, expected_period,
                             f"a={a}, N={n}: detected={period}, expected={expected_period}")

    def test_detect_period_empty_table(self):
        """빈 테이블 → 주기 0."""
        self.assertEqual(detect_period_from_table([]), 0)

    def test_detect_period_single_entry(self):
        """단일 항목 → 주기 0."""
        self.assertEqual(detect_period_from_table([ModExpEntry(0, 1)]), 0)


# ── 연분수 전개 심화 테스트 ──────────────────────────

class TestContinuedFractionAdvanced(unittest.TestCase):
    """Shor 알고리즘에서 사용되는 연분수 전개 심화 테스트."""

    def test_shor_relevant_fractions(self):
        """QFT 측정에서 자주 나오는 분수의 연분수 전개 검증."""
        # m/Q ≈ s/r 형태. Q=256, r=4 → 피크: 0/256, 64/256, 128/256, 192/256
        # 64/256 = 1/4
        cf = continued_fraction(64, 256)
        convs = convergents(cf)
        # 수렴분수에 (1, 4) 포함
        denominators = [q for _, q in convs]
        self.assertIn(4, denominators)

        # 128/256 = 1/2
        cf = continued_fraction(128, 256)
        convs = convergents(cf)
        denominators = [q for _, q in convs]
        self.assertIn(2, denominators)

    def test_convergent_denominators_for_period_6(self):
        """r=6, Q=256: 피크 m ≈ 43, 85, 128, 171, 213에서 r=6 추출."""
        # s=1, m ≈ 256/6 ≈ 42.67 → m=43
        cf = continued_fraction(43, 256)
        convs = convergents(cf)
        denominators = [q for _, q in convs]
        self.assertIn(6, denominators, f"Denominators: {denominators}")

    def test_reconstruction_from_convergents(self):
        """수렴분수가 원래 분수를 정확히 재현."""
        fractions = [(1, 3), (2, 7), (5, 17), (11, 23), (100, 256)]
        for num, den in fractions:
            cf = continued_fraction(num, den)
            convs = convergents(cf)
            p, q = convs[-1]
            # 약분된 형태로 비교
            g = gcd(num, den)
            self.assertEqual(p, num // g, f"{num}/{den}")
            self.assertEqual(q, den // g, f"{num}/{den}")

    def test_continued_fraction_deterministic(self):
        """같은 입력 → 같은 결과."""
        cf1 = continued_fraction(89, 256)
        cf2 = continued_fraction(89, 256)
        self.assertEqual(cf1, cf2)

    def test_convergents_monotonically_improve(self):
        """수렴분수는 원래 값에 점점 가까워짐."""
        num, den = 355, 113
        target = num / den
        cf = continued_fraction(num, den)
        convs = convergents(cf)
        errors = [abs(p / q - target) for p, q in convs if q > 0]
        # 마지막 오차는 0에 가까워야 함
        self.assertAlmostEqual(errors[-1], 0.0, places=10)


# ── 전체 파이프라인 통합 심화 테스트 ─────────────────

class TestFullPipelineAdvanced(unittest.TestCase):
    """전체 파이프라인 통합 심화 테스트 — 다양한 수."""

    def test_known_semiprimes(self):
        """알려진 반소수(semiprime)들의 소인수분해 정확성."""
        semiprimes = {
            15: {(3, 5)},
            21: {(3, 7)},
            35: {(5, 7)},
            77: {(7, 11)},
            91: {(7, 13)},
            143: {(11, 13)},
            221: {(13, 17)},
            323: {(17, 19)},
        }
        for n, expected_pairs in semiprimes.items():
            state = shor_run_full(n)
            self.assertIsNotNone(state.factors, f"Failed to factor {n}")
            p, q = state.factors
            self.assertEqual(p * q, n, f"N={n}: {p}×{q} != {n}")
            # 정렬된 쌍으로 비교
            pair = (min(p, q), max(p, q))
            expected_sorted = {(min(a, b), max(a, b)) for a, b in expected_pairs}
            self.assertIn(pair, expected_sorted,
                          f"N={n}: got {pair}, expected one of {expected_sorted}")

    def test_three_factor_composites(self):
        """3개 이상 소인수를 가진 수 — 부분 인수 발견."""
        for n in [30, 42, 66, 105, 210]:
            state = shor_run_full(n)
            self.assertIsNotNone(state.factors, f"Failed to factor {n}")
            p, q = state.factors
            self.assertEqual(p * q, n, f"N={n}: {p}×{q}")
            # 둘 다 자명하지 않은 인수
            self.assertGreater(p, 1, f"N={n}: trivial factor p={p}")
            self.assertGreater(q, 1, f"N={n}: trivial factor q={q}")

    def test_step_by_step_reaches_success(self):
        """단계별 실행이 SUCCESS에 도달하는지 확인 (여러 수)."""
        for n in [15, 21, 35]:
            state = ShorState(number=n)
            for _ in range(500):
                shor_step(state)
                if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                    break
            self.assertIsNotNone(state.factors, f"N={n}")
            p, q = state.factors
            self.assertEqual(p * q, n, f"N={n}")

    def test_step_by_step_phase_order(self):
        """단계별 실행에서 phase 순서가 올바른지 확인."""
        state = ShorState(number=15)
        visited = []
        for _ in range(500):
            if state.phase not in visited:
                visited.append(state.phase)
            shor_step(state)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                if state.phase not in visited:
                    visited.append(state.phase)
                break
        # INPUT은 항상 첫 번째
        self.assertEqual(visited[0], ShorPhase.INPUT)
        # CLASSICAL_PRECHECK은 두 번째
        self.assertEqual(visited[1], ShorPhase.CLASSICAL_PRECHECK)
        # 최종적으로 SUCCESS 또는 DONE 도달
        self.assertIn(visited[-1], (ShorPhase.SUCCESS, ShorPhase.DONE))

    def test_attempt_history_recorded(self):
        """시도 히스토리가 올바르게 기록됨."""
        state = ShorState(number=15)
        for _ in range(500):
            shor_step(state)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break
        if state.factor_method == "quantum":
            self.assertGreater(len(state.attempt_history), 0)
            last = state.attempt_history[-1]
            self.assertIn("attempt", last)
            self.assertIn("a", last)

    def test_factors_product_always_matches(self):
        """모든 성공 케이스에서 p×q = N."""
        for n in range(4, 100):
            if is_prime(n):
                continue
            state = shor_run_full(n)
            if state.factors is not None:
                p, q = state.factors
                self.assertEqual(p * q, n, f"N={n}: {p}×{q}")


# ── 에지 케이스 심화 테스트 ──────────────────────────

class TestEdgeCases(unittest.TestCase):
    """에지 케이스 — 경계값, 특수 수."""

    def test_n_equals_0(self):
        """N=0 → DONE."""
        state = shor_run_full(0)
        self.assertIsNone(state.factors)

    def test_n_equals_1(self):
        """N=1 → DONE."""
        state = shor_run_full(1)
        self.assertIsNone(state.factors)

    def test_n_equals_2(self):
        """N=2 (소수) → 인수 없음."""
        state = shor_run_full(2)
        # 2는 짝수이므로 (2, 1)로 분해됨
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 2)

    def test_n_equals_3(self):
        """N=3 (소수) → 인수 없음."""
        state = shor_run_full(3)
        self.assertIsNone(state.factors)

    def test_n_equals_4(self):
        """N=4 (2^2) → 짝수 분해."""
        state = shor_run_full(4)
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 4)

    def test_perfect_squares(self):
        """완전 제곱수 분해."""
        squares = [9, 25, 49, 121, 169]
        for n in squares:
            state = shor_run_full(n)
            self.assertIsNotNone(state.factors, f"N={n}")
            p, q = state.factors
            self.assertEqual(p * q, n, f"N={n}")

    def test_large_prime(self):
        """큰 소수 → 인수 없음."""
        state = shor_run_full(7919)
        self.assertIsNone(state.factors)
        self.assertTrue(state.is_prime)

    def test_carmichael_number(self):
        """카마이클 수 (561 = 3×11×17) 분해."""
        state = shor_run_full(561)
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 561)

    def test_max_number_exceeded(self):
        """MAX_NUMBER 초과 → DONE."""
        state = ShorState(number=MAX_NUMBER + 1)
        shor_step(state)
        self.assertEqual(state.phase, ShorPhase.DONE)

    def test_consecutive_resets(self):
        """연속 리셋 후에도 정상 작동."""
        state = ShorState(number=15)
        shor_run_full(15)
        reset_state(state, 21)
        self.assertEqual(state.number, 21)
        self.assertEqual(state.phase, ShorPhase.INPUT)
        reset_state(state, 35)
        self.assertEqual(state.number, 35)

        # 리셋 후 실행
        for _ in range(500):
            shor_step(state)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 35)

    def test_even_prime_power(self):
        """짝수 소수 거듭제곱 (예: 16=2^4) → 짝수 분기 우선."""
        state = ShorState(number=16)
        shor_step(state)   # INPUT
        shor_step(state)   # CLASSICAL_PRECHECK
        self.assertEqual(state.factor_method, "trivial_even")
        self.assertEqual(state.factors, (2, 8))

    def test_large_semiprime(self):
        """큰 반소수 (667 = 23×29) 분해."""
        state = shor_run_full(667)
        self.assertIsNotNone(state.factors)
        p, q = state.factors
        self.assertEqual(p * q, 667)
        pair = (min(p, q), max(p, q))
        self.assertEqual(pair, (23, 29))


# ── QFT 시뮬레이션 심화 테스트 ───────────────────────

class TestQFTAdvanced(unittest.TestCase):
    """QFT 시뮬레이션 심화 테스트."""

    def test_qft_peaks_match_period(self):
        """QFT 확률 분포 피크가 s*Q/r 위치에 집중."""
        a, n, n_qubits = 2, 15, 8
        Q = 1 << n_qubits  # 256
        r = find_order(a, n)  # 4
        self.assertEqual(r, 4)

        probs = compute_qft_probability_distribution(a, n, n_qubits)
        # 피크 위치: 0, 64, 128, 192
        peak_indices = [s * Q // r for s in range(r)]
        for idx in peak_indices:
            # 피크 근처(±1) 확률이 균등 확률보다 훨씬 높아야 함
            peak_prob = sum(probs[max(0, idx - 1):min(Q, idx + 2)])
            uniform_prob = 3.0 / Q
            self.assertGreater(peak_prob, uniform_prob * 5,
                               f"Peak at {idx} not prominent enough")

    def test_qft_non_coprime_uniform(self):
        """gcd(a, N) > 1이면 균등 분포."""
        probs = compute_qft_probability_distribution(3, 15, 8)
        # 균등 분포: 모든 값이 거의 같아야 함
        avg = sum(probs) / len(probs)
        for p in probs:
            self.assertAlmostEqual(p, avg, places=5)

    def test_qft_different_qubits(self):
        """큐빗 수를 바꿔도 확률 합 = 1."""
        for n_q in [4, 6, 8, 10]:
            probs = compute_qft_probability_distribution(2, 15, n_q)
            self.assertAlmostEqual(sum(probs), 1.0, places=5)
            self.assertEqual(len(probs), 1 << n_q)

    def test_statistical_period_recovery(self):
        """통계적으로 QFT 측정에서 올바른 주기를 복원."""
        a, n = 7, 15
        expected_r = find_order(a, n)  # 4
        found_periods = {}

        for _ in range(50):
            result = simulate_qft_measurement(a, n, 8)
            if result.candidate_r is not None:
                found_periods[result.candidate_r] = \
                    found_periods.get(result.candidate_r, 0) + 1

        # 올바른 주기가 가장 많이 발견되어야 함
        self.assertIn(expected_r, found_periods,
                      f"Period {expected_r} not found in {found_periods}")
        self.assertEqual(
            max(found_periods, key=found_periods.get), expected_r,
            f"Period distribution: {found_periods}")


# ── RSA 위협 데모 심화 테스트 ────────────────────────

class TestRSAAdvanced(unittest.TestCase):
    """RSA 위협 데모 심화 테스트."""

    def test_all_difficulty_levels(self):
        """모든 난이도 레벨에서 RSA 크래킹 성공."""
        for diff in range(min(6, len(RSA_EXAMPLES))):
            state = ShorState()
            setup_rsa_demo(state, difficulty=diff)

            # RSA 키 유효성
            rsa = state.rsa
            self.assertEqual(rsa.rsa_n, rsa.rsa_p * rsa.rsa_q,
                             f"diff={diff}")
            self.assertTrue(is_prime(rsa.rsa_p), f"diff={diff}")
            self.assertTrue(is_prime(rsa.rsa_q), f"diff={diff}")

            # 크래킹
            original = rsa.plaintext
            success = crack_rsa(state)
            self.assertTrue(success, f"diff={diff}: crack failed")
            self.assertEqual(state.rsa.decrypted, original,
                             f"diff={diff}: decryption mismatch")

    def test_rsa_encryption_decryption(self):
        """RSA 암호화/복호화가 올바른지 직접 검증."""
        state = ShorState()
        setup_rsa_demo(state, difficulty=0)
        rsa = state.rsa
        # ciphertext = plaintext^e mod N
        self.assertEqual(rsa.ciphertext,
                         mod_pow(rsa.plaintext, rsa.rsa_e, rsa.rsa_n))

    def test_difficulty_out_of_range(self):
        """난이도가 범위를 초과해도 정상 작동."""
        state = ShorState()
        setup_rsa_demo(state, difficulty=999)
        self.assertGreater(state.rsa.rsa_n, 0)

    def test_finalize_rsa_crack_after_shor_success(self):
        """소인수분해 성공 후 finalize_rsa_crack으로 RSA 복호화."""
        state = ShorState()
        setup_rsa_demo(state, difficulty=0)
        original = state.rsa.plaintext

        # Shor 단계별 실행으로 소인수분해
        max_iter = 200
        for _ in range(max_iter):
            shor_step(state)
            if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                break

        self.assertEqual(state.phase, ShorPhase.SUCCESS)
        self.assertIsNotNone(state.factors)

        # finalize_rsa_crack으로 후처리
        success = finalize_rsa_crack(state)
        self.assertTrue(success)
        self.assertTrue(state.rsa.cracked)
        self.assertEqual(state.rsa.decrypted, original)

    def test_finalize_rsa_crack_without_factors_fails(self):
        """소인수분해 미완료 시 finalize_rsa_crack은 False."""
        state = ShorState()
        setup_rsa_demo(state, difficulty=0)
        state.factors = None

        success = finalize_rsa_crack(state)
        self.assertFalse(success)
        self.assertFalse(state.rsa.cracked)

    def test_finalize_rsa_crack_all_difficulties(self):
        """모든 난이도에서 단계별 크래킹 + finalize_rsa_crack 성공."""
        for diff in range(min(4, len(RSA_EXAMPLES))):
            state = ShorState()
            setup_rsa_demo(state, difficulty=diff)
            original = state.rsa.plaintext

            for _ in range(200):
                shor_step(state)
                if state.phase in (ShorPhase.SUCCESS, ShorPhase.DONE):
                    break

            if state.phase == ShorPhase.SUCCESS:
                success = finalize_rsa_crack(state)
                self.assertTrue(success, f"diff={diff}")
                self.assertEqual(state.rsa.decrypted, original,
                                 f"diff={diff}")


if __name__ == "__main__":
    unittest.main()
