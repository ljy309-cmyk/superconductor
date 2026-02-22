"""웹 검색 모듈 - Anthropic API의 web_search 도구를 활용한 리서치"""

import logging

import anthropic

logger = logging.getLogger(__name__)


class WebResearcher:
    """웹 검색 기반 리서치 수행"""

    def __init__(self, api_key: str, model: str = "claude-opus-4-20250918"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def research_topic(self, topic: str, keywords: list[str], context: str = "") -> str:
        """주제에 대한 웹 리서치 수행 후 요약 반환

        Anthropic API의 web_search 도구를 사용하여 최신 정보를 검색하고
        네트워크 관련 기술 내용을 수집합니다.
        """
        search_queries = [topic] + keywords[:3]  # 주제 + 상위 키워드 3개
        prompt = self._build_research_prompt(topic, keywords, context, search_queries)

        logger.info(f"웹 리서치 시작: {topic}")

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 10,
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )

        # 응답에서 텍스트 추출
        result_text = ""
        for block in response.content:
            if block.type == "text":
                result_text += block.text

        logger.info(f"웹 리서치 완료: {topic} ({len(result_text)}자)")
        return result_text

    def _build_research_prompt(
        self, topic: str, keywords: list[str], context: str, search_queries: list[str]
    ) -> str:
        """리서치 프롬프트 생성"""
        keywords_str = ", ".join(keywords) if keywords else "없음"
        queries_str = "\n".join(f"- {q}" for q in search_queries)

        prompt = f"""당신은 네트워크 기술 전문가입니다. 다음 주제에 대해 웹 검색을 수행하고 정확한 기술 정보를 수집해주세요.

## 리서치 주제
{topic}

## 관련 키워드
{keywords_str}

## 검색할 쿼리
{queries_str}

## 요청사항
1. 위 쿼리들을 검색하여 최신 기술 정보를 수집하세요
2. 네트워크 프로토콜, 표준, RFC 관련 정보를 우선적으로 수집하세요
3. 실제 사용 사례와 모범 사례도 포함하세요
4. 수집한 정보를 체계적으로 정리하여 반환하세요
5. 출처 URL도 함께 기록하세요

## 출력 형식
- 핵심 개념 설명
- 기술적 세부사항
- 실제 적용 사례
- 참고 자료 (URL)
"""
        if context:
            prompt += f"\n## 추가 컨텍스트\n{context}\n"

        return prompt
