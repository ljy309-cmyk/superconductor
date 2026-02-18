"""중앙 설정 파일 로더 — config.json에서 값을 읽어온다.

사용법:
    from config_loader import cfg
    NOISE_RATE = cfg("qubit_chain", "noise_rate_base", 3.0)
"""

import json
import os

from logger import get_module_logger

_log = get_module_logger("config_loader")
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
_cache: dict | None = None

# ── 설정값 스키마 (타입, 최소, 최대) ──────────────────
_SCHEMA: dict[str, dict[str, tuple]] = {
    "display": {
        "fps": (int, 1, 240),
        "width": (int, 640, 3840),
        "height": (int, 480, 2160),
    },
    "accessibility": {
        "colorblind_mode": (bool, None, None),
    },
    "server": {
        "host": (str, None, None),
        "port": (int, 1024, 65535),
        "top_n": (int, 1, 100),
    },
    "qrng": {
        "bits_per_key": (int, 8, 4096),
        "noise_sources": (int, 1, 32),
    },
    "ml": {
        "n_estimators": (int, 1, 1000),
        "test_size": (float, 0.01, 0.99),
        "random_state": (int, 0, None),
    },
    "qubit_chain": {
        "stress_threshold": (float, 10.0, 500.0),
        "stress_danger": (float, 1.0, 500.0),
        "stress_warning": (float, 1.0, 500.0),
        "cascade_damage": (float, 0.0, 200.0),
        "noise_rate_base": (float, 0.0, 50.0),
        "recovery_rate": (float, 0.0, 50.0),
        "collapse_anim_duration": (float, 0.1, 5.0),
        "qec_reduction": (float, 0.0, 1.0),
        "qec_duration": (float, 0.5, 60.0),
        "qec_cooldown": (float, 0.5, 60.0),
        "heal_amount": (float, 1.0, 100.0),
        "heal_cooldown": (float, 0.0, 30.0),
        "outer_nodes": (int, 3, 12),
        "node_radius": (int, 5, 100),
        "ring_radius": (int, 50, 500),
    },
    "tunneling": {
        "tunnel_prob_base": (float, 0.0, 1.0),
        "particle_speed": (float, 10.0, 1000.0),
        "barrier_width_default": (int, 1, 500),
        "barrier_width_min": (int, 1, 500),
        "barrier_width_max": (int, 1, 500),
        "tunnel_speed_boost": (float, 1.0, 10.0),
        "superposition_hz": (float, 0.1, 60.0),
        "tunnel_decay_rate": (float, 0.001, 1.0),
        "particle_vy_range": (float, 0.0, 500.0),
        "tunnel_flash_sec": (float, 0.05, 5.0),
        "reflect_flash_sec": (float, 0.05, 5.0),
    },
    "qec_shield": {
        "noise_rate": (float, 0.0, 50.0),
        "qec_reduction_default": (float, 0.0, 1.0),
        "qec_reduction_min": (float, 0.0, 1.0),
        "qec_reduction_max": (float, 0.0, 1.0),
        "qec_duration": (float, 0.5, 60.0),
        "qec_cooldown": (float, 0.5, 60.0),
        "heal_amount": (float, 1.0, 100.0),
        "heal_cooldown": (float, 0.0, 30.0),
        "stress_threshold": (float, 10.0, 500.0),
        "cascade_damage": (float, 0.0, 200.0),
        "grid_cols": (int, 1, 20),
        "grid_rows": (int, 1, 20),
        "node_radius": (int, 5, 100),
        "stress_warning": (float, 1.0, 500.0),
    },
    "squid_mines": {
        "grid_cols": (int, 3, 30),
        "grid_rows": (int, 3, 20),
        "num_mines": (int, 1, 100),
        "sensitivity_default": (float, 0.5, 20.0),
        "sensitivity_min": (float, 0.1, 20.0),
        "sensitivity_max": (float, 0.1, 20.0),
        "beep_freq": (int, 100, 5000),
        "beep_duration_ms": (int, 10, 500),
    },
    "bb84": {
        "send_interval": (float, 0.1, 10.0),
        "eve_chance": (float, 0.0, 1.0),
        "eve_error_inject": (float, 0.0, 1.0),
        "error_threshold": (float, 0.0, 1.0),
        "history_window": (int, 5, 200),
        "auto_block_threshold": (float, 0.0, 1.0),
        "auto_block_score": (int, 0, 10000),
        "manual_block_score": (int, 0, 10000),
        "warning_threshold": (float, 0.0, 1.0),
        "decoy_chance": (float, 0.0, 1.0),
        "decoy_error_mult": (float, 1.0, 10.0),
    },
    "flux_pinning": {
        "equilibrium_gap": (float, 10.0, 200.0),
        "spring_k": (float, 0.1, 20.0),
        "damping": (float, 0.1, 1.0),
        "levitation_amp": (float, 0.0, 20.0),
        "levitation_freq": (float, 0.1, 10.0),
        "gravity": (float, 100.0, 2000.0),
    },
    "achievements": {
        "qc_survive_short": (int, 1, 600),
        "qc_survive_long": (int, 1, 600),
        "qc_shield_uses": (int, 1, 100),
        "qc_no_collapse_time": (int, 1, 600),
        "tn_tunnel_streak": (int, 1, 1000),
        "tn_rate_threshold": (float, 0.0, 1.0),
        "tn_rate_min_attempts": (int, 1, 1000),
        "qec_survive_time": (int, 1, 600),
        "qec_efficient_max_uses": (int, 0, 100),
        "qec_efficient_time": (int, 1, 600),
        "bb84_score_target": (int, 1, 100000),
        "bb84_manual_blocks": (int, 1, 1000),
        "bb84_decoy_trapped": (int, 1, 1000),
        "all_modules_count": (int, 1, 20),
    },
    "phase_transition": {
        "t_range_min": (float, -300.0, -100.0),
        "t_range_max": (float, -50.0, 200.0),
        "r_normal": (float, 0.1, 10.0),
    },
}


