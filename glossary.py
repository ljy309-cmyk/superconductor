"""물리 용어 사전(Glossary) 오버레이.

모든 Pygame 게임 모듈에서 G키를 누르면 반투명 오버레이가 나타나
물리/양자 핵심 용어의 정의·수식·카테고리를 확인할 수 있습니다.

사용법:
    from glossary import GlossaryOverlay
    glossary = GlossaryOverlay()

    # 이벤트 루프:
    glossary.handle_event(event)

    # 렌더링 (맨 마지막에):
    glossary.draw(screen, font)
"""

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore[assignment]

from i18n import t
from quantum.ui_common import draw_page_dots, page_dots_width, wrap_text
from theme import get_pg_theme, is_high_contrast, is_reduced_motion

# ── 용어 정의 ────────────────────────────────────────────
# (term_id, category_key)  →  locale keys: gl_{id}, gl_{id}_def, gl_{id}_formula

_CATEGORY_KEYS = [
    "glossary_cat_all",
    "glossary_cat_quantum",
    "glossary_cat_superconductor",
    "glossary_cat_computing",
    "glossary_cat_crypto",
]

_TERMS: list[tuple[str, str]] = [
    # (term_id, category_key)
    # ── Quantum Mechanics ──
    ("superposition", "glossary_cat_quantum"),
    ("entanglement", "glossary_cat_quantum"),
    ("tunneling", "glossary_cat_quantum"),
    ("measurement", "glossary_cat_quantum"),
    ("bloch_sphere", "glossary_cat_quantum"),
    ("bell_state", "glossary_cat_quantum"),
    ("chsh", "glossary_cat_quantum"),
    ("teleportation", "glossary_cat_quantum"),
    ("no_cloning", "glossary_cat_quantum"),
    ("decoherence", "glossary_cat_quantum"),
    # ── Superconductor Physics ──
    ("cooper_pair", "glossary_cat_superconductor"),
    ("bcs_theory", "glossary_cat_superconductor"),
    ("energy_gap", "glossary_cat_superconductor"),
    ("meissner", "glossary_cat_superconductor"),
    ("flux_pinning", "glossary_cat_superconductor"),
    ("josephson", "glossary_cat_superconductor"),
    ("squid_sensor", "glossary_cat_superconductor"),
    ("phase_transition", "glossary_cat_superconductor"),
    ("critical_temp", "glossary_cat_superconductor"),
    ("flux_quantum", "glossary_cat_superconductor"),
    # ── Quantum Computing ──
    ("qubit", "glossary_cat_computing"),
    ("quantum_gate", "glossary_cat_computing"),
    ("hadamard", "glossary_cat_computing"),
    ("pauli_gates", "glossary_cat_computing"),
    ("cnot", "glossary_cat_computing"),
    ("shor", "glossary_cat_computing"),
    ("grover", "glossary_cat_computing"),
    ("qec", "glossary_cat_computing"),
    ("qft", "glossary_cat_computing"),
    # ── Quantum Cryptography ──
    ("qkd", "glossary_cat_crypto"),
    ("bb84", "glossary_cat_crypto"),
    ("e91", "glossary_cat_crypto"),
    ("qber", "glossary_cat_crypto"),
    ("privacy_amp", "glossary_cat_crypto"),
    ("ghz_state", "glossary_cat_crypto"),
    ("decoy_state", "glossary_cat_crypto"),
    ("otp", "glossary_cat_crypto"),
    ("rsa", "glossary_cat_crypto"),
]

TERMS_PER_PAGE = 4


