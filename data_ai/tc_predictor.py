"""AI 신소재 예측 및 상관관계 그래프 (Tkinter + Matplotlib).

- Pandas로 엑셀 데이터 로드
- 멀티 서브플롯 산점도 (density, atomic_mass, electron_affinity 등 vs Tc)
- RandomForestRegressor로 학습 → 새 성분비 입력 시 Tc 예측
"""

import os
import tkinter as tk
from tkinter import messagebox

from logger import get_module_logger

_log = get_module_logger("tc_predictor")

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from config_loader import cfg
from data_ai.generate_sample_data import generate as generate_data
from theme import get_tk_theme

BG = "#1e1e2e"
FG = "#cdd6f4"
ACCENT = "#a6e3a1"


def _load_tc_colors():
    """현재 테마(색맹 모드 포함)에서 색상을 로드."""
    global BG, FG, ACCENT
    _tk = get_tk_theme()
    BG = _tk.BG
    FG = _tk.TEXT
    ACCENT = _tk.ACCENT_GREEN


DATA_PATH = os.path.join(os.path.dirname(__file__), "superconductor_data.xlsx")
CSV_PATH = os.path.join(os.path.dirname(__file__), "superconductor_data.csv")
FEATURES = ["density", "atomic_mass", "electron_affinity", "thermal_conductivity", "valence", "electronegativity"]
TARGET = "critical_temp"


