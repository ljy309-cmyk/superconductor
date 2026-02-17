"""settings_io 단위 테스트 — ZIP 내보내기/가져오기, 경로 순회 방어, 엣지 케이스."""

import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestExportSettings(unittest.TestCase):
    """export_settings 함수 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_returns_zip_path(self):
        from settings_io import export_settings
        path = export_settings(output_dir=self.tmpdir)
        self.assertTrue(path.endswith(".zip"))
        self.assertTrue(os.path.exists(path))

    def test_zip_is_valid(self):
        from settings_io import export_settings
        path = export_settings(output_dir=self.tmpdir)
        self.assertTrue(zipfile.is_zipfile(path))

    def test_zip_contains_config_json(self):
        """config.json이 존재하면 ZIP에 포함되어야 함."""
        from settings_io import export_settings, _BASE
        path = export_settings(output_dir=self.tmpdir)
        config_path = os.path.join(_BASE, "config.json")
        if os.path.exists(config_path):
            with zipfile.ZipFile(path, "r") as zf:
                self.assertIn("config.json", zf.namelist())

    def test_zip_filename_has_timestamp(self):
        from settings_io import export_settings
        path = export_settings(output_dir=self.tmpdir)
        fname = os.path.basename(path)
        self.assertTrue(fname.startswith("settings_export_"))

    def test_creates_output_dir_if_missing(self):
        from settings_io import export_settings
        sub = os.path.join(self.tmpdir, "new_subdir")
        path = export_settings(output_dir=sub)
        self.assertTrue(os.path.isdir(sub))
        self.assertTrue(os.path.exists(path))

    def test_export_roundtrip_preserves_config(self):
        """내보내기한 ZIP에서 config.json 내용이 원본과 동일한지 확인."""
        from settings_io import export_settings, _BASE
        config_path = os.path.join(_BASE, "config.json")
        if not os.path.exists(config_path):
            self.skipTest("config.json not found")

        with open(config_path, "r", encoding="utf-8") as f:
            original = json.load(f)

        zip_path = export_settings(output_dir=self.tmpdir)
        with zipfile.ZipFile(zip_path, "r") as zf:
            with zf.open("config.json") as f:
                exported = json.load(f)

        self.assertEqual(original, exported)


class TestImportSettings(unittest.TestCase):
    """import_settings 함수 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # import할 대상 디렉터리를 격리하기 위해 _BASE를 임시로 교체
        import settings_io
        self._orig_base = settings_io._BASE
        self.fake_base = tempfile.mkdtemp()
        settings_io._BASE = self.fake_base

    def tearDown(self):
        import settings_io
        settings_io._BASE = self._orig_base
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.fake_base, ignore_errors=True)

    def _make_zip(self, files_dict, zip_name="test.zip"):
        """테스트용 ZIP 파일 생성. files_dict: {arcname: content_bytes}"""
        zip_path = os.path.join(self.tmpdir, zip_name)
        with zipfile.ZipFile(zip_path, "w") as zf:
            for arcname, content in files_dict.items():
                zf.writestr(arcname, content)
        return zip_path

    def test_import_config_json(self):
        """config.json을 정상적으로 가져오기."""
        from settings_io import import_settings
        data = {"display": {"fps": 120}}
        zip_path = self._make_zip({"config.json": json.dumps(data)})
        result = import_settings(zip_path)
        self.assertIn("config.json", result["imported"])
        # 실제 파일이 생성되었는지
        dest = os.path.join(self.fake_base, "config.json")
        self.assertTrue(os.path.exists(dest))
        with open(dest, "r") as f:
            imported = json.load(f)
        self.assertEqual(imported, data)

    def test_import_achievements_json(self):
        from settings_io import import_settings
        zip_path = self._make_zip({"achievements.json": '{"unlocked": []}'})
        result = import_settings(zip_path)
        self.assertIn("achievements.json", result["imported"])

    def test_import_profiles_dir(self):
        """profiles/ 디렉터리 내 파일 가져오기."""
        from settings_io import import_settings
        zip_path = self._make_zip({
            "profiles/user1.json": '{"name": "user1"}',
            "profiles/user2.json": '{"name": "user2"}',
        })
        result = import_settings(zip_path)
        self.assertEqual(len(result["imported"]), 2)
        self.assertTrue(os.path.exists(
            os.path.join(self.fake_base, "profiles", "user1.json")))

    def test_skip_unknown_files(self):
        """허용 목록에 없는 파일은 건너뜀."""
        from settings_io import import_settings
        zip_path = self._make_zip({
            "config.json": "{}",
            "malicious.exe": b"bad".decode(),
            "random.txt": "hello",
        })
        result = import_settings(zip_path)
        self.assertIn("config.json", result["imported"])
        self.assertIn("malicious.exe", result["skipped"])
        self.assertIn("random.txt", result["skipped"])
        # 실제 파일이 생성되지 않았는지
        self.assertFalse(os.path.exists(
            os.path.join(self.fake_base, "malicious.exe")))

    def test_nonexistent_zip_returns_empty(self):
        from settings_io import import_settings
        result = import_settings("/nonexistent/path.zip")
        self.assertEqual(result["imported"], [])
        self.assertEqual(result["skipped"], [])

    def test_corrupt_zip_returns_empty(self):
        """손상된 ZIP 파일 처리."""
        from settings_io import import_settings
        bad_path = os.path.join(self.tmpdir, "corrupt.zip")
        with open(bad_path, "wb") as f:
            f.write(b"this is not a zip file")
        result = import_settings(bad_path)
        self.assertEqual(result["imported"], [])

    def test_empty_zip(self):
        from settings_io import import_settings
        zip_path = self._make_zip({})
        result = import_settings(zip_path)
        self.assertEqual(result["imported"], [])
        self.assertEqual(result["skipped"], [])


