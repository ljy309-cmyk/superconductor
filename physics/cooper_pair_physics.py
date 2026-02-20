"""쿠퍼 쌍(Cooper Pair) 물리 엔진 — 렌더링 없는 순수 물리 로직.

BCS 이론의 핵심 개념을 시뮬레이션합니다:
  - 격자 이온의 열진동 (포논)
  - 전자-포논 상호작용에 의한 쿠퍼 쌍 형성
  - 온도에 따른 에너지 갭(Δ) 변화
  - 초전도 전이 (Tc 이하에서 저항 = 0)

사용법:
    from physics.cooper_pair_physics import LatticeSimulation
    sim = LatticeSimulation()
    sim.update(dt=1/60)
"""

import math

from config_loader import cfg

# ── 물리 파라미터 (config.json에서 로드) ──────────────
TC_KELVIN = cfg("cooper_pair", "tc_kelvin", 77.0)
TEMP_MIN = cfg("cooper_pair", "temp_min", 4.0)
TEMP_MAX = cfg("cooper_pair", "temp_max", 150.0)
LATTICE_COLS = cfg("cooper_pair", "lattice_cols", 10)
LATTICE_ROWS = cfg("cooper_pair", "lattice_rows", 6)
PHONON_STRENGTH = cfg("cooper_pair", "phonon_strength", 8.0)
PAIR_FORMATION_RANGE = cfg("cooper_pair", "pair_formation_range", 80.0)
ELECTRON_COUNT = cfg("cooper_pair", "electron_count", 12)
ELECTRON_SPEED = cfg("cooper_pair", "electron_speed", 120.0)
GAP_DELTA_MAX = cfg("cooper_pair", "gap_delta_max", 1.0)


def energy_gap(temp: float, tc: float = TC_KELVIN) -> float:
    """BCS 에너지 갭 근사: Δ(T) ≈ Δ₀ × √(1 - (T/Tc)²).

    T >= Tc이면 갭 = 0 (정상 상태).
    """
    if temp >= tc or tc <= 0:
        return 0.0
    ratio = temp / tc
    return GAP_DELTA_MAX * math.sqrt(max(0.0, 1.0 - ratio * ratio))


def cooper_pair_density(temp: float, tc: float = TC_KELVIN) -> float:
    """쿠퍼 쌍 밀도 (0.0 ~ 1.0).

    BCS 이론에서 ns/n ∝ Δ(T)²/Δ₀² = 1 - (T/Tc)².
    """
    if temp >= tc or tc <= 0:
        return 0.0
    ratio = temp / tc
    return max(0.0, 1.0 - ratio * ratio)


def resistance_factor(temp: float, tc: float = TC_KELVIN) -> float:
    """정규화된 저항 (0.0 = 초전도, 1.0 = 정상 상태)."""
    if temp >= tc:
        return 1.0
    return 0.0


def lattice_vibration_amplitude(temp: float, tc: float = TC_KELVIN) -> float:
    """격자 진동 진폭 (온도에 비례, 0.0 ~ 1.0 정규화)."""
    return min(1.0, max(0.0, temp / TEMP_MAX))


class LatticeIon:
    """격자 이온 — 평형점 주위에서 열진동."""

    def __init__(self, eq_x: float, eq_y: float):
        self.eq_x = eq_x
        self.eq_y = eq_y
        self.x = eq_x
        self.y = eq_y
        self.phase = 0.0  # 진동 위상

    def update(self, dt: float, amplitude: float, freq: float = 3.0):
        """열진동 업데이트."""
        self.phase += freq * dt
        self.x = self.eq_x + amplitude * math.sin(self.phase)
        self.y = self.eq_y + amplitude * math.cos(self.phase * 0.7 + 1.0)


class Electron:
    """전도 전자 — 격자 내에서 이동, 쿠퍼 쌍 형성 가능."""

    def __init__(self, x: float, y: float, vx: float, vy: float):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.paired = False
        self.partner: Electron | None = None

    def update(self, dt: float, bounds: tuple[float, float, float, float]):
        """위치 업데이트 + 경계 반사."""
        self.x += self.vx * dt
        self.y += self.vy * dt

        x_min, y_min, x_max, y_max = bounds
        if self.x < x_min:
            self.x = x_min
            self.vx = abs(self.vx)
        elif self.x > x_max:
            self.x = x_max
            self.vx = -abs(self.vx)
        if self.y < y_min:
            self.y = y_min
            self.vy = abs(self.vy)
        elif self.y > y_max:
            self.y = y_max
            self.vy = -abs(self.vy)

    def distance_to(self, other: "Electron") -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx * dx + dy * dy)


