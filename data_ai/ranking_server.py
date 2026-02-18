"""로컬 REST API 랭킹 서버 (http.server 기반).

엔드포인트:
  GET  /ranking       → 상위 5위 JSON 반환
  POST /ranking       → 새 점수 등록 (JSON body: {name, score, mode})
  GET  /ranking/all   → 전체 기록 반환

데이터는 로컬 JSON 파일에 저장.
"""

import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

from config_loader import cfg

DATA_PATH = os.path.join(os.path.dirname(__file__), "ranking_data.json")
HOST = cfg("server", "host", "127.0.0.1")
PORT = cfg("server", "port", 18084)
TOP_N = cfg("server", "top_n", 5)
MAX_PAYLOAD = cfg("ranking", "max_payload_bytes", 10_000)
NAME_MAX_LEN = cfg("ranking", "name_max_length", 50)
SCORE_MAX = cfg("ranking", "score_max", 999999)


def _load_data() -> list[dict]:
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_data(records: list[dict]):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


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
            if length > MAX_PAYLOAD:
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

            name = str(data.get("name", "Anonymous"))[:NAME_MAX_LEN]
            score = data.get("score", 0)
            mode = str(data.get("mode", "unknown"))[:30]

            # 점수 타입/범위 검증
            if not isinstance(score, (int, float)):
                self._set_json_headers(400)
                self.wfile.write(json.dumps({"error": "score must be a number"}).encode())
                return
            score = max(0.0, min(float(score), float(SCORE_MAX)))

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
