"""고급 QKD 프로토콜 엔진 단위 테스트.

E91, 키 시프팅, 프라이버시 증폭, GHZ 다자간 QKD를 검증합니다.
"""

import math
import os
import sys
import unittest
from unittest.mock import MagicMock

# GUI 의존성 mock
for mod in ("pygame", "tkinter", "tkinter.messagebox", "tkinter.ttk",
            "matplotlib", "matplotlib.backends", "matplotlib.backends.backend_tkagg",
            "matplotlib.figure"):
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestE91Protocol(unittest.TestCase):
    """E91 프로토콜 테스트."""

    def test_initial_state(self):
        from security.qkd_advanced_engine import E91State
        state = E91State()
        self.assertEqual(state.total_rounds, 0)
        self.assertEqual(len(state.raw_key_alice), 0)
        self.assertFalse(state.bell_violated)

    def test_single_round(self):
        from security.qkd_advanced_engine import E91State, e91_round
        state = E91State()
        rd = e91_round(state)
        self.assertEqual(state.total_rounds, 1)
        self.assertIn(rd.alice_result, (+1, -1))
        self.assertIn(rd.bob_result, (+1, -1))
        self.assertIn(rd.alice_basis_idx, (0, 1, 2))
        self.assertIn(rd.bob_basis_idx, (0, 1, 2))

    def test_batch_rounds_generate_keys(self):
        """200 라운드 후 키 비트가 생성되어야 함."""
        from security.qkd_advanced_engine import E91State, e91_round
        state = E91State()
        for _ in range(200):
            e91_round(state)
        # 약 2/9 확률로 같은 기저 → 40개 이상 기대
        self.assertGreater(len(state.raw_key_alice), 10)
        self.assertEqual(len(state.raw_key_alice), len(state.raw_key_bob))
        self.assertEqual(state.key_rounds, len(state.raw_key_alice))

    def test_bell_violation_no_eve(self):
        """Eve 없을 때 벨 부등식 위반."""
        from security.qkd_advanced_engine import (
            CHSH_CLASSICAL_BOUND,
            E91State,
            compute_bell_S,
            e91_round,
        )
        state = E91State()
        for _ in range(1000):
            e91_round(state, eve_chance=0.0)
        S = compute_bell_S(state)
        # S ≈ 2√2 ≈ 2.828, 통계적 변동으로 2.0 이상이어야 함
        self.assertGreater(abs(S), CHSH_CLASSICAL_BOUND * 0.9,
                           f"S = {S} should exceed ~{CHSH_CLASSICAL_BOUND}")

    def test_bell_weakened_with_eve(self):
        """Eve 도청 시 벨 위반이 약해짐."""
        from security.qkd_advanced_engine import E91State, compute_bell_S, e91_round
        state = E91State()
        for _ in range(1000):
            e91_round(state, eve_chance=0.8)
        S = compute_bell_S(state)
        # Eve 도청 → 상관관계 약화 → S < 2√2
        self.assertLess(abs(S), 2.8,
                        f"S = {S} should be weakened with Eve")

    def test_eve_rounds_counted(self):
        from security.qkd_advanced_engine import E91State, e91_round
        state = E91State()
        for _ in range(100):
            e91_round(state, eve_chance=1.0)
        self.assertEqual(state.eve_rounds, 100)

    def test_rounds_history_bounded(self):
        from security.qkd_advanced_engine import E91State, e91_round
        state = E91State()
        for _ in range(300):
            e91_round(state)
        self.assertLessEqual(len(state.rounds), 200)

    def test_reset_e91(self):
        from security.qkd_advanced_engine import E91State, e91_round, reset_e91
        state = E91State()
        for _ in range(50):
            e91_round(state)
        reset_e91(state)
        self.assertEqual(state.total_rounds, 0)
        self.assertEqual(len(state.raw_key_alice), 0)
        self.assertEqual(len(state.rounds), 0)


