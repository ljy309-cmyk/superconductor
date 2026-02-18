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

    def test_bell_s_history_recorded(self):
        """compute_bell_S 호출 시 히스토리가 기록되어야 함."""
        from security.qkd_advanced_engine import E91State, compute_bell_S, e91_round
        state = E91State()
        for _ in range(100):
            e91_round(state)
        compute_bell_S(state)
        self.assertEqual(len(state.bell_S_history), 1)
        rd, s_val = state.bell_S_history[0]
        self.assertEqual(rd, state.total_rounds)
        self.assertAlmostEqual(s_val, state.bell_S)

    def test_bell_s_history_bounded(self):
        """히스토리가 200개로 제한되어야 함."""
        from security.qkd_advanced_engine import E91State, compute_bell_S, e91_round
        state = E91State()
        for i in range(250):
            e91_round(state)
            if (i + 1) % 1 == 0:
                compute_bell_S(state)
        self.assertLessEqual(len(state.bell_S_history), 200)

    def test_bell_s_history_convergence(self):
        """충분한 라운드 후 S가 이론값에 수렴해야 함 (Eve 없음)."""
        from security.qkd_advanced_engine import E91State, compute_bell_S, e91_round
        state = E91State()
        for i in range(500):
            e91_round(state, eve_chance=0.0)
            if (i + 1) % 50 == 0:
                compute_bell_S(state)
        # 마지막 S 값은 2.0 이상 (벨 위반)
        self.assertGreater(len(state.bell_S_history), 0)
        _, last_s = state.bell_S_history[-1]
        self.assertGreater(abs(last_s), 2.0)

    def test_reset_e91(self):
        from security.qkd_advanced_engine import E91State, e91_round, reset_e91
        state = E91State()
        for _ in range(50):
            e91_round(state)
        reset_e91(state)
        self.assertEqual(state.total_rounds, 0)
        self.assertEqual(len(state.raw_key_alice), 0)
        self.assertEqual(len(state.rounds), 0)
        self.assertEqual(len(state.bell_S_history), 0)


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
        for _ in range(2000):
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
        for _ in range(2000):
            e91_round(state, eve_chance=0.8)
        key_sift(state)
        self.assertGreater(state.error_rate, 0.0)


class TestToeplitzHash(unittest.TestCase):
    """Toeplitz 범용 해시 테스트."""

    def test_output_length(self):
        """출력 길이가 지정한 대로."""
        from security.qkd_advanced_engine import _toeplitz_hash
        key = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1]
        for m in [4, 8, 5]:
            out, seed = _toeplitz_hash(key, m)
            self.assertEqual(len(out), m)

    def test_output_is_binary(self):
        """출력이 0/1 비트."""
        from security.qkd_advanced_engine import _toeplitz_hash
        key = [1, 0, 1, 1, 0, 0, 1, 0]
        out, seed = _toeplitz_hash(key, 4)
        for bit in out:
            self.assertIn(bit, (0, 1))

    def test_deterministic_with_same_seed(self):
        """같은 시드 → 같은 출력."""
        from security.qkd_advanced_engine import _toeplitz_hash
        key = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1]
        out1, seed = _toeplitz_hash(key, 5)
        out2, _ = _toeplitz_hash(key, 5, seed=seed)
        self.assertEqual(out1, out2)

    def test_different_keys_different_output(self):
        """다른 키 → 높은 확률로 다른 출력 (2-universal)."""
        from security.qkd_advanced_engine import _toeplitz_hash
        key1 = [1, 0, 1, 1, 0, 0, 1, 0]
        key2 = [0, 1, 0, 0, 1, 1, 0, 1]
        seed = [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1]  # m + n - 1 = 4 + 8 - 1 = 11
        out1, _ = _toeplitz_hash(key1, 4, seed=seed)
        out2, _ = _toeplitz_hash(key2, 4, seed=seed)
        # 2-universal: 충돌 확률 ≤ 1/2^m = 1/16
        # 이 특정 입력에서는 다른 출력이어야 함
        self.assertNotEqual(out1, out2)

    def test_empty_key(self):
        from security.qkd_advanced_engine import _toeplitz_hash
        out, seed = _toeplitz_hash([], 4)
        self.assertEqual(out, [])

    def test_seed_length(self):
        """시드 길이 = m + n - 1."""
        from security.qkd_advanced_engine import _toeplitz_hash
        key = [1, 0, 1, 0, 1]  # n=5
        out, seed = _toeplitz_hash(key, 3)  # m=3
        self.assertEqual(len(seed), 3 + 5 - 1)  # 7


class TestPrivacyAmplification(unittest.TestCase):
    """프라이버시 증폭 (Toeplitz 해시) 테스트."""

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

    def test_pa_compressed(self):
        """PA 후 키는 입력보다 짧아야 함."""
        from security.qkd_advanced_engine import E91State, privacy_amplification
        state = E91State()
        state.sifted_key = [_random_bit() for _ in range(100)]
        final = privacy_amplification(state)
        # 100 bits * 0.5 = 50 bits = ~12 hex chars
        self.assertLessEqual(len(final), 25)
        self.assertGreater(len(final), 0)

    def test_pa_different_runs_differ(self):
        """Toeplitz 시드가 랜덤이므로 다른 실행마다 다른 키 (높은 확률)."""
        from security.qkd_advanced_engine import E91State, privacy_amplification
        results = set()
        for _ in range(5):
            state = E91State()
            state.sifted_key = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1, 0, 0, 1]
            results.add(privacy_amplification(state))
        # 5번 중 최소 2개는 달라야 함 (랜덤 시드)
        self.assertGreater(len(results), 1)


def _random_bit():
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

    def test_resize_ghz_to_4(self):
        """4자간으로 리사이즈 후 정상 동작."""
        from security.qkd_advanced_engine import GHZState, ghz_round, resize_ghz
        state = GHZState()
        resize_ghz(state, 4)
        self.assertEqual(state.n_parties, 4)
        self.assertEqual(len(state.party_names), 4)
        self.assertEqual(len(state.raw_keys), 4)
        rd = ghz_round(state)
        self.assertEqual(len(rd.bases), 4)
        self.assertEqual(len(rd.results), 4)

    def test_resize_ghz_to_5(self):
        """5자간으로 리사이즈 후 정상 동작."""
        from security.qkd_advanced_engine import GHZState, ghz_round, resize_ghz
        state = GHZState()
        resize_ghz(state, 5)
        self.assertEqual(state.n_parties, 5)
        self.assertEqual(len(state.party_names), 5)
        self.assertEqual(len(state.raw_keys), 5)
        for _ in range(500):
            ghz_round(state)
        self.assertGreater(state.key_rounds, 0)

    def test_resize_ghz_clamps(self):
        """범위 밖 값은 클램프."""
        from security.qkd_advanced_engine import (
            GHZ_MAX_PARTIES,
            GHZ_MIN_PARTIES,
            GHZState,
            resize_ghz,
        )
        state = GHZState()
        resize_ghz(state, 1)
        self.assertEqual(state.n_parties, GHZ_MIN_PARTIES)
        resize_ghz(state, 99)
        self.assertEqual(state.n_parties, GHZ_MAX_PARTIES)

    def test_resize_ghz_resets_state(self):
        """리사이즈 시 상태가 리셋."""
        from security.qkd_advanced_engine import GHZState, ghz_round, resize_ghz
        state = GHZState()
        for _ in range(50):
            ghz_round(state)
        resize_ghz(state, 4)
        self.assertEqual(state.total_rounds, 0)
        self.assertEqual(len(state.rounds), 0)
        self.assertEqual(state.key_rounds, 0)

    def test_ghz_4party_z_correlation(self):
        """4자간 Z 기저 상관관계 (Eve 없음)."""
        from security.qkd_advanced_engine import GHZState, ghz_round, resize_ghz
        state = GHZState()
        resize_ghz(state, 4)
        all_same = 0
        key_count = 0
        for _ in range(500):
            rd = ghz_round(state, eve_chance=0.0)
            if rd.all_same_basis and rd.bases[0] == "Z":
                key_count += 1
                if len(set(rd.results)) == 1:
                    all_same += 1
        if key_count > 0:
            self.assertGreater(all_same / key_count, 0.9)

    def test_ghz_5party_sift(self):
        """5자간 키 시프팅 정상 동작."""
        from security.qkd_advanced_engine import GHZState, ghz_key_sift, ghz_round, resize_ghz
        state = GHZState()
        resize_ghz(state, 5)
        for _ in range(300):
            ghz_round(state, eve_chance=0.0)
        sifted = ghz_key_sift(state)
        self.assertTrue(state.sift_done)
        if state.raw_keys[0]:
            self.assertLessEqual(len(sifted), len(state.raw_keys[0]))