class TestPathTraversal(unittest.TestCase):
    """경로 순회(path traversal) 공격 방어 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import settings_io
        self._orig_base = settings_io._BASE
        self.fake_base = tempfile.mkdtemp()
        settings_io._BASE = self.fake_base

    def tearDown(self):
        import settings_io
        settings_io._BASE = self._orig_base
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.fake_base, ignore_errors=True)

    def _make_zip(self, files_dict):
        zip_path = os.path.join(self.tmpdir, "evil.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for arcname, content in files_dict.items():
                zf.writestr(arcname, content)
        return zip_path

    def test_dotdot_blocked(self):
        """.. 포함 경로 차단."""
        from settings_io import import_settings
        zip_path = self._make_zip({
            "../../../etc/passwd": "root:x:0:0",
        })
        result = import_settings(zip_path)
        self.assertIn("../../../etc/passwd", result["skipped"])
        self.assertEqual(result["imported"], [])

    def test_absolute_path_blocked(self):
        """/로 시작하는 절대 경로 차단."""
        from settings_io import import_settings
        zip_path = self._make_zip({
            "/etc/shadow": "hacked",
        })
        result = import_settings(zip_path)
        self.assertIn("/etc/shadow", result["skipped"])
        self.assertEqual(result["imported"], [])

    def test_dotdot_in_middle_blocked(self):
        """경로 중간의 .. 차단."""
        from settings_io import import_settings
        zip_path = self._make_zip({
            "profiles/../../../etc/passwd": "pwned",
        })
        result = import_settings(zip_path)
        self.assertIn("profiles/../../../etc/passwd", result["skipped"])

    def test_mixed_safe_and_unsafe(self):
        """안전한 파일과 위험한 파일이 섞인 경우."""
        from settings_io import import_settings
        zip_path = self._make_zip({
            "config.json": '{"safe": true}',
            "../escape.txt": "bad",
            "profiles/ok.json": '{"good": true}',
            "/root/.ssh/id_rsa": "secret",
        })
        result = import_settings(zip_path)
        self.assertEqual(sorted(result["imported"]),
                         ["config.json", "profiles/ok.json"])
        self.assertEqual(len(result["skipped"]), 2)


class TestListExports(unittest.TestCase):
    """list_exports 함수 검증."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import settings_io
        self._orig_export_dir = settings_io._EXPORT_DIR
        settings_io._EXPORT_DIR = self.tmpdir

    def tearDown(self):
        import settings_io
        settings_io._EXPORT_DIR = self._orig_export_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_dir(self):
        from settings_io import list_exports
        result = list_exports()
        self.assertEqual(result, [])

    def test_lists_only_zips(self):
        from settings_io import list_exports
        # zip 파일과 비-zip 파일 생성
        for name in ["a.zip", "b.zip", "readme.txt", "data.json"]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("x")
        result = list_exports()
        self.assertEqual(len(result), 2)
        self.assertTrue(all(r.endswith(".zip") for r in result))

    def test_sorted_reverse(self):
        """최신 파일이 먼저 오는지 확인."""
        from settings_io import list_exports
        for name in ["export_20260101.zip", "export_20260301.zip", "export_20260201.zip"]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                f.write("x")
        result = list_exports()
        basenames = [os.path.basename(r) for r in result]
        self.assertEqual(basenames[0], "export_20260301.zip")
        self.assertEqual(basenames[-1], "export_20260101.zip")

    def test_nonexistent_dir(self):
        """내보내기 디렉터리가 없으면 빈 리스트."""
        import settings_io
        settings_io._EXPORT_DIR = "/nonexistent/dir/12345"
        from settings_io import list_exports
        result = list_exports()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
