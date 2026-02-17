"""게임 플레이 기록 수집 및 엑셀 추출 (최종 미션).

각 게임 모듈(2~4)에서 세션 종료 시 플레이 데이터를 기록하고,
누적 데이터를 Excel/CSV로 자동 저장합니다.

사용법:
    from data_ai.play_logger import PlayLogger
    logger = PlayLogger()
    logger.log_session("qubit_chain", {"survival_time": 45.2, "qec_uses": 3, ...})
    logger.export()
"""

import csv
import json
import os
import threading
from datetime import datetime

import pandas as pd

from logger import get_module_logger

_log = get_module_logger("play_logger")

LOG_DIR = os.path.dirname(__file__)
PLAY_LOG_XLSX = os.path.join(LOG_DIR, "play_history.xlsx")
PLAY_LOG_CSV = os.path.join(LOG_DIR, "play_history.csv")
PLAY_LOG_JSON = os.path.join(LOG_DIR, "play_history.json")

# CSV 인젝션 위험 선행 문자 (스프레드시트 수식으로 해석될 수 있음)
_CSV_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def _sanitize_csv_value(value):
    """CSV 인젝션 방지: 위험한 선행 문자가 있는 문자열 앞에 작은따옴표 추가."""
    if isinstance(value, str) and value and value[0] in _CSV_DANGEROUS_PREFIXES:
        return "'" + value
    return value


