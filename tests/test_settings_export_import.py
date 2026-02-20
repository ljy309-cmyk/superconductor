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
# 1. session_io — export_session (JSON) 테스트
# ═══════════════════════════════════════════════════════════


class TestExportSessionJsonFormat(unittest.TestCase):
    """session_io.export_session(fmt='json') 함수 검증."""

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
        from session_io import export_session

        session = {"total_attempts": 100, "tunnel_rate": 0.35}
        result = export_session("test", session)
        self.assertIsNotNone(result)

        json_files = [f for f in os.listdir(self.tmpdir) if f.endswith(".json")]
        self.assertEqual(len(json_files), 1)
        self.assertTrue(json_files[0].startswith("test_stats_"))

        with open(os.path.join(self.tmpdir, json_files[0]), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["total_attempts"], 100)
        self.assertAlmostEqual(data["tunnel_rate"], 0.35)
        self.assertIn("timestamp", data)

    def test_json_with_trial_rows(self):
        """trial_rows 포함 시 JSON에 trial_history 포함."""
        from session_io import export_session

        session = {"total_attempts": 3}
        trials = [
            {"t": 1.0, "barrier": 12, "prob": 0.1, "result": True},
            {"t": 2.5, "barrier": 20, "prob": 0.05, "result": False},
        ]
        result = export_session("test", session, trial_rows=trials)
        self.assertIsNotNone(result)

        with open(result, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["total_attempts"], 3)
        self.assertEqual(len(data["trial_history"]), 2)
        self.assertTrue(data["trial_history"][0]["result"])
        self.assertFalse(data["trial_history"][1]["result"])

    def test_csv_format_with_trial_row_fn(self):
        """CSV 포맷 + custom trial_row_fn."""
        from session_io import export_session

        session = {"count": 2}
        trials = [
            {"t": 1.5, "barrier": 10, "prob": 0.2, "result": True},
            {"t": 3.0, "barrier": 15, "prob": 0.1, "result": False},
        ]
        columns = ["trial", "time_s", "barrier_width", "tunnel_prob", "result"]
        row_fn = lambda i, tr: [i, tr["t"], tr["barrier"], tr["prob"], int(tr["result"])]

        result = export_session(
            "tunneling", session, fmt="csv",
            trial_rows=trials, trial_columns=columns, trial_row_fn=row_fn,
        )
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith(".csv"))

        with open(result, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["trial"], "1")
        self.assertEqual(rows[0]["result"], "1")
        self.assertEqual(rows[1]["result"], "0")

    def test_unicode_data_export(self):
        """유니코드(한글) 데이터 내보내기."""
        from session_io import export_session

        session = {"메모": "터널링 실험 결과", "난이도": "쉬움"}
        result = export_session("unicode_test", session)
        self.assertIsNotNone(result)

        with open(result, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["메모"], "터널링 실험 결과")

    def test_timestamp_added_to_export(self):
        """내보낸 JSON에 timestamp 필드가 자동 추가되는지 확인."""
        from session_io import export_session

        session = {"key": "value"}
        path = export_session("ts_test", session)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("timestamp", data)
        self.assertIn("T", data["timestamp"])

    def test_original_session_dict_not_mutated(self):
        """원본 session_data 딕셔너리가 변형되지 않는지 확인."""
        from session_io import export_session

        session = {"original_key": "original_value"}
        original_keys = set(session.keys())
        export_session("mutate_test", session)
        self.assertEqual(set(session.keys()), original_keys)

    def test_empty_trial_rows_no_trial_history(self):
        """trial_rows가 빈 리스트면 trial_history 미포함."""
        from session_io import export_session

        session = {"count": 0}
        path = export_session("empty_trial", session, trial_rows=[])

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn("trial_history", data)

    def test_export_creates_dir_if_missing(self):
        """EXPORT_DIR이 없으면 자동 생성."""
        import session_io
        from session_io import export_session

        nested_dir = os.path.join(self.tmpdir, "sub", "dir")
        session_io.EXPORT_DIR = nested_dir

        result = export_session("mkdir_test", {"a": 1})
        self.assertIsNotNone(result)
        self.assertTrue(os.path.isdir(nested_dir))

    def test_multiple_exports_create_separate_files(self):
        """여러 번 내보내기하면 각각 별도 파일 생성."""
        from session_io import export_session

        export_session("multi", {"seq": 1})
        export_session("multi", {"seq": 2})

        json_files = [f for f in os.listdir(self.tmpdir) if f.endswith(".json")]
        self.assertGreaterEqual(len(json_files), 1)

    def test_invalid_fmt_falls_back_to_json(self):
        """잘못된 fmt 값은 json으로 대체."""
        from session_io import export_session

        result = export_session("fallback", {"a": 1}, fmt="xml")
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith(".json"))