class GlossaryOverlay:
    """G키 물리 용어 사전 오버레이."""

    def __init__(self):
        self.visible = False
        self._cat_idx = 0          # 0 = All
        self._page = 0
        self._search_text = ""
        self._search_active = False
        self._filtered: list[tuple[str, str]] = list(_TERMS)

    # ── helpers ────────────────────────────────────────────

    def _apply_filter(self):
        cat_key = _CATEGORY_KEYS[self._cat_idx]
        result = []
        for tid, tcat in _TERMS:
            if cat_key != "glossary_cat_all" and tcat != cat_key:
                continue
            if self._search_text:
                name = t(f"gl_{tid}").lower()
                defn = t(f"gl_{tid}_def").lower()
                query = self._search_text.lower()
                if query not in name and query not in defn:
                    continue
            result.append((tid, tcat))
        self._filtered = result
        total_pages = max(1, (len(self._filtered) + TERMS_PER_PAGE - 1) // TERMS_PER_PAGE)
        self._page = max(0, min(self._page, total_pages - 1))

    def _page_items(self):
        start = self._page * TERMS_PER_PAGE
        return self._filtered[start:start + TERMS_PER_PAGE]

    def _total_pages(self):
        return max(1, (len(self._filtered) + TERMS_PER_PAGE - 1) // TERMS_PER_PAGE)

    # ── event handling ────────────────────────────────────

    def handle_event(self, event) -> bool:
        """G키로 토글. True 반환 시 이벤트 소비됨."""
        if event.type != pygame.KEYDOWN:
            return False

        # G키 토글 (검색 모드가 아닐 때만)
        if event.key == pygame.K_g and not self._search_active:
            self.visible = not self.visible
            if self.visible:
                self._apply_filter()
            return True

        if not self.visible:
            return False

        # ESC: 검색 중이면 검색 취소, 아니면 닫기
        if event.key == pygame.K_ESCAPE:
            if self._search_active:
                self._search_active = False
                self._search_text = ""
                self._apply_filter()
            else:
                self.visible = False
            return True

        # / 키: 검색 모드 토글
        if event.key == pygame.K_SLASH and not self._search_active:
            self._search_active = True
            self._search_text = ""
            return True

        # 검색 모드 입력 처리
        if self._search_active:
            if event.key == pygame.K_RETURN:
                self._search_active = False
                return True
            elif event.key == pygame.K_BACKSPACE:
                self._search_text = self._search_text[:-1]
                self._page = 0
                self._apply_filter()
                return True
            elif event.unicode and event.unicode.isprintable() and event.unicode != "/":
                self._search_text += event.unicode
                self._page = 0
                self._apply_filter()
                return True
            return True

        # 카테고리 전환: Left/Right
        if event.key == pygame.K_LEFT:
            self._cat_idx = (self._cat_idx - 1) % len(_CATEGORY_KEYS)
            self._page = 0
            self._apply_filter()
            return True
        if event.key == pygame.K_RIGHT:
            self._cat_idx = (self._cat_idx + 1) % len(_CATEGORY_KEYS)
            self._page = 0
            self._apply_filter()
            return True

        # 페이지 네비게이션
        if event.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
            if self._page < self._total_pages() - 1:
                self._page += 1
            return True
        if event.key in (pygame.K_UP, pygame.K_PAGEUP):
            if self._page > 0:
                self._page -= 1
            return True

        return False  # 처리하지 않은 키는 다른 핸들러에 전달

    # ── rendering ─────────────────────────────────────────

    def draw(self, screen, font):
        """오버레이 렌더링."""
        if pygame is None:
            return
        pg = get_pg_theme()
        hc = is_high_contrast()
        reduced = is_reduced_motion()

        if not self.visible:
            # G키 힌트 작게 표시 (F1 힌트 왼쪽에)
            hint = font.render(t("glossary_hint"), True, pg.SUBTEXT)
            f1_hint = font.render(t("help_f1_hint"), True, pg.SUBTEXT)
            x = screen.get_width() - f1_hint.get_width() - hint.get_width() - 20
            screen.blit(hint, (x, 4))
            return

        w, h = screen.get_size()
        if w <= 0 or h <= 0:
            return

        # 반투명 배경
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))

        # 메인 박스
        box_w = min(700, w - 40)
        box_h = min(580, h - 40)
        box_x = (w - box_w) // 2
        box_y = (h - box_h) // 2

        border_w = 2 if hc else 1
        pygame.draw.rect(screen, pg.BG,
                         (box_x, box_y, box_w, box_h), border_radius=10)
        pygame.draw.rect(screen, pg.ACCENT_BLUE,
                         (box_x, box_y, box_w, box_h), border_w + 1,
                         border_radius=10)

        ty = box_y + 14

        # ── 제목 ──
        title_surf = font.render(t("glossary_title"), True, pg.ACCENT_BLUE)
        screen.blit(title_surf, (box_x + box_w // 2 - title_surf.get_width() // 2, ty))
        ty += 24

        # ── 카테고리 탭 ──
        tab_x = box_x + 16
        for i, ck in enumerate(_CATEGORY_KEYS):
            label = t(ck)
            if i == self._cat_idx:
                color = pg.BG
                tab_bg = pg.ACCENT_BLUE
            else:
                color = pg.TEXT
                tab_bg = pg.PANEL_BG
            ts = font.render(f" {label} ", True, color)
            tw, th = ts.get_size()
            pad = 4
            pygame.draw.rect(screen, tab_bg,
                             (tab_x - pad, ty, tw + pad * 2, th + 2),
                             border_radius=4)
            screen.blit(ts, (tab_x, ty))
            tab_x += tw + pad * 2 + 6
        ty += 22

        # ── 검색 바 ──
        search_bar_y = ty
        if self._search_active:
            bar_color = pg.ACCENT_BLUE
            prompt = t("glossary_search_placeholder")
            display_text = self._search_text if self._search_text else prompt
            text_color = pg.TEXT if self._search_text else pg.SUBTEXT
        else:
            bar_color = pg.OVERLAY
            display_text = f"/ {self._search_text}" if self._search_text else "/"
            text_color = pg.TEXT if self._search_text else pg.SUBTEXT

        pygame.draw.rect(screen, pg.PANEL_BG,
                         (box_x + 16, search_bar_y, box_w - 32, 20),
                         border_radius=4)
        pygame.draw.rect(screen, bar_color,
                         (box_x + 16, search_bar_y, box_w - 32, 20),
                         border_w, border_radius=4)
        st = font.render(display_text, True, text_color)
        screen.blit(st, (box_x + 24, search_bar_y + 3))

        # 커서 깜박임 (감소 모션 시 항상 표시)
        if self._search_active:
            cursor_x = box_x + 24 + font.size(self._search_text)[0]
            if reduced or pygame.time.get_ticks() % 1000 < 500:
                pygame.draw.line(screen, pg.ACCENT_BLUE,
                                 (cursor_x, search_bar_y + 3),
                                 (cursor_x, search_bar_y + 17))
        ty = search_bar_y + 26

        # ── 용어 목록 ──
        items = self._page_items()
        if not items and not self._filtered:
            no_result = font.render(t("glossary_no_results"), True, pg.TEXT)
            screen.blit(no_result, (box_x + box_w // 2 - no_result.get_width() // 2, ty + 20))
        else:
            content_bottom = box_y + box_h - 58
            for tid, tcat in items:
                if ty > content_bottom:
                    break
                name = t(f"gl_{tid}")
                defn = t(f"gl_{tid}_def")
                formula_key = f"gl_{tid}_formula"
                formula = t(formula_key)
                has_formula = formula != formula_key  # key 자체가 반환되면 없는 것

                # 용어 이름
                name_surf = font.render(f"  {name}", True, pg.ACCENT_YELLOW)
                screen.blit(name_surf, (box_x + 16, ty))
                ty += 18

                # 정의 (줄바꿈)
                max_chars = max(20, (box_w - 60) // (font.size("A")[0] or 8))
                def_lines = wrap_text(defn, max_chars)
                for line in def_lines:
                    if ty > content_bottom:
                        break
                    ls = font.render(f"    {line}", True, pg.TEXT)
                    screen.blit(ls, (box_x + 16, ty))
                    ty += 16

                # 수식
                if has_formula:
                    if ty <= content_bottom:
                        fs = font.render(f"    {formula}", True, pg.ACCENT_PURPLE)
                        screen.blit(fs, (box_x + 16, ty))
                        ty += 16

                ty += 8  # 항목 간 간격

        # ── 하단 네비게이션 ──
        bottom_y = box_y + box_h - 42
        total_pg = self._total_pages()

        # 도트 인디케이터
        dot_r = 4 if hc else 3
        dots_w = page_dots_width(total_pg)
        dot_start_x = box_x + box_w // 2 - dots_w // 2
        dot_cy = bottom_y + dot_r + 1
        draw_page_dots(screen, dot_start_x, dot_cy,
                       total_pg, self._page,
                       pg.ACCENT_BLUE, pg.OVERLAY, pg.SUBTEXT)

        # 페이지 번호 (도트 아래)
        page_text = t("glossary_page", page=self._page + 1, total=total_pg)
        page_surf = font.render(page_text, True, pg.SUBTEXT)
        screen.blit(page_surf, (box_x + box_w // 2 - page_surf.get_width() // 2,
                                bottom_y + dot_r * 2 + 4))

        nav_y = bottom_y + dot_r * 2 + 20
        nav_text = t("glossary_nav")
        nav_surf = font.render(nav_text, True, pg.SUBTEXT)
        screen.blit(nav_surf, (box_x + box_w // 2 - nav_surf.get_width() // 2, nav_y))

        # 닫기 안내
        close_surf = font.render(t("glossary_close"), True, pg.SUBTEXT)
        screen.blit(close_surf,
                     (box_x + box_w - close_surf.get_width() // 2 - 16, nav_y))