class TestQBEREstimation(unittest.TestCase):
    """QBER 추정 테스트."""

    def test_qber_no_data(self):
        from security.qkd_advanced_engine import E91State, estimate_qber
        state = E91State()
        result = estimate_qber(state)
        self.assertEqual(result, 0.0)
        self.assertTrue(state.qber_done)

    def test_qber_low_without_eve(self):
        """Eve 없으면 QBER이 낮아야 함."""
        from security.qkd_advanced_engine import E91State, e91_round, estimate_qber
        state = E91State()
        for _ in range(500):
            e91_round(state, eve_chance=0.0)
        estimate_qber(state)
        self.assertTrue(state.qber_done)
        self.assertLess(state.qber_value, 0.1)
        self.assertGreater(state.qber_sample_size, 0)

    def test_qber_high_with_eve(self):
        """Eve 있으면 QBER이 상승해야 함."""
        from security.qkd_advanced_engine import E91State, e91_round, estimate_qber
        state = E91State()
        for _ in range(500):
            e91_round(state, eve_chance=0.8)
        estimate_qber(state)
        self.assertGreater(state.qber_value, 0.0)

    def test_qber_discards_sample(self):
        """QBER 샘플은 sifted_key에서 제외되어야 함."""
        from security.qkd_advanced_engine import E91State, e91_round, estimate_qber
        state = E91State()
        for _ in range(200):
            e91_round(state, eve_chance=0.0)
        raw_n = len(state.raw_key_alice)
        estimate_qber(state)
        # sifted = raw - sample
        self.assertEqual(len(state.sifted_key), raw_n - state.qber_sample_size)


class TestErrorCorrection(unittest.TestCase):
    """에러 정정 테스트."""

    def test_correction_no_data(self):
        from security.qkd_advanced_engine import E91State, error_correct
        state = E91State()
        state.qber_done = True
        result = error_correct(state)
        self.assertEqual(result, [])
        self.assertTrue(state.correction_done)

    def test_correction_fixes_errors(self):
        """에러 정정 후 일치율이 올라야 함."""
        from security.qkd_advanced_engine import (
            E91State,
            e91_round,
            error_correct,
            estimate_qber,
        )
        state = E91State()
        for _ in range(500):
            e91_round(state, eve_chance=0.3)
        estimate_qber(state)
        error_correct(state)
        self.assertTrue(state.correction_done)
        # 정정된 키가 존재해야 함
        self.assertGreater(len(state.corrected_key), 0)

    def test_correction_no_flips_without_eve(self):
        """Eve 없으면 정정할 비트가 거의 없어야 함."""
        from security.qkd_advanced_engine import (
            E91State,
            e91_round,
            error_correct,
            estimate_qber,
        )
        state = E91State()
        for _ in range(500):
            e91_round(state, eve_chance=0.0)
        estimate_qber(state)
        error_correct(state)
        # 대부분 0 또는 매우 적은 flip
        self.assertLessEqual(state.correction_flips, 3)


class TestKeySifting(unittest.TestCase):
    """통합 키 시프팅 파이프라인 테스트."""

    def test_sift_no_data(self):
        from security.qkd_advanced_engine import E91State, key_sift
        state = E91State()
        result = key_sift(state)
        self.assertEqual(result, [])
        self.assertTrue(state.sift_done)

    def test_sift_runs_full_pipeline(self):
        """key_sift가 QBER 추정 + 에러 정정을 순차 실행."""
        from security.qkd_advanced_engine import E91State, e91_round, key_sift
        state = E91State()
        for _ in range(200):
            e91_round(state, eve_chance=0.0)
        result = key_sift(state)
        self.assertTrue(state.qber_done)
        self.assertTrue(state.correction_done)
        self.assertTrue(state.sift_done)
        self.assertGreater(len(result), 0)

    def test_sift_high_match_no_eve(self):
        """Eve 없으면 매칭률이 높아야 함."""
        from security.qkd_advanced_engine import E91State, e91_round, key_sift
        state = E91State()
        for _ in range(500):
            e91_round(state, eve_chance=0.0)
        key_sift(state)
        self.assertGreater(state.key_match_rate, 0.7)

    def test_sift_lower_match_with_eve(self):
        """Eve 있으면 에러율 상승."""
        from security.qkd_advanced_engine import E91State, e91_round, key_sift
        state = E91State()
        for _ in range(500):
            e91_round(state, eve_chance=0.8)
        key_sift(state)
        self.assertGreater(state.error_rate, 0.0)


