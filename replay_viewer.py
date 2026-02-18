"""리플레이 뷰어 — 저장된 시뮬레이션 리플레이를 타임라인으로 재생 (Tkinter).

사용법:
    from replay_viewer import open_replay_viewer
    open_replay_viewer(master)
"""

import json
import tkinter as tk
from tkinter import filedialog, ttk

from i18n import t
from logger import get_module_logger
from replay import REPLAY_DIR, REPLAY_FORMAT_VERSION, list_replays
from theme import FONTS, TK

_log = get_module_logger("replay_viewer")


class ReplayViewer(tk.Toplevel):
    """리플레이 뷰어 (타임라인 슬라이더 + 프레임 데이터 표시)."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title(t("replay_title"))
        self.configure(bg=TK.BG)
        self.geometry("700x500")
        self.resizable(False, False)

        self._data: dict = {}
        self._frames: list[dict] = []
        self._playing = False
        self._play_speed = 1.0
        self._play_after_id: str | None = None
        self._loop = False

        self._build_ui()
        self._bind_keys()
        self._populate_replay_list()

    def _build_ui(self):
        # 상단: 리플레이 선택
        top = tk.Frame(self, bg=TK.BG)
        top.pack(fill="x", padx=12, pady=(10, 4))

        tk.Label(top, text=t("replay_file"), font=FONTS.BODY_BOLD, bg=TK.BG, fg=TK.TEXT).pack(side="left")

        self._replay_var = tk.StringVar()
        self._combo = ttk.Combobox(top, textvariable=self._replay_var, state="readonly", width=50)
        self._combo.pack(side="left", padx=6)
        self._combo.bind("<<ComboboxSelected>>", self._on_select)

        tk.Button(top, text=t("replay_browse"), font=FONTS.SMALL, command=self._browse).pack(side="left", padx=4)

        # 메타데이터
        meta_frame = tk.LabelFrame(
            self, text=f" {t('replay_metadata')} ", font=FONTS.BODY_BOLD, bg=TK.PANEL_BG, fg=TK.TEXT, bd=1
        )
        meta_frame.pack(fill="x", padx=12, pady=4)

        self._meta_label = tk.Label(
            meta_frame,
            text=t("replay_no_data"),
            font=FONTS.BODY,
            bg=TK.PANEL_BG,
            fg=TK.TEXT,
            anchor="w",
            justify="left",
        )
        self._meta_label.pack(fill="x", padx=8, pady=4)

        # 프레임 데이터 표시
        data_frame = tk.LabelFrame(
            self, text=f" {t('replay_frame_data')} ", font=FONTS.BODY_BOLD, bg=TK.PANEL_BG, fg=TK.TEXT, bd=1
        )
        data_frame.pack(fill="both", expand=True, padx=12, pady=4)

        self._frame_text = tk.Text(
            data_frame, bg=TK.SURFACE, fg=TK.TEXT, font=FONTS.BODY, state="disabled", wrap="word", bd=0, padx=8, pady=8
        )
        scrollbar = tk.Scrollbar(data_frame, command=self._frame_text.yview)
        self._frame_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._frame_text.pack(side="left", fill="both", expand=True)

        # 타임라인 슬라이더
        timeline_frame = tk.Frame(self, bg=TK.BG)
        timeline_frame.pack(fill="x", padx=12, pady=4)

        self._frame_var = tk.IntVar(value=0)
        self._slider = tk.Scale(
            timeline_frame,
            from_=0,
            to=0,
            orient="horizontal",
            variable=self._frame_var,
            command=self._on_slider,
            bg=TK.BG,
            fg=TK.TEXT,
            highlightthickness=0,
            troughcolor=TK.SURFACE,
            length=600,
        )
        self._slider.pack(fill="x")

        info_row = tk.Frame(timeline_frame, bg=TK.BG)
        info_row.pack(fill="x")

        self._frame_info = tk.Label(
            info_row, text=t("replay_frame_info", idx=0, total=0), font=FONTS.SMALL, bg=TK.BG, fg=TK.TEXT
        )
        self._frame_info.pack(side="left")

        self._progress_label = tk.Label(info_row, text="", font=FONTS.SMALL, bg=TK.BG, fg=TK.TEXT)
        self._progress_label.pack(side="right")

        # 컨트롤 버튼
        ctrl = tk.Frame(self, bg=TK.BG)
        ctrl.pack(pady=(0, 10))

        self._play_btn = tk.Button(ctrl, text=t("replay_play"), font=FONTS.BUTTON, width=8, command=self._toggle_play)
        self._play_btn.pack(side="left", padx=4)

        tk.Button(ctrl, text="|<", font=FONTS.SMALL, width=4, command=lambda: self._seek(0)).pack(side="left", padx=2)
        tk.Button(ctrl, text="<", font=FONTS.SMALL, width=4, command=lambda: self._step(-1)).pack(side="left", padx=2)
        tk.Button(ctrl, text=">", font=FONTS.SMALL, width=4, command=lambda: self._step(1)).pack(side="left", padx=2)
        tk.Button(ctrl, text=">|", font=FONTS.SMALL, width=4, command=lambda: self._seek(-1)).pack(side="left", padx=2)

        # 루프 토글
        self._loop_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            ctrl,
            text=t("replay_loop"),
            variable=self._loop_var,
            font=FONTS.SMALL,
            bg=TK.BG,
            fg=TK.TEXT,
            selectcolor=TK.SURFACE,
            command=self._on_loop_toggle,
        ).pack(side="left", padx=(8, 4))

        # 속도 조절
        tk.Label(ctrl, text=t("replay_speed"), font=FONTS.SMALL, bg=TK.BG, fg=TK.TEXT).pack(side="left", padx=(12, 2))
        self._speed_var = tk.StringVar(value="1x")
        self._speed_levels = [0.25, 0.5, 1, 2, 4]
        for spd, label in [(0.25, "0.25x"), (0.5, "0.5x"), (1, "1x"), (2, "2x"), (4, "4x")]:
            tk.Radiobutton(
                ctrl,
                text=label,
                variable=self._speed_var,
                value=label,
                font=FONTS.SMALL,
                bg=TK.BG,
                fg=TK.TEXT,
                selectcolor=TK.SURFACE,
                command=lambda s=spd: self._set_speed(s),
            ).pack(side="left")

        # 단축키 안내
        shortcut_label = tk.Label(self, text=t("replay_shortcuts"), font=FONTS.SMALL, bg=TK.BG, fg=TK.TEXT)
        shortcut_label.pack(pady=(0, 6))

    def _bind_keys(self):
        """키보드 단축키 바인딩."""
        self.bind("<space>", lambda e: self._toggle_play())
        self.bind("<Left>", lambda e: self._step(-1))
        self.bind("<Right>", lambda e: self._step(1))
        self.bind("<Shift-Left>", lambda e: self._step(-10))
        self.bind("<Shift-Right>", lambda e: self._step(10))
        self.bind("<Home>", lambda e: self._seek(0))
        self.bind("<End>", lambda e: self._seek(-1))
        self.bind("<plus>", lambda e: self._cycle_speed(1))
        self.bind("<equal>", lambda e: self._cycle_speed(1))
        self.bind("<minus>", lambda e: self._cycle_speed(-1))
        self.bind("<l>", lambda e: self._on_loop_toggle())
        self.focus_set()

    def _on_loop_toggle(self):
        """루프 재생 토글."""
        self._loop = self._loop_var.get() if hasattr(self, "_loop_var") else not self._loop
        if hasattr(self, "_loop_var"):
            self._loop_var.set(self._loop)

    def _cycle_speed(self, direction: int):
        """속도를 한 단계 올리거나(+1) 내린다(-1)."""
        try:
            cur_idx = self._speed_levels.index(self._play_speed)
        except ValueError:
            cur_idx = 2  # 1x
        new_idx = max(0, min(cur_idx + direction, len(self._speed_levels) - 1))
        spd = self._speed_levels[new_idx]
        self._set_speed(spd)
        self._speed_var.set(f"{spd}x" if spd != int(spd) else f"{int(spd)}x")

    def _populate_replay_list(self):
        """저장된 리플레이 목록 로드."""
        replays = list_replays()
        import os

        names = [os.path.basename(r) for r in replays]
        self._replay_paths = {os.path.basename(r): r for r in replays}
        self._combo["values"] = names

    def _on_select(self, _event=None):
        """리플레이 파일 선택."""
        name = self._replay_var.get()
        path = self._replay_paths.get(name, "")
        if path:
            self._load_replay(path)

    def _browse(self):
        """파일 탐색기로 리플레이 선택."""
        path = filedialog.askopenfilename(
            initialdir=REPLAY_DIR,
            filetypes=[("JSON", "*.json")],
            parent=self,
        )
        if path:
            self._load_replay(path)

    def _load_replay(self, path: str):
        """리플레이 파일 로드."""
        try:
            with open(path, encoding="utf-8") as f:
                self._data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self._meta_label.config(text=t("replay_load_error", error=e))
            return

        # 포맷 버전 검사
        file_ver = self._data.get("format_version", 0)
        if file_ver > REPLAY_FORMAT_VERSION:
            from tkinter import messagebox

            messagebox.showwarning(
                t("replay_title"),
                t("replay_version_warning", file_ver=file_ver, cur_ver=REPLAY_FORMAT_VERSION),
                parent=self,
            )

        self._frames = self._data.get("frames", [])
        meta = self._data.get("metadata", {})
        total = len(self._frames)

        # 메타데이터 표시 (버전 포함)
        ver_str = f"v{file_ver}" if file_ver else "legacy"
        meta_lines = [
            t("replay_module", name=meta.get("module", "?")),
            f"Format: {ver_str}",
            t("replay_total_frames", count=total),
            t("replay_start_time", time=meta.get("start_time", "?")),
        ]
        self._meta_label.config(text="  |  ".join(meta_lines))

        # 슬라이더 범위 업데이트
        self._slider.config(to=max(0, total - 1))
        self._frame_var.set(0)
        self._show_frame(0)

    def _show_frame(self, idx: int):
        """특정 프레임 데이터 표시."""
        total = len(self._frames)
        self._frame_info.config(text=t("replay_frame_info", idx=idx, total=total))

        # 진행률 + 예상 시간 (~60fps 기준)
        if total > 0:
            pct = int(idx / max(total - 1, 1) * 100)
            sec = round(idx / 60.0, 1)
            self._progress_label.config(text=t("replay_progress", pct=pct, sec=sec))
        else:
            self._progress_label.config(text="")

        if 0 <= idx < total:
            frame = self._frames[idx]
            text = json.dumps(frame, indent=2, ensure_ascii=False)
        else:
            text = t("replay_no_frame_data")

        self._frame_text.configure(state="normal")
        self._frame_text.delete("1.0", "end")
        self._frame_text.insert("1.0", text)
        self._frame_text.configure(state="disabled")

    def _on_slider(self, val):
        """슬라이더 조작."""
        self._show_frame(int(val))

    def _toggle_play(self):
        """재생/정지 토글."""
        if self._playing:
            self._playing = False
            self._play_btn.config(text=t("replay_play"))
            if self._play_after_id:
                self.after_cancel(self._play_after_id)
        else:
            if not self._frames:
                return
            self._playing = True
            self._play_btn.config(text=t("replay_pause"))
            self._auto_advance()

    def _auto_advance(self):
        """자동 프레임 전진."""
        if not self._playing or not self.winfo_exists():
            return
        idx = self._frame_var.get() + 1
        if idx >= len(self._frames):
            if self._loop:
                idx = 0
            else:
                self._playing = False
                self._play_btn.config(text=t("replay_play"))
                return
        self._frame_var.set(idx)
        self._slider.set(idx)
        self._show_frame(idx)
        delay = max(1, int(16 / self._play_speed))  # ~60fps at 1x
        self._play_after_id = self.after(delay, self._auto_advance)

    def _step(self, delta: int):
        """프레임 1칸 이동."""
        idx = max(0, min(self._frame_var.get() + delta, len(self._frames) - 1))
        self._frame_var.set(idx)
        self._slider.set(idx)
        self._show_frame(idx)

    def _seek(self, pos: int):
        """처음(0) 또는 끝(-1)으로 이동."""
        if pos == 0:
            idx = 0
        else:
            idx = max(0, len(self._frames) - 1)
        self._frame_var.set(idx)
        self._slider.set(idx)
        self._show_frame(idx)

    def _set_speed(self, speed: float):
        """재생 속도 설정."""
        self._play_speed = speed


def open_replay_viewer(master=None):
    """외부에서 호출하는 진입점."""
    ReplayViewer(master)
