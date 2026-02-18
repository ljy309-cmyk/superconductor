"""SCADA 보안 시나리오 엔진 — MITM 공격 + BB84 양자 방어.

순수 Python 로직 (Pygame 불필요, 단위 테스트 가능):
  - 온도 센서 시뮬레이션 (정상 + 노이즈)
  - MITM 공격: 센서값 조작 (표시값과 실제값 분리)
  - BB84 기반 인증: 양자 키 교환으로 통신 무결성 검증
  - 공격 탐지 → 경보 → 복구 시나리오

시나리오 흐름:
  Phase 0: Normal — 정상 모니터링
  Phase 1: Attack — MITM이 센서 데이터 조작 (표시 온도 정상, 실제 온도 상승)
  Phase 2: Detection — BB84 QBER 상승으로 공격 탐지
  Phase 3: Protected — QKD 인증 적용, 공격자 차단
"""

import math
import random
from dataclasses import dataclass, field

from config_loader import cfg

# ── 설정 ─────────────────────────────────────────────

TARGET_TEMP = cfg("scada_security", "target_temp", -196.0)
HEAT_LEAK = cfg("scada_security", "heat_leak", 0.3)
COOLING_POWER = cfg("scada_security", "cooling_power", -0.8)
SENSOR_NOISE = cfg("scada_security", "sensor_noise", 0.2)
MITM_SPOOF_OFFSET = cfg("scada_security", "mitm_spoof_offset", 8.0)
MITM_RAMP_SPEED = cfg("scada_security", "mitm_ramp_speed", 0.5)
QBER_NORMAL = cfg("scada_security", "qber_normal", 0.03)
QBER_ATTACK = cfg("scada_security", "qber_attack", 0.28)
QBER_DETECT_THRESHOLD = cfg("scada_security", "qber_detect_threshold", 0.11)
CRITICAL_TEMP = cfg("scada_security", "critical_temp", -188.0)
RECOVERY_COOLING = cfg("scada_security", "recovery_cooling", -2.0)

# ── 위상 상수 ────────────────────────────────────────

PHASE_NORMAL = 0
PHASE_ATTACK = 1
PHASE_DETECTED = 2
PHASE_PROTECTED = 3

PHASE_NAMES = ["NORMAL", "ATTACK", "DETECTED", "PROTECTED"]


# ── BB84 미니 프로토콜 ────────────────────────────────

@dataclass
class QKDChannel:
    """간소화된 BB84 키 교환 채널."""

    qber: float = 0.0
    qber_history: list[float] = field(default_factory=list)
    keys_exchanged: int = 0
    keys_compromised: int = 0
    authenticated: bool = False
    detection_triggered: bool = False

    # 내부 상태
    _exchange_timer: float = 0.0
    _exchange_interval: float = 0.8

    def update(self, dt: float, under_attack: bool):
        """BB84 키 교환 주기 업데이트."""
        self._exchange_timer += dt
        if self._exchange_timer < self._exchange_interval:
            return

        self._exchange_timer = 0.0
        self.keys_exchanged += 1

        # QBER 시뮬레이션
        if under_attack:
            # 공격 시 Eve가 기저 불일치로 에러 주입
            raw_qber = QBER_ATTACK + random.gauss(0, 0.04)
            self.keys_compromised += 1
        else:
            raw_qber = QBER_NORMAL + random.gauss(0, 0.01)

        raw_qber = max(0.0, min(1.0, raw_qber))

        # 이동 평균
        self.qber_history.append(raw_qber)
        if len(self.qber_history) > 20:
            self.qber_history.pop(0)
        self.qber = sum(self.qber_history) / len(self.qber_history)

        # 탐지 판정
        if (self.qber > QBER_DETECT_THRESHOLD
                and len(self.qber_history) >= 5
                and not self.detection_triggered):
            self.detection_triggered = True

    def reset(self):
        self.qber = 0.0
        self.qber_history.clear()
        self.keys_exchanged = 0
        self.keys_compromised = 0
        self.authenticated = False
        self.detection_triggered = False
        self._exchange_timer = 0.0


# ── 센서 시스템 ──────────────────────────────────────

@dataclass
class SensorReading:
    """센서 읽기 스냅샷."""
    real_temp: float        # 실제 온도
    displayed_temp: float   # HMI에 표시되는 온도 (공격 시 조작됨)
    spoofed: bool           # 조작 여부
    noise: float            # 센서 노이즈


