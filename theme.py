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

    # 공통
    WHITE       = (255, 255, 255)
    INACTIVE    = (100, 100, 100)


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
    FAMILY  = "Consolas"

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

    # 공통
    WHITE       = (255, 255, 255)
    INACTIVE    = (100, 100, 100)


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

    # 공통
    WHITE       = (255, 255, 255)
    INACTIVE    = (100, 100, 100)


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

    # 공통
    WHITE       = (255, 255, 255)
    INACTIVE    = (100, 100, 100)


# ── 테마 & 색맹 모드 토글 ─────────────────────────────
import weakref as _weakref

_current_theme = "dark"
_colorblind = False
_listeners: list = []  # (ref_or_callable, is_weak) 튜플 목록

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

    if hasattr(callback, '__self__'):
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

    __slots__ = ('_fn',)

    def __init__(self, load_fn):
        self._fn = load_fn

    def __enter__(self):
        self._fn()                 # 초기 로드
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
    """현재 Tkinter 테마 클래스 반환 (테마 + 색맹 모드 고려)."""
    return _TK_THEMES[(_current_theme, _colorblind)]


def get_pg_theme():
    """현재 Pygame 테마 클래스 반환 (테마 + 색맹 모드 고려)."""
    return _PG_THEMES[(_current_theme, _colorblind)]


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
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        cfg = {}
    cfg["theme"] = _current_theme
    cfg["colorblind_mode"] = _colorblind
    cfg["font_scale"] = _font_scale
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def load_preferences():
    """config.json에서 테마/색맹 설정을 로드 (알림 없이)."""
    import json
    import os
    global _current_theme, _colorblind, _font_scale
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if cfg.get("theme") in ("dark", "light"):
            _current_theme = cfg["theme"]
        if isinstance(cfg.get("colorblind_mode"), bool):
            _colorblind = cfg["colorblind_mode"]
        if isinstance(cfg.get("font_scale"), (int, float)):
            _font_scale = round(max(_FONT_SCALE_MIN, min(_FONT_SCALE_MAX, cfg["font_scale"])), 1)
    except (OSError, json.JSONDecodeError):
        pass