class PlayLogger:
    """게임 플레이 데이터 누적 기록 및 엑셀 추출 (스레드 안전)."""

    # 기록 가능한 필드 정의 (모듈별)
    FIELDS = {
        "qubit_chain": [
            "total_qubits", "collapsed_count", "alive_count",
            "noise_rate", "cascade_damage",
            "shield_uses", "heal_uses",
            "max_stress", "survival_time",
        ],
        "tunneling": [
            "total_attempts", "tunnel_count", "reflect_count",
            "tunnel_rate", "barrier_width", "tunnel_prob",
        ],
        "qec_shield": [
            "survival_time", "alive_count", "total_qubits",
            "qec_uses", "heal_uses", "qec_reduction",
        ],
        "squid_mines": [
            "mines_found", "wrong_marks", "total_mines",
            "sensitivity", "won",
        ],
        "bb84_defense": [
            "score", "total_sent", "total_errors", "total_safe",
            "eve_intercepts", "auto_blocks", "manual_blocks",
            "decoy_sent", "decoy_trapped",
        ],
        "flux_pinning": [
            "play_time", "superconducting", "flipped",
        ],
        "phase_transition": [
            "material", "last_temp", "noise", "tc",
        ],
        "phase_transition_sim": [
            "play_time", "final_temp",
        ],
    }

    def __init__(self):
        self._lock = threading.Lock()
        self.records: list[dict] = []
        self._load_existing()

    def _load_existing(self):
        """기존 기록 파일이 있으면 로드."""
        if os.path.exists(PLAY_LOG_CSV):
            try:
                df = pd.read_csv(PLAY_LOG_CSV)
                self.records = df.to_dict("records")
                _log.info("기존 기록 %d건 로드", len(self.records))
            except Exception as e:
                _log.error("기록 로드 실패: %s", e)
                self.records = []

    def log_session(self, module_name: str, data: dict):
        """게임 세션 데이터 기록 (스레드 안전).

        Args:
            module_name: 모듈 이름 (예: "qubit_chain", "bb84_defense")
            data: 기록할 데이터 딕셔너리
        """
        if module_name not in self.FIELDS:
            _log.warning("알 수 없는 모듈명: %r (허용: %s)",
                         module_name, ", ".join(sorted(self.FIELDS)))

        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "module": module_name,
        }

        # 해당 모듈의 필드만 기록
        fields = self.FIELDS.get(module_name, [])
        for field in fields:
            record[field] = data.get(field, None)

        # 추가 커스텀 필드도 허용
        for key, val in data.items():
            if key not in record:
                record[key] = val

        with self._lock:
            self.records.append(record)
            self._append_csv(record)

        _log.info("세션 기록: %s (%d건)", module_name, len(self.records))
        return record

    def _append_csv(self, record: dict):
        """단일 레코드를 CSV에 증분 추가 (O(1) 성능)."""
        try:
            file_exists = os.path.exists(PLAY_LOG_CSV)
            # 전체 필드 셋 결정
            all_fields = ["timestamp", "module"]
            for fields in self.FIELDS.values():
                for f in fields:
                    if f not in all_fields:
                        all_fields.append(f)
            for k in record:
                if k not in all_fields:
                    all_fields.append(k)

            safe_record = {k: _sanitize_csv_value(v) for k, v in record.items()}

            if not file_exists or os.path.getsize(PLAY_LOG_CSV) == 0:
                # 새 파일: 헤더 + 레코드
                with open(PLAY_LOG_CSV, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerow(safe_record)
            else:
                # 기존 파일: 레코드만 추가
                with open(PLAY_LOG_CSV, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
                    writer.writerow(safe_record)
        except OSError as e:
            _log.error("CSV 증분 저장 실패: %s", e)

    def export(self) -> str:
        """누적 기록을 Excel + CSV로 전체 저장."""
        with self._lock:
            if not self.records:
                return ""

            df = pd.DataFrame(self.records)

            # 컬럼 정렬: timestamp, module을 앞으로
            priority = ["timestamp", "module"]
            other_cols = [c for c in df.columns if c not in priority]
            df = df[priority + other_cols]

            # CSV 인젝션 방지: 문자열 컬럼 살균화
            safe_df = df.copy()
            for col in safe_df.select_dtypes(include=["object"]).columns:
                safe_df[col] = safe_df[col].map(
                    lambda v: _sanitize_csv_value(v) if isinstance(v, str) else v
                )

            try:
                df.to_excel(PLAY_LOG_XLSX, index=False)
                safe_df.to_csv(PLAY_LOG_CSV, index=False)
                _log.info("기록 내보내기 완료: %d건", len(df))
            except OSError as e:
                _log.error("내보내기 실패: %s", e)

        return PLAY_LOG_XLSX

    def export_json(self) -> str:
        """누적 기록을 JSON으로 저장."""
        with self._lock:
            if not self.records:
                return ""
            try:
                with open(PLAY_LOG_JSON, "w", encoding="utf-8") as f:
                    json.dump(self.records, f, ensure_ascii=False, indent=2)
                _log.info("JSON 내보내기 완료: %d건", len(self.records))
            except OSError as e:
                _log.error("JSON 내보내기 실패: %s", e)
        return PLAY_LOG_JSON

    def get_summary(self) -> dict:
        """모듈별 플레이 통계 요약."""
        with self._lock:
            if not self.records:
                return {"total_sessions": 0}

            df = pd.DataFrame(self.records)

        summary = {
            "total_sessions": len(df),
            "modules_played": df["module"].nunique(),
            "sessions_per_module": df["module"].value_counts().to_dict(),
        }

        for module in df["module"].unique():
            mod_df = df[df["module"] == module]
            fields = self.FIELDS.get(module, [])
            mod_stats = {}
            for field in fields:
                if field in mod_df.columns:
                    series = pd.to_numeric(mod_df[field], errors="coerce").dropna()
                    if not series.empty:
                        mod_stats[field] = {
                            "mean": round(series.mean(), 2),
                            "max": round(series.max(), 2),
                            "min": round(series.min(), 2),
                        }
            summary[module] = mod_stats

        return summary

    def clear(self):
        """기록 초기화."""
        with self._lock:
            self.records.clear()
            for path in (PLAY_LOG_XLSX, PLAY_LOG_CSV, PLAY_LOG_JSON):
                if os.path.exists(path):
                    os.remove(path)
        _log.info("기록 초기화 완료")


# 싱글턴 인스턴스 (스레드 안전 — 더블 체크 락킹)
_logger_lock = threading.Lock()
_logger_instance: PlayLogger | None = None


def get_logger() -> PlayLogger:
    """전역 PlayLogger 인스턴스 반환 (스레드 안전)."""
    global _logger_instance
    if _logger_instance is None:
        with _logger_lock:
            if _logger_instance is None:
                _logger_instance = PlayLogger()
    return _logger_instance
