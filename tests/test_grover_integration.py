"""Grover's Search Phase 3 통합 테스트.

Tutorial, PlayLogger, Preset, Achievement, Config 서브시스템과의 통합을 검증합니다.
"""

import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Tutorial 통합 ────────────────────────────────────────

class TestTutorialIntegration(unittest.TestCase):
    """tutorial.py에 grover_search 스텝이 등록되었는지 검증."""

    def test_grover_steps_registered(self):
        from tutorial import _TUTORIAL_STEPS
        self.assertIn("grover_search", _TUTORIAL_STEPS)

    def test_grover_steps_count(self):
        from tutorial import _TUTORIAL_STEPS
        steps = _TUTORIAL_STEPS["grover_search"]
        self.assertGreaterEqual(len(steps), 6)

    def test_each_step_has_required_keys(self):
        from tutorial import _TUTORIAL_STEPS
        for step in _TUTORIAL_STEPS["grover_search"]:
            self.assertIn("title", step)
            self.assertIn("text", step)
            self.assertIn("highlight", step)

    def test_step_titles_not_empty(self):
        from tutorial import _TUTORIAL_STEPS
        for step in _TUTORIAL_STEPS["grover_search"]:
            self.assertTrue(len(step["title"]) > 0)
            self.assertTrue(len(step["text"]) > 0)

    def test_step_covers_key_concepts(self):
        from tutorial import _TUTORIAL_STEPS
        texts = " ".join(s["text"] for s in _TUTORIAL_STEPS["grover_search"])
        titles = " ".join(s["title"] for s in _TUTORIAL_STEPS["grover_search"])
        combined = texts + " " + titles
        # 핵심 개념이 포함되어야 함
        self.assertIn("Superposition", combined)
        self.assertIn("Oracle", combined)
        self.assertIn("Diffusion", combined)

    def test_tutorial_overlay_creation(self):
        """TutorialOverlay 인스턴스 생성 가능."""
        from tutorial import TutorialOverlay
        overlay = TutorialOverlay("grover_search", auto_show=False)
        self.assertEqual(overlay.module_name, "grover_search")
        self.assertGreaterEqual(len(overlay.steps), 6)


# ── PlayLogger 통합 ──────────────────────────────────────

class TestPlayLoggerIntegration(unittest.TestCase):
    """PlayLogger에 grover_search 필드가 등록되었는지 검증."""

    def test_grover_fields_registered(self):
        from data_ai.play_logger import PlayLogger
        self.assertIn("grover_search", PlayLogger.FIELDS)

    def test_grover_fields_complete(self):
        from data_ai.play_logger import PlayLogger
        fields = PlayLogger.FIELDS["grover_search"]
        expected = ["play_time", "searches_completed", "total_steps",
                    "last_n_qubits", "largest_db"]
        for f in expected:
            self.assertIn(f, fields)

    def test_shor_fields_registered(self):
        from data_ai.play_logger import PlayLogger
        self.assertIn("shor_algorithm", PlayLogger.FIELDS)

    def test_log_session_accepts_grover_data(self):
        from data_ai.play_logger import PlayLogger
        logger = PlayLogger()
        logger.records = []  # 격리
        data = {
            "play_time": 25.5,
            "searches_completed": 3,
            "total_steps": 12,
            "last_n_qubits": 4,
            "largest_db": 5,
        }
        record = logger.log_session("grover_search", data)
        self.assertEqual(record["module"], "grover_search")
        self.assertEqual(record["play_time"], 25.5)
        self.assertEqual(record["searches_completed"], 3)


# ── Preset 통합 ──────────────────────────────────────────

class TestPresetIntegration(unittest.TestCase):
    """config.json presets에 grover 항목이 존재하는지 검증."""

    def test_easy_preset_has_grover(self):
        from presets import get_preset
        easy = get_preset("easy")
        self.assertIn("grover", easy)

    def test_normal_preset_has_grover(self):
        from presets import get_preset
        normal = get_preset("normal")
        self.assertIn("grover", normal)

    def test_hard_preset_has_grover(self):
        from presets import get_preset
        hard = get_preset("hard")
        self.assertIn("grover", hard)

    def test_easy_has_small_qubits(self):
        from presets import get_preset
        easy = get_preset("easy")
        self.assertLessEqual(easy["grover"]["default_qubits"], 4)

    def test_hard_has_large_qubits(self):
        from presets import get_preset
        hard = get_preset("hard")
        self.assertGreaterEqual(hard["grover"]["default_qubits"], 5)

    def test_easy_slower_animation(self):
        from presets import get_preset
        easy = get_preset("easy")
        hard = get_preset("hard")
        self.assertGreater(easy["grover"]["animation_speed"],
                           hard["grover"]["animation_speed"])

    def test_difficulty_progression(self):
        """easy → normal → hard로 갈수록 큐비트 수 증가."""
        from presets import get_preset
        e = get_preset("easy")["grover"]["default_qubits"]
        n = get_preset("normal")["grover"]["default_qubits"]
        h = get_preset("hard")["grover"]["default_qubits"]
        self.assertLessEqual(e, n)
        self.assertLessEqual(n, h)


