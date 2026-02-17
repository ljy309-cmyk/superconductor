"""점수 무결성 검증 — HMAC 기반 스코어 서명/검증.

클라이언트가 점수를 POST할 때 HMAC 토큰을 함께 전송하고,
서버가 해당 토큰을 검증하여 변조를 탐지합니다.

사용법:
    from score_integrity import sign_score, verify_score

    # 클라이언트: 점수 서명
    token = sign_score("Player", 42.5, "qubit_chain")

    # 서버: 점수 검증
    ok = verify_score("Player", 42.5, "qubit_chain", token)
"""

import hashlib
import hmac
import os
import time

from logger import get_module_logger

_log = get_module_logger("score_integrity")

# 비밀 키 — 프로세스마다 고유 (런타임 생성)
# 로컬 싱글 프로세스에서만 유효 (같은 프로세스 내 검증)
_SECRET = os.urandom(32)

# 토큰 유효 시간 (초) — 게임 종료 후 즉시 전송하므로 짧게
_TOKEN_TTL = 60


def _make_message(name: str, score: float, mode: str, ts: int) -> bytes:
    """서명할 메시지 조합."""
    return f"{name}:{score:.2f}:{mode}:{ts}".encode("utf-8")


def sign_score(name: str, score: float, mode: str) -> str:
    """점수에 HMAC 서명 생성.

    Returns:
        "timestamp:hex_digest" 형태의 토큰 문자열
    """
    ts = int(time.time())
    msg = _make_message(name, score, mode, ts)
    digest = hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()
    return f"{ts}:{digest}"


def verify_score(name: str, score: float, mode: str, token: str) -> bool:
    """점수 서명 검증.

    Returns:
        True if valid and not expired
    """
    try:
        parts = token.split(":", 1)
        if len(parts) != 2:
            return False
        ts = int(parts[0])
        provided_digest = parts[1]
    except (ValueError, IndexError):
        _log.warning("잘못된 토큰 형식")
        return False

    # TTL 검사
    now = int(time.time())
    if abs(now - ts) > _TOKEN_TTL:
        _log.warning("토큰 만료: ts=%d, now=%d", ts, now)
        return False

    # HMAC 검증 (타이밍 세이프 비교)
    msg = _make_message(name, score, mode, ts)
    expected = hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(provided_digest, expected):
        _log.warning("토큰 불일치: score=%s, name=%s, mode=%s", score, name, mode)
        return False

    return True