def _validate(section: str, key: str, value):
    """스키마 기반 타입/범위 검증. 실패 시 None 반환."""
    schema = _SCHEMA.get(section, {}).get(key)
    if schema is None:
        return value  # 스키마 없으면 그대로 통과

    expected_type, min_val, max_val = schema

    # 타입 검증
    if expected_type is bool:
        if not isinstance(value, bool):
            _log.warning("설정 타입 오류: [%s].%s = %r (bool 필요)", section, key, value)
            return None
        return value
    if expected_type in (int, float):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            _log.warning("설정 타입 오류: [%s].%s = %r (%s 필요)", section, key, value, expected_type.__name__)
            return None
        if expected_type is int:
            value = int(value)
        else:
            value = float(value)
    elif expected_type is str and not isinstance(value, str):
        _log.warning("설정 타입 오류: [%s].%s = %r (str 필요)", section, key, value)
        return None

    # 범위 검증
    if min_val is not None and value < min_val:
        _log.warning("설정 범위 미달: [%s].%s = %r (최소 %s)", section, key, value, min_val)
        return None
    if max_val is not None and value > max_val:
        _log.warning("설정 범위 초과: [%s].%s = %r (최대 %s)", section, key, value, max_val)
        return None

    return value


def _load() -> dict:
    global _cache
    if _cache is None:
        if os.path.exists(_CONFIG_PATH):
            try:
                with open(_CONFIG_PATH, encoding="utf-8") as f:
                    _cache = json.load(f)
                _log.info("config.json 로드 완료")
            except (json.JSONDecodeError, OSError) as e:
                _log.error("config.json 파싱 실패: %s", e)
                _cache = {}
        else:
            _log.warning("config.json 파일 없음, 기본값 사용")
            _cache = {}
    return _cache


def cfg(section: str, key: str, default=None):
    """설정 값 조회.  cfg("qubit_chain", "noise_rate_base", 3.0)"""
    sec_data = _load().get(section, {})
    if not isinstance(sec_data, dict):
        return default
    raw = sec_data.get(key, default)
    if raw is None:
        return default
    validated = _validate(section, key, raw)
    if validated is None:
        return default
    return validated


def section(name: str) -> dict:
    """섹션 전체를 dict로 반환."""
    return _load().get(name, {})


def reload_config():
    """config.json을 다시 로드한다 (런타임 갱신 지원)."""
    global _cache
    _cache = None
    _load()