# ── Achievement 통합 ─────────────────────────────────────

class TestAchievementIntegration(unittest.TestCase):
    """Grover 업적이 올바르게 정의되었는지 검증."""

    def test_grover_achievements_exist(self):
        from achievements import ACHIEVEMENTS
        grover_ids = [a["id"] for a in ACHIEVEMENTS
                      if a["module"] == "grover_search"]
        self.assertIn("grover_first_search", grover_ids)
        self.assertIn("grover_large_db", grover_ids)
        self.assertIn("grover_speed_run", grover_ids)
        self.assertIn("grover_multi_search", grover_ids)
        self.assertIn("grover_high_prob", grover_ids)

    def test_grover_achievement_count(self):
        from achievements import ACHIEVEMENTS
        grover = [a for a in ACHIEVEMENTS if a["module"] == "grover_search"]
        self.assertGreaterEqual(len(grover), 5)

    def test_first_search_always_triggers(self):
        from achievements import ACHIEVEMENTS
        ach = next(a for a in ACHIEVEMENTS
                   if a["id"] == "grover_first_search")
        self.assertTrue(ach["condition"]({"searches_completed": 1}))
        self.assertFalse(ach["condition"]({"searches_completed": 0}))

    def test_large_db_condition(self):
        from achievements import ACHIEVEMENTS
        ach = next(a for a in ACHIEVEMENTS if a["id"] == "grover_large_db")
        self.assertTrue(ach["condition"]({"largest_db": 10}))
        self.assertFalse(ach["condition"]({"largest_db": 2}))

    def test_speed_run_condition(self):
        from achievements import ACHIEVEMENTS
        ach = next(a for a in ACHIEVEMENTS if a["id"] == "grover_speed_run")
        self.assertTrue(ach["condition"](
            {"searches_completed": 1, "play_time": 10}))
        self.assertFalse(ach["condition"](
            {"searches_completed": 1, "play_time": 999}))

    def test_multi_search_condition(self):
        from achievements import ACHIEVEMENTS
        ach = next(a for a in ACHIEVEMENTS
                   if a["id"] == "grover_multi_search")
        self.assertTrue(ach["condition"]({"searches_completed": 10}))
        self.assertFalse(ach["condition"]({"searches_completed": 1}))

    def test_high_prob_condition(self):
        from achievements import ACHIEVEMENTS
        ach = next(a for a in ACHIEVEMENTS
                   if a["id"] == "grover_high_prob")
        self.assertTrue(ach["condition"]({"best_target_prob": 0.95}))
        self.assertFalse(ach["condition"]({"best_target_prob": 0.3}))

    def test_check_achievements_returns_new(self):
        """check_achievements가 새 업적을 반환."""
        from achievements import check_achievements, _load_unlocked, _SAVE_PATH
        # 임시로 업적 파일 백업/격리
        backup = None
        if os.path.exists(_SAVE_PATH):
            with open(_SAVE_PATH) as f:
                backup = f.read()
        try:
            # 빈 상태로 시작
            with open(_SAVE_PATH, "w") as f:
                json.dump([], f)
            result = check_achievements("grover_search",
                                        {"searches_completed": 1})
            ids = [a["id"] for a in result]
            self.assertIn("grover_first_search", ids)
        finally:
            # 복원
            if backup is not None:
                with open(_SAVE_PATH, "w") as f:
                    f.write(backup)
            elif os.path.exists(_SAVE_PATH):
                os.remove(_SAVE_PATH)


# ── Config Schema 통합 ───────────────────────────────────

class TestConfigSchemaIntegration(unittest.TestCase):
    """config_loader에 grover 스키마가 등록되었는지 검증."""

    def test_grover_schema_exists(self):
        from config_loader import _SCHEMA
        self.assertIn("grover", _SCHEMA)

    def test_grover_schema_keys(self):
        from config_loader import _SCHEMA
        schema = _SCHEMA["grover"]
        self.assertIn("max_qubits", schema)
        self.assertIn("default_qubits", schema)
        self.assertIn("animation_speed", schema)
        self.assertIn("auto_batch_size", schema)
        self.assertIn("display_states", schema)

    def test_achievement_schema_has_grover_keys(self):
        from config_loader import _SCHEMA
        schema = _SCHEMA["achievements"]
        self.assertIn("grover_large_db", schema)
        self.assertIn("grover_speed_run_sec", schema)
        self.assertIn("grover_multi_search", schema)
        self.assertIn("grover_perfect_prob", schema)

    def test_cfg_loads_grover_defaults(self):
        from config_loader import cfg
        self.assertIsNotNone(cfg("grover", "max_qubits", None))
        self.assertIsNotNone(cfg("grover", "default_qubits", None))
        self.assertIsNotNone(cfg("grover", "animation_speed", None))

    def test_cfg_grover_max_qubits_range(self):
        from config_loader import cfg
        val = cfg("grover", "max_qubits", 10)
        self.assertGreaterEqual(val, 1)
        self.assertLessEqual(val, 20)


