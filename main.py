import tkinter as tk

from scada.dashboard import open_dashboard
from physics.launcher import open_physics_launcher
from quantum.launcher import open_quantum_launcher
from security.launcher import open_security_launcher
from data_ai.launcher import open_data_ai_launcher


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Superconductor")
        self.resizable(False, False)

        # 버튼 목록: (이름, 실행할 함수) — 여기에 추가하면 자동으로 버튼 생성
        self._buttons = [
            ("1. 임베디드 제어 및 모니터링 (SCADA)", lambda: open_dashboard(self)),
            ("2. 초전도 물리 엔진 (Physics)", lambda: open_physics_launcher(self)),
            ("3. 양자 역학 시뮬레이터 (Quantum)", lambda: open_quantum_launcher(self)),
            ("4. 첨단 센서 및 암호 보안 (Security)", lambda: open_security_launcher(self)),
            ("5. 데이터 사이언스 & AI (Data)", lambda: open_data_ai_launcher(self)),
        ]

        self._create_widgets()
        self._center_window()

    def _create_widgets(self):
        frame = tk.Frame(self, padx=20, pady=20)
        frame.pack()

        tk.Label(frame, text="메뉴를 선택하세요", font=("Arial", 14, "bold")).pack(
            pady=(0, 15)
        )

        for name, command in self._buttons:
            tk.Button(
                frame, text=name, command=command, width=35, height=2
            ).pack(pady=4)

    def _center_window(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")


if __name__ == "__main__":
    App().mainloop()
