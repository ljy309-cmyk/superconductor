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

    BG = "#1e1e2e"
    PANEL_BG = "#2a2a3d"
    SURFACE = "#181825"
    OVERLAY = "#45475a"
    TEXT = "#cdd6f4"
    SUBTEXT = "#585b70"
    ACCENT_BLUE = "#89b4fa"
    ACCENT_PURPLE = "#cba6f7"
    ACCENT_GREEN = "#a6e3a1"
    ACCENT_YELLOW = "#f9e2af"
    ACCENT_PEACH = "#fab387"
    RED = "#f38ba8"
    GREEN = "#a6e3a1"
    YELLOW = "#f9e2af"
    GOLD = "#f9e2af"
    SILVER = "#bac2de"
    BRONZE = "#fab387"
    GAUGE_BG = "#45475a"


class PG:
    """Pygame 용 RGB 튜플."""

    BG = (30, 30, 46)
    PANEL_BG = (24, 24, 37)
    SURFACE = (24, 24, 37)
    OVERLAY = (69, 71, 90)
    TEXT = (205, 214, 244)
    SUBTEXT = (88, 91, 112)
    ACCENT_BLUE = (137, 180, 250)
    ACCENT_PURPLE = (203, 166, 247)
    ACCENT_GREEN = (166, 227, 161)
    ACCENT_YELLOW = (249, 226, 175)
    ACCENT_PEACH = (250, 179, 135)
    RED = (243, 139, 168)
    GREEN = (166, 227, 161)
    YELLOW = (249, 226, 175)
    SHIELD_CLR = (137, 180, 250)
    SHIELD_GLOW = (116, 199, 236)
    SENSOR_CLR = (116, 199, 236)

    # 자석
    MAGNET_N = (235, 90, 90)
    MAGNET_S = (100, 130, 235)
    SC_COLOR = (166, 227, 161)
    SC_GLOW = (137, 180, 250)

    # 큐비트 상태
    STABLE = (166, 227, 161)
    WARNING = (249, 226, 175)
    DANGER = (250, 179, 135)
    COLLAPSED = (243, 139, 168)

    # BB84
    ALICE = (137, 180, 250)
    BOB = (166, 227, 161)
    EVE = (243, 139, 168)
    QUBIT = (203, 166, 247)
    DECOY = (249, 226, 175)

    # 공통
    WHITE = (255, 255, 255)
    INACTIVE = (100, 100, 100)
    TEAL = (148, 226, 213)


# ── 모듈별 Accent 색상 ──────────────────────────────
LAUNCHER_ACCENTS = {
    "physics": TK.ACCENT_BLUE,
    "quantum": TK.ACCENT_PURPLE,
    "security": TK.ACCENT_YELLOW,
    "data_ai": TK.ACCENT_GREEN,
}

LAUNCHER_ACCENTS_PG = {
    "physics": PG.ACCENT_BLUE,
    "quantum": PG.ACCENT_PURPLE,
    "security": PG.ACCENT_YELLOW,
    "data_ai": PG.ACCENT_GREEN,
}


# ── 폰트 정의 ────────────────────────────────────────
_font_scale: float = 1.0  # 폰트 크기 배율 (0.8 ~ 1.5)
_FONT_SCALE_MIN = 0.8
_FONT_SCALE_MAX = 1.5
_FONT_SCALE_STEP = 0.1


def _scaled(size: int) -> int:
    """폰트 크기에 스케일 적용."""
    return max(6, int(size * _font_scale))


class FONTS:
    """공용 폰트 정의 (family, size, weight).

    font_scale 변경 시 프로퍼티처럼 동적으로 반환합니다.
    """

    FAMILY = "Consolas"

    @staticmethod
    def _f(size, bold=False):
        if bold:
            return (FONTS.FAMILY, _scaled(size), "bold")
        return (FONTS.FAMILY, _scaled(size))

    @property
    def TITLE(self):
        return self._f(18, True)

    @property
    def HEADING(self):
        return self._f(14, True)

    @property
    def BODY(self):
        return self._f(10)

    @property
    def BODY_BOLD(self):
        return self._f(10, True)

    @property
    def SMALL(self):
        return self._f(9)

    @property
    def TINY(self):
        return self._f(8)

    @property
    def MONO_12(self):
        return self._f(12)

    @property
    def MONO_11(self):
        return self._f(11)

    @property
    def BUTTON(self):
        return self._f(10)


