"""첨단 센서 및 암호 보안 — 서브 메뉴 런처."""

import tkinter as tk

from security.squid_mines import open_squid_mines
from security.bb84_defense import open_bb84_defense

BG = "#1e1e2e"
FG = "#cdd6f4"
ACCENT = "#f9e2af"


class SecurityLauncher(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("첨단 센서 및 암호 보안")
        self.configure(bg=BG)
        self.resizable(False, False)

        frame = tk.Frame(self, bg=BG, padx=24, pady=20)
        frame.pack()

        tk.Label(
            frame, text="Security & Sensors", font=("Consolas", 14, "bold"),
            bg=BG, fg=ACCENT,
        ).pack(pady=(0, 14))

        buttons = [
            ("4-1. SQUID 지뢰찾기 (Magnetic Flux Sensor)", self._launch_squid),
            ("4-2. BB84 양자 암호 통신 방어전", self._launch_bb84),
        ]

        for text, cmd in buttons:
            tk.Button(
                frame, text=text, command=cmd,
                width=42, height=2, font=("Consolas", 10),
            ).pack(pady=4)

    def _launch_squid(self):
        self.withdraw()
        open_squid_mines()
        self.deiconify()

    def _launch_bb84(self):
        self.withdraw()
        open_bb84_defense()
        self.deiconify()


def open_security_launcher(master=None):
    SecurityLauncher(master)
