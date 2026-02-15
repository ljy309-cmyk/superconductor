"""데이터 사이언스, AI & 글로벌 서버 — 서브 메뉴 런처."""

import tkinter as tk

from data_ai.tc_predictor import open_tc_predictor
from data_ai.qrng_logger import open_qrng_logger

BG = "#1e1e2e"
FG = "#cdd6f4"
ACCENT = "#a6e3a1"


class DataAILauncher(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("데이터 사이언스 & AI")
        self.configure(bg=BG)
        self.resizable(False, False)

        frame = tk.Frame(self, bg=BG, padx=24, pady=20)
        frame.pack()

        tk.Label(
            frame, text="Data Science & AI", font=("Consolas", 14, "bold"),
            bg=BG, fg=ACCENT,
        ).pack(pady=(0, 14))

        buttons = [
            ("5-1. AI 신소재 Tc 예측 (RandomForest)", self._launch_tc_predictor),
            ("5-2. QRNG 양자 난수 생성 로그", self._launch_qrng),
        ]

        for text, cmd in buttons:
            tk.Button(
                frame, text=text, command=cmd,
                width=42, height=2, font=("Consolas", 10),
            ).pack(pady=4)

    def _launch_tc_predictor(self):
        open_tc_predictor(self)

    def _launch_qrng(self):
        open_qrng_logger(self)


def open_data_ai_launcher(master=None):
    DataAILauncher(master)
