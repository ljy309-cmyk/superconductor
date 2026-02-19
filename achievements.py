"""업적/뱃지 시스템 — 게임 플레이 목표 달성 추적.

사용법:
    from achievements import check_achievements, get_all_achievements
    new = check_achievements("qubit_chain", {"survival_time": 60.0})
    # new = [{"id": "qc_survivor_60", "title": "1분 생존", ...}]
"""

import json
import os

from config_loader import cfg
from logger import get_module_logger

_log = get_module_logger("achievements")

_SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "achievements.json")

# ── 업적 임계값 (config.json에서 로드) ────────────────────────
_T = {
    "qc_survive_short": cfg("achievements", "qc_survive_short", 30),
    "qc_survive_long": cfg("achievements", "qc_survive_long", 60),
    "qc_shield_uses": cfg("achievements", "qc_shield_uses", 5),
    "qc_no_collapse_time": cfg("achievements", "qc_no_collapse_time", 30),
    "tn_tunnel_streak": cfg("achievements", "tn_tunnel_streak", 10),
    "tn_rate_threshold": cfg("achievements", "tn_rate_threshold", 0.5),
    "tn_rate_min_attempts": cfg("achievements", "tn_rate_min_attempts", 10),
    "qec_survive_time": cfg("achievements", "qec_survive_time", 60),
    "qec_efficient_max": cfg("achievements", "qec_efficient_max_uses", 3),
    "qec_efficient_time": cfg("achievements", "qec_efficient_time", 60),
    "bb84_score": cfg("achievements", "bb84_score_target", 500),
    "bb84_manual": cfg("achievements", "bb84_manual_blocks", 5),
    "bb84_decoy": cfg("achievements", "bb84_decoy_trapped", 3),
    "qa_e91_rounds": cfg("achievements", "qa_e91_rounds", 200),
    "qa_ghz_consistency": cfg("achievements", "qa_ghz_consistency", 0.9),
    "qa_ghz_rounds": cfg("achievements", "qa_ghz_rounds", 100),
    "all_modules": cfg("achievements", "all_modules_count", 6),
    "shor_large_number": cfg("achievements", "shor_large_number", 100),
    "shor_speed_run_sec": cfg("achievements", "shor_speed_run_sec", 30),
}

