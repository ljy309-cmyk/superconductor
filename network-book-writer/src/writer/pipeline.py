"""파이프라인 오케스트레이터 - 전체 작업 흐름 관리"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from src.ai.chapter_generator import ChapterGenerator
from src.ai.discussion import AIDiscussion
from src.config import Config
from src.drive.client import GoogleDriveClient
from src.drive.roadmap_parser import Chapter, parse_roadmap
from src.notify.push_notify import PushNotifier
from src.research.web_search import WebResearcher

logger = logging.getLogger(__name__)


class WritingPipeline:
    """네트워크 책 자동 집필 파이프라인

    전체 흐름:
    1. 구글드라이브에서 로드맵 읽기
    2. 로드맵을 챕터 목록으로 파싱
    3. 각 챕터에 대해 병렬로:
       a. 웹 리서치 수행
       b. 챕터 내용 생성
       c. 구글드라이브에 초안 업로드
    4. 각 챕터에 대해 AI 토론 및 수정
    5. 구글드라이브에서 기존 초안 삭제, 수정본 업로드
    6. 완료 알림 전송
    """

    def __init__(self, config: Config):
        self.config = config
        self.drive = GoogleDriveClient(config.google_credentials_path, config.google_token_path)
        self.researcher = WebResearcher(config.anthropic_api_key, config.claude_model)
        self.generator = ChapterGenerator(config.anthropic_api_key, config.claude_model)
        self.discussion = AIDiscussion(config.anthropic_api_key, config.claude_model)
        self.notifier = PushNotifier(config.pushover_user_key, config.pushover_api_token)

    def run(self) -> None:
        """파이프라인 실행 (동기 진입점)"""
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        """비동기 파이프라인 실행"""
        start_time = time.time()

        try:
            # 1. 구글드라이브 인증
            logger.info("=" * 60)
            logger.info("🚀 네트워크 책 자동 집필 파이프라인 시작")
            logger.info("=" * 60)

            self.drive.authenticate()

            # 2. 로드맵 읽기 및 파싱
            logger.info("\n📋 로드맵 읽기...")
            roadmap_content = self.drive.read_file(self.config.roadmap_file_id)
            chapters = parse_roadmap(roadmap_content)

            if not chapters:
                raise ValueError("로드맵에서 챕터를 찾을 수 없습니다")

            # 건너뛸 챕터 제외
            if self.config.skip_chapters:
                chapters = [c for c in chapters if c.index not in self.config.skip_chapters]

            logger.info(f"📖 총 {len(chapters)}개 챕터 처리 예정")
            book_context = roadmap_content

            # 3. 결과 저장용 폴더 생성
            draft_folder_id = self.drive.create_folder("초안", self.config.google_drive_folder_id)
            final_folder_id = self.drive.create_folder("최종본", self.config.google_drive_folder_id)

            # 4. 챕터 병렬 생성 (리서치 → 생성 → 업로드)
            logger.info("\n✍️ 챕터 병렬 생성 시작...")
            draft_results = await self._generate_chapters_parallel(chapters, book_context, draft_folder_id)

            # 5. AI 토론 및 문서 수정
            logger.info("\n🗣️ AI 토론 및 문서 수정 시작...")
            final_results = await self._discuss_and_revise_parallel(draft_results, final_folder_id)

            # 6. 초안 폴더 정리 (기존 초안 삭제)
            logger.info("\n🗑️ 초안 파일 정리...")
            for result in draft_results:
                if result.get("draft_file_id"):
                    self.drive.delete_file(result["draft_file_id"])
            self.drive.delete_file(draft_folder_id)

            # 7. 완료 알림
            elapsed = time.time() - start_time
            logger.info(f"\n✅ 파이프라인 완료! (소요 시간: {elapsed / 60:.1f}분)")
            logger.info(f"   처리된 챕터: {len(final_results)}개")

            self.notifier.notify_completion(len(final_results), elapsed)

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"\n❌ 파이프라인 오류: {e}", exc_info=True)
            self.notifier.notify_error(f"오류 발생 ({elapsed / 60:.1f}분 경과): {e}")
            raise

    async def _generate_chapters_parallel(
        self, chapters: list[Chapter], book_context: str, folder_id: str
    ) -> list[dict]:
        """챕터를 병렬로 생성 (max_concurrent 제한)"""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_chapters)
        results = []

        async def process_chapter(chapter: Chapter) -> dict:
            async with semaphore:
                return await asyncio.get_event_loop().run_in_executor(
                    ThreadPoolExecutor(max_workers=1),
                    self._generate_single_chapter,
                    chapter,
                    book_context,
                    folder_id,
                )

        tasks = [process_chapter(ch) for ch in chapters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 예외 처리
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"챕터 {chapters[i].title} 생성 실패: {result}")
            else:
                valid_results.append(result)

        return valid_results

    def _generate_single_chapter(self, chapter: Chapter, book_context: str, folder_id: str) -> dict:
        """단일 챕터 생성 (리서치 → 생성 → 업로드)"""
        logger.info(f"  [{chapter.index}] {chapter.title} - 리서치 중...")
        research_data = self.researcher.research_topic(
            topic=chapter.title,
            keywords=chapter.keywords,
            context=chapter.description,
        )

        logger.info(f"  [{chapter.index}] {chapter.title} - 생성 중...")
        content = self.generator.generate(chapter, research_data, book_context)

        logger.info(f"  [{chapter.index}] {chapter.title} - 업로드 중...")
        file_id = self.drive.upload_file(
            name=f"[초안] {chapter.filename}",
            content=content,
            folder_id=folder_id,
        )

        return {
            "chapter": chapter,
            "content": content,
            "draft_file_id": file_id,
        }

    async def _discuss_and_revise_parallel(self, draft_results: list[dict], folder_id: str) -> list[dict]:
        """AI 토론을 통한 문서 수정 (병렬)"""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_chapters)
        results = []

        async def process_discussion(draft: dict) -> dict:
            async with semaphore:
                return await asyncio.get_event_loop().run_in_executor(
                    ThreadPoolExecutor(max_workers=1),
                    self._discuss_single_chapter,
                    draft,
                    folder_id,
                )

        tasks = [process_discussion(d) for d in draft_results]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"토론 실패: {draft_results[i]['chapter'].title}: {result}")
            else:
                valid_results.append(result)

        return valid_results

    def _discuss_single_chapter(self, draft: dict, folder_id: str) -> dict:
        """단일 챕터 토론 및 수정"""
        chapter = draft["chapter"]
        content = draft["content"]

        logger.info(f"  [{chapter.index}] {chapter.title} - 토론 중...")
        discussion_result = self.discussion.discuss_and_review(
            chapter_content=content,
            chapter_title=chapter.title,
            rounds=self.config.discussion_rounds,
        )

        revised_content = discussion_result["revised_content"]

        logger.info(f"  [{chapter.index}] {chapter.title} - 최종본 업로드 중...")
        file_id = self.drive.upload_file(
            name=chapter.filename,
            content=revised_content,
            folder_id=folder_id,
        )

        return {
            "chapter": chapter,
            "final_content": revised_content,
            "final_file_id": file_id,
            "changes_summary": discussion_result["changes_summary"],
        }
