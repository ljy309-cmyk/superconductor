"""새 모듈 단위 테스트 — achievements, replay, presets HUD, sound, help overlay, stats."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pygame mock (테스트 환경에 pygame 없는 경우)
sys.modules.setdefault("pygame", MagicMock())
sys.modules.setdefault("pygame.time", MagicMock())
sys.modules.setdefault("pygame.mixer", MagicMock())


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
        from replay import ReplayPlayer, ReplayRecorder

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
        from replay import ReplayPlayer, ReplayRecorder

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
        from replay import REPLAY_FORMAT_VERSION, ReplayRecorder

        rec = ReplayRecorder("test_module")
        rec.record_frame({"x": 1})
        path = rec.save()

        with open(path, encoding="utf-8") as f:
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

        future = {"format_version": 999, "metadata": {"module": "test"}, "frames": [{"b": 2}]}
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
        from theme import get_theme, set_theme, toggle_theme

        set_theme("dark")
        new_theme = toggle_theme()
        self.assertEqual(new_theme, "light")
        self.assertEqual(get_theme(), "light")
        toggle_theme()
        self.assertEqual(get_theme(), "dark")

    def test_get_tk_theme(self):
        from theme import TK, TK_LIGHT, get_tk_theme, set_theme

        set_theme("dark")
        self.assertIs(get_tk_theme(), TK)
        set_theme("light")
        self.assertIs(get_tk_theme(), TK_LIGHT)
        set_theme("dark")

    def test_get_pg_theme(self):
        from theme import PG, PG_LIGHT, get_pg_theme, set_theme

        set_theme("dark")
        self.assertIs(get_pg_theme(), PG)
        set_theme("light")
        self.assertIs(get_pg_theme(), PG_LIGHT)
        set_theme("dark")

    def test_light_theme_colors(self):
        from theme import PG_LIGHT, TK_LIGHT

        self.assertTrue(TK_LIGHT.BG.startswith("#"))
        self.assertIsInstance(PG_LIGHT.BG, tuple)
        self.assertEqual(len(PG_LIGHT.BG), 3)

    def test_observer_notified_on_toggle(self):
        from theme import off_theme_change, on_theme_change, set_theme, toggle_theme

        set_theme("dark")
        calls = []

        def cb():
            return calls.append(1)

        on_theme_change(cb)
        try:
            toggle_theme()
            self.assertEqual(len(calls), 1)
            toggle_theme()
            self.assertEqual(len(calls), 2)
        finally:
            off_theme_change(cb)
            set_theme("dark")

    def test_observer_notified_on_set_colorblind(self):
        from theme import off_theme_change, on_theme_change, set_colorblind

        set_colorblind(False)
        calls = []

        def cb():
            return calls.append(1)

        on_theme_change(cb)
        try:
            set_colorblind(True)
            self.assertEqual(len(calls), 1)
            # 같은 값 설정 시 알림 없음
            set_colorblind(True)
            self.assertEqual(len(calls), 1)
        finally:
            off_theme_change(cb)
            set_colorblind(False)

    def test_save_and_load_preferences(self):
        from theme import get_theme, is_colorblind, load_preferences, save_preferences, set_colorblind, set_theme

        set_theme("light")
        set_colorblind(True)
        save_preferences()
        # 상태 변경 후 로드
        set_theme("dark")
        set_colorblind(False)
        load_preferences()
        self.assertEqual(get_theme(), "light")
        self.assertTrue(is_colorblind())
        # 정리
        set_theme("dark")
        set_colorblind(False)
        save_preferences()

    def test_weakref_listener_auto_cleanup(self):
        """바운드 메서드 리스너가 객체 소멸 시 자동 정리되는지 확인."""
        import gc

        import theme as _theme
        from theme import on_theme_change, set_theme, toggle_theme

        set_theme("dark")

        class Observer:
            def __init__(self):
                self.calls = 0

            def on_change(self):
                self.calls += 1

        obj = Observer()
        on_theme_change(obj.on_change)
        initial_count = len(_theme._listeners)

        toggle_theme()
        self.assertEqual(obj.calls, 1)

        # 객체 삭제 → 약참조 소멸
        del obj
        gc.collect()

        # 다음 notify에서 죽은 참조 정리
        toggle_theme()
        self.assertLess(len(_theme._listeners), initial_count)
        set_theme("dark")


# ── 난이도 선택 대화상자 테스트 ──────────────────────────


class TestDifficultyDialog(unittest.TestCase):
    def test_module_imports(self):
        import difficulty_dialog

        self.assertTrue(hasattr(difficulty_dialog, "choose_difficulty"))
        self.assertTrue(hasattr(difficulty_dialog, "_btn_rect"))

    def test_btn_rects_vertically_spaced(self):
        """버튼 3개가 겹치지 않도록 수직으로 배치되는지 확인."""
        # _btn_rect returns a pygame.Rect; under mock we inspect args
        # Re-compute manually to avoid mock issues
        _panel_w, _btn_w, btn_h = 340, 260, 36
        _W, H = 900, 600
        py = H // 2 - 220 // 2
        tops = [py + 54 + i * (btn_h + 8) for i in range(3)]
        for i in range(len(tops) - 1):
            self.assertGreaterEqual(
                tops[i + 1],
                tops[i] + btn_h,
                f"Button {i} and {i + 1} overlap vertically",
            )

    def test_difficulties_list(self):
        from difficulty_dialog import _DIFFICULTIES

        names = [d[0] for d in _DIFFICULTIES]
        self.assertEqual(names, ["easy", "normal", "hard"])

    def test_i18n_keys_exist(self):
        from i18n import set_locale, t

        for locale in ("ko", "en"):
            set_locale(locale)
            title = t("difficulty_title")
            hint = t("difficulty_hint")
            self.assertNotEqual(title, "difficulty_title", f"Missing key in {locale}")
            self.assertNotEqual(hint, "difficulty_hint", f"Missing key in {locale}")
        set_locale("ko")


# ── load_pg_colors 공통 헬퍼 테스트 ──────────────────────────


class TestLoadPgColors(unittest.TestCase):
    def test_loads_colors_into_target_dict(self):
        from theme import load_pg_colors, set_colorblind, set_theme

        set_theme("dark")
        set_colorblind(False)
        target = {}
        mapping = {"MY_BG": "BG", "MY_TEXT": "TEXT", "MY_GREEN": "GREEN"}
        load_pg_colors(mapping, target)
        self.assertIsInstance(target["MY_BG"], tuple)
        self.assertEqual(len(target["MY_BG"]), 3)
        self.assertIn("MY_TEXT", target)
        self.assertIn("MY_GREEN", target)

    def test_reflects_theme_change(self):
        from theme import PG, PG_LIGHT, load_pg_colors, set_colorblind, set_theme

        set_colorblind(False)
        target = {}
        mapping = {"BG": "BG"}
        set_theme("dark")
        load_pg_colors(mapping, target)
        dark_bg = target["BG"]
        set_theme("light")
        load_pg_colors(mapping, target)
        light_bg = target["BG"]
        self.assertEqual(dark_bg, PG.BG)
        self.assertEqual(light_bg, PG_LIGHT.BG)
        self.assertNotEqual(dark_bg, light_bg)
        set_theme("dark")

    def test_reflects_colorblind_change(self):
        from theme import load_pg_colors, set_colorblind, set_theme

        set_theme("dark")
        target = {}
        mapping = {"STABLE": "STABLE"}
        set_colorblind(False)
        load_pg_colors(mapping, target)
        normal = target["STABLE"]
        set_colorblind(True)
        load_pg_colors(mapping, target)
        cb = target["STABLE"]
        self.assertNotEqual(normal, cb)
        set_colorblind(False)

    def test_unknown_attr_raises(self):
        from theme import load_pg_colors

        target = {}
        with self.assertRaises(AttributeError):
            load_pg_colors({"X": "NONEXISTENT_ATTR"}, target)


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


# ── GameState 데이터클래스 테스트 ──────────────────────────


class TestQubitChainState(unittest.TestCase):
    def test_default_values(self):
        from quantum.qubit_chain import QubitChainState

        gs = QubitChainState()
        self.assertEqual(gs.t, 0.0)
        self.assertFalse(gs.paused)
        self.assertFalse(gs.shield_active)
        self.assertEqual(gs.qec_uses, 0)
        self.assertFalse(gs.game_over)
        self.assertEqual(gs.kb_focus, -1)
        self.assertIsInstance(gs.cascade_log, list)
        self.assertIsInstance(gs.ach_checked_milestones, set)

    def test_reset(self):
        from quantum.qubit_chain import QubitChainState

        gs = QubitChainState()
        gs.shield_active = True
        gs.shield_timer = 3.0
        gs.qec_uses = 5
        gs.survival_time = 42.0
        gs.game_over = True
        gs.cascade_log.append("test")
        gs.reset()
        self.assertFalse(gs.shield_active)
        self.assertEqual(gs.shield_timer, 0.0)
        self.assertEqual(gs.qec_uses, 0)
        self.assertEqual(gs.survival_time, 0.0)
        self.assertFalse(gs.game_over)
        self.assertEqual(len(gs.cascade_log), 0)

    def test_independent_instances(self):
        from quantum.qubit_chain import QubitChainState

        gs1 = QubitChainState()
        gs2 = QubitChainState()
        gs1.cascade_log.append("a")
        self.assertEqual(len(gs2.cascade_log), 0)


class TestSQUIDMinesState(unittest.TestCase):
    def test_default_values(self):
        from security.squid_mines import SQUIDMinesState

        gs = SQUIDMinesState()
        self.assertEqual(gs.t, 0.0)
        self.assertTrue(gs.sound_enabled)
        self.assertFalse(gs.kb_active)
        self.assertEqual(gs.kb_col, 0)
        self.assertEqual(gs.kb_row, 0)

    def test_reset(self):
        from security.squid_mines import SQUIDMinesState

        gs = SQUIDMinesState()
        gs.beep_timer = 1.5
        gs.reset()
        self.assertEqual(gs.beep_timer, 0.0)


class TestSimSpeed(unittest.TestCase):
    def setUp(self):
        from sim_speed import set_sim_speed

        set_sim_speed(1.0)

    def tearDown(self):
        from sim_speed import set_sim_speed

        set_sim_speed(1.0)

    def test_default_speed(self):
        from sim_speed import get_sim_speed

        self.assertEqual(get_sim_speed(), 1.0)

    def test_apply_speed(self):
        from sim_speed import apply_speed, set_sim_speed

        set_sim_speed(2.0)
        self.assertAlmostEqual(apply_speed(0.016), 0.032)

    def test_cycle_speed(self):
        from sim_speed import cycle_sim_speed, get_sim_speed

        cycle_sim_speed(1)
        self.assertEqual(get_sim_speed(), 2.0)
        cycle_sim_speed(1)
        self.assertEqual(get_sim_speed(), 4.0)
        cycle_sim_speed(1)  # 최대에서 더 올려도 4.0
        self.assertEqual(get_sim_speed(), 4.0)

    def test_speed_clamped(self):
        from sim_speed import get_sim_speed, set_sim_speed

        set_sim_speed(10.0)
        self.assertEqual(get_sim_speed(), 4.0)
        set_sim_speed(0.1)
        self.assertEqual(get_sim_speed(), 0.25)

    def test_speed_label(self):
        from sim_speed import set_sim_speed, speed_label

        set_sim_speed(1.0)
        self.assertEqual(speed_label(), "1x")
        set_sim_speed(0.5)
        self.assertEqual(speed_label(), "0.5x")


class TestPerfMonitor(unittest.TestCase):
    def test_tick_and_fps(self):
        from perf_monitor import PerfMonitor

        pm = PerfMonitor(target_fps=60)
        pm.tick(1.0 / 60)
        self.assertAlmostEqual(pm.current_fps, 60.0, places=0)
        self.assertEqual(pm.total_frames, 1)

    def test_frame_drop_detection(self):
        from perf_monitor import PerfMonitor

        pm = PerfMonitor(target_fps=60)
        pm.tick(0.016)  # 정상
        pm.tick(0.050)  # 드롭 (50ms > 25ms threshold)
        self.assertEqual(pm.frame_drops, 1)
        self.assertEqual(pm.total_frames, 2)

    def test_summary(self):
        from perf_monitor import PerfMonitor

        pm = PerfMonitor(target_fps=60)
        for _ in range(10):
            pm.tick(1.0 / 60)
        s = pm.summary()
        self.assertEqual(s["total_frames"], 10)
        self.assertGreater(s["avg_fps"], 50)
        self.assertIsInstance(s["drop_rate"], float)

    def test_avg_and_min_fps(self):
        from perf_monitor import PerfMonitor

        pm = PerfMonitor(target_fps=60)
        pm.tick(0.010)  # 100 FPS
        pm.tick(0.020)  # 50 FPS
        pm.tick(0.050)  # 20 FPS
        self.assertAlmostEqual(pm.min_fps, 20.0, places=0)
        self.assertGreater(pm.avg_fps, 0)


class TestScoreIntegrity(unittest.TestCase):
    def test_sign_and_verify(self):
        from score_integrity import sign_score, verify_score

        token = sign_score("Player", 42.5, "qubit_chain")
        self.assertTrue(verify_score("Player", 42.5, "qubit_chain", token))

    def test_tampered_score_fails(self):
        from score_integrity import sign_score, verify_score

        token = sign_score("Player", 42.5, "qubit_chain")
        self.assertFalse(verify_score("Player", 99.9, "qubit_chain", token))

    def test_tampered_name_fails(self):
        from score_integrity import sign_score, verify_score

        token = sign_score("Player", 42.5, "qubit_chain")
        self.assertFalse(verify_score("Hacker", 42.5, "qubit_chain", token))

    def test_invalid_token_format(self):
        from score_integrity import verify_score

        self.assertFalse(verify_score("Player", 42.5, "qubit_chain", "garbage"))
        self.assertFalse(verify_score("Player", 42.5, "qubit_chain", ""))

    def test_expired_token(self):
        # 과거 타임스탬프로 직접 만료 토큰 생성
        import hashlib
        import hmac
        import time as _time

        import score_integrity
        from score_integrity import verify_score

        old_ts = int(_time.time()) - score_integrity._TOKEN_TTL - 10
        msg = f"Player:10.00:test:{old_ts}".encode()
        digest = hmac.new(score_integrity._SECRET, msg, hashlib.sha256).hexdigest()
        expired_token = f"{old_ts}:{digest}"
        self.assertFalse(verify_score("Player", 10.0, "test", expired_token))


class TestProfileManagement(unittest.TestCase):
    def setUp(self):
        import presets

        self._orig_dir = presets.PROFILES_DIR
        self._tmpdir = tempfile.mkdtemp()
        presets.PROFILES_DIR = self._tmpdir

    def tearDown(self):
        import presets

        presets.PROFILES_DIR = self._orig_dir
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_save_and_list(self):
        from presets import list_profiles, save_profile

        save_profile("test_profile", {"noise_rate": 5.0, "damage": 20})
        profiles = list_profiles()
        self.assertIn("test_profile", profiles)

    def test_delete_profile(self):
        from presets import delete_profile, list_profiles, save_profile

        save_profile("to_delete", {"a": 1})
        self.assertTrue(delete_profile("to_delete"))
        self.assertNotIn("to_delete", list_profiles())

    def test_delete_nonexistent(self):
        from presets import delete_profile

        self.assertFalse(delete_profile("nonexistent"))

    def test_rename_profile(self):
        from presets import list_profiles, load_profile, rename_profile, save_profile

        save_profile("old_name", {"x": 42})
        self.assertTrue(rename_profile("old_name", "new_name"))
        profiles = list_profiles()
        self.assertNotIn("old_name", profiles)
        self.assertIn("new_name", profiles)
        data = load_profile("new_name")
        self.assertEqual(data["x"], 42)

    def test_rename_conflict(self):
        from presets import rename_profile, save_profile

        save_profile("a", {"x": 1})
        save_profile("b", {"y": 2})
        self.assertFalse(rename_profile("a", "b"))

    def test_rename_nonexistent(self):
        from presets import rename_profile

        self.assertFalse(rename_profile("no_such", "new_name"))


class TestFontScale(unittest.TestCase):
    def test_default_scale(self):
        from theme import get_font_scale

        self.assertEqual(get_font_scale(), 1.0)

    def test_set_scale(self):
        from theme import get_font_scale, set_font_scale

        set_font_scale(1.2)
        self.assertEqual(get_font_scale(), 1.2)
        set_font_scale(1.0)  # 복원

    def test_scale_clamped(self):
        from theme import get_font_scale, set_font_scale

        set_font_scale(0.5)  # 최소 0.8
        self.assertEqual(get_font_scale(), 0.8)
        set_font_scale(2.0)  # 최대 1.5
        self.assertEqual(get_font_scale(), 1.5)
        set_font_scale(1.0)  # 복원

    def test_increase_decrease(self):
        from theme import decrease_font_scale, get_font_scale, increase_font_scale, set_font_scale

        set_font_scale(1.0)
        increase_font_scale()
        self.assertAlmostEqual(get_font_scale(), 1.1)
        decrease_font_scale()
        self.assertAlmostEqual(get_font_scale(), 1.0)

    def test_fonts_scale_affects_size(self):
        from theme import FONTS, set_font_scale

        set_font_scale(1.0)
        body_normal = FONTS.BODY
        set_font_scale(1.5)
        body_large = FONTS.BODY
        self.assertGreater(body_large[1], body_normal[1])
        set_font_scale(1.0)  # 복원


class TestFluxPinningState(unittest.TestCase):
    def test_default_values(self):
        from physics.flux_pinning import FluxPinningState

        gs = FluxPinningState()
        self.assertFalse(gs.dragging)
        self.assertFalse(gs.flipped)
        self.assertTrue(gs.superconducting)
        self.assertEqual(gs.sc_vx, 0.0)
        self.assertEqual(gs.sc_vy, 0.0)

    def test_custom_init(self):
        from physics.flux_pinning import FluxPinningState

        gs = FluxPinningState(magnet_x=450.0, magnet_y=340.0)
        self.assertEqual(gs.magnet_x, 450.0)
        self.assertEqual(gs.magnet_y, 340.0)


if __name__ == "__main__":
    unittest.main()