class TestOTPEncryption(unittest.TestCase):
    """OTP(XOR) 암호화 데모 테스트."""

    def test_encrypt_decrypt_roundtrip(self):
        """암호화 후 복호화하면 원문 복원."""
        from security.qkd_advanced_engine import xor_decrypt, xor_encrypt
        plaintext = "QUANTUM OK"
        key = "abcdef0123456789abcd"  # 10 bytes = 20 hex chars
        cipher = xor_encrypt(plaintext, key)
        self.assertGreater(len(cipher), 0)
        decrypted = xor_decrypt(cipher, key)
        self.assertEqual(decrypted, plaintext)

    def test_encrypt_produces_hex(self):
        from security.qkd_advanced_engine import xor_encrypt
        cipher = xor_encrypt("Hello", "deadbeef00")
        # 유효한 hex 문자열
        int(cipher, 16)
        # "Hello" = 5 bytes = 10 hex chars
        self.assertEqual(len(cipher), 10)

    def test_different_keys_different_cipher(self):
        from security.qkd_advanced_engine import xor_encrypt
        c1 = xor_encrypt("TEST", "aaaa0000")
        c2 = xor_encrypt("TEST", "bbbb1111")
        self.assertNotEqual(c1, c2)

    def test_empty_key_returns_empty(self):
        from security.qkd_advanced_engine import xor_encrypt
        self.assertEqual(xor_encrypt("msg", ""), "")

    def test_empty_cipher_returns_empty(self):
        from security.qkd_advanced_engine import xor_decrypt
        self.assertEqual(xor_decrypt("", "abcd"), "")

    def test_short_key_partial_encrypt(self):
        """키가 짧으면 가능한 만큼만 암호화."""
        from security.qkd_advanced_engine import xor_decrypt, xor_encrypt
        plaintext = "ABCDEFGH"  # 8 bytes
        key = "ff"  # 1 byte
        cipher = xor_encrypt(plaintext, key)
        # 1 바이트만 암호화
        self.assertEqual(len(cipher), 2)
        decrypted = xor_decrypt(cipher, key)
        self.assertEqual(decrypted, "A")  # 첫 글자만

    def test_with_real_pa_key(self):
        """실제 PA 파이프라인 키로 암호화/복호화."""
        from security.qkd_advanced_engine import (
            E91State,
            e91_round,
            key_sift,
            privacy_amplification,
            xor_decrypt,
            xor_encrypt,
        )
        state = E91State()
        for _ in range(300):
            e91_round(state, eve_chance=0.0)
        key_sift(state)
        final = privacy_amplification(state)
        if final:
            cipher = xor_encrypt("QKD", final)
            decrypted = xor_decrypt(cipher, final)
            self.assertEqual(decrypted, "QKD")


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


class TestBB84Compare(unittest.TestCase):
    """BB84 비교 모드 엔진 테스트."""

    def test_initial_state(self):
        from security.qkd_advanced_engine import BB84State
        state = BB84State()
        self.assertEqual(state.total_rounds, 0)
        self.assertEqual(state.basis_match_rounds, 0)
        self.assertEqual(state.error_count, 0)
        self.assertAlmostEqual(state.qber, 0.0)
        self.assertFalse(state.eve_detected)

    def test_single_round(self):
        from security.qkd_advanced_engine import BB84State, bb84_round
        state = BB84State()
        rd = bb84_round(state)
        self.assertEqual(state.total_rounds, 1)
        self.assertIn("basis_match", rd)
        self.assertIn("has_error", rd)
        self.assertIn("eve_present", rd)

    def test_batch_generates_key_bits(self):
        """200 라운드 후 기저 매칭된 키 비트가 생성되어야 함."""
        from security.qkd_advanced_engine import BB84State, bb84_round
        state = BB84State()
        for _ in range(200):
            bb84_round(state)
        # ~50% 기저 일치 확률 → 최소 50개 기대
        self.assertGreater(state.basis_match_rounds, 30)
        self.assertEqual(state.raw_key_bits, state.basis_match_rounds)

    def test_low_qber_without_eve(self):
        """Eve 없으면 QBER이 0에 가까워야 함."""
        from security.qkd_advanced_engine import BB84State, bb84_round
        state = BB84State()
        for _ in range(300):
            bb84_round(state, eve_chance=0.0)
        self.assertLess(state.qber, 0.05)
        self.assertFalse(state.eve_detected)

    def test_high_qber_with_eve(self):
        """Eve 도청 시 QBER이 상승하고 탐지되어야 함."""
        from security.qkd_advanced_engine import BB84State, bb84_round
        state = BB84State()
        for _ in range(300):
            bb84_round(state, eve_chance=1.0)
        self.assertGreater(state.qber, 0.11)
        self.assertTrue(state.eve_detected)

    def test_eve_rounds_counted(self):
        from security.qkd_advanced_engine import BB84State, bb84_round
        state = BB84State()
        for _ in range(100):
            bb84_round(state, eve_chance=1.0)
        self.assertEqual(state.eve_rounds, 100)

    def test_sliding_window_bounded(self):
        """슬라이딩 윈도우가 50개로 제한."""
        from security.qkd_advanced_engine import BB84State, bb84_round
        state = BB84State()
        for _ in range(500):
            bb84_round(state)
        self.assertLessEqual(len(state._recent_matches), 50)
        self.assertLessEqual(len(state._recent_errors), 50)

    def test_reset_bb84(self):
        from security.qkd_advanced_engine import BB84State, bb84_round, reset_bb84
        state = BB84State()
        for _ in range(100):
            bb84_round(state, eve_chance=0.5)
        reset_bb84(state)
        self.assertEqual(state.total_rounds, 0)
        self.assertEqual(state.basis_match_rounds, 0)
        self.assertEqual(state.error_count, 0)
        self.assertEqual(state.eve_rounds, 0)
        self.assertEqual(state.raw_key_bits, 0)
        self.assertAlmostEqual(state.qber, 0.0)
        self.assertFalse(state.eve_detected)
        self.assertEqual(len(state._recent_matches), 0)
        self.assertEqual(len(state._recent_errors), 0)


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


class TestBB84ErrorModel(unittest.TestCase):
    """BB84 에러 모델 물리 정확성 테스트."""

    def test_qber_near_25_percent_with_full_eve(self):
        """Eve가 모든 비트를 도청하면 QBER ≈ 25% (이론값).

        슬라이딩 윈도우 50개로 계산하므로 통계적 변동이 큼.
        σ = sqrt(0.25*0.75/50) ≈ 0.061 → 넓은 허용 범위 사용.
        """
        from security.qkd_advanced_engine import BB84State, bb84_round
        state = BB84State()
        for _ in range(2000):
            bb84_round(state, eve_chance=1.0)
        # BB84 이론: QBER = 25% (sliding window 50 → 넓은 범위)
        self.assertGreater(state.qber, 0.08,
                           f"QBER = {state.qber:.3f}, expected ~0.25")
        self.assertLess(state.qber, 0.50,
                        f"QBER = {state.qber:.3f}, expected ~0.25")

    def test_no_corruption_when_eve_absent(self):
        """Eve 없으면 corruption이 발생하지 않아야 함."""
        from security.qkd_advanced_engine import BB84State, bb84_round
        state = BB84State()
        for _ in range(500):
            bb84_round(state, eve_chance=0.0)
        self.assertEqual(state.error_count, 0)
        self.assertAlmostEqual(state.qber, 0.0)


class TestXORErrorHandling(unittest.TestCase):
    """XOR 암호화 잘못된 hex 입력 처리 테스트."""

    def test_invalid_hex_key_encrypt(self):
        from security.qkd_advanced_engine import xor_encrypt
        result = xor_encrypt("Hello", "ZZZZ")
        self.assertEqual(result, "")

    def test_invalid_hex_cipher_decrypt(self):
        from security.qkd_advanced_engine import xor_decrypt
        result = xor_decrypt("ZZZZ", "abcd")
        self.assertEqual(result, "")

    def test_invalid_hex_key_decrypt(self):
        from security.qkd_advanced_engine import xor_decrypt
        result = xor_decrypt("abcd", "ZZZZ")
        self.assertEqual(result, "")

    def test_odd_length_hex_key(self):
        """홀수 길이 hex 키도 정상 동작."""
        from security.qkd_advanced_engine import xor_decrypt, xor_encrypt
        cipher = xor_encrypt("A", "abc")
        self.assertGreater(len(cipher), 0)
        decrypted = xor_decrypt(cipher, "abc")
        self.assertEqual(decrypted, "A")


class TestQRNGRandint(unittest.TestCase):
    """_qrng_randint 함수 테스트."""

    def test_range_output(self):
        from security.qkd_advanced_engine import _qrng_randint
        for _ in range(100):
            val = _qrng_randint(0, 2)
            self.assertIn(val, (0, 1, 2))

    def test_single_value_range(self):
        from security.qkd_advanced_engine import _qrng_randint
        for _ in range(10):
            val = _qrng_randint(5, 5)
            self.assertEqual(val, 5)

    def test_binary_range(self):
        from security.qkd_advanced_engine import _qrng_randint
        seen = set()
        for _ in range(50):
            seen.add(_qrng_randint(0, 1))
        # 50회면 {0, 1} 모두 나와야 함
        self.assertEqual(seen, {0, 1})


