"""중앙 로깅 설정 — 모든 모듈에서 공유.

사용법:
    from logger import get_module_logger
    log = get_module_logger("play_logger")
    log.info("세션 기록 완료")
    log.error("저장 실패", exc_info=True)
"""

import logging
import os
import sys

_LOG_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_FILE = os.path.join(_LOG_DIR, "superconductor.log")
_initialized = False


def _setup():
    """로깅 시스템 초기화 (한 번만 호출)."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    root = logging.getLogger("superconductor")
    root.setLevel(logging.DEBUG)

    # 파일 핸들러 — DEBUG 이상 전부 기록
    try:
        fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fmt = logging.Formatter(
            "[%(asctime)s] %(name)-24s %(levelname)-7s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass  # 파일 쓰기 불가 환경 대비

    # 콘솔 핸들러 — WARNING 이상만 출력
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    sh.setFormatter(logging.Formatter("%(name)s: %(levelname)s: %(message)s"))
    root.addHandler(sh)


def get_module_logger(name: str) -> logging.Logger:
    """모듈별 로거 반환."""
    _setup()
    return logging.getLogger(f"superconductor.{name}")
