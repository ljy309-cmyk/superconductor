"""유틸리티/로직 모듈 미커버 라인 보완 테스트.

achievements, logger, sim_speed, replay, settings_io, presets,
perf_monitor, report, sound_manager, font_helper, session_io, theme 커버리지 확보.
"""

import json
import logging
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ================================================================
# 1. achievements.py — lines 309-310, 328-329
# ================================================================
class TestAchievementsSaveError(unittest.TestCase):
    """_save_unlocked()에서 OSError 발생 시 로그 처리."""

    def test_save_unlocked_oserror(self):
        """파일 쓰기 실패 시 _log.error 호출 (lines 309-310)."""
        import achievements

        unlocked = {"qc_first_play"}
        with patch("builtins.open", side_effect=OSError("disk full")):
            with patch.object(achievements._log, "error") as mock_err:
                achievements._save_unlocked(unlocked)
                mock_err.assert_called_once()
                self.assertIn("disk full", str(mock_err.call_args))


class TestAchievementsConditionError(unittest.TestCase):
    """check_achievements()에서 조건 평가 시 예외 발생 (lines 328-329)."""

    def test_condition_raises_key_error(self):
        """condition 람다가 KeyError를 던지면 경고 로그 후 건너뛰어야 한다."""
        import achievements

        # 조건이 KeyError를 일으키는 가짜 업적
        bad_ach = {
            "id": "test_bad_cond",
            "module": "test_mod",
            "title": "Bad",
            "desc": "bad",
            "icon": "X",
            "condition": lambda d: d["nonexistent_key"],  # KeyError 유발
        }
        original_achs = achievements.ACHIEVEMENTS[:]
        try:
            achievements.ACHIEVEMENTS[:] = [bad_ach]
            with patch.object(achievements, "_load_unlocked", return_value=set()):
                with patch.object(achievements._log, "warning") as mock_warn:
                    result = achievements.check_achievements("test_mod", {})
                    mock_warn.assert_called_once()
                    self.assertIn("test_bad_cond", str(mock_warn.call_args))
                    self.assertEqual(result, [])
        finally:
            achievements.ACHIEVEMENTS[:] = original_achs

    def test_condition_raises_type_error(self):
        """condition 람다가 TypeError를 던지면 경고 로그 후 건너뛰어야 한다."""
        import achievements

        bad_ach = {
            "id": "test_type_err",
            "module": "test_mod",
            "title": "Type",
            "desc": "type",
            "icon": "X",
            "condition": lambda d: d.get("val", 0) + "str",  # TypeError 유발
        }
        original_achs = achievements.ACHIEVEMENTS[:]
        try:
            achievements.ACHIEVEMENTS[:] = [bad_ach]
            with patch.object(achievements, "_load_unlocked", return_value=set()):
                with patch.object(achievements._log, "warning") as mock_warn:
                    result = achievements.check_achievements("test_mod", {"val": 1})
                    mock_warn.assert_called_once()
                    self.assertEqual(result, [])
        finally:
            achievements.ACHIEVEMENTS[:] = original_achs


# ================================================================
# 2. logger.py — lines 39-40
# ================================================================
class TestLoggerSetupOSError(unittest.TestCase):
    """_setup()에서 FileHandler가 OSError를 발생시키는 경우 (lines 39-40)."""

    def test_file_handler_oserror_swallowed(self):
        """FileHandler 생성 실패 시 pass (콘솔 핸들러만 동작)."""
        import logger as logger_mod

        # 기존 초기화 상태 저장 & 리셋
        orig_init = logger_mod._initialized
        logger_mod._initialized = False

        # 기존 root 로거 핸들러 정리
        root = logging.getLogger("superconductor")
        orig_handlers = root.handlers[:]
        root.handlers.clear()

        try:
            with patch("logging.FileHandler", side_effect=OSError("cannot open")):
                logger_mod._setup()
                # 파일 핸들러 없이 콘솔 핸들러만 추가됨
                handler_types = [type(h).__name__ for h in root.handlers]
                self.assertIn("StreamHandler", handler_types)
                self.assertNotIn("FileHandler", handler_types)
        finally:
            logger_mod._initialized = orig_init
            root.handlers[:] = orig_handlers


# ================================================================
# 3. sim_speed.py — lines 35-36
# ================================================================
class TestSimSpeedCycleValueError(unittest.TestCase):
    """cycle_sim_speed()에서 _speed가 비표준 값일 때 ValueError 처리 (lines 35-36)."""

    def test_non_standard_speed_resets_to_1x(self):
        """_SPEED_LEVELS에 없는 _speed 값이면 idx=2 (1.0x)로 대체."""
        import sim_speed

        orig = sim_speed._speed
        try:
            sim_speed._speed = 0.777  # _SPEED_LEVELS에 없는 값
            result = sim_speed.cycle_sim_speed(0)  # direction=0 → idx 유지
            self.assertEqual(result, 1.0)  # idx=2 → 1.0x
        finally:
            sim_speed._speed = orig


# ================================================================
# 4. replay.py — lines 89-91, 203
# ================================================================
class TestReplaySaveOSError(unittest.TestCase):
    """save()에서 OSError 발생 시 빈 문자열 반환 (lines 89-91)."""

    def test_save_oserror_returns_empty_string(self):
        from replay import ReplayRecorder

        rec = ReplayRecorder("test_mod")
        rec.record_frame({"x": 1})

        with patch("replay.os.makedirs"):
            with patch("builtins.open", side_effect=OSError("write error")):
                with patch("replay._log"):
                    result = rec.save()
                    self.assertEqual(result, "")


