"""디지털 트윈 대시보드 — 전문가용 HMI 화면 + 실시간 온도 그래프."""

import tkinter as tk
from datetime import datetime

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from i18n import t
from scada.cooler import CoolerState, CoolingSystem
from theme import FONTS, TK, get_tk_theme

# 최대 기록 유지할 온도 데이터 포인트 수
MAX_HISTORY = 120


class Dashboard(tk.Toplevel):
    """SCADA 디지털 트윈 대시보드 (HMI) + 실시간 그래프."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title(t("dashboard_title"))
        self.configure(bg=TK.BG)
        self.geometry("1020x620")
        self.resizable(False, False)

        self._cooler = CoolingSystem()
        self._cooler.add_listener(self._on_state_update)

        # 온도 이력 (실시간 그래프용)
        self._temp_history: list[float] = []
        self._time_history: list[float] = []
        self._tick_count = 0

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI 구성 ──────────────────────────────────────────

    def _build_ui(self):
        # 상단 타이틀
        title = tk.Label(
            self,
            text=t("dashboard_heading"),
            font=FONTS.HEADING,
            bg=TK.BG,
            fg=TK.ACCENT_BLUE,
        )
        title.pack(pady=(12, 6))

        # 메인 프레임 (좌·중·우 3분할)
        body = tk.Frame(self, bg=TK.BG)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        # ── 좌측: 실시간 온도 텍스트 로그 ──
        left = tk.LabelFrame(
            body,
            text=f" {t('temp_log')} ",
            font=FONTS.BODY_BOLD,
            bg=TK.PANEL_BG,
            fg=TK.TEXT,
            bd=1,
        )
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self._log = tk.Text(
            left,
            bg=TK.SURFACE,
            fg=TK.TEXT,
            font=FONTS.BODY,
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

        # 목표 온도 표시
        self._target_var = tk.StringVar(value=t("target_temp", temp=-196.0))
        tk.Label(
            left,
            textvariable=self._target_var,
            font=FONTS.BODY_BOLD,
            bg=TK.PANEL_BG,
            fg=TK.YELLOW,
            anchor="w",
            padx=8,
        ).pack(side="bottom", fill="x", pady=(4, 6))

        # ── 중앙: 실시간 온도 그래프 ──
        mid = tk.LabelFrame(
            body,
            text=f" {t('graph_title_temp')} ",
            font=FONTS.BODY_BOLD,
            bg=TK.PANEL_BG,
            fg=TK.TEXT,
            bd=1,
        )
        mid.pack(side="left", fill="both", expand=True, padx=6)

        self._fig = Figure(figsize=(3.6, 4.0), dpi=90, facecolor="#1e1e2e")
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasTkAgg(self._fig, master=mid)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)
        self._init_graph()

        # ── 우측: 시스템 상태 게이지 패널 ──
        right = tk.LabelFrame(
            body,
            text=f" {t('system_status')} ",
            font=FONTS.BODY_BOLD,
            bg=TK.PANEL_BG,
            fg=TK.TEXT,
            bd=1,
        )
        right.pack(side="right", fill="both", padx=(6, 0))

        # 현재 온도 표시
        self._temp_var = tk.StringVar(value="-- °C")
        tk.Label(
            right,
            text=t("current_temp"),
            font=FONTS.SMALL,
            bg=TK.PANEL_BG,
            fg=TK.TEXT,
        ).pack(pady=(12, 0))
        self._temp_label = tk.Label(
            right,
            textvariable=self._temp_var,
            font=("Consolas", 22, "bold"),
            bg=TK.PANEL_BG,
            fg=TK.ACCENT_BLUE,
        )
        self._temp_label.pack()

        # 게이지 바
        tk.Label(
            right,
            text=t("cooling_gauge"),
            font=FONTS.SMALL,
            bg=TK.PANEL_BG,
            fg=TK.TEXT,
        ).pack(pady=(16, 4))
        self._gauge_canvas = tk.Canvas(
            right,
            width=60,
            height=220,
            bg=TK.PANEL_BG,
            highlightthickness=0,
        )
        self._gauge_canvas.pack()
        self._draw_gauge_frame()

        # 상태 인디케이터
        self._status_var = tk.StringVar(value=t("stopped"))
        self._cooling_var = tk.StringVar(value=t("cooler_state", state=t("off")))
        self._emergency_var = tk.StringVar(value=t("emergency_state", state=t("off")))

        for var in (self._status_var, self._cooling_var, self._emergency_var):
            tk.Label(
                right,
                textvariable=var,
                font=FONTS.BODY_BOLD,
                bg=TK.PANEL_BG,
                fg=TK.TEXT,
            ).pack(pady=2)

        # 하단 제어 버튼
        btn_frame = tk.Frame(self, bg=TK.BG)
        btn_frame.pack(pady=(0, 12))

        _tk = get_tk_theme()
        self._start_btn = tk.Button(
            btn_frame,
            text=t("start"),
            width=12,
            font=FONTS.BODY_BOLD,
            bg=_tk.GREEN,
            fg=_tk.BG,
            command=self._start,
        )
        self._start_btn.pack(side="left", padx=6)

        self._stop_btn = tk.Button(
            btn_frame,
            text=t("stop"),
            width=12,
            font=FONTS.BODY_BOLD,
            bg=_tk.RED,
            fg=_tk.BG,
            command=self._stop,
            state="disabled",
        )
        self._stop_btn.pack(side="left", padx=6)

    # ── 실시간 그래프 ─────────────────────────────────────

    def _init_graph(self):
        ax = self._ax
        ax.set_facecolor("#181825")
        for spine in ax.spines.values():
            spine.set_color("#585b70")
        ax.tick_params(colors="#cdd6f4", labelsize=7)
        ax.set_xlabel(t("graph_time_ticks"), color="#cdd6f4", fontsize=8)
        ax.set_ylabel(t("graph_temp_celsius"), color="#cdd6f4", fontsize=8)
        ax.set_title(t("graph_live_temp"), color="#89b4fa", fontsize=10, fontweight="bold")
        _tk = get_tk_theme()
        ax.axhline(y=-196.0, color=_tk.RED, linestyle="--", linewidth=1, alpha=0.7, label=t("graph_target_tc"))

        # 라인 객체를 미리 생성 (blitting용)
        (self._temp_line,) = ax.plot([], [], color="#89b4fa", linewidth=1.5, label=t("graph_temperature"))
        ax.legend(loc="upper right", fontsize=7, facecolor="#2a2a3d", edgecolor="#585b70", labelcolor="#cdd6f4")
        self._fig.tight_layout()
        self._canvas.draw()
        self._graph_bg = self._canvas.copy_from_bbox(ax.bbox)
        self._full_redraw_counter = 0

    def _update_graph(self, temperature: float):
        self._tick_count += 1
        self._temp_history.append(temperature)
        self._time_history.append(self._tick_count)

        if len(self._temp_history) > MAX_HISTORY:
            self._temp_history.pop(0)
            self._time_history.pop(0)

        ax = self._ax
        self._full_redraw_counter += 1

        # 매 20틱마다 full redraw (축 범위, fill_between 업데이트)
        if self._full_redraw_counter >= 20:
            self._full_redraw_counter = 0
            ax.set_xlim(self._time_history[0], self._time_history[-1])
            y_min = min(min(self._temp_history), -210.0)
            y_max = max(max(self._temp_history), 30.0)
            ax.set_ylim(y_min - 10, y_max + 10)

            # fill_between 갱신 (기존 컬렉션 제거 후 재생성)
            while ax.collections:
                ax.collections[0].remove()
            _tk = get_tk_theme()
            ax.fill_between(
                self._time_history,
                self._temp_history,
                -196.0,
                where=[tmp > -196.0 for tmp in self._temp_history],
                alpha=0.1,
                color=_tk.RED,
            )
            ax.fill_between(
                self._time_history,
                self._temp_history,
                -196.0,
                where=[tmp <= -196.0 for tmp in self._temp_history],
                alpha=0.1,
                color=_tk.GREEN,
            )
            self._fig.tight_layout()
            self._canvas.draw()
            self._graph_bg = self._canvas.copy_from_bbox(ax.bbox)
        else:
            # 빠른 업데이트: 라인 데이터만 갱신 + blit
            self._temp_line.set_data(self._time_history, self._temp_history)

            # 축 범위 초과 시에만 조정
            if self._time_history[-1] > ax.get_xlim()[1]:
                ax.set_xlim(self._time_history[0], self._time_history[-1])
                self._canvas.draw()
                self._graph_bg = self._canvas.copy_from_bbox(ax.bbox)

            self._canvas.restore_region(self._graph_bg)
            ax.draw_artist(self._temp_line)
            self._canvas.blit(ax.bbox)

    # ── 게이지 바 ────────────────────────────────────────

    def _draw_gauge_frame(self):
        c = self._gauge_canvas
        c.create_rectangle(15, 10, 45, 210, fill=TK.GAUGE_BG, outline="#585b70", width=1)
        marks = [("25°C", 10), ("-50", 52), ("-100", 94), ("-150", 136), ("-196", 180), ("-210", 210)]
        for label, y in marks:
            c.create_text(58, y, text=label, anchor="w", fill=TK.TEXT, font=FONTS.TINY)
            c.create_line(45, y, 50, y, fill="#585b70")
        c.create_rectangle(17, 210, 43, 210, fill=TK.ACCENT_BLUE, outline="", tags="bar")

    def _update_gauge(self, temperature: float):
        c = self._gauge_canvas
        t_min, t_max = -210.0, 25.0
        y_top, y_bot = 10, 210
        ratio = (t_max - temperature) / (t_max - t_min)
        ratio = max(0.0, min(1.0, ratio))
        bar_top = y_top + ratio * (y_bot - y_top)

        _tk = get_tk_theme()
        if temperature <= -196:
            color = _tk.GREEN
        elif temperature <= -190:
            color = _tk.YELLOW
        else:
            color = _tk.RED

        c.delete("bar")
        c.create_rectangle(17, bar_top, 43, y_bot, fill=color, outline="", tags="bar")

    # ── 콜백 / 제어 ─────────────────────────────────────

    def _on_state_update(self, state: CoolerState):
        self.after(0, self._apply_state, state)

    def _apply_state(self, state: CoolerState):
        if not self.winfo_exists():
            return

        self._temp_var.set(f"{state.temperature:.2f} °C")

        _tk = get_tk_theme()
        if state.temperature <= state.target:
            self._temp_label.config(fg=_tk.GREEN)
        elif state.emergency:
            self._temp_label.config(fg=_tk.RED)
        else:
            self._temp_label.config(fg=_tk.ACCENT_BLUE)

        self._update_gauge(state.temperature)
        self._update_graph(state.temperature)

        if state.emergency:
            self._status_var.set(t("emergency"))
        elif state.cooling_on:
            self._status_var.set(t("cooling"))
        else:
            self._status_var.set(t("standby"))

        self._target_var.set(t("target_temp", temp=state.target))
        self._cooling_var.set(t("cooler_state", state=t("on") if state.cooling_on else t("off")))
        self._emergency_var.set(t("emergency_state", state=t("on") if state.emergency else t("off")))

        # 로그 기록 (무한 성장 방지 — 최대 500줄)
        ts = datetime.now().strftime("%H:%M:%S")
        mode = "EMRG" if state.emergency else ("COOL" if state.cooling_on else "IDLE")
        line = f"[{ts}] {state.temperature:>8.2f}°C  | {mode}\n"
        self._log.configure(state="normal")
        self._log.insert("end", line)
        line_count = int(self._log.index("end-1c").split(".")[0])
        if line_count > 500:
            self._log.delete("1.0", "2.0")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _start(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._temp_history.clear()
        self._time_history.clear()
        self._tick_count = 0
        self._cooler.start()
        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._status_var.set(t("running"))

    def _stop(self):
        self._cooler.stop()
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._status_var.set(t("stopped"))

    def _on_close(self):
        self._cooler.stop()
        self.destroy()


def open_dashboard(master=None):
    Dashboard(master)
