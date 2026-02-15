"""양자 역학 시뮬레이터 — 서브 메뉴 런처."""

import tkinter as tk

from quantum.qubit_chain import open_qubit_chain
from quantum.tunneling import open_tunneling
from quantum.qec_shield import open_qec_shield

BG = "#1e1e2e"
FG = "#cdd6f4"
ACCENT = "#cba6f7"


class QuantumLauncher(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("양자 역학 시뮬레이터")
        self.configure(bg=BG)
        self.resizable(False, False)

        frame = tk.Frame(self, bg=BG, padx=24, pady=20)
        frame.pack()

        tk.Label(
            frame, text="Quantum Mechanics", font=("Consolas", 14, "bold"),
            bg=BG, fg=ACCENT,
        ).pack(pady=(0, 14))

        buttons = [
            ("3-1. 큐비트 연쇄 붕괴 (Entanglement Cascade)", self._launch_qubit_chain),
            ("3-2. 양자 중첩 및 터널링 (Tunneling)", self._launch_tunneling),
            ("3-3. 양자 오류 정정 (QEC Shield)", self._launch_qec_shield),
        ]

        for text, cmd in buttons:
            tk.Button(
                frame, text=text, command=cmd,
                width=42, height=2, font=("Consolas", 10),
            ).pack(pady=4)

    def _launch_qubit_chain(self):
        self.withdraw()
        open_qubit_chain()
        self.deiconify()

    def _launch_tunneling(self):
        self.withdraw()
        open_tunneling()
        self.deiconify()

    def _launch_qec_shield(self):
        self.withdraw()
        open_qec_shield()
        self.deiconify()


def open_quantum_launcher(master=None):
    QuantumLauncher(master)
