"""QRNG 비트 추출 로직 단위 테스트."""

import os
import sys
import unittest
from unittest.mock import MagicMock

# tkinter/pandas mock
sys.modules.setdefault("tkinter", MagicMock())
sys.modules.setdefault("tkinter.ttk", MagicMock())
sys.modules.setdefault("tkinter.messagebox", MagicMock())
sys.modules.setdefault("pandas", MagicMock())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_ai.qrng_logger import (
    QuantumNoiseSource,
    _shared_key_queue,
    pop_key_bit,
    push_key_bits,
    shared_key_available,
)


class TestQuantumNoiseSource(unittest.TestCase):
    """QuantumNoiseSource 비트 추출."""

    def test_extract_bit_binary(self):
        src = QuantumNoiseSource(0)
        for _ in range(100):
            self.assertIn(src.extract_bit(), (0, 1))

    def test_extract_bit_detail_tuple(self):
        src = QuantumNoiseSource(0)
        bit, noise, digit = src.extract_bit_detail()
        self.assertIn(bit, (0, 1))
        self.assertIsInstance(noise, float)
        self.assertGreaterEqual(digit, 0)
        self.assertLessEqual(digit, 9)

    def test_detail_consistency(self):
        src = QuantumNoiseSource(0)
        for _ in range(50):
            bit, noise, digit = src.extract_bit_detail()
            self.assertEqual(bit, digit % 2)

    def test_different_sources(self):
        s1 = QuantumNoiseSource(0)
        s2 = QuantumNoiseSource(1)
        self.assertTrue(s1._freq != s2._freq or s1._phase != s2._phase, "Different qids should have different params")

    def test_sample_noise_float(self):
        src = QuantumNoiseSource(0)
        self.assertIsInstance(src.sample_noise(), float)

    def test_entropy_reasonable(self):
        src = QuantumNoiseSource(0)
        bits = [src.extract_bit() for _ in range(200)]
        zeros = bits.count(0)
        ones = bits.count(1)
        self.assertGreater(zeros, 0)
        self.assertGreater(ones, 0)
        ratio = min(zeros, ones) / max(zeros, ones)
        self.assertGreater(ratio, 0.1)


class TestSharedKeyQueue(unittest.TestCase):
    """공유 키 저장소."""

    def setUp(self):
        while not _shared_key_queue.empty():
            _shared_key_queue.get_nowait()

    def test_push_and_pop(self):
        push_key_bits([0, 1, 1, 0])
        self.assertEqual(shared_key_available(), 4)
        self.assertEqual(pop_key_bit(), 0)
        self.assertEqual(pop_key_bit(), 1)
        self.assertEqual(pop_key_bit(), 1)
        self.assertEqual(pop_key_bit(), 0)

    def test_pop_empty(self):
        self.assertIsNone(pop_key_bit())

    def test_available_count(self):
        push_key_bits([1] * 10)
        self.assertEqual(shared_key_available(), 10)

    def test_fifo_order(self):
        bits = [1, 0, 1, 1, 0, 0]
        push_key_bits(bits)
        result = [pop_key_bit() for _ in range(len(bits))]
        self.assertEqual(result, bits)


if __name__ == "__main__":
    unittest.main()
