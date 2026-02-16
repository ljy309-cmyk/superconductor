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


def _load_locale(locale: str) -> dict[str, str]:
    """로케일 파일 로드."""
    path = os.path.join(_LOCALE_DIR, f"{locale}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def set_locale(locale: str):
    """현재 로케일 설정."""
    global _current_locale, _strings, _fallback
    _current_locale = locale
    _strings = _load_locale(locale)
    if locale != "ko":
        _fallback = _load_locale("ko")
    else:
        _fallback = {}


def get_locale() -> str:
    """현재 로케일 반환."""
    return _current_locale


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
