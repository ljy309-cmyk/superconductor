"""터널링 물리 엔진 — tunneling에서 분리된 순수 물리 로직.

렌더링(Pygame)에 의존하지 않으며, 단위 테스트가 가능합니다.

사용법:
    from quantum.tunneling_physics import QuantumParticle, _calc_tunnel_prob
    from quantum.tunneling_physics import compute_wavefunction

    p = QuantumParticle()
    p.update(dt, barrier_width=12, tunnel_prob=0.1)

    # 파동함수 시각화 데이터 생성
    xs, psi = compute_wavefunction(barrier_width=12, n_points=200)
"""

import math
import random

from config_loader import cfg

# ── 물리 파라미터 (config.json에서 로드) ──────────────
TUNNEL_PROB_BASE = cfg("tunneling", "tunnel_prob_base", 0.10)
PARTICLE_SPEED = cfg("tunneling", "particle_speed", 200.0)
PARTICLE_RADIUS = 10
BARRIER_WIDTH_DEFAULT = cfg("tunneling", "barrier_width_default", 12)
BARRIER_WIDTH_MIN = cfg("tunneling", "barrier_width_min", 4)
BARRIER_WIDTH_MAX = cfg("tunneling", "barrier_width_max", 200)
SUPERPOSITION_HZ = cfg("tunneling", "superposition_hz", 6.0)
TUNNEL_SPEED_BOOST = cfg("tunneling", "tunnel_speed_boost", 2.0)
_TUNNEL_DECAY = cfg("tunneling", "tunnel_decay_rate", 0.02)
_VY_RANGE = cfg("tunneling", "particle_vy_range", 60.0)
_TUNNEL_FLASH = cfg("tunneling", "tunnel_flash_sec", 0.6)
_REFLECT_FLASH = cfg("tunneling", "reflect_flash_sec", 0.4)

# ── 영역 레이아웃 ────────────────────────────────────
# 왼쪽: 터널링 시뮬레이션 | 오른쪽: 블로흐 구
SIM_LEFT, SIM_TOP = 30, 70
SIM_W, SIM_H = 520, 420

# 장벽 위치 (시뮬레이션 영역 중앙)
BARRIER_X = SIM_LEFT + SIM_W // 2


def _calc_tunnel_prob(barrier_width: int) -> float:
    """벽 두께에 따른 터널링 확률 — 두꺼울수록 확률 감소.

    기본 두께(12px)에서 10 %, 두께 200px이면 ~0.5 % 수준으로 지수 감쇠.
    """
    return TUNNEL_PROB_BASE * math.exp(-_TUNNEL_DECAY * (barrier_width - BARRIER_WIDTH_DEFAULT))


# ── 파동함수 계산 ────────────────────────────────────
# 1D 구형 포텐셜 장벽 터널링: ψ(x) 시각화용 진폭 계산
#
# 영역 구분:
#   I   (x < barrier_left)  : 입사파 + 반사파  → ψ = e^{ikx} + R·e^{-ikx}
#   II  (barrier 내부)       : 지수감쇠파       → ψ = C·e^{-κx'} + D·e^{κx'}
#   III (x > barrier_right) : 투과파            → ψ = T·e^{ikx}
#
# k  = 입자 파수 (에너지 비례)
# κ  = 장벽 내 감쇠율 (두꺼울수록 급격 감소)
# T  = 투과 계수 (터널링 확률의 진폭)
# R  = 반사 계수

# 파동함수 계산용 물리 파라미터
_WF_K_BASE = 0.15           # 기본 파수 k (입사파 파장 결정)
_WF_KAPPA_SCALE = 0.04      # 장벽 내 감쇠율 스케일


