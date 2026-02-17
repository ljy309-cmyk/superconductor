"""새 모듈 단위 테스트 — achievements, replay, presets HUD, sound, help overlay, stats."""

import json
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Achievements 테스트 ─────────────────────────────────────

class TestAchievements(unittest.TestCase):

    def setUp(self):
        import achievements
        self._orig_path = achievements._SAVE_PATH
        self._tmpdir = tempfile.mkdtemp()
        achievements._SAVE_PATH = os.path.join(self._tmpdir, "achievements.json")

    def tearDown(self):
        import achievements
        achievements._SAVE_PATH = self._orig_path
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_check_first_play(self):
        from achievements import check_achievements
        new = check_achievements("qubit_chain", {"survival_time": 5.0})
        ids = [a["id"] for a in new]
        self.assertIn("qc_first_play", ids)

    def test_check_survivor_30(self):
        from achievements import check_achievements
        new = check_achievements("qubit_chain", {"survival_time": 35.0})
        ids = [a["id"] for a in new]
        self.assertIn("qc_survivor_30", ids)

    def test_no_duplicate_unlock(self):
        from achievements import check_achievements
        check_achievements("qubit_chain", {"survival_time": 35.0})
        new = check_achievements("qubit_chain", {"survival_time": 40.0})
        ids = [a["id"] for a in new]
        self.assertNotIn("qc_first_play", ids)
        self.assertNotIn("qc_survivor_30", ids)

    def test_get_all_achievements(self):
        from achievements import get_all_achievements
        all_ach = get_all_achievements()
        self.assertGreater(len(all_ach), 10)
        self.assertIn("id", all_ach[0])
        self.assertIn("unlocked", all_ach[0])

    def test_get_unlocked_count(self):
        from achievements import get_unlocked_count
        unlocked, total = get_unlocked_count()
        self.assertIsInstance(unlocked, int)
        self.assertIsInstance(total, int)
        self.assertGreater(total, 0)

    def test_squid_mines_perfect(self):
        from achievements import check_achievements
        new = check_achievements("squid_mines", {"won": True, "wrong_marks": 0})
        ids = [a["id"] for a in new]
        self.assertIn("sq_first_win", ids)
        self.assertIn("sq_perfect", ids)

    def test_tunneling_first(self):
        from achievements import check_achievements
        new = check_achievements("tunneling", {"tunnel_count": 1, "total_attempts": 5})
        ids = [a["id"] for a in new]
        self.assertIn("tn_first_tunnel", ids)

    def test_bb84_score(self):
        from achievements import check_achievements
        new = check_achievements("bb84_defense", {"score": 600})
        ids = [a["id"] for a in new]
        self.assertIn("bb84_first_play", ids)
        self.assertIn("bb84_score_500", ids)


# ── Replay 테스트 ───────────────────────────────────────────