class LatticeSimulation:
    """격자 + 전자 + 쿠퍼 쌍 통합 시뮬레이션."""

    def __init__(
        self,
        cols: int = LATTICE_COLS,
        rows: int = LATTICE_ROWS,
        width: float = 600.0,
        height: float = 360.0,
        offset_x: float = 150.0,
        offset_y: float = 100.0,
    ):
        self.cols = cols
        self.rows = rows
        self.width = width
        self.height = height
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.temperature = TC_KELVIN + 20  # 초기: Tc 위 (정상 상태)
        self.t = 0.0

        gap_x = width / (cols - 1) if cols > 1 else width
        gap_y = height / (rows - 1) if rows > 1 else height

        # 격자 이온 생성
        self.ions: list[LatticeIon] = []
        for r in range(rows):
            for c in range(cols):
                x = offset_x + c * gap_x
                y = offset_y + r * gap_y
                ion = LatticeIon(x, y)
                ion.phase = (r * cols + c) * 0.5  # 위상 분산
                self.ions.append(ion)

        # 전자 생성 (격자 내 랜덤 배치)
        self.electrons: list[Electron] = []
        import random

        rng = random.Random(42)
        bounds = self._bounds()
        for _ in range(ELECTRON_COUNT):
            x = rng.uniform(bounds[0] + 20, bounds[2] - 20)
            y = rng.uniform(bounds[1] + 20, bounds[3] - 20)
            angle = rng.uniform(0, 2 * math.pi)
            speed = ELECTRON_SPEED * rng.uniform(0.5, 1.0)
            self.electrons.append(Electron(x, y, speed * math.cos(angle), speed * math.sin(angle)))

    def _bounds(self) -> tuple[float, float, float, float]:
        return (
            self.offset_x - 20,
            self.offset_y - 20,
            self.offset_x + self.width + 20,
            self.offset_y + self.height + 20,
        )

    @property
    def is_superconducting(self) -> bool:
        return self.temperature < TC_KELVIN

    @property
    def gap(self) -> float:
        return energy_gap(self.temperature)

    @property
    def pair_density(self) -> float:
        return cooper_pair_density(self.temperature)

    @property
    def pair_count(self) -> int:
        return sum(1 for e in self.electrons if e.paired) // 2

    def set_temperature(self, temp: float):
        self.temperature = max(TEMP_MIN, min(TEMP_MAX, temp))

    def update(self, dt: float):
        """1프레임 물리 업데이트."""
        self.t += dt
        amp = lattice_vibration_amplitude(self.temperature) * PHONON_STRENGTH

        # 격자 이온 진동
        for ion in self.ions:
            ion.update(dt, amp)

        # 전자 이동
        bounds = self._bounds()
        sc = self.is_superconducting
        speed_mult = 0.3 if sc else 1.0  # 초전도 시 산란 감소 → 느려 보임

        for e in self.electrons:
            e.vx = max(-ELECTRON_SPEED, min(ELECTRON_SPEED, e.vx)) * speed_mult + e.vx * (1 - speed_mult)
            e.vy = max(-ELECTRON_SPEED, min(ELECTRON_SPEED, e.vy)) * speed_mult + e.vy * (1 - speed_mult)
            e.update(dt, bounds)

        # 쿠퍼 쌍 형성/해체
        self._update_pairing()

    def _update_pairing(self):
        """온도에 따라 쿠퍼 쌍을 형성하거나 해체."""
        density = self.pair_density
        pair_range = PAIR_FORMATION_RANGE * (1.0 + density)

        if density <= 0:
            # Tc 이상: 모든 쌍 해체
            for e in self.electrons:
                e.paired = False
                e.partner = None
            return

        # 이미 쌍인 전자의 거리 체크 → 너무 멀면 해체
        for e in self.electrons:
            if e.paired and e.partner:
                if e.distance_to(e.partner) > pair_range * 1.5:
                    e.partner.paired = False
                    e.partner.partner = None
                    e.paired = False
                    e.partner = None

        # 짝 없는 전자끼리 쌍 형성
        unpaired = [e for e in self.electrons if not e.paired]
        paired_new = set()
        for i, e1 in enumerate(unpaired):
            if id(e1) in paired_new:
                continue
            for e2 in unpaired[i + 1 :]:
                if id(e2) in paired_new:
                    continue
                dist = e1.distance_to(e2)
                if dist < pair_range:
                    e1.paired = True
                    e2.paired = True
                    e1.partner = e2
                    e2.partner = e1
                    paired_new.add(id(e1))
                    paired_new.add(id(e2))
                    break
