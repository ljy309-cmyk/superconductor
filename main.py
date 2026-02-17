"""Superconductor — 메인 메뉴 애플리케이션."""

import tkinter as tk

from scada.dashboard import open_dashboard
from physics.launcher import open_physics_launcher
from quantum.launcher import open_quantum_launcher
from security.launcher import open_security_launcher
from data_ai.launcher import open_data_ai_launcher
from config_loader import cfg
from i18n import t, set_locale
from theme import (TK, FONTS, get_theme, toggle_theme, get_tk_theme,
                   is_colorblind, set_colorblind, toggle_colorblind,
                   load_preferences, save_preferences)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Superconductor")
        self.resizable(False, False)

        # config.json에서 테마/색맹 모드 설정 로드
        load_preferences()

        self._buttons = [
            ("menu_scada",    lambda: open_dashboard(self)),
            ("menu_physics",  lambda: open_physics_launcher(self)),
            ("menu_quantum",  lambda: open_quantum_launcher(self)),
            ("menu_security", lambda: open_security_launcher(self)),
            ("menu_data_ai",  lambda: open_data_ai_launcher(self)),
        ]

        self._create_widgets()
        self._center_window()

    def _create_widgets(self):
        frame = tk.Frame(self, padx=20, pady=20)
        frame.pack()

        tk.Label(
            frame, text=t("menu_title"), font=FONTS.HEADING,
        ).pack(pady=(0, 15))

        for key, command in self._buttons:
            tk.Button(
                frame, text=t(key), command=command,
                width=35, height=2,
            ).pack(pady=4)

        # 언어 전환 + 테마 전환 + 색맹 모드 버튼
        option_frame = tk.Frame(frame, bg=get_tk_theme().BG)
        option_frame.pack(pady=(10, 0))
        tk.Button(
            option_frame, text="한국어", font=FONTS.SMALL,
            command=lambda: self._switch_locale("ko"), width=8,
        ).pack(side="left", padx=2)
        tk.Button(
            option_frame, text="English", font=FONTS.SMALL,
            command=lambda: self._switch_locale("en"), width=8,
        ).pack(side="left", padx=2)

        theme_icon = "Light" if get_theme() == "dark" else "Dark"
        tk.Button(
            option_frame, text=f"Theme: {theme_icon}", font=FONTS.SMALL,
            command=self._switch_theme, width=12,
        ).pack(side="left", padx=(10, 2))

        cb_label = t("colorblind_on") if is_colorblind() else t("colorblind_off")
        tk.Button(
            option_frame, text=cb_label, font=FONTS.SMALL,
            command=self._toggle_colorblind, width=14,
        ).pack(side="left", padx=2)

    def _switch_locale(self, locale: str):
        """언어 전환 후 UI 재구성."""
        set_locale(locale)
        for widget in self.winfo_children():
            widget.destroy()
        self._create_widgets()

    def _switch_theme(self):
        """다크/라이트 테마 전환 후 UI 재구성."""
        toggle_theme()
        save_preferences()
        for widget in self.winfo_children():
            widget.destroy()
        self._create_widgets()

    def _toggle_colorblind(self):
        """색맹 친화 모드 토글 후 UI 재구성."""
        toggle_colorblind()
        save_preferences()
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
