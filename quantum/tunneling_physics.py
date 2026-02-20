"""터널링 물리 엔진 — tunneling에서 분리된 순수 물리 로직.

렌더링(Pygame)에 의존하지 않으며, 단위 테스트가 가능합니다.

사용법:
    from quantum.tunneling_physics import QuantumParticle, _calc_tunnel_prob

    p = QuantumParticle()
    p.update(dt, barrier_width=12, tunnel_prob=0.1)
"""

import math
import random

from config_loader import cfg
from logger import get_module_logger

_log = get_module_logger("tunneling_physics")

# ── 물리 파라미터 (config.json에서 로드) ──────────────
TUNNEL_PROB_BASE = cfg("tunneling", "tunnel_prob_base", 0.10)
PARTICLE_SPEED = cfg("tunneling", "particle_speed", 200.0)
PARTICLE_RADIUS = cfg("tunneling", "particle_radius", 10)
BARRIER_WIDTH_DEFAULT = cfg("tunneling", "barrier_width_default", 12)
BARRIER_WIDTH_MIN = cfg("tunneling", "barrier_width_min", 4)
BARRIER_WIDTH_MAX = cfg("tunneling", "barrier_width_max", 200)
SUPERPOSITION_HZ = cfg("tunneling", "superposition_hz", 6.0)
TUNNEL_SPEED_BOOST = cfg("tunneling", "tunnel_speed_boost", 2.0)
_TUNNEL_DECAY = cfg("tunneling", "tunnel_decay_rate", 0.02)
_VY_RANGE = cfg("tunneling", "particle_vy_range", 60.0)
_TUNNEL_FLASH = cfg("tunneling", "tunnel_flash_sec", 0.6)
_REFLECT_FLASH = cfg("tunneling", "reflect_flash_sec", 0.4)
REFLECT_DAMPING = cfg("tunneling", "reflect_damping", 0.8)
BLOCH_LERP_SPEED = cfg("tunneling", "bloch_lerp_speed", 8.0)
TRIAL_HISTORY_MAX = cfg("tunneling", "trial_history_max", 5000)

# ── 영역 레이아웃 (config.json에서 로드) ───────────────
# 왼쪽: 터널링 시뮬레이션 | 오른쪽: 블로흐 구
SIM_LEFT = cfg("tunneling", "sim_left", 30)
SIM_TOP = cfg("tunneling", "sim_top", 70)
SIM_W = cfg("tunneling", "sim_width", 520)
SIM_H = cfg("tunneling", "sim_height", 420)

# 장벽 위치 (시뮬레이션 영역 중앙)
BARRIER_X = SIM_LEFT + SIM_W // 2


def _lerp(a: float, b: float, t: float) -> float:
    """선형 보간 — a에서 b로 t(0~1)만큼.

    t는 [0, 1] 범위로 클램핑됩니다.
    """
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


def _bloch_smooth_theta(
    current: float,
    target: float,
    dt: float,
    speed: float = BLOCH_LERP_SPEED,
) -> float:
    """블로흐 구 θ 각도를 target으로 부드럽게 보간 (지수 감쇠 lerp).

    프레임 속도 독립적인 지수 보간으로 현재 θ를 목표 θ에 수렴시킵니다.
    수식: result = current + (target - current) * (1 - e^(-speed * dt))

    Args:
        current: 현재 θ (라디안).
        target: 목표 θ (라디안).
        dt: 시간 간격 (초). 음수이면 0으로 처리.
        speed: 보간 속도 (높을수록 빠르게 수렴, 기본 8.0).

    Returns:
        보간된 θ (라디안, 0~π 범위로 클램핑).
    """
    if dt <= 0:
        return max(0.0, min(math.pi, current))
    alpha = 1.0 - math.exp(-speed * dt)
    result = current + (target - current) * alpha
    return max(0.0, min(math.pi, result))


def _calc_tunnel_prob(barrier_width: int, base_prob: float | None = None) -> float:
    """벽 두께에 따른 터널링 확률 — 두꺼울수록 확률 감소.

    기본 두께(12px)에서 10 %, 두께 200px이면 ~0.5 % 수준으로 지수 감쇠.
    barrier_width는 [BARRIER_WIDTH_MIN, BARRIER_WIDTH_MAX] 범위로 클램핑됩니다.

    Args:
        barrier_width: 장벽 두께 (px).
        base_prob: 기본 확률. None이면 config 값(TUNNEL_PROB_BASE) 사용.
                   프리셋 전환 시 런타임 값을 전달합니다.
    """
    barrier_width = max(BARRIER_WIDTH_MIN, min(BARRIER_WIDTH_MAX, int(barrier_width)))
    prob_base = TUNNEL_PROB_BASE if base_prob is None else max(0.0, min(1.0, float(base_prob)))
    exponent = -_TUNNEL_DECAY * (barrier_width - BARRIER_WIDTH_DEFAULT)
    # 오버플로 방어: exp(x)에서 x가 너무 크거나 작으면 클램핑
    exponent = max(-500.0, min(500.0, exponent))
    return prob_base * math.exp(exponent)


