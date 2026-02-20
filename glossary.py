"""용어집 오버레이 — 물리 용어 정의 + 수식 참조.

G 키로 토글하며, Up/Down 키로 스크롤합니다.

사용법:
    from glossary import GlossaryOverlay
    glossary = GlossaryOverlay()

    # 이벤트 루프:
    glossary.handle_event(event)

    # 렌더링:
    glossary.draw(screen, font)
"""

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore[assignment]

from i18n import t

# ── 용어집 데이터 ────────────────────────────────────
# 각 항목: {"term": 한글(영문), "def": 설명, "formula": 수식(선택)}
_GLOSSARY_ENTRIES: list[dict] = [
    # ── 양자역학 기초 ──
    {
        "category": "양자역학 기초  Quantum Basics",
        "term": "파동함수  Wave Function  ψ(x)",
        "def": "입자의 양자 상태를 기술하는 함수.\n|ψ(x)|² = 위치 x에서 입자를 발견할 확률 밀도.",
        "formula": "ψ(x) = Ae^(ikx) + Be^(-ikx)  (자유 입자)",
    },
    {
        "term": "확률진폭  Probability Amplitude",
        "def": "파동함수의 값 ψ(x). 복소수이며,\n절대값의 제곱 |ψ|²이 확률. 간섭 현상의 원인.",
    },
    {
        "term": "양자 중첩  Superposition",
        "def": "큐비트가 |0⟩과 |1⟩ 상태를 동시에 가지는 현상.\n관측 시 하나의 상태로 '붕괴'(collapse).",
        "formula": "|ψ⟩ = α|0⟩ + β|1⟩,  |α|²+|β|²=1",
    },
    {
        "term": "블로흐 구  Bloch Sphere",
        "def": "단일 큐비트의 순수 상태를 단위 구 표면의\n점으로 표현. 북극=|0⟩, 남극=|1⟩.",
        "formula": "|ψ⟩ = cos(θ/2)|0⟩ + e^(iφ)sin(θ/2)|1⟩",
    },
    # ── 터널링 ──
    {
        "category": "양자 터널링  Quantum Tunneling",
        "term": "포텐셜 장벽  Potential Barrier",
        "def": "입자의 운동에너지(E)보다 높은 퍼텐셜(V) 영역.\n고전적으로 통과 불가, 양자적으로 투과 가능.",
    },
    {
        "term": "투과계수  Transmission Coefficient  T",
        "def": "입자가 장벽을 투과할 확률.\n장벽 두께(L)와 높이(V-E)에 지수적으로 의존.",
        "formula": "T ≈ e^(−2κL)",
    },
    {
        "term": "감쇠상수  Decay Constant  κ",
        "def": "장벽 내부에서 파동함수가 감쇠하는 비율.\n장벽이 높을수록(V-E↑) κ가 커져 투과 확률 감소.",
        "formula": "κ = √(2m(V−E)) / ℏ",
    },
    {
        "term": "지수감쇠  Exponential Decay",
        "def": "장벽 내부에서 파동함수 진폭이 e^(−κx)로\n급격히 줄어드는 현상. 장벽이 두꺼우면 거의 0에 수렴.",
        "formula": "ψ_barrier(x) ~ e^(−κx)",
    },
    {
        "term": "에바네센트파  Evanescent Wave",
        "def": "장벽 내부의 비진행 파동. 진폭은 감쇠하지만\n장벽 너머에서 다시 진행파로 전환 → 터널링 발생.",
    },
    # ── 확률 해석 ──
    {
        "category": "확률 해석  Probability Theory",
        "term": "보른 규칙  Born Rule",
        "def": "측정 시 특정 결과를 얻을 확률 = |⟨결과|ψ⟩|².\n양자역학의 확률 해석의 핵심 공준.",
        "formula": "P(x) = |ψ(x)|²",
    },
    {
        "term": "대수의 법칙  Law of Large Numbers",
        "def": "시행 횟수가 증가하면 실측 빈도가\n이론 확률값으로 수렴하는 통계적 법칙.",
    },
    {
        "term": "기대값  Expectation Value",
        "def": "관측량의 평균 측정값.\n무한 반복 측정 시 수렴하는 값.",
        "formula": "⟨A⟩ = ⟨ψ|A|ψ⟩",
    },
]

