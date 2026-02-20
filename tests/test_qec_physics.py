"""QEC 물리 엔진 단위 테스트 — 그리드 생성, 노이즈 축적, 캐스케이드 붕괴."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantum.qec_physics import (
    CASCADE_DAMAGE,
    GRID_COLS,
    GRID_ROWS,
    STRESS_THRESHOLD,
    QECQubit,
    build_grid,
)
from quantum.qubit_physics import QubitState


class TestBuildGrid(unittest.TestCase):
    """build_grid() — 그리드 생성 및 연결."""

    def test_grid_size(self):
        """GRID_ROWS × GRID_COLS 개의 큐비트가 생성되어야 한다."""
        nodes = build_grid()
        self.assertEqual(len(nodes), GRID_ROWS * GRID_COLS)

    def test_unique_ids(self):
        """모든 큐비트 ID가 고유해야 한다."""
        nodes = build_grid()
        ids = [n.qid for n in nodes]
        self.assertEqual(len(ids), len(set(ids)))

    def test_corner_neighbors(self):
        """꼭짓점 큐비트는 이웃이 2개여야 한다."""
        nodes = build_grid()
        corners = [
            0,
            GRID_COLS - 1,
            (GRID_ROWS - 1) * GRID_COLS,
            GRID_ROWS * GRID_COLS - 1,
        ]
        for idx in corners:
            self.assertEqual(len(nodes[idx].neighbors), 2, f"corner qid={idx}")

    def test_edge_neighbors(self):
        """변 큐비트(꼭짓점 제외)는 이웃이 3개여야 한다."""
        nodes = build_grid()
        # 첫 행 중간 (열 1 ~ GRID_COLS-2)
        if GRID_COLS > 2:
            edge = nodes[1]
            self.assertEqual(len(edge.neighbors), 3, f"edge qid={edge.qid}")

    def test_interior_neighbors(self):
        """내부 큐비트는 이웃이 4개여야 한다."""
        nodes = build_grid()
        if GRID_ROWS > 2 and GRID_COLS > 2:
            interior = nodes[GRID_COLS + 1]  # (1, 1)
            self.assertEqual(len(interior.neighbors), 4, f"interior qid={interior.qid}")

    def test_symmetric_neighbor(self):
        """A가 B의 이웃이면 B도 A의 이웃이어야 한다."""
        nodes = build_grid()
        for n in nodes:
            for nb in n.neighbors:
                self.assertIn(n, nb.neighbors, f"qid {n.qid} ↔ {nb.qid}")


class TestQECQubit(unittest.TestCase):
    """QECQubit 인스턴스 동작."""

    def test_initial_state_stable(self):
        q = QECQubit(0, 0, 0)
        self.assertEqual(q.stress, 0.0)
        self.assertFalse(q.collapsed)
        self.assertEqual(q.state, QubitState.STABLE)

    def test_apply_noise(self):
        q = QECQubit(0, 0, 0)
        q.apply_noise(30.0)
        self.assertAlmostEqual(q.stress, 30.0)

    def test_apply_noise_capped_at_150(self):
        """스트레스는 150을 초과하지 않아야 한다."""
        q = QECQubit(0, 0, 0)
        q.apply_noise(200.0)
        self.assertEqual(q.stress, 150.0)

    def test_noise_ignored_after_collapse(self):
        """붕괴 후 노이즈가 무시되어야 한다."""
        q = QECQubit(0, 0, 0)
        q.stress = STRESS_THRESHOLD
        q.check_collapse()
        self.assertTrue(q.collapsed)
        old_stress = q.stress
        q.apply_noise(50.0)
        self.assertEqual(q.stress, old_stress)

    def test_warning_state(self):
        q = QECQubit(0, 0, 0)
        q.stress = 75.0  # > 70 default warning
        self.assertEqual(q.state, QubitState.WARNING)

    def test_collapsed_state(self):
        q = QECQubit(0, 0, 0)
        q.collapsed = True
        self.assertEqual(q.state, QubitState.COLLAPSED)


class TestCollapse(unittest.TestCase):
    """큐비트 붕괴 및 캐스케이드 전파."""

    def test_collapse_at_threshold(self):
        """스트레스가 임계값에 도달하면 붕괴해야 한다."""
        q = QECQubit(0, 0, 0)
        q.stress = STRESS_THRESHOLD
        result = q.check_collapse()
        self.assertTrue(result)
        self.assertTrue(q.collapsed)

    def test_no_collapse_below_threshold(self):
        q = QECQubit(0, 0, 0)
        q.stress = STRESS_THRESHOLD - 1
        result = q.check_collapse()
        self.assertFalse(result)
        self.assertFalse(q.collapsed)

    def test_cascade_damage_to_neighbors(self):
        """붕괴 시 이웃에게 CASCADE_DAMAGE만큼 전파되어야 한다."""
        q1 = QECQubit(0, 0, 0)
        q2 = QECQubit(1, 100, 0)
        q3 = QECQubit(2, 0, 100)
        q1.add_neighbor(q2)
        q1.add_neighbor(q3)

        q1.stress = STRESS_THRESHOLD
        q1.check_collapse()

        self.assertAlmostEqual(q2.stress, CASCADE_DAMAGE)
        self.assertAlmostEqual(q3.stress, CASCADE_DAMAGE)

    def test_cascade_skips_collapsed_neighbors(self):
        """이미 붕괴된 이웃에게는 캐스케이드 피해가 전달되지 않아야 한다."""
        q1 = QECQubit(0, 0, 0)
        q2 = QECQubit(1, 100, 0)
        q2.collapsed = True
        q2.stress = 50.0
        q1.add_neighbor(q2)

        q1.stress = STRESS_THRESHOLD
        q1.check_collapse()

        self.assertEqual(q2.stress, 50.0)  # 변화 없음

    def test_chain_cascade(self):
        """연쇄 붕괴: q1 → q2 → q3 전파 가능."""
        q1 = QECQubit(0, 0, 0)
        q2 = QECQubit(1, 100, 0)
        q3 = QECQubit(2, 200, 0)
        q1.add_neighbor(q2)
        q2.add_neighbor(q3)

        # q2를 임계값 바로 아래로 설정
        q2.stress = STRESS_THRESHOLD - CASCADE_DAMAGE + 1

        q1.stress = STRESS_THRESHOLD
        q1.check_collapse()  # q1 붕괴 → q2에 CASCADE_DAMAGE 전달

        # q2가 이제 임계값 이상이므로 붕괴 가능
        q2.check_collapse()
        self.assertTrue(q2.collapsed)
        self.assertGreater(q3.stress, 0)

    def test_damage_mult(self):
        """damage_mult 매개변수가 캐스케이드 피해를 배율 조절해야 한다."""
        q1 = QECQubit(0, 0, 0)
        q2 = QECQubit(1, 100, 0)
        q1.add_neighbor(q2)

        q1.stress = STRESS_THRESHOLD
        q1.check_collapse(damage_mult=2.0)
        self.assertAlmostEqual(q2.stress, CASCADE_DAMAGE * 2.0)

    def test_double_collapse_returns_false(self):
        """이미 붕괴된 큐비트의 check_collapse는 False를 반환해야 한다."""
        q = QECQubit(0, 0, 0)
        q.stress = STRESS_THRESHOLD
        q.check_collapse()
        self.assertFalse(q.check_collapse())


class TestReset(unittest.TestCase):
    """큐비트 리셋."""

    def test_reset_clears_state(self):
        q = QECQubit(0, 0, 0)
        q.stress = 80.0
        q.collapsed = True
        q.reset()
        self.assertEqual(q.stress, 0.0)
        self.assertFalse(q.collapsed)


if __name__ == "__main__":
    unittest.main()
