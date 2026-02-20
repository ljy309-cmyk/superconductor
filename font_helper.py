"""Pygame 한글 폰트 헬퍼 — CJK 지원 폰트 자동 탐색.

모든 Pygame 모듈에서 ``pygame.font.SysFont("Consolas", ...)`` 대신
이 모듈의 ``get_font()`` 를 사용하면 한글이 올바르게 표시됩니다.

사용법::

    from font_helper import get_font
    font = get_font(12)
    bold_font = get_font(16, bold=True)
"""

import pygame

# 한글을 지원하는 폰트 후보 목록 (우선순위순)
_CANDIDATE_FONTS: list[str] = [
    "NanumGothicCoding",       # 한글 코딩 전용 (Linux/Mac)
    "NanumGothic",             # 나눔고딕 (Linux/Mac)
    "Malgun Gothic",           # 맑은 고딕 (Windows)
    "MalgunGothic",
    "Noto Sans CJK KR",       # Noto CJK (Linux)
    "Noto Sans KR",
    "WenQuanYi Zen Hei Mono",  # CJK 모노 (Linux 기본)
    "WenQuanYi Zen Hei",
    "UnDotum",                 # 은돋움 (Linux)
    "AppleGothic",             # macOS
    "Apple SD Gothic Neo",     # macOS
    "Gulim",                   # 굴림 (Windows)
]

_resolved_family: str | None = None


def _resolve_font() -> str:
    """사용 가능한 CJK 폰트를 탐색하여 반환."""
    global _resolved_family
    if _resolved_family is not None:
        return _resolved_family

    if not pygame.font.get_init():
        pygame.font.init()

    for name in _CANDIDATE_FONTS:
        try:
            f = pygame.font.SysFont(name, 14)
            # 한글 '가' 를 렌더링해서 폭이 0이 아닌지 확인
            surf = f.render("가", True, (255, 255, 255))
            if surf.get_width() > 0 and surf.get_width() != f.render("?", True, (255, 255, 255)).get_width():
                _resolved_family = name
                return name
        except Exception:
            continue

    # 최후의 대안: pygame 기본 폰트 (한글 미지원일 수 있음)
    _resolved_family = "Consolas"
    return _resolved_family


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """한글을 지원하는 Pygame 폰트를 반환."""
    family = _resolve_font()
    return pygame.font.SysFont(family, size, bold=bold)


def get_font_family() -> str:
    """현재 선택된 폰트 패밀리 이름을 반환."""
    return _resolve_font()
