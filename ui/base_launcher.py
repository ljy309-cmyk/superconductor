"""공용 런처 베이스 클래스 — 4개 서브메뉴 런처의 중복을 제거.

사용법:
    from ui.base_launcher import BaseLauncher

    class PhysicsLauncher(BaseLauncher):
        MODULE = "physics"
        BUTTONS = [
            ("btn_phase_transition", lambda self: open_phase_transition(self)),
            ...
        ]
"""

import tkinter as tk

from i18n import t
from theme import FONTS, LAUNCHER_ACCENTS, TK


class BaseLauncher(tk.Toplevel):
    """서브메뉴 런처 공용 베이스 클래스.

    서브클래스에서 MODULE, BUTTONS를 정의하면 자동으로 UI 구성.
    """

    MODULE: str = ""  # "physics", "quantum", "security", "data_ai"
    BUTTONS: list[tuple] = []  # [(i18n_key, callback_or_callable), ...]
    BUTTON_WIDTH: int = 42

    def __init__(self, master=None):
        super().__init__(master)
        accent = LAUNCHER_ACCENTS.get(self.MODULE, TK.ACCENT_BLUE)
        title_key = f"launcher_{self.MODULE}_title"
        heading_key = f"launcher_{self.MODULE}_heading"

        self.title(t(title_key))
        self.configure(bg=TK.BG)
        self.resizable(False, False)

        frame = tk.Frame(self, bg=TK.BG, padx=24, pady=20)
        frame.pack()

        tk.Label(
            frame,
            text=t(heading_key),
            font=FONTS.HEADING,
            bg=TK.BG,
            fg=accent,
        ).pack(pady=(0, 14))

        for btn_key, cmd in self.BUTTONS:
            callback = cmd if not callable(cmd) else (lambda c=cmd: c(self))
            tk.Button(
                frame,
                text=t(btn_key),
                command=callback,
                width=self.BUTTON_WIDTH,
                height=2,
                font=FONTS.BUTTON,
            ).pack(pady=4)

    def _launch_pygame(self, open_func):
        """Pygame 모듈 실행: 창 숨기기 → 실행 → 복원."""
        self.withdraw()
        open_func()
        self.deiconify()
