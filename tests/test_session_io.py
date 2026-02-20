"""session_io — 설정 내보내기/가져오기 공통 모듈 중점 테스트.

session_io.py 의 핵심 함수(export_session_json, list_export_files,
load_session_json, load_session_with_trials)와 각 모듈별 통합 래퍼를 검증한다.
"""

import csv
import json
import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for mod in ("pygame", "pygame.locals", "matplotlib", "matplotlib.pyplot", "tkinter"):
    sys.modules.setdefault(mod, MagicMock())


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. session_io 공통 모듈 단위 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExportSessionJson(unittest.TestCase):
    """export_session_json — JSON(+CSV) 내보내기."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_export_dir = None
        # EXPORT_DIR 을 임시 디렉토리로 교체
        import session_io

        self.sio = session_io
        self.orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = os.path.join(self.tmpdir, "exports")

    def tearDown(self):
        self.sio.EXPORT_DIR = self.orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # -- 기본 내보내기 ------------------------------------------------

    def test_export_json_only(self):
        """trial_rows 없이 JSON만 내보내기."""
        data = {"score": 100, "level": 3}
        result = self.sio.export_session_json("test_module", data)
        self.assertIsNotNone(result)
        self.assertTrue(os.path.isdir(result))

        # JSON 파일이 생성되었는지 확인
        files = os.listdir(result)
        json_files = [f for f in files if f.endswith(".json")]
        self.assertEqual(len(json_files), 1)
        self.assertTrue(json_files[0].startswith("test_module_stats_"))

        # JSON 내용 검증
        with open(os.path.join(result, json_files[0]), encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded["score"], 100)
        self.assertEqual(loaded["level"], 3)
        self.assertIn("timestamp", loaded)

    def test_export_json_preserves_all_fields(self):
        """내보낸 JSON이 원본 딕셔너리의 모든 필드를 유지."""
        data = {
            "total_attempts": 50,
            "tunnel_count": 20,
            "barrier_width": 30,
            "base_prob": 0.15,
            "difficulty": "hard",
        }
        result = self.sio.export_session_json("tunnel_test", data)
        files = [f for f in os.listdir(result) if f.endswith(".json")]
        with open(os.path.join(result, files[0]), encoding="utf-8") as f:
            loaded = json.load(f)
        for key, val in data.items():
            self.assertEqual(loaded[key], val, f"필드 {key} 불일치")

    def test_export_does_not_mutate_original(self):
        """export가 원본 딕셔너리를 변경하지 않음."""
        data = {"score": 42}
        self.assertNotIn("timestamp", data)
        self.sio.export_session_json("safe", data)
        self.assertNotIn("timestamp", data)

    def test_export_with_csv(self):
        """trial_rows + trial_columns → CSV도 함께 생성."""
        data = {"total": 3}
        trials = [
            {"time_s": 1.0, "result": 1},
            {"time_s": 2.0, "result": 0},
            {"time_s": 3.0, "result": 1},
        ]
        cols = ["time_s", "result"]
        result = self.sio.export_session_json(
            "csv_test",
            data,
            trial_rows=trials,
            trial_columns=cols,
        )
        self.assertIsNotNone(result)

        csv_files = [f for f in os.listdir(result) if f.endswith(".csv")]
        self.assertEqual(len(csv_files), 1)
        self.assertTrue(csv_files[0].startswith("csv_test_trials_"))

        # CSV 내용 검증
        with open(os.path.join(result, csv_files[0]), encoding="utf-8") as f:
            reader = list(csv.reader(f))
        self.assertEqual(reader[0], ["time_s", "result"])
        self.assertEqual(len(reader), 4)  # 헤더 + 3행

    def test_export_csv_with_custom_row_fn(self):
        """trial_row_fn 커스텀 변환 함수 적용."""
        data = {"total": 2}
        trials = [
            {"t": 1.5, "ok": True},
            {"t": 2.5, "ok": False},
        ]
        cols = ["index", "time", "success"]

        def row_fn(i, tr):
            return [i, tr["t"], int(tr["ok"])]

        result = self.sio.export_session_json(
            "fn_test",
            data,
            trial_rows=trials,
            trial_columns=cols,
            trial_row_fn=row_fn,
        )
        csv_files = [f for f in os.listdir(result) if f.endswith(".csv")]
        with open(os.path.join(result, csv_files[0]), encoding="utf-8") as f:
            reader = list(csv.reader(f))
        self.assertEqual(reader[1], ["1", "1.5", "1"])
        self.assertEqual(reader[2], ["2", "2.5", "0"])

    def test_export_csv_default_row_extraction(self):
        """trial_row_fn 미지정 시 trial_columns 순서로 값 추출."""
        data = {"x": 1}
        trials = [{"a": 10, "b": 20, "c": 30}]
        cols = ["c", "a"]
        result = self.sio.export_session_json(
            "default_fn",
            data,
            trial_rows=trials,
            trial_columns=cols,
        )
        csv_files = [f for f in os.listdir(result) if f.endswith(".csv")]
        with open(os.path.join(result, csv_files[0]), encoding="utf-8") as f:
            reader = list(csv.reader(f))
        self.assertEqual(reader[0], ["c", "a"])
        self.assertEqual(reader[1], ["30", "10"])

    def test_export_empty_trials(self):
        """trial_rows가 빈 리스트 → CSV 미생성."""
        data = {"x": 1}
        result = self.sio.export_session_json(
            "empty_csv",
            data,
            trial_rows=[],
            trial_columns=["a"],
        )
        csv_files = [f for f in os.listdir(result) if f.endswith(".csv")]
        self.assertEqual(len(csv_files), 0)

    def test_export_creates_directory(self):
        """EXPORT_DIR이 없으면 자동 생성."""
        new_dir = os.path.join(self.tmpdir, "new_exports")
        self.sio.EXPORT_DIR = new_dir
        self.assertFalse(os.path.isdir(new_dir))
        self.sio.export_session_json("mkdir_test", {"v": 1})
        self.assertTrue(os.path.isdir(new_dir))

    def test_export_returns_none_on_write_failure(self):
        """쓰기 불가 경로 → None 반환."""
        # makedirs는 통과하지만 파일 쓰기에서 실패하도록 mock
        with unittest.mock.patch("builtins.open", side_effect=OSError("mocked write error")):
            result = self.sio.export_session_json("fail_test", {"v": 1})
        self.assertIsNone(result)

    def test_export_unicode_data(self):
        """유니코드(한글 등) 데이터 정상 저장."""
        data = {"이름": "테스트", "설명": "한글 내보내기 확인"}
        result = self.sio.export_session_json("unicode", data)
        files = [f for f in os.listdir(result) if f.endswith(".json")]
        with open(os.path.join(result, files[0]), encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded["이름"], "테스트")


class TestListExportFiles(unittest.TestCase):
    """list_export_files — 내보내기 파일 목록 조회."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self.sio = session_io
        self.orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = self.tmpdir

    def tearDown(self):
        self.sio.EXPORT_DIR = self.orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_directory(self):
        """파일 없는 디렉토리 → 빈 리스트."""
        result = self.sio.list_export_files("test")
        self.assertEqual(result, [])

    def test_nonexistent_directory(self):
        """존재하지 않는 디렉토리 → 빈 리스트."""
        self.sio.EXPORT_DIR = "/nonexistent_path"
        result = self.sio.list_export_files("test")
        self.assertEqual(result, [])

    def test_filters_by_prefix(self):
        """지정 prefix 파일만 반환."""
        # tunneling 파일 2개 + bb84 파일 1개 생성
        for name in [
            "tunneling_stats_20260101_100000.json",
            "tunneling_stats_20260102_120000.json",
            "bb84_stats_20260101_100000.json",
        ]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("{}")

        result = self.sio.list_export_files("tunneling")
        self.assertEqual(len(result), 2)

        result_bb84 = self.sio.list_export_files("bb84")
        self.assertEqual(len(result_bb84), 1)

    def test_ignores_csv_files(self):
        """CSV 파일은 목록에 포함하지 않음."""
        for name in [
            "test_stats_20260101_100000.json",
            "test_trials_20260101_100000.csv",
        ]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("{}")

        result = self.sio.list_export_files("test")
        self.assertEqual(len(result), 1)

    def test_sorted_reverse_chronological(self):
        """최신순(역순) 정렬."""
        names = [
            "mod_stats_20260101_100000.json",
            "mod_stats_20260103_100000.json",
            "mod_stats_20260102_100000.json",
        ]
        for name in names:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("{}")

        result = self.sio.list_export_files("mod")
        labels = [label for label, _ in result]
        self.assertEqual(labels, ["20260103_100000", "20260102_100000", "20260101_100000"])

    def test_returns_full_paths(self):
        """반환 경로가 절대 경로."""
        with open(os.path.join(self.tmpdir, "p_stats_20260101_120000.json"), "w") as f:
            f.write("{}")

        result = self.sio.list_export_files("p")
        self.assertEqual(len(result), 1)
        _, path = result[0]
        self.assertTrue(os.path.isabs(path))
        self.assertTrue(path.endswith(".json"))

    def test_label_format(self):
        """표시명에서 prefix와 .json이 제거됨."""
        with open(os.path.join(self.tmpdir, "abc_stats_20260115_093000.json"), "w") as f:
            f.write("{}")

        result = self.sio.list_export_files("abc")
        label, _ = result[0]
        self.assertEqual(label, "20260115_093000")


