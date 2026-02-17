"""중앙 테마 정의 — 색상, 폰트, 레이아웃 상수를 한 곳에서 관리.

사용법:
    from theme import TK_COLORS, PG_COLORS, FONTS
    bg = TK_COLORS["bg"]          # Tkinter 16진수 문자열
    bg = PG_COLORS["bg"]          # Pygame RGB 튜플
    font = FONTS["body"]          # ("Consolas", 10)

색맹 친화 모드:
    from theme import set_colorblind, is_colorblind
    set_colorblind(True)           # 색맹 친화 팔레트 활성화
    tk = get_tk_theme()            # 자동으로 CB 변형 반환
"""


# ── Catppuccin Mocha 기반 색상 (Tkinter 16진수) ──────
class TK:
    """Tkinter 용 16진수 색상."""
    BG          = "#1e1e2e"
    PANEL_BG    = "#2a2a3d"
    SURFACE     = "#181825"
    OVERLAY     = "#45475a"
    TEXT        = "#cdd6f4"
    SUBTEXT     = "#585b70"
    ACCENT_BLUE = "#89b4fa"
    ACCENT_PURPLE = "#cba6f7"
    ACCENT_GREEN  = "#a6e3a1"
    ACCENT_YELLOW = "#f9e2af"
    ACCENT_PEACH  = "#fab387"
    RED         = "#f38ba8"
    GREEN       = "#a6e3a1"
    YELLOW      = "#f9e2af"
    GOLD        = "#f9e2af"
    SILVER      = "#bac2de"
    BRONZE      = "#fab387"
    GAUGE_BG    = "#45475a"


class PG:
    """Pygame 용 RGB 튜플."""
    BG          = (30, 30, 46)
    PANEL_BG    = (24, 24, 37)
    SURFACE     = (24, 24, 37)
    OVERLAY     = (69, 71, 90)
    TEXT        = (205, 214, 244)
    SUBTEXT     = (88, 91, 112)
    ACCENT_BLUE = (137, 180, 250)
    ACCENT_PURPLE = (203, 166, 247)
    ACCENT_GREEN  = (166, 227, 161)
    ACCENT_YELLOW = (249, 226, 175)
    ACCENT_PEACH  = (250, 179, 135)
    RED         = (243, 139, 168)
    GREEN       = (166, 227, 161)
    YELLOW      = (249, 226, 175)
    SHIELD_CLR  = (137, 180, 250)
    SHIELD_GLOW = (116, 199, 236)
    SENSOR_CLR  = (116, 199, 236)

    # 자석
    MAGNET_N    = (235, 90, 90)
    MAGNET_S    = (100, 130, 235)
    SC_COLOR    = (166, 227, 161)
    SC_GLOW     = (137, 180, 250)

    # 큐비트 상태
    STABLE      = (166, 227, 161)
    WARNING     = (249, 226, 175)
    DANGER      = (250, 179, 135)
    COLLAPSED   = (243, 139, 168)

    # BB84
    ALICE       = (137, 180, 250)
    BOB         = (166, 227, 161)
    EVE         = (243, 139, 168)
    QUBIT       = (203, 166, 247)
    DECOY       = (249, 226, 175)


# ── 모듈별 Accent 색상 ──────────────────────────────
LAUNCHER_ACCENTS = {
    "physics":  TK.ACCENT_BLUE,
    "quantum":  TK.ACCENT_PURPLE,
    "security": TK.ACCENT_YELLOW,
    "data_ai":  TK.ACCENT_GREEN,
}

LAUNCHER_ACCENTS_PG = {
    "physics":  PG.ACCENT_BLUE,
    "quantum":  PG.ACCENT_PURPLE,
    "security": PG.ACCENT_YELLOW,
    "data_ai":  PG.ACCENT_GREEN,
}


# ── 폰트 정의 ────────────────────────────────────────
class FONTS:
    """공용 폰트 정의 (family, size, weight)."""
    FAMILY  = "Consolas"
    TITLE   = (FAMILY, 18, "bold")
    HEADING = (FAMILY, 14, "bold")
    BODY    = (FAMILY, 10)
    BODY_BOLD = (FAMILY, 10, "bold")
    SMALL   = (FAMILY, 9)
    TINY    = (FAMILY, 8)
    MONO_12 = (FAMILY, 12)
    MONO_11 = (FAMILY, 11)
    BUTTON  = (FAMILY, 10)


# ── 라이트 테마 (Catppuccin Latte 기반) ───────────────
class TK_LIGHT:
    """Tkinter 용 라이트 테마."""
    BG          = "#eff1f5"
    PANEL_BG    = "#e6e9ef"
    SURFACE     = "#dce0e8"
    OVERLAY     = "#ccd0da"
    TEXT        = "#4c4f69"
    SUBTEXT     = "#6c6f85"
    ACCENT_BLUE = "#1e66f5"
    ACCENT_PURPLE = "#8839ef"
    ACCENT_GREEN  = "#40a02b"
    ACCENT_YELLOW = "#df8e1d"
    ACCENT_PEACH  = "#fe640b"
    RED         = "#d20f39"
    GREEN       = "#40a02b"
    YELLOW      = "#df8e1d"
    GOLD        = "#df8e1d"
    SILVER      = "#9ca0b0"
    BRONZE      = "#fe640b"
    GAUGE_BG    = "#ccd0da"


