"""난이도 프리셋 & 프로파일 저장/불러오기.

사용법:
    from presets import get_preset, list_presets, save_profile, load_profile

    preset = get_preset("easy")
    # preset["qubit_chain"]["noise_rate_base"] → 1.5
"""

import json
import os

from config_loader import section
from logger import get_module_logger

_log = get_module_logger("presets")

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")


def _clamp_value(sec: str, key: str, value):
    """config 스키마 범위로 값을 클램핑. 범위 초과 시 경고 로그."""
    from config_loader import _SCHEMA
    schema = _SCHEMA.get(sec, {}).get(key)
    if schema is None:
        return value
    expected_type, lo, hi = schema
    if lo is not None and value < lo:
        _log.warning("값 범위 초과: %s.%s=%s (최소=%s), 클램핑됨", sec, key, value, lo)
        return lo
    if hi is not None and value > hi:
        _log.warning("값 범위 초과: %s.%s=%s (최대=%s), 클램핑됨", sec, key, value, hi)
        return hi
    return value


def get_preset(name: str) -> dict:
    """프리셋 설정 반환 ('easy', 'normal', 'hard')."""
    presets = section("presets")
    return presets.get(name, {})


def list_presets() -> list[str]:
    """사용 가능한 프리셋 이름 목록."""
    presets = section("presets")
    return list(presets.keys())


def apply_preset_to_sliders(preset_name: str, slider_map: dict):
    """프리셋 값을 슬라이더에 적용.

    Args:
        preset_name: "easy", "normal", "hard"
        slider_map: {("section", "key"): slider_obj, ...}
    """
    preset = get_preset(preset_name)
    if not preset:
        _log.warning("프리셋 '%s' 없음", preset_name)
        return

    for (sec, key), slider in slider_map.items():
        sec_data = preset.get(sec, {})
        if key in sec_data:
            slider.value = _clamp_value(sec, key, sec_data[key])
    _log.info("프리셋 '%s' 적용 완료", preset_name)


# ── 프로파일 저장/불러오기 ────────────────────────────

def save_profile(name: str, slider_values: dict):
    """슬라이더 값을 프로파일로 저장.

    Args:
        name: 프로파일 이름 (확장자 없이)
        slider_values: {"slider_label": value, ...}
    """
    os.makedirs(PROFILES_DIR, exist_ok=True)
    path = os.path.join(PROFILES_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(slider_values, f, ensure_ascii=False, indent=2)
    _log.info("프로파일 저장: %s", path)


def load_profile(name: str) -> dict:
    """프로파일 불러오기."""
    path = os.path.join(PROFILES_DIR, f"{name}.json")
    if not os.path.exists(path):
        _log.warning("프로파일 없음: %s", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_profiles() -> list[str]:
    """저장된 프로파일 이름 목록."""
    if not os.path.exists(PROFILES_DIR):
        return []
    return [
        os.path.splitext(f)[0]
        for f in os.listdir(PROFILES_DIR)
        if f.endswith(".json")
    ]


def delete_profile(name: str) -> bool:
    """프로파일 삭제."""
    path = os.path.join(PROFILES_DIR, f"{name}.json")
    if os.path.exists(path):
        os.remove(path)
        _log.info("프로파일 삭제: %s", path)
        return True
    _log.warning("프로파일 없음 (삭제 실패): %s", path)
    return False


def rename_profile(old_name: str, new_name: str) -> bool:
    """프로파일 이름 변경."""
    old_path = os.path.join(PROFILES_DIR, f"{old_name}.json")
    new_path = os.path.join(PROFILES_DIR, f"{new_name}.json")
    if not os.path.exists(old_path):
        _log.warning("프로파일 없음 (이름변경 실패): %s", old_path)
        return False
    if os.path.exists(new_path):
        _log.warning("이름 충돌: %s 이미 존재", new_path)
        return False
    os.rename(old_path, new_path)
    _log.info("프로파일 이름변경: %s → %s", old_name, new_name)
    return True


def apply_profile_to_sliders(profile_name: str, sliders: dict):
    """프로파일 값을 슬라이더에 적용.

    Args:
        profile_name: 프로파일 이름
        sliders: {"slider_label": slider_obj, ...}
    """
    data = load_profile(profile_name)
    for label, value in data.items():
        if label in sliders:
            slider = sliders[label]
            if hasattr(slider, "min_val") and hasattr(slider, "max_val"):
                if value < slider.min_val or value > slider.max_val:
                    _log.warning(
                        "프로파일 값 범위 초과: %s=%s (범위 %s~%s), 클램핑됨",
                        label, value, slider.min_val, slider.max_val,
                    )
            slider.value = value
    _log.info("프로파일 '%s' 적용 완료", profile_name)