# ── 에너지 레벨 (#28) ────────────────────────────────


def calc_energy_levels(barrier_width: int, tunnel_prob: float) -> dict:
    """에너지 다이어그램용 정규화된 에너지 레벨 계산.

    교육용 시각화를 위해 정규화(0~1)된 값을 반환합니다.

    Returns:
        {"particle_energy": float, "barrier_height": float, "ratio": float}
        - particle_energy: 입자 운동 에너지 (0~1 정규화)
        - barrier_height: 장벽 퍼텐셜 높이 (0~1 정규화)
        - ratio: E/V₀ 비율 (1 미만이면 고전적으로 통과 불가)
    """
    # 장벽 높이: 두께에 비례 (BARRIER_WIDTH_MIN → 낮음, BARRIER_WIDTH_MAX → 높음)
    bw_clamped = max(BARRIER_WIDTH_MIN, min(BARRIER_WIDTH_MAX, int(barrier_width)))
    barrier_norm = (bw_clamped - BARRIER_WIDTH_MIN) / max(1, BARRIER_WIDTH_MAX - BARRIER_WIDTH_MIN)
    v0 = 0.3 + 0.65 * barrier_norm  # V₀ ∈ [0.30, 0.95]

    # 입자 에너지: 고정된 운동 에너지 (고전적으로 항상 장벽보다 낮게 설정)
    e_particle = 0.25

    # E/V₀ 비율
    ratio = e_particle / v0 if v0 > 0 else 0.0

    return {
        "particle_energy": e_particle,
        "barrier_height": v0,
        "ratio": ratio,
    }


# ── 파동함수 ψ(x) 계산 (#27) ────────────────────────

_PSI_K_SCALE = cfg("tunneling", "psi_k_scale", 0.12)  # 입사파 파수 스케일


def compute_psi(
    barrier_width: int,
    tunnel_prob: float,
    n_points: int = 200,
) -> list[tuple[float, float]]:
    """시뮬레이션 영역 전체에 걸친 ψ(x) 계산 (정규화 좌표).

    3개 영역:
      - 장벽 왼쪽: 입사파 sin(k·x)
      - 장벽 내부: 지수 감쇠 exp(-κ·x)
      - 장벽 오른쪽: 투과파 T·sin(k·x)

    Returns:
        (x_norm, psi) 리스트. x_norm ∈ [0, 1], psi ∈ [-1, 1].
    """
    barrier_cx = 0.5  # 장벽 중심 (정규화)
    half_w = (barrier_width / SIM_W) * 0.5
    b_left = barrier_cx - half_w
    b_right = barrier_cx + half_w

    k = _PSI_K_SCALE * math.pi  # 입사파 파수
    # 감쇠 상수 κ: 장벽이 두꺼울수록 더 빠르게 감쇠
    kappa = _TUNNEL_DECAY * 80.0 + 0.5

    # 투과 계수 T (장벽 투과 후 진폭 비율)
    t_coeff = max(0.01, math.sqrt(max(0.0, min(1.0, tunnel_prob))))

    points: list[tuple[float, float]] = []
    for i in range(n_points):
        x = i / (n_points - 1)

        if x < b_left:
            # 입사파 영역
            psi = math.sin(k * (x - b_left) * SIM_W)
        elif x <= b_right:
            # 장벽 내부: 왼쪽 경계에서 오른쪽으로 지수 감쇠
            dx = (x - b_left) * SIM_W
            psi = math.exp(-kappa * dx)
        else:
            # 투과파 영역: 감쇠된 진폭
            psi = t_coeff * math.sin(k * (x - b_right) * SIM_W)

        points.append((x, psi))

    return points


# ── 입자 클래스 ──────────────────────────────────────