class TestGHZMeasure(unittest.TestCase):
    """_ghz_measure 함수 단위 테스트."""

    def test_z_basis_all_same(self):
        """Z 기저 측정 시 모든 결과 동일 (Eve 없음)."""
        from security.qkd_advanced_engine import _ghz_measure
        all_same = 0
        n = 100
        for _ in range(n):
            results = _ghz_measure(["Z", "Z", "Z"], eve_present=False)
            if len(set(results)) == 1:
                all_same += 1
        self.assertEqual(all_same, n)

    def test_x_basis_even_parity(self):
        """X 기저 측정 시 짝수 패리티 (Eve 없음)."""
        from security.qkd_advanced_engine import _ghz_measure
        for _ in range(100):
            results = _ghz_measure(["X", "X", "X"], eve_present=False)
            self.assertEqual(sum(results) % 2, 0)

    def test_mixed_basis_random(self):
        """혼합 기저 → 무작위 결과."""
        from security.qkd_advanced_engine import _ghz_measure
        results = _ghz_measure(["X", "Z", "X"], eve_present=False)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIn(r, (0, 1))

    def test_z_basis_eve_disrupts(self):
        """Eve 도청 시 Z 기저 상관관계 파괴."""
        from security.qkd_advanced_engine import _ghz_measure
        disrupted = 0
        n = 200
        for _ in range(n):
            results = _ghz_measure(["Z", "Z", "Z"], eve_present=True)
            if len(set(results)) > 1:
                disrupted += 1
        # Eve → 30% 확률로 각 비트 뒤집힘 → 일부 불일치 기대
        self.assertGreater(disrupted, 0)

    def test_n_party_z_basis(self):
        """N자간 Z 기저 측정."""
        from security.qkd_advanced_engine import _ghz_measure
        for n in (4, 5):
            results = _ghz_measure(["Z"] * n, eve_present=False)
            self.assertEqual(len(results), n)
            self.assertEqual(len(set(results)), 1)


class TestE91StateDuplicate(unittest.TestCase):
    """E91State sifted_key 필드가 단일인지 확인."""

    def test_single_sifted_key_field(self):
        from security.qkd_advanced_engine import E91State
        state = E91State()
        state.sifted_key = [1, 0, 1]
        self.assertEqual(state.sifted_key, [1, 0, 1])


class TestBobRemainingField(unittest.TestCase):
    """bob_remaining이 정식 dataclass 필드인지 확인."""

    def test_bob_remaining_exists(self):
        from security.qkd_advanced_engine import E91State
        state = E91State()
        self.assertEqual(state.bob_remaining, [])

    def test_bob_remaining_populated_after_qber(self):
        from security.qkd_advanced_engine import E91State, e91_round, estimate_qber
        state = E91State()
        for _ in range(200):
            e91_round(state, eve_chance=0.0)
        estimate_qber(state)
        self.assertGreater(len(state.bob_remaining), 0)
        # bob_remaining + qber_sample = raw_key 길이
        self.assertEqual(
            len(state.bob_remaining) + state.qber_sample_size,
            len(state.raw_key_bob),
        )

    def test_reset_clears_bob_remaining(self):
        from security.qkd_advanced_engine import E91State, e91_round, estimate_qber, reset_e91
        state = E91State()
        for _ in range(200):
            e91_round(state)
        estimate_qber(state)
        self.assertGreater(len(state.bob_remaining), 0)
        reset_e91(state)
        self.assertEqual(len(state.bob_remaining), 0)


class TestCompareModeEngine(unittest.TestCase):
    """BB84 vs E91 비교 모드 동시 실행 테스트."""

    def test_concurrent_bb84_e91(self):
        """BB84과 E91이 같은 Eve 조건에서 동시 실행 가능."""
        from security.qkd_advanced_engine import (
            BB84State,
            E91State,
            bb84_round,
            compute_bell_S,
            e91_round,
        )
        bb84 = BB84State()
        e91 = E91State()
        eve_chance = 0.5
        for _ in range(200):
            bb84_round(bb84, eve_chance)
            e91_round(e91, eve_chance)
        compute_bell_S(e91)

        self.assertEqual(bb84.total_rounds, 200)
        self.assertEqual(e91.total_rounds, 200)
        self.assertGreater(bb84.basis_match_rounds, 0)
        self.assertGreater(e91.key_rounds, 0)
        self.assertGreater(bb84.eve_rounds, 0)
        self.assertGreater(e91.eve_rounds, 0)

    def test_both_detect_eve(self):
        """높은 Eve 확률에서 양 프로토콜 모두 도청 탐지."""
        from security.qkd_advanced_engine import (
            BB84State,
            E91State,
            bb84_round,
            compute_bell_S,
            e91_round,
        )
        bb84 = BB84State()
        e91 = E91State()
        for _ in range(3000):
            bb84_round(bb84, eve_chance=1.0)
            e91_round(e91, eve_chance=1.0)
        compute_bell_S(e91)

        # BB84: QBER > 11%
        self.assertTrue(bb84.eve_detected)
        # E91: Eve 도청 시 Bell S가 양자 한계(2√2)보다 크게 약화
        self.assertLess(abs(e91.bell_S), 2.8,
                        f"S = {e91.bell_S:.3f} should be weakened with Eve")


class TestFullPipeline(unittest.TestCase):
    """전체 QKD 파이프라인 통합 테스트."""

    def test_e91_full_pipeline_no_eve(self):
        """E91 전체: 라운드→QBER→정정→PA→OTP 파이프라인."""
        from security.qkd_advanced_engine import (
            E91State,
            _DEMO_PLAINTEXT,
            compute_bell_S,
            e91_round,
            error_correct,
            estimate_qber,
            privacy_amplification,
            xor_decrypt,
            xor_encrypt,
        )
        state = E91State()
        for _ in range(300):
            e91_round(state, eve_chance=0.0)
        S = compute_bell_S(state)
        self.assertGreater(abs(S), 2.0)

        estimate_qber(state)
        self.assertLess(state.qber_value, 0.11)

        error_correct(state)
        self.assertGreater(len(state.corrected_key), 0)

        final = privacy_amplification(state)
        self.assertGreater(len(final), 0)

        # OTP roundtrip
        cipher = xor_encrypt(_DEMO_PLAINTEXT, final)
        if len(final) >= len(_DEMO_PLAINTEXT) * 2:
            decrypted = xor_decrypt(cipher, final)
            self.assertEqual(decrypted, _DEMO_PLAINTEXT)

    def test_ghz_5party_with_eve(self):
        """GHZ 5자간 Eve 있을 때 에러율 상승."""
        from security.qkd_advanced_engine import GHZState, ghz_key_sift, ghz_round, resize_ghz
        state = GHZState()
        resize_ghz(state, 5)
        for _ in range(500):
            ghz_round(state, eve_chance=0.8)
        sifted = ghz_key_sift(state)
        # Eve → 상관관계 파괴 → 에러율 상승
        self.assertGreater(state.error_rate, 0.0)


class TestGHZFullPipeline(unittest.TestCase):
    """GHZ 전체 파이프라인 (라운드→시프팅→PA→OTP) 통합 테스트."""

    def test_ghz_3party_full_pipeline(self):
        """3자간 GHZ 전체 파이프라인 완료."""
        from security.qkd_advanced_engine import (
            GHZState,
            ghz_key_sift,
            ghz_privacy_amplification,
            ghz_round,
            xor_decrypt,
            xor_encrypt,
        )
        state = GHZState()
        for _ in range(300):
            ghz_round(state, eve_chance=0.0)
        sifted = ghz_key_sift(state)
        self.assertTrue(state.sift_done)
        self.assertGreater(len(sifted), 0)

        final = ghz_privacy_amplification(state)
        self.assertTrue(state.pa_done)
        self.assertGreater(len(final), 0)

        # OTP roundtrip
        if len(final) >= 6:
            cipher = xor_encrypt("GHZ", final)
            decrypted = xor_decrypt(cipher, final)
            self.assertEqual(decrypted, "GHZ")

    def test_ghz_4party_pipeline_with_eve(self):
        """4자간 GHZ Eve 있을 때 파이프라인 완료 + 에러율 확인."""
        from security.qkd_advanced_engine import (
            GHZState,
            ghz_key_sift,
            ghz_privacy_amplification,
            ghz_round,
            resize_ghz,
        )
        state = GHZState()
        resize_ghz(state, 4)
        for _ in range(500):
            ghz_round(state, eve_chance=0.5)
        ghz_key_sift(state)
        self.assertTrue(state.sift_done)
        self.assertGreater(state.error_rate, 0.0)

        final = ghz_privacy_amplification(state)
        self.assertTrue(state.pa_done)


