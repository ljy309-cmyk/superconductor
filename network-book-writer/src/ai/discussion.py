"""AI 토론 모듈 - 두 AI 역할이 토론하여 문서를 검증/개선"""

import logging

import anthropic

logger = logging.getLogger(__name__)


class AIDiscussion:
    """AI 모델 간 토론을 통한 문서 검증 및 개선"""

    def __init__(self, api_key: str, model: str = "claude-opus-4-20250918"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def discuss_and_review(self, chapter_content: str, chapter_title: str, rounds: int = 2) -> dict:
        """챕터에 대해 AI 토론 수행

        두 역할 (검토자/저자)이 번갈아가며 토론하여 문서를 개선합니다.

        Args:
            chapter_content: 원본 챕터 내용
            chapter_title: 챕터 제목
            rounds: 토론 라운드 수

        Returns:
            dict: {
                "revised_content": 수정된 문서,
                "discussion_log": 토론 기록,
                "changes_summary": 변경 사항 요약
            }
        """
        logger.info(f"AI 토론 시작: {chapter_title} ({rounds} 라운드)")

        discussion_log = []
        current_content = chapter_content

        for round_num in range(1, rounds + 1):
            logger.info(f"  라운드 {round_num}/{rounds}")

            # 1단계: 검토자가 문서를 리뷰하고 피드백
            review = self._reviewer_feedback(current_content, chapter_title, round_num)
            discussion_log.append({"round": round_num, "role": "검토자", "content": review})

            # 2단계: 저자가 피드백을 반영하여 문서 수정
            current_content = self._author_revise(current_content, review, chapter_title, round_num)
            discussion_log.append({"round": round_num, "role": "저자", "content": "(문서 수정 완료)"})

        # 최종 변경 요약 생성
        changes_summary = self._summarize_changes(chapter_content, current_content, chapter_title)

        logger.info(f"AI 토론 완료: {chapter_title}")

        return {
            "revised_content": current_content,
            "discussion_log": discussion_log,
            "changes_summary": changes_summary,
        }

    def _reviewer_feedback(self, content: str, title: str, round_num: int) -> str:
        """검토자 역할: 문서의 기술적 정확성, 구성, 완성도를 검토"""
        prompt = f"""당신은 네트워크 기술 분야의 전문 검토자(리뷰어)입니다.
다음 챕터를 꼼꼼히 검토하고 구체적인 피드백을 제공하세요.

## 검토 대상
- 챕터: {title}
- 토론 라운드: {round_num}

## 챕터 내용
{content}

## 검토 항목
1. **기술적 정확성**: 잘못된 정보, 부정확한 설명, 오래된 내용이 있는지
2. **완성도**: 빠진 주제, 불충분한 설명이 있는지
3. **구성/흐름**: 논리적 흐름이 자연스러운지, 구조가 적절한지
4. **코드/예시**: 코드 예시가 정확하고 실용적인지
5. **가독성**: 설명이 명확하고 이해하기 쉬운지

## 출력 형식
각 항목별로 구체적인 피드백을 제공하세요:
- [정확성] 문제점과 수정 제안
- [완성도] 추가가 필요한 내용
- [구성] 구조 개선 제안
- [코드] 코드 관련 피드백
- [가독성] 문장/표현 개선점
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    def _author_revise(self, content: str, feedback: str, title: str, round_num: int) -> str:
        """저자 역할: 검토 피드백을 반영하여 문서 수정"""
        prompt = f"""당신은 네트워크 기술 서적의 전문 저자입니다.
검토자의 피드백을 반영하여 챕터를 수정하세요.

## 수정 대상
- 챕터: {title}
- 토론 라운드: {round_num}

## 현재 챕터 내용
{content}

## 검토자 피드백
{feedback}

## 수정 가이드라인
1. 검토자가 지적한 기술적 오류를 정확하게 수정하세요
2. 부족한 내용은 보충하세요
3. 구조 개선이 필요하면 재구성하세요
4. 코드 예시의 오류를 수정하세요
5. 원래 문서의 좋은 부분은 유지하세요
6. 수정한 부분에 대해 근거를 가지고 수정하세요

## 중요
- 전체 챕터를 수정된 최종본으로 출력하세요
- 마크다운 형식을 유지하세요
- "수정했습니다" 같은 메타 코멘트 없이 순수 챕터 내용만 출력하세요
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=16384,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    def _summarize_changes(self, original: str, revised: str, title: str) -> str:
        """원본과 수정본의 차이를 요약"""
        prompt = f"""다음 두 버전의 문서를 비교하고 주요 변경 사항을 요약해주세요.

## 챕터: {title}

## 원본 (일부)
{original[:3000]}

## 수정본 (일부)
{revised[:3000]}

## 요청
주요 변경 사항을 간결하게 5줄 이내로 요약하세요.
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text
