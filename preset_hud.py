"""Pygame 프리셋 HUD — 게임 내에서 1/2/3 키로 난이도 전환.

모든 Pygame 게임 모듈에서 공유하는 프리셋 표시 + 적용 헬퍼.

사용법:
    from preset_hud import PresetHUD
    hud = PresetHUD("qubit_chain", slider_map)

    # 이벤트 루프:
    hud.handle_event(event)

    # 렌더링:
    hud.draw(screen, font)
"""

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore[assignment]

from presets import get_preset, save_profile, load_profile, list_profiles
from logger import get_module_logger

_log = get_module_logger("preset_hud")

# 프리셋 키 매핑 (pygame이 없으면 빈 dict)
if pygame:
    _PRESET_KEYS = {
        pygame.K_1: "easy",
        pygame.K_2: "normal",
        pygame.K_3: "hard",
    }
else:
    _PRESET_KEYS = {}

# 프리셋별 표시 색상
_PRESET_COLORS = {
    "easy": (166, 227, 161),     # 초록
    "normal": (249, 226, 175),   # 노랑
    "hard": (243, 139, 168),     # 빨강
    "custom": (137, 180, 250),   # 파랑
}


class PresetHUD:
    """프리셋 HUD — 현재 난이도 표시 + 1/2/3 키 전환.

    Args:
        module_name: 모듈 이름 (예: "qubit_chain", "bb84")
        slider_map: {("section", "key"): slider_obj, ...}
    """

    def __init__(self, module_name: str, slider_map: dict):
        self.module_name = module_name
        self.slider_map = slider_map
        self.current = "normal"
        self.flash_timer = 0.0
        self.notification = ""

    def handle_event(self, event: pygame.event.Event) -> bool:
        """키 이벤트 처리. 프리셋 변경 시 True 반환."""
        if event.type != pygame.KEYDOWN:
            return False

        # 1/2/3 키 → 프리셋 적용
        preset_name = _PRESET_KEYS.get(event.key)
        if preset_name:
            self._apply_preset(preset_name)
            return True

        # F5 키 → 현재 슬라이더 값을 프로파일로 저장
        if event.key == pygame.K_F5:
            self._save_current()
            return True

        # F9 키 → 프로파일 불러오기
        if event.key == pygame.K_F9:
            self._load_last_profile()
            return True

        return False

    def _apply_preset(self, name: str):
        """프리셋을 슬라이더에 적용."""
        preset = get_preset(name)
        if not preset:
            return

        for (sec, key), slider in self.slider_map.items():
            sec_data = preset.get(sec, {})
            if key in sec_data:
                slider.value = sec_data[key]

        self.current = name
        self.notification = f"Preset: {name.upper()}"
        self.flash_timer = 2.0
        _log.info("프리셋 '%s' 적용: %s", name, self.module_name)

    def _save_current(self):
        """현재 슬라이더 값을 프로파일로 저장."""
        values = {}
        for (sec, key), slider in self.slider_map.items():
            values[f"{sec}.{key}"] = slider.value

        profile_name = f"{self.module_name}_custom"
        save_profile(profile_name, values)
        self.current = "custom"
        self.notification = f"Profile saved: {profile_name}"
        self.flash_timer = 2.0

    def _load_last_profile(self):
        """마지막 저장 프로파일 불러오기."""
        profile_name = f"{self.module_name}_custom"
        data = load_profile(profile_name)
        if not data:
            self.notification = "No saved profile"
            self.flash_timer = 1.5
            return

        for (sec, key), slider in self.slider_map.items():
            compound_key = f"{sec}.{key}"
            if compound_key in data:
                slider.value = data[compound_key]

        self.current = "custom"
        self.notification = f"Profile loaded: {profile_name}"
        self.flash_timer = 2.0

    def update(self, dt: float):
        """타이머 업데이트."""
        if self.flash_timer > 0:
            self.flash_timer -= dt

    def draw(self, screen: pygame.Surface, font: pygame.font.Font,
             x: int = 10, y: int = 10):
        """프리셋 HUD 렌더링."""
        color = _PRESET_COLORS.get(self.current, (205, 214, 244))

        # 현재 프리셋 뱃지
        badge = f"[{self.current.upper()}]"
        badge_surf = font.render(badge, True, color)
        screen.blit(badge_surf, (x, y))

        # 단축키 안내
        hint = "1:Easy 2:Normal 3:Hard"
        hint_surf = font.render(hint, True, (88, 91, 112))
        screen.blit(hint_surf, (x + badge_surf.get_width() + 8, y))

        # 알림 메시지 (페이드 아웃)
        if self.flash_timer > 0:
            alpha = min(255, int(255 * self.flash_timer / 0.5))
            notif_surf = font.render(self.notification, True, color)
            screen.blit(notif_surf, (x, y + 16))