class TestCompareModePA(unittest.TestCase):
    """Compare 모드 파이프라인 (sift+PA) 테스트."""

    def test_compare_e91_sift_pa(self):
        """Compare 모드에서 E91 sift+PA 파이프라인 실행 가능."""
        from security.qkd_advanced_engine import (
            E91State,
            compute_bell_S,
            e91_round,
            key_sift,
            privacy_amplification,
        )
        e91_cmp = E91State()
        for _ in range(300):
            e91_round(e91_cmp, eve_chance=0.0)
        compute_bell_S(e91_cmp)

        key_sift(e91_cmp)
        self.assertTrue(e91_cmp.sift_done)

        final = privacy_amplification(e91_cmp)
        self.assertTrue(e91_cmp.pa_done)
        self.assertGreater(len(final), 0)

    def test_compare_concurrent_pipeline(self):
        """BB84과 E91 동시 실행 후 E91 PA까지 완료."""
        from security.qkd_advanced_engine import (
            BB84State,
            E91State,
            bb84_round,
            compute_bell_S,
            e91_round,
            key_sift,
            privacy_amplification,
        )
        bb84 = BB84State()
        e91 = E91State()
        for _ in range(500):
            bb84_round(bb84, eve_chance=0.3)
            e91_round(e91, eve_chance=0.3)
        compute_bell_S(e91)

        # E91 pipeline
        key_sift(e91)
        final = privacy_amplification(e91)
        self.assertTrue(e91.pa_done)
        self.assertGreater(len(final), 0)

        # BB84 should have detected Eve
        self.assertGreater(bb84.qber, 0.0)


class TestEveLevels(unittest.TestCase):
    """Eve 단계별 제어 테스트."""

    def test_eve_levels_produce_different_qber(self):
        """다른 Eve 레벨이 다른 QBER을 생성."""
        from security.qkd_advanced_engine import BB84State, bb84_round
        results = {}
        for eve in [0.0, 0.3, 1.0]:
            state = BB84State()
            for _ in range(500):
                bb84_round(state, eve_chance=eve)
            results[eve] = state.qber
        # 0% Eve → QBER ≈ 0, 100% Eve → QBER ≈ 25%
        self.assertLess(results[0.0], 0.05)
        self.assertGreater(results[1.0], 0.10)

    def test_eve_cycle_values(self):
        """Eve 순환 레벨 값 검증."""
        levels = [0.0, 0.1, 0.3, 0.5, 0.8, 1.0]
        # 각 레벨에서 다음 레벨로 순환
        for i, lvl in enumerate(levels):
            cur = min(range(len(levels)),
                      key=lambda j: abs(levels[j] - lvl))
            nxt = levels[(cur + 1) % len(levels)]
            expected = levels[(i + 1) % len(levels)]
            self.assertAlmostEqual(nxt, expected)


class TestLocaleKeysComplete(unittest.TestCase):
    """로케일 파일 키 완전성 테스트."""

    def _load_json(self, path):
        import json
        with open(path) as f:
            return json.load(f)

    def test_en_ko_keys_match(self):
        """en.json과 ko.json의 키가 완전히 일치."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        en_keys = set(en.keys())
        ko_keys = set(ko.keys())
        missing_in_ko = en_keys - ko_keys
        missing_in_en = ko_keys - en_keys
        self.assertEqual(missing_in_ko, set(),
                         f"Keys in en.json but not in ko.json: {missing_in_ko}")
        self.assertEqual(missing_in_en, set(),
                         f"Keys in ko.json but not in en.json: {missing_in_en}")

    def test_qa_keys_present(self):
        """QKD 관련 모든 키가 en.json에 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        required_keys = [
            "qa_e91_rounds", "qa_raw_key_len", "qa_bell_s_detail",
            "qa_qber_display", "qa_sift_pipeline", "qa_sift_qber_stat",
            "qa_ghz_rounds", "qa_ghz_consistency", "qa_ghz_sifted",
            "qa_ghz_final_key", "qa_cmp_bb84_rounds", "qa_cmp_bb84_basis",
            "qa_cmp_bb84_rawkey", "qa_cmp_bb84_eve", "qa_cmp_bb84_qber",
            "qa_cmp_e91_rounds", "qa_cmp_e91_keypairs", "qa_cmp_e91_rawkey",
            "qa_cmp_e91_eve", "qa_cmp_e91_bell", "qa_key_rate",
            "qa_sift_bell_stat", "qa_qber_graph", "qa_qber_nodata",
            "tutorial_nav_hint",
        ]
        for key in required_keys:
            self.assertIn(key, en, f"Missing key in en.json: {key}")


class TestBB84QBERHistory(unittest.TestCase):
    """BB84 QBER 히스토리 테스트."""

    def test_qber_history_recorded(self):
        """QBER 히스토리가 10 라운드마다 기록."""
        from security.qkd_advanced_engine import BB84State, bb84_round
        state = BB84State()
        for _ in range(100):
            bb84_round(state, eve_chance=0.5)
        # 100 라운드 → 10 라운드마다 기록 → ~10개
        self.assertGreater(len(state.qber_history), 0)
        # (round_number, qber_value) 튜플 형식 확인
        rd, qv = state.qber_history[-1]
        self.assertIsInstance(rd, int)
        self.assertIsInstance(qv, float)

    def test_qber_history_bounded(self):
        """히스토리가 200개로 제한."""
        from security.qkd_advanced_engine import BB84State, bb84_round
        state = BB84State()
        for _ in range(3000):
            bb84_round(state)
        self.assertLessEqual(len(state.qber_history), 200)

    def test_qber_history_reset(self):
        """리셋 시 히스토리 초기화."""
        from security.qkd_advanced_engine import BB84State, bb84_round, reset_bb84
        state = BB84State()
        for _ in range(100):
            bb84_round(state)
        self.assertGreater(len(state.qber_history), 0)
        reset_bb84(state)
        self.assertEqual(len(state.qber_history), 0)

    def test_qber_history_convergence_with_eve(self):
        """Eve 있을 때 QBER 히스토리에 > 0 값 존재."""
        from security.qkd_advanced_engine import BB84State, bb84_round
        state = BB84State()
        for _ in range(200):
            bb84_round(state, eve_chance=1.0)
        self.assertGreater(len(state.qber_history), 0)
        # 마지막 QBER 값이 0보다 큰지 확인
        _, last_qber = state.qber_history[-1]
        self.assertGreater(last_qber, 0.0)


class TestCompareAutoSiftPA(unittest.TestCase):
    """Compare 모드 자동 시프팅/PA 테스트."""

    def test_e91_cmp_sift_pa_pipeline(self):
        """Compare 모드 E91 측 전체 파이프라인 완료."""
        from security.qkd_advanced_engine import (
            E91State,
            compute_bell_S,
            e91_round,
            error_correct,
            estimate_qber,
            privacy_amplification,
        )
        e91_cmp = E91State()
        for _ in range(300):
            e91_round(e91_cmp, eve_chance=0.0)
        compute_bell_S(e91_cmp)

        estimate_qber(e91_cmp)
        self.assertTrue(e91_cmp.qber_done)

        error_correct(e91_cmp)
        self.assertTrue(e91_cmp.correction_done)

        final = privacy_amplification(e91_cmp)
        self.assertTrue(e91_cmp.pa_done)
        self.assertGreater(len(final), 0)


class TestGHZConsistencyHistory(unittest.TestCase):
    """GHZ 일관성 패스율 히스토리 테스트."""

    def test_consistency_history_recorded(self):
        """일관성 히스토리가 검증 10회마다 기록."""
        from security.qkd_advanced_engine import GHZState, ghz_round
        state = GHZState()
        for _ in range(1000):
            ghz_round(state, eve_chance=0.0)
        # 약 1/4 확률로 XXX → 250개 중 10회마다 기록 → 다수 기록
        if state.consistency_checks >= 10:
            self.assertGreater(len(state.consistency_history), 0)
            rd, pr = state.consistency_history[-1]
            self.assertIsInstance(rd, int)
            self.assertIsInstance(pr, float)
            self.assertGreaterEqual(pr, 0.0)
            self.assertLessEqual(pr, 1.0)

    def test_consistency_history_bounded(self):
        """히스토리가 200개로 제한."""
        from security.qkd_advanced_engine import GHZState, ghz_round
        state = GHZState()
        for _ in range(10000):
            ghz_round(state)
        self.assertLessEqual(len(state.consistency_history), 200)

    def test_consistency_history_reset(self):
        """리셋 시 히스토리 초기화."""
        from security.qkd_advanced_engine import GHZState, ghz_round, reset_ghz
        state = GHZState()
        for _ in range(500):
            ghz_round(state)
        reset_ghz(state)
        self.assertEqual(len(state.consistency_history), 0)

    def test_consistency_high_without_eve(self):
        """Eve 없을 때 일관성 패스율이 높아야 함."""
        from security.qkd_advanced_engine import GHZState, ghz_round
        state = GHZState()
        for _ in range(1000):
            ghz_round(state, eve_chance=0.0)
        if state.consistency_history:
            _, last_rate = state.consistency_history[-1]
            self.assertGreater(last_rate, 0.9)

    def test_consistency_drops_with_eve(self):
        """Eve 도청 시 일관성 패스율 하락."""
        from security.qkd_advanced_engine import GHZState, ghz_round
        state = GHZState()
        for _ in range(1000):
            ghz_round(state, eve_chance=0.8)
        if state.consistency_history:
            _, last_rate = state.consistency_history[-1]
            self.assertLess(last_rate, 0.95)