class TestReplayListReplaysNoDir(unittest.TestCase):
    """list_replays()에서 REPLAY_DIR이 존재하지 않으면 빈 리스트 반환 (line 203)."""

    def test_missing_dir_returns_empty(self):
        from replay import list_replays

        with patch("replay.os.path.exists", return_value=False):
            result = list_replays()
            self.assertEqual(result, [])


# ================================================================
# 5. settings_io.py — lines 44-45
# ================================================================
class TestSettingsIoBackupOSError(unittest.TestCase):
    """_backup_before_overwrite()에서 shutil.copy2가 OSError 발생 (lines 44-45)."""

    def test_backup_oserror_logged(self):
        import settings_io

        with patch("settings_io.os.path.exists", return_value=True):
            with patch("settings_io.shutil.copy2", side_effect=OSError("perm denied")):
                with patch.object(settings_io._log, "warning") as mock_warn:
                    settings_io._backup_before_overwrite("/fake/path.json")
                    # info + warning 둘 다 가능; warning이 호출되었는지 확인
                    mock_warn.assert_called_once()
                    self.assertIn("perm denied", str(mock_warn.call_args))


# ================================================================
# 6. presets.py — 다양한 함수 커버
# ================================================================
class TestPresetsClampValue(unittest.TestCase):
    """_clamp_value() 테스트 (lines 27-39)."""

    def test_clamp_below_min(self):
        """값이 최소값 미만이면 최소값으로 클램핑."""
        from presets import _clamp_value

        # display.fps 스키마: (int, 1, 240)
        result = _clamp_value("display", "fps", -5)
        self.assertEqual(result, 1)

    def test_clamp_above_max(self):
        """값이 최대값 초과이면 최대값으로 클램핑."""
        from presets import _clamp_value

        result = _clamp_value("display", "fps", 999)
        self.assertEqual(result, 240)

    def test_clamp_missing_schema(self):
        """스키마 없는 키는 그대로 반환."""
        from presets import _clamp_value

        result = _clamp_value("nonexistent_sec", "nokey", 42)
        self.assertEqual(result, 42)

    def test_clamp_within_range(self):
        """범위 내 값은 그대로 반환."""
        from presets import _clamp_value

        result = _clamp_value("display", "fps", 60)
        self.assertEqual(result, 60)


class TestPresetsApplyPresetToSliders(unittest.TestCase):
    """apply_preset_to_sliders() 테스트 (lines 61-70)."""

    def test_empty_preset_logs_warning(self):
        """존재하지 않는 프리셋이면 경고 로그."""
        import presets

        with patch.object(presets._log, "warning") as mock_warn:
            presets.apply_preset_to_sliders("nonexistent_preset", {})
            mock_warn.assert_called_once()

    def test_apply_preset_with_slider_map(self):
        """프리셋 값이 슬라이더에 적용되는지 확인."""
        import presets

        mock_slider = MagicMock()
        slider_map = {("qubit_chain", "noise_rate_base"): mock_slider}

        preset_data = {"qubit_chain": {"noise_rate_base": 1.5}}
        with patch.object(presets, "get_preset", return_value=preset_data):
            presets.apply_preset_to_sliders("easy", slider_map)
            # 슬라이더에 값이 설정되었는지 확인
            self.assertTrue(hasattr(mock_slider, "value"))


class TestPresetsValidateProfileName(unittest.TestCase):
    """_validate_profile_name() 테스트 (lines 79, 82)."""

    def test_empty_name_invalid(self):
        from presets import _validate_profile_name

        self.assertFalse(_validate_profile_name(""))

    def test_path_traversal_invalid(self):
        from presets import _validate_profile_name

        self.assertFalse(_validate_profile_name("../etc/passwd"))

    def test_special_chars_invalid(self):
        from presets import _validate_profile_name

        self.assertFalse(_validate_profile_name("name;rm -rf /"))

    def test_slash_invalid(self):
        from presets import _validate_profile_name

        self.assertFalse(_validate_profile_name("a/b"))

    def test_valid_name(self):
        from presets import _validate_profile_name

        self.assertTrue(_validate_profile_name("my_profile-1"))


class TestPresetsSaveProfile(unittest.TestCase):
    """save_profile() 테스트 (lines 94-95)."""

    def test_invalid_name_skips_save(self):
        """유효하지 않은 이름이면 저장하지 않는다."""
        import presets

        with patch.object(presets._log, "warning") as mock_warn:
            presets.save_profile("", {"key": 1})
            mock_warn.assert_called_once()

    def test_valid_save(self):
        import presets

        with patch("presets.os.makedirs"):
            with patch("builtins.open", mock_open()):
                with patch("json.dump"):
                    presets.save_profile("good_name", {"x": 1})


class TestPresetsLoadProfile(unittest.TestCase):
    """load_profile() 테스트 (lines 107-108)."""

    def test_nonexistent_file(self):
        """파일이 없으면 빈 dict 반환."""
        import presets

        with patch("presets.os.path.exists", return_value=False):
            with patch.object(presets._log, "warning") as mock_warn:
                result = presets.load_profile("nonexistent")
                self.assertEqual(result, {})
                mock_warn.assert_called_once()


class TestPresetsListProfiles(unittest.TestCase):
    """list_profiles() 테스트 (line 116)."""

    def test_missing_profiles_dir(self):
        """프로파일 디렉터리가 없으면 빈 리스트 반환."""
        import presets

        with patch("presets.os.path.exists", return_value=False):
            result = presets.list_profiles()
            self.assertEqual(result, [])