class PG_LIGHT:
    """Pygame 용 라이트 테마 RGB 튜플."""
    BG          = (239, 241, 245)
    PANEL_BG    = (230, 233, 239)
    SURFACE     = (220, 224, 232)
    OVERLAY     = (204, 208, 218)
    TEXT        = (76, 79, 105)
    SUBTEXT     = (108, 111, 133)
    ACCENT_BLUE = (30, 102, 245)
    ACCENT_PURPLE = (136, 57, 239)
    ACCENT_GREEN  = (64, 160, 43)
    ACCENT_YELLOW = (223, 142, 29)
    ACCENT_PEACH  = (254, 100, 11)
    RED         = (210, 15, 57)
    GREEN       = (64, 160, 43)
    YELLOW      = (223, 142, 29)
    SHIELD_CLR  = (30, 102, 245)
    SHIELD_GLOW = (32, 159, 181)
    SENSOR_CLR  = (32, 159, 181)
    MAGNET_N    = (210, 15, 57)
    MAGNET_S    = (30, 102, 245)
    SC_COLOR    = (64, 160, 43)
    SC_GLOW     = (30, 102, 245)
    STABLE      = (64, 160, 43)
    WARNING     = (223, 142, 29)
    DANGER      = (254, 100, 11)
    COLLAPSED   = (210, 15, 57)
    ALICE       = (30, 102, 245)
    BOB         = (64, 160, 43)
    EVE         = (210, 15, 57)
    QUBIT       = (136, 57, 239)
    DECOY       = (223, 142, 29)


# ── 색맹 친화 다크 테마 (Blue/Orange — 적록 색맹 안전) ──
class TK_CB:
    """Tkinter 용 색맹 친화 다크 테마.

    RED/GREEN 구분 → Blue/Orange 구분으로 전환.
    Okabe-Ito 팔레트 원칙 적용.
    """
    BG          = "#1e1e2e"
    PANEL_BG    = "#2a2a3d"
    SURFACE     = "#181825"
    OVERLAY     = "#45475a"
    TEXT        = "#cdd6f4"
    SUBTEXT     = "#585b70"
    ACCENT_BLUE = "#89b4fa"
    ACCENT_PURPLE = "#cba6f7"
    ACCENT_GREEN  = "#74c7ec"     # Sky Blue (green 대체)
    ACCENT_YELLOW = "#f9e2af"
    ACCENT_PEACH  = "#fab387"
    RED         = "#fab387"       # Peach/Orange (red 대체)
    GREEN       = "#74c7ec"       # Sky Blue (green 대체)
    YELLOW      = "#f9e2af"
    GOLD        = "#f9e2af"
    SILVER      = "#bac2de"
    BRONZE      = "#fab387"
    GAUGE_BG    = "#45475a"


class PG_CB:
    """Pygame 용 색맹 친화 다크 테마 RGB 튜플."""
    BG          = (30, 30, 46)
    PANEL_BG    = (24, 24, 37)
    SURFACE     = (24, 24, 37)
    OVERLAY     = (69, 71, 90)
    TEXT        = (205, 214, 244)
    SUBTEXT     = (88, 91, 112)
    ACCENT_BLUE = (137, 180, 250)
    ACCENT_PURPLE = (203, 166, 247)
    ACCENT_GREEN  = (116, 199, 236)   # Sky Blue
    ACCENT_YELLOW = (249, 226, 175)
    ACCENT_PEACH  = (250, 179, 135)
    RED         = (250, 179, 135)     # Peach/Orange
    GREEN       = (116, 199, 236)     # Sky Blue
    YELLOW      = (249, 226, 175)
    SHIELD_CLR  = (137, 180, 250)
    SHIELD_GLOW = (116, 199, 236)
    SENSOR_CLR  = (116, 199, 236)

    # 자석
    MAGNET_N    = (250, 179, 135)     # Warm orange (was red)
    MAGNET_S    = (100, 130, 235)
    SC_COLOR    = (116, 199, 236)     # Sky Blue (was green)
    SC_GLOW     = (137, 180, 250)

    # 큐비트 상태 — 밝기 그라데이션으로 구분
    STABLE      = (116, 199, 236)     # Sky Blue (안정)
    WARNING     = (249, 226, 175)     # Yellow (경고)
    DANGER      = (250, 179, 135)     # Peach (위험)
    COLLAPSED   = (230, 150, 100)     # Deep Orange (붕괴)

    # BB84
    ALICE       = (137, 180, 250)
    BOB         = (116, 199, 236)     # Sky Blue (was green)
    EVE         = (250, 179, 135)     # Peach/Orange (was red)
    QUBIT       = (203, 166, 247)
    DECOY       = (249, 226, 175)


