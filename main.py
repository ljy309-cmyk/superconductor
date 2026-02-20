"""Superconductor — 메인 메뉴 애플리케이션."""

import tkinter as tk

from data_ai.launcher import open_data_ai_launcher
from i18n import t
from physics.launcher import open_physics_launcher
from quantum.launcher import open_quantum_launcher
from scada.dashboard import open_dashboard
from security.launcher import open_security_launcher
from settings_panel import open_settings
from theme import (
    FONTS,
    get_tk_theme,
    load_preferences,
)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(t("app_title"))
        self.resizable(False, False)

        # config.json에서 테마/색맹/폰트/언어 설정 로드
        load_preferences()

        self._buttons = [
            ("menu_scada", lambda: open_dashboard(self)),
            ("menu_physics", lambda: open_physics_launcher(self)),
            ("menu_quantum", lambda: open_quantum_launcher(self)),
            ("menu_security", lambda: open_security_launcher(self)),
            ("menu_data_ai", lambda: open_data_ai_launcher(self)),
        ]

        self._create_widgets()
        self._center_window()

    def _create_widgets(self):
        _tk = get_tk_theme()
        frame = tk.Frame(self, padx=20, pady=20, bg=_tk.BG)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text=t("menu_title"),
            font=FONTS.HEADING,
            bg=_tk.BG,
            fg=_tk.TEXT,
        ).pack(pady=(0, 15))

        for key, command in self._buttons:
            tk.Button(
                frame,
                text=t(key),
                command=command,
                font=FONTS.BODY,
                width=35,
                height=2,
            ).pack(pady=4)

        # 설정 버튼
        tk.Button(
            frame,
            text=t("btn_settings"),
            font=FONTS.BODY,
            width=35,
            height=2,
            command=self._open_settings,
        ).pack(pady=(12, 0))

    def _open_settings(self):
        """설정 패널 열기. 변경 시 메인 메뉴 UI 재구성."""
        open_settings(self, on_change=self._rebuild)

    def _rebuild(self):
        """설정 변경 후 UI 재구성."""
        self.title(t("app_title"))
        for widget in self.winfo_children():
            widget.destroy()
        self._create_widgets()

    def _center_window(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")


if __name__ == "__main__":
    App().mainloop()