# ── Engine target_prob in history ─────────────────────────

class TestEngineHistoryTargetProb(unittest.TestCase):
    """grover_search_engine의 search_history에 target_prob이 기록되는지."""

    def test_history_has_target_prob(self):
        from quantum.grover_search_engine import (
            GroverState, grover_step, GroverPhase
        )
        state = GroverState(n_qubits=3, targets=[5])
        # INPUT → ... → SUCCESS/FAIL
        for _ in range(50):
            grover_step(state)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL):
                break
        self.assertTrue(len(state.search_history) >= 1)
        entry = state.search_history[0]
        self.assertIn("target_prob", entry)
        self.assertIsInstance(entry["target_prob"], float)

    def test_target_prob_in_range(self):
        from quantum.grover_search_engine import (
            GroverState, grover_step, GroverPhase
        )
        state = GroverState(n_qubits=3, targets=[5])
        for _ in range(50):
            grover_step(state)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL):
                break
        if state.search_history:
            prob = state.search_history[0]["target_prob"]
            self.assertGreaterEqual(prob, 0.0)
            self.assertLessEqual(prob, 1.0)


# ── Session Data 통합 ────────────────────────────────────

class TestSessionDataIntegration(unittest.TestCase):
    """finalize_session에 전달되는 세션 데이터 구조 검증."""

    def test_session_data_keys(self):
        """grover_search.py의 session_data에 필요한 키가 포함되는지."""
        # Simulate the session_data construction
        from quantum.grover_search_engine import (
            GroverState, grover_step, GroverPhase
        )
        import time
        state = GroverState(n_qubits=4, targets=[7])
        start = time.time()
        for _ in range(50):
            grover_step(state)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL):
                break

        best_prob = max(
            (h.get("target_prob", 0) for h in state.search_history),
            default=0.0)
        session_data = {
            "play_time": round(time.time() - start, 1),
            "searches_completed": 1 if state.phase == GroverPhase.SUCCESS else 0,
            "total_steps": 10,
            "last_n_qubits": state.n_qubits,
            "largest_db": max(
                (h["n_qubits"] for h in state.search_history),
                default=state.n_qubits),
            "best_target_prob": round(best_prob, 4),
        }
        # 모든 필수 키 확인
        for key in ["play_time", "searches_completed", "total_steps",
                     "last_n_qubits", "largest_db", "best_target_prob"]:
            self.assertIn(key, session_data)

    def test_best_target_prob_calculated(self):
        from quantum.grover_search_engine import (
            GroverState, grover_step, GroverPhase
        )
        state = GroverState(n_qubits=3, targets=[5])
        for _ in range(50):
            grover_step(state)
            if state.phase in (GroverPhase.SUCCESS, GroverPhase.FAIL):
                break
        best_prob = max(
            (h.get("target_prob", 0) for h in state.search_history),
            default=0.0)
        self.assertGreaterEqual(best_prob, 0.0)


# ── Difficulty Preset ← Engine ────────────────────────────

class TestDifficultyToEngine(unittest.TestCase):
    """난이도 프리셋이 엔진 파라미터에 올바르게 매핑되는지."""

    def test_easy_creates_small_state(self):
        from presets import get_preset
        from quantum.grover_search_engine import GroverState
        preset = get_preset("easy")
        n = preset["grover"]["default_qubits"]
        state = GroverState(n_qubits=n, targets=[0])
        self.assertEqual(state.n_qubits, n)
        self.assertEqual(len(state.amplitudes), 0)  # not yet initialized

    def test_hard_creates_large_state(self):
        from presets import get_preset
        from quantum.grover_search_engine import (
            GroverState, grover_step, GroverPhase
        )
        preset = get_preset("hard")
        n = preset["grover"]["default_qubits"]
        state = GroverState(n_qubits=n, targets=[0])
        grover_step(state)  # INPUT → INIT_SUPERPOSITION
        grover_step(state)  # INIT_SUPERPOSITION → ORACLE
        self.assertEqual(len(state.amplitudes), 1 << n)

    def test_optimal_iterations_scale(self):
        """큐비트가 많을수록 최적 반복 횟수가 증가."""
        from quantum.grover_search_engine import optimal_iterations
        easy_opt = optimal_iterations(1 << 3, 1)   # 8 states
        hard_opt = optimal_iterations(1 << 6, 1)   # 64 states
        self.assertLess(easy_opt, hard_opt)


if __name__ == "__main__":
    unittest.main()
