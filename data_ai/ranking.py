"""글로벌 멀티플레이어 랭킹 GUI (Tkinter).

- 로컬 REST API 서버에 requests로 점수 POST / 랭킹 GET
- 큐비트 생존 시간 기반 점수 경쟁
- 상위 5위 랭킹 보드
"""

import tkinter as tk
from tkinter import ttk, messagebox

import requests

from data_ai.ranking_server import start_server, get_base_url
from theme import get_tk_theme, FONTS


class RankingApp(tk.Toplevel):
    """글로벌 랭킹 GUI."""

    def __init__(self, master=None):
        super().__init__(master)
        self._th = get_tk_theme()
        self.title("Global Qubit Survival Ranking")
        self.configure(bg=self._th.BG)
        self.geometry("700x560")
        self.resizable(False, False)

        # 서버 시작
        start_server()
        self.base_url = get_base_url()

        # 미션1: 연결 상태 관리
        self.online = False
        # 미션2: 1등 점수 기록
        self.top1_score = 0.0

        self._build_ui()
        self._refresh_ranking()

    def _build_ui(self):
        th = self._th
        RANK_COLORS = {1: th.GOLD, 2: th.SILVER, 3: th.BRONZE}

        # ── 타이틀 ───────────────────────────────────
        tk.Label(
            self, text="Global Ranking", font=FONTS.TITLE,
            bg=th.BG, fg=th.GOLD,
        ).pack(pady=(14, 4))
        tk.Label(
            self, text="Qubit Survival Time Leaderboard", font=FONTS.BODY,
            bg=th.BG, fg=th.TEXT,
        ).pack(pady=(0, 4))

        # 미션1: 서버 연결 상태 표시
        self.conn_var = tk.StringVar(value="Connecting...")
        self.conn_label = tk.Label(
            self, textvariable=self.conn_var, font=FONTS.BODY_BOLD,
            bg=th.BG, fg=th.TEXT,
        )
        self.conn_label.pack(pady=(0, 6))

        # ── 랭킹 보드 (상위 5위) ────────────────────
        board_frame = tk.LabelFrame(
            self, text="  TOP 5  ", font=FONTS.HEADING,
            bg=th.BG, fg=th.GOLD, padx=12, pady=8,
        )
        board_frame.pack(fill=tk.X, padx=20, pady=(0, 8))

        self.rank_labels: list[tk.Label] = []
        for i in range(5):
            color = RANK_COLORS.get(i + 1, th.TEXT)
            medal = {0: "1st", 1: "2nd", 2: "3rd"}.get(i, f"{i+1}th")
            lbl = tk.Label(
                board_frame,
                text=f"  {medal}   ---",
                font=(FONTS.FAMILY, 13 if i < 3 else 11, "bold" if i < 3 else ""),
                bg=th.BG, fg=color, anchor="w",
            )
            lbl.pack(fill=tk.X, pady=2)
            self.rank_labels.append(lbl)

        # ── 점수 등록 패널 ───────────────────────────
        submit_frame = tk.LabelFrame(
            self, text="  Submit Score  ", font=FONTS.HEADING,
            bg=th.BG, fg=th.ACCENT_GREEN, padx=12, pady=10,
        )
        submit_frame.pack(fill=tk.X, padx=20, pady=8)

        row1 = tk.Frame(submit_frame, bg=th.BG)
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="Player Name:", font=FONTS.BODY, bg=th.BG, fg=th.TEXT, width=14, anchor="w").pack(side=tk.LEFT)
        self.name_entry = tk.Entry(row1, font=FONTS.MONO_11, width=20)
        self.name_entry.insert(0, "Player1")
        self.name_entry.pack(side=tk.LEFT, padx=4)

        row2 = tk.Frame(submit_frame, bg=th.BG)
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="Survival (sec):", font=FONTS.BODY, bg=th.BG, fg=th.TEXT, width=14, anchor="w").pack(side=tk.LEFT)
        self.score_entry = tk.Entry(row2, font=FONTS.MONO_11, width=20)
        self.score_entry.insert(0, "0.0")
        self.score_entry.pack(side=tk.LEFT, padx=4)

        row3 = tk.Frame(submit_frame, bg=th.BG)
        row3.pack(fill=tk.X, pady=2)
        tk.Label(row3, text="Game Mode:", font=FONTS.BODY, bg=th.BG, fg=th.TEXT, width=14, anchor="w").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="QEC Shield")
        modes = ["QEC Shield", "Entanglement Cascade", "Free Play"]
        ttk.Combobox(row3, textvariable=self.mode_var, values=modes, width=18, state="readonly").pack(side=tk.LEFT, padx=4)

        btn_row = tk.Frame(submit_frame, bg=th.BG)
        btn_row.pack(fill=tk.X, pady=(8, 0))

        tk.Button(
            btn_row, text="POST Score", command=self._submit_score,
            font=FONTS.BODY_BOLD, width=14,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_row, text="GET Refresh", command=self._refresh_ranking,
            font=FONTS.BODY, width=14,
        ).pack(side=tk.LEFT, padx=4)

        self.submit_status = tk.StringVar(value="")
        tk.Label(
            btn_row, textvariable=self.submit_status, font=FONTS.SMALL,
            bg=th.BG, fg=th.ACCENT_GREEN,
        ).pack(side=tk.LEFT, padx=8)

        # 미션2: 점수 비교 결과 표시
        self.compare_var = tk.StringVar(value="")
        tk.Label(
            submit_frame, textvariable=self.compare_var, font=FONTS.MONO_11,
            bg=th.BG, fg=th.GOLD, wraplength=620,
        ).pack(fill=tk.X, pady=(6, 0))

        # ── 전체 기록 테이블 ─────────────────────────
        log_frame = tk.LabelFrame(
            self, text="  All Records  ", font=FONTS.HEADING,
            bg=th.BG, fg=th.ACCENT_GREEN, padx=8, pady=6,
        )
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(4, 14))

        columns = ("rank", "name", "score", "mode", "timestamp")
        self.tree = ttk.Treeview(log_frame, columns=columns, show="headings", height=6)
        self.tree.heading("rank", text="#")
        self.tree.heading("name", text="Player")
        self.tree.heading("score", text="Score (s)")
        self.tree.heading("mode", text="Mode")
        self.tree.heading("timestamp", text="Timestamp")
        self.tree.column("rank", width=36)
        self.tree.column("name", width=120)
        self.tree.column("score", width=80)
        self.tree.column("mode", width=150)
        self.tree.column("timestamp", width=160)

        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ── 하단 도구 버튼 ──────────────────────────────
        tool_row = tk.Frame(self, bg=th.BG)
        tool_row.pack(fill=tk.X, padx=20, pady=(0, 8))

        tk.Button(
            tool_row, text="Save Profile", command=self._save_profile,
            font=FONTS.SMALL, width=14,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            tool_row, text="Load Profile", command=self._load_profile,
            font=FONTS.SMALL, width=14,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            tool_row, text="Stats Dashboard", command=self._open_stats,
            font=(FONTS.FAMILY, 9, "bold"), width=16, fg=th.ACCENT_BLUE,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            tool_row, text="Achievements", command=self._open_achievements,
            font=FONTS.SMALL, width=14, fg=th.GOLD,
        ).pack(side=tk.LEFT, padx=4)

    # ── 프로파일 관리 ─────────────────────────────────

    def _save_profile(self):
        """현재 플레이어 설정을 프로파일로 저장."""
        from presets import save_profile
        name = self.name_entry.get().strip() or "default"
        data = {
            "player_name": name,
            "game_mode": self.mode_var.get(),
        }
        save_profile(f"ranking_{name}", data)
        messagebox.showinfo("Profile", f"Profile '{name}' saved.", parent=self)

    def _load_profile(self):
        """프로파일 불러오기."""
        from presets import list_profiles, load_profile
        profiles = list_profiles()
        ranking_profiles = [p for p in profiles if p.startswith("ranking_")]
        if not ranking_profiles:
            messagebox.showinfo("Profile", "No saved profiles.", parent=self)
            return

        th = self._th
        win = tk.Toplevel(self)
        win.title("Load Profile")
        win.configure(bg=th.BG)
        win.geometry("300x200")

        tk.Label(win, text="Select Profile:", font=FONTS.BODY_BOLD,
                 bg=th.BG, fg=th.TEXT).pack(pady=8)

        listbox = tk.Listbox(win, font=FONTS.BODY, height=5)
        for p in ranking_profiles:
            listbox.insert(tk.END, p)
        listbox.pack(fill=tk.X, padx=12)

        def _apply():
            sel = listbox.curselection()
            if sel:
                profile_name = ranking_profiles[sel[0]]
                data = load_profile(profile_name)
                if "player_name" in data:
                    self.name_entry.delete(0, tk.END)
                    self.name_entry.insert(0, data["player_name"])
                if "game_mode" in data:
                    self.mode_var.set(data["game_mode"])
            win.destroy()

        tk.Button(win, text="Load", command=_apply,
                  font=FONTS.BODY_BOLD, width=10).pack(pady=8)

    def _open_stats(self):
        """통계 대시보드 열기."""
        try:
            from stats_dashboard import open_stats_dashboard
            open_stats_dashboard(self)
        except Exception:
            messagebox.showerror("Error", "Stats dashboard unavailable.", parent=self)

    def _open_achievements(self):
        """업적 목록 표시."""
        try:
            from achievements import get_all_achievements, get_unlocked_count
            unlocked, total = get_unlocked_count()
            achievements = get_all_achievements()

            th = self._th
            win = tk.Toplevel(self)
            win.title(f"Achievements ({unlocked}/{total})")
            win.configure(bg=th.BG)
            win.geometry("500x400")

            tk.Label(win, text=f"Achievements: {unlocked}/{total}",
                     font=FONTS.HEADING, bg=th.BG, fg=th.GOLD).pack(pady=8)

            text = tk.Text(win, bg=th.SURFACE, fg=th.TEXT, font=FONTS.BODY,
                           state="normal", wrap="word", padx=8, pady=8)
            text.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

            for ach in achievements:
                status = "[*]" if ach["unlocked"] else "[ ]"
                text.insert(tk.END, f" {status} [{ach['icon']}] {ach['title']}\n")
                text.insert(tk.END, f"      {ach['desc']}\n\n")

            text.configure(state="disabled")
        except Exception:
            messagebox.showerror("Error", "Achievement system unavailable.", parent=self)

    # ── REST API 호출 ────────────────────────────────

    def _submit_score(self):
        """POST /ranking — 미션1: 에러 핸들링 + 미션2: 점수 비교."""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("입력 오류", "플레이어 이름을 입력하세요.", parent=self)
            return

        try:
            score = float(self.score_entry.get())
        except ValueError:
            messagebox.showwarning("입력 오류", "점수에 숫자를 입력하세요.", parent=self)
            return

        payload = {
            "name": name,
            "score": score,
            "mode": self.mode_var.get(),
        }

        th = self._th
        # 미션1: try-except로 방어적 프로그래밍 (Defensive Programming)
        try:
            resp = requests.post(f"{self.base_url}/ranking", json=payload, timeout=5)
            if resp.status_code == 201:
                data = resp.json()
                rank = data.get("rank", "?")
                self.submit_status.set(f"Registered! Current rank: #{rank}")
                self.online = True
                # 미션2: 점수 비교 로직
                self._compare_score(score)
            else:
                self.submit_status.set(f"Server error: {resp.status_code}")
        except requests.RequestException:
            # 미션1: 인터넷 끊김 → 프로그램이 죽지 않고 안내 메시지 표시
            self.online = False
            self.conn_var.set("[OFFLINE] 인터넷 연결 실패! 오프라인 모드 가동")
            self.conn_label.configure(fg=th.RED)
            self.submit_status.set("전송 실패 -- 오프라인 모드 (점수 미등록)")

        self._refresh_ranking()

    def _refresh_ranking(self):
        """GET /ranking — 미션1: 오프라인 대비 방어적 프로그래밍."""
        th = self._th
        # 상위 5위 (GET 요청)
        try:
            resp = requests.get(f"{self.base_url}/ranking", timeout=5)
            if resp.status_code == 200:
                self.online = True
                self.conn_var.set("[ONLINE] 서버 연결 성공")
                self.conn_label.configure(fg=th.GREEN)

                top5 = resp.json()
                # 미션2: 1등 점수 저장 (비교용)
                if top5:
                    self.top1_score = top5[0].get("score", 0)

                for i, lbl in enumerate(self.rank_labels):
                    if i < len(top5):
                        r = top5[i]
                        medal = {0: "1st", 1: "2nd", 2: "3rd"}.get(i, f"{i+1}th")
                        lbl.configure(text=f"  {medal}   {r['name']:16s}  {r['score']:8.2f}s   ({r.get('mode', '')})")
                    else:
                        medal = {0: "1st", 1: "2nd", 2: "3rd"}.get(i, f"{i+1}th")
                        lbl.configure(text=f"  {medal}   ---")
        except requests.RequestException:
            # 미션1: except 문이 작동하여 프로그램을 보호
            self.online = False
            self.conn_var.set("[OFFLINE] 인터넷 연결 실패! 오프라인 모드 가동")
            self.conn_label.configure(fg=th.RED)

        # 전체 기록 (GET 요청)
        try:
            resp = requests.get(f"{self.base_url}/ranking/all", timeout=5)
            if resp.status_code == 200:
                records = resp.json()
                for item in self.tree.get_children():
                    self.tree.delete(item)
                for i, r in enumerate(records):
                    self.tree.insert("", tk.END, values=(
                        i + 1,
                        r.get("name", ""),
                        f"{r.get('score', 0):.2f}",
                        r.get("mode", ""),
                        r.get("timestamp", ""),
                    ))
        except requests.RequestException:
            pass  # 미션1: 오프라인이면 조용히 넘어감

    # ── 미션2: 점수 비교 로직 ─────────────────────────

    def _compare_score(self, my_score: float):
        """미션2: 내 점수(my_score)와 1등 점수 비교 — if/else 조건문."""
        if self.top1_score > 0 and my_score > self.top1_score:
            # 내 점수가 1등보다 높으면 → 신기록!
            self.compare_var.set(
                f"*** 신기록 달성!! *** "
                f"({my_score:.2f}s > 기존 1등 {self.top1_score:.2f}s)"
            )
        elif self.top1_score > 0:
            # 낮으면 → 아쉽습니다
            diff = self.top1_score - my_score
            self.compare_var.set(
                f"아쉽습니다. 다음 기회에! (1등까지 {diff:.2f}초 부족)"
            )
        else:
            # 첫 기록
            self.compare_var.set("첫 기록 등록! 당신이 1등!")


def open_ranking(master=None):
    """외부에서 호출하는 진입점."""
    RankingApp(master)
