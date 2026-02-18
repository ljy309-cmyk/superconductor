"""BB84 프로토콜 게임 로직 단위 테스트."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.bb84_protocol import (
    AUTO_BLOCK_THRESHOLD,
    ERROR_THRESHOLD,
    HISTORY_WINDOW,
    WARNING_THRESHOLD,
    BB84Game,
    QubitPacket,
)


class TestQubitPacket(unittest.TestCase):
    """QubitPacket 데이터 및 이동."""

    def test_initial_state(self):
        pkt = QubitPacket("0", "+", 1)
        self.assertEqual(pkt.bit, "0")
        self.assertEqual(pkt.basis, "+")
        self.assertFalse(pkt.is_decoy)
        self.assertFalse(pkt.intercepted)
        self.assertFalse(pkt.corrupted)
        self.assertFalse(pkt.arrived)

    def test_decoy_packet(self):
        pkt = QubitPacket("1", "×", 2, is_decoy=True)
        self.assertTrue(pkt.is_decoy)

    def test_display_arrows(self):
        cases = {
            ("+", "0"): "↑", ("+", "1"): "→",
            ("×", "0"): "↗", ("×", "1"): "↘",
        }
        for (basis, bit), expected in cases.items():
            pkt = QubitPacket(bit, basis, 1)
            self.assertEqual(pkt.display, expected)

    def test_display_unknown(self):
        pkt = QubitPacket("0", "?", 1)
        self.assertEqual(pkt.display, "?")

    def test_update_moves(self):
        pkt = QubitPacket("0", "+", 1)
        start_x = pkt.x
        pkt.update(0.1)
        self.assertGreater(pkt.x, start_x)

    def test_update_arrives(self):
        pkt = QubitPacket("0", "+", 1)
        for _ in range(100):
            pkt.update(0.1)
        self.assertTrue(pkt.arrived)


class TestBB84GameState(unittest.TestCase):
    """BB84Game 초기화 및 상태 관리."""

    def test_initial_state(self):
        game = BB84Game()
        self.assertEqual(game.round_id, 0)
        self.assertEqual(game.score, 0)
        self.assertTrue(game.channel_open)

    def test_reset(self):
        game = BB84Game()
        game.score = 100
        game.round_id = 50
        game.channel_open = False
        game.reset()
        self.assertEqual(game.score, 0)
        self.assertEqual(game.round_id, 0)
        self.assertTrue(game.channel_open)

    def test_reopen(self):
        game = BB84Game()
        game.channel_open = False
        game.error_history = [True, True]
        game.error_rate = 0.5
        game.reopen()
        self.assertTrue(game.channel_open)
        self.assertEqual(game.error_history, [])
        self.assertAlmostEqual(game.error_rate, 0.0)


class TestBB84GameRounds(unittest.TestCase):
    """new_round / process_arrival."""

    def test_new_round_increments_id(self):
        game = BB84Game()
        game.new_round()
        self.assertEqual(game.round_id, 1)

    def test_new_round_creates_packet(self):
        game = BB84Game()
        game.new_round()
        self.assertEqual(len(game.packets), 1)
        self.assertEqual(game.total_sent, 1)

    def test_closed_channel_no_send(self):
        game = BB84Game()
        game.channel_open = False
        game.new_round()
        self.assertEqual(game.round_id, 0)

    def test_eve_100_percent(self):
        game = BB84Game()
        game.new_round(eve_chance=1.0, decoy_chance=0.0)
        self.assertTrue(game.packets[0].intercepted)
        self.assertEqual(game.eve_intercept_count, 1)

    def test_no_eve(self):
        game = BB84Game()
        game.new_round(eve_chance=0.0, decoy_chance=0.0)
        self.assertFalse(game.packets[0].intercepted)

    def test_decoy_trap(self):
        game = BB84Game()
        game.new_round(eve_chance=1.0, decoy_chance=1.0)
        pkt = game.packets[0]
        self.assertTrue(pkt.is_decoy)
        self.assertTrue(pkt.corrupted)
        self.assertEqual(game.decoy_trapped, 1)


class TestBB84ErrorTracking(unittest.TestCase):
    """에러 추적 및 자동 차단."""

    def _make_packet(self, corrupted=False, intercepted=False, is_decoy=False):
        pkt = QubitPacket("0", "+", 1, is_decoy=is_decoy)
        pkt.arrived = True
        pkt.corrupted = corrupted
        pkt.intercepted = intercepted
        return pkt

    def test_error_rate_all_errors(self):
        game = BB84Game()
        with patch("security.bb84_protocol.random.choice", return_value="+"):
            for _ in range(10):
                game.process_arrival(self._make_packet(corrupted=True))
        self.assertAlmostEqual(game.error_rate, 1.0)

    def test_clean_channel(self):
        game = BB84Game()
        with patch("security.bb84_protocol.random.choice", return_value="+"):
            for _ in range(10):
                game.process_arrival(self._make_packet(corrupted=False))
        self.assertAlmostEqual(game.error_rate, 0.0)

    def test_history_window_cap(self):
        game = BB84Game()
        with patch("security.bb84_protocol.random.choice", return_value="+"):
            for _ in range(HISTORY_WINDOW + 20):
                game.process_arrival(self._make_packet(corrupted=False))
        self.assertLessEqual(len(game.error_history), HISTORY_WINDOW)

    def test_auto_block(self):
        game = BB84Game()
        with patch("security.bb84_protocol.random.choice", return_value="+"):
            for _ in range(10):
                game.process_arrival(self._make_packet(corrupted=True))
        self.assertFalse(game.channel_open)
        self.assertTrue(game.auto_shutdown)
        self.assertGreaterEqual(game.auto_blocks, 1)
        self.assertGreater(game.score, 0)

    def test_decoy_double_error(self):
        game = BB84Game()
        pkt = self._make_packet(corrupted=True, intercepted=True, is_decoy=True)
        with patch("security.bb84_protocol.random.choice", return_value="+"):
            game.process_arrival(pkt)
        errors = sum(game.error_history)
        self.assertEqual(errors, 2)


class TestBB84ManualShutdown(unittest.TestCase):
    """수동 통신망 폐쇄."""

    def test_manual_shutdown(self):
        game = BB84Game()
        game.manual_shutdown()
        self.assertFalse(game.channel_open)
        self.assertEqual(game.manual_blocks, 1)

    def test_manual_shutdown_with_high_error(self):
        game = BB84Game()
        game.error_rate = WARNING_THRESHOLD + 0.01
        game.manual_shutdown()
        self.assertGreater(game.score, 0)

    def test_already_closed(self):
        game = BB84Game()
        game.channel_open = False
        game.manual_shutdown()
        self.assertEqual(game.manual_blocks, 0)


if __name__ == "__main__":
    unittest.main()