# ── 업적 정의 ───────────────────────────────────────────────
ACHIEVEMENTS = [
    # 큐비트 연쇄 붕괴
    {
        "id": "qc_first_play",
        "module": "qubit_chain",
        "title": "First Cascade",
        "desc": "큐비트 연쇄 붕괴를 처음 플레이했습니다.",
        "icon": "Q",
        "condition": lambda d: True,
    },
    {
        "id": "qc_survivor_30",
        "module": "qubit_chain",
        "title": "30s Survivor",
        "desc": "30초 이상 생존했습니다.",
        "icon": "T",
        "condition": lambda d: d.get("survival_time", 0) >= _T["qc_survive_short"],
    },
    {
        "id": "qc_survivor_60",
        "module": "qubit_chain",
        "title": "1min Survivor",
        "desc": "1분 이상 생존했습니다!",
        "icon": "S",
        "condition": lambda d: d.get("survival_time", 0) >= _T["qc_survive_long"],
    },
    {
        "id": "qc_shield_master",
        "module": "qubit_chain",
        "title": "Shield Master",
        "desc": "QEC 방어막을 5회 이상 사용했습니다.",
        "icon": "D",
        "condition": lambda d: d.get("shield_uses", 0) >= _T["qc_shield_uses"],
    },
    {
        "id": "qc_no_collapse",
        "module": "qubit_chain",
        "title": "Perfect Defense",
        "desc": "큐비트 붕괴 없이 30초 생존!",
        "icon": "P",
        "condition": lambda d: (
            d.get("collapsed_count", 1) == 0 and d.get("survival_time", 0) >= _T["qc_no_collapse_time"]
        ),
    },
    # 터널링
    {
        "id": "tn_first_tunnel",
        "module": "tunneling",
        "title": "First Tunnel",
        "desc": "첫 터널링 성공!",
        "icon": "W",
        "condition": lambda d: d.get("tunnel_count", 0) >= 1,
    },
    {
        "id": "tn_lucky_10",
        "module": "tunneling",
        "title": "Lucky Streak",
        "desc": "터널링 10회 성공!",
        "icon": "L",
        "condition": lambda d: d.get("tunnel_count", 0) >= _T["tn_tunnel_streak"],
    },
    {
        "id": "tn_rate_50",
        "module": "tunneling",
        "title": "Probability Bender",
        "desc": "터널링 성공률 50% 달성!",
        "icon": "B",
        "condition": lambda d: (
            d.get("tunnel_rate", 0) >= _T["tn_rate_threshold"]
            and d.get("total_attempts", 0) >= _T["tn_rate_min_attempts"]
        ),
    },
    # QEC 방어막
    {
        "id": "qec_survivor_60",
        "module": "qec_shield",
        "title": "QEC Master",
        "desc": "QEC 모드에서 60초 이상 생존!",
        "icon": "M",
        "condition": lambda d: d.get("survival_time", 0) >= _T["qec_survive_time"],
    },
    {
        "id": "qec_efficient",
        "module": "qec_shield",
        "title": "Efficient Shielding",
        "desc": "QEC 3회 이하로 60초 생존!",
        "icon": "E",
        "condition": lambda d: (
            d.get("qec_uses", 99) <= _T["qec_efficient_max"] and d.get("survival_time", 0) >= _T["qec_efficient_time"]
        ),
    },
    # BB84
    {
        "id": "bb84_first_play",
        "module": "bb84_defense",
        "title": "Protocol Initiator",
        "desc": "BB84 프로토콜을 처음 실행했습니다.",
        "icon": "K",
        "condition": lambda d: True,
    },
    {
        "id": "bb84_score_500",
        "module": "bb84_defense",
        "title": "Score 500",
        "desc": "BB84에서 500점 달성!",
        "icon": "H",
        "condition": lambda d: d.get("score", 0) >= _T["bb84_score"],
    },
    {
        "id": "bb84_manual_5",
        "module": "bb84_defense",
        "title": "Quick Hands",
        "desc": "수동 차단을 5회 이상 실행!",
        "icon": "F",
        "condition": lambda d: d.get("manual_blocks", 0) >= _T["bb84_manual"],
    },
    {
        "id": "bb84_trap_3",
        "module": "bb84_defense",
        "title": "Decoy Expert",
        "desc": "디코이 트랩 3회 이상 발동!",
        "icon": "X",
        "condition": lambda d: d.get("decoy_trapped", 0) >= _T["bb84_decoy"],
    },
    # SQUID 지뢰찾기
    {
        "id": "sq_first_win",
        "module": "squid_mines",
        "title": "Mine Sweeper",
        "desc": "모든 지뢰를 찾았습니다!",
        "icon": "G",
        "condition": lambda d: d.get("won", False),
    },
    {
        "id": "sq_perfect",
        "module": "squid_mines",
        "title": "Perfect Scan",
        "desc": "오답 없이 모든 지뢰를 찾았습니다!",
        "icon": "V",
        "condition": lambda d: d.get("won", False) and d.get("wrong_marks", 1) == 0,
    },
    # 고급 QKD
    {
        "id": "qa_first_play",
        "module": "qkd_advanced",
        "title": "Entangled Keys",
        "desc": "고급 QKD(E91) 프로토콜을 처음 실행했습니다.",
        "icon": "E",
        "condition": lambda d: True,
    },
    {
        "id": "qa_bell_violation",
        "module": "qkd_advanced",
        "title": "Bell Breaker",
        "desc": "벨 부등식 위반을 확인하여 양자 보안을 검증했습니다!",
        "icon": "B",
        "condition": lambda d: d.get("e91_bell_violated", False),
    },
    {
        "id": "qa_e91_200",
        "module": "qkd_advanced",
        "title": "E91 Veteran",
        "desc": f"E91 프로토콜 {_T['qa_e91_rounds']}라운드 달성!",
        "icon": "R",
        "condition": lambda d: d.get("e91_rounds", 0) >= _T["qa_e91_rounds"],
    },
    {
        "id": "qa_ghz_consistent",
        "module": "qkd_advanced",
        "title": "GHZ Harmony",
        "desc": "GHZ 일관성 검증 통과율 90% 이상 달성!",
        "icon": "G",
        "condition": lambda d: (
            d.get("ghz_consistency_rate", 0) >= _T["qa_ghz_consistency"]
            and d.get("ghz_rounds", 0) >= _T["qa_ghz_rounds"]
        ),
    },
    # Shor's Algorithm
    {
        "id": "shor_first_factorization",
        "module": "shor_algorithm",
        "title": "Quantum Factorizer",
        "desc": "Shor 알고리즘으로 첫 소인수분해에 성공했습니다!",
        "icon": "F",
        "condition": lambda d: d.get("numbers_factored", 0) >= 1,
    },
    {
        "id": "shor_large_number",
        "module": "shor_algorithm",
        "title": "Big Number Breaker",
        "desc": f"{_T['shor_large_number']} 이상의 큰 수를 소인수분해했습니다!",
        "icon": "N",
        "condition": lambda d: d.get("largest_factored", 0) >= _T["shor_large_number"],
    },
    {
        "id": "shor_speed_run",
        "module": "shor_algorithm",
        "title": "Speed Cracker",
        "desc": f"{_T['shor_speed_run_sec']}초 내에 소인수분해를 완료했습니다!",
        "icon": "Z",
        "condition": lambda d: (
            d.get("numbers_factored", 0) >= 1
            and d.get("play_time", 999) <= _T["shor_speed_run_sec"]
        ),
    },
    # 플럭스 피닝
    {
        "id": "fp_first_play",
        "module": "flux_pinning",
        "title": "Levitation!",
        "desc": "마이스너 부상 시뮬레이션을 체험했습니다.",
        "icon": "U",
        "condition": lambda d: True,
    },
    # 범용
    {
        "id": "all_modules",
        "module": "_global",
        "title": "Explorer",
        "desc": "모든 6개 게임 모듈을 플레이했습니다!",
        "icon": "A",
        "condition": lambda d: len(d.get("modules_played", [])) >= _T["all_modules"],
    },
]


