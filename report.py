"""시뮬레이션 결과 보고서 생성 — PNG 이미지 + 텍스트 요약.

사용법:
    from report import generate_report
    generate_report("bb84_defense", data_dict, output_dir="reports")
"""

import os
from datetime import datetime

from logger import get_module_logger

_log = get_module_logger("report")

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

# 모듈별 보고서 제목
_MODULE_TITLES = {
    "qubit_chain": "Qubit Entanglement Cascade",
    "tunneling": "Quantum Superposition & Tunneling",
    "qec_shield": "Quantum Error Correction Shield",
    "squid_mines": "SQUID Magnetic Flux Minesweeper",
    "bb84_defense": "BB84 Quantum Key Distribution Defense",
    "flux_pinning": "Meissner Levitation & Flux Pinning",
    "phase_transition": "Superconducting Phase Transition",
}


def generate_report(module_name: str, data: dict, output_dir: str | None = None) -> str:
    """시뮬레이션 결과 보고서 생성 (PNG 이미지).

    Args:
        module_name: 모듈 이름
        data: 시뮬레이션 결과 데이터
        output_dir: 출력 디렉토리 (기본: reports/)

    Returns:
        생성된 보고서 파일 경로
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover
        _log.warning("matplotlib 없음 — 텍스트 보고서만 생성")
        return _generate_text_report(module_name, data, output_dir)

    out_dir = output_dir or REPORTS_DIR
    os.makedirs(out_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    title = _MODULE_TITLES.get(module_name, module_name)
    filename = f"report_{module_name}_{timestamp}.png"
    filepath = os.path.join(out_dir, filename)

    # 보고서 레이아웃 생성
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor="#1e1e2e")
    fig.suptitle(f"Simulation Report — {title}", color="#cdd6f4", fontsize=14, fontweight="bold")

    # 좌측: 데이터 요약 테이블
    ax_table = axes[0]
    ax_table.set_facecolor("#181825")
    ax_table.axis("off")
    ax_table.set_title("Parameters & Results", color="#89b4fa", fontsize=11, pad=10)

    # 테이블 데이터
    table_data = []
    for key, val in data.items():
        if isinstance(val, float):
            table_data.append([key, f"{val:.2f}"])
        elif isinstance(val, bool):
            table_data.append([key, "Yes" if val else "No"])
        else:
            table_data.append([key, str(val)])

    if table_data:
        table = ax_table.table(
            cellText=table_data,
            colLabels=["Metric", "Value"],
            loc="center",
            cellLoc="left",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        for cell in table.get_celld().values():
            cell.set_facecolor("#2a2a3d")
            cell.set_edgecolor("#585b70")
            cell.set_text_props(color="#cdd6f4")

    # 우측: 핵심 지표 바 차트
    ax_bar = axes[1]
    ax_bar.set_facecolor("#181825")
    ax_bar.set_title("Key Metrics", color="#89b4fa", fontsize=11, pad=10)

    numeric_items = {k: v for k, v in data.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    if numeric_items:
        labels = list(numeric_items.keys())[:8]
        values = [numeric_items[k] for k in labels]
        colors = ["#89b4fa", "#a6e3a1", "#f9e2af", "#cba6f7", "#f38ba8", "#fab387", "#74c7ec", "#94e2d5"]
        bars = ax_bar.barh(labels, values, color=colors[: len(labels)])
        ax_bar.tick_params(colors="#cdd6f4", labelsize=8)
        for spine in ax_bar.spines.values():
            spine.set_color("#585b70")

        # 값 레이블
        for bar, val in zip(bars, values):
            ax_bar.text(
                bar.get_width(),
                bar.get_y() + bar.get_height() / 2,
                f" {val:.1f}" if isinstance(val, float) else f" {val}",
                va="center",
                color="#cdd6f4",
                fontsize=8,
            )
    else:
        ax_bar.text(
            0.5,
            0.5,
            "No numeric data",
            transform=ax_bar.transAxes,
            ha="center",
            va="center",
            color="#585b70",
            fontsize=12,
        )

    # 타임스탬프
    fig.text(
        0.5,
        0.02,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ha="center",
        color="#585b70",
        fontsize=8,
    )

    fig.tight_layout(rect=[0, 0.05, 1, 0.93])
    fig.savefig(filepath, dpi=150, facecolor="#1e1e2e", bbox_inches="tight")
    plt.close(fig)

    _log.info("보고서 생성: %s", filepath)
    return filepath


def _generate_text_report(module_name: str, data: dict, output_dir: str | None = None) -> str:
    """텍스트 전용 보고서 (matplotlib 없을 때 대안)."""
    out_dir = output_dir or REPORTS_DIR
    os.makedirs(out_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    title = _MODULE_TITLES.get(module_name, module_name)
    filename = f"report_{module_name}_{timestamp}.txt"
    filepath = os.path.join(out_dir, filename)

    lines = [
        "=" * 60,
        f"  Simulation Report — {title}",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
    ]

    for key, val in data.items():
        if isinstance(val, float):
            lines.append(f"  {key:30s} : {val:.4f}")
        else:
            lines.append(f"  {key:30s} : {val}")

    lines.append("")
    lines.append("=" * 60)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    _log.info("텍스트 보고서 생성: %s", filepath)
    return filepath