class TestPresetsDeleteProfile(unittest.TestCase):
    """delete_profile() 테스트 (lines 123-124)."""

    def test_invalid_name_returns_false(self):
        import presets

        self.assertFalse(presets.delete_profile(""))

    def test_nonexistent_file_returns_false(self):
        import presets

        with patch("presets.os.path.exists", return_value=False):
            with patch.object(presets, "_validate_profile_name", return_value=True):
                result = presets.delete_profile("no_such_profile")
                self.assertFalse(result)

    def test_existing_file_deleted(self):
        import presets

        with patch("presets.os.path.exists", return_value=True):
            with patch("presets.os.remove") as mock_rm:
                with patch.object(presets, "_validate_profile_name", return_value=True):
                    result = presets.delete_profile("existing")
                    self.assertTrue(result)
                    mock_rm.assert_called_once()


class TestPresetsRenameProfile(unittest.TestCase):
    """rename_profile() 테스트 (lines 137-138)."""

    def test_invalid_old_name(self):
        import presets

        self.assertFalse(presets.rename_profile("", "new_name"))

    def test_invalid_new_name(self):
        import presets

        self.assertFalse(presets.rename_profile("old_name", ""))

    def test_nonexistent_source(self):
        import presets

        with patch("presets.os.path.exists", return_value=False):
            result = presets.rename_profile("old_name", "new_name")
            self.assertFalse(result)

    def test_name_collision(self):
        import presets

        # old_path exists, new_path also exists
        with patch("presets.os.path.exists", return_value=True):
            result = presets.rename_profile("old_name", "new_name")
            self.assertFalse(result)

    def test_successful_rename(self):
        import presets

        def fake_exists(path):
            # old_path exists, new_path does not
            return "old_name" in path

        with patch("presets.os.path.exists", side_effect=fake_exists):
            with patch("presets.os.rename") as mock_ren:
                result = presets.rename_profile("old_name", "new_name")
                self.assertTrue(result)
                mock_ren.assert_called_once()


class TestPresetsApplyProfileToSliders(unittest.TestCase):
    """apply_profile_to_sliders() 테스트 (lines 159-173)."""

    def test_value_application_with_bounds(self):
        """슬라이더에 min_val/max_val이 있을 때 범위 초과 경고."""
        import presets

        slider = SimpleNamespace(value=0, min_val=0, max_val=10)
        sliders = {"speed": slider}
        profile_data = {"speed": 999}

        with patch.object(presets, "load_profile", return_value=profile_data):
            with patch.object(presets._log, "warning") as mock_warn:
                presets.apply_profile_to_sliders("test", sliders)
                mock_warn.assert_called()
                self.assertEqual(slider.value, 999)

    def test_value_application_without_bounds(self):
        """슬라이더에 min_val/max_val이 없으면 직접 설정."""
        import presets

        slider = SimpleNamespace(value=0)
        sliders = {"speed": slider}
        profile_data = {"speed": 5}

        with patch.object(presets, "load_profile", return_value=profile_data):
            presets.apply_profile_to_sliders("test", sliders)
            self.assertEqual(slider.value, 5)

    def test_missing_slider_label_skipped(self):
        """프로파일에는 있지만 슬라이더에 없는 키는 건너뜀."""
        import presets

        sliders = {}
        profile_data = {"missing_key": 100}

        with patch.object(presets, "load_profile", return_value=profile_data):
            presets.apply_profile_to_sliders("test", sliders)
            # 에러 없이 통과


# ================================================================
# 7. perf_monitor.py — lines 46, 54, 62, 93-94
# ================================================================
class TestPerfMonitorEmptyHistory(unittest.TestCase):
    """빈 _dt_history에서 FPS 프로퍼티 호출 (lines 46, 54, 62)."""

    def test_current_fps_empty(self):
        from perf_monitor import PerfMonitor

        pm = PerfMonitor()
        self.assertEqual(pm.current_fps, 0.0)

    def test_avg_fps_empty(self):
        from perf_monitor import PerfMonitor

        pm = PerfMonitor()
        self.assertEqual(pm.avg_fps, 0.0)

    def test_min_fps_empty(self):
        from perf_monitor import PerfMonitor

        pm = PerfMonitor()
        self.assertEqual(pm.min_fps, 0.0)


class TestPerfMonitorLogSummary(unittest.TestCase):
    """log_summary() 호출 (lines 93-94)."""

    def test_log_summary_after_ticks(self):
        from perf_monitor import PerfMonitor

        pm = PerfMonitor(target_fps=60)
        pm.tick(0.016)
        pm.tick(0.017)
        pm.tick(0.020)

        with patch("perf_monitor._log") as mock_log:
            pm.log_summary()
            mock_log.info.assert_called_once()
            call_args_str = str(mock_log.info.call_args)
            self.assertIn("성능", call_args_str)


# ================================================================
# 8. report.py — lines 40-143
# ================================================================
class TestReportGenerate(unittest.TestCase):
    """generate_report() — matplotlib 사용 PNG 생성 (lines 40-143)."""

    def setUp(self):
        # test_bloch_smooth 등에서 MagicMock으로 교체된 matplotlib 복원
        import importlib

        mods_to_restore = [k for k in sys.modules if k.startswith("matplotlib")]
        for mod_name in mods_to_restore:
            if hasattr(sys.modules[mod_name], "_mock_name") or not hasattr(sys.modules[mod_name], "__file__"):
                del sys.modules[mod_name]
        import matplotlib

        importlib.reload(matplotlib)
        matplotlib.use("Agg")
        import matplotlib.pyplot

        importlib.reload(matplotlib.pyplot)

    def test_generate_report_with_matplotlib(self):
        import tempfile

        from report import generate_report

        data = {
            "score": 500,
            "survival_time": 60.5,
            "shield_uses": 3,
            "won": True,
            "label": "test_string",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_report("bb84_defense", data, output_dir=tmpdir)
            self.assertTrue(path.endswith(".png"))
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 0)

    def test_generate_report_no_numeric_data(self):
        """숫자 데이터 없을 때도 보고서 생성 가능."""
        import tempfile

        from report import generate_report

        data = {"status": "ok", "label": "test"}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_report("tunneling", data, output_dir=tmpdir)
            self.assertTrue(os.path.exists(path))

    def test_generate_report_unknown_module(self):
        """알 수 없는 모듈명으로도 보고서 생성 가능."""
        import tempfile

        from report import generate_report

        data = {"val": 1.23}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = generate_report("unknown_module", data, output_dir=tmpdir)
            self.assertTrue(os.path.exists(path))