# 싱글톤 인스턴스 — 기존 코드와 호환 유지: FONTS.BODY 등 사용 가능
FONTS = FONTS()


# ── 라이트 테마 (Catppuccin Latte 기반) ───────────────
class TK_LIGHT:
    """Tkinter 용 라이트 테마."""

    BG = "#eff1f5"
    PANEL_BG = "#e6e9ef"
    SURFACE = "#dce0e8"
    OVERLAY = "#ccd0da"
    TEXT = "#4c4f69"
    SUBTEXT = "#6c6f85"
    ACCENT_BLUE = "#1e66f5"
    ACCENT_PURPLE = "#8839ef"
    ACCENT_GREEN = "#40a02b"
    ACCENT_YELLOW = "#df8e1d"
    ACCENT_PEACH = "#fe640b"
    RED = "#d20f39"
    GREEN = "#40a02b"
    YELLOW = "#df8e1d"
    GOLD = "#df8e1d"
    SILVER = "#9ca0b0"
    BRONZE = "#fe640b"
    GAUGE_BG = "#ccd0da"


class PG_LIGHT:
    """Pygame 용 라이트 테마 RGB 튜플."""

    BG = (239, 241, 245)
    PANEL_BG = (230, 233, 239)
    SURFACE = (220, 224, 232)
    OVERLAY = (204, 208, 218)
    TEXT = (76, 79, 105)
    SUBTEXT = (108, 111, 133)
    ACCENT_BLUE = (30, 102, 245)
    ACCENT_PURPLE = (136, 57, 239)
    ACCENT_GREEN = (64, 160, 43)
    ACCENT_YELLOW = (223, 142, 29)
    ACCENT_PEACH = (254, 100, 11)
    RED = (210, 15, 57)
    GREEN = (64, 160, 43)
    YELLOW = (223, 142, 29)
    SHIELD_CLR = (30, 102, 245)
    SHIELD_GLOW = (32, 159, 181)
    SENSOR_CLR = (32, 159, 181)
    MAGNET_N = (210, 15, 57)
    MAGNET_S = (30, 102, 245)
    SC_COLOR = (64, 160, 43)
    SC_GLOW = (30, 102, 245)
    STABLE = (64, 160, 43)
    WARNING = (223, 142, 29)
    DANGER = (254, 100, 11)
    COLLAPSED = (210, 15, 57)
    ALICE = (30, 102, 245)
    BOB = (64, 160, 43)
    EVE = (210, 15, 57)
    QUBIT = (136, 57, 239)
    DECOY = (223, 142, 29)

    # 공통
    WHITE = (255, 255, 255)
    INACTIVE = (100, 100, 100)
    TEAL = (32, 159, 181)


# ── 색맹 친화 다크 테마 (Blue/Orange — 적록 색맹 안전) ──
class TK_CB:
    """Tkinter 용 색맹 친화 다크 테마.

    RED/GREEN 구분 → Blue/Orange 구분으로 전환.
    Okabe-Ito 팔레트 원칙 적용.
    """

    BG = "#1e1e2e"
    PANEL_BG = "#2a2a3d"
    SURFACE = "#181825"
    OVERLAY = "#45475a"
    TEXT = "#cdd6f4"
    SUBTEXT = "#585b70"
    ACCENT_BLUE = "#89b4fa"
    ACCENT_PURPLE = "#cba6f7"
    ACCENT_GREEN = "#74c7ec"  # Sky Blue (green 대체)
    ACCENT_YELLOW = "#f9e2af"
    ACCENT_PEACH = "#fab387"
    RED = "#fab387"  # Peach/Orange (red 대체)
    GREEN = "#74c7ec"  # Sky Blue (green 대체)
    YELLOW = "#f9e2af"
    GOLD = "#f9e2af"
    SILVER = "#bac2de"
    BRONZE = "#fab387"
    GAUGE_BG = "#45475a"


