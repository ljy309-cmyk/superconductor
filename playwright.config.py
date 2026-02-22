"""Playwright 테스트 설정 — 랭킹 서버 E2E 테스트 구성.

사용법:
    pip install playwright pytest-playwright
    playwright install chromium
    python -m pytest tests/test_e2e_playwright.py -v
"""

# Playwright pytest 설정
# pytest-playwright가 자동으로 읽는 설정 파일

PLAYWRIGHT_BROWSERS = ["chromium"]
PLAYWRIGHT_HEADLESS = True
PLAYWRIGHT_SLOW_MO = 0  # 디버깅 시 100~500ms로 설정
PLAYWRIGHT_TIMEOUT = 10000  # 기본 타임아웃 10초

# 테스트 서버 설정
TEST_SERVER_HOST = "127.0.0.1"
TEST_SERVER_PORT = 19876
