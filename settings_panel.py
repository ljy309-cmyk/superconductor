"""설정 패널 — 통합 설정 UI (Tkinter Toplevel).

폰트, 테마, 언어, 사운드, 데이터 관리 등 모든 설정을 하나의 창에서 관리합니다.

사용법::

    from settings_panel import open_settings
    open_settings(master, on_change_callback)
"""

import json
import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

from logger import get_module_logger
from font_helper import get_font_family, get_user_font, set_user_font
from i18n import get_locale, set_locale, t
from sound_manager import get_sound_manager
from theme import (
    FONTS,
    decrease_font_scale,
    get_font_scale,
    get_theme,
    get_tk_theme,
    increase_font_scale,
    is_colorblind,
    save_preferences,
    toggle_colorblind,
    toggle_theme,
)

_log = get_module_logger("settings_panel")
_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _read_config() -> dict:
    """config.json 읽기. 실패 시 빈 dict 반환."""
    try:
        with open(_CFG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _write_config(cfg: dict) -> bool:
    """config.json 쓰기. 실패 시 ``False`` 반환 및 로그 기록."""
    try:
        with open(_CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        _log.warning("설정 저장 실패: %s", e)
        return False


class SettingsPanel(tk.Toplevel):
    """통합 설정 윈도우."""

    def __init__(self, master=None, on_change=None):
        super().__init__(master)
        self._on_change = on_change
        self.title(t("settings_title"))
        self.resizable(False, False)
        self._build_ui()
        self._center()

    def _notify(self):
        """설정 변경 후 부모에게 알림."""
        save_preferences()
        if self._on_change:
            self._on_change()

    def _build_ui(self):
        _tk = get_tk_theme()
        self.configure(bg=_tk.BG)

        main = tk.Frame(self, bg=_tk.BG, padx=20, pady=16)
        main.pack(fill="both", expand=True)

        # ── 디스플레이 섹션 ──
        self._section_label(main, t("settings_section_display"))

        # 테마
        row = tk.Frame(main, bg=_tk.BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=t("settings_theme"), font=FONTS.BODY, bg=_tk.BG, fg=_tk.TEXT, width=14, anchor="w").pack(side="left")
        theme_name = t("theme_dark") if get_theme() == "dark" else t("theme_light")
        self._theme_btn = tk.Button(row, text=theme_name, font=FONTS.BODY, width=12, command=self._toggle_theme)
        self._theme_btn.pack(side="left", padx=4)

        # 색맹 모드
        row = tk.Frame(main, bg=_tk.BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=t("settings_colorblind"), font=FONTS.BODY, bg=_tk.BG, fg=_tk.TEXT, width=14, anchor="w").pack(side="left")
        cb_text = "ON" if is_colorblind() else "OFF"
        self._cb_btn = tk.Button(row, text=cb_text, font=FONTS.BODY, width=12, command=self._toggle_colorblind)
        self._cb_btn.pack(side="left", padx=4)

        # 언어
        row = tk.Frame(main, bg=_tk.BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=t("settings_language"), font=FONTS.BODY, bg=_tk.BG, fg=_tk.TEXT, width=14, anchor="w").pack(side="left")
        self._locale_var = tk.StringVar(value=get_locale())
        tk.OptionMenu(row, self._locale_var, "ko", "en", command=self._change_locale).pack(side="left", padx=4)

        # FPS
        row = tk.Frame(main, bg=_tk.BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=t("settings_fps"), font=FONTS.BODY, bg=_tk.BG, fg=_tk.TEXT, width=14, anchor="w").pack(side="left")
        self._fps_var = tk.StringVar(value=str(self._get_fps()))
        tk.OptionMenu(row, self._fps_var, "30", "60", "120", command=self._change_fps).pack(side="left", padx=4)

        # ── 폰트 섹션 ──
        self._section_label(main, t("settings_section_font"))

        # 폰트 종류
        row = tk.Frame(main, bg=_tk.BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=t("settings_font_family"), font=FONTS.BODY, bg=_tk.BG, fg=_tk.TEXT, width=14, anchor="w").pack(side="left")

        font_choices = self._get_font_choices()
        current_font = get_user_font() or get_font_family()
        self._font_var = tk.StringVar(value=current_font)
        self._font_menu = tk.OptionMenu(row, self._font_var, *font_choices, command=self._change_font)
        self._font_menu.config(font=FONTS.SMALL, width=22)
        self._font_menu.pack(side="left", padx=4)

        # 폰트 크기
        row = tk.Frame(main, bg=_tk.BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=t("settings_font_scale"), font=FONTS.BODY, bg=_tk.BG, fg=_tk.TEXT, width=14, anchor="w").pack(side="left")
        tk.Button(row, text="A-", font=FONTS.BODY, width=3, command=self._decrease_font).pack(side="left", padx=2)
        self._scale_label = tk.Label(row, text=f"{get_font_scale():.1f}x", font=FONTS.BODY, bg=_tk.BG, fg=_tk.TEXT, width=5)
        self._scale_label.pack(side="left", padx=4)
        tk.Button(row, text="A+", font=FONTS.BODY, width=3, command=self._increase_font).pack(side="left", padx=2)

        # ── 사운드 섹션 ──
        self._section_label(main, t("settings_section_sound"))

        snd = get_sound_manager()

        # 효과음 ON/OFF
        row = tk.Frame(main, bg=_tk.BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=t("settings_sound_enabled"), font=FONTS.BODY, bg=_tk.BG, fg=_tk.TEXT, width=14, anchor="w").pack(side="left")
        snd_text = "ON" if snd.enabled else "OFF"
        self._snd_btn = tk.Button(row, text=snd_text, font=FONTS.BODY, width=12, command=self._toggle_sound)
        self._snd_btn.pack(side="left", padx=4)

        # 볼륨
        row = tk.Frame(main, bg=_tk.BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=t("settings_volume"), font=FONTS.BODY, bg=_tk.BG, fg=_tk.TEXT, width=14, anchor="w").pack(side="left")
        self._vol_scale = tk.Scale(
            row, from_=0, to=100, orient="horizontal", length=180,
            font=FONTS.SMALL, bg=_tk.BG, fg=_tk.TEXT, highlightthickness=0,
            troughcolor=_tk.SURFACE, command=self._change_volume,
        )
        self._vol_scale.set(int(snd.volume * 100))
        self._vol_scale.pack(side="left", padx=4)

        # ── 기본 난이도 ──
        row = tk.Frame(main, bg=_tk.BG)
        row.pack(fill="x", pady=(8, 2))
        tk.Label(row, text=t("settings_default_difficulty"), font=FONTS.BODY, bg=_tk.BG, fg=_tk.TEXT, width=14, anchor="w").pack(side="left")
        self._diff_var = tk.StringVar(value=self._get_default_difficulty())
        tk.OptionMenu(row, self._diff_var, "easy", "normal", "hard", command=self._change_difficulty).pack(side="left", padx=4)

        # ── 데이터 관리 섹션 ──
        self._section_label(main, t("settings_section_data"))

        btn_frame = tk.Frame(main, bg=_tk.BG)
        btn_frame.pack(fill="x", pady=4)
        tk.Button(btn_frame, text=t("settings_export"), font=FONTS.BODY, width=16, command=self._export_settings).pack(side="left", padx=4)
        tk.Button(btn_frame, text=t("settings_import"), font=FONTS.BODY, width=16, command=self._import_settings).pack(side="left", padx=4)
        tk.Button(btn_frame, text=t("settings_profiles"), font=FONTS.BODY, width=16, command=self._open_profiles).pack(side="left", padx=4)

        btn_frame2 = tk.Frame(main, bg=_tk.BG)
        btn_frame2.pack(fill="x", pady=2)
        tk.Button(btn_frame2, text=t("settings_manage_exports"), font=FONTS.BODY, width=16, command=self._manage_exports).pack(side="left", padx=4)

        # ── 닫기 버튼 ──
        tk.Button(main, text=t("settings_close"), font=FONTS.BODY, width=12, command=self.destroy).pack(pady=(16, 0))

    def _section_label(self, parent, text):
        _tk = get_tk_theme()
        sep = tk.Frame(parent, bg=_tk.OVERLAY, height=1)
        sep.pack(fill="x", pady=(10, 2))
        tk.Label(parent, text=text, font=FONTS.HEADING, bg=_tk.BG, fg=_tk.ACCENT_BLUE, anchor="w").pack(fill="x")

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    # ── 디스플레이 ──

    def _toggle_theme(self):
        toggle_theme()
        name = t("theme_dark") if get_theme() == "dark" else t("theme_light")
        self._theme_btn.config(text=name)
        self._notify()
        self._rebuild()

    def _toggle_colorblind(self):
        toggle_colorblind()
        self._cb_btn.config(text="ON" if is_colorblind() else "OFF")
        self._notify()
        self._rebuild()

    def _change_locale(self, locale):
        set_locale(locale)
        self._notify()
        self._rebuild()

    def _change_fps(self, fps_str):
        fps = int(fps_str)
        cfg = _read_config()
        if "display" not in cfg:
            cfg["display"] = {}
        cfg["display"]["fps"] = fps
        if not _write_config(cfg):
            messagebox.showwarning(t("settings_title"), t("settings_save_error"), parent=self)

    def _get_fps(self) -> int:
        return _read_config().get("display", {}).get("fps", 60)

    # ── 폰트 ──

    def _get_font_choices(self) -> list[str]:
        """사용 가능한 폰트 목록 + 시스템 폰트 목록."""
        try:
            result = subprocess.run(
                ["fc-list", "--format", "%{family}\n"],
                capture_output=True, text=True, timeout=5,
            )
            families = sorted(set(
                line.split(",")[0].strip()
                for line in result.stdout.split("\n")
                if line.strip()
            ))
            # CJK 지원 폰트를 앞에 배치
            cjk_keywords = ["wen", "cjk", "gothic", "nanum", "dotum", "gulim", "noto sans", "unifont"]
            cjk = [f for f in families if any(kw in f.lower() for kw in cjk_keywords)]
            others = [f for f in families if f not in cjk]
            return cjk + others if cjk else families
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return [get_font_family()]

    def _change_font(self, family):
        set_user_font(family)
        FONTS.FAMILY = family
        self._notify()
        self._rebuild()

    def _increase_font(self):
        increase_font_scale()
        self._scale_label.config(text=f"{get_font_scale():.1f}x")
        self._notify()

    def _decrease_font(self):
        decrease_font_scale()
        self._scale_label.config(text=f"{get_font_scale():.1f}x")
        self._notify()

    # ── 사운드 ──

    def _toggle_sound(self):
        snd = get_sound_manager()
        snd.toggle()
        snd.save_preferences()
        self._snd_btn.config(text="ON" if snd.enabled else "OFF")
        if self._on_change:
            self._on_change()

    def _change_volume(self, val):
        snd = get_sound_manager()
        snd.volume = int(val) / 100.0
        snd.save_preferences()
        if self._on_change:
            self._on_change()

    # ── 난이도 ──

    def _get_default_difficulty(self) -> str:
        return _read_config().get("default_difficulty", "normal")

    def _change_difficulty(self, diff):
        cfg = _read_config()
        cfg["default_difficulty"] = diff
        if not _write_config(cfg):
            messagebox.showwarning(t("settings_title"), t("settings_save_error"), parent=self)

    # ── 데이터 관리 ──

    def _export_settings(self):
        from settings_io import export_settings
        path = export_settings()
        if path:
            messagebox.showinfo(t("settings_title"), t("settings_export_done", path=path), parent=self)
        else:
            messagebox.showwarning(t("settings_title"), t("settings_export_fail"), parent=self)

    def _import_settings(self):
        path = filedialog.askopenfilename(
            parent=self,
            title=t("settings_import"),
            filetypes=[("ZIP", "*.zip")],
        )
        if not path:
            return
        from settings_io import import_settings
        result = import_settings(path)
        if result["imported"]:
            msg = t("settings_import_done", count=len(result["imported"]))
            if result["skipped"]:
                msg += "\n" + t("settings_import_skipped", count=len(result["skipped"]),
                                files=", ".join(result["skipped"][:5]))
            messagebox.showinfo(
                t("settings_title"),
                msg,
                parent=self,
            )
            # 설정 리로드
            from config_loader import reload_config
            from theme import load_preferences

            reload_config()
            load_preferences()
            get_sound_manager().load_preferences()
            self._notify()
            self._rebuild()
        else:
            messagebox.showwarning(t("settings_title"), t("settings_import_fail"), parent=self)

    def _manage_exports(self):
        from settings_io import delete_export, list_exports

        exports = list_exports()
        if not exports:
            messagebox.showinfo(t("settings_title"), t("settings_no_exports"), parent=self)
            return

        _tk = get_tk_theme()
        dlg = tk.Toplevel(self)
        dlg.title(t("settings_manage_exports"))
        dlg.configure(bg=_tk.BG)
        dlg.geometry("420x300")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text=t("settings_manage_exports"), font=FONTS.HEADING, bg=_tk.BG, fg=_tk.TEXT).pack(pady=(10, 4))

        frame = tk.Frame(dlg, bg=_tk.BG)
        frame.pack(fill="both", expand=True, padx=10)

        scrollbar = tk.Scrollbar(frame, orient="vertical")
        lb = tk.Listbox(frame, font=FONTS.BODY, selectmode="single", yscrollcommand=scrollbar.set)
        scrollbar.config(command=lb.yview)
        scrollbar.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)

        for path in exports:
            lb.insert("end", os.path.basename(path))
        if exports:
            lb.select_set(0)

        def _delete():
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            path = exports[idx]
            if not messagebox.askyesno(t("settings_title"), t("settings_delete_confirm", name=os.path.basename(path)), parent=dlg):
                return
            if delete_export(path):
                exports.pop(idx)
                lb.delete(idx)
                messagebox.showinfo(t("settings_title"), t("settings_deleted"), parent=dlg)
            if not exports:
                dlg.destroy()
                return
            # 삭제 후 인접 항목 자동 선택
            new_idx = min(idx, len(exports) - 1)
            lb.select_set(new_idx)

        btn_frame = tk.Frame(dlg, bg=_tk.BG)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text=t("settings_delete"), font=FONTS.BODY, width=10, command=_delete).pack(side="left", padx=4)
        tk.Button(btn_frame, text=t("settings_close"), font=FONTS.BODY, width=10, command=dlg.destroy).pack(side="left", padx=4)

    def _open_profiles(self):
        from profile_manager import open_profile_manager
        open_profile_manager(self)

    # ── UI 재구성 ──

    def _rebuild(self):
        """설정 변경 후 UI 재구성."""
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()


def open_settings(master=None, on_change=None):
    """설정 패널 열기."""
    SettingsPanel(master, on_change)
