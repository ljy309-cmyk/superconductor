"""프로파일 관리 UI — 저장된 프로파일 목록/삭제/이름변경 (Tkinter).

사용법:
    from profile_manager import open_profile_manager
    open_profile_manager(master)
"""

import tkinter as tk
from tkinter import messagebox, simpledialog

from i18n import t
from logger import get_module_logger
from presets import delete_profile, list_profiles, load_profile, rename_profile
from theme import FONTS, get_tk_theme

_log = get_module_logger("profile_manager")


class ProfileManager(tk.Toplevel):
    """프로파일 관리 윈도우."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title(t("profile_title"))
        _tk = get_tk_theme()
        self.configure(bg=_tk.BG)
        self.geometry("500x400")
        self.resizable(False, False)

        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        _tk = get_tk_theme()

        # 상단 라벨
        tk.Label(
            self,
            text=t("profile_heading"),
            font=FONTS.HEADING,
            bg=_tk.BG,
            fg=_tk.TEXT,
        ).pack(pady=(12, 6))

        # 리스트 프레임
        list_frame = tk.Frame(self, bg=_tk.PANEL_BG)
        list_frame.pack(fill="both", expand=True, padx=12, pady=4)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self._listbox = tk.Listbox(
            list_frame,
            font=FONTS.BODY,
            bg=_tk.SURFACE,
            fg=_tk.TEXT,
            selectbackground=_tk.ACCENT_BLUE,
            selectforeground="#ffffff",
            yscrollcommand=scrollbar.set,
            bd=0,
            highlightthickness=0,
        )
        self._listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._listbox.yview)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # 상세 정보
        self._detail_label = tk.Label(
            self,
            text="",
            font=FONTS.SMALL,
            bg=_tk.BG,
            fg=_tk.SUBTEXT,
            anchor="w",
            justify="left",
        )
        self._detail_label.pack(fill="x", padx=16, pady=(2, 4))

        # 버튼 프레임
        btn_frame = tk.Frame(self, bg=_tk.BG)
        btn_frame.pack(pady=(4, 12))

        tk.Button(
            btn_frame,
            text=t("profile_rename"),
            font=FONTS.BUTTON,
            width=12,
            command=self._rename,
        ).pack(side="left", padx=4)

        tk.Button(
            btn_frame,
            text=t("profile_delete"),
            font=FONTS.BUTTON,
            width=12,
            command=self._delete,
        ).pack(side="left", padx=4)

        tk.Button(
            btn_frame,
            text=t("profile_refresh"),
            font=FONTS.BUTTON,
            width=12,
            command=self._refresh_list,
        ).pack(side="left", padx=4)

    def _refresh_list(self):
        """프로파일 목록 새로고침."""
        self._listbox.delete(0, "end")
        profiles = sorted(list_profiles())
        for name in profiles:
            self._listbox.insert("end", name)
        self._detail_label.config(
            text=t("profile_count", count=len(profiles)),
        )

    def _get_selected(self) -> str | None:
        """선택된 프로파일 이름 반환."""
        sel = self._listbox.curselection()
        if not sel:
            return None
        return self._listbox.get(sel[0])

    def _on_select(self, _event=None):
        """프로파일 선택 시 상세 표시."""
        name = self._get_selected()
        if not name:
            return
        data = load_profile(name)
        keys = list(data.keys())[:5]
        preview = ", ".join(f"{k}={data[k]}" for k in keys)
        if len(data) > 5:
            preview += f" ... (+{len(data) - 5})"
        self._detail_label.config(text=f"{name}: {preview}")

    def _rename(self):
        """프로파일 이름 변경."""
        name = self._get_selected()
        if not name:
            messagebox.showinfo(t("profile_title"), t("profile_select_first"), parent=self)
            return
        new_name = simpledialog.askstring(
            t("profile_rename"),
            t("profile_new_name"),
            initialvalue=name,
            parent=self,
        )
        if not new_name or new_name == name:
            return
        if rename_profile(name, new_name):
            self._refresh_list()
        else:
            messagebox.showerror(
                t("profile_title"),
                t("profile_rename_fail"),
                parent=self,
            )

    def _delete(self):
        """프로파일 삭제."""
        name = self._get_selected()
        if not name:
            messagebox.showinfo(t("profile_title"), t("profile_select_first"), parent=self)
            return
        confirm = messagebox.askyesno(
            t("profile_title"),
            t("profile_delete_confirm", name=name),
            parent=self,
        )
        if confirm and delete_profile(name):
            self._refresh_list()


def open_profile_manager(master=None):
    """외부에서 호출하는 진입점."""
    ProfileManager(master)