class PG_CB:
    """Pygame 용 색맹 친화 다크 테마 RGB 튜플."""

    BG = (30, 30, 46)
    PANEL_BG = (24, 24, 37)
    SURFACE = (24, 24, 37)
    OVERLAY = (69, 71, 90)
    TEXT = (205, 214, 244)
    SUBTEXT = (88, 91, 112)
    ACCENT_BLUE = (137, 180, 250)
    ACCENT_PURPLE = (203, 166, 247)
    ACCENT_GREEN = (116, 199, 236)  # Sky Blue
    ACCENT_YELLOW = (249, 226, 175)
    ACCENT_PEACH = (250, 179, 135)
    RED = (250, 179, 135)  # Peach/Orange
    GREEN = (116, 199, 236)  # Sky Blue
    YELLOW = (249, 226, 175)
    SHIELD_CLR = (137, 180, 250)
    SHIELD_GLOW = (116, 199, 236)
    SENSOR_CLR = (116, 199, 236)

    # 자석
    MAGNET_N = (250, 179, 135)  # Warm orange (was red)
    MAGNET_S = (100, 130, 235)
    SC_COLOR = (116, 199, 236)  # Sky Blue (was green)
    SC_GLOW = (137, 180, 250)

    # 큐비트 상태 — 밝기 그라데이션으로 구분
    STABLE = (116, 199, 236)  # Sky Blue (안정)
    WARNING = (249, 226, 175)  # Yellow (경고)
    DANGER = (250, 179, 135)  # Peach (위험)
    COLLAPSED = (230, 150, 100)  # Deep Orange (붕괴)

    # BB84
    ALICE = (137, 180, 250)
    BOB = (116, 199, 236)  # Sky Blue (was green)
    EVE = (250, 179, 135)  # Peach/Orange (was red)
    QUBIT = (203, 166, 247)
    DECOY = (249, 226, 175)

    # 공통
    WHITE = (255, 255, 255)
    INACTIVE = (100, 100, 100)
    TEAL = (116, 199, 236)


# ── 색맹 친화 라이트 테마 ─────────────────────────────
class TK_CB_LIGHT:
    """Tkinter 용 색맹 친화 라이트 테마."""

    BG = "#eff1f5"
    PANEL_BG = "#e6e9ef"
    SURFACE = "#dce0e8"
    OVERLAY = "#ccd0da"
    TEXT = "#4c4f69"
    SUBTEXT = "#6c6f85"
    ACCENT_BLUE = "#1e66f5"
    ACCENT_PURPLE = "#8839ef"
    ACCENT_GREEN = "#209fb5"  # Teal (green 대체)
    ACCENT_YELLOW = "#df8e1d"
    ACCENT_PEACH = "#fe640b"
    RED = "#fe640b"  # Vivid Orange (red 대체)
    GREEN = "#209fb5"  # Teal (green 대체)
    YELLOW = "#df8e1d"
    GOLD = "#df8e1d"
    SILVER = "#9ca0b0"
    BRONZE = "#fe640b"
    GAUGE_BG = "#ccd0da"


class PG_CB_LIGHT:
    """Pygame 용 색맹 친화 라이트 테마 RGB 튜플."""

    BG = (239, 241, 245)
    PANEL_BG = (230, 233, 239)
    SURFACE = (220, 224, 232)
    OVERLAY = (204, 208, 218)
    TEXT = (76, 79, 105)
    SUBTEXT = (108, 111, 133)
    ACCENT_BLUE = (30, 102, 245)
    ACCENT_PURPLE = (136, 57, 239)
    ACCENT_GREEN = (32, 159, 181)  # Teal
    ACCENT_YELLOW = (223, 142, 29)
    ACCENT_PEACH = (254, 100, 11)
    RED = (254, 100, 11)  # Vivid Orange
    GREEN = (32, 159, 181)  # Teal
    YELLOW = (223, 142, 29)
    SHIELD_CLR = (30, 102, 245)
    SHIELD_GLOW = (32, 159, 181)
    SENSOR_CLR = (32, 159, 181)
    MAGNET_N = (254, 100, 11)  # Vivid Orange (was red)
    MAGNET_S = (30, 102, 245)
    SC_COLOR = (32, 159, 181)  # Teal (was green)
    SC_GLOW = (30, 102, 245)
    STABLE = (32, 159, 181)  # Teal (안정)
    WARNING = (223, 142, 29)  # Yellow (경고)
    DANGER = (254, 100, 11)  # Orange (위험)
    COLLAPSED = (200, 80, 10)  # Deep Orange (붕괴)
    ALICE = (30, 102, 245)
    BOB = (32, 159, 181)  # Teal (was green)
    EVE = (254, 100, 11)  # Orange (was red)
    QUBIT = (136, 57, 239)
    DECOY = (223, 142, 29)

    # 공통
    WHITE = (255, 255, 255)
    INACTIVE = (100, 100, 100)
    TEAL = (32, 159, 181)


