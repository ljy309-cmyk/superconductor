"""SQUID 지뢰찾기 게임 엔진 — squid_mines에서 분리된 순수 게임 로직.

렌더링(Pygame)에 의존하지 않으며, 단위 테스트가 가능합니다.

사용법:
    from security.squid_logic import SQUIDGame

    game = SQUIDGame()
    intensity, dist, count = game.flux_intensity(mx, my, sensitivity=3.0)
"""

import math
import random

from config_loader import cfg

# ── 그리드 설정 (config.json에서 로드) ────────────────
GRID_COLS = cfg("squid_mines", "grid_cols", 10)
GRID_ROWS = cfg("squid_mines", "grid_rows", 8)
CELL_SIZE = 52
GRID_OX = (cfg("display", "width", 900) - GRID_COLS * CELL_SIZE) // 2
GRID_OY = 60
NUM_MINES = cfg("squid_mines", "num_mines", 8)

# ── 그래프 설정 ──────────────────────────────────────
GRAPH_HISTORY = 200  # 샘플 수

# ── 센서 민감도 (config.json에서 로드) ────────────────
SENSITIVITY_DEFAULT = cfg("squid_mines", "sensitivity_default", 3.0)
SENSITIVITY_MIN = cfg("squid_mines", "sensitivity_min", 1.0)
SENSITIVITY_MAX = cfg("squid_mines", "sensitivity_max", 8.0)
SENSITIVITY_STEP = 0.5


# ── 게임 로직 ────────────────────────────────────────


class SQUIDGame:
    """SQUID 지뢰찾기 게임 상태."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.mines: set[tuple[int, int]] = set()
        while len(self.mines) < NUM_MINES:
            c = random.randint(0, GRID_COLS - 1)
            r = random.randint(0, GRID_ROWS - 1)
            self.mines.add((c, r))

        self.marked: set[tuple[int, int]] = set()
        self.wrong: set[tuple[int, int]] = set()
        self.revealed = False  # 게임 종료 시 전체 공개
        self.graph_history: list[float] = [0.0] * GRAPH_HISTORY
        self.won = False
        self.t = 0.0
        self._undo_stack: list[tuple[tuple[int, int], str]] = []

    def cell_center(self, col: int, row: int) -> tuple[float, float]:
        """셀 중심 화면 좌표."""
        cx = GRID_OX + col * CELL_SIZE + CELL_SIZE / 2
        cy = GRID_OY + row * CELL_SIZE + CELL_SIZE / 2
        return cx, cy

    def flux_intensity(
        self, mx: float, my: float, sensitivity: float = SENSITIVITY_DEFAULT
    ) -> tuple[float, float, int]:
        """마우스 위치에서의 자기 선속 강도.

        미션2: 가장 가까운 타겟 기반 신호 + 근접 타겟 수
        미션3: sensitivity로 감지 범위/강도 조절

        Returns:
            (intensity 0~1, nearest_dist, nearby_count)
        """
        unfound = [(c, r) for (c, r) in self.mines if (c, r) not in self.marked]
        if not unfound:
            return (0.0, 9999.0, 0)

        # 미션2: 각 타겟까지 거리 계산 → 최근접 기반
        distances: list[float] = []
        for c, r in unfound:
            cx, cy = self.cell_center(c, r)
            distances.append(math.hypot(mx - cx, my - cy))

        nearest_dist = min(distances)
        # 근접 타겟 수 (감지 반경 내)
        detect_radius = CELL_SIZE * sensitivity
        nearby_count = sum(1 for d in distances if d < detect_radius)

        # 미션3: 민감도에 따른 강도 — 가까울수록 + 민감도 높을수록 강한 신호
        ref = CELL_SIZE * sensitivity
        intensity = (ref / max(nearest_dist, 1.0)) ** 2
        # 근접 타겟이 여러 개면 보너스 (+10% per extra)
        intensity *= 1.0 + 0.1 * max(nearby_count - 1, 0)
        intensity = min(intensity, 1.0)

        return (intensity, nearest_dist, nearby_count)

    def update_graph(self, intensity: float, dt: float):
        """자기 선속 그래프에 새 샘플 추가."""
        self.t += dt
        # 노이즈 + 강도 비례 요동
        noise = random.gauss(0, 0.03 + intensity * 0.15)
        value = intensity * 0.7 + noise + 0.05 * math.sin(self.t * 8)
        value = max(-0.3, min(value, 1.2))
        self.graph_history.append(value)
        if len(self.graph_history) > GRAPH_HISTORY:
            self.graph_history.pop(0)

    def mark_cell(self, col: int, row: int):
        """셀 마킹 (지뢰 예상 위치)."""
        if self.revealed:
            return
        pos = (col, row)
        if pos in self.marked or pos in self.wrong:
            return
        if pos in self.mines:
            self.marked.add(pos)
            self._undo_stack.append((pos, "marked"))
            # 승리 체크
            if self.marked == self.mines:
                self.won = True
                self.revealed = True
        else:
            self.wrong.add(pos)
            self._undo_stack.append((pos, "wrong"))

    def undo_mark(self) -> tuple[tuple[int, int], str] | None:
        """마지막 마킹을 실행취소. 되돌린 (pos, kind)를 반환, 없으면 None."""
        if self.revealed or not self._undo_stack:
            return None
        pos, kind = self._undo_stack.pop()
        if kind == "marked":
            self.marked.discard(pos)
        else:
            self.wrong.discard(pos)
        return (pos, kind)

    def get_hover_cell(self, mx: int, my: int) -> tuple[int, int] | None:
        """마우스 위치의 그리드 셀 반환."""
        col = (mx - GRID_OX) // CELL_SIZE
        row = (my - GRID_OY) // CELL_SIZE
        if 0 <= col < GRID_COLS and 0 <= row < GRID_ROWS:
            return (col, row)
        return None