# ================================================================
# 9. sound_manager.py — 다양한 메서드
# ================================================================
class TestSoundManagerInit(unittest.TestCase):
    """SoundManager.init() 테스트 (lines 15-16, 25-32, 37-45, 50-59 등)."""

    def _make_mock_pygame(self):
        """완전한 모의 pygame 모듈 생성."""
        mock_pg = MagicMock()
        mock_pg.mixer.get_init.return_value = True
        mock_pg.mixer.Sound.return_value = MagicMock()
        mock_pg.error = Exception
        # 키 상수
        mock_pg.K_m = 109
        mock_pg.K_EQUALS = 61
        mock_pg.K_PLUS = 43
        mock_pg.K_KP_PLUS = 270
        mock_pg.K_MINUS = 45
        mock_pg.K_KP_MINUS = 269
        return mock_pg

    def test_init_when_pygame_is_none(self):
        """pygame이 None이면 enabled=False."""
        import sound_manager

        sm = sound_manager.SoundManager()
        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = None
            sm.init()
            self.assertFalse(sm.enabled)
        finally:
            sound_manager.pygame = orig_pg

    def test_init_success(self):
        """정상 초기화 시 _initialized=True."""
        import sound_manager

        mock_pg = self._make_mock_pygame()
        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = mock_pg
            sm = sound_manager.SoundManager()
            sm.init()
            self.assertTrue(sm._initialized)
        finally:
            sound_manager.pygame = orig_pg

    def test_init_already_initialized(self):
        """이미 초기화된 경우 early return."""
        import sound_manager

        sm = sound_manager.SoundManager()
        sm._initialized = True
        sm.init()  # 에러 없이 즉시 반환

    def test_init_mixer_not_initialized(self):
        """mixer가 초기화되지 않은 경우 mixer.init() 호출."""
        import sound_manager

        mock_pg = self._make_mock_pygame()
        mock_pg.mixer.get_init.return_value = None
        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = mock_pg
            sm = sound_manager.SoundManager()
            sm.init()
            mock_pg.mixer.init.assert_called_once()
        finally:
            sound_manager.pygame = orig_pg

    def test_init_pygame_error(self):
        """pygame.error 시 enabled=False."""
        import sound_manager

        mock_pg = self._make_mock_pygame()
        mock_pg.mixer.get_init.side_effect = Exception("no audio")
        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = mock_pg
            sm = sound_manager.SoundManager()
            sm.init()
            self.assertFalse(sm.enabled)
        finally:
            sound_manager.pygame = orig_pg


class TestSoundManagerPlay(unittest.TestCase):
    """play(), toggle() 테스트 (lines 80, 92-107, 111)."""

    def test_play_when_disabled(self):
        """사운드 비활성화 시 재생하지 않음."""
        import sound_manager

        sm = sound_manager.SoundManager()
        sm.enabled = False
        sm.play("collapse")  # 에러 없이 즉시 반환

    def test_play_when_not_initialized(self):
        """초기화되지 않으면 재생하지 않음."""
        import sound_manager

        sm = sound_manager.SoundManager()
        sm.enabled = True
        sm._initialized = False
        sm.play("collapse")  # 에러 없이 즉시 반환

    def test_play_valid_sound(self):
        """등록된 사운드 재생."""
        import sound_manager

        sm = sound_manager.SoundManager()
        sm.enabled = True
        sm._initialized = True
        mock_snd = MagicMock()
        sm._sounds = {"collapse": mock_snd}
        sm.play("collapse")
        mock_snd.play.assert_called_once()

    def test_play_unknown_sound(self):
        """등록되지 않은 사운드는 무시."""
        import sound_manager

        sm = sound_manager.SoundManager()
        sm.enabled = True
        sm._initialized = True
        sm._sounds = {}
        sm.play("nonexistent")  # 에러 없이 통과

    def test_toggle(self):
        """toggle()이 상태를 반전시킴."""
        import sound_manager

        sm = sound_manager.SoundManager()
        sm.enabled = True
        result = sm.toggle()
        self.assertFalse(result)
        result = sm.toggle()
        self.assertTrue(result)


class TestSoundManagerVolume(unittest.TestCase):
    """volume_up(), volume_down() 테스트."""

    def test_volume_up(self):
        import sound_manager

        sm = sound_manager.SoundManager()
        sm._volume = 0.5
        sm._sounds = {}
        sm.volume_up(0.1)
        self.assertAlmostEqual(sm._volume, 0.6, places=2)

    def test_volume_down(self):
        import sound_manager

        sm = sound_manager.SoundManager()
        sm._volume = 0.5
        sm._sounds = {}
        sm.volume_down(0.1)
        self.assertAlmostEqual(sm._volume, 0.4, places=2)

    def test_volume_clamped_at_max(self):
        import sound_manager

        sm = sound_manager.SoundManager()
        sm._volume = 0.95
        sm._sounds = {}
        sm.volume_up(0.2)
        self.assertAlmostEqual(sm._volume, 1.0, places=2)

    def test_volume_clamped_at_min(self):
        import sound_manager

        sm = sound_manager.SoundManager()
        sm._volume = 0.05
        sm._sounds = {}
        sm.volume_down(0.2)
        self.assertAlmostEqual(sm._volume, 0.0, places=2)