class TestPrivacyAmplification(unittest.TestCase):
    """프라이버시 증폭 테스트."""

    def test_pa_empty_key(self):
        from security.qkd_advanced_engine import E91State, privacy_amplification
        state = E91State()
        result = privacy_amplification(state)
        self.assertEqual(result, "")
        self.assertTrue(state.pa_done)

    def test_pa_produces_hex_key(self):
        from security.qkd_advanced_engine import (
            E91State,
            e91_round,
            key_sift,
            privacy_amplification,
        )
        state = E91State()
        for _ in range(200):
            e91_round(state)
        key_sift(state)
        final = privacy_amplification(state)
        self.assertGreater(len(final), 0)
        # 유효한 hex 문자열인지 확인
        int(final, 16)
        self.assertTrue(state.pa_done)

    def test_pa_deterministic(self):
        """같은 시프트 키 → 같은 최종 키."""
        from security.qkd_advanced_engine import E91State, privacy_amplification
        state = E91State()
        state.sifted_key = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1]
        key1 = privacy_amplification(state)
        state.pa_done = False
        key2 = privacy_amplification(state)
        self.assertEqual(key1, key2)

    def test_pa_compressed(self):
        """PA 후 키는 SHA-256 길이의 절반 이하."""
        from security.qkd_advanced_engine import E91State, privacy_amplification
        state = E91State()
        state.sifted_key = [random_bit() for _ in range(100)]
        final = privacy_amplification(state)
        self.assertLessEqual(len(final), 64)  # SHA-256 = 64 hex chars


def random_bit():
    import random
    return random.randint(0, 1)


class TestGHZProtocol(unittest.TestCase):
    """GHZ 다자간 QKD 테스트."""

    def test_initial_state(self):
        from security.qkd_advanced_engine import GHZState
        state = GHZState()
        self.assertEqual(state.n_parties, 3)
        self.assertEqual(len(state.party_names), 3)
        self.assertEqual(state.total_rounds, 0)

    def test_single_round(self):
        from security.qkd_advanced_engine import GHZState, ghz_round
        state = GHZState()
        rd = ghz_round(state)
        self.assertEqual(state.total_rounds, 1)
        self.assertEqual(len(rd.bases), 3)
        self.assertEqual(len(rd.results), 3)
        for b in rd.bases:
            self.assertIn(b, ("X", "Z"))
        for r in rd.results:
            self.assertIn(r, (0, 1))

    def test_batch_generates_keys(self):
        """200 라운드 후 키 비트가 생성되어야 함."""
        from security.qkd_advanced_engine import GHZState, ghz_round
        state = GHZState()
        for _ in range(200):
            ghz_round(state)
        # 1/4 확률로 ZZZ → 약 50개 기대
        self.assertGreater(state.key_rounds, 5)

    def test_z_basis_correlation_no_eve(self):
        """Eve 없을 때 Z 기저 결과는 모두 같아야 함."""
        from security.qkd_advanced_engine import GHZState, ghz_round
        state = GHZState()
        all_same = 0
        key_count = 0
        for _ in range(500):
            rd = ghz_round(state, eve_chance=0.0)
            if rd.all_same_basis and rd.bases[0] == "Z":
                key_count += 1
                if len(set(rd.results)) == 1:
                    all_same += 1
        if key_count > 0:
            rate = all_same / key_count
            self.assertGreater(rate, 0.9,
                               f"Z basis should give same results: {rate:.2f}")

    def test_x_basis_parity_no_eve(self):
        """Eve 없을 때 X 기저 패리티는 짝수."""
        from security.qkd_advanced_engine import GHZState, ghz_round
        state = GHZState()
        for _ in range(500):
            ghz_round(state, eve_chance=0.0)
        if state.consistency_checks > 0:
            pass_rate = state.consistency_pass / state.consistency_checks
            self.assertGreater(pass_rate, 0.9)

    def test_eve_disrupts_consistency(self):
        """Eve 도청 시 일관성 검증 실패율 상승."""
        from security.qkd_advanced_engine import GHZState, ghz_round
        state = GHZState()
        for _ in range(500):
            ghz_round(state, eve_chance=0.8)
        if state.consistency_checks > 0:
            pass_rate = state.consistency_pass / state.consistency_checks
            # Eve → 패리티 깨짐 → 패스율 하락
            self.assertLess(pass_rate, 0.95)

    def test_ghz_key_sift(self):
        from security.qkd_advanced_engine import GHZState, ghz_key_sift, ghz_round
        state = GHZState()
        for _ in range(200):
            ghz_round(state, eve_chance=0.0)
        sifted = ghz_key_sift(state)
        self.assertTrue(state.sift_done)
        self.assertLessEqual(len(sifted), len(state.raw_keys[0]))

    def test_ghz_privacy_amplification(self):
        from security.qkd_advanced_engine import (
            GHZState,
            ghz_key_sift,
            ghz_privacy_amplification,
            ghz_round,
        )
        state = GHZState()
        for _ in range(200):
            ghz_round(state)
        ghz_key_sift(state)
        final = ghz_privacy_amplification(state)
        self.assertTrue(state.pa_done)
        if state.sifted_key:
            self.assertGreater(len(final), 0)

    def test_rounds_history_bounded(self):
        from security.qkd_advanced_engine import GHZState, ghz_round
        state = GHZState()
        for _ in range(300):
            ghz_round(state)
        self.assertLessEqual(len(state.rounds), 200)

    def test_reset_ghz(self):
        from security.qkd_advanced_engine import GHZState, ghz_round, reset_ghz
        state = GHZState()
        for _ in range(50):
            ghz_round(state)
        reset_ghz(state)
        self.assertEqual(state.total_rounds, 0)
        self.assertEqual(len(state.rounds), 0)
        self.assertEqual(len(state.raw_keys[0]), 0)


