"""네트워크 책 자동 집필 파이프라인 - 메인 진입점"""

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from src.config import Config
from src.writer.pipeline import WritingPipeline

console = Console()


def setup_logging(verbose: bool = False) -> None:
    """로깅 설정"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def main() -> None:
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="네트워크 책 자동 집필 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  book-writer                          # 기본 실행
  book-writer --env .env.production    # 특정 환경 파일 사용
  book-writer --verbose                # 상세 로그 출력
  book-writer --dry-run                # 실제 업로드 없이 테스트
  book-writer --skip 1 3 5             # 특정 챕터 건너뛰기
        """,
    )

    parser.add_argument("--env", type=str, default=None, help="환경변수 파일 경로 (기본: .env)")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 로그 출력")
    parser.add_argument("--dry-run", action="store_true", help="구글드라이브 업로드 없이 로컬 테스트")
    parser.add_argument("--skip", type=int, nargs="*", default=[], help="건너뛸 챕터 번호들")
    parser.add_argument("--rounds", type=int, default=None, help="AI 토론 라운드 수 (기본: 2)")
    parser.add_argument("--concurrent", type=int, default=None, help="동시 처리 챕터 수 (기본: 5)")

    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # 설정 로드
    config = Config.from_env(args.env)

    # CLI 인자로 설정 오버라이드
    if args.skip:
        config.skip_chapters = args.skip
    if args.rounds:
        config.discussion_rounds = args.rounds
    if args.concurrent:
        config.max_concurrent_chapters = args.concurrent

    # 설정 검증
    if not args.dry_run:
        errors = config.validate()
        if errors:
            console.print("\n[bold red]❌ 설정 오류:[/bold red]")
            for error in errors:
                console.print(f"  • {error}")
            console.print("\n[dim].env.example 파일을 참고하여 .env 파일을 설정해주세요.[/dim]")
            sys.exit(1)

    # 실행 정보 출력
    console.print("\n[bold cyan]📚 네트워크 책 자동 집필 파이프라인[/bold cyan]")
    console.print(f"  모델: {config.claude_model}")
    console.print(f"  동시 처리: {config.max_concurrent_chapters}개")
    console.print(f"  토론 라운드: {config.discussion_rounds}회")
    if config.skip_chapters:
        console.print(f"  건너뛸 챕터: {config.skip_chapters}")
    if args.dry_run:
        console.print("  [yellow]⚠ DRY RUN 모드 (구글드라이브 업로드 생략)[/yellow]")
    console.print()

    # 파이프라인 실행
    try:
        pipeline = WritingPipeline(config)
        pipeline.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ 사용자가 중단했습니다.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]❌ 실행 오류: {e}[/bold red]")
        logger.exception("파이프라인 실행 중 오류 발생")
        sys.exit(1)


if __name__ == "__main__":
    main()
