"""글로벌 멀티플레이어 랭킹 GUI (Tkinter).

- 로컬 REST API 서버에 requests로 점수 POST / 랭킹 GET
- 큐비트 생존 시간 기반 점수 경쟁
- 상위 5위 랭킹 보드
"""

import tkinter as tk
from tkinter import ttk, messagebox

import requests

from data_ai.ranking_server import start_server, get_base_url

BG = "#1e1e2e"
FG = "#cdd6f4"
ACCENT = "#a6e3a1"
GOLD = "#f9e2af"
SILVER = "#bac2de"
BRONZE = "#fab387"

RANK_COLORS = {1: GOLD, 2: SILVER, 3: BRONZE}


class RankingApp(tk.Toplevel):
    """글로벌 랭킹 GUI."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title("Global Qubit Survival Ranking")
        self.configure(bg=BG)
        self.geometry("700x560")
        self.resizable(False, False)

        # 서버 시작
        start_server()
        self.base_url = get_base_url()

        self._build_ui()
        self._refresh_ranking()

    def _build_ui(self):
        # ── 타이틀 ───────────────────────────────────
        tk.Label(
            self, text="Global Ranking", font=("Consolas", 18, "bold"),
            bg=BG, fg=GOLD,
        ).pack(pady=(14, 4))
        tk.Label(
            self, text="Qubit Survival Time Leaderboard", font=("Consolas", 10),
            bg=BG, fg=FG,
        ).pack(pady=(0, 10))

        # ── 랭킹 보드 (상위 5위) ────────────────────
        board_frame = tk.LabelFrame(
            self, text="  TOP 5  ", font=("Consolas", 12, "bold"),
            bg=BG, fg=GOLD, padx=12, pady=8,
        )
        board_frame.pack(fill=tk.X, padx=20, pady=(0, 8))

        self.rank_labels: list[tk.Label] = []
        for i in range(5):
            color = RANK_COLORS.get(i + 1, FG)
            medal = {0: "1st", 1: "2nd", 2: "3rd"}.get(i, f"{i+1}th")
            lbl = tk.Label(
                board_frame,
                text=f"  {medal}   ---",
                font=("Consolas", 13 if i < 3 else 11, "bold" if i < 3 else ""),
                bg=BG, fg=color, anchor="w",
            )
            lbl.pack(fill=tk.X, pady=2)
            self.rank_labels.append(lbl)

        # ── 점수 등록 패널 ───────────────────────────
        submit_frame = tk.LabelFrame(
            self, text="  Submit Score  ", font=("Consolas", 11, "bold"),
            bg=BG, fg=ACCENT, padx=12, pady=10,
        )
        submit_frame.pack(fill=tk.X, padx=20, pady=8)

        row1 = tk.Frame(submit_frame, bg=BG)
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="Player Name:", font=("Consolas", 10), bg=BG, fg=FG, width=14, anchor="w").pack(side=tk.LEFT)
        self.name_entry = tk.Entry(row1, font=("Consolas", 11), width=20)
        self.name_entry.insert(0, "Player1")
        self.name_entry.pack(side=tk.LEFT, padx=4)

        row2 = tk.Frame(submit_frame, bg=BG)
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="Survival (sec):", font=("Consolas", 10), bg=BG, fg=FG, width=14, anchor="w").pack(side=tk.LEFT)
        self.score_entry = tk.Entry(row2, font=("Consolas", 11), width=20)
        self.score_entry.insert(0, "0.0")
        self.score_entry.pack(side=tk.LEFT, padx=4)

        row3 = tk.Frame(submit_frame, bg=BG)
        row3.pack(fill=tk.X, pady=2)
        tk.Label(row3, text="Game Mode:", font=("Consolas", 10), bg=BG, fg=FG, width=14, anchor="w").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="QEC Shield")
        modes = ["QEC Shield", "Entanglement Cascade", "Free Play"]
        ttk.Combobox(row3, textvariable=self.mode_var, values=modes, width=18, state="readonly").pack(side=tk.LEFT, padx=4)

        btn_row = tk.Frame(submit_frame, bg=BG)
        btn_row.pack(fill=tk.X, pady=(8, 0))

        tk.Button(
            btn_row, text="POST Score", command=self._submit_score,
            font=("Consolas", 10, "bold"), width=14,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_row, text="GET Refresh", command=self._refresh_ranking,
            font=("Consolas", 10), width=14,
        ).pack(side=tk.LEFT, padx=4)

        self.submit_status = tk.StringVar(value="")
        tk.Label(
            btn_row, textvariable=self.submit_status, font=("Consolas", 9),
            bg=BG, fg=ACCENT,
        ).pack(side=tk.LEFT, padx=8)

        # ── 전체 기록 테이블 ─────────────────────────
        log_frame = tk.LabelFrame(
            self, text="  All Records  ", font=("Consolas", 11, "bold"),
            bg=BG, fg=ACCENT, padx=8, pady=6,
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

    # ── REST API 호출 ────────────────────────────────

    def _submit_score(self):
        """POST /ranking — 점수 등록."""
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

        try:
            resp = requests.post(f"{self.base_url}/ranking", json=payload, timeout=5)
            if resp.status_code == 201:
                data = resp.json()
                rank = data.get("rank", "?")
                self.submit_status.set(f"Registered! Current rank: #{rank}")
            else:
                self.submit_status.set(f"Server error: {resp.status_code}")
        except requests.RequestException as e:
            self.submit_status.set(f"Connection failed: {e}")

        self._refresh_ranking()

    def _refresh_ranking(self):
        """GET /ranking — 상위 5위 + 전체 기록 갱신."""
        # 상위 5위
        try:
            resp = requests.get(f"{self.base_url}/ranking", timeout=5)
            if resp.status_code == 200:
                top5 = resp.json()
                for i, lbl in enumerate(self.rank_labels):
                    if i < len(top5):
                        r = top5[i]
                        medal = {0: "1st", 1: "2nd", 2: "3rd"}.get(i, f"{i+1}th")
                        lbl.configure(text=f"  {medal}   {r['name']:16s}  {r['score']:8.2f}s   ({r.get('mode', '')})")
                    else:
                        medal = {0: "1st", 1: "2nd", 2: "3rd"}.get(i, f"{i+1}th")
                        lbl.configure(text=f"  {medal}   ---")
        except requests.RequestException:
            pass

        # 전체 기록
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
            pass


def open_ranking(master=None):
    """외부에서 호출하는 진입점."""
    RankingApp(master)
