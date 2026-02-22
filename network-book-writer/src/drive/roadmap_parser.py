"""로드맵/목차 파싱 모듈 - 구글드라이브에서 읽어온 로드맵을 챕터 목록으로 변환"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    """챕터 정보"""

    index: int
    title: str
    subtopics: list[str]
    keywords: list[str]
    description: str = ""

    @property
    def filename(self) -> str:
        """파일명 생성 (예: 01_TCP_IP_기초.md)"""
        safe_title = re.sub(r"[^\w가-힣\s]", "", self.title)
        safe_title = safe_title.strip().replace(" ", "_")
        return f"{self.index:02d}_{safe_title}.md"


def parse_roadmap(content: str) -> list[Chapter]:
    """로드맵 텍스트를 챕터 목록으로 파싱

    지원하는 형식:
    - 마크다운 헤딩 (# 또는 ##)
    - 번호 목록 (1. 2. 3.)
    - 하위 항목은 - 또는 * 로 표시
    """
    chapters = []
    current_chapter = None
    current_subtopics = []

    lines = content.strip().split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 마크다운 헤딩 또는 번호 목록 → 새 챕터
        chapter_match = re.match(r"^(?:#{1,2}\s+|(\d+)[.)]\s+)(.+)", stripped)
        if chapter_match:
            # 이전 챕터 저장
            if current_chapter:
                current_chapter.subtopics = current_subtopics
                current_chapter.keywords = _extract_keywords(current_chapter.title, current_subtopics)
                chapters.append(current_chapter)

            title = chapter_match.group(2).strip()
            current_chapter = Chapter(
                index=len(chapters) + 1,
                title=title,
                subtopics=[],
                keywords=[],
            )
            current_subtopics = []
            continue

        # 하위 항목 (- 또는 *)
        subtopic_match = re.match(r"^\s*[-*]\s+(.+)", stripped)
        if subtopic_match and current_chapter:
            current_subtopics.append(subtopic_match.group(1).strip())
            continue

        # 설명 텍스트
        if current_chapter and stripped:
            if current_chapter.description:
                current_chapter.description += " " + stripped
            else:
                current_chapter.description = stripped

    # 마지막 챕터 저장
    if current_chapter:
        current_chapter.subtopics = current_subtopics
        current_chapter.keywords = _extract_keywords(current_chapter.title, current_subtopics)
        chapters.append(current_chapter)

    logger.info(f"로드맵 파싱 완료: {len(chapters)}개 챕터 발견")
    return chapters


def _extract_keywords(title: str, subtopics: list[str]) -> list[str]:
    """챕터 제목과 하위 주제에서 검색 키워드 추출"""
    keywords = []

    # 제목에서 키워드 추출
    # 영문 기술 용어 추출
    english_terms = re.findall(r"[A-Za-z][A-Za-z0-9/.-]+", title)
    keywords.extend(english_terms)

    # 하위 주제에서도 추출
    for subtopic in subtopics:
        terms = re.findall(r"[A-Za-z][A-Za-z0-9/.-]+", subtopic)
        keywords.extend(terms)

    # 중복 제거
    seen = set()
    unique_keywords = []
    for kw in keywords:
        lower = kw.lower()
        if lower not in seen:
            seen.add(lower)
            unique_keywords.append(kw)

    return unique_keywords