def _load_unlocked() -> set[str]:
    """해금된 업적 ID 로드."""
    if os.path.exists(_SAVE_PATH):
        try:
            with open(_SAVE_PATH, encoding="utf-8") as f:
                return set(json.load(f))
        except (OSError, json.JSONDecodeError, TypeError) as e:
            _log.warning("업적 로드 실패 (초기화): %s", e)
    return set()


def _save_unlocked(unlocked: set[str]):
    """해금 상태 저장."""
    try:
        with open(_SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(unlocked), f)
    except OSError as e:
        _log.error("업적 저장 실패: %s", e)


def check_achievements(module_name: str, data: dict) -> list[dict]:
    """세션 데이터로 업적 달성 여부 확인. 새로 해금된 업적 목록 반환."""
    unlocked = _load_unlocked()
    new_achievements = []

    for ach in ACHIEVEMENTS:
        if ach["id"] in unlocked:
            continue
        if ach["module"] != module_name and ach["module"] != "_global":
            continue
        try:
            if ach["condition"](data):
                unlocked.add(ach["id"])
                new_achievements.append(ach)
                _log.info("업적 해금: %s — %s", ach["id"], ach["title"])
        except (KeyError, TypeError, ValueError) as e:
            _log.warning("업적 조건 평가 실패 [%s]: %s", ach["id"], e)

    if new_achievements:
        _save_unlocked(unlocked)

    return new_achievements


def get_all_achievements() -> list[dict]:
    """전체 업적 목록 (해금 상태 포함)."""
    unlocked = _load_unlocked()
    result = []
    for ach in ACHIEVEMENTS:
        info = {
            "id": ach["id"],
            "module": ach["module"],
            "title": ach["title"],
            "desc": ach["desc"],
            "icon": ach["icon"],
            "unlocked": ach["id"] in unlocked,
        }
        result.append(info)
    return result


def get_unlocked_count() -> tuple[int, int]:
    """(해금 수, 전체 수) 반환."""
    unlocked = _load_unlocked()
    return len(unlocked), len(ACHIEVEMENTS)