class QuantumParticle:
    """양자 입자 — 중첩 상태 + 터널링.

    Args:
        seed: 난수 시드. 지정하면 재현 가능한 시뮬레이션.
              None이면 비결정적 (기본 동작).
    """

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self.reset()
        self.tunnel_count = 0
        self.reflect_count = 0
        self.total_attempts = 0

    def reset(self):
        """입자를 왼쪽에서 다시 발사."""
        self.x = SIM_LEFT + 40.0
        self.y = SIM_TOP + SIM_H / 2.0
        self.vx = PARTICLE_SPEED
        self.vy = (self._rng.random() - 0.5) * _VY_RANGE  # 약간의 수직 랜덤
        self.alive = True
        self.tunneled: bool | None = None  # None=미결정, True=터널링, False=반사
        self.flash_timer = 0.0

    def qubit_state(self, time_ms: float) -> int:
        """현재 중첩 상태에서의 '관측값' (빠르게 교차).

        Args:
            time_ms: 현재 시간 (밀리초). Pygame 환경에서는 pygame.time.get_ticks().
        """
        phase = math.sin(time_ms / 1000.0 * SUPERPOSITION_HZ * 2 * math.pi)
        return 0 if phase >= 0 else 1

    def superposition_alpha(self, time_ms: float) -> float:
        """블로흐 구 위의 각도 (0~π): 0=|0⟩, π=|1⟩.

        Args:
            time_ms: 현재 시간 (밀리초). Pygame 환경에서는 pygame.time.get_ticks().
        """
        phase = math.sin(time_ms / 1000.0 * SUPERPOSITION_HZ * 2 * math.pi)
        return math.pi * (1 - phase) / 2  # 0→π 매핑

    def update(
        self,
        dt: float,
        barrier_width: int = BARRIER_WIDTH_DEFAULT,
        tunnel_prob: float = TUNNEL_PROB_BASE,
        speed_boost: float = TUNNEL_SPEED_BOOST,
    ):
        if not self.alive:
            return
        if dt <= 0:
            return

        # 입력 클램핑
        barrier_width = max(BARRIER_WIDTH_MIN, min(BARRIER_WIDTH_MAX, int(barrier_width)))
        tunnel_prob = max(0.0, min(1.0, float(tunnel_prob)))
        speed_boost = max(0.0, float(speed_boost))

        self.x += self.vx * dt
        self.y += self.vy * dt

        # 상하 벽 반사
        if self.y - PARTICLE_RADIUS < SIM_TOP:
            self.y = SIM_TOP + PARTICLE_RADIUS
            self.vy = abs(self.vy)
        elif self.y + PARTICLE_RADIUS > SIM_TOP + SIM_H:
            self.y = SIM_TOP + SIM_H - PARTICLE_RADIUS
            self.vy = -abs(self.vy)

        # 장벽 충돌 판정
        if self.tunneled is None and self.vx > 0:
            # 오른쪽으로 진행 중, 장벽에 도달
            if self.x + PARTICLE_RADIUS >= BARRIER_X - barrier_width / 2:
                self.total_attempts += 1
                if self._rng.random() < tunnel_prob:
                    # 터널링 성공! 장벽 반대편으로 좌표 이동 + 속도 부스트
                    self.x = BARRIER_X + barrier_width / 2 + PARTICLE_RADIUS + 5
                    self.vx = abs(self.vx) * speed_boost
                    self.tunneled = True
                    self.tunnel_count += 1
                    self.flash_timer = _TUNNEL_FLASH
                    _log.debug(
                        "터널링 성공 #%d prob=%.3f barrier=%.0f",
                        self.tunnel_count,
                        tunnel_prob,
                        barrier_width,
                    )
                else:
                    # 반사
                    self.vx = -abs(self.vx) * REFLECT_DAMPING
                    self.x = BARRIER_X - barrier_width / 2 - PARTICLE_RADIUS - 2
                    self.tunneled = False
                    self.reflect_count += 1
                    self.flash_timer = _REFLECT_FLASH
                    _log.debug(
                        "반사 #%d prob=%.3f barrier=%.0f",
                        self.reflect_count,
                        tunnel_prob,
                        barrier_width,
                    )

        # 화면 밖으로 나가면 재발사
        if self.x < SIM_LEFT - 20 or self.x > SIM_LEFT + SIM_W + 20:
            self.reset()

        if self.flash_timer > 0:
            self.flash_timer -= dt


# ── 배리어 스위퍼 (#29) ──────────────────────────────


# 스위퍼 설정 (config.json에서 로드)
SWEEP_TRIALS_PER_WIDTH = cfg("tunneling", "sweep_trials_per_width", 50)
SWEEP_STEP = cfg("tunneling", "sweep_step", 10)
SWEEP_BATCH_SIZE = cfg("tunneling", "sweep_batch_per_frame", 10)