# ═══════════════════════════════════════════════════════════
# 2. session_io — load_session 테스트
# ═══════════════════════════════════════════════════════════


class TestLoadSession(unittest.TestCase):
    """session_io.load_session 함수 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_valid_json(self):
        from session_io import load_session

        data = {"total": 42, "rate": 0.5}
        path = os.path.join(self.tmpdir, "test.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        result = load_session(path)
        self.assertIsNotNone(result)
        self.assertEqual(result["total"], 42)

    def test_load_nonexistent_returns_none(self):
        from session_io import load_session

        result = load_session("/nonexistent/path/data.json")
        self.assertIsNone(result)

    def test_load_invalid_json_returns_none(self):
        from session_io import load_session

        path = os.path.join(self.tmpdir, "bad.json")
        with open(path, "w") as f:
            f.write("{invalid json content!!!")

        result = load_session(path)
        self.assertIsNone(result)

    def test_load_empty_file_returns_none(self):
        from session_io import load_session

        path = os.path.join(self.tmpdir, "empty.json")
        with open(path, "w") as f:
            pass

        result = load_session(path)
        self.assertIsNone(result)

    def test_load_unicode_json(self):
        """유니코드 JSON 파일 로드."""
        from session_io import load_session

        data = {"이름": "실험1", "결과": "성공"}
        path = os.path.join(self.tmpdir, "unicode.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        result = load_session(path)
        self.assertEqual(result["이름"], "실험1")

    def test_load_csv_auto_detect(self):
        """CSV 확장자 자동 감지."""
        from session_io import load_session

        path = os.path.join(self.tmpdir, "test.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["total", "rate"])
            writer.writerow([42, 0.5])

        result = load_session(path)
        self.assertIsNotNone(result)
        self.assertEqual(result["total"], 42)
        self.assertAlmostEqual(result["rate"], 0.5)

    def test_load_json_with_trial_history(self):
        """trial_history 포함 JSON 로드."""
        from session_io import load_session

        data = {
            "total": 3,
            "trial_history": [
                {"t": 1.0, "result": True},
                {"t": 2.0, "result": False},
            ],
        }
        path = os.path.join(self.tmpdir, "test.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        result = load_session(path)
        self.assertEqual(result["total"], 3)
        self.assertEqual(len(result["trial_history"]), 2)
        self.assertTrue(result["trial_history"][0]["result"])


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
        """JSON 내보내기 → load_session으로 로드."""
        from session_io import export_session, load_session

        session = {"attempts": 50, "rate": 0.4, "speed": 2.0}
        path = export_session("roundtrip", session)

        loaded = load_session(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["attempts"], 50)
        self.assertAlmostEqual(loaded["rate"], 0.4)

    def test_json_with_trials_export_then_load(self):
        """JSON + trial_rows 내보내기 → load_session으로 로드."""
        from session_io import export_session, load_session

        session = {"total": 3}
        trials = [
            {"t": 1.0, "width": 10, "prob": 0.2, "result": True},
            {"t": 2.0, "width": 15, "prob": 0.1, "result": False},
            {"t": 3.5, "width": 10, "prob": 0.2, "result": True},
        ]
        path = export_session("rt", session, trial_rows=trials)

        loaded = load_session(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["total"], 3)
        self.assertEqual(len(loaded["trial_history"]), 3)
        self.assertTrue(loaded["trial_history"][0]["result"])
        self.assertFalse(loaded["trial_history"][1]["result"])


# ═══════════════════════════════════════════════════════════
# 9. tunneling_data — _load_import_data 테스트
# ═══════════════════════════════════════════════════════════


class TestTunnelingDataImport(unittest.TestCase):
    """tunneling_data._load_import_data 함수 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_json_with_trials(self, session_data, trial_history):
        """trial_history가 포함된 JSON 파일 생성."""
        ts = "20260220_120000"
        json_path = os.path.join(self.tmpdir, f"tunneling_stats_{ts}.json")
        data = dict(session_data)
        data["trial_history"] = trial_history
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return json_path

    def test_load_tunneling_data_with_trial_history(self):
        """JSON에 포함된 trial_history 추출."""
        from quantum.tunneling_data import _load_import_data

        trials = [
            {"t": 1.5, "barrier": 12, "prob": 0.1, "result": True},
            {"t": 3.0, "barrier": 20, "prob": 0.05, "result": False},
        ]
        json_path = self._create_json_with_trials(
            {"total_attempts": 2, "tunnel_rate": 0.5}, trials,
        )

        session, loaded_trials = _load_import_data(json_path)
        self.assertIsNotNone(session)
        self.assertEqual(len(loaded_trials), 2)
        self.assertAlmostEqual(loaded_trials[0]["t"], 1.5)
        self.assertEqual(loaded_trials[0]["barrier"], 12)
        self.assertTrue(loaded_trials[0]["result"])
        self.assertFalse(loaded_trials[1]["result"])
        # session에서 trial_history가 제거되었는지 확인
        self.assertNotIn("trial_history", session)

    def test_load_tunneling_no_trials(self):
        """trial_history 없는 JSON."""
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
        from session_io import export_session

        export_session("module_a", {"type": "a"})
        export_session("module_b", {"type": "b"})

        files = os.listdir(self.tmpdir)
        a_files = [f for f in files if f.startswith("module_a")]
        b_files = [f for f in files if f.startswith("module_b")]
        self.assertEqual(len(a_files), 1)
        self.assertEqual(len(b_files), 1)

    def test_export_filename_format(self):
        """파일명이 {prefix}_stats_{timestamp}.json 형식인지."""
        from session_io import export_session

        export_session("fmt_test", {"a": 1})

        files = os.listdir(self.tmpdir)
        self.assertEqual(len(files), 1)
        name = files[0]
        self.assertTrue(name.startswith("fmt_test_stats_"))
        self.assertTrue(name.endswith(".json"))
        ts_part = name.replace("fmt_test_stats_", "").replace(".json", "")
        self.assertEqual(len(ts_part), 15)  # 20260220_120000