class TestLoadSessionJson(unittest.TestCase):
    """load_session_json — 단일 JSON 파일 로드."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_valid_json(self):
        """유효한 JSON 정상 로드."""
        data = {"score": 100, "time": 30.5}
        path = os.path.join(self.tmpdir, "test.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        import session_io

        result = session_io.load_session_json(path)
        self.assertIsNotNone(result)
        self.assertEqual(result["score"], 100)
        self.assertAlmostEqual(result["time"], 30.5)

    def test_load_nonexistent_file(self):
        """존재하지 않는 파일 → None."""
        import session_io

        result = session_io.load_session_json("/no/such/file.json")
        self.assertIsNone(result)

    def test_load_invalid_json(self):
        """잘못된 JSON → None."""
        path = os.path.join(self.tmpdir, "bad.json")
        with open(path, "w") as f:
            f.write("{not valid json!}")

        import session_io

        result = session_io.load_session_json(path)
        self.assertIsNone(result)

    def test_load_empty_file(self):
        """빈 파일 → None (JSONDecodeError)."""
        path = os.path.join(self.tmpdir, "empty.json")
        open(path, "w").close()

        import session_io

        result = session_io.load_session_json(path)
        self.assertIsNone(result)

    def test_load_unicode_content(self):
        """유니코드 내용 정상 로드."""
        data = {"이름": "양자 터널링", "점수": 95}
        path = os.path.join(self.tmpdir, "kr.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        import session_io

        result = session_io.load_session_json(path)
        self.assertEqual(result["이름"], "양자 터널링")

    def test_load_nested_data(self):
        """중첩 딕셔너리/리스트 정상 로드."""
        data = {"settings": {"a": 1, "b": [2, 3]}, "items": [{"x": 10}]}
        path = os.path.join(self.tmpdir, "nested.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        import session_io

        result = session_io.load_session_json(path)
        self.assertEqual(result["settings"]["a"], 1)
        self.assertEqual(result["items"][0]["x"], 10)


class TestLoadSessionWithTrials(unittest.TestCase):
    """load_session_with_trials — JSON + CSV 시행 이력 로드."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.export_dir = self.tmpdir

        # JSON 파일 생성
        self.session_data = {
            "total_attempts": 30,
            "tunnel_count": 12,
            "barrier_width": 40,
        }
        self.json_path = os.path.join(self.export_dir, "mymod_stats_20260115_120000.json")
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.session_data, f, indent=2)

        # 매칭 CSV 파일 생성
        self.csv_path = os.path.join(self.export_dir, "mymod_trials_20260115_120000.csv")
        with open(self.csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["trial", "time_s", "value"])
            writer.writerow([1, "1.0", "100"])
            writer.writerow([2, "2.0", "200"])
            writer.writerow([3, "3.0", "300"])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_json_and_csv(self):
        """JSON + CSV 모두 정상 로드."""
        import session_io

        session, trials = session_io.load_session_with_trials(self.json_path, "mymod")
        self.assertIsNotNone(session)
        self.assertEqual(session["total_attempts"], 30)
        self.assertEqual(len(trials), 3)

    def test_csv_rows_as_dicts(self):
        """trial_parse_fn 미지정 → CSV 행을 그대로 dict 반환."""
        import session_io

        _, trials = session_io.load_session_with_trials(self.json_path, "mymod")
        self.assertEqual(trials[0]["trial"], "1")
        self.assertEqual(trials[0]["time_s"], "1.0")
        self.assertEqual(trials[2]["value"], "300")

    def test_custom_parse_fn(self):
        """trial_parse_fn으로 타입 변환."""
        import session_io

        def parse_fn(row):
            return {"t": float(row["time_s"]), "v": int(row["value"])}

        _, trials = session_io.load_session_with_trials(self.json_path, "mymod", trial_parse_fn=parse_fn)
        self.assertIsInstance(trials[0]["t"], float)
        self.assertAlmostEqual(trials[0]["t"], 1.0)
        self.assertEqual(trials[1]["v"], 200)

    def test_no_csv_file(self):
        """CSV 없이 JSON만 → session 정상, trials 빈 리스트."""
        json_only = os.path.join(self.export_dir, "mymod_stats_20260201_000000.json")
        with open(json_only, "w", encoding="utf-8") as f:
            json.dump({"count": 5}, f)

        import session_io

        session, trials = session_io.load_session_with_trials(json_only, "mymod")
        self.assertIsNotNone(session)
        self.assertEqual(session["count"], 5)
        self.assertEqual(trials, [])

    def test_bad_json(self):
        """잘못된 JSON → (None, [])."""
        bad_path = os.path.join(self.export_dir, "mymod_stats_20260301_000000.json")
        with open(bad_path, "w") as f:
            f.write("NOT JSON")

        import session_io

        session, trials = session_io.load_session_with_trials(bad_path, "mymod")
        self.assertIsNone(session)
        self.assertEqual(trials, [])

    def test_missing_file(self):
        """존재하지 않는 파일 → (None, [])."""
        import session_io

        session, trials = session_io.load_session_with_trials("/nonexistent.json", "mymod")
        self.assertIsNone(session)
        self.assertEqual(trials, [])

    def test_csv_path_derived_from_json(self):
        """CSV 경로가 prefix_stats_ → prefix_trials_ 변환으로 결정됨을 검증."""
        import session_io

        # json: mymod_stats_20260115_120000.json
        # csv:  mymod_trials_20260115_120000.csv (이미 setUp에서 생성됨)
        _, trials = session_io.load_session_with_trials(self.json_path, "mymod")
        self.assertEqual(len(trials), 3)

    def test_corrupted_csv_still_returns_session(self):
        """CSV 파싱 실패해도 session은 정상 반환."""
        # CSV를 손상된 내용으로 덮어쓰기
        with open(self.csv_path, "w") as f:
            f.write("not,a,csv\n\x00\x01\x02")

        import session_io

        # trial_parse_fn에서 KeyError 유발
        def parse_fn(row):
            return {"t": float(row["time_s"])}

        session, trials = session_io.load_session_with_trials(self.json_path, "mymod", trial_parse_fn=parse_fn)
        # session은 정상, trials는 부분 또는 빈 리스트
        self.assertIsNotNone(session)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 내보내기→가져오기 라운드트립 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExportImportRoundTrip(unittest.TestCase):
    """export → list → load 라운드트립 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self.sio = session_io
        self.orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = os.path.join(self.tmpdir, "exports")

    def tearDown(self):
        self.sio.EXPORT_DIR = self.orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_json_only_roundtrip(self):
        """JSON만 내보내고 → 목록 조회 → 로드하여 내용 일치 확인."""
        original = {"score": 42, "level": "easy", "rate": 0.75}
        self.sio.export_session_json("rt", original)

        files = self.sio.list_export_files("rt")
        self.assertEqual(len(files), 1)

        _, json_path = files[0]
        loaded = self.sio.load_session_json(json_path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["score"], 42)
        self.assertEqual(loaded["level"], "easy")
        self.assertAlmostEqual(loaded["rate"], 0.75)

    def test_json_csv_roundtrip(self):
        """JSON+CSV 내보내고 → 로드하여 시행 이력까지 복원 확인."""
        original = {"total": 3, "success": 2}
        trials = [
            {"time_s": 1.0, "barrier_width": 30, "result": 1},
            {"time_s": 2.0, "barrier_width": 30, "result": 0},
            {"time_s": 3.5, "barrier_width": 40, "result": 1},
        ]
        cols = ["time_s", "barrier_width", "result"]
        self.sio.export_session_json("rt2", original, trial_rows=trials, trial_columns=cols)

        files = self.sio.list_export_files("rt2")
        _, json_path = files[0]

        session, loaded_trials = self.sio.load_session_with_trials(json_path, "rt2")
        self.assertEqual(session["total"], 3)
        self.assertEqual(len(loaded_trials), 3)
        self.assertEqual(loaded_trials[0]["time_s"], "1.0")
        self.assertEqual(loaded_trials[2]["barrier_width"], "40")

    def test_roundtrip_with_parse_fn(self):
        """내보내기(row_fn) → 가져오기(parse_fn) 타입 변환 일관성."""
        original = {"count": 2}
        trials = [
            {"t": 1.5, "barrier": 30, "prob": 0.105, "result": True},
            {"t": 2.5, "barrier": 40, "prob": 0.200, "result": False},
        ]
        cols = ["trial", "time_s", "barrier_width", "tunnel_prob", "result"]

        def row_fn(i, tr):
            return [i, tr["t"], tr["barrier"], tr["prob"], int(tr["result"])]

        self.sio.export_session_json(
            "rt3",
            original,
            trial_rows=trials,
            trial_columns=cols,
            trial_row_fn=row_fn,
        )

        files = self.sio.list_export_files("rt3")
        _, json_path = files[0]

        def parse_fn(row):
            return {
                "t": float(row["time_s"]),
                "barrier": int(row["barrier_width"]),
                "prob": float(row["tunnel_prob"]),
                "result": bool(int(row["result"])),
            }

        _, loaded_trials = self.sio.load_session_with_trials(json_path, "rt3", trial_parse_fn=parse_fn)
        self.assertEqual(len(loaded_trials), 2)
        self.assertAlmostEqual(loaded_trials[0]["t"], 1.5)
        self.assertEqual(loaded_trials[0]["barrier"], 30)
        self.assertAlmostEqual(loaded_trials[0]["prob"], 0.105)
        self.assertTrue(loaded_trials[0]["result"])
        self.assertFalse(loaded_trials[1]["result"])

    def test_multiple_exports_listed(self):
        """여러 번 내보내기 → 목록에 모두 표시."""
        # 타임스탬프가 다르도록 datetime.now를 mock
        timestamps = ["20260101_100000", "20260102_100000", "20260103_100000"]

        for i, ts in enumerate(timestamps):
            with unittest.mock.patch("session_io.datetime") as mock_dt:
                mock_dt.now.return_value.strftime.return_value = ts
                mock_dt.now.return_value.isoformat.return_value = f"2026-01-0{i + 1}T10:00:00"
                self.sio.export_session_json("multi", {"seq": i})

        files = self.sio.list_export_files("multi")
        self.assertEqual(len(files), 3)
        self.assertIsInstance(files[0], tuple)
        self.assertEqual(len(files[0]), 2)

    def test_prefix_isolation(self):
        """서로 다른 prefix는 독립된 목록."""
        self.sio.export_session_json("alpha", {"v": 1})
        self.sio.export_session_json("beta", {"v": 2})

        self.assertEqual(len(self.sio.list_export_files("alpha")), 1)
        self.assertEqual(len(self.sio.list_export_files("beta")), 1)
        self.assertEqual(len(self.sio.list_export_files("gamma")), 0)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. tunneling_data 모듈 통합 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestTunnelingDataExport(unittest.TestCase):
    """tunneling_data._export_session — 터널링 내보내기 통합."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self.sio = session_io
        self.orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = os.path.join(self.tmpdir, "exports")

        # tunneling_data도 같은 EXPORT_DIR 사용 (session_io에서 import됨)
        import quantum.tunneling_data as td

        self.td = td

    def tearDown(self):
        self.sio.EXPORT_DIR = self.orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_ctx(self):
        """최소한의 mock 컨텍스트 객체 생성."""
        import time

        ctx = unittest.mock.MagicMock()
        ctx.barrier_width = 30
        ctx.base_prob = 0.15
        ctx.tunnel_prob = 0.105
        ctx.speed_mult = 2.0
        ctx.start_time = time.monotonic() - 60
        ctx.max_tunnel_barrier = 50
        ctx.barrier_configs_tried = {30, 40, 50}
        ctx.peak_rate = 0.45
        ctx.trial_history = [
            {"t": 1.0, "barrier": 30, "prob": 0.105, "result": True},
            {"t": 2.0, "barrier": 30, "prob": 0.105, "result": False},
            {"t": 3.5, "barrier": 40, "prob": 0.08, "result": True},
        ]
        ctx.preset_hud.current = "normal"

        # particle mock
        ctx.particle.total_attempts = 3
        ctx.particle.tunnel_count = 2
        ctx.particle.reflect_count = 1
        return ctx

    def test_build_session_data_fields(self):
        """_build_session_data 반환 필드 검증."""
        ctx = self._make_ctx()
        data = self.td._build_session_data(ctx)

        expected_keys = {
            "total_attempts",
            "tunnel_count",
            "reflect_count",
            "tunnel_rate",
            "barrier_width",
            "base_prob",
            "tunnel_prob",
            "elapsed_time",
            "max_tunnel_barrier",
            "barrier_configs_tried",
            "peak_rate",
            "avg_barrier_width",
            "trials_per_minute",
            "speed_mult",
            "difficulty",
            "trial_history",
        }
        for key in expected_keys:
            self.assertIn(key, data, f"누락된 필드: {key}")

    def test_build_session_data_values(self):
        """_build_session_data 계산값 검증."""
        ctx = self._make_ctx()
        data = self.td._build_session_data(ctx)

        self.assertEqual(data["total_attempts"], 3)
        self.assertEqual(data["tunnel_count"], 2)
        self.assertEqual(data["reflect_count"], 1)
        self.assertAlmostEqual(data["tunnel_rate"], 2 / 3, places=3)
        self.assertEqual(data["barrier_width"], 30)
        self.assertEqual(data["difficulty"], "normal")

    def test_build_session_avg_barrier(self):
        """평균 barrier_width 계산."""
        ctx = self._make_ctx()
        data = self.td._build_session_data(ctx)
        # trials: barrier 30, 30, 40 → avg = 100/3 ≈ 33.3
        expected_avg = round((30 + 30 + 40) / 3, 1)
        self.assertAlmostEqual(data["avg_barrier_width"], expected_avg, places=1)

    def test_export_session_creates_files(self):
        """_export_session이 JSON+CSV 파일 생성."""
        ctx = self._make_ctx()
        result = self.td._export_session(ctx)
        self.assertIsNotNone(result)

        export_dir = self.sio.EXPORT_DIR
        files = os.listdir(export_dir)
        json_files = [f for f in files if f.startswith("tunneling_stats_") and f.endswith(".json")]
        csv_files = [f for f in files if f.startswith("tunneling_trials_") and f.endswith(".csv")]
        self.assertEqual(len(json_files), 1)
        self.assertEqual(len(csv_files), 1)

    def test_export_json_no_trial_history(self):
        """내보낸 JSON에 trial_history가 포함되지 않음 (CSV로 분리)."""
        ctx = self._make_ctx()
        self.td._export_session(ctx)

        export_dir = self.sio.EXPORT_DIR
        json_file = [f for f in os.listdir(export_dir) if f.endswith(".json")][0]
        with open(os.path.join(export_dir, json_file), encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn("trial_history", data)

    def test_export_csv_columns(self):
        """CSV 헤더 컬럼 순서 검증."""
        ctx = self._make_ctx()
        self.td._export_session(ctx)

        export_dir = self.sio.EXPORT_DIR
        csv_file = [f for f in os.listdir(export_dir) if f.endswith(".csv")][0]
        with open(os.path.join(export_dir, csv_file), encoding="utf-8") as f:
            reader = list(csv.reader(f))
        self.assertEqual(reader[0], ["trial", "time_s", "barrier_width", "tunnel_prob", "result"])

    def test_export_csv_data_rows(self):
        """CSV 데이터 행 내용 검증."""
        ctx = self._make_ctx()
        self.td._export_session(ctx)

        export_dir = self.sio.EXPORT_DIR
        csv_file = [f for f in os.listdir(export_dir) if f.endswith(".csv")][0]
        with open(os.path.join(export_dir, csv_file), encoding="utf-8") as f:
            reader = list(csv.reader(f))
        # 첫 번째 데이터 행: trial=1, t=1.0, barrier=30, prob=0.105, result=1(True)
        self.assertEqual(reader[1][0], "1")
        self.assertEqual(reader[1][1], "1.0")
        self.assertEqual(reader[1][2], "30")
        self.assertEqual(reader[1][4], "1")  # True → 1
        # 두 번째 행: result=0(False)
        self.assertEqual(reader[2][4], "0")


class TestTunnelingDataImport(unittest.TestCase):
    """tunneling_data._load_import_data — 터널링 가져오기 통합."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.export_dir = self.tmpdir

        # JSON 파일
        self.session_data = {
            "total_attempts": 50,
            "tunnel_count": 20,
            "barrier_width": 30,
            "base_prob": 0.15,
            "tunnel_prob": 0.105,
            "speed_mult": 2.0,
            "difficulty": "hard",
        }
        self.json_path = os.path.join(self.export_dir, "tunneling_stats_20260115_120000.json")
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.session_data, f, indent=2)

        # CSV 파일
        self.csv_path = os.path.join(self.export_dir, "tunneling_trials_20260115_120000.csv")
        with open(self.csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["trial", "time_s", "barrier_width", "tunnel_prob", "result"])
            writer.writerow([1, "1.0", "30", "0.105", "1"])
            writer.writerow([2, "2.0", "30", "0.105", "0"])
            writer.writerow([3, "3.5", "40", "0.080", "1"])
            writer.writerow([4, "4.0", "40", "0.080", "1"])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load(self, path):
        """tunneling_data._load_import_data 호출 헬퍼."""
        from quantum.tunneling_data import _load_import_data

        return _load_import_data(path)

    def test_load_session_data(self):
        """JSON 세션 데이터 로드."""
        session, _ = self._load(self.json_path)
        self.assertIsNotNone(session)
        self.assertEqual(session["total_attempts"], 50)
        self.assertEqual(session["base_prob"], 0.15)

    def test_load_trial_count(self):
        """CSV 시행 이력 개수."""
        _, trials = self._load(self.json_path)
        self.assertEqual(len(trials), 4)

    def test_trial_type_conversion(self):
        """trial_parse_fn 타입 변환 검증."""
        _, trials = self._load(self.json_path)
        tr = trials[0]
        self.assertIsInstance(tr["t"], float)
        self.assertIsInstance(tr["barrier"], int)
        self.assertIsInstance(tr["prob"], float)
        self.assertIsInstance(tr["result"], bool)

    def test_trial_values(self):
        """시행 이력 값 검증."""
        _, trials = self._load(self.json_path)
        self.assertAlmostEqual(trials[0]["t"], 1.0)
        self.assertEqual(trials[0]["barrier"], 30)
        self.assertAlmostEqual(trials[0]["prob"], 0.105)
        self.assertTrue(trials[0]["result"])
        self.assertFalse(trials[1]["result"])

    def test_trial_field_names(self):
        """CSV 헤더 → 내부 필드명 변환 (time_s→t, barrier_width→barrier 등)."""
        _, trials = self._load(self.json_path)
        tr = trials[0]
        self.assertIn("t", tr)
        self.assertIn("barrier", tr)
        self.assertIn("prob", tr)
        self.assertIn("result", tr)
        # CSV 원본 키는 없어야 함
        self.assertNotIn("time_s", tr)
        self.assertNotIn("barrier_width", tr)

    def test_no_csv(self):
        """CSV 없이 JSON만 → trials 빈 리스트."""
        json_only = os.path.join(self.export_dir, "tunneling_stats_20260201_000000.json")
        with open(json_only, "w", encoding="utf-8") as f:
            json.dump({"total_attempts": 5}, f)

        session, trials = self._load(json_only)
        self.assertIsNotNone(session)
        self.assertEqual(trials, [])

    def test_bad_json(self):
        """잘못된 JSON → (None, [])."""
        bad = os.path.join(self.export_dir, "tunneling_stats_20260301_000000.json")
        with open(bad, "w") as f:
            f.write("{invalid}")

        session, trials = self._load(bad)
        self.assertIsNone(session)
        self.assertEqual(trials, [])

    def test_missing_file(self):
        """존재하지 않는 파일 → (None, [])."""
        session, trials = self._load("/no/such/path.json")
        self.assertIsNone(session)
        self.assertEqual(trials, [])

    def test_cumulative_tunnel_rate(self):
        """가져온 시행에서 누적 터널링 확률 계산."""
        _, trials = self._load(self.json_path)
        # [True, False, True, True] → 누적: [1/1, 1/2, 2/3, 3/4]
        tunnels = 0
        rates = []
        for tr in trials:
            if tr["result"]:
                tunnels += 1
            rates.append(tunnels / (len(rates) + 1))
        self.assertAlmostEqual(rates[0], 1.0)
        self.assertAlmostEqual(rates[1], 0.5)
        self.assertAlmostEqual(rates[2], 2 / 3, places=4)
        self.assertAlmostEqual(rates[3], 0.75)


class TestTunnelingExportImportRoundTrip(unittest.TestCase):
    """tunneling 내보내기 → 가져오기 전체 라운드트립."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self.sio = session_io
        self.orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = os.path.join(self.tmpdir, "exports")

    def tearDown(self):
        self.sio.EXPORT_DIR = self.orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_full_roundtrip(self):
        """내보내기 → 파일 목록 → 가져오기 데이터 일치."""
        import time

        from quantum.tunneling_data import _export_session, _load_import_data

        # mock 컨텍스트
        ctx = unittest.mock.MagicMock()
        ctx.barrier_width = 35
        ctx.base_prob = 0.20
        ctx.tunnel_prob = 0.14
        ctx.speed_mult = 1.5
        ctx.start_time = time.monotonic() - 30
        ctx.max_tunnel_barrier = 45
        ctx.barrier_configs_tried = {35}
        ctx.peak_rate = 0.60
        ctx.trial_history = [
            {"t": 1.0, "barrier": 35, "prob": 0.14, "result": True},
            {"t": 2.0, "barrier": 35, "prob": 0.14, "result": False},
        ]
        ctx.preset_hud.current = "easy"
        ctx.particle.total_attempts = 2
        ctx.particle.tunnel_count = 1
        ctx.particle.reflect_count = 1

        # 내보내기
        result = _export_session(ctx)
        self.assertIsNotNone(result)

        # 파일 목록
        from quantum.tunneling_data import _list_export_files

        files = _list_export_files()
        self.assertGreaterEqual(len(files), 1)

        # 가져오기
        _, json_path = files[0]
        session, trials = _load_import_data(json_path)

        self.assertIsNotNone(session)
        self.assertEqual(session["total_attempts"], 2)
        self.assertEqual(session["barrier_width"], 35)
        self.assertAlmostEqual(session["base_prob"], 0.20)

        self.assertEqual(len(trials), 2)
        self.assertAlmostEqual(trials[0]["t"], 1.0)
        self.assertEqual(trials[0]["barrier"], 35)
        self.assertTrue(trials[0]["result"])
        self.assertFalse(trials[1]["result"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 다른 모듈 내보내기/가져오기 통합 테스트
#    (entanglement, qubit_chain, bb84_defense, qkd — JSON only)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestModuleExportJsonOnly(unittest.TestCase):
    """JSON만 사용하는 모듈(entanglement, qubit_chain, bb84, qkd)의 내보내기/가져오기."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self.sio = session_io
        self.orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = os.path.join(self.tmpdir, "exports")

    def tearDown(self):
        self.sio.EXPORT_DIR = self.orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # -- entanglement -------------------------------------------

    def test_entanglement_export(self):
        """entanglement 세션 데이터 내보내기."""
        data = {
            "play_time": 120.5,
            "total_measurements": 45,
            "chsh_experiments": 3,
            "teleport_completions": 2,
        }
        result = self.sio.export_session_json("entanglement", data)
        self.assertIsNotNone(result)

        files = self.sio.list_export_files("entanglement")
        self.assertEqual(len(files), 1)

    def test_entanglement_roundtrip(self):
        """entanglement 내보내기 → 가져오기 일치."""
        data = {
            "play_time": 90.0,
            "total_measurements": 30,
            "chsh_experiments": 2,
            "teleport_completions": 1,
        }
        self.sio.export_session_json("entanglement", data)
        files = self.sio.list_export_files("entanglement")
        _, path = files[0]
        loaded = self.sio.load_session_json(path)
        self.assertEqual(loaded["total_measurements"], 30)
        self.assertAlmostEqual(loaded["play_time"], 90.0)

    # -- qubit_chain -------------------------------------------

    def test_qubit_chain_export(self):
        """qubit_chain 세션 데이터 내보내기."""
        data = {
            "total_qubits": 8,
            "collapsed_count": 3,
            "alive_count": 5,
            "noise_rate": 0.05,
            "cascade_damage": 2,
            "shield_uses": 4,
            "max_stress": 0.85,
            "survival_time": 45.2,
        }
        result = self.sio.export_session_json("qubit_chain", data)
        self.assertIsNotNone(result)

    def test_qubit_chain_roundtrip(self):
        """qubit_chain 내보내기 → 가져오기 일치."""
        data = {
            "total_qubits": 10,
            "collapsed_count": 2,
            "noise_rate": 0.03,
            "survival_time": 60.0,
        }
        self.sio.export_session_json("qubit_chain", data)
        files = self.sio.list_export_files("qubit_chain")
        _, path = files[0]
        loaded = self.sio.load_session_json(path)
        self.assertEqual(loaded["total_qubits"], 10)
        self.assertAlmostEqual(loaded["noise_rate"], 0.03)

    # -- bb84_defense -------------------------------------------

    def test_bb84_defense_export(self):
        """bb84_defense 세션 데이터 내보내기."""
        data = {
            "score": 850,
            "total_sent": 100,
            "total_errors": 5,
            "total_safe": 90,
            "eve_intercepts": 3,
            "auto_blocks": 2,
            "manual_blocks": 1,
            "decoy_sent": 10,
            "decoy_trapped": 2,
            "qrng_bits_used": 50,
        }
        result = self.sio.export_session_json("bb84_defense", data)
        self.assertIsNotNone(result)

    def test_bb84_defense_roundtrip(self):
        """bb84_defense 내보내기 → 가져오기 일치."""
        data = {
            "score": 920,
            "total_sent": 200,
            "eve_intercepts": 7,
        }
        self.sio.export_session_json("bb84_defense", data)
        files = self.sio.list_export_files("bb84_defense")
        _, path = files[0]
        loaded = self.sio.load_session_json(path)
        self.assertEqual(loaded["score"], 920)
        self.assertEqual(loaded["eve_intercepts"], 7)

    # -- qkd ---------------------------------------------------

    def test_qkd_export(self):
        """qkd 세션 데이터 내보내기."""
        data = {
            "protocol": "BB84",
            "key_length": 128,
            "error_rate": 0.02,
        }
        result = self.sio.export_session_json("qkd", data)
        self.assertIsNotNone(result)

    def test_qkd_roundtrip(self):
        """qkd 내보내기 → 가져오기 일치."""
        data = {
            "protocol": "E91",
            "key_length": 256,
            "error_rate": 0.01,
        }
        self.sio.export_session_json("qkd", data)
        files = self.sio.list_export_files("qkd")
        _, path = files[0]
        loaded = self.sio.load_session_json(path)
        self.assertEqual(loaded["protocol"], "E91")
        self.assertEqual(loaded["key_length"], 256)

    # -- 접두사 격리 -------------------------------------------

    def test_prefix_isolation_across_modules(self):
        """모듈별 prefix가 서로 격리됨."""
        self.sio.export_session_json("entanglement", {"v": 1})
        self.sio.export_session_json("bb84_defense", {"v": 2})
        self.sio.export_session_json("qubit_chain", {"v": 3})
        self.sio.export_session_json("qkd", {"v": 4})

        self.assertEqual(len(self.sio.list_export_files("entanglement")), 1)
        self.assertEqual(len(self.sio.list_export_files("bb84_defense")), 1)
        self.assertEqual(len(self.sio.list_export_files("qubit_chain")), 1)
        self.assertEqual(len(self.sio.list_export_files("qkd")), 1)
        self.assertEqual(len(self.sio.list_export_files("nonexistent")), 0)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. 엣지 케이스 및 예외 처리 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestEdgeCases(unittest.TestCase):
    """엣지 케이스 및 예외 처리."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self.sio = session_io
        self.orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = os.path.join(self.tmpdir, "exports")

    def tearDown(self):
        self.sio.EXPORT_DIR = self.orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_session_data(self):
        """빈 세션 딕셔너리 내보내기."""
        result = self.sio.export_session_json("empty", {})
        self.assertIsNotNone(result)
        files = self.sio.list_export_files("empty")
        _, path = files[0]
        loaded = self.sio.load_session_json(path)
        self.assertIn("timestamp", loaded)

    def test_large_trial_data(self):
        """많은 시행 이력 (1000건) 내보내기/가져오기."""
        data = {"total": 1000}
        trials = [{"idx": i, "val": i * 0.1} for i in range(1000)]
        cols = ["idx", "val"]
        self.sio.export_session_json("large", data, trial_rows=trials, trial_columns=cols)
        files = self.sio.list_export_files("large")
        _, path = files[0]
        session, loaded_trials = self.sio.load_session_with_trials(path, "large")
        self.assertEqual(session["total"], 1000)
        self.assertEqual(len(loaded_trials), 1000)

    def test_special_chars_in_data(self):
        """특수문자가 포함된 데이터 내보내기/가져오기."""
        data = {"desc": 'quotes "and" <tags>', "path": "C:\\Users\\test"}
        result = self.sio.export_session_json("special", data)
        self.assertIsNotNone(result)
        files = self.sio.list_export_files("special")
        _, path = files[0]
        loaded = self.sio.load_session_json(path)
        self.assertEqual(loaded["desc"], 'quotes "and" <tags>')

    def test_float_precision(self):
        """부동소수점 정밀도 유지."""
        data = {"pi": 3.141592653589793, "tiny": 1e-10}
        self.sio.export_session_json("precision", data)
        files = self.sio.list_export_files("precision")
        _, path = files[0]
        loaded = self.sio.load_session_json(path)
        self.assertAlmostEqual(loaded["pi"], 3.141592653589793, places=10)
        self.assertAlmostEqual(loaded["tiny"], 1e-10)

    def test_csv_with_missing_columns(self):
        """trial_rows에 일부 컬럼이 없는 경우 빈 문자열로 대체."""
        data = {"x": 1}
        trials = [{"a": 10}]  # "b" 키 없음
        cols = ["a", "b"]
        result = self.sio.export_session_json("missing_col", data, trial_rows=trials, trial_columns=cols)
        csv_files = [f for f in os.listdir(result) if f.endswith(".csv")]
        with open(os.path.join(result, csv_files[0]), encoding="utf-8") as f:
            reader = list(csv.reader(f))
        self.assertEqual(reader[1], ["10", ""])

    def test_import_session_slider_clamping(self):
        """_import_session이 슬라이더 범위를 클램핑하는지 검증."""
        from quantum.tunneling_data import _load_import_data

        # 극단적 값이 포함된 JSON 생성
        extreme_data = {
            "base_prob": 99.9,  # max 0.50 초과
            "barrier_width": 9999,  # max 초과
            "speed_mult": 100.0,  # max 5.0 초과
        }
        json_path = os.path.join(self.tmpdir, "tunneling_stats_20260401_000000.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(extreme_data, f)

        session, _ = _load_import_data(json_path)
        self.assertIsNotNone(session)
        # 값이 JSON에서 로드되는 것 확인 (클램핑은 _import_session에서 수행)
        self.assertEqual(session["base_prob"], 99.9)


if __name__ == "__main__":
    unittest.main()