# ── 고대비 다크 테마 (WCAG AAA 대비율 목표) ────────────
class TK_HC:
    """Tkinter 용 고대비 다크 테마."""

    BG = "#000000"
    PANEL_BG = "#0a0a12"
    SURFACE = "#050510"
    OVERLAY = "#5a5d72"
    TEXT = "#ffffff"
    SUBTEXT = "#aab0c8"
    ACCENT_BLUE = "#a0c8ff"
    ACCENT_PURPLE = "#dcc0ff"
    ACCENT_GREEN = "#b8f0b0"
    ACCENT_YELLOW = "#ffe8a0"
    ACCENT_PEACH = "#ffc8a0"
    RED = "#ff9ab0"
    GREEN = "#b8f0b0"
    YELLOW = "#ffe8a0"
    GOLD = "#ffe8a0"
    SILVER = "#d0d8f0"
    BRONZE = "#ffc8a0"
    GAUGE_BG = "#5a5d72"


class PG_HC:
    """Pygame 용 고대비 다크 테마 RGB 튜플."""

    BG = (0, 0, 0)
    PANEL_BG = (10, 10, 18)
    SURFACE = (5, 5, 16)
    OVERLAY = (90, 93, 114)
    TEXT = (255, 255, 255)
    SUBTEXT = (170, 176, 200)
    ACCENT_BLUE = (160, 200, 255)
    ACCENT_PURPLE = (220, 192, 255)
    ACCENT_GREEN = (184, 240, 176)
    ACCENT_YELLOW = (255, 232, 160)
    ACCENT_PEACH = (255, 200, 160)
    RED = (255, 154, 176)
    GREEN = (184, 240, 176)
    YELLOW = (255, 232, 160)
    SHIELD_CLR = (160, 200, 255)
    SHIELD_GLOW = (140, 220, 255)
    SENSOR_CLR = (140, 220, 255)

    MAGNET_N = (255, 110, 110)
    MAGNET_S = (120, 150, 255)
    SC_COLOR = (184, 240, 176)
    SC_GLOW = (160, 200, 255)

    STABLE = (184, 240, 176)
    WARNING = (255, 232, 160)
    DANGER = (255, 200, 160)
    COLLAPSED = (255, 154, 176)

    ALICE = (160, 200, 255)
    BOB = (184, 240, 176)
    EVE = (255, 154, 176)
    QUBIT = (220, 192, 255)
    DECOY = (255, 232, 160)

    WHITE = (255, 255, 255)
    INACTIVE = (130, 130, 130)
    TEAL = (170, 240, 230)


# ── 고대비 라이트 테마 ────────────────────────────────
class TK_HC_LIGHT:
    """Tkinter 용 고대비 라이트 테마."""

    BG = "#ffffff"
    PANEL_BG = "#f0f0f5"
    SURFACE = "#e8e8f0"
    OVERLAY = "#b0b4c0"
    TEXT = "#000000"
    SUBTEXT = "#282a38"
    ACCENT_BLUE = "#0044cc"
    ACCENT_PURPLE = "#6020c0"
    ACCENT_GREEN = "#1a7a10"
    ACCENT_YELLOW = "#a06800"
    ACCENT_PEACH = "#c04000"
    RED = "#b00020"
    GREEN = "#1a7a10"
    YELLOW = "#a06800"
    GOLD = "#a06800"
    SILVER = "#606880"
    BRONZE = "#c04000"
    GAUGE_BG = "#b0b4c0"