class BarrierSweeper:
    """자동으로 장벽 폭 범위를 순회하며 터널링 통계 수집.

    프레임마다 ``advance()``를 호출하면 내부적으로 소량의 시행(batch)을
    수행하여 UI 프레임 드롭 없이 점진적으로 스위프를 진행합니다.

    Args:
        base_prob: 기본 터널링 확률 (슬라이더 값).
        width_min: 스위프 시작 폭 (px).
        width_max: 스위프 종료 폭 (px).
        step: 폭 증가 단위.
        trials_per_width: 각 폭에서의 시행 횟수.
        batch_size: 프레임당 진행할 시행 수.
        seed: 난수 시드 (재현성).
    """

    def __init__(
        self,
        base_prob: float = TUNNEL_PROB_BASE,
        width_min: int = BARRIER_WIDTH_MIN,
        width_max: int = BARRIER_WIDTH_MAX,
        step: int = SWEEP_STEP,
        trials_per_width: int = SWEEP_TRIALS_PER_WIDTH,
        batch_size: int = SWEEP_BATCH_SIZE,
        seed: int | None = None,
    ):
        self.base_prob = max(0.0, min(1.0, float(base_prob)))
        self.width_min = max(BARRIER_WIDTH_MIN, int(width_min))
        self.width_max = min(BARRIER_WIDTH_MAX, int(width_max))
        self.step = max(1, int(step))
        self.trials_per_width = max(1, int(trials_per_width))
        self.batch_size = max(1, int(batch_size))
        self._rng = random.Random(seed)

        # 스위프할 폭 목록
        self.widths: list[int] = list(range(self.width_min, self.width_max + 1, self.step))
        if not self.widths:
            self.widths = [self.width_min]

        # 결과: {width: {"tunnel": int, "reflect": int, "total": int, "rate": float}}
        self.results: dict[int, dict] = {}

        # 진행 상태
        self._width_idx = 0  # 현재 폭 인덱스
        self._trial_count = 0  # 현재 폭에서 완료된 시행 수
        self.done = False

        _log.info(
            "배리어 스위퍼 시작: %d~%dpx step=%d trials=%d",
            self.width_min,
            self.width_max,
            self.step,
            self.trials_per_width,
        )

    @property
    def current_width(self) -> int:
        """현재 스위프 중인 장벽 폭."""
        if self._width_idx < len(self.widths):
            return self.widths[self._width_idx]
        return self.widths[-1]

    @property
    def progress(self) -> float:
        """전체 진행률 (0.0~1.0)."""
        total = len(self.widths) * self.trials_per_width
        if total == 0:
            return 1.0
        completed = self._width_idx * self.trials_per_width + self._trial_count
        return min(1.0, completed / total)

    def advance(self) -> bool:
        """프레임당 호출 — batch_size만큼 시행 진행.

        Returns:
            True면 아직 진행 중, False면 스위프 완료.
        """
        if self.done:
            return False

        remaining_batch = self.batch_size
        while remaining_batch > 0 and not self.done:
            w = self.widths[self._width_idx]
            prob = _calc_tunnel_prob(w, self.base_prob)

            # 현재 폭에서 남은 시행 수
            remaining_for_width = self.trials_per_width - self._trial_count
            do_now = min(remaining_batch, remaining_for_width)

            # 결과 딕셔너리 초기화
            if w not in self.results:
                self.results[w] = {"tunnel": 0, "reflect": 0, "total": 0, "rate": 0.0}

            # 시행 실행 (순수 확률 판정)
            for _ in range(do_now):
                if self._rng.random() < prob:
                    self.results[w]["tunnel"] += 1
                else:
                    self.results[w]["reflect"] += 1
                self.results[w]["total"] += 1

            self._trial_count += do_now
            remaining_batch -= do_now

            # 현재 폭 완료 → 확률 계산 후 다음 폭으로
            if self._trial_count >= self.trials_per_width:
                r = self.results[w]
                r["rate"] = r["tunnel"] / r["total"] if r["total"] > 0 else 0.0
                _log.debug(
                    "스위프 w=%dpx: %d/%d = %.1f%% (이론 %.1f%%)",
                    w,
                    r["tunnel"],
                    r["total"],
                    r["rate"] * 100,
                    prob * 100,
                )
                self._width_idx += 1
                self._trial_count = 0
                if self._width_idx >= len(self.widths):
                    self.done = True
                    _log.info("배리어 스위퍼 완료: %d개 폭 스위프", len(self.widths))

        return not self.done

    def get_sorted_results(self) -> list[tuple[int, float, float]]:
        """완료된 결과를 (width, measured_rate, theory_rate) 리스트로 반환.

        폭 기준 오름차순 정렬.
        """
        out: list[tuple[int, float, float]] = []
        for w in sorted(self.results):
            r = self.results[w]
            measured = r["rate"]
            theory = _calc_tunnel_prob(w, self.base_prob)
            out.append((w, measured, theory))
        return out
