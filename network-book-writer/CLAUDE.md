# CLAUDE.md

## 프로젝트 개요

네트워크 책 자동 집필 파이프라인 - 구글드라이브의 로드맵을 기반으로 AI가 네트워크 기술 서적을 자동 작성하는 도구

## 파이프라인 흐름

1. 구글드라이브에서 목차/로드맵 읽기
2. 로드맵을 챕터 목록으로 파싱
3. 각 챕터에 대해 병렬로: 웹 리서치 → 내용 생성 → 구글드라이브 업로드
4. AI 토론 (검토자/저자 역할)을 통한 문서 검증 및 수정
5. 구글드라이브에서 초안 삭제, 최종본만 남김
6. 완료 시 핸드폰 푸시 알림 (Pushover)

## 아키텍처

```
src/
├── main.py              # CLI 진입점
├── config.py            # 환경변수 기반 설정 관리
├── drive/
│   ├── client.py        # 구글 드라이브 API 클라이언트
│   └── roadmap_parser.py # 로드맵 파싱 (마크다운/번호목록 → Chapter 객체)
├── ai/
│   ├── chapter_generator.py  # AI 챕터 생성
│   └── discussion.py         # AI 토론 (검토자↔저자)
├── research/
│   └── web_search.py    # Anthropic web_search 도구 기반 리서치
├── notify/
│   └── push_notify.py   # Pushover 푸시 알림
└── writer/
    └── pipeline.py      # 전체 파이프라인 오케스트레이터
```

## 주요 명령어

```bash
# 실행
python -m src.main                    # 기본 실행
python -m src.main --verbose          # 상세 로그
python -m src.main --skip 1 3         # 특정 챕터 건너뛰기
python -m src.main --rounds 3         # 토론 라운드 수 조정
python -m src.main --concurrent 3     # 동시 처리 수 조정

# 테스트
python -m pytest tests/ -v

# 린트
ruff check .
ruff format .
```

## 핵심 규칙

- Python 3.10+, 줄 길이 120자
- Ruff 린터/포매터 사용
- 물리 엔진/로직과 UI 분리 (이 프로젝트에서는 API 클라이언트와 비즈니스 로직 분리)
- 환경변수는 `.env` 파일로 관리, 절대 커밋하지 않음
- 한국어 주석/docstring 사용