def sensor_read(real_temp: float, under_attack: bool,
                attack_intensity: float) -> SensorReading:
    """센서 판독 시뮬레이션.

    Args:
        real_temp: 실제 물리적 온도
        under_attack: MITM 공격 여부
        attack_intensity: 0.0~1.0 공격 강도 (ramp-up)
    """
    noise = random.gauss(0, SENSOR_NOISE)

    if under_attack and attack_intensity > 0.01:
        # MITM: 실제 온도 대신 조작된 값 표시
        # 실제로는 온도가 올라가지만, 공격자가 정상값을 보여줌
        fake_temp = TARGET_TEMP + noise * 0.5  # 안정적인 척
        displayed = fake_temp
        spoofed = True
    else:
        displayed = real_temp + noise
        spoofed = False

    return SensorReading(
        real_temp=real_temp,
        displayed_temp=displayed,
        spoofed=spoofed,
        noise=noise,
    )


# ── 메인 시나리오 상태 ───────────────────────────────

@dataclass
class ScadaSecurityState:
    """SCADA 보안 시나리오 전체 상태."""

    phase: int = PHASE_NORMAL
    t: float = 0.0

    # 물리 상태
    real_temp: float = -196.0
    displayed_temp: float = -196.0
    cooling_on: bool = True
    emergency: bool = False

    # MITM 공격
    attack_active: bool = False
    attack_intensity: float = 0.0  # 0.0~1.0 서서히 증가
    attack_start_time: float = 0.0
    attack_duration: float = 0.0  # 공격 지속 시간

    # BB84 채널
    qkd: QKDChannel = field(default_factory=QKDChannel)
    qkd_enabled: bool = True

    # 센서 히스토리
    real_temp_history: list[float] = field(default_factory=list)
    displayed_temp_history: list[float] = field(default_factory=list)
    qber_plot_history: list[float] = field(default_factory=list)

    # 이벤트 로그
    event_log: list[str] = field(default_factory=list)

    # 통계
    attacks_detected: int = 0
    attacks_blocked: int = 0
    max_real_temp: float = -196.0
    time_under_attack: float = 0.0
    false_alarms: int = 0

    # 자동 시나리오 타이머
    scenario_timer: float = 0.0
    auto_scenario: bool = True
    _next_attack_time: float = 8.0  # 첫 공격까지 대기

    def log(self, msg: str):
        self.event_log.append(msg)
        if len(self.event_log) > 12:
            self.event_log.pop(0)


def update_scenario(gs: ScadaSecurityState, dt: float):
    """시나리오 물리/로직 업데이트 (1프레임)."""
    gs.t += dt
    gs.scenario_timer += dt

    # ── 자동 시나리오 (공격 발생/종료) ──
    if gs.auto_scenario:
        _auto_scenario_logic(gs, dt)

    # ── 물리: 온도 업데이트 ──
    _update_temperature(gs, dt)

    # ── MITM 공격 강도 램프 ──
    if gs.attack_active:
        gs.attack_intensity = min(1.0,
                                  gs.attack_intensity + MITM_RAMP_SPEED * dt)
        gs.attack_duration += dt
        gs.time_under_attack += dt
    else:
        gs.attack_intensity = max(0.0,
                                  gs.attack_intensity - MITM_RAMP_SPEED * 2 * dt)

    # ── 센서 판독 ──
    reading = sensor_read(gs.real_temp, gs.attack_active, gs.attack_intensity)
    gs.displayed_temp = reading.displayed_temp

    # 히스토리 기록
    gs.real_temp_history.append(gs.real_temp)
    gs.displayed_temp_history.append(gs.displayed_temp)
    if len(gs.real_temp_history) > 200:
        gs.real_temp_history.pop(0)
        gs.displayed_temp_history.pop(0)

    # ── BB84 채널 업데이트 ──
    if gs.qkd_enabled:
        gs.qkd.update(dt, gs.attack_active)
        gs.qber_plot_history.append(gs.qkd.qber)
        if len(gs.qber_plot_history) > 200:
            gs.qber_plot_history.pop(0)

        # 탐지 판정 → Phase 전환
        if gs.qkd.detection_triggered and gs.phase == PHASE_ATTACK:
            gs.phase = PHASE_DETECTED
            gs.attacks_detected += 1
            gs.log("[QKD] QBER threshold exceeded — attack detected!")

    # ── 위험 온도 체크 ──
    if gs.real_temp > CRITICAL_TEMP and not gs.emergency:
        gs.emergency = True
        gs.log(f"[ALARM] Critical temp reached: {gs.real_temp:.1f}°C!")

    gs.max_real_temp = max(gs.max_real_temp, gs.real_temp)


