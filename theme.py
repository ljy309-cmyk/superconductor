"""중앙 테마 정의 — 색상, 폰트, 레이아웃 상수를 한 곳에서 관리.

사용법:
    from theme import TK_COLORS, PG_COLORS, FONTS
    bg = TK_COLORS["bg"]          # Tkinter 16진수 문자열
    bg = PG_COLORS["bg"]          # Pygame RGB 튜플
    font = FONTS["body"]          # ("Consolas", 10)
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


# ── 색각 이상 접근성 팔레트 (Deuteranopia-safe) ──────
class TK_COLORBLIND:
    """Tkinter 용 색각 이상 접근성 팔레트 (dark base)."""
    BG          = "#1e1e2e"
    PANEL_BG    = "#2a2a3d"
    SURFACE     = "#181825"
    OVERLAY     = "#45475a"
    TEXT        = "#cdd6f4"
    SUBTEXT     = "#585b70"
    ACCENT_BLUE = "#6fa8dc"
    ACCENT_PURPLE = "#b4a7d6"
    ACCENT_GREEN  = "#93c47d"
    ACCENT_YELLOW = "#ffd966"
    ACCENT_PEACH  = "#e69138"
    RED         = "#e06666"
    GREEN       = "#93c47d"
    YELLOW      = "#ffd966"
    GOLD        = "#ffd966"
    SILVER      = "#bac2de"
    BRONZE      = "#e69138"
    GAUGE_BG    = "#45475a"


class PG_COLORBLIND:
    """Pygame 용 색각 이상 접근성 팔레트."""
    BG          = (30, 30, 46)
    PANEL_BG    = (24, 24, 37)
    SURFACE     = (24, 24, 37)
    OVERLAY     = (69, 71, 90)
    TEXT        = (205, 214, 244)
    SUBTEXT     = (88, 91, 112)
    ACCENT_BLUE = (111, 168, 220)
    ACCENT_PURPLE = (180, 167, 214)
    ACCENT_GREEN  = (147, 196, 125)
    ACCENT_YELLOW = (255, 217, 102)
    ACCENT_PEACH  = (230, 145, 56)
    RED         = (224, 102, 102)
    GREEN       = (147, 196, 125)
    YELLOW      = (255, 217, 102)
    SHIELD_CLR  = (111, 168, 220)
    SHIELD_GLOW = (111, 168, 220)
    SENSOR_CLR  = (111, 168, 220)
    MAGNET_N    = (224, 102, 102)
    MAGNET_S    = (111, 168, 220)
    SC_COLOR    = (147, 196, 125)
    SC_GLOW     = (111, 168, 220)
    STABLE      = (147, 196, 125)
    WARNING     = (255, 217, 102)
    DANGER      = (230, 145, 56)
    COLLAPSED   = (224, 102, 102)
    ALICE       = (111, 168, 220)
    BOB         = (147, 196, 125)
    EVE         = (224, 102, 102)
    QUBIT       = (180, 167, 214)
    DECOY       = (255, 217, 102)


# ── 테마 토글 ────────────────────────────────────────
_current_theme = "dark"
_colorblind_mode = False


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
    """색각 이상 모드 활성화 여부."""
    return _colorblind_mode


def toggle_colorblind() -> bool:
    """색각 이상 모드 토글. 새 상태 반환."""
    global _colorblind_mode
    _colorblind_mode = not _colorblind_mode
    return _colorblind_mode


def get_tk_theme():
    """현재 Tkinter 테마 클래스 반환."""
    if _colorblind_mode:
        return TK_COLORBLIND
    return TK_LIGHT if _current_theme == "light" else TK


def get_pg_theme():
    """현재 Pygame 테마 클래스 반환."""
    if _colorblind_mode:
        return PG_COLORBLIND
    return PG_LIGHT if _current_theme == "light" else PG