def compute_wavefunction(
    barrier_width: int = BARRIER_WIDTH_DEFAULT,
    n_points: int = 200,
    time_phase: float = 0.0,
) -> tuple[list[float], list[float], list[int]]:
    """1D 포텐셜 장벽에 대한 파동함수 |ψ(x)|² 를 계산.

    Args:
        barrier_width: 장벽 두께 (px 단위, 시뮬레이션 좌표계).
        n_points: 계산할 x 좌표 개수.
        time_phase: 시간 위상 (라디안). 실시간 파동 진행 애니메이션용.

    Returns:
        (xs, amplitudes, regions) 튜플:
        - xs: x 좌표 리스트 (시뮬레이션 영역 내, SIM_LEFT ~ SIM_LEFT+SIM_W)
        - amplitudes: |ψ(x)|² 진폭 (0.0~1.0 정규화)
        - regions: 영역 분류 (0=입사측, 1=장벽내부, 2=투과측)
    """
    half_w = barrier_width / 2.0
    barrier_left = BARRIER_X - half_w
    barrier_right = BARRIER_X + half_w

    k = _WF_K_BASE
    kappa = _WF_KAPPA_SCALE * barrier_width

    # 투과 계수 T (지수감쇠 모델)
    decay = math.exp(-kappa)
    t_coeff = max(decay, 1e-6)
    # 반사 계수 R (|R|² + |T|² = 1 근사)
    r_coeff = math.sqrt(max(1.0 - t_coeff * t_coeff, 0.0))

    xs: list[float] = []
    amplitudes: list[float] = []
    regions: list[int] = []

    dx = SIM_W / max(n_points - 1, 1)
    raw_max = 0.0

    for i in range(n_points):
        x = SIM_LEFT + i * dx
        xs.append(x)

        if x < barrier_left:
            # 영역 I: 입사파 + 반사파 → 정재파 패턴
            rel = x - barrier_left
            # ψ = e^{ikx} + R·e^{-ikx} → |ψ|² = 1 + R² + 2R·cos(2kx + φ)
            psi_sq = 1.0 + r_coeff ** 2 + 2.0 * r_coeff * math.cos(
                2.0 * k * rel + time_phase
            )
            regions.append(0)
        elif x > barrier_right:
            # 영역 III: 투과파 → |ψ|² = T²
            rel = x - barrier_right
            psi_sq = t_coeff ** 2 * (
                1.0 + 0.3 * math.cos(2.0 * k * rel + time_phase)
            )
            regions.append(2)
        else:
            # 영역 II: 장벽 내부 → 지수감쇠
            frac = (x - barrier_left) / max(barrier_width, 1)
            # 왼쪽 경계에서 오른쪽으로 지수감쇠
            psi_sq = math.exp(-2.0 * kappa * frac)
            regions.append(1)

        amplitudes.append(psi_sq)
        if psi_sq > raw_max:
            raw_max = psi_sq

    # 정규화 (0~1)
    if raw_max > 0:
        amplitudes = [a / raw_max for a in amplitudes]

    return xs, amplitudes, regions


# ── 입자 클래스 ──────────────────────────────────────


class QuantumParticle:
    """양자 입자 — 중첩 상태 + 터널링."""

    def __init__(self):
        self.reset()
        self.tunnel_count = 0
        self.reflect_count = 0
        self.total_attempts = 0

    def reset(self):
        """입자를 왼쪽에서 다시 발사."""
        self.x = SIM_LEFT + 40.0
        self.y = SIM_TOP + SIM_H / 2.0
        self.vx = PARTICLE_SPEED
        self.vy = (random.random() - 0.5) * _VY_RANGE  # 약간의 수직 랜덤
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

        # ── CCD(연속 충돌 감지): 이동 전 장벽 교차 판정 ──
        # 프레임 드랍 시 입자가 장벽을 관통하는 것을 방지합니다.
        # 접촉점까지의 정확한 시간을 계산하고, 충돌 후 남은 시간만큼 이동합니다.
        remaining_dt = dt
        if self.tunneled is None and self.vx > 0:
            contact_x = BARRIER_X - barrier_width / 2 - PARTICLE_RADIUS
            if self.x >= contact_x:
                # 이미 접촉 영역 — 즉시 판정
                t_hit = 0.0
            else:
                t_hit = (contact_x - self.x) / self.vx
                if t_hit > dt:
                    t_hit = None  # 이번 프레임에 도달 불가

            if t_hit is not None:
                # 접촉점까지 y 이동 (x는 판정 후 덮어씀)
                self.y += self.vy * t_hit
                remaining_dt = dt - t_hit

                # 충돌 판정
                self.total_attempts += 1
                if random.random() < tunnel_prob:
                    # 터널링 성공! 장벽 반대편으로 좌표 이동 + 속도 부스트
                    self.x = BARRIER_X + barrier_width / 2 + PARTICLE_RADIUS + 5
                    self.vx = abs(self.vx) * speed_boost
                    self.tunneled = True
                    self.tunnel_count += 1
                    self.flash_timer = _TUNNEL_FLASH
                else:
                    # 반사
                    self.vx = -abs(self.vx) * 0.8
                    self.x = BARRIER_X - barrier_width / 2 - PARTICLE_RADIUS - 2
                    self.tunneled = False
                    self.reflect_count += 1
                    self.flash_timer = _REFLECT_FLASH

        # ── 남은 시간만큼 이동 ──
        self.x += self.vx * remaining_dt
        self.y += self.vy * remaining_dt

        # 상하 벽 반사
        if self.y - PARTICLE_RADIUS < SIM_TOP:
            self.y = SIM_TOP + PARTICLE_RADIUS
            self.vy = abs(self.vy)
        elif self.y + PARTICLE_RADIUS > SIM_TOP + SIM_H:
            self.y = SIM_TOP + SIM_H - PARTICLE_RADIUS
            self.vy = -abs(self.vy)

        # 화면 밖으로 나가면 재발사
        if self.x < SIM_LEFT - 20 or self.x > SIM_LEFT + SIM_W + 20:
            self.reset()

        if self.flash_timer > 0:
            self.flash_timer = max(0.0, self.flash_timer - dt)
