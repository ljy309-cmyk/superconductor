"""가상 액체 질소 냉각기 — 히스테리시스 피드백 루프 시뮬레이션."""

import threading
import time
from dataclasses import dataclass


@dataclass
class CoolerState:
    """냉각기 상태 스냅샷."""

    temperature: float  # 현재 온도 (°C)
    target: float  # 목표 온도 T_c
    cooling_on: bool  # 냉각기 가동 여부
    emergency: bool  # 긴급 재냉각 여부
    running: bool  # 시뮬레이션 실행 여부


class CoolingSystem:
    """히스테리시스 제어 기반 액체 질소 냉각 시뮬레이션.

    Parameters
    ----------
    target_temp : 목표 임계 온도 T_c (기본 -196°C)
    hysteresis  : 히스테리시스 대역폭 (기본 ±2°C)
    emergency_threshold : 긴급 냉각 진입 온도 오프셋 (기본 +6°C)
    cooling_power : 냉각 출력 (°C/tick, 기본 -1.5)
    emergency_power : 긴급 냉각 출력 (°C/tick, 기본 -3.0)
    heat_leak : 외부 열 유입 (°C/tick, 기본 +0.5)
    tick_interval : 시뮬레이션 틱 간격 (초, 기본 0.5)
    """

    def __init__(
        self,
        target_temp: float = -196.0,
        hysteresis: float = 2.0,
        emergency_threshold: float = 6.0,
        cooling_power: float = -1.5,
        emergency_power: float = -3.0,
        heat_leak: float = 0.5,
        tick_interval: float = 0.5,
    ):
        self.target = target_temp
        self.hysteresis = hysteresis
        self.emergency_threshold = emergency_threshold
        self.cooling_power = cooling_power
        self.emergency_power = emergency_power
        self.heat_leak = heat_leak
        self.tick_interval = tick_interval

        # 내부 상태
        self._temperature: float = 25.0  # 시작 온도 (상온)
        self._cooling_on: bool = False
        self._emergency: bool = False
        self._running: bool = False
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._listeners: list = []

    # ── 외부 인터페이스 ──────────────────────────────────

    def add_listener(self, callback):
        """상태 변경 시 호출될 콜백 등록. callback(CoolerState)."""
        self._listeners.append(callback)

    def start(self):
        """시뮬레이션 시작."""
        if self._running:
            return
        self._running = True
        self._temperature = 25.0
        self._cooling_on = False
        self._emergency = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """시뮬레이션 중지."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def get_state(self) -> CoolerState:
        with self._lock:
            return CoolerState(
                temperature=round(self._temperature, 2),
                target=self.target,
                cooling_on=self._cooling_on,
                emergency=self._emergency,
                running=self._running,
            )

    # ── 시뮬레이션 루프 ──────────────────────────────────

    def _run_loop(self):
        while self._running:
            with self._lock:
                self._tick()
            state = self.get_state()
            for cb in self._listeners:
                cb(state)
            time.sleep(self.tick_interval)

    def _tick(self):
        # 외부 열 유입 (항상 발생)
        self._temperature += self.heat_leak

        # 히스테리시스 제어
        upper = self.target + self.hysteresis  # -194°C
        emergency_line = self.target + self.emergency_threshold  # -190°C

        # 긴급 냉각 판단
        if self._temperature >= emergency_line:
            self._emergency = True
            self._cooling_on = True
        elif self._temperature <= self.target:
            self._emergency = False
            self._cooling_on = False
        elif self._temperature >= upper and not self._cooling_on:
            self._cooling_on = True

        # 냉각 적용
        if self._cooling_on:
            power = self.emergency_power if self._emergency else self.cooling_power
            self._temperature += power  # power는 음수
