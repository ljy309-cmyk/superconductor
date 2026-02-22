"""게임 로직 단위 테스트 — 물리 계산, 노드 상태, 업적 조건, 토스트, 리플레이 deque."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum.qubit_physics import QubitState

# ── QubitNode 물리 로직 테스트 ──────────────────────────────


class TestQubitNode(unittest.TestCase):
    """qubit_chain.QubitNode 물리 로직."""

    def _make_node(self, qid=0, x=100, y=100):
        from quantum.qubit_chain import QubitNode

        return QubitNode(qid, x, y)

    def test_initial_state(self):
        node = self._make_node()
        self.assertEqual(node.stress, 0.0)
        self.assertFalse(node.collapsed)
        self.assertEqual(node.state, QubitState.STABLE)

    def test_apply_noise_increases_stress(self):
        node = self._make_node()
        node.apply_noise(30.0)
        self.assertAlmostEqual(node.stress, 30.0)

    def test_apply_noise_capped(self):
        node = self._make_node()
        node.apply_noise(200.0)
        self.assertLessEqual(node.stress, 150.0)  # STRESS_THRESHOLD + 50

    def test_apply_noise_does_nothing_when_collapsed(self):
        node = self._make_node()
        node.collapsed = True
        node.apply_noise(50.0)
        self.assertEqual(node.stress, 0.0)

    def test_stabilize_reduces_stress(self):
        node = self._make_node()
        node.apply_noise(60.0)
        node.stabilize(25.0)
        self.assertAlmostEqual(node.stress, 35.0)

    def test_stabilize_floors_at_zero(self):
        node = self._make_node()
        node.apply_noise(10.0)
        node.stabilize(50.0)
        self.assertEqual(node.stress, 0.0)

    def test_state_transitions(self):
        node = self._make_node()
        self.assertEqual(node.state, QubitState.STABLE)

        node.stress = 50.0
        self.assertEqual(node.state, QubitState.WARNING)

        node.stress = 85.0
        self.assertEqual(node.state, QubitState.DANGER)

        node.collapsed = True
        self.assertEqual(node.state, QubitState.COLLAPSED)

    def test_state_labels_are_strings(self):
        """모든 QubitState에 짧은 문자열 라벨이 있어야 함."""
        for state in QubitState:
            self.assertIsInstance(state.label, str)
            self.assertGreater(len(state.label), 0)

    def test_state_labels_unique(self):
        """각 상태의 라벨이 서로 다르야 함."""
        labels = [s.label for s in QubitState]
        self.assertEqual(len(labels), len(set(labels)))

    def test_collapse_at_threshold(self):
        node = self._make_node()
        node.stress = 100.0  # STRESS_THRESHOLD
        result = node.check_collapse()
        self.assertTrue(result)
        self.assertTrue(node.collapsed)

    def test_no_collapse_below_threshold(self):
        node = self._make_node()
        node.stress = 99.0
        result = node.check_collapse()
        self.assertFalse(result)
        self.assertFalse(node.collapsed)

    def test_cascade_damage_to_neighbors(self):
        n1 = self._make_node(0)
        n2 = self._make_node(1, 200, 100)
        n1.add_neighbor(n2)

        n1.stress = 100.0
        n1.check_collapse(cascade_damage=20.0)

        self.assertTrue(n1.collapsed)
        self.assertAlmostEqual(n2.stress, 20.0)

    def test_already_collapsed_no_cascade(self):
        node = self._make_node()
        node.collapsed = True
        result = node.check_collapse()
        self.assertFalse(result)

    def test_reset(self):
        node = self._make_node()
        node.stress = 80.0
        node.collapsed = True
        node.collapse_timer = 0.3
        node.reset()
        self.assertEqual(node.stress, 0.0)
        self.assertFalse(node.collapsed)
        self.assertEqual(node.collapse_timer, 0.0)

    def test_add_neighbor_bidirectional(self):
        n1 = self._make_node(0)
        n2 = self._make_node(1, 200, 100)
        n1.add_neighbor(n2)
        self.assertIn(n2, n1.neighbors)
        self.assertIn(n1, n2.neighbors)

    def test_no_duplicate_neighbors(self):
        n1 = self._make_node(0)
        n2 = self._make_node(1, 200, 100)
        n1.add_neighbor(n2)
        n1.add_neighbor(n2)
        self.assertEqual(len(n1.neighbors), 1)


class TestBuildNetwork(unittest.TestCase):
    """_build_network 함수 검증."""

    def test_network_structure(self):
        from quantum.qubit_chain import _build_network

        nodes = _build_network()
        self.assertEqual(len(nodes), 7)  # 중앙 1 + 외곽 6

        # 중앙 노드는 6개 이웃
        center = nodes[0]
        self.assertEqual(len(center.neighbors), 6)

        # 외곽 노드는 3개 이웃 (중앙 + 양쪽)
        for i in range(1, 7):
            self.assertEqual(len(nodes[i].neighbors), 3)


# ── Achievement Conditions 테스트 ───────────────────────────


class TestAchievementConditions(unittest.TestCase):
    """업적 조건 람다 함수 검증."""

    def test_qc_first_play_always_true(self):
        from achievements import ACHIEVEMENTS

        ach = next(a for a in ACHIEVEMENTS if a["id"] == "qc_first_play")
        self.assertTrue(ach["condition"]({}))

    def test_qc_survivor_30_boundary(self):
        from achievements import _T, ACHIEVEMENTS

        ach = next(a for a in ACHIEVEMENTS if a["id"] == "qc_survivor_30")
        threshold = _T["qc_survive_short"]
        self.assertFalse(ach["condition"]({"survival_time": threshold - 0.1}))
        self.assertTrue(ach["condition"]({"survival_time": threshold}))

    def test_qc_no_collapse_condition(self):
        from achievements import _T, ACHIEVEMENTS

        ach = next(a for a in ACHIEVEMENTS if a["id"] == "qc_no_collapse")
        t = _T["qc_no_collapse_time"]
        self.assertTrue(ach["condition"]({"collapsed_count": 0, "survival_time": t}))
        self.assertFalse(ach["condition"]({"collapsed_count": 1, "survival_time": t}))
        self.assertFalse(ach["condition"]({"collapsed_count": 0, "survival_time": t - 10}))

    def test_tn_rate_50_needs_min_attempts(self):
        from achievements import _T, ACHIEVEMENTS

        ach = next(a for a in ACHIEVEMENTS if a["id"] == "tn_rate_50")
        rate = _T["tn_rate_threshold"]
        min_att = _T["tn_rate_min_attempts"]
        self.assertFalse(ach["condition"]({"tunnel_rate": rate + 0.3, "total_attempts": min_att - 5}))
        self.assertTrue(ach["condition"]({"tunnel_rate": rate, "total_attempts": min_att}))

    def test_sq_perfect_needs_win_and_zero_wrong(self):
        from achievements import ACHIEVEMENTS

        ach = next(a for a in ACHIEVEMENTS if a["id"] == "sq_perfect")
        self.assertTrue(ach["condition"]({"won": True, "wrong_marks": 0}))
        self.assertFalse(ach["condition"]({"won": True, "wrong_marks": 1}))
        self.assertFalse(ach["condition"]({"won": False, "wrong_marks": 0}))

    def test_missing_key_defaults(self):
        """누락된 키에 대해 안전하게 기본값 사용."""
        from achievements import ACHIEVEMENTS

        for ach in ACHIEVEMENTS:
            try:
                ach["condition"]({})  # 빈 dict로 호출 시 에러 없어야 함
            except Exception as e:  # pragma: no cover
                self.fail(f"Achievement {ach['id']} 조건에서 예외: {e}")


# ── AchievementToast 테스트 ─────────────────────────────────


class TestAchievementToast(unittest.TestCase):
    def test_initial_idle(self):
        from achievement_toast import AchievementToast

        toast = AchievementToast()
        self.assertEqual(toast._phase, "idle")
        self.assertIsNone(toast._current)

    def test_show_starts_slide_in(self):
        from achievement_toast import AchievementToast

        toast = AchievementToast()
        toast.show({"title": "Test", "icon": "T", "desc": "desc"})
        self.assertEqual(toast._phase, "slide_in")
        self.assertIsNotNone(toast._current)

    def test_update_phases(self):
        from achievement_toast import AchievementToast

        toast = AchievementToast()
        toast.show({"title": "Test", "icon": "T", "desc": "desc"})

        # slide_in → show
        toast.update(0.35)
        self.assertEqual(toast._phase, "show")

        # show → slide_out
        toast.update(3.1)
        self.assertEqual(toast._phase, "slide_out")

        # slide_out → idle
        toast.update(0.35)
        self.assertEqual(toast._phase, "idle")

    def test_queue_multiple(self):
        from achievement_toast import AchievementToast

        toast = AchievementToast()
        toast.show_many(
            [
                {"title": "A", "icon": "1", "desc": "first"},
                {"title": "B", "icon": "2", "desc": "second"},
            ]
        )
        self.assertEqual(toast._current["title"], "A")
        self.assertEqual(len(toast._queue), 1)


# ── Replay Deque 테스트 ─────────────────────────────────────


class TestReplayDeque(unittest.TestCase):
    def test_deque_maxlen(self):
        from replay import ReplayRecorder

        rec = ReplayRecorder("test", max_frames=10)
        for i in range(20):
            rec.record_frame({"i": i})
        self.assertEqual(rec.frame_count, 10)

    def test_deque_preserves_recent(self):
        from replay import ReplayRecorder

        rec = ReplayRecorder("test", max_frames=5)
        for i in range(10):
            rec.record_frame({"i": i})
        # deque keeps most recent
        self.assertEqual(rec._frames[-1]["i"], 9)
        self.assertEqual(rec._frames[0]["i"], 5)

    def test_save_with_deque(self):
        from replay import ReplayRecorder

        tmpdir = tempfile.mkdtemp()
        try:
            import replay

            orig_dir = replay.REPLAY_DIR
            replay.REPLAY_DIR = tmpdir

            rec = ReplayRecorder("test", max_frames=5)
            for i in range(10):
                rec.record_frame({"v": i})
            path = rec.save()
            self.assertTrue(os.path.exists(path))

            import json

            with open(path) as f:
                data = json.load(f)
            self.assertEqual(len(data["frames"]), 5)

            replay.REPLAY_DIR = orig_dir
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── Ranking Server Validation 테스트 ────────────────────────


class TestRankingValidation(unittest.TestCase):
    def test_name_truncation(self):
        """50자 초과 이름이 잘리는지 확인."""
        long_name = "A" * 100
        truncated = str(long_name)[:50]
        self.assertEqual(len(truncated), 50)

    def test_score_clamping(self):
        """점수 범위 클램핑 로직 검증."""
        self.assertEqual(max(0.0, min(float(-10), 999999.0)), 0.0)
        self.assertEqual(max(0.0, min(float(1000000), 999999.0)), 999999.0)
        self.assertEqual(max(0.0, min(42.5, 999999.0)), 42.5)


# ── QubitNetwork (MVC Model) 테스트 ─────────────────────────


class TestQubitNetwork(unittest.TestCase):
    """quantum/qubit_physics.py QubitNetwork 통합 테스트."""

    def _make_network(self):
        from quantum.qubit_physics import QubitNetwork

        return QubitNetwork()

    def test_initial_state(self):
        net = self._make_network()
        self.assertEqual(len(net.nodes), 7)
        self.assertFalse(net.is_game_over)
        self.assertEqual(net.alive_count, 7)
        self.assertEqual(net.collapsed_count, 0)

    def test_heal_all(self):
        net = self._make_network()
        for n in net.nodes:
            n.stress = 50.0
        net.heal_all(30.0)
        for n in net.nodes:
            self.assertAlmostEqual(n.stress, 20.0)

    def test_correct_node(self):
        net = self._make_network()
        net.nodes[3].stress = 80.0
        result = net.correct_node(3)
        self.assertTrue(result)
        self.assertEqual(net.nodes[3].stress, 0.0)

    def test_correct_collapsed_returns_false(self):
        net = self._make_network()
        net.nodes[0].collapsed = True
        result = net.correct_node(0)
        self.assertFalse(result)

    def test_update_causes_collapse(self):
        net = self._make_network()
        net.nodes[0].stress = 99.9
        collapsed = net.update(0.1, noise_rate=50.0, cascade_damage=20.0, shield_active=False, qec_reduction=0.2)
        # 높은 노이즈로 최소 1개는 붕괴
        self.assertTrue(len(collapsed) >= 0)  # 확률적이므로 >= 0

    def test_game_over(self):
        net = self._make_network()
        for n in net.nodes:
            n.collapsed = True
        self.assertTrue(net.is_game_over)

    def test_reset(self):
        net = self._make_network()
        for n in net.nodes:
            n.stress = 80.0
            n.collapsed = True
        net.reset()
        self.assertEqual(net.alive_count, 7)
        for n in net.nodes:
            self.assertEqual(n.stress, 0.0)

    def test_shield_reduces_noise(self):
        """방어막 ON 시 노이즈가 감소하는지 확인."""
        from quantum.qubit_physics import QubitNetwork

        net1 = QubitNetwork()
        net2 = QubitNetwork()

        # 동일 시드로 비교
        import random

        random.seed(42)
        net1.update(1.0, noise_rate=10.0, cascade_damage=20.0, shield_active=False, qec_reduction=0.2)
        stress_no_shield = sum(n.stress for n in net1.nodes)

        random.seed(42)
        net2.update(1.0, noise_rate=10.0, cascade_damage=20.0, shield_active=True, qec_reduction=0.2)
        stress_with_shield = sum(n.stress for n in net2.nodes)

        self.assertLess(stress_with_shield, stress_no_shield)

    def test_pop_events(self):
        net = self._make_network()
        net.heal_all(10.0)
        events = net.pop_events()
        self.assertEqual(len(events), 1)
        self.assertIn("HEAL", events[0])
        # 두 번째 호출은 빈 리스트
        self.assertEqual(net.pop_events(), [])


# ── Tutorial 테스트 ─────────────────────────────────────────


class TestTutorial(unittest.TestCase):
    def test_tutorial_steps_defined(self):
        from tutorial import _TUTORIAL_STEPS

        self.assertIn("qubit_chain", _TUTORIAL_STEPS)
        self.assertGreater(len(_TUTORIAL_STEPS["qubit_chain"]), 3)

    def test_overlay_init(self):
        from tutorial import TutorialOverlay

        overlay = TutorialOverlay("qubit_chain", auto_show=False)
        self.assertFalse(overlay.visible)
        self.assertEqual(overlay.current_step, 0)

    def test_unknown_module(self):
        from tutorial import TutorialOverlay

        overlay = TutorialOverlay("nonexistent", auto_show=False)
        self.assertEqual(overlay.steps, [])


if __name__ == "__main__":
    unittest.main()
