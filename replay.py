"""리플레이 기록 시스템 — 시뮬레이션 상태를 프레임 단위로 저장/재생.

사용법:
    from replay import ReplayRecorder, ReplayPlayer

    # 기록
    rec = ReplayRecorder("qubit_chain")
    rec.record_frame({"nodes": [...], "shield": True, ...})
    rec.save()

    # 재생
    player = ReplayPlayer("qubit_chain")
    player.load()
    for frame in player.frames():
        render(frame)
"""

import json
import os
from collections import deque
from datetime import datetime

from logger import get_module_logger

_log = get_module_logger("replay")

REPLAY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replays")


class ReplayRecorder:
    """프레임 단위 상태 기록."""

    def __init__(self, module_name: str, max_frames: int = 3600):
        self.module_name = module_name
        self.max_frames = max_frames
        self._frames: deque[dict] = deque(maxlen=max_frames)
        self._metadata: dict = {
            "module": module_name,
            "start_time": datetime.now().isoformat(),
        }

    def record_frame(self, state: dict):
        """한 프레임의 상태 기록. deque maxlen으로 자동 관리."""
        self._frames.append(state)

    def save(self, extra_metadata: dict | None = None) -> str:
        """기록을 파일로 저장."""
        if not self._frames:
            return ""

        os.makedirs(REPLAY_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"replay_{self.module_name}_{ts}.json"
        filepath = os.path.join(REPLAY_DIR, filename)

        self._metadata["end_time"] = datetime.now().isoformat()
        self._metadata["total_frames"] = len(self._frames)
        if extra_metadata:
            self._metadata.update(extra_metadata)

        data = {
            "metadata": self._metadata,
            "frames": list(self._frames),
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f)
            _log.info("리플레이 저장: %s (%d 프레임)", filepath, len(self._frames))
            return filepath
        except OSError as e:
            _log.error("리플레이 저장 실패: %s", e)
            return ""

    @property
    def frame_count(self) -> int:
        return len(self._frames)


class ReplayPlayer:
    """저장된 리플레이 재생."""

    def __init__(self):
        self._data: dict = {}
        self._index = 0

    def load(self, filepath: str) -> bool:
        """리플레이 파일 로드."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            self._index = 0
            _log.info("리플레이 로드: %s", filepath)
            return True
        except (OSError, json.JSONDecodeError) as e:
            _log.error("리플레이 로드 실패: %s", e)
            return False

    @property
    def metadata(self) -> dict:
        return self._data.get("metadata", {})

    @property
    def total_frames(self) -> int:
        return len(self._data.get("frames", []))

    def get_frame(self, index: int) -> dict:
        """특정 프레임 반환."""
        frames = self._data.get("frames", [])
        if 0 <= index < len(frames):
            return frames[index]
        return {}

    def next_frame(self) -> dict | None:
        """다음 프레임 반환. 끝이면 None."""
        frames = self._data.get("frames", [])
        if self._index < len(frames):
            frame = frames[self._index]
            self._index += 1
            return frame
        return None

    def reset(self):
        """재생 위치 초기화."""
        self._index = 0

    def seek(self, index: int):
        """특정 위치로 이동."""
        self._index = max(0, min(index, self.total_frames))


def list_replays(module_name: str | None = None) -> list[str]:
    """저장된 리플레이 파일 목록."""
    if not os.path.exists(REPLAY_DIR):
        return []
    files = sorted(os.listdir(REPLAY_DIR), reverse=True)
    if module_name:
        files = [f for f in files if f.startswith(f"replay_{module_name}_")]
    return [os.path.join(REPLAY_DIR, f) for f in files if f.endswith(".json")]