class PG_HC_LIGHT:
    """Pygame 용 고대비 라이트 테마 RGB 튜플."""

    BG = (255, 255, 255)
    PANEL_BG = (240, 240, 245)
    SURFACE = (232, 232, 240)
    OVERLAY = (176, 180, 192)
    TEXT = (0, 0, 0)
    SUBTEXT = (40, 42, 56)
    ACCENT_BLUE = (0, 68, 204)
    ACCENT_PURPLE = (96, 32, 192)
    ACCENT_GREEN = (26, 122, 16)
    ACCENT_YELLOW = (160, 104, 0)
    ACCENT_PEACH = (192, 64, 0)
    RED = (176, 0, 32)
    GREEN = (26, 122, 16)
    YELLOW = (160, 104, 0)
    SHIELD_CLR = (0, 68, 204)
    SHIELD_GLOW = (0, 130, 160)
    SENSOR_CLR = (0, 130, 160)

    MAGNET_N = (176, 0, 32)
    MAGNET_S = (0, 68, 204)
    SC_COLOR = (26, 122, 16)
    SC_GLOW = (0, 68, 204)

    STABLE = (26, 122, 16)
    WARNING = (160, 104, 0)
    DANGER = (192, 64, 0)
    COLLAPSED = (176, 0, 32)

    ALICE = (0, 68, 204)
    BOB = (26, 122, 16)
    EVE = (176, 0, 32)
    QUBIT = (96, 32, 192)
    DECOY = (160, 104, 0)

    WHITE = (255, 255, 255)
    INACTIVE = (80, 80, 80)
    TEAL = (0, 130, 160)


# ── 고대비 + 색맹 친화 다크 ───────────────────────────
class TK_HC_CB:
    """Tkinter 용 고대비 + 색맹 다크 테마."""

    BG = "#000000"
    PANEL_BG = "#0a0a12"
    SURFACE = "#050510"
    OVERLAY = "#5a5d72"
    TEXT = "#ffffff"
    SUBTEXT = "#aab0c8"
    ACCENT_BLUE = "#a0c8ff"
    ACCENT_PURPLE = "#dcc0ff"
    ACCENT_GREEN = "#90d8ff"  # Sky Blue (green 대체)
    ACCENT_YELLOW = "#ffe8a0"
    ACCENT_PEACH = "#ffc8a0"
    RED = "#ffc8a0"  # Peach/Orange (red 대체)
    GREEN = "#90d8ff"  # Sky Blue
    YELLOW = "#ffe8a0"
    GOLD = "#ffe8a0"
    SILVER = "#d0d8f0"
    BRONZE = "#ffc8a0"
    GAUGE_BG = "#5a5d72"


class PG_HC_CB:
    """Pygame 용 고대비 + 색맹 다크 테마 RGB 튜플."""

    BG = (0, 0, 0)
    PANEL_BG = (10, 10, 18)
    SURFACE = (5, 5, 16)
    OVERLAY = (90, 93, 114)
    TEXT = (255, 255, 255)
    SUBTEXT = (170, 176, 200)
    ACCENT_BLUE = (160, 200, 255)
    ACCENT_PURPLE = (220, 192, 255)
    ACCENT_GREEN = (144, 216, 255)  # Sky Blue
    ACCENT_YELLOW = (255, 232, 160)
    ACCENT_PEACH = (255, 200, 160)
    RED = (255, 200, 160)  # Peach/Orange
    GREEN = (144, 216, 255)  # Sky Blue
    YELLOW = (255, 232, 160)
    SHIELD_CLR = (160, 200, 255)
    SHIELD_GLOW = (144, 216, 255)
    SENSOR_CLR = (144, 216, 255)

    MAGNET_N = (255, 200, 160)
    MAGNET_S = (120, 150, 255)
    SC_COLOR = (144, 216, 255)
    SC_GLOW = (160, 200, 255)

    STABLE = (144, 216, 255)
    WARNING = (255, 232, 160)
    DANGER = (255, 200, 160)
    COLLAPSED = (240, 170, 120)

    ALICE = (160, 200, 255)
    BOB = (144, 216, 255)
    EVE = (255, 200, 160)
    QUBIT = (220, 192, 255)
    DECOY = (255, 232, 160)

    WHITE = (255, 255, 255)
    INACTIVE = (130, 130, 130)
    TEAL = (144, 216, 255)