# ── 렌더링 상수 ──────────────────────────────────────
_CLR_BG = (30, 30, 46)
_CLR_BORDER = (137, 180, 250)
_CLR_CATEGORY = (137, 180, 250)
_CLR_TERM = (249, 226, 175)
_CLR_DEF = (205, 214, 244)
_CLR_FORMULA = (203, 166, 247)
_CLR_HINT = (88, 91, 112)
_LINE_H = 16
_SCROLL_STEP = 3  # 스크롤 한 번에 이동할 줄 수


def _build_lines() -> list[tuple[str, tuple[int, int, int]]]:
    """용어집 항목을 (텍스트, 색상) 리스트로 변환."""
    lines: list[tuple[str, tuple[int, int, int]]] = []
    for entry in _GLOSSARY_ENTRIES:
        # 카테고리 헤더
        if "category" in entry:
            if lines:
                lines.append(("", _CLR_DEF))  # 빈 줄 구분
            lines.append((f"━━ {entry['category']} ━━", _CLR_CATEGORY))
            lines.append(("", _CLR_DEF))

        # 용어
        lines.append((f"▸ {entry['term']}", _CLR_TERM))

        # 정의 (줄 바꿈 지원)
        for def_line in entry["def"].split("\n"):
            lines.append((f"    {def_line}", _CLR_DEF))

        # 수식
        if "formula" in entry:
            lines.append((f"    ▹ {entry['formula']}", _CLR_FORMULA))

        lines.append(("", _CLR_DEF))  # 항목 간 빈 줄

    return lines


class GlossaryOverlay:
    """G 키로 토글하는 용어집 오버레이."""

    def __init__(self):
        self._lines = _build_lines()
        self.visible = False
        self.scroll = 0

    @property
    def _max_scroll(self):
        return max(0, len(self._lines) - 20)

    def handle_event(self, event) -> bool:
        """이벤트 처리. G로 토글, Up/Down으로 스크롤."""
        if pygame is None:
            return False
        if event.type != pygame.KEYDOWN:
            return False

        if event.key == pygame.K_g and not self.visible:
            self.visible = True
            self.scroll = 0
            return True

        if not self.visible:
            return False

        if event.key in (pygame.K_g, pygame.K_ESCAPE):
            self.visible = False
            return True
        if event.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
            self.scroll = min(self._max_scroll, self.scroll + _SCROLL_STEP)
            return True
        if event.key in (pygame.K_UP, pygame.K_PAGEUP):
            self.scroll = max(0, self.scroll - _SCROLL_STEP)
            return True

        return False

    def draw(self, screen, font):
        """용어집 오버레이 렌더링."""
        if pygame is None:
            return
        if not self.visible:
            return

        w, h = screen.get_size()

        # 반투명 배경
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))

        # 박스
        box_w = min(580, w - 60)
        box_h = min(480, h - 60)
        box_x = (w - box_w) // 2
        box_y = (h - box_h) // 2

        pygame.draw.rect(screen, _CLR_BG, (box_x, box_y, box_w, box_h), border_radius=10)
        pygame.draw.rect(screen, _CLR_BORDER, (box_x, box_y, box_w, box_h), 2, border_radius=10)

        # 타이틀
        title = font.render(t("glossary_title"), True, _CLR_CATEGORY)
        screen.blit(title, (box_x + box_w // 2 - title.get_width() // 2, box_y + 10))

        # 스크롤 인디케이터
        total = len(self._lines)
        if total > 0:
            indicator = f"({self.scroll + 1}–{min(self.scroll + 24, total)}/{total})"
            ind_surf = font.render(indicator, True, _CLR_HINT)
            screen.blit(ind_surf, (box_x + box_w - ind_surf.get_width() - 12, box_y + 10))

        # 본문 렌더링
        ty = box_y + 30
        visible_lines = self._lines[self.scroll : self.scroll + 26]
        for text, color in visible_lines:
            if text and ty < box_y + box_h - 30:
                surf = font.render(text, True, color)
                screen.blit(surf, (box_x + 16, ty))
            ty += _LINE_H
            if ty >= box_y + box_h - 30:
                break

        # 하단 네비게이션 힌트
        nav = t("glossary_nav_hint")
        nav_surf = font.render(nav, True, _CLR_HINT)
        screen.blit(nav_surf, (box_x + box_w // 2 - nav_surf.get_width() // 2, box_y + box_h - 22))
