"""설정 모듈 테스트"""

import os

from src.config import Config


class TestConfig:
    """Config 클래스 테스트"""

    def test_default_values(self):
        """기본 설정값 확인"""
        config = Config()
        assert config.claude_model == "claude-opus-4-20250918"
        assert config.max_concurrent_chapters == 5
        assert config.discussion_rounds == 2
        assert config.skip_chapters == []

    def test_validate_missing_api_key(self):
        """API 키 누락 검증"""
        config = Config()
        errors = config.validate()
        assert any("ANTHROPIC_API_KEY" in e for e in errors)

    def test_validate_missing_folder_id(self):
        """폴더 ID 누락 검증"""
        config = Config(anthropic_api_key="test-key")
        errors = config.validate()
        assert any("GOOGLE_DRIVE_FOLDER_ID" in e for e in errors)

    def test_from_env(self, monkeypatch):
        """환경변수에서 설정 로드"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")
        monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "test-folder-id")
        monkeypatch.setenv("ROADMAP_FILE_ID", "test-roadmap-id")
        monkeypatch.setenv("MAX_CONCURRENT_CHAPTERS", "3")

        config = Config.from_env()
        assert config.anthropic_api_key == "test-api-key"
        assert config.google_drive_folder_id == "test-folder-id"
        assert config.max_concurrent_chapters == 3