# ── 고대비 + 색맹 친화 라이트 ─────────────────────────
class TK_HC_CB_LIGHT:
    """Tkinter 용 고대비 + 색맹 라이트 테마."""

    BG = "#ffffff"
    PANEL_BG = "#f0f0f5"
    SURFACE = "#e8e8f0"
    OVERLAY = "#b0b4c0"
    TEXT = "#000000"
    SUBTEXT = "#282a38"
    ACCENT_BLUE = "#0044cc"
    ACCENT_PURPLE = "#6020c0"
    ACCENT_GREEN = "#007098"  # Teal (green 대체)
    ACCENT_YELLOW = "#a06800"
    ACCENT_PEACH = "#c04000"
    RED = "#c04000"  # Orange (red 대체)
    GREEN = "#007098"  # Teal
    YELLOW = "#a06800"
    GOLD = "#a06800"
    SILVER = "#606880"
    BRONZE = "#c04000"
    GAUGE_BG = "#b0b4c0"


class PG_HC_CB_LIGHT:
    """Pygame 용 고대비 + 색맹 라이트 테마 RGB 튜플."""

    BG = (255, 255, 255)
    PANEL_BG = (240, 240, 245)
    SURFACE = (232, 232, 240)
    OVERLAY = (176, 180, 192)
    TEXT = (0, 0, 0)
    SUBTEXT = (40, 42, 56)
    ACCENT_BLUE = (0, 68, 204)
    ACCENT_PURPLE = (96, 32, 192)
    ACCENT_GREEN = (0, 112, 152)  # Teal
    ACCENT_YELLOW = (160, 104, 0)
    ACCENT_PEACH = (192, 64, 0)
    RED = (192, 64, 0)  # Orange
    GREEN = (0, 112, 152)  # Teal
    YELLOW = (160, 104, 0)
    SHIELD_CLR = (0, 68, 204)
    SHIELD_GLOW = (0, 112, 152)
    SENSOR_CLR = (0, 112, 152)

    MAGNET_N = (192, 64, 0)
    MAGNET_S = (0, 68, 204)
    SC_COLOR = (0, 112, 152)
    SC_GLOW = (0, 68, 204)

    STABLE = (0, 112, 152)
    WARNING = (160, 104, 0)
    DANGER = (192, 64, 0)
    COLLAPSED = (160, 50, 0)

    ALICE = (0, 68, 204)
    BOB = (0, 112, 152)
    EVE = (192, 64, 0)
    QUBIT = (96, 32, 192)
    DECOY = (160, 104, 0)

    WHITE = (255, 255, 255)
    INACTIVE = (80, 80, 80)
    TEAL = (0, 112, 152)


# ── 테마 & 색맹 모드 토글 ─────────────────────────────
import weakref as _weakref

_current_theme = "dark"
_colorblind = False
_reduced_motion = False
_high_contrast = False
_listeners: list = []  # (ref_or_callable, is_weak) 튜플 목록

# 테마 조합 매핑: (theme, colorblind, high_contrast) → 클래스
_TK_THEMES = {
    ("dark", False, False): TK,
    ("dark", True, False): TK_CB,
    ("light", False, False): TK_LIGHT,
    ("light", True, False): TK_CB_LIGHT,
    ("dark", False, True): TK_HC,
    ("dark", True, True): TK_HC_CB,
    ("light", False, True): TK_HC_LIGHT,
    ("light", True, True): TK_HC_CB_LIGHT,
}

_PG_THEMES = {
    ("dark", False, False): PG,
    ("dark", True, False): PG_CB,
    ("light", False, False): PG_LIGHT,
    ("light", True, False): PG_CB_LIGHT,
    ("dark", False, True): PG_HC,
    ("dark", True, True): PG_HC_CB,
    ("light", False, True): PG_HC_LIGHT,
    ("light", True, True): PG_HC_CB_LIGHT,
}


