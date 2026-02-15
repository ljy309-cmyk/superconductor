"""디지털 트윈 대시보드 — 전문가용 HMI 화면."""

import tkinter as tk
from datetime import datetime

from scada.cooler import CoolerState, CoolingSystem

# ── 색상 팔레트 ──────────────────────────────────────
BG = "#1e1e2e"
PANEL_BG = "#2a2a3d"
TEXT_FG = "#cdd6f4"
ACCENT = "#89b4fa"
GREEN = "#a6e3a1"
RED = "#f38ba8"
YELLOW = "#f9e2af"
GAUGE_BG = "#45475a"


class Dashboard(tk.Toplevel):
    """SCADA 디지털 트윈 대시보드 (HMI)."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title("SCADA — 액체 질소 냉각 모니터링")
        self.configure(bg=BG)
        self.geometry("900x520")
        self.resizable(False, False)

        self._cooler = CoolingSystem()
        self._cooler.add_listener(self._on_state_update)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI 구성 ──────────────────────────────────────────

    def _build_ui(self):
        # 상단 타이틀
        title = tk.Label(
            self,
            text="Liquid Nitrogen Cooling — Digital Twin",
            font=("Consolas", 14, "bold"),
            bg=BG,
            fg=ACCENT,
        )
        title.pack(pady=(12, 6))

        # 메인 프레임 (좌·우 분할)
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        # ── 좌측: 실시간 온도 텍스트 로그 ──
        left = tk.LabelFrame(
            body,
            text=" Temperature Log ",
            font=("Consolas", 10, "bold"),
            bg=PANEL_BG,
            fg=TEXT_FG,
            bd=1,
        )
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self._log = tk.Text(
            left,
            bg="#181825",
            fg=TEXT_FG,
            font=("Consolas", 10),
            state="disabled",
            wrap="none",
            bd=0,
            padx=8,
            pady=8,
        )
        scrollbar = tk.Scrollbar(left, command=self._log.yview)
        self._log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._log.pack(side="left", fill="both", expand=True)

        # ── 우측: 시스템 상태 게이지 패널 ──
        right = tk.LabelFrame(
            body,
            text=" System Status ",
            font=("Consolas", 10, "bold"),
            bg=PANEL_BG,
            fg=TEXT_FG,
            bd=1,
        )
        right.pack(side="right", fill="both", padx=(6, 0))

        # 현재 온도 표시
        self._temp_var = tk.StringVar(value="-- °C")
        tk.Label(
            right, text="현재 온도", font=("Consolas", 9), bg=PANEL_BG, fg=TEXT_FG
        ).pack(pady=(12, 0))
        self._temp_label = tk.Label(
            right,
            textvariable=self._temp_var,
            font=("Consolas", 22, "bold"),
            bg=PANEL_BG,
            fg=ACCENT,
        )
        self._temp_label.pack()

        # 게이지 바 (Canvas)
        tk.Label(
            right, text="냉각 게이지", font=("Consolas", 9), bg=PANEL_BG, fg=TEXT_FG
        ).pack(pady=(16, 4))
        self._gauge_canvas = tk.Canvas(
            right, width=60, height=220, bg=PANEL_BG, highlightthickness=0
        )
        self._gauge_canvas.pack()
        self._draw_gauge_frame()

        # 상태 인디케이터
        self._status_var = tk.StringVar(value="STOPPED")
        self._cooling_var = tk.StringVar(value="냉각기: OFF")
        self._emergency_var = tk.StringVar(value="긴급 냉각: OFF")

        for var in (self._status_var, self._cooling_var, self._emergency_var):
            tk.Label(
                right,
                textvariable=var,
                font=("Consolas", 10, "bold"),
                bg=PANEL_BG,
                fg=TEXT_FG,
            ).pack(pady=2)

        # 하단 제어 버튼
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(pady=(0, 12))

        self._start_btn = tk.Button(
            btn_frame,
            text="START",
            width=12,
            font=("Consolas", 10, "bold"),
            bg=GREEN,
            fg="#1e1e2e",
            command=self._start,
        )
        self._start_btn.pack(side="left", padx=6)

        self._stop_btn = tk.Button(
            btn_frame,
            text="STOP",
            width=12,
            font=("Consolas", 10, "bold"),
            bg=RED,
            fg="#1e1e2e",
            command=self._stop,
            state="disabled",
        )
        self._stop_btn.pack(side="left", padx=6)

    # ── 게이지 바 ────────────────────────────────────────

    def _draw_gauge_frame(self):
        c = self._gauge_canvas
        # 배경 바
        c.create_rectangle(15, 10, 45, 210, fill=GAUGE_BG, outline="#585b70", width=1)
        # 눈금 레이블
        marks = [("25°C", 10), ("-50", 52), ("-100", 94), ("-150", 136), ("-196", 180), ("-210", 210)]
        for label, y in marks:
            c.create_text(58, y, text=label, anchor="w", fill=TEXT_FG, font=("Consolas", 7))
            c.create_line(45, y, 50, y, fill="#585b70")
        # 채워질 바 (태그로 업데이트)
        c.create_rectangle(17, 210, 43, 210, fill=ACCENT, outline="", tags="bar")

    def _update_gauge(self, temperature: float):
        c = self._gauge_canvas
        # 온도 범위: 25 ~ -210 → y 범위: 10 ~ 210
        t_min, t_max = -210.0, 25.0
        y_top, y_bot = 10, 210
        ratio = (t_max - temperature) / (t_max - t_min)
        ratio = max(0.0, min(1.0, ratio))
        bar_top = y_top + ratio * (y_bot - y_top)

        # 색상 결정
        if temperature <= -196:
            color = GREEN
        elif temperature <= -190:
            color = YELLOW
        else:
            color = RED

        c.delete("bar")
        c.create_rectangle(17, bar_top, 43, y_bot, fill=color, outline="", tags="bar")

    # ── 콜백 / 제어 ─────────────────────────────────────

    def _on_state_update(self, state: CoolerState):
        # 백그라운드 스레드에서 호출되므로 after 로 GUI 스레드에 전달
        self.after(0, self._apply_state, state)

    def _apply_state(self, state: CoolerState):
        if not self.winfo_exists():
            return

        # 온도 텍스트
        self._temp_var.set(f"{state.temperature:.2f} °C")

        # 온도 라벨 색상
        if state.temperature <= state.target:
            self._temp_label.config(fg=GREEN)
        elif state.emergency:
            self._temp_label.config(fg=RED)
        else:
            self._temp_label.config(fg=ACCENT)

        # 게이지 업데이트
        self._update_gauge(state.temperature)

        # 상태 텍스트
        if state.emergency:
            self._status_var.set("⚠ EMERGENCY")
        elif state.cooling_on:
            self._status_var.set("COOLING")
        else:
            self._status_var.set("STANDBY")

        self._cooling_var.set(f"냉각기: {'ON' if state.cooling_on else 'OFF'}")
        self._emergency_var.set(f"긴급 냉각: {'ON' if state.emergency else 'OFF'}")

        # 로그 기록
        ts = datetime.now().strftime("%H:%M:%S")
        mode = "EMRG" if state.emergency else ("COOL" if state.cooling_on else "IDLE")
        line = f"[{ts}] {state.temperature:>8.2f}°C  | {mode}\n"
        self._log.configure(state="normal")
        self._log.insert("end", line)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _start(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._cooler.start()
        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._status_var.set("RUNNING")

    def _stop(self):
        self._cooler.stop()
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._status_var.set("STOPPED")

    def _on_close(self):
        self._cooler.stop()
        self.destroy()


def open_dashboard(master=None):
    """외부에서 대시보드를 여는 진입점."""
    Dashboard(master)
