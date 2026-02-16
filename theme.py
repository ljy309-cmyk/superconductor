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
