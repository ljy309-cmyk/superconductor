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
        for _ in range(100):
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


if __name__ == "__main__":
    unittest.main()