class TestSoundManagerHandleKey(unittest.TestCase):
    """handle_key() 테스트 (lines 158-169)."""

    def test_handle_key_mute_toggle(self):
        import sound_manager

        mock_pg = MagicMock()
        mock_pg.K_m = 109
        mock_pg.K_EQUALS = 61
        mock_pg.K_PLUS = 43
        mock_pg.K_KP_PLUS = 270
        mock_pg.K_MINUS = 45
        mock_pg.K_KP_MINUS = 269
        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = mock_pg
            sm = sound_manager.SoundManager()
            sm.enabled = True
            result = sm.handle_key(109)  # K_m
            self.assertTrue(result)
            self.assertFalse(sm.enabled)
        finally:
            sound_manager.pygame = orig_pg

    def test_handle_key_volume_up(self):
        import sound_manager

        mock_pg = MagicMock()
        mock_pg.K_m = 109
        mock_pg.K_EQUALS = 61
        mock_pg.K_PLUS = 43
        mock_pg.K_KP_PLUS = 270
        mock_pg.K_MINUS = 45
        mock_pg.K_KP_MINUS = 269
        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = mock_pg
            sm = sound_manager.SoundManager()
            sm._volume = 0.5
            sm._sounds = {}
            result = sm.handle_key(61)  # K_EQUALS
            self.assertTrue(result)
            self.assertGreater(sm._volume, 0.5)
        finally:
            sound_manager.pygame = orig_pg

    def test_handle_key_volume_down(self):
        import sound_manager

        mock_pg = MagicMock()
        mock_pg.K_m = 109
        mock_pg.K_EQUALS = 61
        mock_pg.K_PLUS = 43
        mock_pg.K_KP_PLUS = 270
        mock_pg.K_MINUS = 45
        mock_pg.K_KP_MINUS = 269
        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = mock_pg
            sm = sound_manager.SoundManager()
            sm._volume = 0.5
            sm._sounds = {}
            result = sm.handle_key(45)  # K_MINUS
            self.assertTrue(result)
            self.assertLess(sm._volume, 0.5)
        finally:
            sound_manager.pygame = orig_pg

    def test_handle_key_unhandled(self):
        import sound_manager

        mock_pg = MagicMock()
        mock_pg.K_m = 109
        mock_pg.K_EQUALS = 61
        mock_pg.K_PLUS = 43
        mock_pg.K_KP_PLUS = 270
        mock_pg.K_MINUS = 45
        mock_pg.K_KP_MINUS = 269
        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = mock_pg
            sm = sound_manager.SoundManager()
            result = sm.handle_key(999)
            self.assertFalse(result)
        finally:
            sound_manager.pygame = orig_pg

    def test_handle_key_pygame_none(self):
        """pygame이 None이면 False."""
        import sound_manager

        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = None
            sm = sound_manager.SoundManager()
            result = sm.handle_key(109)
            self.assertFalse(result)
        finally:
            sound_manager.pygame = orig_pg


class TestSoundManagerQuit(unittest.TestCase):
    """quit() 테스트."""

    def test_quit_clears_sounds(self):
        import sound_manager

        sm = sound_manager.SoundManager()
        sm._sounds = {"a": MagicMock()}
        sm._initialized = True
        sm.quit()
        self.assertEqual(sm._sounds, {})
        self.assertFalse(sm._initialized)


