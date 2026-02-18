"""사운드 매니저 — 모든 게임 모듈의 효과음을 중앙 관리.

사용법:
    from sound_manager import SoundManager
    snd = SoundManager()
    snd.play("collapse")
    snd.play("shield_on")
"""

import array
import math

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore[assignment]

from logger import get_module_logger

_log = get_module_logger("sound")


def _sine_wave(freq: float, duration_ms: int, volume: float = 0.3,
               sample_rate: int = 22050):
    """사인파 사운드 생성."""
    n = int(sample_rate * duration_ms / 1000)
    buf = array.array("h", [0] * n)
    amp = int(32767 * volume)
    for i in range(n):
        t = i / sample_rate
        env = min(i / (n * 0.1 + 1), 1.0, (n - i) / (n * 0.1 + 1))
        buf[i] = int(amp * env * math.sin(2 * math.pi * freq * t))
    return pygame.mixer.Sound(buffer=buf)


def _dual_tone(f1: float, f2: float, duration_ms: int, volume: float = 0.25,
               sample_rate: int = 22050):
    """두 주파수 혼합 사운드."""
    n = int(sample_rate * duration_ms / 1000)
    buf = array.array("h", [0] * n)
    amp = int(32767 * volume)
    for i in range(n):
        t = i / sample_rate
        env = min(i / (n * 0.1 + 1), 1.0, (n - i) / (n * 0.15 + 1))
        val = 0.6 * math.sin(2 * math.pi * f1 * t) + 0.4 * math.sin(2 * math.pi * f2 * t)
        buf[i] = int(amp * env * val)
    return pygame.mixer.Sound(buffer=buf)


def _descending(start_freq: float, end_freq: float, duration_ms: int,
                volume: float = 0.25, sample_rate: int = 22050):
    """하강 톤 (경고/붕괴)."""
    n = int(sample_rate * duration_ms / 1000)
    buf = array.array("h", [0] * n)
    amp = int(32767 * volume)
    for i in range(n):
        t = i / sample_rate
        ratio = i / n
        freq = start_freq + (end_freq - start_freq) * ratio
        env = min(i / (n * 0.05 + 1), 1.0, (n - i) / (n * 0.2 + 1))
        buf[i] = int(amp * env * math.sin(2 * math.pi * freq * t))
    return pygame.mixer.Sound(buffer=buf)


class SoundManager:
    """효과음 관리자."""

    def __init__(self):
        self.enabled = True
        self._sounds: dict = {}
        self._initialized = False
        self._volume = 0.7  # 0.0 ~ 1.0

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, val: float):
        self._volume = max(0.0, min(1.0, round(val, 2)))
        # 이미 생성된 사운드에 볼륨 적용
        for snd in self._sounds.values():
            snd.set_volume(self._volume)

    def volume_up(self, step: float = 0.1):
        """볼륨 한 단계 증가."""
        self.volume = self._volume + step

    def volume_down(self, step: float = 0.1):
        """볼륨 한 단계 감소."""
        self.volume = self._volume - step

    def init(self):
        """사운드 시스템 초기화. pygame.mixer.init() 이후 호출."""
        if self._initialized:
            return
        if pygame is None:
            self.enabled = False
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self._build_sounds()
            # 초기 볼륨 적용
            for snd in self._sounds.values():
                snd.set_volume(self._volume)
            self._initialized = True
        except (pygame.error, OSError, TypeError) as e:
            _log.warning("사운드 초기화 실패: %s", e)
            self.enabled = False

    def _build_sounds(self):
        """모든 효과음 생성."""
        self._sounds = {
            # 큐비트/QEC
            "collapse": _descending(800, 200, 150),
            "shield_on": _dual_tone(660, 880, 120),
            "shield_off": _descending(440, 220, 100),
            "heal": _dual_tone(523, 659, 100),
            "error_correct": _sine_wave(1046, 60, 0.2),

            # 터널링
            "tunnel_success": _dual_tone(880, 1320, 100),
            "tunnel_reflect": _sine_wave(220, 80, 0.2),

            # BB84
            "eve_detected": _descending(1000, 400, 200),
            "channel_shutdown": _descending(600, 150, 300),
            "channel_open": _dual_tone(440, 660, 120),
            "decoy_trap": _sine_wave(1200, 60, 0.15),

            # SQUID (기존 beep은 squid_mines에서 자체 관리)
            "mine_found": _dual_tone(880, 1100, 150),
            "wrong_mark": _descending(400, 200, 120),
            "victory": _dual_tone(523, 784, 300),

            # 플럭스 피닝
            "levitate": _sine_wave(440, 100, 0.15),
            "fall": _descending(300, 80, 200),

            # 공용
            "preset_change": _sine_wave(660, 50, 0.15),
            "achievement": _dual_tone(523, 1046, 250),
        }

    def play(self, name: str):
        """효과음 재생."""
        if not self.enabled or not self._initialized:
            return
        sound = self._sounds.get(name)
        if sound:
            sound.play()

    def toggle(self) -> bool:
        """사운드 ON/OFF 토글. 현재 상태 반환."""
        self.enabled = not self.enabled
        return self.enabled

    def handle_key(self, key) -> bool:
        """공통 사운드 키 처리. 처리했으면 True 반환.

        M: 뮤트 토글, +/=: 볼륨 업, -: 볼륨 다운
        """
        if pygame is None:
            return False
        if key == pygame.K_m:
            self.toggle()
            return True
        if key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.volume_up()
            return True
        if key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.volume_down()
            return True
        return False

    def quit(self):
        """정리."""
        self._sounds.clear()
        self._initialized = False


# 전역 싱글턴
_instance: SoundManager | None = None


def get_sound_manager() -> SoundManager:
    """전역 SoundManager 반환."""
    global _instance
    if _instance is None:
        _instance = SoundManager()
    return _instance
