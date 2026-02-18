"""리플레이 시스템 단위 테스트 — 녹화/저장/재생 라운드트립."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from replay import (
    REPLAY_FORMAT_VERSION,
    ReplayPlayer,
    ReplayRecorder,
    _migrate_replay,
)


class TestReplayRecorder(unittest.TestCase):
    """ReplayRecorder 녹화 기능."""

    def test_record_frames(self):
        rec = ReplayRecorder("test_module")
        rec.record_frame({"x": 1})
        rec.record_frame({"x": 2})
        rec.record_frame({"x": 3})
        self.assertEqual(rec.frame_count, 3)

    def test_max_frames_limit(self):
        """max_frames 초과 시 오래된 프레임이 제거되어야 한다."""
        rec = ReplayRecorder("test_module", max_frames=5)
        for i in range(10):
            rec.record_frame({"i": i})
        self.assertEqual(rec.frame_count, 5)

    def test_record_alias(self):
        """record()가 record_frame()과 동일하게 작동해야 한다."""
        rec = ReplayRecorder("test_module")
        rec.record({"a": 1})
        self.assertEqual(rec.frame_count, 1)

    def test_empty_save_returns_empty(self):
        """프레임이 없으면 저장 시 빈 문자열을 반환해야 한다."""
        rec = ReplayRecorder("test_module")
        self.assertEqual(rec.save(), "")

    def test_save_creates_file(self):
        """저장 시 파일이 생성되어야 한다."""
        rec = ReplayRecorder("test_module")
        rec.record_frame({"x": 1})

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("replay.REPLAY_DIR", tmpdir):
                path = rec.save()
                self.assertTrue(os.path.exists(path))

                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self.assertEqual(data["format_version"], REPLAY_FORMAT_VERSION)
                self.assertEqual(len(data["frames"]), 1)

    def test_save_with_extra_metadata(self):
        """extra_metadata가 메타데이터에 병합되어야 한다."""
        rec = ReplayRecorder("test_module")
        rec.record_frame({"x": 1})

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("replay.REPLAY_DIR", tmpdir):
                path = rec.save(extra_metadata={"score": 100})
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self.assertEqual(data["metadata"]["score"], 100)
                self.assertEqual(data["metadata"]["module"], "test_module")


class TestReplayPlayer(unittest.TestCase):
    """ReplayPlayer 재생 기능."""

    def _create_replay_file(self, tmpdir, frames, version=REPLAY_FORMAT_VERSION):
        """헬퍼: 테스트용 리플레이 파일 생성."""
        filepath = os.path.join(tmpdir, "test_replay.json")
        data = {
            "format_version": version,
            "metadata": {"module": "test", "total_frames": len(frames)},
            "frames": frames,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return filepath

    def test_load_valid_file(self):
        player = ReplayPlayer()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._create_replay_file(tmpdir, [{"x": 1}, {"x": 2}])
            self.assertTrue(player.load(path))
            self.assertEqual(player.total_frames, 2)

    def test_load_invalid_file(self):
        player = ReplayPlayer()
        self.assertFalse(player.load("/nonexistent/path.json"))

    def test_load_corrupt_json(self):
        player = ReplayPlayer()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "corrupt.json")
            with open(path, "w") as f:
                f.write("{invalid json")
            self.assertFalse(player.load(path))

    def test_next_frame_sequential(self):
        player = ReplayPlayer()
        frames = [{"i": 0}, {"i": 1}, {"i": 2}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._create_replay_file(tmpdir, frames)
            player.load(path)

            self.assertEqual(player.next_frame(), {"i": 0})
            self.assertEqual(player.next_frame(), {"i": 1})
            self.assertEqual(player.next_frame(), {"i": 2})
            self.assertIsNone(player.next_frame())

    def test_get_frame_by_index(self):
        player = ReplayPlayer()
        frames = [{"i": 0}, {"i": 1}, {"i": 2}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._create_replay_file(tmpdir, frames)
            player.load(path)

            self.assertEqual(player.get_frame(0), {"i": 0})
            self.assertEqual(player.get_frame(2), {"i": 2})
            self.assertEqual(player.get_frame(99), {})  # 범위 밖
            self.assertEqual(player.get_frame(-1), {})  # 음수

    def test_reset(self):
        player = ReplayPlayer()
        frames = [{"i": 0}, {"i": 1}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._create_replay_file(tmpdir, frames)
            player.load(path)
            player.next_frame()
            player.next_frame()
            player.reset()
            self.assertEqual(player.current_index, 0)
            self.assertEqual(player.next_frame(), {"i": 0})

    def test_seek(self):
        player = ReplayPlayer()
        frames = [{"i": j} for j in range(10)]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._create_replay_file(tmpdir, frames)
            player.load(path)
            player.seek(5)
            self.assertEqual(player.current_index, 5)
            self.assertEqual(player.next_frame(), {"i": 5})

    def test_seek_clamped(self):
        """seek()가 범위 밖 값을 클램핑해야 한다."""
        player = ReplayPlayer()
        frames = [{"i": j} for j in range(5)]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._create_replay_file(tmpdir, frames)
            player.load(path)
            player.seek(-10)
            self.assertEqual(player.current_index, 0)
            player.seek(100)
            self.assertEqual(player.current_index, 5)

    def test_prev_frame(self):
        player = ReplayPlayer()
        frames = [{"i": 0}, {"i": 1}, {"i": 2}]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._create_replay_file(tmpdir, frames)
            player.load(path)
            player.seek(2)
            self.assertEqual(player.prev_frame(), {"i": 1})
            self.assertEqual(player.prev_frame(), {"i": 0})
            self.assertIsNone(player.prev_frame())  # 처음

    def test_rewind_and_fast_forward(self):
        player = ReplayPlayer()
        frames = [{"i": j} for j in range(20)]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._create_replay_file(tmpdir, frames)
            player.load(path)
            player.seek(15)
            player.rewind(5)
            self.assertEqual(player.current_index, 10)
            player.fast_forward(3)
            self.assertEqual(player.current_index, 13)

    def test_progress(self):
        player = ReplayPlayer()
        frames = [{"i": j} for j in range(10)]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._create_replay_file(tmpdir, frames)
            player.load(path)
            self.assertAlmostEqual(player.progress, 0.0)
            player.seek(5)
            self.assertAlmostEqual(player.progress, 0.5)
            player.seek(10)
            self.assertAlmostEqual(player.progress, 1.0)

    def test_progress_empty(self):
        player = ReplayPlayer()
        self.assertAlmostEqual(player.progress, 0.0)

    def test_format_version(self):
        player = ReplayPlayer()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._create_replay_file(tmpdir, [{"x": 1}], version=1)
            player.load(path)
            self.assertEqual(player.format_version, 1)


class TestRoundTrip(unittest.TestCase):
    """녹화 → 저장 → 로드 → 재생 전체 라운드트립."""

    def test_full_roundtrip(self):
        frames = [{"pos": [i, i * 2], "active": i % 2 == 0} for i in range(50)]

        rec = ReplayRecorder("roundtrip_test")
        for frame in frames:
            rec.record_frame(frame)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("replay.REPLAY_DIR", tmpdir):
                path = rec.save(extra_metadata={"test": True})
                self.assertTrue(os.path.exists(path))

                player = ReplayPlayer()
                self.assertTrue(player.load(path))
                self.assertEqual(player.total_frames, 50)
                self.assertEqual(player.metadata["module"], "roundtrip_test")
                self.assertTrue(player.metadata["test"])

                # 모든 프레임이 원본과 일치
                for i, original in enumerate(frames):
                    self.assertEqual(player.get_frame(i), original)


class TestMigration(unittest.TestCase):
    """리플레이 포맷 마이그레이션."""

    def test_migrate_v1_noop(self):
        """v1 → v1은 변환 없어야 한다."""
        data = {"frames": [{"x": 1}]}
        result = _migrate_replay(data, 1)
        self.assertEqual(result, data)

    def test_legacy_version_triggers_migration(self):
        """v0(레거시) 로드 시 마이그레이션 후 버전이 업데이트되어야 한다."""
        player = ReplayPlayer()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "legacy.json")
            data = {
                "format_version": 0,
                "metadata": {"module": "old"},
                "frames": [{"x": 1}],
            }
            with open(filepath, "w") as f:
                json.dump(data, f)

            player.load(filepath)
            self.assertEqual(player.format_version, REPLAY_FORMAT_VERSION)


if __name__ == "__main__":
    unittest.main()