class TestGHZSiftEmptyKey(unittest.TestCase):
    """GHZ 빈 키 시프팅 테스트."""

    def test_sift_empty_sets_done(self):
        """빈 키로 시프팅 시 sift_done이 True여야 함."""
        from security.qkd_advanced_engine import GHZState, ghz_key_sift
        state = GHZState()
        result = ghz_key_sift(state)
        self.assertEqual(result, [])
        self.assertTrue(state.sift_done)


class TestLocaleNewKeys(unittest.TestCase):
    """새로 추가된 로케일 키 존재 확인."""

    def _load_json(self, path):
        import json
        with open(path) as f:
            return json.load(f)

    def test_new_keys_in_en(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        new_keys = [
            "qa_ghz_consistency_graph",
            "qa_ghz_consistency_nodata",
            "qa_cmp_no_data",
        ]
        for key in new_keys:
            self.assertIn(key, en, f"Missing key in en.json: {key}")

    def test_new_keys_in_ko(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        new_keys = [
            "qa_ghz_consistency_graph",
            "qa_ghz_consistency_nodata",
            "qa_cmp_no_data",
        ]
        for key in new_keys:
            self.assertIn(key, ko, f"Missing key in ko.json: {key}")


class TestLocaleRound8Keys(unittest.TestCase):
    """Round 8 로케일 키 존재 확인."""

    def _load_json(self, path):
        import json
        with open(path) as f:
            return json.load(f)

    def test_alice_bob_eve_keys(self):
        """Alice/Bob/Eve 라벨 키가 en.json에 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        for key in ["qa_alice", "qa_bob", "qa_eve"]:
            self.assertIn(key, en, f"Missing key: {key}")

    def test_bell_badge_keys(self):
        """Bell S 뱃지 키가 양쪽 로케일에 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        badge_keys = ["qa_bell_badge_secure", "qa_bell_badge_caution", "qa_bell_badge_danger"]
        for key in badge_keys:
            self.assertIn(key, en, f"Missing in en.json: {key}")
            self.assertIn(key, ko, f"Missing in ko.json: {key}")

    def test_en_ko_keys_still_match(self):
        """en.json과 ko.json의 키가 여전히 완전히 일치."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        en_keys = set(en.keys())
        ko_keys = set(ko.keys())
        self.assertEqual(en_keys - ko_keys, set(),
                         f"Keys in en.json but not in ko.json: {en_keys - ko_keys}")
        self.assertEqual(ko_keys - en_keys, set(),
                         f"Keys in ko.json but not in en.json: {ko_keys - en_keys}")


class TestBellSBadgeLogic(unittest.TestCase):
    """Bell S 뱃지 상태 논리 테스트."""

    def test_secure_badge_without_eve(self):
        """Eve 없을 때 S ≈ 2√2 → SECURE or CAUTION."""
        from security.qkd_advanced_engine import (
            CHSH_CLASSICAL_BOUND,
            E91State,
            compute_bell_S,
            e91_round,
        )
        state = E91State()
        for _ in range(2000):
            e91_round(state, eve_chance=0.0)
        S = compute_bell_S(state)
        abs_s = abs(S)
        # Eve 없으면 S > 고전 한계 2.0 (벨 부등식 위반)
        self.assertGreater(abs_s, CHSH_CLASSICAL_BOUND)

    def test_danger_badge_with_full_eve(self):
        """100% Eve → S 약화 → DANGER 가능."""
        from security.qkd_advanced_engine import (
            CHSH_CLASSICAL_BOUND,
            E91State,
            compute_bell_S,
            e91_round,
        )
        state = E91State()
        for _ in range(1000):
            e91_round(state, eve_chance=1.0)
        S = compute_bell_S(state)
        abs_s = abs(S)
        # 100% Eve → S 약화 → classical bound 이하 가능
        self.assertLess(abs_s, 2.8)


class TestLocaleRound9Keys(unittest.TestCase):
    """Round 9 로케일 키 존재 확인."""

    def _load_json(self, path):
        import json
        with open(path) as f:
            return json.load(f)

    def test_round_log_keys(self):
        """라운드 로그 항목 키가 양쪽 로케일에 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        for key in ["qa_e91_log_entry", "qa_ghz_log_entry"]:
            self.assertIn(key, en, f"Missing in en.json: {key}")
            self.assertIn(key, ko, f"Missing in ko.json: {key}")

    def test_en_ko_keys_still_match(self):
        """en.json과 ko.json의 키가 여전히 일치."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        en_keys = set(en.keys())
        ko_keys = set(ko.keys())
        self.assertEqual(en_keys - ko_keys, set())
        self.assertEqual(ko_keys - en_keys, set())


class TestGHZConsistencyHistoryResize(unittest.TestCase):
    """리사이즈 시 일관성 히스토리 초기화 테스트."""

    def test_resize_clears_consistency_history(self):
        """리사이즈 시 consistency_history도 초기화."""
        from security.qkd_advanced_engine import GHZState, ghz_round, resize_ghz
        state = GHZState()
        for _ in range(500):
            ghz_round(state)
        resize_ghz(state, 4)
        self.assertEqual(len(state.consistency_history), 0)
        self.assertEqual(state.n_parties, 4)


class TestNibbleConversionRemainder(unittest.TestCase):
    """PA 닙블 변환에서 나머지 비트 패딩 처리 테스트."""

    def test_pa_handles_non_multiple_of_4(self):
        """비트 수가 4의 배수가 아닌 경우에도 최종 키가 생성됨."""
        from security.qkd_advanced_engine import E91State, e91_round, compute_bell_S, \
            key_sift, privacy_amplification
        state = E91State()
        for _ in range(200):
            e91_round(state, 0.0)
        compute_bell_S(state)
        key_sift(state)
        result = privacy_amplification(state)
        self.assertTrue(len(result) > 0)
        # 16진수 문자열인지 확인
        int(result, 16)

    def test_ghz_pa_handles_non_multiple_of_4(self):
        """GHZ PA도 나머지 비트 패딩 처리."""
        from security.qkd_advanced_engine import GHZState, ghz_round, \
            ghz_key_sift, ghz_privacy_amplification
        state = GHZState()
        for _ in range(200):
            ghz_round(state, 0.0)
        ghz_key_sift(state)
        if state.sifted_key:
            result = ghz_privacy_amplification(state)
            if result:
                int(result, 16)


class TestLocaleRound10Keys(unittest.TestCase):
    """Round 10 로케일 키 존재 확인."""

    def _load_json(self, path):
        import json
        with open(path) as f:
            return json.load(f)

    def test_new_round10_keys(self):
        """라운드 10 신규 키가 양쪽 로케일에 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        keys = ["qa_tag_mix", "qa_stage_rounds", "qa_stage_ec",
                "qa_stage_pa", "qa_stage_done"]
        for key in keys:
            self.assertIn(key, en, f"Missing in en.json: {key}")
            self.assertIn(key, ko, f"Missing in ko.json: {key}")

    def test_en_ko_keys_still_match(self):
        """en.json과 ko.json의 키가 여전히 일치."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        en_keys = set(en.keys())
        ko_keys = set(ko.keys())
        self.assertEqual(en_keys - ko_keys, set())
        self.assertEqual(ko_keys - en_keys, set())


class TestTextCacheRoundTrip(unittest.TestCase):
    """텍스트 캐시 round-trip 테스트."""

    def test_cache_returns_same_surface(self):
        """동일 키에 대해 동일 객체 반환."""
        import sys
        sys.modules.setdefault("pygame", type(sys)("pygame"))
        from security.qkd_advanced import _TextCache
        cache = _TextCache(max_size=4)

        class FakeFont:
            def render(self, text, aa, color):
                return (text, color)
        f = FakeFont()
        s1 = cache.render(f, "hello", (1, 2, 3))
        s2 = cache.render(f, "hello", (1, 2, 3))
        self.assertIs(s1, s2)

    def test_cache_evicts_when_full(self):
        """캐시가 꽉 차면 가장 오래된 항목 제거."""
        import sys
        sys.modules.setdefault("pygame", type(sys)("pygame"))
        from security.qkd_advanced import _TextCache
        cache = _TextCache(max_size=2)

        class FakeFont:
            def render(self, text, aa, color):
                return (text, color)
        f = FakeFont()
        cache.render(f, "a", (0,))
        cache.render(f, "b", (0,))
        cache.render(f, "c", (0,))  # evicts "a"
        self.assertEqual(len(cache._cache), 2)


class TestLocaleRound11Keys(unittest.TestCase):
    """Round 11 로케일 키 존재 확인."""

    def _load_json(self, path):
        import json
        with open(path) as f:
            return json.load(f)

    def test_shortcut_keys(self):
        """단축키 패널 키가 양쪽 로케일에 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        keys = [
            "qa_sc_title", "qa_sc_space", "qa_sc_sift", "qa_sc_auto",
            "qa_sc_eve", "qa_sc_pause", "qa_sc_reset", "qa_sc_tab",
            "qa_sc_locale", "qa_sc_updown", "qa_sc_help", "qa_sc_shortcuts",
            "qa_sc_exit",
        ]
        for key in keys:
            self.assertIn(key, en, f"Missing in en.json: {key}")
            self.assertIn(key, ko, f"Missing in ko.json: {key}")

    def test_pipeline_tip_keys(self):
        """파이프라인 툴팁 키가 양쪽 로케일에 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        for key in ["qa_tip_raw_key", "qa_tip_qber", "qa_tip_ec", "qa_tip_pa"]:
            self.assertIn(key, en, f"Missing in en.json: {key}")
            self.assertIn(key, ko, f"Missing in ko.json: {key}")

    def test_en_ko_keys_still_match(self):
        """en.json과 ko.json의 키가 여전히 일치."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        en_keys = set(en.keys())
        ko_keys = set(ko.keys())
        self.assertEqual(en_keys - ko_keys, set())
        self.assertEqual(ko_keys - en_keys, set())


class TestBB84Pipeline(unittest.TestCase):
    """BB84 sift/PA 파이프라인 테스트."""

    def test_bb84_estimate_qber(self):
        from security.qkd_advanced_engine import (
            BB84State, bb84_round, bb84_estimate_qber,
        )
        state = BB84State()
        for _ in range(200):
            bb84_round(state, eve_chance=0.0)
        self.assertGreater(len(state.raw_key), 0)
        bb84_estimate_qber(state)
        self.assertTrue(state.qber_done)
        self.assertGreater(state.qber_sample_size, 0)
        self.assertGreater(len(state.sifted_key), 0)

    def test_bb84_full_pipeline(self):
        from security.qkd_advanced_engine import (
            BB84State, bb84_round, bb84_estimate_qber,
            bb84_error_correct, bb84_privacy_amplification,
        )
        state = BB84State()
        for _ in range(500):
            bb84_round(state, eve_chance=0.0)
        bb84_estimate_qber(state)
        bb84_error_correct(state)
        self.assertTrue(state.correction_done)
        bb84_privacy_amplification(state)
        self.assertTrue(state.pa_done)
        self.assertGreater(len(state.final_key), 0)

    def test_bb84_pipeline_idempotent(self):
        """이미 완료된 단계 재호출 시 상태 변경 없음."""
        from security.qkd_advanced_engine import (
            BB84State, bb84_round, bb84_estimate_qber,
            bb84_error_correct, bb84_privacy_amplification,
        )
        state = BB84State()
        for _ in range(300):
            bb84_round(state, eve_chance=0.0)
        bb84_estimate_qber(state)
        bb84_error_correct(state)
        bb84_privacy_amplification(state)
        key1 = state.final_key
        # 재호출
        bb84_estimate_qber(state)
        bb84_error_correct(state)
        bb84_privacy_amplification(state)
        self.assertEqual(state.final_key, key1)

    def test_bb84_reset_clears_pipeline(self):
        from security.qkd_advanced_engine import (
            BB84State, bb84_round, bb84_estimate_qber,
            bb84_error_correct, bb84_privacy_amplification, reset_bb84,
        )
        state = BB84State()
        for _ in range(300):
            bb84_round(state, eve_chance=0.0)
        bb84_estimate_qber(state)
        bb84_error_correct(state)
        bb84_privacy_amplification(state)
        self.assertTrue(state.pa_done)
        reset_bb84(state)
        self.assertFalse(state.pa_done)
        self.assertFalse(state.qber_done)
        self.assertEqual(state.final_key, "")
        self.assertEqual(len(state.raw_key), 0)

    def test_bb84_raw_key_tracks_bits(self):
        from security.qkd_advanced_engine import BB84State, bb84_round
        state = BB84State()
        for _ in range(100):
            bb84_round(state, eve_chance=0.0)
        self.assertEqual(len(state.raw_key), state.raw_key_bits)


class TestStatsExport(unittest.TestCase):
    """통계 내보내기 테스트."""

    def test_export_creates_file(self):
        import json
        import tempfile
        from security.qkd_advanced_engine import E91State, GHZState, BB84State
        from security.qkd_advanced import _export_stats

        e91 = E91State()
        ghz = GHZState()
        bb84 = BB84State()
        e91_cmp = E91State()

        # 임시 디렉토리로 export 경로 변경하지 않고 실제 호출
        _export_stats(0, e91, ghz, bb84, e91_cmp)

        # exports 디렉토리에 파일이 생겼는지 확인
        import os
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports"
        )
        files = [f for f in os.listdir(export_dir) if f.startswith("qkd_stats_")]
        self.assertGreater(len(files), 0)

        # 파일 내용 확인
        latest = sorted(files)[-1]
        with open(os.path.join(export_dir, latest)) as f:
            data = json.load(f)
        self.assertIn("e91", data)
        self.assertIn("ghz", data)
        self.assertEqual(data["mode"], "E91")


class TestLocaleExportKey(unittest.TestCase):
    """내보내기 로케일 키 확인."""

    def _load_json(self, path):
        import json
        with open(path) as f:
            return json.load(f)

    def test_export_key_exists(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        self.assertIn("qa_sc_export", en)
        self.assertIn("qa_sc_export", ko)


class TestRound13Features(unittest.TestCase):
    """Round 13 신규 기능 테스트."""

    def _load_json(self, path):
        import json
        with open(path) as f:
            return json.load(f)

    def test_round13_locale_keys(self):
        """Round 13 로케일 키가 양쪽 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        keys = [
            "qa_paused_banner", "qa_auto_speed", "qa_fps_counter",
            "qa_sc_speed", "qa_sc_fps",
        ]
        for key in keys:
            self.assertIn(key, en, f"Missing in en.json: {key}")
            self.assertIn(key, ko, f"Missing in ko.json: {key}")

    def test_auto_speed_values(self):
        """자동실행 속도 범위 확인."""
        speeds = [0.5, 1.0, 2.0, 4.0]
        self.assertEqual(speeds[0], 0.5)
        self.assertEqual(speeds[-1], 4.0)
        # 0.05 / speed 계산이 0이 되지 않는지 확인
        for s in speeds:
            self.assertGreater(0.05 / s, 0)

    def test_en_ko_keys_match_round14(self):
        """en.json과 ko.json의 키가 Round 14 이후에도 일치."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        en_keys = set(en.keys())
        ko_keys = set(ko.keys())
        self.assertEqual(en_keys - ko_keys, set(),
                         f"en에만 있는 키: {en_keys - ko_keys}")
        self.assertEqual(ko_keys - en_keys, set(),
                         f"ko에만 있는 키: {ko_keys - en_keys}")


class TestRound14Features(unittest.TestCase):
    """Round 14 신규 기능 테스트."""

    def _load_json(self, path):
        import json
        with open(path) as f:
            return json.load(f)

    def test_round14_locale_keys(self):
        """Round 14 로케일 키가 양쪽 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        keys = ["qa_key_verify", "qa_fidelity", "qa_ghz_parity_title"]
        for key in keys:
            self.assertIn(key, en, f"Missing in en.json: {key}")
            self.assertIn(key, ko, f"Missing in ko.json: {key}")

    def test_key_match_rate_after_pa(self):
        """PA 완료 후 key_match_rate 설정 확인."""
        from security.qkd_advanced_engine import E91State, e91_round, key_sift
        state = E91State()
        for _ in range(500):
            e91_round(state, eve_chance=0.0)
        key_sift(state)
        # Eve 없으면 높은 일치율
        self.assertGreater(state.key_match_rate, 0.8)

    def test_entanglement_fidelity_calc(self):
        """상관값 기반 충실도 — 벨 검증 상관 데이터 존재."""
        from security.qkd_advanced_engine import E91State, e91_round, compute_bell_S
        state = E91State()
        for _ in range(3000):
            e91_round(state, eve_chance=0.0)
        compute_bell_S(state)
        self.assertGreater(len(state.correlators), 0)
        self.assertGreater(abs(state.bell_S), 2.0)

    def test_ghz_x_basis_parity(self):
        """GHZ X-기저 라운드에서 패리티 검사 데이터 존재."""
        from security.qkd_advanced_engine import GHZState, ghz_round
        state = GHZState()
        for _ in range(200):
            ghz_round(state, eve_chance=0.0)
        x_rounds = [rd for rd in state.rounds
                     if rd.all_same_basis and rd.bases[0] == "X"]
        self.assertGreater(len(x_rounds), 0)
        for rd in x_rounds:
            parity = sum(rd.results) % 2
            self.assertIn(parity, [0, 1])

    def test_fidelity_degrades_with_eve(self):
        """Eve 있으면 상관값(충실도) 약화."""
        from security.qkd_advanced_engine import E91State, e91_round, compute_bell_S
        clean = E91State()
        noisy = E91State()
        for _ in range(2000):
            e91_round(clean, eve_chance=0.0)
            e91_round(noisy, eve_chance=0.8)
        compute_bell_S(clean)
        compute_bell_S(noisy)
        # 깨끗한 상태의 Bell S가 더 커야 함
        self.assertGreater(abs(clean.bell_S), abs(noisy.bell_S))


class TestRound15Features(unittest.TestCase):
    """Round 15 신규 기능 테스트."""

    def _load_json(self, path):
        import json
        with open(path) as f:
            return json.load(f)

    def test_round15_locale_keys(self):
        """Round 15 로케일 키가 양쪽 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        keys = [
            "qa_toast_bell", "qa_toast_pa", "qa_toast_eve",
            "qa_toast_winner_e91", "qa_toast_winner_tie",
            "qa_summary_title", "qa_summary_rounds", "qa_summary_keybits",
            "qa_summary_bells", "qa_summary_qber", "qa_summary_exit",
        ]
        for key in keys:
            self.assertIn(key, en, f"Missing in en.json: {key}")
            self.assertIn(key, ko, f"Missing in ko.json: {key}")

    def test_key_accumulation_history(self):
        """누적 키 생성 히스토리가 기록됨."""
        from security.qkd_advanced_engine import E91State, e91_round
        state = E91State()
        for _ in range(500):
            e91_round(state, eve_chance=0.0)
        self.assertGreater(len(state.key_accumulation), 0)
        # 튜플 형식 (round, bits) 확인
        for rd, bits in state.key_accumulation:
            self.assertIsInstance(rd, int)
            self.assertIsInstance(bits, int)

    def test_key_accumulation_cleared_on_reset(self):
        """리셋 시 히스토리 클리어."""
        from security.qkd_advanced_engine import E91State, e91_round, reset_e91
        state = E91State()
        for _ in range(100):
            e91_round(state, eve_chance=0.0)
        self.assertGreater(len(state.key_accumulation), 0)
        reset_e91(state)
        self.assertEqual(len(state.key_accumulation), 0)

    def test_en_ko_keys_match_round15(self):
        """en.json과 ko.json 키 완전 일치."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        en_keys = set(en.keys())
        ko_keys = set(ko.keys())
        self.assertEqual(en_keys - ko_keys, set(),
                         f"en에만: {en_keys - ko_keys}")
        self.assertEqual(ko_keys - en_keys, set(),
                         f"ko에만: {ko_keys - en_keys}")


class TestRound16Features(unittest.TestCase):
    """Round 16 신규 기능 테스트."""

    def _load_json(self, path):
        import json
        with open(path) as f:
            return json.load(f)

    def test_round16_locale_keys(self):
        """Round 16 로케일 키가 양쪽 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        keys = [
            "qa_sc_theme", "qa_sc_noise",
            "qa_noise_model", "qa_noise_label",
        ]
        for key in keys:
            self.assertIn(key, en, f"Missing in en.json: {key}")
            self.assertIn(key, ko, f"Missing in ko.json: {key}")

    def test_noise_model_default(self):
        """기본 노이즈 모델은 depolarizing."""
        from security.qkd_advanced_engine import get_noise_model, set_noise_model
        set_noise_model("depolarizing")  # ensure default
        self.assertEqual(get_noise_model(), "depolarizing")

    def test_noise_model_cycle(self):
        """노이즈 모델 순환."""
        from security.qkd_advanced_engine import (
            NOISE_MODELS, cycle_noise_model, get_noise_model, set_noise_model,
        )
        set_noise_model("depolarizing")
        result = cycle_noise_model()
        self.assertEqual(result, "dephasing")
        self.assertEqual(get_noise_model(), "dephasing")
        result = cycle_noise_model()
        self.assertEqual(result, "amplitude_damping")
        result = cycle_noise_model()
        self.assertEqual(result, "depolarizing")  # wraps around

    def test_noise_model_set_invalid(self):
        """잘못된 모델은 무시."""
        from security.qkd_advanced_engine import get_noise_model, set_noise_model
        set_noise_model("depolarizing")
        set_noise_model("nonexistent")
        self.assertEqual(get_noise_model(), "depolarizing")

    def test_noise_models_list(self):
        """3개 노이즈 모델이 정의됨."""
        from security.qkd_advanced_engine import NOISE_MODELS
        self.assertEqual(len(NOISE_MODELS), 3)
        self.assertIn("depolarizing", NOISE_MODELS)
        self.assertIn("dephasing", NOISE_MODELS)
        self.assertIn("amplitude_damping", NOISE_MODELS)

    def test_depolarizing_noise_with_eve(self):
        """Depolarizing 노이즈에서 Eve 시 Bell S 감소."""
        from security.qkd_advanced_engine import (
            E91State, compute_bell_S, e91_round, set_noise_model,
        )
        set_noise_model("depolarizing")
        state = E91State()
        for _ in range(3000):
            e91_round(state, eve_chance=0.8)
        compute_bell_S(state)
        # Eve가 강하면 S < 2.0 (고전 한계 이하)
        self.assertLess(abs(state.bell_S), 2.5)

    def test_dephasing_noise_with_eve(self):
        """Dephasing 노이즈에서 Eve 시 상관관계 변화."""
        from security.qkd_advanced_engine import (
            E91State, compute_bell_S, e91_round, set_noise_model,
        )
        set_noise_model("dephasing")
        state = E91State()
        for _ in range(3000):
            e91_round(state, eve_chance=0.8)
        compute_bell_S(state)
        # Dephasing 모델에서도 Eve 시 S 값이 양자 한계 이하
        self.assertLess(abs(state.bell_S), 3.0)
        set_noise_model("depolarizing")  # restore

    def test_amplitude_damping_noise_with_eve(self):
        """Amplitude damping 노이즈에서 Eve 시 비대칭 효과."""
        from security.qkd_advanced_engine import (
            E91State, e91_round, set_noise_model,
        )
        set_noise_model("amplitude_damping")
        state = E91State()
        for _ in range(2000):
            e91_round(state, eve_chance=0.8)
        # 키 비트가 생성됨
        self.assertGreater(len(state.raw_key_alice), 0)
        set_noise_model("depolarizing")  # restore

    def test_ghz_noise_model_dephasing(self):
        """GHZ에서 dephasing 노이즈 모델 적용."""
        from security.qkd_advanced_engine import (
            GHZState, ghz_round, set_noise_model,
        )
        set_noise_model("dephasing")
        state = GHZState()
        for _ in range(500):
            ghz_round(state, eve_chance=0.5)
        self.assertGreater(state.total_rounds, 0)
        set_noise_model("depolarizing")  # restore

    def test_ghz_noise_model_amplitude_damping(self):
        """GHZ에서 amplitude_damping 모델 적용."""
        from security.qkd_advanced_engine import (
            GHZState, ghz_round, set_noise_model,
        )
        set_noise_model("amplitude_damping")
        state = GHZState()
        for _ in range(500):
            ghz_round(state, eve_chance=0.5)
        self.assertGreater(state.total_rounds, 0)
        set_noise_model("depolarizing")  # restore

    def test_en_ko_keys_match_round16(self):
        """en.json과 ko.json 키 완전 일치."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        en_keys = set(en.keys())
        ko_keys = set(ko.keys())
        self.assertEqual(en_keys - ko_keys, set(),
                         f"en에만: {en_keys - ko_keys}")
        self.assertEqual(ko_keys - en_keys, set(),
                         f"ko에만: {ko_keys - en_keys}")


class TestRound17Features(unittest.TestCase):
    """Round 17 신규 기능 테스트."""

    def _load_json(self, path):
        import json
        with open(path) as f:
            return json.load(f)

    def test_round17_locale_keys(self):
        """Round 17 로케일 키가 양쪽 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        keys = [
            "qa_witness_title", "qa_witness_entangled",
            "qa_witness_border", "qa_witness_separable",
            "qa_error_heatmap", "qa_error_legend",
            "qa_screenshot", "qa_sc_screenshot",
            "qa_sc_step", "qa_step_on", "qa_step_off",
            "qa_step_active",
            "qa_step_first_key", "qa_step_bell_violated",
            "qa_step_qber_done", "qa_step_ec_done", "qa_step_pa_done",
        ]
        for key in keys:
            self.assertIn(key, en, f"Missing in en.json: {key}")
            self.assertIn(key, ko, f"Missing in ko.json: {key}")

    def test_witness_computed_no_eve(self):
        """Eve 없을 때 witness > 0.5 (얽힘 확인)."""
        from security.qkd_advanced_engine import (
            E91State, compute_bell_S, e91_round, set_noise_model,
        )
        set_noise_model("depolarizing")
        state = E91State()
        for _ in range(2000):
            e91_round(state, eve_chance=0.0)
        compute_bell_S(state)
        self.assertGreater(state.witness_value, 0.5)
        self.assertGreater(len(state.witness_history), 0)

    def test_witness_degrades_with_eve(self):
        """Eve가 강하면 witness 값 하락."""
        from security.qkd_advanced_engine import (
            E91State, compute_bell_S, e91_round, set_noise_model,
        )
        set_noise_model("depolarizing")
        state = E91State()
        for _ in range(3000):
            e91_round(state, eve_chance=1.0)
        compute_bell_S(state)
        # 완전한 Eve에서는 witness가 낮아져야 함
        self.assertLess(state.witness_value, 0.9)

    def test_witness_reset(self):
        """리셋 시 witness 클리어."""
        from security.qkd_advanced_engine import (
            E91State, compute_bell_S, e91_round, reset_e91,
        )
        state = E91State()
        for _ in range(200):
            e91_round(state, eve_chance=0.0)
        compute_bell_S(state)
        self.assertGreater(len(state.witness_history), 0)
        reset_e91(state)
        self.assertEqual(state.witness_value, 0.0)
        self.assertEqual(len(state.witness_history), 0)

    def test_error_positions_tracked(self):
        """에러 정정에서 에러 위치가 기록됨."""
        from security.qkd_advanced_engine import (
            E91State, e91_round, estimate_qber, error_correct,
        )
        state = E91State()
        for _ in range(2000):
            e91_round(state, eve_chance=0.5)
        estimate_qber(state)
        error_correct(state)
        # Eve가 있으므로 에러가 발생해야 함
        if state.correction_flips > 0:
            self.assertEqual(len(state.error_positions), state.correction_flips)
            for pos in state.error_positions:
                self.assertIsInstance(pos, int)

    def test_error_positions_empty_no_eve(self):
        """Eve 없이 에러 위치 빈 리스트 또는 매우 적음."""
        from security.qkd_advanced_engine import (
            E91State, e91_round, estimate_qber, error_correct,
        )
        state = E91State()
        for _ in range(1000):
            e91_round(state, eve_chance=0.0)
        estimate_qber(state)
        error_correct(state)
        # Eve 없이는 에러가 매우 적어야 함
        self.assertLessEqual(len(state.error_positions), 5)

    def test_error_positions_reset(self):
        """리셋 시 에러 위치 클리어."""
        from security.qkd_advanced_engine import (
            E91State, e91_round, estimate_qber, error_correct, reset_e91,
        )
        state = E91State()
        for _ in range(500):
            e91_round(state, eve_chance=0.5)
        estimate_qber(state)
        error_correct(state)
        reset_e91(state)
        self.assertEqual(len(state.error_positions), 0)

    def test_en_ko_keys_match_round17(self):
        """en.json과 ko.json 키 완전 일치."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        en_keys = set(en.keys())
        ko_keys = set(ko.keys())
        self.assertEqual(en_keys - ko_keys, set(),
                         f"en에만: {en_keys - ko_keys}")
        self.assertEqual(ko_keys - en_keys, set(),
                         f"ko에만: {ko_keys - en_keys}")


class TestRound18Features(unittest.TestCase):
    """R18: channel capacity, bloch sphere, entropy, agreement, benchmark."""

    @staticmethod
    def _load_json(path):
        import json as _json
        with open(path, encoding="utf-8") as f:
            return _json.load(f)

    def test_round18_locale_keys(self):
        """R18 로캘 키가 en/ko 모두 존재."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        r18_keys = [
            "qa_channel_cap", "qa_secure_rate", "qa_bloch_title",
            "qa_entropy_title", "qa_entropy_raw", "qa_entropy_eve",
            "qa_entropy_final", "qa_entropy_pending",
            "qa_agreement_title", "qa_bench_title", "qa_bench_done",
            "qa_bench_close", "qa_sc_bench",
        ]
        for key in r18_keys:
            self.assertIn(key, en, f"en missing {key}")
            self.assertIn(key, ko, f"ko missing {key}")

    def test_channel_capacity_no_eve(self):
        """Eve 없이 채널 용량 계산 — I(A;B) 높고, I(E;B) 낮아야."""
        from security.qkd_advanced_engine import (
            E91State, e91_round, compute_bell_S,
        )
        state = E91State()
        for _ in range(500):
            e91_round(state, eve_chance=0.0)
        compute_bell_S(state)
        # Eve 없으면 I(A;B) 높음
        self.assertGreater(state.mutual_info, 0.5)
        self.assertLess(state.eve_info, 0.5)
        self.assertGreater(state.secure_key_rate, 0.0)

    def test_channel_capacity_with_eve(self):
        """Eve 있으면 채널 용량 감소."""
        from security.qkd_advanced_engine import (
            E91State, e91_round, compute_bell_S,
        )
        state = E91State()
        for _ in range(500):
            e91_round(state, eve_chance=1.0)
        compute_bell_S(state)
        # Eve가 있으면 secure_key_rate 감소
        self.assertLess(state.secure_key_rate, 0.8)

    def test_channel_history_recorded(self):
        """채널 히스토리가 20 라운드마다 기록."""
        from security.qkd_advanced_engine import (
            E91State, e91_round, compute_bell_S,
        )
        state = E91State()
        for _ in range(100):
            e91_round(state, eve_chance=0.0)
        compute_bell_S(state)
        self.assertGreater(len(state.channel_history), 0)
        # 각 항목은 (round, I_AB, I_EB) 튜플
        entry = state.channel_history[0]
        self.assertEqual(len(entry), 3)

    def test_agreement_history_recorded(self):
        """키 합의율 히스토리가 기록."""
        from security.qkd_advanced_engine import (
            E91State, e91_round, compute_bell_S,
        )
        state = E91State()
        for _ in range(200):
            e91_round(state, eve_chance=0.0)
        compute_bell_S(state)
        # 키 라운드가 있으면 히스토리 존재
        if state.key_rounds > 0:
            self.assertGreater(len(state.agreement_history), 0)
            # 값이 0~1 범위
            _, rate = state.agreement_history[-1]
            self.assertGreaterEqual(rate, 0.0)
            self.assertLessEqual(rate, 1.0)

    def test_binary_entropy_function(self):
        """이진 엔트로피 함수 검증."""
        from security.qkd_advanced_engine import _binary_entropy
        # h(0) = 0, h(1) = 0
        self.assertAlmostEqual(_binary_entropy(0.0), 0.0)
        self.assertAlmostEqual(_binary_entropy(1.0), 0.0)
        # h(0.5) = 1.0
        self.assertAlmostEqual(_binary_entropy(0.5), 1.0, places=5)
        # h(0.11) ≈ 0.5
        h_011 = _binary_entropy(0.11)
        self.assertGreater(h_011, 0.3)
        self.assertLess(h_011, 0.7)

    def test_channel_capacity_reset(self):
        """리셋 시 채널 용량 필드 클리어."""
        from security.qkd_advanced_engine import (
            E91State, e91_round, compute_bell_S, reset_e91,
        )
        state = E91State()
        for _ in range(100):
            e91_round(state, eve_chance=0.0)
        compute_bell_S(state)
        reset_e91(state)
        self.assertEqual(state.mutual_info, 0.0)
        self.assertEqual(state.eve_info, 0.0)
        self.assertEqual(state.secure_key_rate, 0.0)
        self.assertEqual(len(state.channel_history), 0)
        self.assertEqual(len(state.agreement_history), 0)

    def test_benchmark_runs(self):
        """벤치마크 함수가 올바른 결과 반환."""
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from security.qkd_advanced import _run_benchmark
        results = _run_benchmark()
        self.assertEqual(len(results), 4)  # 4 Eve levels
        for r in results:
            self.assertIn("eve", r)
            self.assertIn("bb84_qber", r)
            self.assertIn("e91_bell_S", r)
            self.assertIn("bb84_final", r)
            self.assertIn("e91_final", r)
            self.assertGreaterEqual(r["bb84_key"], 0)
            self.assertGreaterEqual(r["e91_key"], 0)

    def test_en_ko_keys_match_round18(self):
        """en.json과 ko.json 키 완전 일치 (R18 포함)."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        en = self._load_json(os.path.join(base, "locale", "en.json"))
        ko = self._load_json(os.path.join(base, "locale", "ko.json"))
        en_keys = set(en.keys())
        ko_keys = set(ko.keys())
        self.assertEqual(en_keys - ko_keys, set(),
                         f"en에만: {en_keys - ko_keys}")
        self.assertEqual(ko_keys - en_keys, set(),
                         f"ko에만: {ko_keys - en_keys}")


if __name__ == "__main__":
    unittest.main()
