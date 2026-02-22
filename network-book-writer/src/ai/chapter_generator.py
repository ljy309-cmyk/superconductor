"""챕터 생성 모듈 - AI를 활용한 네트워크 책 챕터 작성"""

import logging

import anthropic

from src.drive.roadmap_parser import Chapter

logger = logging.getLogger(__name__)


class ChapterGenerator:
    """AI 기반 챕터 콘텐츠 생성"""

    def __init__(self, api_key: str, model: str = "claude-opus-4-20250918"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate(self, chapter: Chapter, research_data: str, book_context: str = "") -> str:
        """챕터 내용 생성

        Args:
            chapter: 챕터 정보 (제목, 하위 주제 등)
            research_data: 웹 리서치 결과
            book_context: 책 전체 맥락 (로드맵 정보)

        Returns:
            생성된 챕터 마크다운 텍스트
        """
        prompt = self._build_generation_prompt(chapter, research_data, book_context)

        logger.info(f"챕터 생성 시작: [{chapter.index}] {chapter.title}")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=16384,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        logger.info(f"챕터 생성 완료: [{chapter.index}] {chapter.title} ({len(content)}자)")
        return content

    def _build_generation_prompt(self, chapter: Chapter, research_data: str, book_context: str) -> str:
        """챕터 생성 프롬프트 구성"""
        subtopics_str = "\n".join(f"  - {s}" for s in chapter.subtopics) if chapter.subtopics else "  (없음)"

        return f"""당신은 네트워크 기술 서적의 전문 저자입니다. 다음 정보를 바탕으로 네트워크 책의 한 챕터를 작성해주세요.

## 챕터 정보
- 챕터 번호: {chapter.index}
- 제목: {chapter.title}
- 하위 주제:
{subtopics_str}
- 설명: {chapter.description or '없음'}

## 웹 리서치 결과
{research_data}

## 책 전체 구성
{book_context or '제공되지 않음'}

## 작성 가이드라인
1. **마크다운 형식**으로 작성하세요
2. 챕터 제목은 `# {chapter.index}장. {chapter.title}` 형식으로 시작
3. 각 하위 주제를 `##` 또는 `###` 소제목으로 구성
4. 기술 용어는 처음 등장 시 설명을 추가
5. 코드 예시나 설정 예시가 있으면 코드블록으로 포함
6. 다이어그램이 필요한 부분은 ASCII art 또는 설명으로 대체
7. 각 섹션 끝에 핵심 정리 또는 요약 포함
8. RFC 번호, 프로토콜 버전 등 정확한 참조를 포함
9. 실무에서의 적용 사례나 트러블슈팅 팁 포함
10. 분량은 충분히 상세하게 (3000~8000자)

## 작성 스타일
- 전문적이면서도 이해하기 쉬운 설명
- 비유나 예시를 적절히 활용
- 단계적 설명 (기초 → 심화)
- 한국어로 작성 (기술 용어는 영문 병기)
"""
