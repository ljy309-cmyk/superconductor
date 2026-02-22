"""Tkinter UI 모듈 mock 테스트 — main, launcher, settings_panel, stats_dashboard 등."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Tkinter/matplotlib mock 설정 ──────────────────────────
# Toplevel/Tk를 실제 클래스로 만들어야 상속이 정상 동작
_FakeTk = type("Tk", (), {"__init__": lambda self, *a, **kw: None})
_FakeToplevel = type(
    "Toplevel",
    (),
    {
        "__init__": lambda self, *a, **kw: None,
        "title": lambda self, *a: None,
        "configure": lambda self, **kw: None,
        "geometry": lambda self, *a: None,
        "resizable": lambda self, *a: None,
        "protocol": lambda self, *a: None,
        "pack": lambda self, **kw: None,
        "winfo_exists": lambda self: True,
        "winfo_children": lambda self: [],
        "winfo_width": lambda self: 800,
        "winfo_height": lambda self: 600,
        "winfo_screenwidth": lambda self: 1920,
        "winfo_screenheight": lambda self: 1080,
        "update_idletasks": lambda self: None,
        "after": lambda self, *a, **kw: None,
        "after_cancel": lambda self, *a: None,
        "bind": lambda self, *a, **kw: None,
        "focus_set": lambda self: None,
        "grab_set": lambda self: None,
        "transient": lambda self, *a: None,
        "destroy": lambda self: None,
    },
)

_tk_mock = MagicMock()
_tk_mock.Tk = _FakeTk
_tk_mock.Toplevel = _FakeToplevel
_tk_mock.Frame = MagicMock
_tk_mock.Label = MagicMock
_tk_mock.Button = MagicMock
_tk_mock.Text = MagicMock
_tk_mock.Listbox = MagicMock
_tk_mock.Canvas = MagicMock
_tk_mock.Scale = MagicMock
_tk_mock.Scrollbar = MagicMock
_tk_mock.BooleanVar = MagicMock
_tk_mock.StringVar = MagicMock
_tk_mock.IntVar = MagicMock
_tk_mock.Checkbutton = MagicMock
_tk_mock.Radiobutton = MagicMock
_tk_mock.OptionMenu = MagicMock
_tk_mock.LabelFrame = MagicMock
_tk_mock.PhotoImage = MagicMock
_mpl_mock = MagicMock()

_mock_modules = {
    "tkinter": _tk_mock,
    "tkinter.ttk": MagicMock(),
    "tkinter.messagebox": MagicMock(),
    "tkinter.filedialog": MagicMock(),
    "tkinter.font": MagicMock(),
    "tkinter.simpledialog": MagicMock(),
}
for _m in (
    "matplotlib",
    "matplotlib.backends",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends._backend_tk",
    "matplotlib.figure",
):
    if _m not in sys.modules:
        _mock_modules[_m] = _mpl_mock

# pygame mock
_pg_mock = MagicMock()
_pg_mock.KEYDOWN = 768
_pg_mock.SRCALPHA = 0x00010000
for _m in ("pygame", "pygame.time", "pygame.mixer"):
    if _m not in sys.modules:
        _mock_modules[_m] = _pg_mock

# 모듈레벨에서 한 번만 mock 적용 후 import (numpy 충돌 방지)
_saved = {k: sys.modules.get(k) for k in _mock_modules}
for k, v in _mock_modules.items():
    sys.modules[k] = v

try:
    import main  # noqa: F401
    import settings_panel  # noqa: F401
    from data_ai.launcher import DataAILauncher, open_data_ai_launcher  # noqa: F401
    from data_ai.qrng_logger import _load_qrng_colors, _shared_key_queue, push_key_bits  # noqa: F401
    from data_ai.ranking import _load_tk_colors  # noqa: F401
    from data_ai.tc_predictor import MODEL_CONFIGS, _load_tc_colors  # noqa: F401
    from physics.launcher import PhysicsLauncher, open_physics_launcher  # noqa: F401
    from profile_manager import open_profile_manager  # noqa: F401
    from quantum.launcher import QuantumLauncher, open_quantum_launcher  # noqa: F401
    from replay_viewer import ReplayViewer, open_replay_viewer  # noqa: F401
    from scada.dashboard import MAX_HISTORY, Dashboard, open_dashboard  # noqa: F401
    from security.launcher import SecurityLauncher, open_security_launcher  # noqa: F401
    from stats_dashboard import open_stats_dashboard  # noqa: F401
    from ui.base_launcher import BaseLauncher  # noqa: F401
except Exception:  # pragma: no cover
    pass  # 개별 테스트에서 skip 처리
finally:
    # mock 원복 (기존 모듈 복원)
    for k in _mock_modules:
        if _saved[k] is not None:
            sys.modules[k] = _saved[k]
        else:
            sys.modules.pop(k, None)


# ═══════════════════════════════════════════════════════════
# 1. settings_panel.py 테스트
# ═══════════════════════════════════════════════════════════


class TestSettingsPanelConfig(unittest.TestCase):
    """settings_panel의 _read_config / _write_config 테스트."""

    def test_read_config(self):
        result = settings_panel._read_config()
        self.assertIsInstance(result, dict)

    def test_write_config(self):
        tmpdir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmpdir, "config_test.json")
        orig = settings_panel._CFG_PATH
        settings_panel._CFG_PATH = tmp_path
        try:
            result = settings_panel._write_config({"test": True})
            self.assertTrue(result)
            with open(tmp_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertTrue(data["test"])
        finally:
            settings_panel._CFG_PATH = orig

    def test_write_config_failure(self):
        orig = settings_panel._CFG_PATH
        settings_panel._CFG_PATH = "/nonexistent/dir/config.json"
        try:
            result = settings_panel._write_config({"test": True})
            self.assertFalse(result)
        finally:
            settings_panel._CFG_PATH = orig


# ═══════════════════════════════════════════════════════════
# 2. Launcher 모듈 테스트
# ═══════════════════════════════════════════════════════════


class TestLaunchers(unittest.TestCase):
    """모든 launcher 모듈의 클래스 구조 검증."""

    def test_quantum_launcher_attributes(self):
        self.assertEqual(QuantumLauncher.MODULE, "quantum")
        self.assertIsInstance(QuantumLauncher.BUTTONS, list)
        self.assertGreater(len(QuantumLauncher.BUTTONS), 0)

    def test_physics_launcher_attributes(self):
        self.assertEqual(PhysicsLauncher.MODULE, "physics")
        self.assertGreater(len(PhysicsLauncher.BUTTONS), 0)

    def test_security_launcher_attributes(self):
        self.assertEqual(SecurityLauncher.MODULE, "security")
        self.assertGreater(len(SecurityLauncher.BUTTONS), 0)

    def test_data_ai_launcher_attributes(self):
        self.assertEqual(DataAILauncher.MODULE, "data_ai")
        self.assertGreater(len(DataAILauncher.BUTTONS), 0)

    def test_open_functions_callable(self):
        self.assertTrue(callable(open_quantum_launcher))
        self.assertTrue(callable(open_physics_launcher))
        self.assertTrue(callable(open_security_launcher))
        self.assertTrue(callable(open_data_ai_launcher))


# ═══════════════════════════════════════════════════════════
# 3. ui/base_launcher.py 테스트
# ═══════════════════════════════════════════════════════════


class TestBaseLauncherClass(unittest.TestCase):
    """BaseLauncher 테스트."""

    def test_has_module_and_buttons(self):
        self.assertTrue(hasattr(BaseLauncher, "MODULE"))
        self.assertTrue(hasattr(BaseLauncher, "BUTTONS"))

    def test_launcher_has_button_width(self):
        self.assertTrue(hasattr(QuantumLauncher, "BUTTON_WIDTH"))
        self.assertEqual(QuantumLauncher.BUTTON_WIDTH, 42)


# ═══════════════════════════════════════════════════════════
# 4. main.py 테스트
# ═══════════════════════════════════════════════════════════


class TestMainApp(unittest.TestCase):
    """main.py App 클래스 테스트."""

    def test_app_class_exists(self):
        self.assertTrue(hasattr(main, "App"))

    def test_app_is_class(self):
        self.assertTrue(isinstance(main.App, type) or callable(main.App))


# ═══════════════════════════════════════════════════════════
# 5. replay_viewer.py 테스트
# ═══════════════════════════════════════════════════════════


class TestReplayViewerLogic(unittest.TestCase):
    """ReplayViewer 로직 테스트."""

    def test_show_frame_empty(self):
        viewer = MagicMock(spec=ReplayViewer)
        viewer._frames = []
        viewer._frame_info = MagicMock()
        viewer._frame_text = MagicMock()
        viewer._progress_label = MagicMock()
        ReplayViewer._show_frame(viewer, 0)

    def test_show_frame_with_data(self):
        viewer = MagicMock(spec=ReplayViewer)
        viewer._frames = [{"x": 1}, {"x": 2}, {"x": 3}]
        viewer._frame_info = MagicMock()
        viewer._frame_text = MagicMock()
        viewer._progress_label = MagicMock()
        ReplayViewer._show_frame(viewer, 1)

    def test_cycle_speed_up(self):
        viewer = MagicMock(spec=ReplayViewer)
        viewer._play_speed = 1
        viewer._speed_levels = [0.25, 0.5, 1, 2, 4]
        viewer._speed_var = MagicMock()
        ReplayViewer._cycle_speed(viewer, 1)
        viewer._set_speed.assert_called_with(2)

    def test_cycle_speed_down(self):
        viewer = MagicMock(spec=ReplayViewer)
        viewer._play_speed = 1
        viewer._speed_levels = [0.25, 0.5, 1, 2, 4]
        viewer._speed_var = MagicMock()
        ReplayViewer._cycle_speed(viewer, -1)
        viewer._set_speed.assert_called_with(0.5)

    def test_step_forward(self):
        viewer = MagicMock(spec=ReplayViewer)
        viewer._frames = [{"x": 1}, {"x": 2}, {"x": 3}]
        viewer._frame_var = MagicMock()
        viewer._frame_var.get.return_value = 0
        viewer._slider = MagicMock()
        viewer._frame_info = MagicMock()
        viewer._frame_text = MagicMock()
        viewer._progress_label = MagicMock()
        ReplayViewer._step(viewer, 1)
        viewer._frame_var.set.assert_called_with(1)

    def test_seek_start(self):
        viewer = MagicMock(spec=ReplayViewer)
        viewer._frames = [{"x": 1}, {"x": 2}]
        viewer._frame_var = MagicMock()
        viewer._slider = MagicMock()
        viewer._frame_info = MagicMock()
        viewer._frame_text = MagicMock()
        viewer._progress_label = MagicMock()
        ReplayViewer._seek(viewer, 0)
        viewer._frame_var.set.assert_called_with(0)

    def test_seek_end(self):
        viewer = MagicMock(spec=ReplayViewer)
        viewer._frames = [{"x": 1}, {"x": 2}]
        viewer._frame_var = MagicMock()
        viewer._slider = MagicMock()
        viewer._frame_info = MagicMock()
        viewer._frame_text = MagicMock()
        viewer._progress_label = MagicMock()
        ReplayViewer._seek(viewer, -1)
        viewer._frame_var.set.assert_called_with(1)

    def test_set_speed(self):
        viewer = MagicMock(spec=ReplayViewer)
        ReplayViewer._set_speed(viewer, 4.0)
        self.assertEqual(viewer._play_speed, 4.0)

    def test_on_loop_toggle(self):
        viewer = MagicMock(spec=ReplayViewer)
        viewer._loop_var = MagicMock()
        viewer._loop_var.get.return_value = True
        ReplayViewer._on_loop_toggle(viewer)
        self.assertTrue(viewer._loop)

    def test_open_replay_viewer_callable(self):
        self.assertTrue(callable(open_replay_viewer))


# ═══════════════════════════════════════════════════════════
# 6. data_ai 모듈 테스트
# ═══════════════════════════════════════════════════════════


class TestDataAIModules(unittest.TestCase):
    """data_ai 하위 모듈 테스트."""

    def test_ranking_load_tk_colors(self):
        colors = _load_tk_colors()
        self.assertIn("bg", colors)
        self.assertIn("fg", colors)
        self.assertIn("accent", colors)

    def test_qrng_push_key_bits(self):
        while not _shared_key_queue.empty():
            _shared_key_queue.get_nowait()
        push_key_bits([1, 0, 1])
        self.assertEqual(_shared_key_queue.qsize(), 3)

    def test_qrng_load_colors(self):
        _load_qrng_colors()

    def test_tc_predictor_load_colors(self):
        _load_tc_colors()

    def test_tc_predictor_model_configs(self):
        self.assertIn("RandomForest", MODEL_CONFIGS)
        self.assertIn("GradientBoosting", MODEL_CONFIGS)


# ═══════════════════════════════════════════════════════════
# 7. stats_dashboard / profile_manager / scada 테스트
# ═══════════════════════════════════════════════════════════


class TestOtherTkModules(unittest.TestCase):
    """기타 Tkinter 모듈 테스트."""

    def test_open_stats_dashboard_callable(self):
        self.assertTrue(callable(open_stats_dashboard))

    def test_open_profile_manager_callable(self):
        self.assertTrue(callable(open_profile_manager))

    def test_scada_dashboard_constants(self):
        self.assertEqual(MAX_HISTORY, 120)
        self.assertTrue(callable(open_dashboard))


if __name__ == "__main__":
    unittest.main()
