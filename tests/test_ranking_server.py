"""ranking_server 단위 테스트 — rate-limit 정리 로직 및 기본 동작."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "data_ai"))


class TestCheckRateLimit:
    """_check_rate_limit 함수 테스트."""

    def _import_module(self):
        from data_ai.ranking_server import _check_rate_limit, _rate_limit_lock, _rate_limit_map

        return _check_rate_limit, _rate_limit_map, _rate_limit_lock

    def _clear_map(self):
        _, rate_map, lock = self._import_module()
        with lock:
            rate_map.clear()

    def test_first_request_allowed(self):
        """첫 요청은 항상 허용되어야 한다."""
        self._clear_map()
        check, _, _ = self._import_module()
        assert check("192.168.0.1") is True

    def test_rapid_request_denied(self):
        """동일 IP의 빠른 연속 요청은 거부되어야 한다."""
        self._clear_map()
        check, _, _ = self._import_module()
        check("10.0.0.1")
        assert check("10.0.0.1") is False

    def test_different_ips_allowed(self):
        """서로 다른 IP의 동시 요청은 허용되어야 한다."""
        self._clear_map()
        check, _, _ = self._import_module()
        assert check("10.0.0.1") is True
        assert check("10.0.0.2") is True

    def test_stale_entries_cleaned(self):
        """100개 초과 시 60초 이전 항목만 정리되어야 한다."""
        self._clear_map()
        check, rate_map, lock = self._import_module()

        now = time.time()
        # 101개의 오래된 항목(70초 전) 삽입
        with lock:
            for i in range(101):
                rate_map[f"stale-{i}"] = now - 70

        # 새 요청 → 정리 트리거
        result = check("fresh-ip")
        assert result is True

        # 오래된 항목은 정리되고 fresh-ip만 남아야 한다
        with lock:
            assert "fresh-ip" in rate_map
            stale_remaining = [k for k in rate_map if k.startswith("stale-")]
            assert len(stale_remaining) == 0

    def test_recent_entries_preserved(self):
        """100개 초과 시 최근 항목(60초 이내)은 보존되어야 한다."""
        self._clear_map()
        check, rate_map, lock = self._import_module()

        now = time.time()
        with lock:
            # 50개 오래된 항목
            for i in range(50):
                rate_map[f"stale-{i}"] = now - 70
            # 55개 최근 항목
            for i in range(55):
                rate_map[f"recent-{i}"] = now - 10

        # 총 105개 → 정리 트리거
        check("trigger-ip")

        with lock:
            stale_remaining = [k for k in rate_map if k.startswith("stale-")]
            recent_remaining = [k for k in rate_map if k.startswith("recent-")]
            assert len(stale_remaining) == 0
            assert len(recent_remaining) == 55


class TestSanitizeStr:
    """_sanitize_str 함수 테스트."""

    def test_normal_string(self):
        from data_ai.ranking_server import _sanitize_str

        assert _sanitize_str("hello") == "hello"

    def test_max_length(self):
        from data_ai.ranking_server import _sanitize_str

        result = _sanitize_str("a" * 100, max_len=10)
        assert len(result) == 10

    def test_control_chars_removed(self):
        from data_ai.ranking_server import _sanitize_str

        result = _sanitize_str("hello\x00world\x01")
        assert result == "helloworld"
