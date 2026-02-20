"""ranking_server REST API 통합 테스트 — HTTPServer를 실제 기동하여 검증."""

import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import HTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "data_ai"))

from data_ai.ranking_server import RankingHandler, _rate_limit_lock, _rate_limit_map


def _find_free_port():
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestRankingAPI(unittest.TestCase):
    """REST API 통합 테스트."""

    @classmethod
    def setUpClass(cls):
        cls.port = _find_free_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server = HTTPServer(("127.0.0.1", cls.port), RankingHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        # 테스트마다 깨끗한 데이터를 위해 임시 파일 사용
        cls._tmp_dir = tempfile.mkdtemp()
        cls._data_path = os.path.join(cls._tmp_dir, "ranking_data.json")
        cls._backup_path = cls._data_path + ".bak"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        # 임시 파일 정리
        for f in (cls._data_path, cls._backup_path):
            if os.path.exists(f):
                os.unlink(f)
        if os.path.exists(cls._tmp_dir):
            os.rmdir(cls._tmp_dir)

    def setUp(self):
        """각 테스트 전 rate-limit 맵과 데이터 파일 초기화."""
        with _rate_limit_lock:
            _rate_limit_map.clear()

    def _post_score(self, name, score, mode="test"):
        """점수 POST 헬퍼."""
        body = json.dumps({"name": name, "score": score, "mode": mode}).encode()
        req = Request(
            f"{self.base_url}/ranking",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())

    def _get_ranking(self, path="/ranking"):
        """GET 랭킹 헬퍼."""
        req = Request(f"{self.base_url}{path}", method="GET")
        with urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())

    @patch("data_ai.ranking_server.DATA_PATH")
    @patch("data_ai.ranking_server._BACKUP_PATH")
    def test_post_and_get(self, mock_backup, mock_data):
        """점수 등록 후 GET으로 조회할 수 있어야 한다."""
        mock_data.__str__ = lambda s: self._data_path
        mock_backup.__str__ = lambda s: self._backup_path

        status, body = self._post_score("Alice", 500)
        self.assertEqual(status, 201)
        self.assertEqual(body["status"], "ok")

    def test_get_404(self):
        """존재하지 않는 경로에 GET 시 404를 반환해야 한다."""
        req = Request(f"{self.base_url}/nonexistent", method="GET")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 404)

    def test_post_invalid_json(self):
        """유효하지 않은 JSON body 시 400을 반환해야 한다."""
        req = Request(
            f"{self.base_url}/ranking",
            data=b"not json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 400)

    def test_post_wrong_content_type(self):
        """Content-Type이 json이 아니면 415를 반환해야 한다."""
        req = Request(
            f"{self.base_url}/ranking",
            data=b'{"name": "test", "score": 100}',
            headers={"Content-Type": "text/plain"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 415)

    def test_post_empty_body(self):
        """빈 body 시 에러를 반환해야 한다."""
        req = Request(
            f"{self.base_url}/ranking",
            data=b"",
            headers={"Content-Type": "application/json", "Content-Length": "0"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=5)
        self.assertIn(ctx.exception.code, (400, 411, 413))

    def test_post_non_object_json(self):
        """JSON body가 dict가 아니면 400을 반환해야 한다."""
        req = Request(
            f"{self.base_url}/ranking",
            data=b"[1, 2, 3]",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 400)

    def test_post_invalid_score_type(self):
        """score가 숫자가 아니면 400을 반환해야 한다."""
        body = json.dumps({"name": "test", "score": "not_a_number"}).encode()
        req = Request(
            f"{self.base_url}/ranking",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 400)

    def test_rate_limit(self):
        """동일 IP에서 빠른 연속 요청 시 429를 반환해야 한다."""
        # 첫 요청 성공
        body = json.dumps({"name": "Alice", "score": 100}).encode()
        req = Request(
            f"{self.base_url}/ranking",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5):
            pass

        # 즉시 두 번째 요청 → 429
        req2 = Request(
            f"{self.base_url}/ranking",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req2, timeout=5)
        self.assertEqual(ctx.exception.code, 429)

    def test_options_cors(self):
        """OPTIONS 요청에 CORS 헤더가 포함되어야 한다."""
        req = Request(f"{self.base_url}/ranking", method="OPTIONS")
        with urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.getheader("Access-Control-Allow-Origin"), "*")


if __name__ == "__main__":
    unittest.main()
