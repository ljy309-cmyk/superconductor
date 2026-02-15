"""상전이(Phase Transition) 시각화 — 온도-저항 관계 그래프."""

import tkinter as tk

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# ── 물리 상수 ────────────────────────────────────────
T_C = -196.0        # 임계 온도 (°C)
R_NORMAL = 1.0      # 정규화된 상온 저항 (임의 단위)
T_RANGE = (-250, 50)  # 그래프 온도 범위


def resistance(t: np.ndarray) -> np.ndarray:
    """온도에 따른 저항값 계산.

    T > T_c : 온도에 비례하는 선형 저항 (금속 특성)
    T ≤ T_c : 저항 = 0 (초전도 상태)
    """
    r = np.where(
        t > T_C,
        R_NORMAL * (t - T_C) / (0 - T_C),  # T_c에서 0, 0°C에서 R_NORMAL
        0.0,
    )
    return np.clip(r, 0, None)


class PhaseTransitionWindow(tk.Toplevel):
    """상전이 시각화 윈도우."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title("상전이 시각화 — 온도 vs 저항")
        self.geometry("780x560")
        self.resizable(False, False)

        self._current_temp = 50.0  # 슬라이더 초기 온도

        self._build_ui()
        self._draw_graph()

    def _build_ui(self):
        # matplotlib Figure
        self._fig = Figure(figsize=(7.4, 4.2), dpi=100, facecolor="#1e1e2e")
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(8, 0))

        # 온도 슬라이더
        ctrl = tk.Frame(self, bg="#1e1e2e")
        ctrl.pack(fill="x", padx=8, pady=8)

        tk.Label(
            ctrl, text="온도 (°C):", font=("Consolas", 10, "bold"),
            bg="#1e1e2e", fg="#cdd6f4",
        ).pack(side="left")

        self._slider = tk.Scale(
            ctrl,
            from_=T_RANGE[0], to=T_RANGE[1],
            orient="horizontal",
            resolution=0.5,
            length=550,
            bg="#1e1e2e", fg="#cdd6f4",
            troughcolor="#45475a",
            highlightthickness=0,
            font=("Consolas", 9),
            command=self._on_slider,
        )
        self._slider.set(self._current_temp)
        self._slider.pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _draw_graph(self):
        ax = self._ax
        ax.clear()

        # 스타일
        ax.set_facecolor("#181825")
        for spine in ax.spines.values():
            spine.set_color("#585b70")
        ax.tick_params(colors="#cdd6f4", labelsize=8)
        ax.set_xlabel("Temperature (°C)", color="#cdd6f4", fontsize=10)
        ax.set_ylabel("Resistance (a.u.)", color="#cdd6f4", fontsize=10)
        ax.set_title("Superconducting Phase Transition", color="#89b4fa", fontsize=12, fontweight="bold")

        # 전체 곡선
        t = np.linspace(T_RANGE[0], T_RANGE[1], 1000)
        r = resistance(t)
        ax.plot(t, r, color="#89b4fa", linewidth=2, label="R(T)")

        # T_c 수직선
        ax.axvline(x=T_C, color="#f38ba8", linestyle="--", linewidth=1, alpha=0.7, label=f"T_c = {T_C}°C")

        # 현재 온도 마커
        cur_r = resistance(np.array([self._current_temp]))[0]
        marker_color = "#a6e3a1" if self._current_temp <= T_C else "#f9e2af"
        ax.plot(self._current_temp, cur_r, "o", color=marker_color, markersize=10, zorder=5)
        ax.annotate(
            f"  {self._current_temp:.1f}°C\n  R={cur_r:.3f}",
            xy=(self._current_temp, cur_r),
            fontsize=9, color=marker_color, fontweight="bold",
        )

        # 초전도 / 정상 영역 배경
        ax.axvspan(T_RANGE[0], T_C, alpha=0.08, color="#a6e3a1", label="초전도 영역")
        ax.axvspan(T_C, T_RANGE[1], alpha=0.08, color="#f38ba8", label="정상 영역")

        ax.legend(loc="upper left", fontsize=8, facecolor="#2a2a3d", edgecolor="#585b70", labelcolor="#cdd6f4")
        ax.set_xlim(T_RANGE)
        ax.set_ylim(-0.05, R_NORMAL * 1.35)

        self._fig.tight_layout()
        self._canvas.draw()

    def _on_slider(self, value):
        self._current_temp = float(value)
        self._draw_graph()


def open_phase_transition(master=None):
    """외부에서 호출하는 진입점."""
    PhaseTransitionWindow(master)
