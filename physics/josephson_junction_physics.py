"""조셉슨 접합(Josephson Junction) 물리 엔진 — 렌더링 없는 순수 물리 로직.

조셉슨 효과의 핵심 개념을 시뮬레이션합니다:
  - DC 조셉슨 효과: I = Ic × sin(φ)  (전압 없이 초전류)
  - AC 조셉슨 효과: dφ/dt = 2eV/ℏ  (전압 인가 시 위상 진동)
  - RCSJ 모델: 저항-캐패시턴스 분로 접합
  - 워시보드 퍼텐셜(Washboard Potential)

사용법:
    from physics.josephson_junction_physics import JosephsonJunction
    jj = JosephsonJunction()
    jj.update(dt=1/60)
"""

import math

from config_loader import cfg

# ── 물리 상수 ──────────────────────────────────────
HBAR = 1.054571817e-34  # ℏ (J·s)
ELECTRON_CHARGE = 1.602176634e-19  # e (C)
FLUX_QUANTUM = 2.067833848e-15  # Φ₀ = h/(2e) (Wb)

# ── 시뮬레이션 파라미터 (config.json에서 로드) ──────
IC_DEFAULT = cfg("josephson_junction", "ic_default", 1.0)  # 정규화 임계 전류
BIAS_MAX = cfg("josephson_junction", "bias_max", 3.0)  # 최대 바이어스 전류
R_NORMAL = cfg("josephson_junction", "r_normal", 1.0)  # 정상 저항
CAPACITANCE = cfg("josephson_junction", "capacitance", 0.5)  # McCumber 파라미터용
PHASE_DAMPING = cfg("josephson_junction", "phase_damping", 0.3)  # 위상 감쇠 계수
TIME_SCALE = cfg("josephson_junction", "time_scale", 5.0)  # 시간 가속 배율


def josephson_current(phi: float, ic: float = IC_DEFAULT) -> float:
    """DC 조셉슨 전류: I = Ic × sin(φ)."""
    return ic * math.sin(phi)


def ac_frequency(voltage: float) -> float:
    """AC 조셉슨 주파수: f = 2eV/h (정규화 단위에서 2πV)."""
    return 2.0 * math.pi * voltage


def washboard_potential(phi: float, bias: float, ic: float = IC_DEFAULT) -> float:
    """워시보드 퍼텐셜: U(φ) = -Ic × cos(φ) - (I_bias × φ)/(2π).

    bias < Ic: 포텐셜에 우물(국소 최소)이 존재 → 위상 갇힘
    bias > Ic: 우물 소멸 → 위상 미끄러짐 (전압 발생)
    """
    return -ic * math.cos(phi) - (bias / (2.0 * math.pi)) * phi


def iv_curve_point(bias: float, ic: float = IC_DEFAULT, r_n: float = R_NORMAL) -> float:
    """I-V 특성 곡선의 한 점 (전압 반환).

    |I_bias| <= Ic: V = 0 (초전류 영역)
    |I_bias| > Ic: V = R_n × sqrt(I² - Ic²) (정상 전류 영역, 근사)
    """
    if abs(bias) <= ic:
        return 0.0
    sign = 1 if bias > 0 else -1
    return sign * r_n * math.sqrt(bias * bias - ic * ic)


class JosephsonJunction:
    """단일 조셉슨 접합 — RCSJ 모델 시뮬레이션.

    정규화 단위를 사용합니다:
    - 전류: Ic 기준 (I/Ic)
    - 시간: ℏ/(2eIcRn) 기준
    - 전압: IcRn 기준
    """

    def __init__(
        self,
        ic: float = IC_DEFAULT,
        r_normal: float = R_NORMAL,
        capacitance: float = CAPACITANCE,
        damping: float = PHASE_DAMPING,
    ):
        self.ic = ic
        self.r_normal = r_normal
        self.capacitance = capacitance
        self.damping = damping

        self.phi = 0.0  # 위상 차이
        self.dphi = 0.0  # 위상 시간 미분 (∝ 전압)
        self.bias_current = 0.0  # 외부 바이어스 전류
        self.t = 0.0

        # 히스토리 (I-V 곡선, 위상 궤적)
        self.phi_history: list[float] = []
        self.voltage_history: list[float] = []
        self.current_history: list[float] = []
        self._history_max = 300

    @property
    def supercurrent(self) -> float:
        """현재 조셉슨 초전류."""
        return josephson_current(self.phi, self.ic)

    @property
    def voltage(self) -> float:
        """접합 양단 전압 (∝ dφ/dt)."""
        return self.dphi

    @property
    def is_zero_voltage(self) -> bool:
        """제로 전압 상태 (DC 조셉슨 효과)인지."""
        return abs(self.voltage) < 0.05

    @property
    def power(self) -> float:
        """접합에서의 소산 전력."""
        return self.voltage * self.bias_current

    def set_bias(self, bias: float):
        """바이어스 전류 설정."""
        self.bias_current = max(-BIAS_MAX, min(BIAS_MAX, bias))

    def update(self, dt: float):
        """1프레임 물리 업데이트 — RCSJ 모델.

        C × d²φ/dt² + (1/R) × dφ/dt + Ic × sin(φ) = I_bias

        정규화하면:
        βc × φ'' + φ' + sin(φ) = I_bias/Ic

        여기서 βc = McCumber parameter = 2πIcR²C/Φ₀
        """
        dt_scaled = dt * TIME_SCALE
        beta_c = self.capacitance  # McCumber parameter (정규화)
        i_norm = self.bias_current / self.ic if self.ic > 0 else 0

        # Velocity Verlet 적분
        ddphi = (i_norm - math.sin(self.phi) - self.damping * self.dphi) / max(beta_c, 0.01)
        self.dphi += ddphi * dt_scaled
        self.phi += self.dphi * dt_scaled
        self.t += dt_scaled

        # 히스토리 기록
        self.phi_history.append(self.phi)
        self.voltage_history.append(self.voltage)
        self.current_history.append(self.supercurrent)
        if len(self.phi_history) > self._history_max:
            self.phi_history.pop(0)
            self.voltage_history.pop(0)
            self.current_history.pop(0)

    def reset(self):
        """상태 초기화."""
        self.phi = 0.0
        self.dphi = 0.0
        self.t = 0.0
        self.phi_history.clear()
        self.voltage_history.clear()
        self.current_history.clear()