def _notify_listeners():
    """등록된 모든 콜백에 테마 변경을 알린다. 죽은 약참조 자동 제거."""
    alive = []
    for ref, is_weak in _listeners:
        cb = ref() if is_weak else ref
        if cb is None:
            continue  # 약참조 대상 소멸 → 건너뜀
        try:
            cb()
        except (TypeError, AttributeError, ValueError, RuntimeError):
            pass  # 리스너 오류가 테마 변경을 차단하지 않도록
        alive.append((ref, is_weak))
    _listeners[:] = alive


def on_theme_change(callback):
    """테마 변경 시 호출될 콜백 등록.

    바운드 메서드는 약참조(WeakMethod)로 저장되어 객체 소멸 시
    자동 정리됩니다. 일반 함수/람다는 강참조로 저장됩니다.

    콜백은 인자 없이 호출됩니다. get_pg_theme()/get_tk_theme()으로
    새 테마를 조회하세요.

    사용법:
        from theme import on_theme_change
        on_theme_change(my_module._load_theme_colors)
    """
    # 중복 등록 방지
    for ref, is_weak in _listeners:
        existing = ref() if is_weak else ref
        if existing is not None and existing == callback:
            return

    if hasattr(callback, "__self__"):
        # 바운드 메서드 → WeakMethod (객체 GC 허용)
        _listeners.append((_weakref.WeakMethod(callback), True))
    else:
        _listeners.append((callback, False))


def off_theme_change(callback):
    """등록된 테마 변경 콜백 제거."""
    for i, (ref, is_weak) in enumerate(_listeners):
        existing = ref() if is_weak else ref
        if existing is not None and existing == callback:
            _listeners.pop(i)
            return


class use_theme_colors:
    """_load_theme_colors() 자동 등록/해제 컨텍스트 매니저.

    사용법:
        with use_theme_colors(_load_theme_colors):
            # 게임 루프 — 테마 변경 시 색상 자동 갱신
            ...
    """

    __slots__ = ("_fn",)

    def __init__(self, load_fn):
        self._fn = load_fn

    def __enter__(self):
        self._fn()  # 초기 로드
        on_theme_change(self._fn)  # 런타임 갱신 등록
        return self

    def __exit__(self, *exc):
        off_theme_change(self._fn)
        return False


def get_theme() -> str:
    """현재 테마 반환."""
    return _current_theme


def set_theme(theme: str):
    """테마 설정 ('dark' 또는 'light')."""
    global _current_theme
    if theme == _current_theme:
        return
    _current_theme = theme
    _notify_listeners()


def toggle_theme() -> str:
    """다크/라이트 토글. 새 테마 이름 반환."""
    global _current_theme
    _current_theme = "light" if _current_theme == "dark" else "dark"
    _notify_listeners()
    return _current_theme


def is_colorblind() -> bool:
    """색맹 친화 모드 활성화 여부."""
    return _colorblind


def set_colorblind(enabled: bool):
    """색맹 친화 모드 설정."""
    global _colorblind
    if enabled == _colorblind:
        return
    _colorblind = enabled
    _notify_listeners()


def toggle_colorblind() -> bool:
    """색맹 친화 모드 토글. 새 상태 반환."""
    global _colorblind
    _colorblind = not _colorblind
    _notify_listeners()
    return _colorblind


def is_reduced_motion() -> bool:
    """감소된 모션 모드 활성화 여부."""
    return _reduced_motion


def set_reduced_motion(enabled: bool):
    """감소된 모션 모드 설정."""
    global _reduced_motion
    if enabled == _reduced_motion:
        return
    _reduced_motion = enabled


def toggle_reduced_motion() -> bool:
    """감소된 모션 모드 토글. 새 상태 반환."""
    global _reduced_motion
    _reduced_motion = not _reduced_motion
    return _reduced_motion


def is_high_contrast() -> bool:
    """고대비 모드 활성화 여부."""
    return _high_contrast


