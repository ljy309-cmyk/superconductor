"""중앙 설정 파일 로더 — config.json에서 값을 읽어온다.

사용법:
    from config_loader import cfg
    NOISE_RATE = cfg("qubit_chain", "noise_rate_base", 3.0)
"""

import json
import os

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        else:
            _cache = {}
    return _cache


def cfg(section: str, key: str, default=None):
    """설정 값 조회.  cfg("qubit_chain", "noise_rate_base", 3.0)"""
    return _load().get(section, {}).get(key, default)


def section(name: str) -> dict:
    """섹션 전체를 dict로 반환."""
    return _load().get(name, {})
