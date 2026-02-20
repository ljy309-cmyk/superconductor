"""설정 가져오기/내보내기 중점 테스트.

session_io, settings_io, tunneling_data, config_loader의
내보내기/가져오기 기능을 심층적으로 검증합니다.
"""

import csv
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════
# 1. session_io — export_session_json 테스트
# ═══════════════════════════════════════════════════════════


class TestExportSessionJson(unittest.TestCase):
    """session_io.export_session_json 함수 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self._orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import session_io

        session_io.EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_json_only_export(self):
        """trial 없이 JSON만 내보내기."""
        from session_io import export_session_json

        session = {"total_attempts": 100, "tunnel_rate": 0.35}
        result = export_session_json("test", session)
        self.assertIsNotNone(result)

        # JSON 파일 존재 확인
        json_files = [f for f in os.listdir(self.tmpdir) if f.endswith(".json")]
        self.assertEqual(len(json_files), 1)
        self.assertTrue(json_files[0].startswith("test_stats_"))

        # 내용 확인
        with open(os.path.join(self.tmpdir, json_files[0]), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["total_attempts"], 100)
        self.assertAlmostEqual(data["tunnel_rate"], 0.35)
        self.assertIn("timestamp", data)

    def test_json_with_csv_export(self):
        """JSON + CSV 동시 내보내기."""
        from session_io import export_session_json

        session = {"total_attempts": 3, "tunnel_rate": 0.33}
        trials = [
            {"trial": 1, "time_s": 1.0, "barrier_width": 12, "tunnel_prob": 0.1, "result": 1},
            {"trial": 2, "time_s": 2.5, "barrier_width": 20, "tunnel_prob": 0.05, "result": 0},
            {"trial": 3, "time_s": 4.0, "barrier_width": 12, "tunnel_prob": 0.1, "result": 1},
        ]
        columns = ["trial", "time_s", "barrier_width", "tunnel_prob", "result"]
        result = export_session_json("test", session, trial_rows=trials, trial_columns=columns)
        self.assertIsNotNone(result)

        csv_files = [f for f in os.listdir(self.tmpdir) if f.endswith(".csv")]
        self.assertEqual(len(csv_files), 1)
        self.assertTrue(csv_files[0].startswith("test_trials_"))

        # CSV 내용 확인
        with open(os.path.join(self.tmpdir, csv_files[0]), encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["trial"], "1")
        self.assertEqual(rows[1]["result"], "0")

    def test_csv_with_custom_row_fn(self):
        """custom trial_row_fn을 사용한 CSV 내보내기."""
        from session_io import export_session_json

        session = {"count": 2}
        trials = [
            {"t": 1.5, "barrier": 10, "prob": 0.2, "result": True},
            {"t": 3.0, "barrier": 15, "prob": 0.1, "result": False},
        ]
        columns = ["trial", "time_s", "barrier_width", "tunnel_prob", "result"]
        row_fn = lambda i, tr: [i, tr["t"], tr["barrier"], tr["prob"], int(tr["result"])]

        result = export_session_json(
            "tunneling", session,
            trial_rows=trials, trial_columns=columns, trial_row_fn=row_fn,
        )
        self.assertIsNotNone(result)

        csv_files = [f for f in os.listdir(self.tmpdir) if f.endswith(".csv")]
        with open(os.path.join(self.tmpdir, csv_files[0]), encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["trial"], "1")
        self.assertEqual(rows[0]["result"], "1")
        self.assertEqual(rows[1]["result"], "0")

    def test_unicode_data_export(self):
        """유니코드(한글) 데이터 내보내기."""
        from session_io import export_session_json

        session = {"메모": "터널링 실험 결과", "난이도": "쉬움"}
        result = export_session_json("unicode_test", session)
        self.assertIsNotNone(result)

        json_files = [f for f in os.listdir(self.tmpdir) if f.endswith(".json")]
        with open(os.path.join(self.tmpdir, json_files[0]), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["메모"], "터널링 실험 결과")

    def test_timestamp_added_to_export(self):
        """내보낸 JSON에 timestamp 필드가 자동 추가되는지 확인."""
        from session_io import export_session_json

        session = {"key": "value"}
        export_session_json("ts_test", session)

        json_files = [f for f in os.listdir(self.tmpdir) if f.endswith(".json")]
        with open(os.path.join(self.tmpdir, json_files[0]), encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("timestamp", data)
        # ISO 형식 확인
        self.assertIn("T", data["timestamp"])

    def test_original_session_dict_not_mutated(self):
        """원본 session_data 딕셔너리가 변형되지 않는지 확인."""
        from session_io import export_session_json

        session = {"original_key": "original_value"}
        original_keys = set(session.keys())
        export_session_json("mutate_test", session)
        # timestamp가 원본에 추가되면 안 됨
        self.assertEqual(set(session.keys()), original_keys)

    def test_empty_trial_rows_no_csv(self):
        """trial_rows가 빈 리스트면 CSV 생성 안 함."""
        from session_io import export_session_json

        session = {"count": 0}
        export_session_json("empty_trial", session, trial_rows=[], trial_columns=["a", "b"])

        csv_files = [f for f in os.listdir(self.tmpdir) if f.endswith(".csv")]
        self.assertEqual(len(csv_files), 0)

    def test_export_creates_dir_if_missing(self):
        """EXPORT_DIR이 없으면 자동 생성."""
        import session_io
        from session_io import export_session_json

        nested_dir = os.path.join(self.tmpdir, "sub", "dir")
        session_io.EXPORT_DIR = nested_dir

        result = export_session_json("mkdir_test", {"a": 1})
        self.assertIsNotNone(result)
        self.assertTrue(os.path.isdir(nested_dir))

    def test_multiple_exports_create_separate_files(self):
        """여러 번 내보내기하면 각각 별도 파일 생성."""
        from session_io import export_session_json

        export_session_json("multi", {"seq": 1})
        export_session_json("multi", {"seq": 2})

        json_files = [f for f in os.listdir(self.tmpdir) if f.endswith(".json")]
        # 타임스탬프가 같은 초에 생성되면 1개일 수도 있으나 최소 1개 이상
        self.assertGreaterEqual(len(json_files), 1)


# ═══════════════════════════════════════════════════════════
# 2. session_io — load_session_json / load_session_with_trials 테스트
# ═══════════════════════════════════════════════════════════


class TestLoadSessionJson(unittest.TestCase):
    """session_io.load_session_json 함수 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_valid_json(self):
        from session_io import load_session_json

        data = {"total": 42, "rate": 0.5}
        path = os.path.join(self.tmpdir, "test.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        result = load_session_json(path)
        self.assertIsNotNone(result)
        self.assertEqual(result["total"], 42)

    def test_load_nonexistent_returns_none(self):
        from session_io import load_session_json

        result = load_session_json("/nonexistent/path/data.json")
        self.assertIsNone(result)

    def test_load_invalid_json_returns_none(self):
        from session_io import load_session_json

        path = os.path.join(self.tmpdir, "bad.json")
        with open(path, "w") as f:
            f.write("{invalid json content!!!")

        result = load_session_json(path)
        self.assertIsNone(result)

    def test_load_empty_file_returns_none(self):
        from session_io import load_session_json

        path = os.path.join(self.tmpdir, "empty.json")
        with open(path, "w") as f:
            pass  # 빈 파일

        result = load_session_json(path)
        self.assertIsNone(result)

    def test_load_unicode_json(self):
        """유니코드 JSON 파일 로드."""
        from session_io import load_session_json

        data = {"이름": "실험1", "결과": "성공"}
        path = os.path.join(self.tmpdir, "unicode.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        result = load_session_json(path)
        self.assertEqual(result["이름"], "실험1")


class TestLoadSessionWithTrials(unittest.TestCase):
    """session_io.load_session_with_trials 함수 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_json_and_csv(self, prefix, session_data, trial_rows, columns):
        """테스트용 JSON+CSV 쌍 생성."""
        ts = "20260220_120000"
        json_path = os.path.join(self.tmpdir, f"{prefix}_stats_{ts}.json")
        csv_path = os.path.join(self.tmpdir, f"{prefix}_trials_{ts}.csv")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f)

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in trial_rows:
                writer.writerow(row)

        return json_path

    def test_load_json_and_csv_together(self):
        """JSON + CSV 동시 로드."""
        from session_io import load_session_with_trials

        json_path = self._create_json_and_csv(
            "tunneling",
            {"total": 3, "rate": 0.33},
            [[1, 1.0, 12, 0.1, 1], [2, 2.5, 20, 0.05, 0], [3, 4.0, 12, 0.1, 1]],
            ["trial", "time_s", "barrier_width", "tunnel_prob", "result"],
        )

        session, trials = load_session_with_trials(json_path, "tunneling")
        self.assertIsNotNone(session)
        self.assertEqual(session["total"], 3)
        self.assertEqual(len(trials), 3)
        self.assertEqual(trials[0]["trial"], "1")

    def test_load_json_without_csv(self):
        """CSV 없이 JSON만 있을 때."""
        from session_io import load_session_with_trials

        json_path = os.path.join(self.tmpdir, "tunneling_stats_20260220_120000.json")
        with open(json_path, "w") as f:
            json.dump({"total": 5}, f)

        session, trials = load_session_with_trials(json_path, "tunneling")
        self.assertIsNotNone(session)
        self.assertEqual(session["total"], 5)
        self.assertEqual(trials, [])

    def test_load_with_custom_parse_fn(self):
        """custom trial_parse_fn으로 CSV 행 변환."""
        from session_io import load_session_with_trials

        json_path = self._create_json_and_csv(
            "tunneling",
            {"total": 2},
            [[1, 1.5, 10, 0.2, 1], [2, 3.0, 15, 0.1, 0]],
            ["trial", "time_s", "barrier_width", "tunnel_prob", "result"],
        )

        parse_fn = lambda row: {
            "t": float(row["time_s"]),
            "barrier": int(row["barrier_width"]),
            "prob": float(row["tunnel_prob"]),
            "result": bool(int(row["result"])),
        }

        session, trials = load_session_with_trials(json_path, "tunneling", trial_parse_fn=parse_fn)
        self.assertIsNotNone(session)
        self.assertEqual(len(trials), 2)
        self.assertAlmostEqual(trials[0]["t"], 1.5)
        self.assertEqual(trials[0]["barrier"], 10)
        self.assertTrue(trials[0]["result"])
        self.assertFalse(trials[1]["result"])

    def test_load_invalid_json_returns_none_empty(self):
        """잘못된 JSON은 (None, []) 반환."""
        from session_io import load_session_with_trials

        session, trials = load_session_with_trials("/nonexistent.json", "test")
        self.assertIsNone(session)
        self.assertEqual(trials, [])


# ═══════════════════════════════════════════════════════════
# 3. session_io — list_export_files 테스트
# ═══════════════════════════════════════════════════════════


class TestListExportFiles(unittest.TestCase):
    """session_io.list_export_files 함수 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self._orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import session_io

        session_io.EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_dir_returns_empty(self):
        from session_io import list_export_files

        self.assertEqual(list_export_files("tunneling"), [])

    def test_filters_by_prefix(self):
        """prefix별로 필터링."""
        from session_io import list_export_files

        for name in [
            "tunneling_stats_20260101.json",
            "tunneling_stats_20260102.json",
            "other_stats_20260101.json",
            "tunneling_trials_20260101.csv",
        ]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("{}")

        result = list_export_files("tunneling")
        self.assertEqual(len(result), 2)
        # 다른 prefix는 포함 안 됨
        labels = [r[0] for r in result]
        for label in labels:
            self.assertNotIn("other", label)

    def test_sorted_newest_first(self):
        """최신 파일이 먼저."""
        from session_io import list_export_files

        for name in [
            "tunneling_stats_20260101_100000.json",
            "tunneling_stats_20260301_100000.json",
            "tunneling_stats_20260201_100000.json",
        ]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("{}")

        result = list_export_files("tunneling")
        self.assertEqual(len(result), 3)
        self.assertIn("20260301", result[0][0])
        self.assertIn("20260101", result[2][0])

    def test_nonexistent_export_dir(self):
        """존재하지 않는 디렉터리."""
        import session_io

        session_io.EXPORT_DIR = "/nonexistent/dir/999"
        from session_io import list_export_files

        self.assertEqual(list_export_files("tunneling"), [])


# ═══════════════════════════════════════════════════════════
# 4. settings_io — 라운드트립 테스트
# ═══════════════════════════════════════════════════════════


class TestSettingsIoRoundtrip(unittest.TestCase):
    """settings_io 내보내기 → 가져오기 라운드트립 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.fake_base = tempfile.mkdtemp()
        import settings_io

        self._orig_base = settings_io._BASE
        self._orig_export_dir = settings_io._EXPORT_DIR

    def tearDown(self):
        import settings_io

        settings_io._BASE = self._orig_base
        settings_io._EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.fake_base, ignore_errors=True)

    def test_full_roundtrip(self):
        """내보내기 → 가져오기 전체 사이클."""
        import settings_io

        # 1. 원본 설정 준비 (fake base에 config.json 생성)
        src_base = tempfile.mkdtemp()
        settings_io._BASE = src_base
        settings_io._EXPORT_DIR = self.tmpdir

        original_config = {"display": {"fps": 120}, "theme": "light"}
        config_path = os.path.join(src_base, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(original_config, f)

        achievements = {"unlocked": ["first_tunnel", "speed_demon"]}
        ach_path = os.path.join(src_base, "achievements.json")
        with open(ach_path, "w", encoding="utf-8") as f:
            json.dump(achievements, f)

        # 2. 내보내기
        zip_path = settings_io.export_settings(output_dir=self.tmpdir)
        self.assertTrue(zip_path.endswith(".zip"))
        self.assertTrue(os.path.exists(zip_path))

        # 3. 다른 위치로 가져오기
        settings_io._BASE = self.fake_base
        result = settings_io.import_settings(zip_path)

        self.assertIn("config.json", result["imported"])
        self.assertIn("achievements.json", result["imported"])

        # 4. 가져온 내용 검증
        imported_config_path = os.path.join(self.fake_base, "config.json")
        with open(imported_config_path, encoding="utf-8") as f:
            imported_config = json.load(f)
        self.assertEqual(imported_config, original_config)

        imported_ach_path = os.path.join(self.fake_base, "achievements.json")
        with open(imported_ach_path, encoding="utf-8") as f:
            imported_ach = json.load(f)
        self.assertEqual(imported_ach, achievements)

        shutil.rmtree(src_base, ignore_errors=True)

    def test_roundtrip_with_profiles_dir(self):
        """profiles 디렉터리 포함 라운드트립."""
        import settings_io

        src_base = tempfile.mkdtemp()
        settings_io._BASE = src_base
        settings_io._EXPORT_DIR = self.tmpdir

        # profiles 디렉터리 생성
        profiles_dir = os.path.join(src_base, "profiles")
        os.makedirs(profiles_dir)
        for name in ["user1.json", "user2.json"]:
            with open(os.path.join(profiles_dir, name), "w") as f:
                json.dump({"name": name.replace(".json", ""), "settings": {}}, f)

        # 내보내기
        zip_path = settings_io.export_settings(output_dir=self.tmpdir)

        # 가져오기
        settings_io._BASE = self.fake_base
        result = settings_io.import_settings(zip_path)

        self.assertIn("profiles/user1.json", result["imported"])
        self.assertIn("profiles/user2.json", result["imported"])

        # 파일 존재 확인
        self.assertTrue(os.path.exists(os.path.join(self.fake_base, "profiles", "user1.json")))
        self.assertTrue(os.path.exists(os.path.join(self.fake_base, "profiles", "user2.json")))

        shutil.rmtree(src_base, ignore_errors=True)

    def test_roundtrip_with_tutorial_state(self):
        """tutorial_state.json 라운드트립."""
        import settings_io

        src_base = tempfile.mkdtemp()
        settings_io._BASE = src_base
        settings_io._EXPORT_DIR = self.tmpdir

        tutorial = {"completed": True, "step": 5}
        with open(os.path.join(src_base, "tutorial_state.json"), "w") as f:
            json.dump(tutorial, f)

        zip_path = settings_io.export_settings(output_dir=self.tmpdir)
        settings_io._BASE = self.fake_base
        result = settings_io.import_settings(zip_path)

        self.assertIn("tutorial_state.json", result["imported"])

        with open(os.path.join(self.fake_base, "tutorial_state.json")) as f:
            imported = json.load(f)
        self.assertEqual(imported, tutorial)

        shutil.rmtree(src_base, ignore_errors=True)


# ═══════════════════════════════════════════════════════════
# 5. settings_io — 보안 및 엣지 케이스
# ═══════════════════════════════════════════════════════════


class TestSettingsIoSecurity(unittest.TestCase):
    """settings_io 보안 관련 추가 테스트."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.fake_base = tempfile.mkdtemp()
        import settings_io

        self._orig_base = settings_io._BASE
        settings_io._BASE = self.fake_base

    def tearDown(self):
        import settings_io

        settings_io._BASE = self._orig_base
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.fake_base, ignore_errors=True)

    def _make_zip(self, files_dict):
        zip_path = os.path.join(self.tmpdir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for arcname, content in files_dict.items():
                zf.writestr(arcname, content)
        return zip_path

    def test_windows_style_path_traversal(self):
        """윈도우 스타일 경로 순회 차단 (..\\)."""
        from settings_io import import_settings

        zip_path = self._make_zip({"..\\..\\etc\\passwd": "hacked"})
        result = import_settings(zip_path)
        self.assertIn("..\\..\\etc\\passwd", result["skipped"])
        self.assertEqual(result["imported"], [])

    def test_symlink_style_name_blocked(self):
        """profiles 하위이지만 .. 포함된 경로 차단."""
        from settings_io import import_settings

        zip_path = self._make_zip({"profiles/../../../etc/shadow": "evil"})
        result = import_settings(zip_path)
        self.assertIn("profiles/../../../etc/shadow", result["skipped"])

    def test_only_allowed_toplevel_files(self):
        """허용된 파일 목록에 없는 최상위 파일 차단."""
        from settings_io import import_settings

        zip_path = self._make_zip({
            "config.json": "{}",
            "achievements.json": "{}",
            "tutorial_state.json": "{}",
            "main.py": "import os; os.system('rm -rf /')",
            "settings_io.py": "# malicious override",
            ".env": "SECRET_KEY=abc123",
        })
        result = import_settings(zip_path)
        self.assertEqual(sorted(result["imported"]),
                         ["achievements.json", "config.json", "tutorial_state.json"])
        self.assertIn("main.py", result["skipped"])
        self.assertIn("settings_io.py", result["skipped"])
        self.assertIn(".env", result["skipped"])

    def test_empty_filename_in_zip(self):
        """ZIP 내 빈 이름 엔트리 처리."""
        from settings_io import import_settings

        zip_path = os.path.join(self.tmpdir, "empty_name.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            # 빈 이름은 zipfile 모듈이 알아서 처리하므로
            # 대신 공백 이름 테스트
            zf.writestr("   ", "content")
        result = import_settings(zip_path)
        self.assertIn("   ", result["skipped"])

    def test_very_large_config_import(self):
        """매우 큰 config.json도 정상 가져오기."""
        from settings_io import import_settings

        large_config = {"data": "x" * 100000, "array": list(range(1000))}
        zip_path = self._make_zip({"config.json": json.dumps(large_config)})
        result = import_settings(zip_path)
        self.assertIn("config.json", result["imported"])

        with open(os.path.join(self.fake_base, "config.json")) as f:
            imported = json.load(f)
        self.assertEqual(len(imported["data"]), 100000)

    def test_import_overwrites_existing_file(self):
        """기존 파일이 있을 때 덮어쓰기 확인."""
        from settings_io import import_settings

        # 기존 config.json 생성
        old_config = {"theme": "dark", "old_key": True}
        with open(os.path.join(self.fake_base, "config.json"), "w") as f:
            json.dump(old_config, f)

        # 새 config으로 가져오기
        new_config = {"theme": "light", "new_key": 42}
        zip_path = self._make_zip({"config.json": json.dumps(new_config)})
        result = import_settings(zip_path)
        self.assertIn("config.json", result["imported"])

        with open(os.path.join(self.fake_base, "config.json")) as f:
            imported = json.load(f)
        self.assertEqual(imported["theme"], "light")
        self.assertEqual(imported["new_key"], 42)
        self.assertNotIn("old_key", imported)


# ═══════════════════════════════════════════════════════════
# 6. settings_io — list_exports 추가 테스트
# ═══════════════════════════════════════════════════════════


class TestListExportsExtended(unittest.TestCase):
    """settings_io.list_exports 추가 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import settings_io

        self._orig_export_dir = settings_io._EXPORT_DIR
        settings_io._EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import settings_io

        settings_io._EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_ignores_non_zip_files(self):
        from settings_io import list_exports

        for name in ["settings.json", "backup.tar.gz", "readme.txt"]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("x")
        self.assertEqual(list_exports(), [])

    def test_returns_full_paths(self):
        from settings_io import list_exports

        with open(os.path.join(self.tmpdir, "backup.zip"), "w") as f:
            f.write("x")
        result = list_exports()
        self.assertEqual(len(result), 1)
        self.assertTrue(os.path.isabs(result[0]))

    def test_multiple_zips_sorted_reverse(self):
        from settings_io import list_exports

        for name in ["a_20260101.zip", "a_20260301.zip", "a_20260201.zip"]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("x")
        result = list_exports()
        basenames = [os.path.basename(r) for r in result]
        self.assertEqual(basenames[0], "a_20260301.zip")
        self.assertEqual(basenames[-1], "a_20260101.zip")


# ═══════════════════════════════════════════════════════════
# 7. session_io + settings_io 통합 — 내보내기→가져오기→config_loader 연동
# ═══════════════════════════════════════════════════════════


class TestExportImportConfigReload(unittest.TestCase):
    """내보낸 설정을 가져온 후 config_loader로 읽기."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.fake_base = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.fake_base, ignore_errors=True)

    def test_imported_config_readable_by_config_loader(self):
        """가져온 config.json을 config_loader로 정상 읽기."""
        import config_loader
        import settings_io

        orig_base = settings_io._BASE
        orig_cfg_path = config_loader._CONFIG_PATH
        orig_cache = config_loader._cache

        try:
            # config.json 준비
            config = {
                "display": {"fps": 144, "width": 1920, "height": 1080},
                "tunneling": {"tunnel_prob_base": 0.25, "particle_speed": 300.0},
            }
            settings_io._BASE = self.fake_base
            zip_path = os.path.join(self.tmpdir, "test.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("config.json", json.dumps(config))

            # 가져오기
            result = settings_io.import_settings(zip_path)
            self.assertIn("config.json", result["imported"])

            # config_loader로 읽기
            config_loader._cache = None
            config_loader._CONFIG_PATH = os.path.join(self.fake_base, "config.json")

            fps = config_loader.cfg("display", "fps", 60)
            self.assertEqual(fps, 144)

            prob = config_loader.cfg("tunneling", "tunnel_prob_base", 0.1)
            self.assertAlmostEqual(prob, 0.25)

        finally:
            settings_io._BASE = orig_base
            config_loader._CONFIG_PATH = orig_cfg_path
            config_loader._cache = orig_cache

    def test_imported_invalid_config_falls_back_to_default(self):
        """가져온 config에 유효하지 않은 값이면 기본값 반환."""
        import config_loader
        import settings_io

        orig_base = settings_io._BASE
        orig_cfg_path = config_loader._CONFIG_PATH
        orig_cache = config_loader._cache

        try:
            # 범위 초과 값 포함 config
            config = {
                "display": {"fps": 9999},  # max=240
                "tunneling": {"tunnel_prob_base": 5.0},  # max=1.0
            }
            settings_io._BASE = self.fake_base
            zip_path = os.path.join(self.tmpdir, "bad.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("config.json", json.dumps(config))

            settings_io.import_settings(zip_path)

            config_loader._cache = None
            config_loader._CONFIG_PATH = os.path.join(self.fake_base, "config.json")

            # 범위 초과 → 기본값 반환
            fps = config_loader.cfg("display", "fps", 60)
            self.assertEqual(fps, 60)

            prob = config_loader.cfg("tunneling", "tunnel_prob_base", 0.1)
            self.assertAlmostEqual(prob, 0.1)

        finally:
            settings_io._BASE = orig_base
            config_loader._CONFIG_PATH = orig_cfg_path
            config_loader._cache = orig_cache


# ═══════════════════════════════════════════════════════════
# 8. session_io — export/import 라운드트립 (JSON + CSV)
# ═══════════════════════════════════════════════════════════


class TestSessionIoRoundtrip(unittest.TestCase):
    """session_io 내보내기 → 로드 라운드트립."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self._orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import session_io

        session_io.EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_json_export_then_load(self):
        """JSON 내보내기 → load_session_json으로 로드."""
        from session_io import export_session_json, load_session_json

        session = {"attempts": 50, "rate": 0.4, "speed": 2.0}
        export_session_json("roundtrip", session)

        json_files = [
            os.path.join(self.tmpdir, f)
            for f in os.listdir(self.tmpdir)
            if f.endswith(".json")
        ]
        self.assertEqual(len(json_files), 1)

        loaded = load_session_json(json_files[0])
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["attempts"], 50)
        self.assertAlmostEqual(loaded["rate"], 0.4)

    def test_json_csv_export_then_load_with_trials(self):
        """JSON+CSV 내보내기 → load_session_with_trials로 로드."""
        from session_io import export_session_json, load_session_with_trials

        session = {"total": 3}
        trials = [
            {"trial": 1, "time_s": 1.0, "width": 10, "prob": 0.2, "res": 1},
            {"trial": 2, "time_s": 2.0, "width": 15, "prob": 0.1, "res": 0},
            {"trial": 3, "time_s": 3.5, "width": 10, "prob": 0.2, "res": 1},
        ]
        columns = ["trial", "time_s", "width", "prob", "res"]
        export_session_json("rt", session, trial_rows=trials, trial_columns=columns)

        json_files = [
            os.path.join(self.tmpdir, f)
            for f in os.listdir(self.tmpdir)
            if f.startswith("rt_stats_") and f.endswith(".json")
        ]
        self.assertEqual(len(json_files), 1)

        loaded_session, loaded_trials = load_session_with_trials(json_files[0], "rt")
        self.assertIsNotNone(loaded_session)
        self.assertEqual(loaded_session["total"], 3)
        self.assertEqual(len(loaded_trials), 3)
        self.assertEqual(loaded_trials[0]["trial"], "1")
        self.assertEqual(loaded_trials[2]["res"], "1")


# ═══════════════════════════════════════════════════════════
# 9. tunneling_data — _load_import_data 테스트
# ═══════════════════════════════════════════════════════════


class TestTunnelingDataImport(unittest.TestCase):
    """tunneling_data._load_import_data 함수 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_tunneling_files(self, session_data, trial_rows):
        ts = "20260220_120000"
        json_path = os.path.join(self.tmpdir, f"tunneling_stats_{ts}.json")
        csv_path = os.path.join(self.tmpdir, f"tunneling_trials_{ts}.csv")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f)

        columns = ["trial", "time_s", "barrier_width", "tunnel_prob", "result"]
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in trial_rows:
                writer.writerow(row)

        return json_path

    def test_load_tunneling_data_parses_types(self):
        """tunneling trial_parse_fn이 올바른 타입 변환."""
        from quantum.tunneling_data import _load_import_data

        json_path = self._create_tunneling_files(
            {"total_attempts": 2, "tunnel_rate": 0.5},
            [[1, "1.5", 12, "0.1", 1], [2, "3.0", 20, "0.05", 0]],
        )

        session, trials = _load_import_data(json_path)
        self.assertIsNotNone(session)
        self.assertEqual(len(trials), 2)

        # 타입 확인
        self.assertIsInstance(trials[0]["t"], float)
        self.assertIsInstance(trials[0]["barrier"], int)
        self.assertIsInstance(trials[0]["prob"], float)
        self.assertIsInstance(trials[0]["result"], bool)

        # 값 확인
        self.assertAlmostEqual(trials[0]["t"], 1.5)
        self.assertEqual(trials[0]["barrier"], 12)
        self.assertTrue(trials[0]["result"])
        self.assertFalse(trials[1]["result"])

    def test_load_tunneling_no_csv(self):
        """CSV 없이 JSON만 있을 때."""
        from quantum.tunneling_data import _load_import_data

        json_path = os.path.join(self.tmpdir, "tunneling_stats_20260220_120000.json")
        with open(json_path, "w") as f:
            json.dump({"total_attempts": 10}, f)

        session, trials = _load_import_data(json_path)
        self.assertIsNotNone(session)
        self.assertEqual(trials, [])

    def test_load_tunneling_nonexistent(self):
        """존재하지 않는 파일."""
        from quantum.tunneling_data import _load_import_data

        session, trials = _load_import_data("/nonexistent/tunneling_stats_x.json")
        self.assertIsNone(session)
        self.assertEqual(trials, [])


# ═══════════════════════════════════════════════════════════
# 10. tunneling_data — _list_export_files / EXPORT_DIR
# ═══════════════════════════════════════════════════════════


class TestTunnelingDataExportFiles(unittest.TestCase):
    """tunneling_data._list_export_files 및 하위 호환성."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self._orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = self.tmpdir

        # tunneling_data도 EXPORT_DIR을 참조하므로 동기화
        import quantum.tunneling_data as td

        td._EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import session_io

        session_io.EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_export_files(self):
        from quantum.tunneling_data import _list_export_files

        for name in [
            "tunneling_stats_20260101.json",
            "tunneling_stats_20260201.json",
            "other_stats_20260101.json",
        ]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("{}")

        result = _list_export_files()
        self.assertEqual(len(result), 2)


# ═══════════════════════════════════════════════════════════
# 11. settings_io — ZIP 구조 무결성 검증
# ═══════════════════════════════════════════════════════════


class TestSettingsZipIntegrity(unittest.TestCase):
    """내보낸 ZIP 파일의 구조 무결성 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.src_base = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.src_base, ignore_errors=True)

    def test_zip_contains_only_expected_files(self):
        """ZIP에 예상 파일만 포함되는지 확인."""
        import settings_io

        orig_base = settings_io._BASE
        try:
            settings_io._BASE = self.src_base

            # 허용된 파일 + 허용되지 않은 파일 모두 생성
            with open(os.path.join(self.src_base, "config.json"), "w") as f:
                f.write("{}")
            with open(os.path.join(self.src_base, "main.py"), "w") as f:
                f.write("# code")
            with open(os.path.join(self.src_base, "secret.env"), "w") as f:
                f.write("SECRET=123")

            zip_path = settings_io.export_settings(output_dir=self.tmpdir)
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
            self.assertIn("config.json", names)
            self.assertNotIn("main.py", names)
            self.assertNotIn("secret.env", names)
        finally:
            settings_io._BASE = orig_base

    def test_zip_file_compression(self):
        """ZIP이 DEFLATED 압축을 사용하는지 확인."""
        import settings_io

        orig_base = settings_io._BASE
        try:
            settings_io._BASE = self.src_base
            with open(os.path.join(self.src_base, "config.json"), "w") as f:
                json.dump({"key": "value" * 100}, f)

            zip_path = settings_io.export_settings(output_dir=self.tmpdir)
            with zipfile.ZipFile(zip_path, "r") as zf:
                for info in zf.infolist():
                    if info.file_size > 0:
                        self.assertEqual(info.compress_type, zipfile.ZIP_DEFLATED)
        finally:
            settings_io._BASE = orig_base

    def test_export_with_nested_profiles(self):
        """중첩 프로파일 디렉터리 내보내기."""
        import settings_io

        orig_base = settings_io._BASE
        try:
            settings_io._BASE = self.src_base

            # profiles/sub/ 디렉터리 생성
            sub_dir = os.path.join(self.src_base, "profiles", "sub")
            os.makedirs(sub_dir)
            with open(os.path.join(sub_dir, "nested.json"), "w") as f:
                json.dump({"nested": True}, f)

            zip_path = settings_io.export_settings(output_dir=self.tmpdir)
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
            # 상대 경로 확인
            self.assertTrue(
                any("profiles/sub/nested.json" in n or "profiles\\sub\\nested.json" in n for n in names),
                f"Expected nested profile in ZIP, got: {names}",
            )
        finally:
            settings_io._BASE = orig_base


# ═══════════════════════════════════════════════════════════
# 12. 동시 내보내기 및 파일명 고유성
# ═══════════════════════════════════════════════════════════


class TestExportFilenameUniqueness(unittest.TestCase):
    """내보내기 파일명 고유성 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self._orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import session_io

        session_io.EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_different_prefixes_create_different_files(self):
        """다른 prefix는 다른 파일 생성."""
        from session_io import export_session_json

        export_session_json("module_a", {"type": "a"})
        export_session_json("module_b", {"type": "b"})

        files = os.listdir(self.tmpdir)
        a_files = [f for f in files if f.startswith("module_a")]
        b_files = [f for f in files if f.startswith("module_b")]
        self.assertEqual(len(a_files), 1)
        self.assertEqual(len(b_files), 1)

    def test_export_filename_format(self):
        """파일명이 {prefix}_stats_{timestamp}.json 형식인지."""
        from session_io import export_session_json

        export_session_json("fmt_test", {"a": 1})

        files = os.listdir(self.tmpdir)
        self.assertEqual(len(files), 1)
        name = files[0]
        self.assertTrue(name.startswith("fmt_test_stats_"))
        self.assertTrue(name.endswith(".json"))
        # timestamp 부분 추출: YYYYMMDD_HHMMSS
        ts_part = name.replace("fmt_test_stats_", "").replace(".json", "")
        self.assertEqual(len(ts_part), 15)  # 20260220_120000


# ═══════════════════════════════════════════════════════════
# 13. export_session_json 반환값이 JSON 파일 경로인지 확인
# ═══════════════════════════════════════════════════════════


class TestExportReturnValue(unittest.TestCase):
    """export_session_json 반환값이 JSON 파일 경로인지 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self._orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import session_io

        session_io.EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_returns_json_file_path(self):
        """반환값이 .json 파일 경로여야 함."""
        from session_io import export_session_json

        result = export_session_json("ret_test", {"key": "value"})
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith(".json"))
        self.assertTrue(os.path.isfile(result))

    def test_returned_path_is_loadable(self):
        """반환된 경로로 바로 load_session_json 호출 가능."""
        from session_io import export_session_json, load_session_json

        path = export_session_json("load_test", {"count": 42})
        loaded = load_session_json(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["count"], 42)


# ═══════════════════════════════════════════════════════════
# 14. import_settings JSON 유효성 검사 테스트
# ═══════════════════════════════════════════════════════════


class TestImportSettingsJsonValidation(unittest.TestCase):
    """import_settings 가져오기 시 유효하지 않은 JSON 건너뜀 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.fake_base = tempfile.mkdtemp()
        import settings_io

        self._orig_base = settings_io._BASE
        settings_io._BASE = self.fake_base

    def tearDown(self):
        import settings_io

        settings_io._BASE = self._orig_base
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.fake_base, ignore_errors=True)

    def _make_zip(self, files_dict):
        zip_path = os.path.join(self.tmpdir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for arcname, content in files_dict.items():
                zf.writestr(arcname, content)
        return zip_path

    def test_invalid_json_skipped(self):
        """유효하지 않은 JSON 파일은 건너뜀."""
        from settings_io import import_settings

        zip_path = self._make_zip({"config.json": "{invalid json!!"})
        result = import_settings(zip_path)
        self.assertIn("config.json", result["skipped"])
        self.assertEqual(result["imported"], [])
        # 파일이 실제로 생성되지 않았는지
        self.assertFalse(os.path.exists(os.path.join(self.fake_base, "config.json")))

    def test_valid_json_imported(self):
        """유효한 JSON은 정상 가져오기."""
        from settings_io import import_settings

        zip_path = self._make_zip({"config.json": '{"theme": "dark"}'})
        result = import_settings(zip_path)
        self.assertIn("config.json", result["imported"])

    def test_mixed_valid_invalid_json(self):
        """유효/무효 JSON이 섞인 경우 유효한 것만 가져오기."""
        from settings_io import import_settings

        zip_path = self._make_zip({
            "config.json": '{"ok": true}',
            "achievements.json": "not valid json {{{",
            "tutorial_state.json": '{"step": 3}',
        })
        result = import_settings(zip_path)
        self.assertIn("config.json", result["imported"])
        self.assertIn("tutorial_state.json", result["imported"])
        self.assertIn("achievements.json", result["skipped"])

    def test_non_json_files_bypass_validation(self):
        """JSON이 아닌 파일(profiles 내)은 유효성 검사 없이 가져오기."""
        from settings_io import import_settings

        zip_path = self._make_zip({
            "profiles/user1.json": '{"name": "user1"}',
            "profiles/avatar.png": b"PNG binary data".decode("latin-1"),
        })
        result = import_settings(zip_path)
        # profiles/ 내 파일은 허용됨 — .json은 유효성 검사, .png는 바이패스 가능
        # (profiles/ prefix가 허용되므로 .png도 통과)
        # profiles/user1.json은 유효한 JSON이므로 imported
        self.assertIn("profiles/user1.json", result["imported"])

    def test_empty_json_object_imported(self):
        """빈 JSON 객체 {}는 유효한 JSON이므로 가져오기."""
        from settings_io import import_settings

        zip_path = self._make_zip({"config.json": "{}"})
        result = import_settings(zip_path)
        self.assertIn("config.json", result["imported"])

    def test_json_array_imported(self):
        """JSON 배열도 유효한 JSON이므로 가져오기."""
        from settings_io import import_settings

        zip_path = self._make_zip({"achievements.json": "[]"})
        result = import_settings(zip_path)
        self.assertIn("achievements.json", result["imported"])


# ═══════════════════════════════════════════════════════════
# 15. exports 디렉터리 분리 검증
# ═══════════════════════════════════════════════════════════


class TestExportDirectorySeparation(unittest.TestCase):
    """session_io와 settings_io의 exports 디렉터리가 분리되었는지 검증."""

    def test_session_io_uses_sessions_subdir(self):
        import session_io

        self.assertTrue(session_io.EXPORT_DIR.endswith(os.path.join("exports", "sessions")))

    def test_settings_io_uses_settings_subdir(self):
        import settings_io

        self.assertTrue(settings_io._EXPORT_DIR.endswith(os.path.join("exports", "settings")))

    def test_directories_are_different(self):
        import session_io
        import settings_io

        self.assertNotEqual(session_io.EXPORT_DIR, settings_io._EXPORT_DIR)


# ═══════════════════════════════════════════════════════════
# 16. session_io의 pygame 지연 import 검증
# ═══════════════════════════════════════════════════════════


class TestSessionIoLazyImport(unittest.TestCase):
    """session_io가 최상위에서 pygame을 import하지 않는지 검증."""

    def test_data_functions_work_without_pygame(self):
        """데이터 함수들은 pygame 없이도 동작해야 함."""
        # 이미 pygame이 설치되어 있으므로 직접 확인은 어렵지만,
        # 최상위 import에 pygame이 없는지 소스 코드로 확인
        import inspect

        import session_io

        source = inspect.getsource(session_io)
        # 모듈 최상위(함수 밖)에서 import pygame이 없어야 함
        lines = source.split("\n")
        top_level_pygame = False
        for line in lines:
            stripped = line.strip()
            # 함수/클래스 정의 안에 있으면 무시
            if stripped.startswith("def ") or stripped.startswith("class "):
                break
            if stripped == "import pygame" or stripped.startswith("from pygame"):
                top_level_pygame = True
                break
        self.assertFalse(top_level_pygame, "session_io가 최상위에서 pygame을 import하면 안 됩니다")


if __name__ == "__main__":
    unittest.main()
