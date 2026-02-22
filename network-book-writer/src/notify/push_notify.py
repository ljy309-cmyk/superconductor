"""알림 모듈 - 작업 완료 시 핸드폰으로 푸시 알림 전송"""

import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class PushNotifier:
    """Pushover를 통한 핸드폰 푸시 알림"""

    PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"

    def __init__(self, user_key: str, api_token: str):
        self.user_key = user_key
        self.api_token = api_token

    def send(self, title: str, message: str, priority: int = 0) -> bool:
        """푸시 알림 전송

        Args:
            title: 알림 제목
            message: 알림 본문
            priority: 우선순위 (-2~2, 0=보통, 1=높음, 2=긴급)

        Returns:
            전송 성공 여부
        """
        if not self.user_key or not self.api_token:
            logger.warning("Pushover 인증 정보가 없어 알림을 건너뜁니다")
            return False

        payload = {
            "token": self.api_token,
            "user": self.user_key,
            "title": title,
            "message": message,
            "priority": priority,
        }

        try:
            response = requests.post(self.PUSHOVER_API_URL, data=payload, timeout=30)
            response.raise_for_status()
            logger.info(f"푸시 알림 전송 완료: {title}")
            return True
        except requests.RequestException as e:
            logger.error(f"푸시 알림 전송 실패: {e}")
            return False

    def notify_completion(self, total_chapters: int, elapsed_seconds: float) -> bool:
        """파이프라인 완료 알림"""
        elapsed_min = elapsed_seconds / 60
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        title = "📚 네트워크 책 집필 완료!"
        message = (
            f"완료 시각: {now}\n"
            f"처리 챕터: {total_chapters}개\n"
            f"소요 시간: {elapsed_min:.1f}분\n"
            f"모든 챕터의 생성, 토론, 수정이 완료되었습니다."
        )

        return self.send(title, message, priority=1)

    def notify_error(self, error_message: str) -> bool:
        """에러 발생 알림"""
        title = "⚠️ 네트워크 책 집필 오류"
        return self.send(title, error_message, priority=1)
