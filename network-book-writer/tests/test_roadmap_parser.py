"""로드맵 파서 테스트"""

from src.drive.roadmap_parser import Chapter, parse_roadmap, _extract_keywords


class TestParseRoadmap:
    """parse_roadmap 함수 테스트"""

    def test_parse_markdown_headings(self):
        """마크다운 헤딩 형식 파싱"""
        content = """# 네트워크 기초
- OSI 7 Layer
- TCP/IP 모델

# 데이터 링크 계층
- Ethernet
- MAC 주소
- ARP 프로토콜
"""
        chapters = parse_roadmap(content)
        assert len(chapters) == 2
        assert chapters[0].title == "네트워크 기초"
        assert chapters[0].index == 1
        assert "OSI 7 Layer" in chapters[0].subtopics
        assert chapters[1].title == "데이터 링크 계층"

    def test_parse_numbered_list(self):
        """번호 목록 형식 파싱"""
        content = """1. TCP/IP 프로토콜
- 3-way handshake
- 흐름 제어

2. UDP 프로토콜
- 비연결형 특성
- 사용 사례
"""
        chapters = parse_roadmap(content)
        assert len(chapters) == 2
        assert chapters[0].title == "TCP/IP 프로토콜"
        assert "3-way handshake" in chapters[0].subtopics

    def test_parse_empty_content(self):
        """빈 내용 파싱"""
        chapters = parse_roadmap("")
        assert chapters == []

    def test_chapter_filename(self):
        """챕터 파일명 생성"""
        chapter = Chapter(
            index=3,
            title="TCP/IP 프로토콜 기초",
            subtopics=[],
            keywords=[],
        )
        filename = chapter.filename
        assert filename.startswith("03_")
        assert filename.endswith(".md")

    def test_parse_mixed_format(self):
        """혼합 형식 파싱"""
        content = """## 라우팅 기초
- 정적 라우팅
- 동적 라우팅

## OSPF
- Area 개념
- LSA 타입
"""
        chapters = parse_roadmap(content)
        assert len(chapters) == 2


class TestExtractKeywords:
    """_extract_keywords 함수 테스트"""

    def test_extract_english_terms(self):
        """영문 기술 용어 추출"""
        keywords = _extract_keywords("TCP/IP 프로토콜", ["HTTP/2", "TLS 1.3"])
        assert "TCP/IP" in keywords
        assert "HTTP/2" in keywords

    def test_no_duplicates(self):
        """중복 키워드 제거"""
        keywords = _extract_keywords("TCP 개요", ["TCP 상세", "TCP 고급"])
        tcp_count = sum(1 for k in keywords if k.upper() == "TCP")
        assert tcp_count == 1

    def test_empty_input(self):
        """빈 입력"""
        keywords = _extract_keywords("네트워크 기초", [])
        assert isinstance(keywords, list)
