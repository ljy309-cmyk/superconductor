"""시뮬레이션 속도 조절 — 게임 물리 dt에 배율 적용.

사용법:
    from sim_speed import get_sim_speed, apply_speed
    dt = apply_speed(raw_dt)  # raw_dt * speed_multiplier
"""

from config_loader import cfg
from logger import get_module_logger

_log = get_module_logger("sim_speed")

_speed: float = cfg("simulation", "speed", 1.0)
_SPEED_MIN = 0.25
_SPEED_MAX = 4.0
_SPEED_LEVELS = [0.25, 0.5, 1.0, 2.0, 4.0]


def get_sim_speed() -> float:
    """현재 시뮬레이션 속도 배율."""
    return _speed


def set_sim_speed(speed: float):
    """시뮬레이션 속도 설정 (0.25 ~ 4.0)."""
    global _speed
    _speed = max(_SPEED_MIN, min(_SPEED_MAX, speed))


def cycle_sim_speed(direction: int = 1):
    """속도를 한 단계 올리거나(+1) 내린다(-1). 현재 속도 반환."""
    global _speed
    try:
        idx = _SPEED_LEVELS.index(_speed)
    except ValueError:
        idx = 2  # 1.0x
    new_idx = max(0, min(idx + direction, len(_SPEED_LEVELS) - 1))
    _speed = _SPEED_LEVELS[new_idx]
    return _speed


def apply_speed(dt: float) -> float:
    """raw dt에 속도 배율을 적용."""
    return dt * _speed


def speed_label() -> str:
    """현재 속도 표시 문자열."""
    if _speed == int(_speed):
        return f"{int(_speed)}x"
    return f"{_speed}x"