class TestReplay(unittest.TestCase):

    def setUp(self):
        import replay
        self._orig_dir = replay.REPLAY_DIR
        self._tmpdir = tempfile.mkdtemp()
        replay.REPLAY_DIR = self._tmpdir

    def tearDown(self):
        import replay
        replay.REPLAY_DIR = self._orig_dir
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_record_and_save(self):
        from replay import ReplayRecorder
        rec = ReplayRecorder("test_module")
        rec.record_frame({"x": 10, "y": 20})
        rec.record_frame({"x": 15, "y": 25})
        path = rec.save()
        self.assertTrue(os.path.exists(path))
        self.assertEqual(rec.frame_count, 2)

    def test_load_and_play(self):
        from replay import ReplayRecorder, ReplayPlayer
        rec = ReplayRecorder("test_module")
        for i in range(5):
            rec.record_frame({"step": i})
        path = rec.save()

        player = ReplayPlayer()
        self.assertTrue(player.load(path))
        self.assertEqual(player.total_frames, 5)

        frame = player.next_frame()
        self.assertEqual(frame["step"], 0)

        frame = player.get_frame(4)
        self.assertEqual(frame["step"], 4)

    def test_player_seek(self):
        from replay import ReplayRecorder, ReplayPlayer
        rec = ReplayRecorder("test_module")
        for i in range(10):
            rec.record_frame({"v": i})
        path = rec.save()

        player = ReplayPlayer()
        player.load(path)
        player.seek(5)
        frame = player.next_frame()
        self.assertEqual(frame["v"], 5)

    def test_list_replays(self):
        from replay import ReplayRecorder, list_replays
        rec = ReplayRecorder("test_module")
        rec.record_frame({"x": 1})
        rec.save()

        replays = list_replays("test_module")
        self.assertEqual(len(replays), 1)

        replays_all = list_replays()
        self.assertGreaterEqual(len(replays_all), 1)

    def test_empty_save_returns_empty(self):
        from replay import ReplayRecorder
        rec = ReplayRecorder("test_module")
        path = rec.save()
        self.assertEqual(path, "")

    def test_max_frames_compression(self):
        from replay import ReplayRecorder
        rec = ReplayRecorder("test_module", max_frames=100)
        for i in range(150):
            rec.record_frame({"i": i})
        self.assertLessEqual(rec.frame_count, 130)

    def test_save_includes_format_version(self):
        from replay import ReplayRecorder, REPLAY_FORMAT_VERSION
        rec = ReplayRecorder("test_module")
        rec.record_frame({"x": 1})
        path = rec.save()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["format_version"], REPLAY_FORMAT_VERSION)

    def test_load_legacy_no_version(self):
        """format_version이 없는 레거시 파일도 로드 가능."""
        from replay import ReplayPlayer
        legacy = {"metadata": {"module": "test"}, "frames": [{"a": 1}]}
        path = os.path.join(self._tmpdir, "legacy.json")
        with open(path, "w") as f:
            json.dump(legacy, f)

        player = ReplayPlayer()
        self.assertTrue(player.load(path))
        self.assertEqual(player.format_version, 1)  # 마이그레이션 후 현재 버전
        self.assertEqual(player.total_frames, 1)

    def test_load_future_version_still_works(self):
        """미래 버전 파일도 경고 후 로드 가능."""
        from replay import ReplayPlayer
        future = {"format_version": 999, "metadata": {"module": "test"},
                  "frames": [{"b": 2}]}
        path = os.path.join(self._tmpdir, "future.json")
        with open(path, "w") as f:
            json.dump(future, f)

        player = ReplayPlayer()
        self.assertTrue(player.load(path))
        self.assertEqual(player.format_version, 999)
        self.assertEqual(player.total_frames, 1)


# ── Theme Toggle 테스트 ─────────────────────────────────────

class TestThemeToggle(unittest.TestCase):

    def test_default_dark(self):
        from theme import get_theme
        self.assertEqual(get_theme(), "dark")

    def test_toggle(self):
        from theme import toggle_theme, get_theme, set_theme
        set_theme("dark")
        new_theme = toggle_theme()
        self.assertEqual(new_theme, "light")
        self.assertEqual(get_theme(), "light")
        toggle_theme()
        self.assertEqual(get_theme(), "dark")

    def test_get_tk_theme(self):
        from theme import get_tk_theme, set_theme, TK, TK_LIGHT
        set_theme("dark")
        self.assertIs(get_tk_theme(), TK)
        set_theme("light")
        self.assertIs(get_tk_theme(), TK_LIGHT)
        set_theme("dark")

    def test_get_pg_theme(self):
        from theme import get_pg_theme, set_theme, PG, PG_LIGHT
        set_theme("dark")
        self.assertIs(get_pg_theme(), PG)
        set_theme("light")
        self.assertIs(get_pg_theme(), PG_LIGHT)
        set_theme("dark")

    def test_light_theme_colors(self):
        from theme import TK_LIGHT, PG_LIGHT
        self.assertTrue(TK_LIGHT.BG.startswith("#"))
        self.assertIsInstance(PG_LIGHT.BG, tuple)
        self.assertEqual(len(PG_LIGHT.BG), 3)


