"""AI 신소재 예측 및 상관관계 그래프 (Tkinter + Matplotlib).

고도화:
  - 멀티 모델 비교: RandomForest, GradientBoosting, SVR
  - Feature Importance / Permutation Importance 시각화
  - SuperCon 실제 데이터셋 활용 옵션
  - 탭 UI: 산점도, 모델 비교, Feature Importance
"""

import os
import tkinter as tk
from tkinter import messagebox, ttk

from logger import get_module_logger

_log = get_module_logger("tc_predictor")

from config_loader import cfg
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
FEATURES = ["density", "atomic_mass", "electron_affinity", "thermal_conductivity", "valence", "electronegativity"]
TARGET = "critical_temp"

# 모델 설정
MODEL_CONFIGS = {
    "RandomForest": {
        "label": "Random Forest",
        "color": "#a6e3a1",
        "short": "RF",
    },
    "GradientBoosting": {
        "label": "Gradient Boosting",
        "color": "#89b4fa",
        "short": "GBR",
    },
    "SVR": {
        "label": "Support Vector Regression",
        "color": "#f38ba8",
        "short": "SVR",
    },
}


def _build_model(name, seed, n_est):
    """모델 이름으로 sklearn 모델 인스턴스 생성."""
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.svm import SVR as _SVR

    if name == "RandomForest":
        return RandomForestRegressor(n_estimators=n_est, random_state=seed)
    elif name == "GradientBoosting":
        return GradientBoostingRegressor(
            n_estimators=n_est,
            random_state=seed,
            max_depth=4,
            learning_rate=0.1,
        )
    elif name == "SVR":
        return _SVR(kernel="rbf", C=100.0, epsilon=0.1)
    raise ValueError(f"Unknown model: {name}")


def train_and_evaluate(df, model_name, seed=42, n_est=100, test_size=0.2):
    """모델 학습 + 평가 결과를 dict로 반환."""
    import numpy as np
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    X = df[FEATURES].values
    y = df[TARGET].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed,
    )

    # SVR은 스케일링 필요
    scaler = None
    if model_name == "SVR":
        scaler = StandardScaler()
        X_train_fit = scaler.fit_transform(X_train)
        X_test_fit = scaler.transform(X_test)
    else:
        X_train_fit = X_train
        X_test_fit = X_test

    model = _build_model(model_name, seed, n_est)
    model.fit(X_train_fit, y_train)

    y_pred = model.predict(X_test_fit)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

    # Feature importance (RF, GBR은 내장, SVR은 permutation)
    importances = _get_feature_importances(model, X_test_fit, y_test, model_name)

    return {
        "model": model,
        "scaler": scaler,
        "r2": r2,
        "mae": mae,
        "rmse": rmse,
        "y_test": y_test,
        "y_pred": y_pred,
        "importances": importances,
        "X_train": X_train,
        "X_test": X_test,
    }


def _get_feature_importances(model, X_test, y_test, model_name):
    """모델 타입에 맞는 Feature Importance 추출."""
    import numpy as np

    if model_name in ("RandomForest", "GradientBoosting"):
        return model.feature_importances_

    # SVR: permutation importance (sklearn 내장)
    try:
        from sklearn.inspection import permutation_importance
        result = permutation_importance(model, X_test, y_test, n_repeats=10, random_state=42)
        return result.importances_mean
    except (ImportError, AttributeError):
        # fallback: 균등 분배
        return np.ones(len(FEATURES)) / len(FEATURES)


