"""게임 플레이 기록 수집 및 엑셀 추출 (최종 미션).

각 게임 모듈(2~4)에서 세션 종료 시 플레이 데이터를 기록하고,
누적 데이터를 Excel/CSV로 자동 저장합니다.

사용법:
    from data_ai.play_logger import PlayLogger
    logger = PlayLogger()
    logger.log_session("qubit_chain", {"survival_time": 45.2, "qec_uses": 3, ...})
    logger.export()
"""

import os
from datetime import datetime

import pandas as pd

LOG_DIR = os.path.dirname(__file__)
PLAY_LOG_XLSX = os.path.join(LOG_DIR, "play_history.xlsx")
PLAY_LOG_CSV = os.path.join(LOG_DIR, "play_history.csv")


class PlayLogger:
    """게임 플레이 데이터 누적 기록 및 엑셀 추출."""

    # 기록 가능한 필드 정의 (모듈별)
    FIELDS = {
        # 모듈 3-1: 큐비트 연쇄 붕괴
        "qubit_chain": [
            "total_qubits", "collapsed_count", "alive_count",
            "noise_rate", "cascade_damage",
            "shield_uses", "heal_uses",
            "max_stress",
        ],
        # 모듈 3-2: 양자 터널링
        "tunneling": [
            "total_attempts", "tunnel_count", "reflect_count",
            "tunnel_rate", "barrier_width", "tunnel_prob",
        ],
        # 모듈 3-3: QEC 방어막
        "qec_shield": [
            "survival_time", "alive_count", "total_qubits",
            "qec_uses", "heal_uses", "qec_reduction",
        ],
        # 모듈 4-1: SQUID 지뢰찾기
        "squid_mines": [
            "mines_found", "wrong_marks", "total_mines",
            "sensitivity", "won",
        ],
        # 모듈 4-2: BB84 방어전
        "bb84_defense": [
            "score", "total_sent", "total_errors", "total_safe",
            "eve_intercepts", "auto_blocks", "manual_blocks",
            "decoy_sent", "decoy_trapped",
        ],
    }

    def __init__(self):
        self.records: list[dict] = []
        self._load_existing()

    def _load_existing(self):
        """기존 기록 파일이 있으면 로드."""
        if os.path.exists(PLAY_LOG_CSV):
            try:
                df = pd.read_csv(PLAY_LOG_CSV)
                self.records = df.to_dict("records")
            except Exception:
                self.records = []

    def log_session(self, module_name: str, data: dict):
        """게임 세션 데이터 기록.

        Args:
            module_name: 모듈 이름 (예: "qubit_chain", "bb84_defense")
            data: 기록할 데이터 딕셔너리
        """
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

        self.records.append(record)
        self._auto_save()
        return record

    def _auto_save(self):
        """기록 변경 시 자동 저장."""
        try:
            self.export()
        except Exception:
            pass  # UI 없는 환경에서도 안전

    def export(self) -> str:
        """누적 기록을 Excel + CSV로 저장."""
        if not self.records:
            return ""

        df = pd.DataFrame(self.records)

        # 컬럼 정렬: timestamp, module을 앞으로
        priority = ["timestamp", "module"]
        other_cols = [c for c in df.columns if c not in priority]
        df = df[priority + other_cols]

        df.to_excel(PLAY_LOG_XLSX, index=False)
        df.to_csv(PLAY_LOG_CSV, index=False)
        return PLAY_LOG_XLSX

    def get_summary(self) -> dict:
        """모듈별 플레이 통계 요약."""
        if not self.records:
            return {"total_sessions": 0}

        df = pd.DataFrame(self.records)
        summary = {
            "total_sessions": len(df),
            "modules_played": df["module"].nunique(),
            "sessions_per_module": df["module"].value_counts().to_dict(),
        }

        # 모듈별 주요 지표 평균
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
        self.records.clear()
        for path in (PLAY_LOG_XLSX, PLAY_LOG_CSV):
            if os.path.exists(path):
                os.remove(path)


# 싱글턴 인스턴스 (모든 모듈에서 공유)
_logger_instance: PlayLogger | None = None


def get_logger() -> PlayLogger:
    """전역 PlayLogger 인스턴스 반환."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = PlayLogger()
    return _logger_instance
