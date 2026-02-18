"""플레이 통계 대시보드 — play_logger 데이터 시각화 (Tkinter + matplotlib).

사용법:
    from stats_dashboard import open_stats_dashboard
    open_stats_dashboard(master)
"""

import tkinter as tk
from tkinter import messagebox

from theme import TK, FONTS, get_tk_theme
from i18n import t
from logger import get_module_logger

_log = get_module_logger("stats_dashboard")


class StatsDashboard(tk.Toplevel):
    """플레이 통계 대시보드."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title(t("stats_title"))
        self.configure(bg=TK.BG)
        self.geometry("900x650")
        self.resizable(False, False)

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        # 타이틀
        tk.Label(
            self, text=t("stats_title"),
            font=FONTS.HEADING, bg=TK.BG, fg=TK.ACCENT_BLUE,
        ).pack(pady=(12, 4))

        # 메인 프레임
        body = tk.Frame(self, bg=TK.BG)
        body.pack(fill="both", expand=True, padx=14, pady=8)

        # 좌측: 요약 통계
        left = tk.LabelFrame(
            body, text=f" {t('stats_summary')} ", font=FONTS.BODY_BOLD,
            bg=TK.PANEL_BG, fg=TK.TEXT, bd=1,
        )
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self._summary_text = tk.Text(
            left, bg=TK.SURFACE, fg=TK.TEXT, font=FONTS.BODY,
            state="disabled", wrap="word", bd=0, padx=8, pady=8, width=35,
        )
        self._summary_text.pack(fill="both", expand=True)

        # 우측: 그래프
        right = tk.LabelFrame(
            body, text=f" {t('stats_charts')} ", font=FONTS.BODY_BOLD,
            bg=TK.PANEL_BG, fg=TK.TEXT, bd=1,
        )
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure

            self._fig = Figure(figsize=(5, 5), dpi=90, facecolor="#1e1e2e")
            self._canvas = FigureCanvasTkAgg(self._fig, master=right)
            self._canvas.get_tk_widget().pack(fill="both", expand=True)
            self._has_matplotlib = True
        except ImportError:
            tk.Label(
                right, text=t("stats_matplotlib_missing"),
                font=FONTS.BODY, bg=TK.PANEL_BG, fg=TK.RED,
            ).pack(expand=True)
            self._has_matplotlib = False

        # 하단: 업적
        ach_frame = tk.LabelFrame(
            self, text=f" {t('stats_achievements')} ", font=FONTS.BODY_BOLD,
            bg=TK.PANEL_BG, fg=TK.ACCENT_YELLOW, bd=1,
        )
        ach_frame.pack(fill="x", padx=14, pady=(0, 12))

        self._ach_text = tk.Text(
            ach_frame, bg=TK.SURFACE, fg=TK.TEXT, font=FONTS.BODY,
            state="disabled", wrap="word", bd=0, padx=8, pady=4, height=4,
        )
        self._ach_text.pack(fill="x")

        # 하단 컨트롤 바
        ctrl_frame = tk.Frame(self, bg=TK.BG)
        ctrl_frame.pack(pady=(0, 8))

        tk.Button(
            ctrl_frame, text=t("stats_refresh"), command=self._load_data,
            font=FONTS.BUTTON, width=12,
        ).pack(side="left", padx=4)

        tk.Button(
            ctrl_frame, text=t("stats_export_csv"), command=self._export_csv,
            font=FONTS.BUTTON, width=12,
        ).pack(side="left", padx=4)

        tk.Button(
            ctrl_frame, text=t("stats_export_json"), command=self._export_json,
            font=FONTS.BUTTON, width=12,
        ).pack(side="left", padx=4)

        # 자동 새로고침 토글
        self._auto_refresh = tk.BooleanVar(value=False)
        tk.Checkbutton(
            ctrl_frame, text=t("stats_auto_refresh"), variable=self._auto_refresh,
            font=FONTS.SMALL, bg=TK.BG, fg=TK.TEXT, selectcolor=TK.SURFACE,
            command=self._toggle_auto_refresh,
        ).pack(side="left", padx=4)

        self._auto_refresh_id: str | None = None

    def _load_data(self):
        """데이터 로드 및 표시."""
        try:
            from data_ai.play_logger import get_logger
            summary = get_logger().get_summary()
        except (ImportError, OSError, ValueError, TypeError) as e:
            _log.error("통계 로드 실패: %s", e)
            summary = {"total_sessions": 0}

        # 요약 텍스트
        self._summary_text.configure(state="normal")
        self._summary_text.delete("1.0", "end")

        total = summary.get("total_sessions", 0)
        modules = summary.get("modules_played", 0)
        per_module = summary.get("sessions_per_module", {})

        lines = [
            t("stats_total_sessions", count=total),
            t("stats_modules_played", count=modules),
            "",
            f"=== {t('stats_sessions_per_module')} ===",
        ]
        for mod, count in per_module.items():
            lines.append(t("stats_sessions_count", mod=mod, count=count))

        lines.append("")
        lines.append(f"=== {t('stats_module_statistics')} ===")

        module_names = {
            "qubit_chain": "Qubit Chain",
            "tunneling": "Tunneling",
            "qec_shield": "QEC Shield",
            "bb84_defense": "BB84 Defense",
            "squid_mines": "SQUID Mines",
            "flux_pinning": "Flux Pinning",
            "phase_transition": "Phase Transition",
        }

        for mod_key, mod_name in module_names.items():
            if mod_key in summary:
                lines.append(f"\n  --- {mod_name} ---")
                stats = summary[mod_key]
                for field, vals in stats.items():
                    if isinstance(vals, dict):
                        lines.append(f"    {field}:")
                        lines.append(f"      avg={vals.get('mean', '-')}  "
                                     f"max={vals.get('max', '-')}  "
                                     f"min={vals.get('min', '-')}")

        self._summary_text.insert("1.0", "\n".join(lines))
        self._summary_text.configure(state="disabled")

        # 차트 업데이트
        if self._has_matplotlib and per_module:
            self._draw_charts(per_module, summary)

        # 업적 표시
        self._show_achievements()

    def _draw_charts(self, per_module: dict, summary: dict):
        """차트 렌더링."""
        self._fig.clear()

        # 상단: 모듈별 플레이 횟수 바 차트
        ax1 = self._fig.add_subplot(211)
        ax1.set_facecolor("#181825")
        for spine in ax1.spines.values():
            spine.set_color("#585b70")
        ax1.tick_params(colors="#cdd6f4", labelsize=7)

        modules = list(per_module.keys())
        counts = list(per_module.values())
        colors = ["#89b4fa", "#a6e3a1", "#f9e2af", "#cba6f7", "#f38ba8", "#fab387", "#74c7ec"]

        ax1.barh(modules, counts, color=colors[:len(modules)])
        ax1.set_title(t("stats_sessions_per_module"), color="#89b4fa", fontsize=10, fontweight="bold")

        for i, v in enumerate(counts):
            ax1.text(v + 0.1, i, str(v), va="center", color="#cdd6f4", fontsize=8)

        # 하단: 생존 시간 추이 (qubit_chain 또는 qec_shield)
        ax2 = self._fig.add_subplot(212)
        ax2.set_facecolor("#181825")
        for spine in ax2.spines.values():
            spine.set_color("#585b70")
        ax2.tick_params(colors="#cdd6f4", labelsize=7)
        ax2.set_title(t("stats_survival_trend"), color=get_tk_theme().GREEN, fontsize=10, fontweight="bold")

        try:
            from data_ai.play_logger import get_logger
            import pandas as pd
            records = get_logger().records
            df = pd.DataFrame(records)
            for mod_name, color in [("qubit_chain", "#89b4fa"), ("qec_shield", "#cba6f7")]:
                mod_df = df[df["module"] == mod_name]
                if "survival_time" in mod_df.columns and not mod_df.empty:
                    times = pd.to_numeric(mod_df["survival_time"], errors="coerce").dropna().tolist()
                    if times:
                        ax2.plot(range(len(times)), times, color=color, linewidth=1.5,
                                 label=mod_name, marker="o", markersize=3)
            ax2.legend(fontsize=7, facecolor="#2a2a3d", edgecolor="#585b70", labelcolor="#cdd6f4")
            ax2.set_xlabel(t("stats_session_num"), color="#cdd6f4", fontsize=8)
            ax2.set_ylabel(t("stats_time_sec"), color="#cdd6f4", fontsize=8)
        except (KeyError, ValueError, TypeError, AttributeError) as e:
            _log.warning("생존 시간 차트 렌더링 실패: %s", e)
            ax2.text(0.5, 0.5, t("stats_no_survival_data"), transform=ax2.transAxes,
                     ha="center", va="center", color="#585b70", fontsize=11)

        self._fig.tight_layout()
        self._canvas.draw()

    def _show_achievements(self):
        """업적 표시."""
        self._ach_text.configure(state="normal")
        self._ach_text.delete("1.0", "end")

        try:
            from achievements import get_all_achievements, get_unlocked_count
            unlocked, total = get_unlocked_count()
            achievements = get_all_achievements()

            lines = [t("stats_ach_count", unlocked=unlocked, total=total) + "\n"]
            for ach in achievements:
                status = "[*]" if ach["unlocked"] else "[ ]"
                lines.append(f"  {status} [{ach['icon']}] {ach['title']} — {ach['desc']}")

            self._ach_text.insert("1.0", "\n".join(lines))
        except (ImportError, KeyError, TypeError, ValueError) as e:
            _log.warning("업적 로드 실패: %s", e)
            self._ach_text.insert("1.0", t("stats_ach_unavailable"))

        self._ach_text.configure(state="disabled")


    def _export_csv(self):
        """CSV 내보내기."""
        try:
            from data_ai.play_logger import get_logger
            path = get_logger().export()
            if path:
                messagebox.showinfo(
                    t("stats_export_csv"),
                    t("stats_export_done", path=path),
                    parent=self,
                )
            else:
                messagebox.showwarning(
                    t("stats_export_csv"),
                    t("stats_export_empty"),
                    parent=self,
                )
        except (ImportError, OSError, ValueError, TypeError) as e:
            _log.error("CSV 내보내기 실패: %s", e)

    def _export_json(self):
        """JSON 내보내기."""
        try:
            from data_ai.play_logger import get_logger
            path = get_logger().export_json()
            if path:
                messagebox.showinfo(
                    t("stats_export_json"),
                    t("stats_export_done", path=path),
                    parent=self,
                )
            else:
                messagebox.showwarning(
                    t("stats_export_json"),
                    t("stats_export_empty"),
                    parent=self,
                )
        except (ImportError, OSError, ValueError, TypeError) as e:
            _log.error("JSON 내보내기 실패: %s", e)

    def _toggle_auto_refresh(self):
        """자동 새로고침 ON/OFF."""
        if self._auto_refresh.get():
            self._schedule_auto_refresh()
        else:
            if self._auto_refresh_id:
                self.after_cancel(self._auto_refresh_id)
                self._auto_refresh_id = None

    def _schedule_auto_refresh(self):
        """10초마다 자동 새로고침."""
        if not self.winfo_exists():
            return
        self._load_data()
        if self._auto_refresh.get():
            self._auto_refresh_id = self.after(10000, self._schedule_auto_refresh)


def open_stats_dashboard(master=None):
    """외부에서 호출하는 진입점."""
    StatsDashboard(master)