class TcPredictorApp(tk.Toplevel):
    """AI 임계 온도 예측 GUI (고도화 버전)."""

    def __init__(self, master=None):
        import matplotlib
        matplotlib.use("TkAgg")

        super().__init__(master)
        self.title("AI Tc Predictor — Multi-Model Comparison")
        self.configure(bg=BG)
        self.geometry("1100x780")
        self.resizable(False, False)

        self.data_mode = "synthetic"  # "synthetic" or "supercon"
        self._load_data()

        # 전체 모델 학습
        self.results = {}
        self._train_all_models()

        self._build_ui()

    def _load_data(self):
        """데이터 모드에 따라 데이터 로드."""
        import pandas as pd
        from data_ai.generate_sample_data import (
            CSV_PATH,
            SUPERCON_PATH,
            generate as generate_data,
            generate_supercon,
        )

        if self.data_mode == "supercon":
            if not os.path.exists(SUPERCON_PATH):
                generate_supercon()
            self.df = pd.read_csv(SUPERCON_PATH)
        else:
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

    def _train_all_models(self):
        """모든 모델 학습 및 평가."""
        _test_size = cfg("ml", "test_size", 0.2)
        _seed = cfg("ml", "random_state", 42)
        _n_est = cfg("ml", "n_estimators", 100)

        for name in MODEL_CONFIGS:
            self.results[name] = train_and_evaluate(
                self.df, name, seed=_seed, n_est=_n_est, test_size=_test_size,
            )

    # ── UI 구성 ──────────────────────────────────────

    def _build_ui(self):
        # 상단: 데이터셋 전환 + 탭
        top_bar = tk.Frame(self, bg=BG)
        top_bar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(8, 0))

        tk.Label(top_bar, text="Dataset:", font=("Consolas", 10), bg=BG, fg=FG).pack(side=tk.LEFT)
        self.dataset_var = tk.StringVar(value=self.data_mode)
        for mode, label in [("synthetic", "Synthetic (212)"), ("supercon", "SuperCon (330+)")]:
            rb = tk.Radiobutton(
                top_bar, text=label, variable=self.dataset_var, value=mode,
                command=self._on_dataset_change, font=("Consolas", 9),
                bg=BG, fg=FG, selectcolor="#313244", activebackground=BG,
            )
            rb.pack(side=tk.LEFT, padx=6)

        self.data_info_var = tk.StringVar(value=f"  |  {len(self.df)} rows")
        tk.Label(top_bar, textvariable=self.data_info_var, font=("Consolas", 9), bg=BG, fg="#6c7086").pack(
            side=tk.LEFT, padx=8,
        )

        # 탭 노트북
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook", background=BG, borderwidth=0)
        style.configure("Dark.TNotebook.Tab", background="#313244", foreground=FG,
                        padding=[12, 4], font=("Consolas", 9))
        style.map("Dark.TNotebook.Tab", background=[("selected", "#45475a")])

        self.notebook = ttk.Notebook(self, style="Dark.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 탭 1: 산점도
        self.tab_scatter = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.tab_scatter, text="  Scatter Plots  ")
        self._build_scatter_tab()

        # 탭 2: 모델 비교
        self.tab_compare = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.tab_compare, text="  Model Comparison  ")
        self._build_compare_tab()

        # 탭 3: Feature Importance
        self.tab_importance = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(self.tab_importance, text="  Feature Importance  ")
        self._build_importance_tab()

        # 하단: 입력 + 예측
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=8)
        self._build_input_panel(bottom)
        self._build_info_panel(bottom)

    def _on_dataset_change(self):
        """데이터셋 전환 시 재학습."""
        new_mode = self.dataset_var.get()
        if new_mode == self.data_mode:
            return
        self.data_mode = new_mode
        self._load_data()
        self._train_all_models()
        self.data_info_var.set(f"  |  {len(self.df)} rows")
        # 차트 갱신
        self._draw_scatter_plots()
        self._draw_compare_charts()
        self._draw_importance_charts()
        # 성능 정보 갱신
        self._update_info_panel()

    # ── 탭 1: 산점도 ─────────────────────────────────

    def _build_scatter_tab(self):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure

        self.scatter_fig = Figure(figsize=(10.5, 4.5), dpi=100, facecolor=BG)
        self.scatter_canvas = FigureCanvasTkAgg(self.scatter_fig, self.tab_scatter)
        self.scatter_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._draw_scatter_plots()

    def _draw_scatter_plots(self):
        """멀티 서브플롯 산점도."""
        self.scatter_fig.clear()
        colors = ["#89b4fa", "#cba6f7", "#f9e2af", "#a6e3a1", "#f38ba8", "#74c7ec"]
        titles = ["Density", "Atomic Mass", "e- Affinity", "Thermal K", "Valence", "Electroneg."]

        for i, (feat, color, title) in enumerate(zip(FEATURES, colors, titles)):
            ax = self.scatter_fig.add_subplot(1, 6, i + 1)
            ax.set_facecolor("#181825")
            ax.scatter(self.df[feat], self.df[TARGET], c=color, s=8, alpha=0.6, edgecolors="none")
            ax.set_xlabel(title, fontsize=8, color="#cdd6f4")
            if i == 0:
                ax.set_ylabel("Tc (K)", fontsize=8, color="#cdd6f4")
            ax.tick_params(colors="#6c7086", labelsize=6)
            for spine in ax.spines.values():
                spine.set_color("#45475a")

        mode_label = "SuperCon" if self.data_mode == "supercon" else "Synthetic"
        self.scatter_fig.suptitle(
            f"Feature vs Critical Temperature — {mode_label} ({len(self.df)} samples)",
            color="#cdd6f4", fontsize=11,
        )
        self.scatter_fig.tight_layout(rect=[0, 0, 1, 0.93])
        self.scatter_canvas.draw()

    # ── 탭 2: 모델 비교 ──────────────────────────────

    def _build_compare_tab(self):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure

        self.compare_fig = Figure(figsize=(10.5, 4.5), dpi=100, facecolor=BG)
        self.compare_canvas = FigureCanvasTkAgg(self.compare_fig, self.tab_compare)
        self.compare_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._draw_compare_charts()

    def _draw_compare_charts(self):
        """모델 비교: 성능 지표 바 차트 + Actual vs Predicted 산점도."""
        import numpy as np

        self.compare_fig.clear()

        names = list(MODEL_CONFIGS.keys())
        colors = [MODEL_CONFIGS[n]["color"] for n in names]
        labels = [MODEL_CONFIGS[n]["label"] for n in names]

        # 좌측: 성능 지표 비교 바 차트
        ax1 = self.compare_fig.add_subplot(1, 3, 1)
        ax1.set_facecolor("#181825")
        r2_vals = [self.results[n]["r2"] for n in names]
        x_pos = np.arange(len(names))
        bars = ax1.bar(x_pos, r2_vals, color=colors, width=0.6, alpha=0.85)
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels([MODEL_CONFIGS[n]["short"] for n in names], fontsize=9, color="#cdd6f4")
        ax1.set_ylabel("R² Score", fontsize=9, color="#cdd6f4")
        ax1.set_title("R² Score", fontsize=10, color="#cdd6f4")
        ax1.set_ylim(0, 1.05)
        ax1.tick_params(colors="#6c7086", labelsize=7)
        for spine in ax1.spines.values():
            spine.set_color("#45475a")
        for bar, val in zip(bars, r2_vals):
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                     f"{val:.3f}", ha="center", fontsize=8, color="#cdd6f4")

        # 중앙: MAE + RMSE 비교
        ax2 = self.compare_fig.add_subplot(1, 3, 2)
        ax2.set_facecolor("#181825")
        mae_vals = [self.results[n]["mae"] for n in names]
        rmse_vals = [self.results[n]["rmse"] for n in names]
        width = 0.3
        ax2.bar(x_pos - width / 2, mae_vals, width, label="MAE", color=colors, alpha=0.7)
        ax2.bar(x_pos + width / 2, rmse_vals, width, label="RMSE", color=colors, alpha=0.4)
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels([MODEL_CONFIGS[n]["short"] for n in names], fontsize=9, color="#cdd6f4")
        ax2.set_ylabel("Error (K)", fontsize=9, color="#cdd6f4")
        ax2.set_title("MAE / RMSE", fontsize=10, color="#cdd6f4")
        ax2.legend(fontsize=7, facecolor="#313244", edgecolor="#45475a", labelcolor="#cdd6f4")
        ax2.tick_params(colors="#6c7086", labelsize=7)
        for spine in ax2.spines.values():
            spine.set_color("#45475a")

        # 우측: Actual vs Predicted (최고 성능 모델)
        best_name = max(names, key=lambda n: self.results[n]["r2"])
        res = self.results[best_name]
        ax3 = self.compare_fig.add_subplot(1, 3, 3)
        ax3.set_facecolor("#181825")
        ax3.scatter(res["y_test"], res["y_pred"], c=MODEL_CONFIGS[best_name]["color"],
                    s=15, alpha=0.6, edgecolors="none")
        lims = [min(res["y_test"].min(), res["y_pred"].min()) - 5,
                max(res["y_test"].max(), res["y_pred"].max()) + 5]
        ax3.plot(lims, lims, "--", color="#f9e2af", linewidth=1, alpha=0.6)
        ax3.set_xlabel("Actual Tc (K)", fontsize=9, color="#cdd6f4")
        ax3.set_ylabel("Predicted Tc (K)", fontsize=9, color="#cdd6f4")
        ax3.set_title(f"Actual vs Predicted ({MODEL_CONFIGS[best_name]['short']})",
                      fontsize=10, color="#cdd6f4")
        ax3.tick_params(colors="#6c7086", labelsize=7)
        for spine in ax3.spines.values():
            spine.set_color("#45475a")

        self.compare_fig.tight_layout()
        self.compare_canvas.draw()

    # ── 탭 3: Feature Importance ──────────────────────

    def _build_importance_tab(self):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure

        self.importance_fig = Figure(figsize=(10.5, 4.5), dpi=100, facecolor=BG)
        self.importance_canvas = FigureCanvasTkAgg(self.importance_fig, self.tab_importance)
        self.importance_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._draw_importance_charts()

    def _draw_importance_charts(self):
        """모델별 Feature Importance 수평 바 차트."""
        import numpy as np

        self.importance_fig.clear()
        names = list(MODEL_CONFIGS.keys())

        for idx, name in enumerate(names):
            ax = self.importance_fig.add_subplot(1, 3, idx + 1)
            ax.set_facecolor("#181825")

            importances = self.results[name]["importances"]
            sorted_indices = np.argsort(importances)
            sorted_features = [FEATURES[i] for i in sorted_indices]
            sorted_importances = importances[sorted_indices]

            color = MODEL_CONFIGS[name]["color"]
            y_pos = np.arange(len(FEATURES))
            ax.barh(y_pos, sorted_importances, color=color, alpha=0.8, height=0.6)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(sorted_features, fontsize=8, color="#cdd6f4")
            ax.set_xlabel("Importance", fontsize=8, color="#cdd6f4")
            imp_type = "Permutation" if name == "SVR" else "Gini / Split"
            ax.set_title(f"{MODEL_CONFIGS[name]['short']} ({imp_type})",
                         fontsize=10, color="#cdd6f4")
            ax.tick_params(colors="#6c7086", labelsize=7)
            for spine in ax.spines.values():
                spine.set_color("#45475a")

            # 값 레이블
            for i, (val, feat) in enumerate(zip(sorted_importances, sorted_features)):
                ax.text(val + 0.005, i, f"{val:.3f}", va="center", fontsize=7, color="#cdd6f4")

        self.importance_fig.suptitle("Feature Importance by Model", color="#cdd6f4", fontsize=11)
        self.importance_fig.tight_layout(rect=[0, 0, 1, 0.93])
        self.importance_canvas.draw()

    # ── 하단: 입력 패널 ──────────────────────────────

    def _build_input_panel(self, parent):
        """성분비 입력 패널."""
        input_frame = tk.LabelFrame(
            parent, text="  New Material — Predict Tc  ",
            font=("Consolas", 11, "bold"), bg=BG, fg=ACCENT, padx=12, pady=8,
        )
        input_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        self.entries: dict[str, tk.Entry] = {}
        defaults = {
            "density": "6.5", "atomic_mass": "90.0", "electron_affinity": "80.0",
            "thermal_conductivity": "50.0", "valence": "3", "electronegativity": "1.8",
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

        # 모델 선택
        tk.Label(btn_frame, text="Model:", font=("Consolas", 9), bg=BG, fg=FG).pack(side=tk.LEFT)
        self.predict_model_var = tk.StringVar(value="RandomForest")
        model_menu = tk.OptionMenu(btn_frame, self.predict_model_var, *MODEL_CONFIGS.keys())
        model_menu.config(font=("Consolas", 8), width=14)
        model_menu.pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="Predict Tc", command=self._predict,
            font=("Consolas", 10, "bold"), width=12,
        ).pack(side=tk.LEFT, padx=4)

        self.result_var = tk.StringVar(value="—")
        tk.Label(
            btn_frame, textvariable=self.result_var, font=("Consolas", 12, "bold"), bg=BG, fg=ACCENT,
        ).pack(side=tk.LEFT, padx=8)

    def _build_info_panel(self, parent):
        """모델 성능 정보."""
        self.info_frame = tk.LabelFrame(
            parent, text="  Model Performance  ",
            font=("Consolas", 11, "bold"), bg=BG, fg="#89b4fa", padx=12, pady=8,
        )
        self.info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._populate_info()

    def _populate_info(self):
        """모델 성능 정보 레이블 채우기."""
        for widget in self.info_frame.winfo_children():
            widget.destroy()

        # 모델별 요약 (1줄씩)
        for name in MODEL_CONFIGS:
            res = self.results[name]
            conf = MODEL_CONFIGS[name]
            line = f"{conf['short']:4s}  R²={res['r2']:.4f}  MAE={res['mae']:.2f}K  RMSE={res['rmse']:.2f}K"
            tk.Label(self.info_frame, text=line, font=("Consolas", 9), bg=BG, fg=conf["color"], anchor="w").pack(
                fill=tk.X, pady=1,
            )

        tk.Label(self.info_frame, text="", bg=BG).pack()

        # 데이터 정보
        info_lines = [
            f"Data Points: {len(self.df)}  |  Mode: {self.data_mode}",
            f"Features:    {', '.join(FEATURES)}",
            f"Target:      {TARGET} (Tc, K)",
        ]
        for line in info_lines:
            tk.Label(self.info_frame, text=line, font=("Consolas", 8), bg=BG, fg="#6c7086", anchor="w").pack(
                fill=tk.X, pady=1,
            )

        # 최고 모델의 Feature Importance (텍스트)
        best_name = max(MODEL_CONFIGS.keys(), key=lambda n: self.results[n]["r2"])
        importances = self.results[best_name]["importances"]
        tk.Label(self.info_frame, text="", bg=BG).pack()
        tk.Label(
            self.info_frame,
            text=f"Top Features ({MODEL_CONFIGS[best_name]['short']}):",
            font=("Consolas", 9, "bold"), bg=BG, fg="#f9e2af", anchor="w",
        ).pack(fill=tk.X)
        for feat, imp in sorted(zip(FEATURES, importances), key=lambda x: -x[1]):
            bar_len = int(imp * 30)
            bar = "\u2588" * bar_len + "\u2591" * (30 - bar_len)
            tk.Label(
                self.info_frame,
                text=f"  {feat:24s} {bar} {imp:.3f}",
                font=("Consolas", 8), bg=BG, fg=FG, anchor="w",
            ).pack(fill=tk.X)

    def _update_info_panel(self):
        """데이터셋 변경 시 성능 패널 갱신."""
        self._populate_info()

    # ── 예측 ─────────────────────────────────────────

    def _predict(self):
        import numpy as np

        try:
            values = [float(self.entries[f].get()) for f in FEATURES]
        except (ValueError, TypeError):
            messagebox.showerror("입력 오류", "모든 필드에 숫자를 입력하세요.", parent=self)
            return

        for val, feat in zip(values, FEATURES):
            if not np.isfinite(val):
                messagebox.showerror("입력 오류", f"{feat}에 유효한 숫자를 입력하세요.", parent=self)
                return
            if val < 0:
                messagebox.showwarning(
                    "범위 경고", f"{feat} 값이 음수입니다. 결과가 부정확할 수 있습니다.", parent=self,
                )
                break

        model_name = self.predict_model_var.get()
        res = self.results[model_name]
        X_new = np.array([values])

        if res["scaler"] is not None:
            X_new_fit = res["scaler"].transform(X_new)
        else:
            X_new_fit = X_new

        tc_pred = res["model"].predict(X_new_fit)[0]
        short = MODEL_CONFIGS[model_name]["short"]
        self.result_var.set(f"[{short}] Tc = {tc_pred:.2f} K")

        # 산점도에 예측점 표시
        self._draw_scatter_plots()
        axes = self.scatter_fig.get_axes()
        _tk = get_tk_theme()
        for i, ax in enumerate(axes):
            ax.axhline(y=tc_pred, color=_tk.RED, linewidth=0.8, linestyle="--", alpha=0.6)
            ax.scatter([values[i]], [tc_pred], c=_tk.RED, s=60, marker="*", zorder=5)
        self.scatter_canvas.draw()


def open_tc_predictor(master=None):
    """외부에서 호출하는 진입점."""
    _load_tc_colors()
    TcPredictorApp(master)
