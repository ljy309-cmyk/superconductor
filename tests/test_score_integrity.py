"""score_integrity 단위 테스트 — HMAC 서명/검증, TTL, 변조 탐지."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSignScore(unittest.TestCase):
    """sign_score 함수 검증."""

    def test_returns_string(self):
        from score_integrity import sign_score
        token = sign_score("Alice", 42.5, "qubit_chain")
        self.assertIsInstance(token, str)

    def test_token_format(self):
        """토큰이 'timestamp:hex_digest' 형식인지 확인."""
        from score_integrity import sign_score
        token = sign_score("Player", 100.0, "bb84")
        parts = token.split(":", 1)
        self.assertEqual(len(parts), 2)
        # 첫 부분은 정수 타임스탬프
        ts = int(parts[0])
        self.assertGreater(ts, 0)
        # 두 번째 부분은 64자 hex (SHA-256)
        self.assertEqual(len(parts[1]), 64)
        int(parts[1], 16)  # hex 파싱 가능해야 함

    def test_different_inputs_different_tokens(self):
        """다른 입력은 다른 토큰 생성."""
        from score_integrity import sign_score
        t1 = sign_score("Alice", 42.5, "qubit_chain")
        t2 = sign_score("Bob", 42.5, "qubit_chain")
        t3 = sign_score("Alice", 99.0, "qubit_chain")
        t4 = sign_score("Alice", 42.5, "bb84")
        # digest 부분 비교
        digests = {t.split(":", 1)[1] for t in [t1, t2, t3, t4]}
        self.assertEqual(len(digests), 4)

    def test_same_input_same_second_same_digest(self):
        """같은 초 내 동일 입력이면 동일 digest."""
        from score_integrity import sign_score
        t1 = sign_score("X", 1.0, "m")
        t2 = sign_score("X", 1.0, "m")
        # 같은 초 내에 실행되므로 동일해야 함
        self.assertEqual(t1.split(":", 1)[1], t2.split(":", 1)[1])


class TestVerifyScore(unittest.TestCase):
    """verify_score 함수 검증."""

    def test_valid_token_passes(self):
        from score_integrity import sign_score, verify_score
        token = sign_score("Alice", 42.5, "qubit_chain")
        self.assertTrue(verify_score("Alice", 42.5, "qubit_chain", token))

    def test_wrong_name_fails(self):
        from score_integrity import sign_score, verify_score
        token = sign_score("Alice", 42.5, "qubit_chain")
        self.assertFalse(verify_score("Bob", 42.5, "qubit_chain", token))

    def test_wrong_score_fails(self):
        from score_integrity import sign_score, verify_score
        token = sign_score("Alice", 42.5, "qubit_chain")
        self.assertFalse(verify_score("Alice", 99.0, "qubit_chain", token))

    def test_wrong_mode_fails(self):
        from score_integrity import sign_score, verify_score
        token = sign_score("Alice", 42.5, "qubit_chain")
        self.assertFalse(verify_score("Alice", 42.5, "bb84", token))

    def test_tampered_digest_fails(self):
        """digest를 변조하면 실패."""
        from score_integrity import sign_score, verify_score
        token = sign_score("Alice", 42.5, "qubit_chain")
        ts, digest = token.split(":", 1)
        # 마지막 문자를 변경
        tampered = digest[:-1] + ("0" if digest[-1] != "0" else "1")
        self.assertFalse(verify_score("Alice", 42.5, "qubit_chain", f"{ts}:{tampered}"))

    def test_tampered_timestamp_fails(self):
        """타임스탬프를 변조하면 실패."""
        from score_integrity import sign_score, verify_score
        token = sign_score("Alice", 42.5, "qubit_chain")
        ts, digest = token.split(":", 1)
        fake_ts = int(ts) + 1
        self.assertFalse(verify_score("Alice", 42.5, "qubit_chain", f"{fake_ts}:{digest}"))

    def test_score_precision(self):
        """점수 소수점 2자리까지만 비교 (:.2f 포맷)."""
        from score_integrity import sign_score, verify_score
        token = sign_score("P", 42.555, "m")
        # 동일 .2f 반올림이면 통과
        self.assertTrue(verify_score("P", 42.555, "m", token))
        # 다른 .2f 반올림이면 실패
        self.assertFalse(verify_score("P", 42.56, "m", token))


class TestVerifyScoreEdgeCases(unittest.TestCase):
    """verify_score 엣지 케이스."""

    def test_empty_token_fails(self):
        from score_integrity import verify_score
        self.assertFalse(verify_score("A", 1.0, "m", ""))

    def test_no_colon_fails(self):
        from score_integrity import verify_score
        self.assertFalse(verify_score("A", 1.0, "m", "notavalidtoken"))

    def test_non_numeric_timestamp_fails(self):
        from score_integrity import verify_score
        self.assertFalse(verify_score("A", 1.0, "m", "abc:def"))

    def test_multiple_colons(self):
        """콜론이 여러 개인 경우 첫 번째로만 split."""
        from score_integrity import verify_score
        self.assertFalse(verify_score("A", 1.0, "m", "123:abc:def"))

    def test_negative_score(self):
        """음수 점수도 서명/검증 가능."""
        from score_integrity import sign_score, verify_score
        token = sign_score("P", -10.0, "mode")
        self.assertTrue(verify_score("P", -10.0, "mode", token))

    def test_zero_score(self):
        from score_integrity import sign_score, verify_score
        token = sign_score("P", 0.0, "mode")
        self.assertTrue(verify_score("P", 0.0, "mode", token))

    def test_very_large_score(self):
        from score_integrity import sign_score, verify_score
        token = sign_score("P", 999999.99, "mode")
        self.assertTrue(verify_score("P", 999999.99, "mode", token))

    def test_empty_name(self):
        from score_integrity import sign_score, verify_score
        token = sign_score("", 1.0, "mode")
        self.assertTrue(verify_score("", 1.0, "mode", token))

    def test_unicode_name(self):
        from score_integrity import sign_score, verify_score
        token = sign_score("유저이름", 50.0, "qubit_chain")
        self.assertTrue(verify_score("유저이름", 50.0, "qubit_chain", token))

    def test_special_chars_in_name(self):
        from score_integrity import sign_score, verify_score
        token = sign_score("a:b:c", 1.0, "m")
        self.assertTrue(verify_score("a:b:c", 1.0, "m", token))


class TestTokenTTL(unittest.TestCase):
    """토큰 TTL (만료) 검증."""

    def test_expired_token_fails(self):
        """TTL을 초과한 토큰은 실패해야 함."""
        import score_integrity
        token = score_integrity.sign_score("P", 1.0, "m")
        # TTL을 0초로 일시 변경
        orig_ttl = score_integrity._TOKEN_TTL
        try:
            score_integrity._TOKEN_TTL = 0
            # 1초 이상 차이나면 만료
            ts, digest = token.split(":", 1)
            old_ts = int(ts) - 2
            expired_token = f"{old_ts}:{digest}"
            self.assertFalse(score_integrity.verify_score("P", 1.0, "m", expired_token))
        finally:
            score_integrity._TOKEN_TTL = orig_ttl

    def test_future_timestamp_within_ttl_passes(self):
        """미래 타임스탬프라도 TTL 내이면 통과."""
        import score_integrity
        # 현재 시각으로 서명하고 바로 검증 → TTL 내
        token = score_integrity.sign_score("P", 1.0, "m")
        self.assertTrue(score_integrity.verify_score("P", 1.0, "m", token))

    def test_far_future_timestamp_fails(self):
        """먼 미래 타임스탬프는 실패 (abs 비교)."""
        import score_integrity
        from score_integrity import _make_message
        import hashlib
        import hmac

        far_future = int(time.time()) + 9999
        msg = _make_message("P", 1.0, "m", far_future)
        digest = hmac.new(score_integrity._SECRET, msg, hashlib.sha256).hexdigest()
        token = f"{far_future}:{digest}"
        self.assertFalse(score_integrity.verify_score("P", 1.0, "m", token))


class TestMakeMessage(unittest.TestCase):
    """_make_message 내부 함수 검증."""

    def test_returns_bytes(self):
        from score_integrity import _make_message
        msg = _make_message("A", 1.0, "m", 123)
        self.assertIsInstance(msg, bytes)

    def test_deterministic(self):
        from score_integrity import _make_message
        m1 = _make_message("A", 1.0, "m", 123)
        m2 = _make_message("A", 1.0, "m", 123)
        self.assertEqual(m1, m2)

    def test_format_includes_all_fields(self):
        from score_integrity import _make_message
        msg = _make_message("Alice", 42.50, "qubit_chain", 1000)
        self.assertEqual(msg, b"Alice:42.50:qubit_chain:1000")

    def test_score_two_decimals(self):
        """점수가 소수점 2자리로 포맷되는지 확인."""
        from score_integrity import _make_message
        msg = _make_message("P", 42.556, "m", 0)
        self.assertIn(b"42.56", msg)  # 반올림


if __name__ == "__main__":
    unittest.main()
