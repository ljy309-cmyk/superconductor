"""QEC 물리 엔진 — qec_shield에서 분리된 순수 물리 로직.

렌더링(Pygame)에 의존하지 않으며, 단위 테스트가 가능합니다.

사용법:
    from quantum.qec_physics import QECQubit, build_grid

    nodes = build_grid()
    for n in nodes:
        n.apply_noise(5.0)
"""

from config_loader import cfg
from quantum.qubit_physics import QubitState

# ── 물리 파라미터 (config.json에서 로드) ──────────────
NOISE_RATE = cfg("qec_shield", "noise_rate", 5.0)
QEC_REDUCTION_DEFAULT = cfg("qec_shield", "qec_reduction_default", 0.5)
QEC_REDUCTION_MIN = cfg("qec_shield", "qec_reduction_min", 0.0)
QEC_REDUCTION_MAX = cfg("qec_shield", "qec_reduction_max", 1.0)
QEC_REDUCTION_STEP = 0.1
QEC_DURATION = cfg("qec_shield", "qec_duration", 5.0)
QEC_COOLDOWN = cfg("qec_shield", "qec_cooldown", 8.0)
HEAL_AMOUNT = cfg("qec_shield", "heal_amount", 20.0)
STRESS_THRESHOLD = cfg("qec_shield", "stress_threshold", 100.0)
CASCADE_DAMAGE = cfg("qec_shield", "cascade_damage", 15.0)

NODE_RADIUS = cfg("qec_shield", "node_radius", 30)
_STRESS_WARNING = cfg("qec_shield", "stress_warning", 70.0)
GRID_COLS = cfg("qec_shield", "grid_cols", 5)
GRID_ROWS = cfg("qec_shield", "grid_rows", 3)


# ── 큐비트 노드 ──────────────────────────────────────

class QECQubit:
    """QEC 보호 대상 큐비트."""

    def __init__(self, qid: int, x: float, y: float):
        self.qid = qid
        self.x = x
        self.y = y
        self.stress = 0.0
        self.collapsed = False
        self.neighbors: list["QECQubit"] = []

    @property
    def state(self) -> QubitState:
        if self.collapsed:
            return QubitState.COLLAPSED
        if self.stress >= _STRESS_WARNING:
            return QubitState.WARNING
        return QubitState.STABLE

    def add_neighbor(self, other: "QECQubit"):
        if other not in self.neighbors:
            self.neighbors.append(other)
            other.neighbors.append(self)

    def apply_noise(self, amount: float):
        if not self.collapsed:
            self.stress = min(self.stress + amount, 150.0)

    def check_collapse(self, damage_mult: float = 1.0, base_damage: float = 0) -> bool:
        if self.collapsed:
            return False
        if self.stress >= STRESS_THRESHOLD:
            self.collapsed = True
            dmg = (base_damage if base_damage > 0 else CASCADE_DAMAGE) * damage_mult
            for nb in self.neighbors:
                if not nb.collapsed:
                    nb.apply_noise(dmg)
            return True
        return False

    def reset(self):
        self.stress = 0.0
        self.collapsed = False


# ── 네트워크 빌더 ────────────────────────────────────

def build_grid() -> list[QECQubit]:
    """5x3 격자 큐비트 네트워크."""
    nodes: list[QECQubit] = []
    ox, oy = 200, 140
    gap_x, gap_y = 110, 110

    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            qid = r * GRID_COLS + c
            x = ox + c * gap_x
            y = oy + r * gap_y
            nodes.append(QECQubit(qid, x, y))

    # 인접 연결 (상하좌우)
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            idx = r * GRID_COLS + c
            if c + 1 < GRID_COLS:
                nodes[idx].add_neighbor(nodes[idx + 1])
            if r + 1 < GRID_ROWS:
                nodes[idx].add_neighbor(nodes[idx + GRID_COLS])

    return nodes
