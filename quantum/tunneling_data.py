"""터널링 시뮬레이션 데이터 관리 — 세션 내보내기/가져오기.

``quantum.tunneling`` 에서 분리된 데이터 I/O 전용 모듈.
공통 ``session_io`` 를 활용하여 export/import 처리.
"""

import os
import time

from logger import get_module_logger
from quantum.tunneling_physics import (
    BARRIER_WIDTH_MAX,
    BARRIER_WIDTH_MIN,
)
from session_io import (
    choose_import_file,
    export_session,
    load_session,
)

_log = get_module_logger("tunneling")

_PREFIX = "tunneling"


# ── 세션 데이터 빌드 ────────────────────────────────


def _build_session_data(ctx) -> dict:
    """finalize_session용 세션 요약 딕셔너리 생성."""
    p = ctx.particle
    rate = p.tunnel_count / max(p.total_attempts, 1)
    elapsed_time = time.monotonic() - ctx.start_time
    elapsed_min = elapsed_time / 60.0 if elapsed_time > 0 else 1.0
    avg_bw = (
        round(sum(tr["barrier"] for tr in ctx.trial_history) / len(ctx.trial_history), 1)
        if ctx.trial_history
        else ctx.barrier_width
    )
    return {
        "total_attempts": p.total_attempts,
        "tunnel_count": p.tunnel_count,
        "reflect_count": p.reflect_count,
        "tunnel_rate": round(rate, 3),
        "barrier_width": ctx.barrier_width,
        "base_prob": round(ctx.base_prob, 3),
        "tunnel_prob": round(ctx.tunnel_prob, 3),
        "elapsed_time": round(elapsed_time, 2),
        "max_tunnel_barrier": ctx.max_tunnel_barrier,
        "barrier_configs_tried": len(ctx.barrier_configs_tried),
        "peak_rate": round(ctx.peak_rate, 3),
        "avg_barrier_width": avg_bw,
        "trials_per_minute": round(p.total_attempts / elapsed_min, 1),
        "speed_mult": round(ctx.speed_mult, 1),
        "difficulty": ctx.preset_hud.current,
        "trial_history": list(ctx.trial_history),
    }


# ── 데이터 내보내기 ──────────────────────────────────


def _export_session(ctx) -> str | None:
    """세션 통계를 내보내기. 저장 경로 반환 (실패 시 None)."""
    session = _build_session_data(ctx)
    trials = session.pop("trial_history", [])
    return export_session(_PREFIX, session, trial_rows=trials)


# ── 데이터 가져오기 ──────────────────────────────────


def _safe_numeric(value, typ, default):
    """값을 안전하게 숫자로 변환. 실패 시 default 반환."""
    if isinstance(value, typ):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return typ(value)
    return default


def _load_import_data(path: str) -> tuple[dict | None, list[dict]]:
    """세션 파일 로드 (포맷 자동 감지) + 타입 검증."""
    data = load_session(path)
    if data is None:
        return None, []
    # 핵심 필드 타입 검증
    for key in ("base_prob", "tunnel_prob", "tunnel_rate", "peak_rate", "speed_mult"):
        if key in data:
            data[key] = _safe_numeric(data[key], float, None)
            if data[key] is None:
                _log.warning("가져오기 필드 타입 오류 (제거): %s", key)
                del data[key]
    for key in ("total_attempts", "tunnel_count", "reflect_count", "barrier_width"):
        if key in data:
            data[key] = _safe_numeric(data[key], int, None)
            if data[key] is None:
                _log.warning("가져오기 필드 타입 오류 (제거): %s", key)
                del data[key]
    trials = data.pop("trial_history", [])
    if not isinstance(trials, list):
        _log.warning("trial_history가 list가 아님, 무시")
        trials = []
    return data, trials


def _import_session(ctx) -> bool:
    """내보내기 파일을 선택하고 파라미터 적용 + 비교 데이터 로드."""
    path = choose_import_file(ctx.screen, ctx.font, _PREFIX)
    if path is None:
        return False

    session, trials = _load_import_data(path)
    if session is None:
        return False

    # 슬라이더에 파라미터 적용 (타입이 검증된 값만 사용)
    if "base_prob" in session:
        ctx.sl_prob.value = max(0.01, min(0.50, session["base_prob"]))
    if "barrier_width" in session:
        ctx.sl_barrier.value = max(BARRIER_WIDTH_MIN, min(BARRIER_WIDTH_MAX, session["barrier_width"]))
    if "speed_mult" in session:
        ctx.sl_speed.value = max(0.5, min(5.0, session["speed_mult"]))
    ctx.read_sliders()

    # 비교용 시행 이력 저장
    if trials:
        ctx.imported_trials = trials
        fname = os.path.basename(path).replace("tunneling_stats_", "")
        ts_label = os.path.splitext(fname)[0]
        ctx.imported_label = ts_label

    _log.info("데이터 가져오기 완료: %s (%d trials)", path, len(trials))
    return True
