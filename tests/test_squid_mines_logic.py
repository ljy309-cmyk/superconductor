"""SQUID 지뢰찾기 게임 로직 단위 테스트."""

import os
import sys
import unittest
from unittest.mock import MagicMock

# pygame mock
sys.modules.setdefault("pygame", MagicMock())
sys.modules.setdefault("pygame.time", MagicMock())
sys.modules.setdefault("pygame.mixer", MagicMock())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.squid_mines import (
    CELL_SIZE,
    GRID_COLS,
    GRID_OX,
    GRID_OY,
    GRID_ROWS,
    NUM_MINES,
    SQUIDGame,
)


class TestSQUIDGameInit(unittest.TestCase):
    """게임 초기화 및 리셋."""

    def test_mines_count(self):
        game = SQUIDGame()
        self.assertEqual(len(game.mines), NUM_MINES)

    def test_mines_within_grid(self):
        game = SQUIDGame()
        for col, row in game.mines:
            self.assertGreaterEqual(col, 0)
            self.assertLess(col, GRID_COLS)
            self.assertGreaterEqual(row, 0)
            self.assertLess(row, GRID_ROWS)

    def test_reset_clears_state(self):
        game = SQUIDGame()
        game.marked.add((0, 0))
        game.wrong.add((1, 1))
        game.won = True
        game.reset()
        self.assertEqual(len(game.marked), 0)
        self.assertEqual(len(game.wrong), 0)
        self.assertFalse(game.won)


class TestSQUIDCellCenter(unittest.TestCase):
    """셀 중심 좌표 계산."""

    def test_first_cell(self):
        game = SQUIDGame()
        cx, cy = game.cell_center(0, 0)
        self.assertEqual(cx, GRID_OX + CELL_SIZE / 2)
        self.assertEqual(cy, GRID_OY + CELL_SIZE / 2)

    def test_last_cell(self):
        game = SQUIDGame()
        cx, cy = game.cell_center(GRID_COLS - 1, GRID_ROWS - 1)
        expected_x = GRID_OX + (GRID_COLS - 1) * CELL_SIZE + CELL_SIZE / 2
        expected_y = GRID_OY + (GRID_ROWS - 1) * CELL_SIZE + CELL_SIZE / 2
        self.assertEqual(cx, expected_x)
        self.assertEqual(cy, expected_y)


class TestSQUIDFluxIntensity(unittest.TestCase):
    """자기 선속 강도 계산."""

    def test_no_unfound_mines_zero(self):
        game = SQUIDGame()
        game.marked = game.mines.copy()
        intensity, dist, count = game.flux_intensity(400, 300)
        self.assertEqual(intensity, 0.0)
        self.assertEqual(dist, 9999.0)
        self.assertEqual(count, 0)

    def test_close_to_mine_high_intensity(self):
        game = SQUIDGame()
        mine = next(iter(game.mines))
        cx, cy = game.cell_center(*mine)
        intensity, dist, count = game.flux_intensity(cx, cy, sensitivity=3.0)
        self.assertGreater(intensity, 0.5)

    def test_far_from_mine_low_intensity(self):
        game = SQUIDGame()
        intensity, dist, count = game.flux_intensity(-1000, -1000, sensitivity=1.0)
        self.assertLess(intensity, 0.1)

    def test_higher_sensitivity(self):
        game = SQUIDGame()
        mine = next(iter(game.mines))
        cx, cy = game.cell_center(*mine)
        offset = CELL_SIZE * 2
        i_low, _, _ = game.flux_intensity(cx + offset, cy, sensitivity=1.0)
        i_high, _, _ = game.flux_intensity(cx + offset, cy, sensitivity=5.0)
        self.assertGreaterEqual(i_high, i_low)

    def test_intensity_capped(self):
        game = SQUIDGame()
        mine = next(iter(game.mines))
        cx, cy = game.cell_center(*mine)
        intensity, _, _ = game.flux_intensity(cx, cy, sensitivity=8.0)
        self.assertLessEqual(intensity, 1.0)

    def test_nearby_count_positive(self):
        game = SQUIDGame()
        mine = next(iter(game.mines))
        cx, cy = game.cell_center(*mine)
        _, _, count = game.flux_intensity(cx, cy, sensitivity=8.0)
        self.assertGreaterEqual(count, 1)


class TestSQUIDMarkCell(unittest.TestCase):
    """셀 마킹."""

    def test_mark_mine_correct(self):
        game = SQUIDGame()
        mine = next(iter(game.mines))
        game.mark_cell(*mine)
        self.assertIn(mine, game.marked)

    def test_mark_empty_wrong(self):
        game = SQUIDGame()
        empty = None
        for c in range(GRID_COLS):
            for r in range(GRID_ROWS):
                if (c, r) not in game.mines:
                    empty = (c, r)
                    break
            if empty:
                break
        game.mark_cell(*empty)
        self.assertIn(empty, game.wrong)

    def test_no_duplicate(self):
        game = SQUIDGame()
        mine = next(iter(game.mines))
        game.mark_cell(*mine)
        game.mark_cell(*mine)
        self.assertEqual(len(game.marked), 1)

    def test_win_condition(self):
        game = SQUIDGame()
        for mine in list(game.mines):
            game.mark_cell(*mine)
        self.assertTrue(game.won)
        self.assertTrue(game.revealed)

    def test_no_mark_after_reveal(self):
        game = SQUIDGame()
        game.revealed = True
        mine = next(iter(game.mines))
        game.mark_cell(*mine)
        self.assertEqual(len(game.marked), 0)


class TestSQUIDHoverCell(unittest.TestCase):
    """마우스 위치 → 셀."""

    def test_inside(self):
        game = SQUIDGame()
        mx = GRID_OX + CELL_SIZE // 2
        my = GRID_OY + CELL_SIZE // 2
        self.assertEqual(game.get_hover_cell(mx, my), (0, 0))

    def test_outside_left(self):
        game = SQUIDGame()
        self.assertIsNone(game.get_hover_cell(GRID_OX - 10, GRID_OY))

    def test_outside_below(self):
        game = SQUIDGame()
        my = GRID_OY + GRID_ROWS * CELL_SIZE + 10
        self.assertIsNone(game.get_hover_cell(GRID_OX, my))


class TestSQUIDGraphUpdate(unittest.TestCase):
    """그래프 업데이트."""

    def test_values_bounded(self):
        game = SQUIDGame()
        for _ in range(100):
            game.update_graph(0.8, 0.016)
        for val in game.graph_history:
            self.assertGreaterEqual(val, -0.3)
            self.assertLessEqual(val, 1.2)


if __name__ == "__main__":
    unittest.main()
