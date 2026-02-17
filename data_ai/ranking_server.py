"""로컬 REST API 랭킹 서버 (http.server 기반).

엔드포인트:
  GET  /ranking       → 상위 5위 JSON 반환
  POST /ranking       → 새 점수 등록 (JSON body: {name, score, mode})
  GET  /ranking/all   → 전체 기록 반환

데이터는 로컬 JSON 파일에 저장.
"""

import json
import os
import shutil
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

from config_loader import cfg
from logger import get_module_logger

_log = get_module_logger("ranking_server")

DATA_PATH = os.path.join(os.path.dirname(__file__), "ranking_data.json")
_BACKUP_PATH = DATA_PATH + ".bak"
HOST = cfg("server", "host", "127.0.0.1")
PORT = cfg("server", "port", 18084)
TOP_N = cfg("server", "top_n", 5)

_data_lock = threading.Lock()


def _load_data() -> list[dict]:
    """랭킹 데이터 로드 (백업 복원 포함)."""
    with _data_lock:
        for path in (DATA_PATH, _BACKUP_PATH):
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        return data
                except (json.JSONDecodeError, OSError) as e:
                    _log.warning("랭킹 데이터 로드 실패 (%s): %s", path, e)
        return []


def _save_data(records: list[dict]):
    """랭킹 데이터 저장 (원자적 쓰기 + 백업)."""
    with _data_lock:
        # 기존 파일 백업
        if os.path.exists(DATA_PATH):
            try:
                shutil.copy2(DATA_PATH, _BACKUP_PATH)
            except OSError:
                pass
        # 임시 파일에 쓰고 이동 (원자적)
        tmp_path = DATA_PATH + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, DATA_PATH)
        except OSError as e:
            _log.error("랭킹 데이터 저장 실패: %s", e)


class RankingHandler(BaseHTTPRequestHandler):
    """REST API 핸들러."""

    def log_message(self, format, *args):
        pass  # 콘솔 로그 억제

    def _set_json_headers(self, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_GET(self):
        records = _load_data()
        sorted_records = sorted(records, key=lambda r: r.get("score", 0), reverse=True)

        if self.path == "/ranking":
            top = sorted_records[:TOP_N]
            for i, r in enumerate(top):
                r["rank"] = i + 1
            self._set_json_headers()
            self.wfile.write(json.dumps(top, ensure_ascii=False).encode())

        elif self.path == "/ranking/all":
            self._set_json_headers()
            self.wfile.write(json.dumps(sorted_records, ensure_ascii=False).encode())

        else:
            self._set_json_headers(404)
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def do_POST(self):
        if self.path == "/ranking":
            length = int(self.headers.get("Content-Length", 0))
            if length > 10_000:  # 최대 10KB
                self._set_json_headers(413)
                self.wfile.write(json.dumps({"error": "Payload too large"}).encode())
                return

            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
                return

            name = str(data.get("name", "Anonymous"))[:50]  # 최대 50자
            score = data.get("score", 0)
            mode = str(data.get("mode", "unknown"))[:30]
            token = data.get("token", "")

            # 무결성 토큰 검증 (있으면)
            if token:
                try:
                    from score_integrity import verify_score
                    if not verify_score(name, float(score) if isinstance(score, (int, float)) else 0, mode, token):
                        _log.warning("점수 무결성 검증 실패: name=%s, score=%s", name, score)
                        self._set_json_headers(403)
                        self.wfile.write(json.dumps({"error": "Invalid score token"}).encode())
                        return
                except (ImportError, Exception) as e:
                    _log.warning("무결성 검증 모듈 오류: %s", e)

            # 점수 타입/범위 검증
            if not isinstance(score, (int, float)):
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"error": "score must be a number"}).encode())
                return
            score = max(0.0, min(float(score), 999999.0))  # 0 ~ 999999

            record = {
                "name": name,
                "score": round(score, 2),
                "mode": mode,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            records = _load_data()
            records.append(record)
            _save_data(records)

            # 현재 순위 계산
            sorted_records = sorted(records, key=lambda r: r["score"], reverse=True)
            rank = next(i + 1 for i, r in enumerate(sorted_records) if r["timestamp"] == record["timestamp"] and r["name"] == record["name"])

            self._set_json_headers(201)
            self.wfile.write(json.dumps({"status": "ok", "rank": rank, "record": record}, ensure_ascii=False).encode())
        else:
            self._set_json_headers(404)
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


_server_lock = threading.Lock()
_server_instance: HTTPServer | None = None
_server_thread: threading.Thread | None = None


def start_server():
    """백그라운드 스레드에서 랭킹 서버 시작 (스레드 안전)."""
    global _server_instance, _server_thread
    with _server_lock:
        if _server_instance is not None:
            return  # 이미 실행 중

        try:
            _server_instance = HTTPServer((HOST, PORT), RankingHandler)
            _server_thread = threading.Thread(target=_server_instance.serve_forever, daemon=True)
            _server_thread.start()
        except OSError:
            pass  # 포트 이미 사용 중


def stop_server():
    """서버 종료 (스레드 안전)."""
    global _server_instance
    with _server_lock:
        if _server_instance:
            _server_instance.shutdown()
            _server_instance = None


def get_base_url() -> str:
    return f"http://{HOST}:{PORT}"