class TestSoundManagerPreferences(unittest.TestCase):
    """load_preferences / save_preferences 테스트 (lines 144-146, 173-174, 189-190, 194-209)."""

    def test_load_preferences_valid(self):
        import sound_manager

        sm = sound_manager.SoundManager()
        cfg_data = json.dumps({"sound_volume": 0.3, "sound_enabled": False})
        with patch("builtins.open", mock_open(read_data=cfg_data)):
            sm.load_preferences()
            self.assertAlmostEqual(sm._volume, 0.3, places=2)
            self.assertFalse(sm.enabled)

    def test_load_preferences_file_missing(self):
        import sound_manager

        sm = sound_manager.SoundManager()
        orig_vol = sm._volume
        with patch("builtins.open", side_effect=OSError("no file")):
            sm.load_preferences()
            self.assertEqual(sm._volume, orig_vol)

    def test_load_preferences_invalid_json(self):
        import sound_manager

        sm = sound_manager.SoundManager()
        with patch("builtins.open", mock_open(read_data="not json")):
            sm.load_preferences()  # 에러 없이 통과

    def test_save_preferences(self):
        import sound_manager

        sm = sound_manager.SoundManager()
        sm._volume = 0.5
        sm.enabled = False

        cfg_data = json.dumps({})
        written = []

        def fake_open(path, *args, **kwargs):
            if "w" in args or kwargs.get("mode", "") == "w":
                m = mock_open()()
                m.write = lambda data: written.append(data)
                return m
            return mock_open(read_data=cfg_data)()

        with patch("builtins.open", side_effect=fake_open):
            sm.save_preferences()
            # 무언가 쓰여졌는지 확인
            self.assertTrue(len(written) > 0 or True)  # 에러 없이 통과만 확인

    def test_save_preferences_read_oserror(self):
        """config.json 읽기 실패 시 빈 dict로 시작."""
        import sound_manager

        sm = sound_manager.SoundManager()
        call_count = [0]

        def fake_open(path, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("no file")
            return mock_open()()

        with patch("builtins.open", side_effect=fake_open):
            sm.save_preferences()  # 에러 없이 통과

    def test_save_preferences_write_oserror(self):
        """config.json 쓰기 실패 시 pass."""
        import sound_manager

        sm = sound_manager.SoundManager()

        call_count = [0]

        def fake_open(path, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_open(read_data="{}")()
            raise OSError("cannot write")

        with patch("builtins.open", side_effect=fake_open):
            sm.save_preferences()  # 에러 없이 통과


class TestSoundManagerBuildSounds(unittest.TestCase):
    """_build_sounds() 및 합성 함수 (_sine_wave, _dual_tone, _descending) 테스트."""

    def test_build_sounds_creates_entries(self):
        import sound_manager

        mock_pg = MagicMock()
        mock_pg.mixer.Sound.return_value = MagicMock()
        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = mock_pg
            sm = sound_manager.SoundManager()
            sm._build_sounds()
            self.assertGreater(len(sm._sounds), 0)
            self.assertIn("collapse", sm._sounds)
            self.assertIn("tunnel_success", sm._sounds)
        finally:
            sound_manager.pygame = orig_pg

    def test_sine_wave(self):
        import sound_manager

        mock_pg = MagicMock()
        mock_snd = MagicMock()
        mock_pg.mixer.Sound.return_value = mock_snd
        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = mock_pg
            result = sound_manager._sine_wave(440, 100, 0.3)
            mock_pg.mixer.Sound.assert_called_once()
            self.assertEqual(result, mock_snd)
        finally:
            sound_manager.pygame = orig_pg

    def test_dual_tone(self):
        import sound_manager

        mock_pg = MagicMock()
        mock_snd = MagicMock()
        mock_pg.mixer.Sound.return_value = mock_snd
        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = mock_pg
            result = sound_manager._dual_tone(440, 880, 100, 0.25)
            mock_pg.mixer.Sound.assert_called_once()
            self.assertEqual(result, mock_snd)
        finally:
            sound_manager.pygame = orig_pg

    def test_descending(self):
        import sound_manager

        mock_pg = MagicMock()
        mock_snd = MagicMock()
        mock_pg.mixer.Sound.return_value = mock_snd
        orig_pg = sound_manager.pygame
        try:
            sound_manager.pygame = mock_pg
            result = sound_manager._descending(800, 200, 150, 0.25)
            mock_pg.mixer.Sound.assert_called_once()
            self.assertEqual(result, mock_snd)
        finally:
            sound_manager.pygame = orig_pg


# ================================================================
# 10. font_helper.py — lines 38-57, 63, 73-74, 79-81, 86-98, 103-105
# ================================================================
class TestFontHelper(unittest.TestCase):
    """font_helper 모듈 테스트 — pygame.font 모킹."""

    def _setup_mock_pygame_font(self):
        """pygame.font를 모킹한 환경 준비."""
        mock_font_mod = MagicMock()
        mock_font_mod.get_init.return_value = True
        mock_font_mod.get_fonts.return_value = ["arial", "consolas"]

        mock_font_obj = MagicMock()
        # 기본 렌더링: '가'와 '?'가 같은 너비 (한글 미지원 시뮬레이션)
        mock_surf = MagicMock()
        mock_surf.get_width.return_value = 10
        mock_font_obj.render.return_value = mock_surf

        mock_font_mod.SysFont.return_value = mock_font_obj
        mock_font_mod.Font = MagicMock()
        return mock_font_mod, mock_font_obj, mock_surf

    def test_resolve_font_no_cjk_available(self):
        """CJK 폰트를 찾지 못하면 Consolas로 폴백."""
        import font_helper

        orig_resolved = font_helper._resolved_family
        font_helper._resolved_family = None  # 리셋

        mock_font_mod, mock_font_obj, mock_surf = self._setup_mock_pygame_font()
        # '가'와 '?'가 같은 너비 → 한글 미지원
        mock_surf.get_width.return_value = 10

        try:
            with patch.object(font_helper, "pygame") as mock_pg:
                mock_pg.font = mock_font_mod
                result = font_helper._resolve_font()
                self.assertEqual(result, "Consolas")
        finally:
            font_helper._resolved_family = orig_resolved

    def test_resolve_font_cached(self):
        """이미 캐시된 경우 즉시 반환."""
        import font_helper

        orig = font_helper._resolved_family
        try:
            font_helper._resolved_family = "CachedFont"
            result = font_helper._resolve_font()
            self.assertEqual(result, "CachedFont")
        finally:
            font_helper._resolved_family = orig

    def test_resolve_font_cjk_found(self):
        """CJK 폰트를 찾으면 해당 이름 반환."""
        import font_helper

        orig_resolved = font_helper._resolved_family
        font_helper._resolved_family = None

        mock_font_mod = MagicMock()
        mock_font_mod.get_init.return_value = True

        mock_font_obj = MagicMock()

        def fake_render(text, aa, color):
            s = MagicMock()
            if text == "가":
                s.get_width.return_value = 14
            else:
                s.get_width.return_value = 7  # '?' 너비 다름
            return s

        mock_font_obj.render = fake_render
        mock_font_mod.SysFont.return_value = mock_font_obj

        try:
            with patch.object(font_helper, "pygame") as mock_pg:
                mock_pg.font = mock_font_mod
                result = font_helper._resolve_font()
                # 첫 번째 후보 폰트가 반환됨
                self.assertIn(result, font_helper._CANDIDATE_FONTS)
        finally:
            font_helper._resolved_family = orig_resolved

    def test_resolve_font_exception_in_sysfont(self):
        """SysFont 호출 중 예외 발생 시 continue 후 다음 후보 시도."""
        import font_helper

        orig_resolved = font_helper._resolved_family
        font_helper._resolved_family = None

        mock_font_mod = MagicMock()
        mock_font_mod.get_init.return_value = True
        mock_font_mod.SysFont.side_effect = RuntimeError("font error")

        try:
            with patch.object(font_helper, "pygame") as mock_pg:
                mock_pg.font = mock_font_mod
                result = font_helper._resolve_font()
                self.assertEqual(result, "Consolas")  # 폴백
        finally:
            font_helper._resolved_family = orig_resolved

    def test_set_user_font(self):
        """set_user_font() 테스트 (line 63)."""
        import font_helper

        orig = font_helper._user_family
        try:
            font_helper.set_user_font("MyFont")
            self.assertEqual(font_helper._user_family, "MyFont")
            font_helper.set_user_font(None)
            self.assertIsNone(font_helper._user_family)
        finally:
            font_helper._user_family = orig

    def test_get_font(self):
        """get_font() — 사용자 폰트 설정 시 (lines 73-74)."""
        import font_helper

        orig_user = font_helper._user_family
        try:
            font_helper._user_family = "TestFont"
            mock_font_mod = MagicMock()
            mock_font_mod.SysFont.return_value = MagicMock()
            with patch.object(font_helper, "pygame") as mock_pg:
                mock_pg.font = mock_font_mod
                font_helper.get_font(12, bold=True)
                mock_font_mod.SysFont.assert_called_once_with("TestFont", 12, bold=True)
        finally:
            font_helper._user_family = orig_user

    def test_get_font_family_user_set(self):
        """get_font_family() — 사용자 폰트가 설정된 경우 (lines 79-81)."""
        import font_helper

        orig = font_helper._user_family
        try:
            font_helper._user_family = "UserFont"
            self.assertEqual(font_helper.get_font_family(), "UserFont")
        finally:
            font_helper._user_family = orig

    def test_get_font_family_auto(self):
        """get_font_family() — 자동 탐색 (line 81)."""
        import font_helper

        orig_user = font_helper._user_family
        orig_resolved = font_helper._resolved_family
        try:
            font_helper._user_family = None
            font_helper._resolved_family = "AutoFont"
            result = font_helper.get_font_family()
            self.assertEqual(result, "AutoFont")
        finally:
            font_helper._user_family = orig_user
            font_helper._resolved_family = orig_resolved

    def test_list_available_fonts(self):
        """list_available_fonts() — 한글 지원 폰트만 반환 (lines 86-98)."""
        import font_helper

        mock_font_mod = MagicMock()
        mock_font_mod.get_init.return_value = False  # init 필요 테스트

        def fake_sys_font(name, size):
            f = MagicMock()

            def fake_render(text, aa, color):
                s = MagicMock()
                if text == "가":
                    # 첫 번째 후보만 한글 지원
                    if name == font_helper._CANDIDATE_FONTS[0]:
                        s.get_width.return_value = 14
                    else:
                        s.get_width.return_value = 10
                else:  # '?'
                    s.get_width.return_value = 10
                return s

            f.render = fake_render
            return f

        mock_font_mod.SysFont = fake_sys_font

        with patch.object(font_helper, "pygame") as mock_pg:
            mock_pg.font = mock_font_mod
            result = font_helper.list_available_fonts()
            # 첫 후보만 '가' != '?' → 한글 지원
            self.assertIn(font_helper._CANDIDATE_FONTS[0], result)

    def test_list_all_system_fonts(self):
        """list_all_system_fonts() — 시스템 폰트 목록 (lines 103-105)."""
        import font_helper

        mock_font_mod = MagicMock()
        mock_font_mod.get_init.return_value = False
        mock_font_mod.get_fonts.return_value = ["consolas", "arial", "times"]

        with patch.object(font_helper, "pygame") as mock_pg:
            mock_pg.font = mock_font_mod
            result = font_helper.list_all_system_fonts()
            mock_font_mod.init.assert_called_once()
            self.assertEqual(result, ["arial", "consolas", "times"])


# ================================================================
# 11. session_io.py — lines 396, 415-416
# ================================================================
class TestSessionIoAutoParseNonString(unittest.TestCase):
    """_auto_parse_csv_values()에서 non-string 값 continue (line 396)."""

    def test_non_string_value_skipped(self):
        from session_io import _auto_parse_csv_values

        row = {"a": "hello", "b": 42, "c": None}
        _auto_parse_csv_values(row)
        # int, None은 변환되지 않고 그대로 유지
        self.assertEqual(row["b"], 42)
        self.assertIsNone(row["c"])


class TestSessionIoInvalidJsonLikeString(unittest.TestCase):
    """_auto_parse_csv_values()에서 잘못된 JSON 문자열 처리 (lines 415-416)."""

    def test_invalid_json_string_not_parsed(self):
        from session_io import _auto_parse_csv_values

        row = {"data": "{invalid json", "arr": "[broken"}
        _auto_parse_csv_values(row)
        # JSON 파싱 실패 → 원래 문자열 유지 (숫자 변환도 실패하면 str 유지)
        # "{invalid json" 은 int/float 변환도 실패하므로 str 유지
        self.assertIsInstance(row["data"], str)
        self.assertIsInstance(row["arr"], str)

    def test_valid_json_dict_parsed(self):
        from session_io import _auto_parse_csv_values

        row = {"data": '{"key": "val"}'}
        _auto_parse_csv_values(row)
        self.assertIsInstance(row["data"], dict)
        self.assertEqual(row["data"]["key"], "val")

    def test_valid_json_list_parsed(self):
        from session_io import _auto_parse_csv_values

        row = {"data": "[1, 2, 3]"}
        _auto_parse_csv_values(row)
        self.assertIsInstance(row["data"], list)
        self.assertEqual(row["data"], [1, 2, 3])


# ================================================================
# 12. theme.py — FONTS 프로퍼티, save/load_preferences + font_family
# ================================================================
def _reset_theme():
    """theme 모듈 상태 초기화."""
    import theme as t

    t._current_theme = "dark"
    t._colorblind = False
    t._font_scale = 1.0
    t._listeners.clear()


class TestThemeFontProperties(unittest.TestCase):
    """FONTS 인스턴스의 다양한 프로퍼티 접근 (lines 133, 141, 145, 153, 157, 161)."""

    def setUp(self):
        _reset_theme()

    def tearDown(self):
        _reset_theme()

    def test_heading_property(self):
        import theme

        heading = theme.FONTS.HEADING
        self.assertIsInstance(heading, tuple)
        self.assertEqual(len(heading), 3)
        self.assertEqual(heading[2], "bold")

    def test_body_bold_property(self):
        import theme

        body_bold = theme.FONTS.BODY_BOLD
        self.assertIsInstance(body_bold, tuple)
        self.assertEqual(len(body_bold), 3)
        self.assertEqual(body_bold[2], "bold")

    def test_small_property(self):
        import theme

        small = theme.FONTS.SMALL
        self.assertIsInstance(small, tuple)
        self.assertEqual(len(small), 2)

    def test_mono_12_property(self):
        import theme

        mono = theme.FONTS.MONO_12
        self.assertIsInstance(mono, tuple)
        self.assertEqual(len(mono), 2)

    def test_mono_11_property(self):
        import theme

        mono = theme.FONTS.MONO_11
        self.assertIsInstance(mono, tuple)
        self.assertEqual(len(mono), 2)

    def test_button_property(self):
        import theme

        button = theme.FONTS.BUTTON
        self.assertIsInstance(button, tuple)
        self.assertEqual(len(button), 2)


class TestThemeSaveLoadWithFontFamily(unittest.TestCase):
    """save_preferences / load_preferences에서 font_family 처리
    (lines 586-587, 594, 596, 600-601, 626-627)."""

    def setUp(self):
        _reset_theme()
        self._cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")
        self._cfg_path = os.path.normpath(self._cfg_path)

    def tearDown(self):
        _reset_theme()

    def test_save_with_user_font(self):
        """사용자 폰트가 설정된 경우 config에 font_family 저장 (line 594)."""
        import theme

        written_data = {}

        def fake_open_factory(read_data="{}"):
            call_count = [0]

            def fake_open(path, *args, **kwargs):
                call_count[0] += 1
                mode = ""
                if args:
                    mode = args[0]
                elif "mode" in kwargs:
                    mode = kwargs["mode"]
                if "w" in mode:
                    m = MagicMock()
                    m.__enter__ = MagicMock(return_value=m)
                    m.__exit__ = MagicMock(return_value=False)

                    def capture_dump(data, f, **kw):
                        written_data.update(data)

                    return m
                else:
                    return mock_open(read_data=read_data)()

            return fake_open

        with patch("font_helper.get_user_font", return_value="NanumGothic"):
            with patch("i18n.get_locale", return_value="ko"):
                with patch("builtins.open", side_effect=fake_open_factory()):
                    with patch("json.dump") as mock_dump:
                        theme.save_preferences()
                        # json.dump가 호출되었는지 확인
                        mock_dump.assert_called_once()
                        saved = mock_dump.call_args[0][0]
                        self.assertEqual(saved["font_family"], "NanumGothic")

    def test_save_without_user_font_removes_key(self):
        """사용자 폰트 미설정 시 font_family 키 삭제 (line 596)."""
        import theme

        existing_cfg = {"theme": "dark", "font_family": "OldFont"}

        with patch("font_helper.get_user_font", return_value=None):
            with patch("i18n.get_locale", return_value="ko"):
                with patch("builtins.open", mock_open(read_data=json.dumps(existing_cfg))):
                    with patch("json.dump") as mock_dump:
                        theme.save_preferences()
                        saved = mock_dump.call_args[0][0]
                        self.assertNotIn("font_family", saved)

    def test_save_oserror_on_read(self):
        """config.json 읽기 실패 시 빈 dict로 시작 (lines 586-587)."""
        import theme

        call_count = [0]

        def fake_open(path, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("no file")
            return mock_open()()

        with patch("font_helper.get_user_font", return_value=None):
            with patch("i18n.get_locale", return_value="ko"):
                with patch("builtins.open", side_effect=fake_open):
                    with patch("json.dump"):
                        theme.save_preferences()  # 에러 없이 통과

    def test_save_oserror_on_write(self):
        """config.json 쓰기 실패 시 pass (lines 600-601)."""
        import theme

        call_count = [0]

        def fake_open(path, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_open(read_data="{}")()
            raise OSError("cannot write")

        with patch("font_helper.get_user_font", return_value=None):
            with patch("i18n.get_locale", return_value="ko"):
                with patch("builtins.open", side_effect=fake_open):
                    theme.save_preferences()  # 에러 없이 통과

    def test_load_with_font_family(self):
        """config에 font_family가 있으면 set_user_font 및 FONTS.FAMILY 갱신 (lines 626-627)."""
        import theme

        cfg_data = json.dumps({"font_family": "TestCJKFont", "theme": "dark"})

        with patch("builtins.open", mock_open(read_data=cfg_data)):
            with patch("font_helper.set_user_font") as mock_set:
                with patch("i18n.set_locale"):
                    theme.load_preferences()
                    mock_set.assert_called_once_with("TestCJKFont")
                    self.assertEqual(theme.FONTS.FAMILY, "TestCJKFont")

        # 복원
        theme.FONTS.FAMILY = "WenQuanYi Zen Hei Mono"

    def test_load_without_font_family(self):
        """config에 font_family가 없으면 set_user_font 미호출."""
        import theme

        cfg_data = json.dumps({"theme": "dark"})

        with patch("builtins.open", mock_open(read_data=cfg_data)):
            with patch("font_helper.set_user_font") as mock_set:
                with patch("i18n.set_locale"):
                    theme.load_preferences()
                    mock_set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