# ── Report 추가 테스트 ──────────────────────────────────────

class TestReportExtended(unittest.TestCase):

    def test_report_module_titles(self):
        from report import _MODULE_TITLES
        self.assertIn("qubit_chain", _MODULE_TITLES)
        self.assertIn("bb84_defense", _MODULE_TITLES)

    def test_text_report_all_modules(self):
        from report import _generate_text_report
        tmpdir = tempfile.mkdtemp()
        try:
            for module in ["qubit_chain", "tunneling", "qec_shield"]:
                path = _generate_text_report(module, {"score": 42}, output_dir=tmpdir)
                self.assertTrue(os.path.exists(path))
        finally:
            shutil.rmtree(tmpdir)


# ── Help Overlay 테스트 ─────────────────────────────────────

class TestHelpOverlay(unittest.TestCase):

    def test_all_modules_have_help(self):
        from help_overlay import _HELP_TEXTS
        for module in ["qubit_chain", "tunneling", "qec_shield", "bb84_defense", "squid_mines", "flux_pinning"]:
            self.assertIn(module, _HELP_TEXTS)
            self.assertGreater(len(_HELP_TEXTS[module]), 5)

    def test_overlay_init(self):
        from help_overlay import HelpOverlay
        overlay = HelpOverlay("qubit_chain")
        self.assertFalse(overlay.visible)
        self.assertEqual(overlay.module_name, "qubit_chain")

    def test_unknown_module_fallback(self):
        from help_overlay import HelpOverlay
        overlay = HelpOverlay("nonexistent")
        self.assertEqual(overlay.lines, ["No help available."])


# ── Sound Manager 테스트 (without pygame init) ──────────────

class TestSoundManagerStructure(unittest.TestCase):

    def test_singleton(self):
        from sound_manager import get_sound_manager
        s1 = get_sound_manager()
        s2 = get_sound_manager()
        self.assertIs(s1, s2)

    def test_default_enabled(self):
        from sound_manager import SoundManager
        snd = SoundManager()
        self.assertTrue(snd.enabled)

    def test_toggle(self):
        from sound_manager import SoundManager
        snd = SoundManager()
        result = snd.toggle()
        self.assertFalse(result)
        result = snd.toggle()
        self.assertTrue(result)


# ── __init__.py 테스트 ──────────────────────────────────────

class TestPackageInit(unittest.TestCase):

    def test_physics_init(self):
        import physics
        self.assertIn("open_phase_transition", physics.__all__)
        self.assertIn("open_flux_pinning", physics.__all__)

    def test_quantum_init(self):
        import quantum
        self.assertIn("open_qubit_chain", quantum.__all__)

    def test_security_init(self):
        import security
        self.assertIn("open_squid_mines", security.__all__)

    def test_data_ai_init(self):
        import data_ai
        self.assertIn("PlayLogger", data_ai.__all__)

    def test_ui_init(self):
        import ui
        self.assertIn("BaseLauncher", ui.__all__)

    def test_scada_init(self):
        import scada
        self.assertIn("open_dashboard", scada.__all__)


# ── Preset HUD 테스트 (구조만, Pygame 없이) ─────────────────

class TestPresetHUDStructure(unittest.TestCase):

    def test_preset_colors_defined(self):
        from preset_hud import _PRESET_COLORS
        self.assertIn("easy", _PRESET_COLORS)
        self.assertIn("normal", _PRESET_COLORS)
        self.assertIn("hard", _PRESET_COLORS)


# ── Stats Dashboard 테스트 (구조만) ─────────────────────────

try:
    import tkinter
    _HAS_TK = True
except ImportError:
    _HAS_TK = False


@unittest.skipUnless(_HAS_TK, "tkinter not available")
class TestStatsDashboardModule(unittest.TestCase):

    def test_importable(self):
        import stats_dashboard
        self.assertTrue(hasattr(stats_dashboard, "open_stats_dashboard"))


if __name__ == "__main__":
    unittest.main()