class TcPredictorApp(tk.Toplevel):
    """AI 임계 온도 예측 GUI."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title("AI 신소재 Tc 예측")
        self.configure(bg=BG)
        self.geometry("1050x720")
        self.resizable(False, False)

        # 데이터 로드 (없거나 컬럼 부족·손상 시 재생성)
        try:
            need_regen = not os.path.exists(DATA_PATH)
            if not need_regen:
                tmp = pd.read_excel(DATA_PATH)
                if "electronegativity" not in tmp.columns:
                    need_regen = True
            if need_regen:
                generate_data()
            self.df = pd.read_excel(DATA_PATH)
        except (OSError, ValueError, KeyError) as e:
            _log.warning("데이터 로드 실패, 재생성: %s", e)
            generate_data()
            self.df = pd.read_excel(DATA_PATH)

        # 모델 학습
        self.model, self.r2, self.mae = self._train_model()

        self._build_ui()

    # ── 모델 학습 ────────────────────────────────────

    def _train_model(self):
        X = self.df[FEATURES].values
        y = self.df[TARGET].values

        _test_size = cfg("ml", "test_size", 0.2)
        _seed = cfg("ml", "random_state", 42)
        _n_est = cfg("ml", "n_estimators", 100)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=_test_size, random_state=_seed)

        model = RandomForestRegressor(n_estimators=_n_est, random_state=_seed)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        return model, r2, mae

    # ── UI 구성 ──────────────────────────────────────

    def _build_ui(self):
        # 상단: 차트 영역
        chart_frame = tk.Frame(self, bg=BG)
        chart_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        self.fig = Figure(figsize=(10, 4.2), dpi=100, facecolor="#1e1e2e")
        self.canvas = FigureCanvasTkAgg(self.fig, chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._draw_scatter_plots()

        # 하단: 입력 + 예측
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        self._build_input_panel(bottom)
        self._build_info_panel(bottom)

    def _draw_scatter_plots(self):
        """멀티 서브플롯 산점도."""
        self.fig.clear()

        colors = ["#89b4fa", "#cba6f7", "#f9e2af", "#a6e3a1", "#f38ba8", "#74c7ec"]
        titles = ["Density", "Atomic Mass", "e- Affinity", "Thermal K", "Valence", "Electroneg."]

        for i, (feat, color, title) in enumerate(zip(FEATURES, colors, titles)):
            ax = self.fig.add_subplot(1, 6, i + 1)
            ax.set_facecolor("#181825")
            ax.scatter(
                self.df[feat],
                self.df[TARGET],
                c=color,
                s=8,
                alpha=0.6,
                edgecolors="none",
            )
            ax.set_xlabel(title, fontsize=8, color="#cdd6f4")
            if i == 0:
                ax.set_ylabel("Tc (K)", fontsize=8, color="#cdd6f4")
            ax.tick_params(colors="#6c7086", labelsize=6)
            for spine in ax.spines.values():
                spine.set_color("#45475a")

        self.fig.suptitle("Feature vs Critical Temperature (Tc)", color="#cdd6f4", fontsize=11)
        self.fig.tight_layout(rect=[0, 0, 1, 0.93])
        self.canvas.draw()

    def _build_input_panel(self, parent):
        """성분비 입력 패널."""
        input_frame = tk.LabelFrame(
            parent,
            text="  New Material — Predict Tc  ",
            font=("Consolas", 11, "bold"),
            bg=BG,
            fg=ACCENT,
            padx=12,
            pady=8,
        )
        input_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        self.entries: dict[str, tk.Entry] = {}
        defaults = {
            "density": "6.5",
            "atomic_mass": "90.0",
            "electron_affinity": "80.0",
            "thermal_conductivity": "50.0",
            "valence": "3",
            "electronegativity": "1.8",
        }

        for feat in FEATURES:
            row = tk.Frame(input_frame, bg=BG)
            row.pack(fill=tk.X, pady=2)
            lbl = tk.Label(row, text=f"{feat}:", width=22, anchor="w", font=("Consolas", 9), bg=BG, fg=FG)
            lbl.pack(side=tk.LEFT)
            entry = tk.Entry(row, width=10, font=("Consolas", 10))
            entry.insert(0, defaults.get(feat, "0"))
            entry.pack(side=tk.LEFT, padx=4)
            self.entries[feat] = entry

        btn_frame = tk.Frame(input_frame, bg=BG)
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        tk.Button(
            btn_frame,
            text="Predict Tc",
            command=self._predict,
            font=("Consolas", 10, "bold"),
            width=14,
        ).pack(side=tk.LEFT)

        self.result_var = tk.StringVar(value="—")
        tk.Label(
            btn_frame,
            textvariable=self.result_var,
            font=("Consolas", 12, "bold"),
            bg=BG,
            fg=ACCENT,
        ).pack(side=tk.LEFT, padx=12)

    def _build_info_panel(self, parent):
        """모델 성능 정보."""
        info = tk.LabelFrame(
            parent,
            text="  Model Performance  ",
            font=("Consolas", 11, "bold"),
            bg=BG,
            fg="#89b4fa",
            padx=12,
            pady=8,
        )
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        lines = [
            "Algorithm:   RandomForestRegressor (100 trees)",
            f"R² Score:    {self.r2:.4f}",
            f"MAE:         {self.mae:.2f} K",
            f"Data Points: {len(self.df)}",
            f"Features:    {', '.join(FEATURES)}",
            "Target:      critical_temp (Tc, K)",
        ]
        for line in lines:
            tk.Label(info, text=line, font=("Consolas", 9), bg=BG, fg=FG, anchor="w").pack(
                fill=tk.X,
                pady=1,
            )

        # Feature importance
        importances = self.model.feature_importances_
        tk.Label(info, text="", bg=BG).pack()
        tk.Label(info, text="Feature Importance:", font=("Consolas", 9, "bold"), bg=BG, fg="#f9e2af", anchor="w").pack(
            fill=tk.X
        )
        for feat, imp in sorted(zip(FEATURES, importances), key=lambda x: -x[1]):
            bar_len = int(imp * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
            tk.Label(info, text=f"  {feat:24s} {bar} {imp:.3f}", font=("Consolas", 8), bg=BG, fg=FG, anchor="w").pack(
                fill=tk.X
            )

    # ── 예측 ─────────────────────────────────────────

    def _predict(self):
        try:
            values = [float(self.entries[f].get()) for f in FEATURES]
        except (ValueError, TypeError):
            messagebox.showerror("입력 오류", "모든 필드에 숫자를 입력하세요.", parent=self)
            return

        # 범위 검증: 음수·극단값 경고
        for val, feat in zip(values, FEATURES):
            if not np.isfinite(val):
                messagebox.showerror("입력 오류", f"{feat}에 유효한 숫자를 입력하세요.", parent=self)
                return
            if val < 0:
                messagebox.showwarning(
                    "범위 경고", f"{feat} 값이 음수입니다. 결과가 부정확할 수 있습니다.", parent=self
                )
                break

        X_new = np.array([values])
        tc_pred = self.model.predict(X_new)[0]
        self.result_var.set(f"Predicted Tc = {tc_pred:.2f} K")

        # 산점도에 예측점 표시
        self._draw_scatter_plots()
        axes = self.fig.get_axes()
        for i, ax in enumerate(axes):
            _tk = get_tk_theme()
            ax.axhline(y=tc_pred, color=_tk.RED, linewidth=0.8, linestyle="--", alpha=0.6)
            ax.scatter([values[i]], [tc_pred], c=_tk.RED, s=60, marker="*", zorder=5)
        self.canvas.draw()


def open_tc_predictor(master=None):
    """외부에서 호출하는 진입점."""
    _load_tc_colors()
    TcPredictorApp(master)
