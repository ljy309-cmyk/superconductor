"""국제화(i18n) 지원 — 다국어 문자열 관리.

사용법:
    from i18n import t, set_locale
    set_locale("en")      # 영어로 전환
    label = t("menu_title")  # "Select a menu"
"""

import json
import os

_LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locale")
_current_locale = "ko"
_strings: dict[str, str] = {}
_fallback: dict[str, str] = {}
_locale_listeners: list = []

SUPPORTED_LOCALES = ["ko", "en"]


def _load_locale(locale: str) -> dict[str, str]:
    """로케일 파일 로드."""
    path = os.path.join(_LOCALE_DIR, f"{locale}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def set_locale(locale: str):
    """현재 로케일 설정."""
    global _current_locale, _strings, _fallback
    if locale == _current_locale and _strings:
        return
    _current_locale = locale
    _strings = _load_locale(locale)
    if locale != "ko":
        _fallback = _load_locale("ko")
    else:
        _fallback = {}
    _notify_locale_listeners()


def get_locale() -> str:
    """현재 로케일 반환."""
    return _current_locale


def toggle_locale() -> str:
    """ko ↔ en 토글. 새 로케일 반환."""
    idx = SUPPORTED_LOCALES.index(_current_locale) if _current_locale in SUPPORTED_LOCALES else 0
    new_locale = SUPPORTED_LOCALES[(idx + 1) % len(SUPPORTED_LOCALES)]
    set_locale(new_locale)
    return new_locale


def on_locale_change(callback):
    """로케일 변경 시 호출될 콜백 등록."""
    if callback not in _locale_listeners:
        _locale_listeners.append(callback)


def off_locale_change(callback):
    """로케일 변경 콜백 제거."""
    try:
        _locale_listeners.remove(callback)
    except ValueError:
        pass


def _notify_locale_listeners():
    """로케일 변경 알림."""
    for cb in _locale_listeners:
        try:
            cb()
        except (TypeError, AttributeError, ValueError, RuntimeError):
            pass


def t(key: str, **kwargs) -> str:
    """번역 문자열 조회. kwargs로 포맷 변수 치환.

    Example:
        t("target_temp", temp=-196.0)  → "목표 온도: -196.00 °C"
    """
    if not _strings:
        set_locale(_current_locale)

    text = _strings.get(key) or _fallback.get(key) or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text
