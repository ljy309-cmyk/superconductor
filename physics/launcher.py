"""초전도 물리 엔진 — 서브 메뉴 런처."""

import tkinter as tk

from physics.phase_transition import open_phase_transition
from physics.flux_pinning import open_flux_pinning

BG = "#1e1e2e"
FG = "#cdd6f4"
ACCENT = "#89b4fa"


class PhysicsLauncher(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("초전도 물리 엔진")
        self.configure(bg=BG)
        self.resizable(False, False)

        frame = tk.Frame(self, bg=BG, padx=24, pady=20)
        frame.pack()

        tk.Label(
            frame, text="Physics Engine", font=("Consolas", 14, "bold"),
            bg=BG, fg=ACCENT,
        ).pack(pady=(0, 14))

        buttons = [
            ("2-1. 상전이 시각화 (Phase Transition)", lambda: open_phase_transition(self)),
            ("2-2. 마이스너 부상 & 플럭스 피닝", self._launch_flux_pinning),
        ]

        for text, cmd in buttons:
            tk.Button(
                frame, text=text, command=cmd,
                width=38, height=2, font=("Consolas", 10),
            ).pack(pady=4)

    def _launch_flux_pinning(self):
        self.withdraw()
        open_flux_pinning()
        self.deiconify()


def open_physics_launcher(master=None):
    PhysicsLauncher(master)
