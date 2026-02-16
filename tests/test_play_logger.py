"""play_logger 단위 테스트."""

import os
import sys
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPlayLogger(unittest.TestCase):

    def setUp(self):
        """각 테스트마다 임시 디렉토리 사용."""
        import data_ai.play_logger as pl
        self._orig_csv = pl.PLAY_LOG_CSV
        self._orig_xlsx = pl.PLAY_LOG_XLSX
        self._tmpdir = tempfile.mkdtemp()
        pl.PLAY_LOG_CSV = os.path.join(self._tmpdir, "test_history.csv")
        pl.PLAY_LOG_XLSX = os.path.join(self._tmpdir, "test_history.xlsx")

    def tearDown(self):
        import data_ai.play_logger as pl
        pl.PLAY_LOG_CSV = self._orig_csv
        pl.PLAY_LOG_XLSX = self._orig_xlsx
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_log_session_creates_record(self):
        from data_ai.play_logger import PlayLogger
        logger = PlayLogger()
        record = logger.log_session("bb84_defense", {"score": 100, "total_sent": 50})
        self.assertEqual(record["module"], "bb84_defense")
        self.assertEqual(record["score"], 100)
        self.assertEqual(len(logger.records), 1)

    def test_log_session_incremental_csv(self):
        from data_ai.play_logger import PlayLogger
        import data_ai.play_logger as pl
        logger = PlayLogger()
        logger.log_session("bb84_defense", {"score": 100})
        logger.log_session("squid_mines", {"won": True, "mines_found": 8})

        self.assertTrue(os.path.exists(pl.PLAY_LOG_CSV))
        self.assertEqual(len(logger.records), 2)

    def test_export_creates_files(self):
        from data_ai.play_logger import PlayLogger
        import data_ai.play_logger as pl
        logger = PlayLogger()
        logger.log_session("qec_shield", {"survival_time": 45.2})
        path = logger.export()

        self.assertTrue(os.path.exists(pl.PLAY_LOG_CSV))

    def test_get_summary_empty(self):
        from data_ai.play_logger import PlayLogger
        logger = PlayLogger()
        summary = logger.get_summary()
        self.assertEqual(summary["total_sessions"], 0)

    def test_get_summary_with_data(self):
        from data_ai.play_logger import PlayLogger
        logger = PlayLogger()
        logger.log_session("bb84_defense", {"score": 100, "total_sent": 50})
        logger.log_session("bb84_defense", {"score": 200, "total_sent": 80})
        summary = logger.get_summary()
        self.assertEqual(summary["total_sessions"], 2)
        self.assertEqual(summary["modules_played"], 1)

    def test_clear(self):
        from data_ai.play_logger import PlayLogger
        logger = PlayLogger()
        logger.log_session("bb84_defense", {"score": 100})
        logger.clear()
        self.assertEqual(len(logger.records), 0)

    def test_thread_safety_singleton(self):
        import threading
        from data_ai.play_logger import PlayLogger

        instances = []
        errors = []

        def create():
            try:
                l = PlayLogger()
                instances.append(id(l))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)

    def test_custom_fields(self):
        from data_ai.play_logger import PlayLogger
        logger = PlayLogger()
        record = logger.log_session("bb84_defense", {
            "score": 100,
            "custom_field": "hello",
        })
        self.assertEqual(record["custom_field"], "hello")


try:
    import tkinter
    _HAS_TKINTER = True
except ImportError:
    _HAS_TKINTER = False


@unittest.skipUnless(_HAS_TKINTER, "tkinter not available in this environment")
class TestQRNGThreadSafety(unittest.TestCase):

    def test_push_and_pop(self):
        from data_ai.qrng_logger import push_key_bits, pop_key_bit, shared_key_available

        # 큐 비우기
        while pop_key_bit() is not None:
            pass

        push_key_bits([1, 0, 1, 1])
        self.assertEqual(shared_key_available(), 4)

        bit = pop_key_bit()
        self.assertEqual(bit, 1)
        self.assertEqual(shared_key_available(), 3)

    def test_pop_empty(self):
        from data_ai.qrng_logger import pop_key_bit, shared_key_available

        # 큐 비우기
        while pop_key_bit() is not None:
            pass

        result = pop_key_bit()
        self.assertIsNone(result)

    def test_concurrent_access(self):
        import threading
        from data_ai.qrng_logger import push_key_bits, pop_key_bit

        # 큐 비우기
        while pop_key_bit() is not None:
            pass

        results = []
        errors = []

        def producer():
            try:
                push_key_bits([1] * 100)
            except Exception as e:
                errors.append(e)

        def consumer():
            count = 0
            try:
                for _ in range(100):
                    b = pop_key_bit()
                    if b is not None:
                        count += 1
                results.append(count)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=producer))
            threads.append(threading.Thread(target=consumer))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
