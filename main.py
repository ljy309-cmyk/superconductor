import tkinter as tk
from tkinter import messagebox

from scada.dashboard import open_dashboard


# 기능 함수 정의 (나중에 구현)
def function_2():
    messagebox.showinfo("기능 2", "기능 2은 아직 구현되지 않았습니다.")


def function_3():
    messagebox.showinfo("기능 3", "기능 3은 아직 구현되지 않았습니다.")


def function_4():
    messagebox.showinfo("기능 4", "기능 4은 아직 구현되지 않았습니다.")


def function_5():
    messagebox.showinfo("기능 5", "기능 5은 아직 구현되지 않았습니다.")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Superconductor")
        self.resizable(False, False)

        # 버튼 목록: (이름, 실행할 함수) — 여기에 추가하면 자동으로 버튼 생성
        self._buttons = [
            ("1. 임베디드 제어 및 모니터링 (SCADA)", lambda: open_dashboard(self)),
            ("2. 기능 2", function_2),
            ("3. 기능 3", function_3),
            ("4. 기능 4", function_4),
            ("5. 기능 5", function_5),
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
