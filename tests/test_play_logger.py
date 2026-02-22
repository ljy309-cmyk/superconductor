"""play_logger 단위 테스트."""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pandas가 없는 환경용 모킹
if "pandas" not in sys.modules:  # pragma: no cover
    _pd_mock = MagicMock()
    _pd_mock.DataFrame.return_value = MagicMock(
        to_dict=MagicMock(return_value=[]),
        to_csv=MagicMock(),
        to_excel=MagicMock(),
        columns=[],
        __len__=lambda self: 0,
    )
    _pd_mock.read_csv.side_effect = FileNotFoundError
    sys.modules.setdefault("pandas", _pd_mock)


class TestPlayLogger(unittest.TestCase):
    def setUp(self):
        """각 테스트마다 임시 디렉토리 사용 + pandas 모킹 해제."""
        import data_ai.play_logger as pl

        self._orig_csv = pl.PLAY_LOG_CSV
        self._orig_xlsx = pl.PLAY_LOG_XLSX
        self._orig_pd = pl.pd
        self._tmpdir = tempfile.mkdtemp()
        pl.PLAY_LOG_CSV = os.path.join(self._tmpdir, "test_history.csv")
        pl.PLAY_LOG_XLSX = os.path.join(self._tmpdir, "test_history.xlsx")
        # pandas 모킹이 불완전하므로 순수 Python 경로 사용
        pl.pd = None

    def tearDown(self):
        import data_ai.play_logger as pl

        pl.PLAY_LOG_CSV = self._orig_csv
        pl.PLAY_LOG_XLSX = self._orig_xlsx
        pl.pd = self._orig_pd
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_log_session_creates_record(self):
        from data_ai.play_logger import PlayLogger

        logger = PlayLogger()
        record = logger.log_session("bb84_defense", {"score": 100, "total_sent": 50})
        self.assertEqual(record["module"], "bb84_defense")
        self.assertEqual(record["score"], 100)
        self.assertEqual(len(logger.records), 1)

    def test_log_session_incremental_csv(self):
        import data_ai.play_logger as pl
        from data_ai.play_logger import PlayLogger

        logger = PlayLogger()
        logger.log_session("bb84_defense", {"score": 100})
        logger.log_session("squid_mines", {"won": True, "mines_found": 8})

        self.assertTrue(os.path.exists(pl.PLAY_LOG_CSV))
        self.assertEqual(len(logger.records), 2)

    def test_export_creates_files(self):
        import data_ai.play_logger as pl
        from data_ai.play_logger import PlayLogger

        logger = PlayLogger()
        logger.log_session("qec_shield", {"survival_time": 45.2})
        logger.export()

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
            except Exception as e:  # pragma: no cover
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
        record = logger.log_session(
            "bb84_defense",
            {
                "score": 100,
                "custom_field": "hello",
            },
        )
        self.assertEqual(record["custom_field"], "hello")

    def test_csv_injection_sanitize_function(self):
        from data_ai.play_logger import _sanitize_csv_value

        # 위험 접두사가 살균됨
        self.assertEqual(_sanitize_csv_value("=CMD()"), "'=CMD()")
        self.assertEqual(_sanitize_csv_value("+1+1"), "'+1+1")
        self.assertEqual(_sanitize_csv_value("-1-1"), "'-1-1")
        self.assertEqual(_sanitize_csv_value("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(_sanitize_csv_value("\tdata"), "'\tdata")
        # 안전한 값은 그대로
        self.assertEqual(_sanitize_csv_value("hello"), "hello")
        self.assertEqual(_sanitize_csv_value(""), "")
        self.assertEqual(_sanitize_csv_value(42), 42)
        self.assertEqual(_sanitize_csv_value(None), None)

    def test_csv_injection_in_incremental_write(self):
        """CSV 증분 저장 시 인젝션 위험 문자열이 살균되는지 확인."""
        import csv

        import data_ai.play_logger as pl
        from data_ai.play_logger import PlayLogger

        logger = PlayLogger()
        logger.log_session(
            "bb84_defense",
            {
                "score": 100,
                "custom_field": '=HYPERLINK("evil")',
            },
        )
        # CSV 파일 파싱하여 셀 값 검증
        with open(pl.PLAY_LOG_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)
        # 셀 값이 '= 로 시작해야 함 (작은따옴표 접두사로 살균됨)
        self.assertTrue(
            row["custom_field"].startswith("'="), f"Expected sanitized prefix, got: {row['custom_field']!r}"
        )


try:
    import tkinter

    _HAS_TKINTER = True
except ImportError:  # pragma: no cover
    _HAS_TKINTER = False


@unittest.skipUnless(_HAS_TKINTER, "tkinter not available in this environment")
class TestQRNGThreadSafety(unittest.TestCase):
    def test_push_and_pop(self):
        from data_ai.qrng_logger import pop_key_bit, push_key_bits, shared_key_available

        # 큐 비우기
        while pop_key_bit() is not None:
            pass

        push_key_bits([1, 0, 1, 1])
        self.assertEqual(shared_key_available(), 4)

        bit = pop_key_bit()
        self.assertEqual(bit, 1)
        self.assertEqual(shared_key_available(), 3)

    def test_pop_empty(self):
        from data_ai.qrng_logger import pop_key_bit

        # 큐 비우기
        while pop_key_bit() is not None:
            pass

        result = pop_key_bit()
        self.assertIsNone(result)

    def test_concurrent_access(self):
        import threading

        from data_ai.qrng_logger import pop_key_bit, push_key_bits

        # 큐 비우기
        while pop_key_bit() is not None:
            pass

        results = []
        errors = []

        def producer():
            try:
                push_key_bits([1] * 100)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        def consumer():
            count = 0
            try:
                for _ in range(100):
                    b = pop_key_bit()
                    if b is not None:
                        count += 1
                results.append(count)
            except Exception as e:  # pragma: no cover
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