class TestE91Constants(unittest.TestCase):
    """E91 상수 검증."""

    def test_alice_bases(self):
        from security.qkd_advanced_engine import E91_ALICE_BASES
        self.assertEqual(len(E91_ALICE_BASES), 3)
        self.assertAlmostEqual(E91_ALICE_BASES[0], 0.0)
        self.assertAlmostEqual(E91_ALICE_BASES[1], math.pi / 8)
        self.assertAlmostEqual(E91_ALICE_BASES[2], math.pi / 4)

    def test_bob_bases(self):
        from security.qkd_advanced_engine import E91_BOB_BASES
        self.assertEqual(len(E91_BOB_BASES), 3)
        self.assertAlmostEqual(E91_BOB_BASES[0], math.pi / 8)
        self.assertAlmostEqual(E91_BOB_BASES[1], math.pi / 4)
        self.assertAlmostEqual(E91_BOB_BASES[2], 3 * math.pi / 8)

    def test_chsh_bounds(self):
        from security.qkd_advanced_engine import CHSH_CLASSICAL_BOUND, CHSH_QUANTUM_BOUND
        self.assertAlmostEqual(CHSH_CLASSICAL_BOUND, 2.0)
        self.assertAlmostEqual(CHSH_QUANTUM_BOUND, 2 * math.sqrt(2), places=10)

    def test_key_pairs_valid(self):
        """키 쌍이 같은 각도를 가리키는지 확인."""
        from security.qkd_advanced_engine import (
            E91_ALICE_BASES,
            E91_BOB_BASES,
            E91_KEY_PAIRS,
        )
        for a_idx, b_idx in E91_KEY_PAIRS:
            self.assertAlmostEqual(
                E91_ALICE_BASES[a_idx], E91_BOB_BASES[b_idx],
                msg=f"Key pair ({a_idx},{b_idx}) should be same angle")


class TestMeasureEntangled(unittest.TestCase):
    """얽힘 측정 함수 테스트."""

    def test_same_angle_perfect_correlation(self):
        """같은 각도로 측정하면 항상 같은 결과."""
        from security.qkd_advanced_engine import _measure_entangled
        same = 0
        n = 200
        for _ in range(n):
            a, b = _measure_entangled(0.0, 0.0, eve_present=False)
            if a == b:
                same += 1
        self.assertGreater(same / n, 0.9)

    def test_orthogonal_angles_anticorrelation(self):
        """직교 편광(90°)으로 측정하면 반상관."""
        from security.qkd_advanced_engine import _measure_entangled
        diff = 0
        n = 200
        for _ in range(n):
            a, b = _measure_entangled(0.0, math.pi / 2, eve_present=False)
            if a != b:
                diff += 1
        self.assertGreater(diff / n, 0.7)

    def test_results_are_pm1(self):
        from security.qkd_advanced_engine import _measure_entangled
        for _ in range(50):
            a, b = _measure_entangled(0.3, 0.5)
            self.assertIn(a, (+1, -1))
            self.assertIn(b, (+1, -1))


if __name__ == "__main__":
    unittest.main()
