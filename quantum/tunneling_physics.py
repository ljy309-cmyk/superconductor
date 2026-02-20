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
BLOCH_LERP_SPEED = cfg("tunneling", "bloch_lerp_speed", 8.0)

# ── 영역 레이아웃 ────────────────────────────────────
# 왼쪽: 터널링 시뮬레이션 | 오른쪽: 블로흐 구
SIM_LEFT, SIM_TOP = 30, 70
SIM_W, SIM_H = 520, 420

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


def _calc_tunnel_prob(barrier_width: int) -> float:
    """벽 두께에 따른 터널링 확률 — 두꺼울수록 확률 감소.

    기본 두께(12px)에서 10 %, 두께 200px이면 ~0.5 % 수준으로 지수 감쇠.
    """
    return TUNNEL_PROB_BASE * math.exp(-_TUNNEL_DECAY * (barrier_width - BARRIER_WIDTH_DEFAULT))


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

        # 화면 밖으로 나가면 재발사
        if self.x < SIM_LEFT - 20 or self.x > SIM_LEFT + SIM_W + 20:
            self.reset()

        if self.flash_timer > 0:
            self.flash_timer -= dt
