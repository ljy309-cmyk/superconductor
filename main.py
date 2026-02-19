"""Superconductor — 메인 메뉴 애플리케이션."""

import tkinter as tk

from data_ai.launcher import open_data_ai_launcher
from i18n import set_locale, t
from physics.launcher import open_physics_launcher
from quantum.launcher import open_quantum_launcher
from scada.dashboard import open_dashboard
from security.launcher import open_security_launcher
from sound_manager import get_sound_manager
from theme import (
    FONTS,
    decrease_font_scale,
    get_font_scale,
    get_theme,
    get_tk_theme,
    increase_font_scale,
    is_colorblind,
    load_preferences,
    save_preferences,
    toggle_colorblind,
    toggle_theme,
)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(t("app_title"))
        self.resizable(False, False)

        # config.json에서 테마/색맹 모드 설정 로드
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
        frame = tk.Frame(self, padx=20, pady=20)
        frame.pack()

        tk.Label(
            frame,
            text=t("menu_title"),
            font=FONTS.HEADING,
        ).pack(pady=(0, 15))

        for key, command in self._buttons:
            tk.Button(
                frame,
                text=t(key),
                command=command,
                width=35,
                height=2,
            ).pack(pady=4)

        # 언어 전환 + 테마 전환 + 색맹 모드 버튼
        option_frame = tk.Frame(frame, bg=get_tk_theme().BG)
        option_frame.pack(pady=(10, 0))
        tk.Button(
            option_frame,
            text=t("lang_ko"),
            font=FONTS.SMALL,
            command=lambda: self._switch_locale("ko"),
            width=8,
        ).pack(side="left", padx=2)
        tk.Button(
            option_frame,
            text=t("lang_en"),
            font=FONTS.SMALL,
            command=lambda: self._switch_locale("en"),
            width=8,
        ).pack(side="left", padx=2)

        theme_name = t("theme_light") if get_theme() == "dark" else t("theme_dark")
        tk.Button(
            option_frame,
            text=t("theme_toggle", theme=theme_name),
            font=FONTS.SMALL,
            command=self._switch_theme,
            width=12,
        ).pack(side="left", padx=(10, 2))

        cb_label = t("colorblind_on") if is_colorblind() else t("colorblind_off")
        tk.Button(
            option_frame,
            text=cb_label,
            font=FONTS.SMALL,
            command=self._toggle_colorblind,
            width=14,
        ).pack(side="left", padx=2)

        # 폰트 크기 조절
        font_frame = tk.Frame(frame, bg=get_tk_theme().BG)
        font_frame.pack(pady=(4, 0))
        tk.Button(
            font_frame,
            text=t("font_decrease"),
            font=FONTS.SMALL,
            command=self._decrease_font,
            width=4,
        ).pack(side="left", padx=2)
        tk.Label(
            font_frame,
            text=f"{t('font_scale')}: {get_font_scale():.1f}x",
            font=FONTS.SMALL,
            bg=get_tk_theme().BG,
            fg=get_tk_theme().TEXT,
        ).pack(side="left", padx=4)
        tk.Button(
            font_frame,
            text=t("font_increase"),
            font=FONTS.SMALL,
            command=self._increase_font,
            width=4,
        ).pack(side="left", padx=2)

        # 프로파일 관리 버튼
        tk.Button(
            font_frame,
            text=t("menu_profiles"),
            font=FONTS.SMALL,
            command=lambda: __import__("profile_manager").open_profile_manager(self),
            width=14,
        ).pack(side="left", padx=(10, 2))

        # 볼륨 조절
        vol_frame = tk.Frame(frame, bg=get_tk_theme().BG)
        vol_frame.pack(pady=(4, 0))
        snd = get_sound_manager()

        tk.Button(
            vol_frame,
            text=t("mute_toggle"),
            font=FONTS.SMALL,
            command=self._toggle_mute,
            width=6,
        ).pack(side="left", padx=2)
        tk.Button(
            vol_frame,
            text="-",
            font=FONTS.SMALL,
            command=self._volume_down,
            width=3,
        ).pack(side="left", padx=2)
        if snd.enabled:
            vol_text = t("volume_label", vol=int(snd.volume * 100))
        else:
            vol_text = t("volume_muted")
        tk.Label(
            vol_frame,
            text=vol_text,
            font=FONTS.SMALL,
            bg=get_tk_theme().BG,
            fg=get_tk_theme().TEXT,
            width=12,
        ).pack(side="left", padx=4)
        tk.Button(
            vol_frame,
            text="+",
            font=FONTS.SMALL,
            command=self._volume_up,
            width=3,
        ).pack(side="left", padx=2)

    def _switch_locale(self, locale: str):
        """언어 전환 후 UI 재구성."""
        set_locale(locale)
        self.title(t("app_title"))
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

    def _increase_font(self):
        """폰트 크기 증가 후 UI 재구성."""
        increase_font_scale()
        save_preferences()
        for widget in self.winfo_children():
            widget.destroy()
        self._create_widgets()

    def _decrease_font(self):
        """폰트 크기 감소 후 UI 재구성."""
        decrease_font_scale()
        save_preferences()
        for widget in self.winfo_children():
            widget.destroy()
        self._create_widgets()

    def _toggle_mute(self):
        """음소거 토글 후 UI 재구성."""
        snd = get_sound_manager()
        snd.toggle()
        snd.save_preferences()
        for widget in self.winfo_children():
            widget.destroy()
        self._create_widgets()

    def _volume_up(self):
        """볼륨 증가 후 UI 재구성."""
        snd = get_sound_manager()
        snd.volume_up()
        snd.save_preferences()
        for widget in self.winfo_children():
            widget.destroy()
        self._create_widgets()

    def _volume_down(self):
        """볼륨 감소 후 UI 재구성."""
        snd = get_sound_manager()
        snd.volume_down()
        snd.save_preferences()
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
