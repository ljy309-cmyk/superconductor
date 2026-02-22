"""성능 모니터링 — FPS, 프레임 드롭, 평균/최소 FPS 추적.

사용법:
    from perf_monitor import PerfMonitor
    perf = PerfMonitor(target_fps=60)

    while running:
        dt = clock.tick(60) / 1000.0
        perf.tick(dt)
        # 렌더링 ...
        perf.draw_overlay(screen, font)  # 선택적 HUD 표시
"""

import time
from collections import deque

from logger import get_module_logger

_log = get_module_logger("perf_monitor")


class PerfMonitor:
    """프레임 성능 추적기."""

    def __init__(self, target_fps: int = 60, window: int = 120):
        self.target_fps = target_fps
        self._target_dt = 1.0 / target_fps if target_fps > 0 else 0.016
        self._window = window
        self._dt_history: deque[float] = deque(maxlen=window)
        self._frame_count = 0
        self._drop_count = 0
        self._start_time = time.time()
        self._drop_threshold = self._target_dt * 1.5  # 50% 초과 시 드롭

    def tick(self, dt: float):
        """매 프레임 호출. dt는 초 단위."""
        self._dt_history.append(dt)
        self._frame_count += 1
        if dt > self._drop_threshold:
            self._drop_count += 1

    @property
    def current_fps(self) -> float:
        """현재 FPS (최근 프레임 기준)."""
        if not self._dt_history:
            return 0.0
        last = self._dt_history[-1]
        return 1.0 / last if last > 0 else 0.0

    @property
    def avg_fps(self) -> float:
        """윈도우 평균 FPS."""
        if not self._dt_history:
            return 0.0
        avg_dt = sum(self._dt_history) / len(self._dt_history)
        return 1.0 / avg_dt if avg_dt > 0 else 0.0

    @property
    def min_fps(self) -> float:
        """윈도우 내 최소 FPS (최대 dt 기준)."""
        if not self._dt_history:
            return 0.0
        max_dt = max(self._dt_history)
        return 1.0 / max_dt if max_dt > 0 else 0.0

    @property
    def frame_drops(self) -> int:
        """총 프레임 드롭 수."""
        return self._drop_count

    @property
    def total_frames(self) -> int:
        return self._frame_count

    @property
    def uptime(self) -> float:
        """실행 시간 (초)."""
        return time.time() - self._start_time

    def summary(self) -> dict:
        """성능 요약 반환."""
        return {
            "total_frames": self._frame_count,
            "frame_drops": self._drop_count,
            "drop_rate": round(self._drop_count / max(self._frame_count, 1) * 100, 1),
            "avg_fps": round(self.avg_fps, 1),
            "min_fps": round(self.min_fps, 1),
            "uptime": round(self.uptime, 1),
        }

    def log_summary(self):
        """성능 요약을 로그에 기록."""
        s = self.summary()
        _log.info(
            "성능: %d 프레임, 드롭 %d (%.1f%%), 평균 %.1f FPS, 최소 %.1f FPS, %.1fs",
            s["total_frames"],
            s["frame_drops"],
            s["drop_rate"],
            s["avg_fps"],
            s["min_fps"],
            s["uptime"],
        )

    def draw_overlay(self, screen, font, x: int = 4, y: int = 4):  # pragma: no cover
        """성능 HUD 오버레이 (Pygame)."""
        try:
            import pygame
        except ImportError:
            return
        fps = self.current_fps
        avg = self.avg_fps
        color = (
            (166, 227, 161)
            if fps >= self.target_fps * 0.9
            else ((249, 226, 175) if fps >= self.target_fps * 0.5 else (243, 139, 168))
        )
        text = f"FPS: {fps:.0f}  AVG: {avg:.0f}  DROP: {self._drop_count}"
        surf = font.render(text, True, color)
        screen.blit(surf, (x, y))
