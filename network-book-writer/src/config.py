"""설정 관리 모듈 - 환경변수 로드 및 설정값 관리"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    """전체 파이프라인 설정"""

    # Anthropic API
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-4-20250918"

    # Google Drive
    google_credentials_path: str = "config/credentials.json"
    google_token_path: str = "config/token.json"
    google_drive_folder_id: str = ""
    roadmap_file_id: str = ""

    # 알림 (Pushover)
    pushover_user_key: str = ""
    pushover_api_token: str = ""

    # 동시 처리
    max_concurrent_chapters: int = 5

    # 웹 검색
    search_api_key: str = ""

    # 출력 경로
    output_dir: str = "output"

    # 토론 라운드 수
    discussion_rounds: int = 2

    # 제외할 챕터 목록 (인덱스)
    skip_chapters: list[int] = field(default_factory=list)

    @classmethod
    def from_env(cls, env_path: str | None = None) -> "Config":
        """환경변수에서 설정 로드"""
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            claude_model=os.getenv("CLAUDE_MODEL", "claude-opus-4-20250918"),
            google_credentials_path=os.getenv("GOOGLE_CREDENTIALS_PATH", "config/credentials.json"),
            google_token_path=os.getenv("GOOGLE_TOKEN_PATH", "config/token.json"),
            google_drive_folder_id=os.getenv("GOOGLE_DRIVE_FOLDER_ID", ""),
            roadmap_file_id=os.getenv("ROADMAP_FILE_ID", ""),
            pushover_user_key=os.getenv("PUSHOVER_USER_KEY", ""),
            pushover_api_token=os.getenv("PUSHOVER_API_TOKEN", ""),
            max_concurrent_chapters=int(os.getenv("MAX_CONCURRENT_CHAPTERS", "5")),
            search_api_key=os.getenv("SEARCH_API_KEY", ""),
        )

    def validate(self) -> list[str]:
        """필수 설정값 검증, 누락된 항목 목록 반환"""
        errors = []
        if not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY가 설정되지 않았습니다")
        if not self.google_drive_folder_id:
            errors.append("GOOGLE_DRIVE_FOLDER_ID가 설정되지 않았습니다")
        if not self.roadmap_file_id:
            errors.append("ROADMAP_FILE_ID가 설정되지 않았습니다")
        if not Path(self.google_credentials_path).exists():
            errors.append(f"Google 인증 파일을 찾을 수 없습니다: {self.google_credentials_path}")
        return errors
