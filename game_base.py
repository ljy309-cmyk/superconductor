"""게임 루프 공통 유틸리티 — 종료 정리 및 난이도 선택 중복 제거.

5개 Pygame 게임 모드(qubit_chain, bb84_defense, tunneling, squid_mines,
flux_pinning)가 공유하는 보일러플레이트를 통합합니다.
"""

import pygame

from logger import get_module_logger
from theme import off_theme_change

_log = get_module_logger("game_base")


def finalize_session(
    mode: str,
    session_data: dict,
    *,
    recorder=None,
    recorder_meta=None,
    snd=None,
    theme_callback=None,
    extra_cleanup=None,
):
    """게임 종료 시 공통 정리 로직.

    play_logger · report · achievements 저장 후 리소스를 해제합니다.

    Args:
        mode: 게임 모드 이름 (예: "qubit_chain")
        session_data: 세션 통계 dict
        recorder: ReplayRecorder 인스턴스
        recorder_meta: recorder.save()에 전달할 메타데이터 dict
        snd: SoundManager 인스턴스
        theme_callback: _load_theme_colors 콜백 (off_theme_change용)
        extra_cleanup: 추가 정리 콜백 (예: 랭킹 서버 POST)
    """
    # 플레이 기록
    try:
        from data_ai.play_logger import get_logger

        get_logger().log_session(mode, session_data)
    except (ImportError, OSError, ValueError, TypeError) as e:
        _log.error("[%s] 플레이 기록 실패: %s", mode, e)

    # 보고서 생성
    try:
        from report import generate_report

        generate_report(mode, session_data)
    except (ImportError, OSError, ValueError, TypeError) as e:
        _log.error("[%s] 보고서 생성 실패: %s", mode, e)

    # 업적 확인
    try:
        from achievements import check_achievements

        new_ach = check_achievements(mode, session_data)
        for ach in new_ach:
            _log.info("[%s] Achievement unlocked: %s — %s", mode, ach["title"], ach["desc"])
    except (ImportError, KeyError, TypeError, ValueError) as e:
        _log.error("[%s] 업적 확인 실패: %s", mode, e)

    # 추가 정리 (랭킹 서버 POST 등)
    if extra_cleanup:
        try:
            extra_cleanup()
        except (OSError, ValueError, RuntimeError, TypeError) as e:
            _log.error("[%s] 추가 정리 실패: %s", mode, e)

    # 리소스 정리
    if recorder:
        recorder.save(recorder_meta)
    if snd:
        snd.quit()
    if theme_callback:
        off_theme_change(theme_callback)
    pygame.quit()


def choose_difficulty_or_quit(screen, font, preset_hud, theme_callback):
    """난이도 선택 다이얼로그 — 취소 시 pygame을 정리하고 False 반환.

    Returns:
        True: 난이도 선택 완료, False: 취소(게임 종료)
    """
    from difficulty_dialog import choose_difficulty

    chosen = choose_difficulty(screen, font)
    if chosen is None:
        off_theme_change(theme_callback)
        pygame.quit()
        return False
    preset_hud._apply_preset(chosen)
    return True
