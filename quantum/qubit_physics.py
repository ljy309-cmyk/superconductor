"""큐비트 물리 엔진 (Model) — qubit_chain에서 분리된 순수 물리 로직.

렌더링(Pygame)에 의존하지 않으며, 단위 테스트가 가능합니다.

사용법:
    from quantum.qubit_physics import QubitNetwork

    net = QubitNetwork()
    net.update(dt, noise_rate=3.0, cascade_damage=20.0, shield_active=False, qec_reduction=0.2)
    print(net.is_game_over)
"""

import math
import random

from config_loader import cfg


# 물리 파라미터 (config.json에서 로드, 없으면 기본값)
STRESS_THRESHOLD = cfg("qubit_chain", "stress_threshold", 100.0)
CASCADE_DAMAGE = cfg("qubit_chain", "cascade_damage", 20.0)
NOISE_RATE_BASE = cfg("qubit_chain", "noise_rate_base", 3.0)
COLLAPSE_ANIM_DURATION = cfg("qubit_chain", "collapse_anim_duration", 0.5)
_STRESS_DANGER = cfg("qubit_chain", "stress_danger", 85.0)
_STRESS_WARNING = cfg("qubit_chain", "stress_warning", 50.0)


class QubitNode:
    """초전도 큐비트 노드."""

    def __init__(self, qid: int, x: float, y: float):
        self.qid = qid
        self.x = x
        self.y = y
        self.stress = 0.0
        self.collapsed = False
        self.collapse_timer = 0.0
        self.neighbors: list["QubitNode"] = []

    @property
    def state(self) -> str:
        if self.collapsed:
            return "collapsed"
        if self.stress >= _STRESS_DANGER:
            return "danger"
        if self.stress >= _STRESS_WARNING:
            return "warning"
        return "stable"

    def add_neighbor(self, other: "QubitNode"):
        if other not in self.neighbors:
            self.neighbors.append(other)
            other.neighbors.append(self)

    def apply_noise(self, amount: float):
        if not self.collapsed:
            self.stress = min(self.stress + amount, STRESS_THRESHOLD + 50)

    def stabilize(self, amount: float):
        if not self.collapsed:
            self.stress = max(self.stress - amount, 0.0)

    def check_collapse(self, cascade_damage: float = CASCADE_DAMAGE) -> bool:
        if self.collapsed:
            return False
        if self.stress >= STRESS_THRESHOLD:
            self.collapsed = True
            self.collapse_timer = COLLAPSE_ANIM_DURATION
            for nb in self.neighbors:
                if not nb.collapsed:
                    nb.apply_noise(cascade_damage)
            return True
        return False

    def reset(self):
        self.stress = 0.0
        self.collapsed = False
        self.collapse_timer = 0.0


def build_hexagonal_network(cx: float, cy: float, ring_r: float = 150) -> list[QubitNode]:
    """육각형 + 중앙 큐비트 네트워크 생성."""
    nodes: list[QubitNode] = []

    center = QubitNode(0, cx, cy)
    nodes.append(center)

    for i in range(6):
        angle = math.radians(60 * i - 90)
        nx = cx + ring_r * math.cos(angle)
        ny = cy + ring_r * math.sin(angle)
        nodes.append(QubitNode(i + 1, nx, ny))

    for i in range(1, 7):
        center.add_neighbor(nodes[i])
        next_i = (i % 6) + 1
        nodes[i].add_neighbor(nodes[next_i])

    return nodes


class QubitNetwork:
    """큐비트 네트워크 시뮬레이션 (순수 물리 로직)."""

    def __init__(self, cx: float = 450, cy: float = 320, ring_r: float = 150):
        self.nodes = build_hexagonal_network(cx, cy, ring_r)
        self._cascade_events: list[str] = []

    @property
    def is_game_over(self) -> bool:
        return all(n.collapsed for n in self.nodes)

    @property
    def alive_count(self) -> int:
        return sum(1 for n in self.nodes if not n.collapsed)

    @property
    def collapsed_count(self) -> int:
        return sum(1 for n in self.nodes if n.collapsed)

    @property
    def max_stress(self) -> float:
        return max((n.stress for n in self.nodes), default=0)

    def pop_events(self) -> list[str]:
        """최근 이벤트 로그 반환 후 비움."""
        events = self._cascade_events[:]
        self._cascade_events.clear()
        return events

    def update(self, dt: float, noise_rate: float, cascade_damage: float,
               shield_active: bool, qec_reduction: float) -> list[int]:
        """물리 업데이트. 붕괴된 노드 ID 목록 반환."""
        noise_mult = qec_reduction if shield_active else 1.0
        collapsed_ids: list[int] = []

        for n in self.nodes:
            if not n.collapsed:
                noise = noise_rate * dt * (0.5 + random.random()) * noise_mult
                n.apply_noise(noise)
            if n.collapse_timer > 0:
                n.collapse_timer -= dt

        # 연쇄 붕괴 체크
        effective_cascade = cascade_damage * (qec_reduction if shield_active else 1.0)
        changed = True
        while changed:
            changed = False
            for n in self.nodes:
                if n.check_collapse(effective_cascade):
                    changed = True
                    collapsed_ids.append(n.qid)
                    if shield_active:
                        self._cascade_events.append(
                            f"Q{n.qid} COLLAPSED (shielded: +{int(effective_cascade)})")
                    else:
                        self._cascade_events.append(
                            f"Q{n.qid} COLLAPSED → cascade +{int(cascade_damage)}")

        return collapsed_ids

    def heal_all(self, amount: float):
        """모든 생존 큐비트 힐링."""
        for n in self.nodes:
            if not n.collapsed:
                n.stress = max(n.stress - amount, 0.0)
        self._cascade_events.append(f"HEAL! All -{int(amount)} stress")

    def correct_node(self, qid: int) -> bool:
        """특정 큐비트 오류 정정 (stress → 0)."""
        for n in self.nodes:
            if n.qid == qid and not n.collapsed:
                n.stress = 0.0
                self._cascade_events.append(f"Q{qid} corrected (stress → 0)")
                return True
        return False

    def reset(self):
        """전체 리셋."""
        for n in self.nodes:
            n.reset()
        self._cascade_events.clear()