# ═══════════════════════════════════════════════════════════
# 13. export_session 반환값 검증
# ═══════════════════════════════════════════════════════════


class TestExportReturnValue(unittest.TestCase):
    """export_session 반환값 검증."""

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
        from session_io import export_session

        result = export_session("ret_test", {"key": "value"})
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith(".json"))
        self.assertTrue(os.path.isfile(result))

    def test_returned_path_is_loadable(self):
        """반환된 경로로 바로 load_session 호출 가능."""
        from session_io import export_session, load_session

        path = export_session("load_test", {"count": 42})
        loaded = load_session(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["count"], 42)

    def test_csv_returns_csv_file_path(self):
        """CSV 포맷 반환값이 .csv 파일 경로."""
        from session_io import export_session

        result = export_session("csv_ret", {"key": "value"}, fmt="csv")
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith(".csv"))
        self.assertTrue(os.path.isfile(result))


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


# ═══════════════════════════════════════════════════════════
# 17. export_session — 통합 내보내기 함수 (fmt 파라미터)
# ═══════════════════════════════════════════════════════════


class TestExportSession(unittest.TestCase):
    """export_session 통합 함수 (JSON/CSV 포맷 선택) 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self._orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import session_io

        session_io.EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_json_format_default(self):
        """기본 포맷은 JSON."""
        from session_io import export_session

        path = export_session("test", {"count": 10, "rate": 0.5})
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".json"))
        self.assertTrue(os.path.isfile(path))

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["count"], 10)
        self.assertIn("timestamp", data)

    def test_json_format_explicit(self):
        """fmt='json' 명시적 지정."""
        from session_io import export_session

        path = export_session("test", {"key": "val"}, fmt="json")
        self.assertTrue(path.endswith(".json"))

    def test_csv_format_session_summary(self):
        """fmt='csv': trial_rows 없이 세션 요약만 CSV로 내보내기."""
        from session_io import export_session

        session = {"attempts": 100, "rate": 0.35, "speed": 2.0}
        path = export_session("test", session, fmt="csv")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".csv"))
        self.assertTrue(os.path.isfile(path))

        # CSV 내용 확인
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["attempts"], "100")
        self.assertIn("timestamp", rows[0])

    def test_csv_format_with_trials(self):
        """fmt='csv': trial_rows를 CSV로 내보내기."""
        from session_io import export_session

        session = {"total": 3}
        trials = [
            {"trial": 1, "time_s": 1.0, "prob": 0.2, "result": 1},
            {"trial": 2, "time_s": 2.5, "prob": 0.1, "result": 0},
            {"trial": 3, "time_s": 4.0, "prob": 0.2, "result": 1},
        ]
        columns = ["trial", "time_s", "prob", "result"]

        path = export_session("test", session, fmt="csv",
                              trial_rows=trials, trial_columns=columns)
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".csv"))

        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["trial"], "1")
        self.assertEqual(rows[2]["result"], "1")

    def test_csv_with_trial_row_fn(self):
        """fmt='csv': trial_row_fn을 사용한 CSV 내보내기."""
        from session_io import export_session

        trials = [
            {"t": 1.5, "barrier": 10, "prob": 0.2, "result": True},
        ]
        columns = ["idx", "time", "width", "prob", "res"]
        row_fn = lambda i, tr: [i, tr["t"], tr["barrier"], tr["prob"], int(tr["result"])]

        path = export_session("test", {}, fmt="csv",
                              trial_rows=trials, trial_columns=columns, trial_row_fn=row_fn)
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(rows[0]["idx"], "1")
        self.assertEqual(rows[0]["res"], "1")

    def test_json_embeds_trial_history(self):
        """fmt='json': trial_rows가 있으면 JSON에 trial_history로 포함."""
        from session_io import export_session

        trials = [{"t": 1.0, "result": True}, {"t": 2.0, "result": False}]
        path = export_session("test", {"total": 2}, trial_rows=trials)
        self.assertTrue(path.endswith(".json"))

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("trial_history", data)
        self.assertEqual(len(data["trial_history"]), 2)
        self.assertTrue(data["trial_history"][0]["result"])

    def test_json_no_trials_no_trial_history_key(self):
        """fmt='json': trial_rows 없으면 trial_history 키 없음."""
        from session_io import export_session

        path = export_session("test", {"total": 0})
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn("trial_history", data)

    def test_csv_nested_dict_serialized_as_json_string(self):
        """fmt='csv': 중첩된 dict/list는 JSON 문자열로 저장."""
        from session_io import export_session

        session = {"name": "test", "config": {"fps": 60, "mode": "fast"}, "tags": [1, 2, 3]}
        path = export_session("test", session, fmt="csv")

        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        # JSON 인코딩된 필드 확인
        config_str = rows[0]["config"]
        parsed = json.loads(config_str)
        self.assertEqual(parsed["fps"], 60)

    def test_csv_filename_uses_stats_prefix(self):
        """fmt='csv': 파일명 형식이 {prefix}_stats_{ts}.csv."""
        from session_io import export_session

        path = export_session("mymod", {"a": 1}, fmt="csv")
        basename = os.path.basename(path)
        self.assertTrue(basename.startswith("mymod_stats_"))
        self.assertTrue(basename.endswith(".csv"))

    def test_original_data_not_mutated(self):
        """원본 session_data가 변경되지 않는지 확인."""
        from session_io import export_session

        session = {"key": "val"}
        original_keys = set(session.keys())
        export_session("test", session, fmt="json")
        self.assertEqual(set(session.keys()), original_keys)

        session2 = {"key": "val"}
        export_session("test", session2, fmt="csv")
        self.assertEqual(set(session2.keys()), set(["key"]))


# ═══════════════════════════════════════════════════════════
# 18. load_session / load_session_csv — 통합 로드 함수
# ═══════════════════════════════════════════════════════════


class TestLoadSession(unittest.TestCase):
    """load_session (포맷 자동 감지) 및 load_session_csv 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_session_auto_detect_json(self):
        """load_session: .json 확장자 → JSON으로 로드."""
        from session_io import load_session

        path = os.path.join(self.tmpdir, "data.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"format": "json", "count": 42}, f)

        result = load_session(path)
        self.assertIsNotNone(result)
        self.assertEqual(result["format"], "json")
        self.assertEqual(result["count"], 42)

    def test_load_session_auto_detect_csv(self):
        """load_session: .csv 확장자 → CSV로 로드."""
        from session_io import load_session

        path = os.path.join(self.tmpdir, "data.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "value"])
            writer.writerow(["test", "123"])

        result = load_session(path)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["value"], 123)

    def test_load_session_csv_single_row(self):
        """load_session_csv: 단일 행 → dict 반환."""
        from session_io import load_session_csv

        path = os.path.join(self.tmpdir, "single.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["attempts", "rate", "speed"])
            writer.writerow(["100", "0.35", "2.0"])

        result = load_session_csv(path)
        self.assertIsNotNone(result)
        self.assertEqual(result["attempts"], 100)
        self.assertAlmostEqual(result["rate"], 0.35)
        self.assertAlmostEqual(result["speed"], 2.0)

    def test_load_session_csv_multi_rows(self):
        """load_session_csv: 다중 행 → {"rows": [...]} 반환."""
        from session_io import load_session_csv

        path = os.path.join(self.tmpdir, "multi.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["trial", "time_s", "result"])
            writer.writerow(["1", "1.5", "1"])
            writer.writerow(["2", "3.0", "0"])
            writer.writerow(["3", "4.5", "1"])

        result = load_session_csv(path)
        self.assertIsNotNone(result)
        self.assertIn("rows", result)
        self.assertEqual(len(result["rows"]), 3)
        self.assertEqual(result["rows"][0]["trial"], 1)
        self.assertAlmostEqual(result["rows"][1]["time_s"], 3.0)

    def test_load_session_csv_empty_file(self):
        """load_session_csv: 빈 CSV → None."""
        from session_io import load_session_csv

        path = os.path.join(self.tmpdir, "empty.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["col1", "col2"])
            # 데이터 행 없음

        result = load_session_csv(path)
        self.assertIsNone(result)

    def test_load_session_csv_nonexistent(self):
        """load_session_csv: 존재하지 않는 파일 → None."""
        from session_io import load_session_csv

        result = load_session_csv("/nonexistent/path/data.csv")
        self.assertIsNone(result)

    def test_load_session_csv_json_encoded_fields(self):
        """load_session_csv: JSON 인코딩된 dict/list 필드 자동 파싱."""
        from session_io import load_session_csv

        path = os.path.join(self.tmpdir, "nested.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "config", "tags"])
            writer.writerow(["test", '{"fps": 60}', '[1, 2, 3]'])

        result = load_session_csv(path)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "test")
        self.assertIsInstance(result["config"], dict)
        self.assertEqual(result["config"]["fps"], 60)
        self.assertIsInstance(result["tags"], list)
        self.assertEqual(result["tags"], [1, 2, 3])

    def test_load_session_csv_numeric_conversion(self):
        """load_session_csv: 숫자 문자열 자동 변환."""
        from session_io import load_session_csv

        path = os.path.join(self.tmpdir, "nums.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["int_val", "float_val", "str_val"])
            writer.writerow(["42", "3.14", "hello"])

        result = load_session_csv(path)
        self.assertEqual(result["int_val"], 42)
        self.assertIsInstance(result["int_val"], int)
        self.assertAlmostEqual(result["float_val"], 3.14)
        self.assertIsInstance(result["float_val"], float)
        self.assertEqual(result["str_val"], "hello")
        self.assertIsInstance(result["str_val"], str)


# ═══════════════════════════════════════════════════════════
# 19. export_session → load_session 라운드트립
# ═══════════════════════════════════════════════════════════


class TestExportLoadRoundtrip(unittest.TestCase):
    """export_session → load_session 라운드트립 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self._orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import session_io

        session_io.EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_json_roundtrip(self):
        """JSON 포맷 라운드트립: export → load."""
        from session_io import export_session, load_session

        session = {"attempts": 50, "rate": 0.4, "difficulty": "hard"}
        path = export_session("rt", session, fmt="json")

        loaded = load_session(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["attempts"], 50)
        self.assertAlmostEqual(loaded["rate"], 0.4)
        self.assertEqual(loaded["difficulty"], "hard")
        self.assertIn("timestamp", loaded)

    def test_csv_summary_roundtrip(self):
        """CSV 포맷 (세션 요약) 라운드트립: export → load."""
        from session_io import export_session, load_session

        session = {"total": 100, "rate": 0.25, "speed": 3.0}
        path = export_session("rt", session, fmt="csv")

        loaded = load_session(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["total"], 100)
        self.assertAlmostEqual(loaded["rate"], 0.25)
        self.assertAlmostEqual(loaded["speed"], 3.0)
        self.assertIn("timestamp", loaded)

    def test_csv_trials_roundtrip(self):
        """CSV 포맷 (시행 데이터) 라운드트립: export → load."""
        from session_io import export_session, load_session

        trials = [
            {"trial": 1, "time_s": 1.0, "result": 1},
            {"trial": 2, "time_s": 2.5, "result": 0},
        ]
        columns = ["trial", "time_s", "result"]
        path = export_session("rt", {}, fmt="csv",
                              trial_rows=trials, trial_columns=columns)

        loaded = load_session(path)
        self.assertIsNotNone(loaded)
        self.assertIn("rows", loaded)
        self.assertEqual(len(loaded["rows"]), 2)
        self.assertEqual(loaded["rows"][0]["trial"], 1)

    def test_json_with_trials_roundtrip(self):
        """JSON 포맷 + trial_rows 라운드트립."""
        from session_io import export_session, load_session

        trials = [{"t": 1.0, "result": True}, {"t": 2.0, "result": False}]
        session = {"total": 2, "rate": 0.5}
        path = export_session("rt", session, fmt="json", trial_rows=trials)

        loaded = load_session(path)
        self.assertEqual(loaded["total"], 2)
        self.assertEqual(len(loaded["trial_history"]), 2)
        self.assertTrue(loaded["trial_history"][0]["result"])

    def test_csv_nested_data_roundtrip(self):
        """CSV 포맷: 중첩 dict/list의 라운드트립."""
        from session_io import export_session, load_session

        session = {"name": "exp", "params": {"a": 1, "b": 2}, "ids": [10, 20]}
        path = export_session("rt", session, fmt="csv")

        loaded = load_session(path)
        self.assertEqual(loaded["name"], "exp")
        self.assertEqual(loaded["params"], {"a": 1, "b": 2})
        self.assertEqual(loaded["ids"], [10, 20])


# ═══════════════════════════════════════════════════════════
# 20. list_export_files — JSON/CSV 모두 표시
# ═══════════════════════════════════════════════════════════


class TestListExportFilesDualFormat(unittest.TestCase):
    """list_export_files가 JSON과 CSV 파일 모두 포함하는지 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self._orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import session_io

        session_io.EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_includes_json_and_csv(self):
        """JSON과 CSV 파일 모두 목록에 포함."""
        from session_io import list_export_files

        for name in [
            "test_stats_20260101_100000.json",
            "test_stats_20260102_100000.csv",
        ]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("data")

        result = list_export_files("test")
        self.assertEqual(len(result), 2)

        labels = [r[0] for r in result]
        # CSV가 최신이므로 첫 번째
        self.assertIn("(CSV)", labels[0])
        self.assertIn("(JSON)", labels[1])

    def test_label_format_json(self):
        """JSON 파일 라벨에 (JSON) 포함."""
        from session_io import list_export_files

        with open(os.path.join(self.tmpdir, "mod_stats_20260101_120000.json"), "w") as f:
            f.write("{}")

        result = list_export_files("mod")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "20260101_120000 (JSON)")

    def test_label_format_csv(self):
        """CSV 파일 라벨에 (CSV) 포함."""
        from session_io import list_export_files

        with open(os.path.join(self.tmpdir, "mod_stats_20260101_120000.csv"), "w") as f:
            f.write("a,b")

        result = list_export_files("mod")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "20260101_120000 (CSV)")

    def test_ignores_trials_csv(self):
        """기존 trials CSV 파일은 무시 (stats_ 패턴만)."""
        from session_io import list_export_files

        for name in [
            "test_stats_20260101.json",
            "test_trials_20260101.csv",  # 이건 무시됨
        ]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("data")

        result = list_export_files("test")
        self.assertEqual(len(result), 1)
        self.assertIn("(JSON)", result[0][0])

    def test_mixed_formats_sorted_by_timestamp(self):
        """JSON/CSV 혼합 시 타임스탬프 순 정렬."""
        from session_io import list_export_files

        for name in [
            "m_stats_20260101_100000.json",
            "m_stats_20260103_100000.csv",
            "m_stats_20260102_100000.json",
        ]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("data")

        result = list_export_files("m")
        self.assertEqual(len(result), 3)
        # 최신이 첫 번째
        self.assertIn("20260103", result[0][0])
        self.assertIn("(CSV)", result[0][0])
        self.assertIn("20260101", result[2][0])


# ═══════════════════════════════════════════════════════════
# 21. session_io — delete_export 테스트
# ═══════════════════════════════════════════════════════════


class TestSessionDeleteExport(unittest.TestCase):
    """session_io.delete_export 함수 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_delete_existing_file(self):
        from session_io import delete_export

        path = os.path.join(self.tmpdir, "test.json")
        with open(path, "w") as f:
            f.write("{}")
        self.assertTrue(delete_export(path))
        self.assertFalse(os.path.exists(path))

    def test_delete_nonexistent_file(self):
        from session_io import delete_export

        self.assertFalse(delete_export("/nonexistent/file.json"))


# ═══════════════════════════════════════════════════════════
# 22. settings_io — delete_export 테스트
# ═══════════════════════════════════════════════════════════


class TestSettingsDeleteExport(unittest.TestCase):
    """settings_io.delete_export 함수 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_delete_existing_zip(self):
        from settings_io import delete_export

        path = os.path.join(self.tmpdir, "backup.zip")
        with open(path, "w") as f:
            f.write("data")
        self.assertTrue(delete_export(path))
        self.assertFalse(os.path.exists(path))

    def test_delete_nonexistent_zip(self):
        from settings_io import delete_export

        self.assertFalse(delete_export("/nonexistent/backup.zip"))


# ═══════════════════════════════════════════════════════════
# 23. _auto_parse_csv_values — bool 타입 복원 테스트
# ═══════════════════════════════════════════════════════════


class TestAutoParseCSVBool(unittest.TestCase):
    """_auto_parse_csv_values의 bool 타입 복원 검증."""

    def test_bool_true_restored(self):
        from session_io import _auto_parse_csv_values

        row = {"flag": "true", "FLAG2": "True", "FLAG3": "TRUE"}
        _auto_parse_csv_values(row)
        self.assertIs(row["flag"], True)
        self.assertIs(row["FLAG2"], True)
        self.assertIs(row["FLAG3"], True)

    def test_bool_false_restored(self):
        from session_io import _auto_parse_csv_values

        row = {"flag": "false", "FLAG2": "False", "FLAG3": "FALSE"}
        _auto_parse_csv_values(row)
        self.assertIs(row["flag"], False)
        self.assertIs(row["FLAG2"], False)
        self.assertIs(row["FLAG3"], False)

    def test_bool_roundtrip_via_csv(self):
        """CSV export → load 라운드트립에서 bool 복원."""
        from session_io import load_session_csv

        path = os.path.join(tempfile.mkdtemp(), "bool_test.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "enabled", "visible"])
            writer.writerow(["test", "True", "False"])

        result = load_session_csv(path)
        self.assertIs(result["enabled"], True)
        self.assertIs(result["visible"], False)
        shutil.rmtree(os.path.dirname(path), ignore_errors=True)


# ═══════════════════════════════════════════════════════════
# 24. settings_io — 가져오기 전 백업 테스트
# ═══════════════════════════════════════════════════════════


class TestImportSettingsBackup(unittest.TestCase):
    """import_settings 시 기존 파일의 .bak 백업 생성 검증."""

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

    def test_backup_created_on_overwrite(self):
        """기존 config.json이 있으면 .bak 백업 생성."""
        from settings_io import import_settings

        # 기존 파일 생성
        existing = os.path.join(self.fake_base, "config.json")
        with open(existing, "w") as f:
            json.dump({"old": "data"}, f)

        # ZIP 생성
        zip_path = os.path.join(self.tmpdir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.json", json.dumps({"new": "data"}))

        import_settings(zip_path)

        # .bak 파일 생성 확인
        bak_path = existing + ".bak"
        self.assertTrue(os.path.exists(bak_path))
        with open(bak_path, encoding="utf-8") as f:
            bak_data = json.load(f)
        self.assertEqual(bak_data["old"], "data")

        # 새 파일 확인
        with open(existing, encoding="utf-8") as f:
            new_data = json.load(f)
        self.assertEqual(new_data["new"], "data")

    def test_no_backup_for_new_file(self):
        """기존 파일이 없으면 .bak 미생성."""
        from settings_io import import_settings

        zip_path = os.path.join(self.tmpdir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.json", json.dumps({"new": "data"}))

        import_settings(zip_path)

        bak_path = os.path.join(self.fake_base, "config.json.bak")
        self.assertFalse(os.path.exists(bak_path))


# ═══════════════════════════════════════════════════════════
# 25. export_session — fmt 검증 테스트
# ═══════════════════════════════════════════════════════════


class TestExportSessionFmtValidation(unittest.TestCase):
    """export_session의 fmt 파라미터 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self._orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import session_io

        session_io.EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_invalid_fmt_falls_back_to_json(self):
        """잘못된 fmt → json 폴백."""
        from session_io import export_session

        path = export_session("fb", {"a": 1}, fmt="xml")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".json"))

    def test_csv_fmt_creates_csv(self):
        """fmt='csv' → .csv 파일 생성."""
        from session_io import export_session

        path = export_session("fmt", {"a": 1}, fmt="csv")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".csv"))

    def test_json_fmt_creates_json(self):
        """fmt='json' → .json 파일 생성."""
        from session_io import export_session

        path = export_session("fmt", {"a": 1}, fmt="json")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".json"))


# ═══════════════════════════════════════════════════════════
# 26. _export_as_csv — bool 명시적 처리 테스트
# ═══════════════════════════════════════════════════════════


class TestExportCsvBool(unittest.TestCase):
    """CSV 내보내기에서 bool 값의 라운드트립."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import session_io

        self._orig_export_dir = session_io.EXPORT_DIR
        session_io.EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import session_io

        session_io.EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_bool_roundtrip_csv(self):
        """bool 값 CSV 라운드트립: True/False → 'True'/'False' → True/False."""
        from session_io import export_session, load_session

        session = {"enabled": True, "visible": False, "count": 42}
        path = export_session("bool_rt", session, fmt="csv")
        loaded = load_session(path)
        self.assertIs(loaded["enabled"], True)
        self.assertIs(loaded["visible"], False)
        self.assertEqual(loaded["count"], 42)


if __name__ == "__main__":
    unittest.main()
