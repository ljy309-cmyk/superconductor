"""상전이(Phase Transition) 시각화 — 온도-저항 관계 그래프."""

import tkinter as tk
from tkinter import ttk

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# ── 물질별 임계 온도 (°C) ────────────────────────────────
MATERIALS = {
    "YBCO (Tc=93K)": -180.15,          # 93 K
    "Mercury / Hg (Tc=4.2K)": -268.95, # 4.2 K
}
DEFAULT_MATERIAL = "YBCO (Tc=93K)"

R_NORMAL = 1.0        # 정규화된 상온 저항 (임의 단위)
T_RANGE = (-275, 50)  # 그래프 온도 범위 (°C)


def _celsius_to_kelvin(t):
    return t + 273.15


def _kelvin_to_celsius(k):
    return k - 273.15


def resistance(t: np.ndarray, tc: float, noise: bool = False) -> np.ndarray:
    """온도에 따른 저항값 계산.

    T > T_c : 온도에 비례하는 선형 저항 (금속 특성)
    T ≤ T_c : 저항 = 0 (초전도 상태)
    """
    r = np.where(
        t > tc,
        R_NORMAL * (t - tc) / (0 - tc),  # T_c에서 0, 0°C에서 R_NORMAL
        0.0,
    )
    r = np.clip(r, 0, None)
    if noise:
        noise_vals = np.where(
            t > tc,
            np.random.uniform(-0.03, 0.03, size=r.shape),
            0.0,
        )
        r = np.clip(r + noise_vals, 0, None)
    return r


class PhaseTransitionWindow(tk.Toplevel):
    """상전이 시각화 윈도우."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title("상전이 시각화 — 온도 vs 저항")
        self.geometry("780x600")
        self.resizable(False, False)

        self._current_temp = 50.0       # 슬라이더 초기 온도 (°C)
        self._tc = MATERIALS[DEFAULT_MATERIAL]
        self._noise = False

        self._build_ui()
        self._draw_graph()

    # ── UI 구성 ──────────────────────────────────────────

    def _build_ui(self):
        # matplotlib Figure
        self._fig = Figure(figsize=(7.4, 4.2), dpi=100, facecolor="#1e1e2e")
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(8, 0))

        # ── 상단 컨트롤: 물질 선택 + 노이즈 토글 ──
        ctrl = tk.Frame(self, bg="#1e1e2e")
        ctrl.pack(fill="x", padx=8, pady=4)

        tk.Label(
            ctrl, text="물질:", font=("Consolas", 10, "bold"),
            bg="#1e1e2e", fg="#cdd6f4",
        ).pack(side="left")

        self._material_var = tk.StringVar(value=DEFAULT_MATERIAL)
        material_combo = ttk.Combobox(
            ctrl, textvariable=self._material_var,
            values=list(MATERIALS.keys()),
            state="readonly", width=24,
        )
        material_combo.pack(side="left", padx=(4, 12))
        material_combo.bind("<<ComboboxSelected>>", self._on_material_change)

        self._noise_var = tk.BooleanVar(value=False)
        noise_cb = tk.Checkbutton(
            ctrl, text="노이즈 추가", variable=self._noise_var,
            command=self._on_noise_toggle,
            bg="#1e1e2e", fg="#cdd6f4", selectcolor="#45475a",
            activebackground="#1e1e2e", activeforeground="#cdd6f4",
            font=("Consolas", 10, "bold"),
        )
        noise_cb.pack(side="left", padx=(0, 12))

        # ── 온도 슬라이더 ──
        slider_frame = tk.Frame(self, bg="#1e1e2e")
        slider_frame.pack(fill="x", padx=8, pady=(0, 8))

        tk.Label(
            slider_frame, text="온도 (°C):", font=("Consolas", 10, "bold"),
            bg="#1e1e2e", fg="#cdd6f4",
        ).pack(side="left")

        self._slider = tk.Scale(
            slider_frame,
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

    # ── 그래프 렌더링 ────────────────────────────────────

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
        ax.set_title(
            "Superconducting Phase Transition",
            color="#89b4fa", fontsize=12, fontweight="bold",
        )

        # 전체 곡선
        t = np.linspace(T_RANGE[0], T_RANGE[1], 1000)
        r = resistance(t, self._tc, noise=self._noise)
        ax.plot(t, r, color="#89b4fa", linewidth=2, label="R(T)")

        # T_c 수직선 (켈빈 병기)
        tc_k = _celsius_to_kelvin(self._tc)
        ax.axvline(
            x=self._tc, color="#f38ba8", linestyle="--", linewidth=1,
            alpha=0.7, label=f"Tc = {self._tc:.1f}°C ({tc_k:.1f}K)",
        )

        # 현재 온도 마커 (켈빈 병기)
        cur_r = resistance(np.array([self._current_temp]), self._tc)[0]
        marker_color = "#a6e3a1" if self._current_temp <= self._tc else "#f9e2af"
        cur_k = _celsius_to_kelvin(self._current_temp)
        ax.plot(self._current_temp, cur_r, "o", color=marker_color, markersize=10, zorder=5)
        ax.annotate(
            f"  {self._current_temp:.1f}°C ({cur_k:.1f}K)\n  R={cur_r:.3f}",
            xy=(self._current_temp, cur_r),
            fontsize=9, color=marker_color, fontweight="bold",
        )

        # 초전도 / 정상 영역 배경
        ax.axvspan(T_RANGE[0], self._tc, alpha=0.08, color="#a6e3a1", label="초전도 영역")
        ax.axvspan(self._tc, T_RANGE[1], alpha=0.08, color="#f38ba8", label="정상 영역")

        ax.legend(
            loc="upper left", fontsize=8,
            facecolor="#2a2a3d", edgecolor="#585b70", labelcolor="#cdd6f4",
        )

        # ★ X축 반전: 오른쪽(고온 50°C) → 왼쪽(저온 -275°C)  냉각 방향
        ax.set_xlim(T_RANGE[1], T_RANGE[0])
        ax.set_ylim(-0.05, R_NORMAL * 1.35)

        # ★ 상단에 켈빈 보조 축 표시
        ax2 = ax.secondary_xaxis("top", functions=(_celsius_to_kelvin, _kelvin_to_celsius))
        ax2.set_xlabel("Temperature (K)", color="#cdd6f4", fontsize=9)
        ax2.tick_params(colors="#cdd6f4", labelsize=8)

        self._fig.tight_layout()
        self._canvas.draw()

    # ── 이벤트 핸들러 ────────────────────────────────────

    def _on_slider(self, value):
        self._current_temp = float(value)
        self._draw_graph()

    def _on_material_change(self, event=None):
        material = self._material_var.get()
        self._tc = MATERIALS[material]
        self._draw_graph()

    def _on_noise_toggle(self):
        self._noise = self._noise_var.get()
        self._draw_graph()


def open_phase_transition(master=None):
    """외부에서 호출하는 진입점."""
    PhaseTransitionWindow(master)