def set_high_contrast(enabled: bool):
    """고대비 모드 설정."""
    global _high_contrast
    if enabled == _high_contrast:
        return
    _high_contrast = enabled
    _notify_listeners()


def toggle_high_contrast() -> bool:
    """고대비 모드 토글. 새 상태 반환."""
    global _high_contrast
    _high_contrast = not _high_contrast
    _notify_listeners()
    return _high_contrast


def get_font_scale() -> float:
    """현재 폰트 크기 배율 반환."""
    return _font_scale


def set_font_scale(scale: float):
    """폰트 크기 배율 설정 (0.8 ~ 1.5)."""
    global _font_scale
    new_scale = round(max(_FONT_SCALE_MIN, min(_FONT_SCALE_MAX, scale)), 1)
    if new_scale == _font_scale:
        return
    _font_scale = new_scale
    _notify_listeners()


def increase_font_scale():
    """폰트 크기 한 단계 증가."""
    set_font_scale(_font_scale + _FONT_SCALE_STEP)


def decrease_font_scale():
    """폰트 크기 한 단계 감소."""
    set_font_scale(_font_scale - _FONT_SCALE_STEP)


def get_tk_theme():
    """현재 Tkinter 테마 클래스 반환 (테마 + 색맹 + 고대비 모드 고려)."""
    return _TK_THEMES[(_current_theme, _colorblind, _high_contrast)]


def get_pg_theme():
    """현재 Pygame 테마 클래스 반환 (테마 + 색맹 + 고대비 모드 고려)."""
    return _PG_THEMES[(_current_theme, _colorblind, _high_contrast)]


def load_pg_colors(mapping: dict[str, str], target_globals: dict) -> None:
    """Pygame 모듈의 테마 색상을 일괄 갱신하는 공통 헬퍼.

    각 모듈에서 반복되던 _load_theme_colors() 패턴을 대체합니다.

    Args:
        mapping: {모듈_글로벌_변수명: PG테마_속성명} 딕셔너리.
                 예: {"BG": "BG", "TEXT_CLR": "TEXT", "ACCENT": "ACCENT_BLUE"}
        target_globals: 호출 모듈의 globals() 딕셔너리.

    사용법::

        from theme import load_pg_colors, on_theme_change, off_theme_change

        _COLOR_MAP = {"BG": "BG", "TEXT_CLR": "TEXT", "ACCENT": "ACCENT_BLUE"}

        def _refresh_colors():
            load_pg_colors(_COLOR_MAP, globals())

        # 시뮬레이션 시작 시:
        _refresh_colors()
        on_theme_change(_refresh_colors)

        # 시뮬레이션 종료 시:
        off_theme_change(_refresh_colors)
    """
    pg = get_pg_theme()
    for global_name, attr_name in mapping.items():
        target_globals[global_name] = getattr(pg, attr_name)


def save_preferences():
    """현재 테마/색맹 설정을 config.json에 저장."""
    import json
    import os

    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        cfg = {}
    cfg["theme"] = _current_theme
    cfg["colorblind_mode"] = _colorblind
    cfg["font_scale"] = _font_scale
    acc = cfg.setdefault("accessibility", {})
    acc["reduced_motion"] = _reduced_motion
    acc["high_contrast"] = _high_contrast
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def load_preferences():
    """config.json에서 테마/색맹 설정을 로드 (알림 없이)."""
    import json
    import os

    global _current_theme, _colorblind, _font_scale, _reduced_motion, _high_contrast
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        if cfg.get("theme") in ("dark", "light"):
            _current_theme = cfg["theme"]
        if isinstance(cfg.get("colorblind_mode"), bool):
            _colorblind = cfg["colorblind_mode"]
        if isinstance(cfg.get("font_scale"), (int, float)):
            _font_scale = round(max(_FONT_SCALE_MIN, min(_FONT_SCALE_MAX, cfg["font_scale"])), 1)
        acc = cfg.get("accessibility", {})
        if isinstance(acc.get("reduced_motion"), bool):
            _reduced_motion = acc["reduced_motion"]
        if isinstance(acc.get("high_contrast"), bool):
            _high_contrast = acc["high_contrast"]
    except (OSError, json.JSONDecodeError):
        pass