def _update_temperature(gs: ScadaSecurityState, dt: float):
    """온도 물리 업데이트."""
    # 냉각 시스템
    if gs.cooling_on:
        if gs.emergency:
            cool = RECOVERY_COOLING * dt
        else:
            cool = COOLING_POWER * dt
    else:
        cool = 0.0

    # 열 누출
    heat = HEAT_LEAK * dt

    # MITM 공격 시 냉각 시스템 방해 (공격자가 냉각 명령도 조작)
    if gs.attack_active and gs.attack_intensity > 0.3:
        # 공격 강도에 비례하여 냉각 효율 감소
        sabotage = gs.attack_intensity * 0.6
        cool *= (1.0 - sabotage)
        heat += gs.attack_intensity * 0.4 * dt  # 추가 열 유입

    gs.real_temp += heat + cool

    # 클램프
    gs.real_temp = max(-210.0, min(25.0, gs.real_temp))

    # 긴급 냉각 해제
    if gs.emergency and gs.real_temp <= TARGET_TEMP:
        gs.emergency = False


def _auto_scenario_logic(gs: ScadaSecurityState, dt: float):
    """자동 시나리오: 공격 시작/탐지/방어 사이클."""

    if gs.phase == PHASE_NORMAL:
        if gs.scenario_timer >= gs._next_attack_time:
            # 공격 시작
            gs.phase = PHASE_ATTACK
            gs.attack_active = True
            gs.attack_start_time = gs.t
            gs.attack_intensity = 0.0
            gs.qkd.detection_triggered = False
            gs.log("[MITM] Attacker infiltrated sensor channel!")
            gs.log("[MITM] Spoofing temperature readings...")

    elif gs.phase == PHASE_DETECTED:
        # 탐지 후 2초 대기 → 방어 모드
        if gs.attack_duration > 2.0 and gs.qkd.detection_triggered:
            gs.phase = PHASE_PROTECTED
            gs.attack_active = False
            gs.attacks_blocked += 1
            gs.qkd.authenticated = True
            gs.log("[QKD] Quantum-authenticated channel established!")
            gs.log("[SCADA] Attacker blocked — switching to verified sensor")

    elif gs.phase == PHASE_PROTECTED:
        # 보호 모드 5초 후 → 정상 복귀
        if not gs.attack_active and gs.attack_intensity < 0.01:
            gs.phase = PHASE_NORMAL
            gs.scenario_timer = 0.0
            gs._next_attack_time = random.uniform(8.0, 15.0)
            gs.qkd.reset()
            gs.attack_duration = 0.0
            gs.log("[SYSTEM] System restored — monitoring resumed")


def trigger_attack(gs: ScadaSecurityState):
    """수동 공격 트리거."""
    if gs.phase == PHASE_NORMAL:
        gs.phase = PHASE_ATTACK
        gs.attack_active = True
        gs.attack_start_time = gs.t
        gs.attack_intensity = 0.0
        gs.attack_duration = 0.0
        gs.qkd.detection_triggered = False
        gs.log("[MITM] Manual attack triggered!")


def trigger_defense(gs: ScadaSecurityState):
    """수동 방어 트리거."""
    if gs.phase in (PHASE_ATTACK, PHASE_DETECTED):
        gs.phase = PHASE_PROTECTED
        gs.attack_active = False
        gs.attacks_blocked += 1
        gs.qkd.authenticated = True
        gs.log("[QKD] Manual defense activated!")
        gs.log("[SCADA] Attacker blocked!")


def reset_scenario(gs: ScadaSecurityState):
    """시나리오 전체 리셋."""
    gs.phase = PHASE_NORMAL
    gs.t = 0.0
    gs.real_temp = TARGET_TEMP
    gs.displayed_temp = TARGET_TEMP
    gs.cooling_on = True
    gs.emergency = False
    gs.attack_active = False
    gs.attack_intensity = 0.0
    gs.attack_duration = 0.0
    gs.qkd.reset()
    gs.real_temp_history.clear()
    gs.displayed_temp_history.clear()
    gs.qber_plot_history.clear()
    gs.event_log.clear()
    gs.attacks_detected = 0
    gs.attacks_blocked = 0
    gs.max_real_temp = TARGET_TEMP
    gs.time_under_attack = 0.0
    gs.scenario_timer = 0.0
    gs._next_attack_time = 8.0
    gs.log("[SYSTEM] SCADA Security Scenario initialized")