# ── 색맹 친화 라이트 테마 ─────────────────────────────
class TK_CB_LIGHT:
    """Tkinter 용 색맹 친화 라이트 테마."""
    BG          = "#eff1f5"
    PANEL_BG    = "#e6e9ef"
    SURFACE     = "#dce0e8"
    OVERLAY     = "#ccd0da"
    TEXT        = "#4c4f69"
    SUBTEXT     = "#6c6f85"
    ACCENT_BLUE = "#1e66f5"
    ACCENT_PURPLE = "#8839ef"
    ACCENT_GREEN  = "#209fb5"     # Teal (green 대체)
    ACCENT_YELLOW = "#df8e1d"
    ACCENT_PEACH  = "#fe640b"
    RED         = "#fe640b"       # Vivid Orange (red 대체)
    GREEN       = "#209fb5"       # Teal (green 대체)
    YELLOW      = "#df8e1d"
    GOLD        = "#df8e1d"
    SILVER      = "#9ca0b0"
    BRONZE      = "#fe640b"
    GAUGE_BG    = "#ccd0da"


class PG_CB_LIGHT:
    """Pygame 용 색맹 친화 라이트 테마 RGB 튜플."""
    BG          = (239, 241, 245)
    PANEL_BG    = (230, 233, 239)
    SURFACE     = (220, 224, 232)
    OVERLAY     = (204, 208, 218)
    TEXT        = (76, 79, 105)
    SUBTEXT     = (108, 111, 133)
    ACCENT_BLUE = (30, 102, 245)
    ACCENT_PURPLE = (136, 57, 239)
    ACCENT_GREEN  = (32, 159, 181)    # Teal
    ACCENT_YELLOW = (223, 142, 29)
    ACCENT_PEACH  = (254, 100, 11)
    RED         = (254, 100, 11)      # Vivid Orange
    GREEN       = (32, 159, 181)      # Teal
    YELLOW      = (223, 142, 29)
    SHIELD_CLR  = (30, 102, 245)
    SHIELD_GLOW = (32, 159, 181)
    SENSOR_CLR  = (32, 159, 181)
    MAGNET_N    = (254, 100, 11)      # Vivid Orange (was red)
    MAGNET_S    = (30, 102, 245)
    SC_COLOR    = (32, 159, 181)      # Teal (was green)
    SC_GLOW     = (30, 102, 245)
    STABLE      = (32, 159, 181)      # Teal (안정)
    WARNING     = (223, 142, 29)      # Yellow (경고)
    DANGER      = (254, 100, 11)      # Orange (위험)
    COLLAPSED   = (200, 80, 10)       # Deep Orange (붕괴)
    ALICE       = (30, 102, 245)
    BOB         = (32, 159, 181)      # Teal (was green)
    EVE         = (254, 100, 11)      # Orange (was red)
    QUBIT       = (136, 57, 239)
    DECOY       = (223, 142, 29)


# ── 테마 & 색맹 모드 토글 ─────────────────────────────
_current_theme = "dark"
_colorblind = False

# 테마 조합 매핑
_TK_THEMES = {
    ("dark",  False): TK,
    ("dark",  True):  TK_CB,
    ("light", False): TK_LIGHT,
    ("light", True):  TK_CB_LIGHT,
}

_PG_THEMES = {
    ("dark",  False): PG,
    ("dark",  True):  PG_CB,
    ("light", False): PG_LIGHT,
    ("light", True):  PG_CB_LIGHT,
}


def get_theme() -> str:
    """현재 테마 반환."""
    return _current_theme


def set_theme(theme: str):
    """테마 설정 ('dark' 또는 'light')."""
    global _current_theme
    _current_theme = theme


def toggle_theme() -> str:
    """다크/라이트 토글. 새 테마 이름 반환."""
    global _current_theme
    _current_theme = "light" if _current_theme == "dark" else "dark"
    return _current_theme


def is_colorblind() -> bool:
    """색맹 친화 모드 활성화 여부."""
    return _colorblind


def set_colorblind(enabled: bool):
    """색맹 친화 모드 설정."""
    global _colorblind
    _colorblind = enabled


def toggle_colorblind() -> bool:
    """색맹 친화 모드 토글. 새 상태 반환."""
    global _colorblind
    _colorblind = not _colorblind
    return _colorblind


def get_tk_theme():
    """현재 Tkinter 테마 클래스 반환 (테마 + 색맹 모드 고려)."""
    return _TK_THEMES[(_current_theme, _colorblind)]


def get_pg_theme():
    """현재 Pygame 테마 클래스 반환 (테마 + 색맹 모드 고려)."""
    return _PG_THEMES[(_current_theme, _colorblind)]
