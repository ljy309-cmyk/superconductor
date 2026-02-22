"""Playwright E2E 테스트 — 랭킹 서버 REST API 검증.

Flask/http.server 기반 랭킹 서버에 대해 Playwright를 사용한
E2E 테스트를 수행합니다. Playwright 미설치 시 자동 skip.

사용법:
    pip install playwright pytest-playwright
    playwright install chromium
    python -m pytest tests/test_e2e_playwright.py -v

환경 요구사항:
    - playwright Python 패키지
    - chromium 브라우저 (playwright install chromium)
"""

import json
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Playwright 가용성 확인
try:
    from playwright.sync_api import sync_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# 서버 가용성 확인
try:
    from http.server import HTTPServer

    from data_ai.ranking_server import HOST, PORT, RankingHandler, stop_server  # noqa: F401

    HAS_SERVER = True
except ImportError:
    HAS_SERVER = False


def _start_test_server(port: int) -> HTTPServer:
    """테스트용 서버를 별도 스레드에서 시작."""
    server = HTTPServer(("127.0.0.1", port), RankingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)  # 서버 시작 대기
    return server


@unittest.skipUnless(HAS_PLAYWRIGHT and HAS_SERVER, "playwright 또는 서버 모듈 미설치")
class TestRankingAPIWithPlaywright(unittest.TestCase):
    """Playwright를 사용한 랭킹 API E2E 테스트."""

    _server = None
    _port = 19876  # 테스트용 포트 (충돌 방지)
    _base_url = ""

    @classmethod
    def setUpClass(cls):
        """테스트 서버 시작."""
        cls._base_url = f"http://127.0.0.1:{cls._port}"
        try:
            cls._server = _start_test_server(cls._port)
        except OSError:
            cls._server = None

    @classmethod
    def tearDownClass(cls):
        """테스트 서버 종료."""
        if cls._server:
            cls._server.shutdown()

    def setUp(self):
        if not self._server:
            self.skipTest("테스트 서버 시작 실패")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._context = self._browser.new_context()

    def tearDown(self):
        if hasattr(self, "_context"):
            self._context.close()
        if hasattr(self, "_browser"):
            self._browser.close()
        if hasattr(self, "_pw"):
            self._pw.stop()

    def test_get_ranking_returns_json(self):
        """GET /ranking이 JSON 배열을 반환."""
        page = self._context.new_page()
        response = page.goto(f"{self._base_url}/ranking")
        self.assertEqual(response.status, 200)
        self.assertIn("application/json", response.headers.get("content-type", ""))
        data = response.json()
        self.assertIsInstance(data, list)
        page.close()

    def test_get_ranking_all(self):
        """GET /ranking/all이 전체 기록을 반환."""
        page = self._context.new_page()
        response = page.goto(f"{self._base_url}/ranking/all")
        self.assertEqual(response.status, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        page.close()

    def test_get_404(self):
        """존재하지 않는 경로는 404."""
        page = self._context.new_page()
        response = page.goto(f"{self._base_url}/nonexistent")
        self.assertEqual(response.status, 404)
        page.close()

    def test_post_and_get_ranking(self):
        """POST /ranking → GET /ranking으로 점수 등록 및 조회."""
        page = self._context.new_page()

        # POST 요청 (Playwright의 API request 사용)
        api = self._context.request
        post_response = api.post(
            f"{self._base_url}/ranking",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"name": "E2E_TestUser", "score": 99.5, "mode": "qubit_chain"}),
        )
        self.assertEqual(post_response.status, 201)
        post_data = post_response.json()
        self.assertEqual(post_data["status"], "ok")
        self.assertIn("rank", post_data)

        # GET으로 확인
        get_response = api.get(f"{self._base_url}/ranking/all")
        all_data = get_response.json()
        names = [r["name"] for r in all_data]
        self.assertIn("E2E_TestUser", names)

        page.close()

    def test_post_invalid_json(self):
        """잘못된 JSON body는 400."""
        api = self._context.request
        response = api.post(
            f"{self._base_url}/ranking",
            headers={"Content-Type": "application/json"},
            data="not json",
        )
        self.assertEqual(response.status, 400)

    def test_post_missing_content_type(self):
        """Content-Type 누락 시 415."""
        api = self._context.request
        response = api.post(
            f"{self._base_url}/ranking",
            headers={"Content-Type": "text/plain"},
            data=json.dumps({"name": "test", "score": 1}),
        )
        self.assertEqual(response.status, 415)


# ═══════════════════════════════════════════════════════════
# Playwright 없이 HTTP 수준에서 동작하는 경량 E2E 테스트
# (urllib만 사용 — 항상 실행 가능)
# ═══════════════════════════════════════════════════════════


@unittest.skipUnless(HAS_SERVER, "서버 모듈 미설치")
class TestRankingAPILightweight(unittest.TestCase):
    """urllib 기반 경량 E2E 테스트 (Playwright 불필요)."""

    _server = None
    _port = 19877

    @classmethod
    def setUpClass(cls):
        cls._base_url = f"http://127.0.0.1:{cls._port}"
        try:
            cls._server = _start_test_server(cls._port)
        except OSError:
            cls._server = None

    @classmethod
    def tearDownClass(cls):
        if cls._server:
            cls._server.shutdown()

    def setUp(self):
        if not self._server:
            self.skipTest("테스트 서버 시작 실패")

    def test_get_ranking(self):
        """GET /ranking 정상 응답."""
        from urllib.request import urlopen

        with urlopen(f"{self._base_url}/ranking", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read())
            self.assertIsInstance(data, list)

    def test_get_ranking_all(self):
        """GET /ranking/all 정상 응답."""
        from urllib.request import urlopen

        with urlopen(f"{self._base_url}/ranking/all", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read())
            self.assertIsInstance(data, list)

    def test_post_score(self):
        """POST /ranking 점수 등록."""
        from urllib.request import Request, urlopen

        body = json.dumps({"name": "LW_TestUser", "score": 42.0, "mode": "tunneling"}).encode()
        req = Request(
            f"{self._base_url}/ranking",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 201)
            data = json.loads(resp.read())
            self.assertEqual(data["status"], "ok")

    def test_options_cors(self):
        """OPTIONS 요청에 CORS 헤더 포함."""
        from urllib.request import Request, urlopen

        req = Request(f"{self._base_url}/ranking", method="OPTIONS")
        with urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")


if __name__ == "__main__":
    unittest.main()
