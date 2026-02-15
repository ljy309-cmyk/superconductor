# 임계 온도 예측 데이터 분석
# 학습 포인트: 외부 라이브러리 활용 (pandas, scipy, matplotlib)
# CSV 파일(2만 개 이상 실험 데이터) 또는 내장 데이터셋으로 분석 가능

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from scipy.optimize import curve_fit


# ── 내장 초전도체 데이터셋 (소규모 기본 데이터) ──────────
# CSV 파일이 없을 때 사용되는 폴백 데이터
# 출처: 물리학 핸드북, 실험 논문 데이터 종합

SUPERCONDUCTOR_DATA = [
    # (물질명, 유형, 평균 원자 질량(amu), 가전자 수, 밀도(g/cm³), T_c(K))
    ("Al",          "원소",     26.98,  3,   2.70,   1.18),
    ("Ti",          "원소",     47.87,  4,   4.51,   0.40),
    ("Zn",          "원소",     65.38,  2,   7.13,   0.85),
    ("Ga",          "원소",     69.72,  3,   5.91,   1.08),
    ("Sn",          "원소",     118.71, 4,  7.27,   3.72),
    ("Hg",          "원소",     200.59, 2,  13.53,   4.15),
    ("Pb",          "원소",     207.2,  4,  11.34,   7.19),
    ("Nb",          "원소",     92.91,  5,   8.57,   9.26),
    ("V",           "원소",     50.94,  5,   6.11,   5.40),
    ("La",          "원소",     138.91, 3,   6.15,   6.00),
    ("Ta",          "원소",     180.95, 5,  16.65,   4.47),
    ("NbN",         "화합물",   52.95,  5,   8.47,  16.00),
    ("NbTi",        "합금",     70.39,  5,   6.50,   9.80),
    ("Nb3Sn",       "화합물",   72.38,  5,   8.96,  18.30),
    ("Nb3Ge",       "화합물",   64.64,  5,   8.20,  23.20),
    ("MgB2",        "화합물",   24.31,  2,   2.57,  39.00),
    ("YBa2Cu3O7",   "고온",     93.27,  3,   6.30,  92.00),
    ("Bi2Sr2CaCu2O8","고온",    104.58, 3,   6.50,  85.00),
    ("HgBa2Ca2Cu3O8","고온",    135.20, 3,   7.80, 133.00),
    ("LaH10",       "수소화물", 14.89,  3,   5.50, 250.00),
]

COLUMNS = ["물질명", "유형", "평균원자질량", "가전자수", "밀도", "Tc"]

# CSV 파일의 열 이름 (확장된 데이터)
CSV_COLUMNS = ["물질명", "유형", "원소수", "평균원자질량", "평균가전자수",
               "밀도", "열전도도", "전자비열계수", "Tc"]

# CSV에서 분석 가능한 수치 열 목록
CSV_NUMERIC_COLS = ["평균원자질량", "평균가전자수", "밀도", "열전도도", "전자비열계수", "원소수"]

DEFAULT_CSV_PATH = "superconductor_data.csv"


def load_dataset():
    """내장 초전도체 데이터를 pandas DataFrame으로 반환한다."""
    df = pd.DataFrame(SUPERCONDUCTOR_DATA, columns=COLUMNS)
    return df


def load_csv(csv_path):
    """CSV 파일에서 초전도체 데이터를 로드한다.

    Args:
        csv_path: CSV 파일 경로

    Returns:
        pandas DataFrame

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        ValueError: 필수 열(물질명, 유형, Tc)이 없을 때
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {csv_path}")

    df = pd.read_csv(csv_path)

    # 필수 열 검증
    required = {"물질명", "유형", "Tc"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"필수 열이 없습니다: {missing}")

    return df


def get_numeric_columns(df):
    """DataFrame에서 Tc를 제외한 수치형 열 목록을 반환한다."""
    numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    return [c for c in numeric if c != "Tc"]


def show_basic_stats(df):
    """데이터셋 기본 통계를 출력한다."""
    print("\n[ 데이터셋 기본 정보 ]")
    print(f"  총 물질 수: {len(df)}개")
    print(f"  유형별 개수:")
    for type_name, count in df["유형"].value_counts().items():
        print(f"    {type_name}: {count}개")

    print(f"\n[ 임계 온도(T_c) 통계 ]")
    print(f"  최솟값: {df['Tc'].min():.2f} K ({df.loc[df['Tc'].idxmin(), '물질명']})")
    print(f"  최댓값: {df['Tc'].max():.2f} K ({df.loc[df['Tc'].idxmax(), '물질명']})")
    print(f"  평균값: {df['Tc'].mean():.2f} K")
    print(f"  중앙값: {df['Tc'].median():.2f} K")
    print(f"  표준편차: {df['Tc'].std():.2f} K")

    # CSV 데이터(대규모)인 경우 추가 분위수 정보
    if len(df) > 100:
        print(f"\n[ 분위수 ]")
        for q in [0.25, 0.50, 0.75, 0.90, 0.95, 0.99]:
            print(f"  {q*100:5.1f}%: {df['Tc'].quantile(q):8.2f} K")


def show_data_table(df, max_rows=30):
    """데이터를 표 형태로 출력한다. 대규모 데이터는 앞뒤만 보여준다."""
    num_cols = get_numeric_columns(df)
    print(f"\n[ 초전도체 데이터 테이블 ] (총 {len(df)}개)")
    print("-" * 75)

    # 열 헤더 결정 (데이터에 있는 열 기준)
    header_cols = ["물질명", "유형"]
    display_cols = []
    for col in ["평균원자질량", "평균가전자수", "가전자수", "밀도", "Tc"]:
        if col in df.columns:
            header_cols.append(col)
            display_cols.append(col)

    print(f"{'물질명':16s} {'유형':8s}", end="")
    for col in display_cols:
        print(f" {col:>10s}", end="")
    print()
    print("-" * 75)

    if len(df) <= max_rows:
        rows_to_show = df
    else:
        # 앞 15개 + 뒤 15개
        rows_to_show = pd.concat([df.head(15), df.tail(15)])
        show_ellipsis = True

    for idx, (_, row) in enumerate(rows_to_show.iterrows()):
        if len(df) > max_rows and idx == 15:
            print(f"  ... ({len(df) - 30}개 행 생략) ...")
        print(f"{str(row['물질명']):16s} {str(row['유형']):8s}", end="")
        for col in display_cols:
            print(f" {row[col]:10.2f}", end="")
        print()
    print("-" * 75)


def compute_correlation(df):
    """각 수치 변수와 T_c 사이의 상관계수를 계산한다."""
    numeric_cols = get_numeric_columns(df)
    results = []

    print(f"\n[ 상관 분석: 각 변수 vs T_c ] ({len(numeric_cols)}개 변수)")
    print("-" * 65)
    for col in numeric_cols:
        r, p_value = stats.pearsonr(df[col], df["Tc"])
        results.append({"변수": col, "상관계수(r)": r, "p-value": p_value})
        strength = "강함" if abs(r) > 0.5 else "약함"
        sign = "양의" if r > 0 else "음의"
        sig = "***" if p_value < 0.001 else ("**" if p_value < 0.01 else ("*" if p_value < 0.05 else ""))
        print(f"  {col:12s} → r = {r:+.4f} (p={p_value:.4e}) [{sign} 상관, {strength}] {sig}")
    print("-" * 65)
    if len(df) > 100:
        print("  유의수준: *** p<0.001, ** p<0.01, * p<0.05")

    return pd.DataFrame(results)


def linear_model(x, a, b):
    """선형 모델: y = a*x + b"""
    return a * x + b


def fit_regression(df, x_col):
    """주어진 열에 대해 T_c의 선형 회귀를 수행한다.

    Args:
        df: 데이터프레임
        x_col: 독립 변수 열 이름

    Returns:
        (기울기, 절편, R² 값) 튜플
    """
    x = df[x_col].values
    y = df["Tc"].values

    popt, _ = curve_fit(linear_model, x, y)
    a, b = popt

    # R² 계산
    y_pred = linear_model(x, a, b)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (ss_res / ss_tot)

    return a, b, r_squared


def show_type_summary(df):
    """유형별 Tc 요약 통계를 출력한다."""
    print("\n[ 유형별 Tc 요약 통계 ]")
    print("-" * 70)
    print(f"  {'유형':10s} {'개수':>6s} {'평균(K)':>8s} {'중앙값(K)':>9s} "
          f"{'최솟값(K)':>9s} {'최댓값(K)':>9s} {'표준편차':>8s}")
    print("-" * 70)

    for type_name in sorted(df["유형"].unique()):
        subset = df[df["유형"] == type_name]["Tc"]
        print(f"  {type_name:10s} {len(subset):6d} {subset.mean():8.2f} "
              f"{subset.median():9.2f} {subset.min():9.2f} "
              f"{subset.max():9.2f} {subset.std():8.2f}")
    print("-" * 70)
    print(f"  {'전체':10s} {len(df):6d} {df['Tc'].mean():8.2f} "
          f"{df['Tc'].median():9.2f} {df['Tc'].min():9.2f} "
          f"{df['Tc'].max():9.2f} {df['Tc'].std():8.2f}")


def plot_analysis(df, save_path=None):
    """4개 서브플롯으로 데이터 분석 결과를 시각화한다.

    1. T_c 분포 히스토그램
    2. 평균원자질량 vs T_c 산점도 + 회귀선
    3. 유형별 T_c 비교 박스플롯
    4. 밀도 vs T_c 산점도 + 회귀선

    Returns:
        fig, axes
    """
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # 유형별 색상
    type_colors = {"원소": "#1E88E5", "화합물": "#43A047",
                   "합금": "#FB8C00", "고온": "#E53935", "수소화물": "#8E24AA"}

    colors = [type_colors.get(t, "#999999") for t in df["유형"]]

    # 대규모 데이터용 점 크기/투명도 조정
    n = len(df)
    point_size = max(5, min(80, 800 / (n ** 0.5)))
    alpha = max(0.1, min(1.0, 100 / (n ** 0.5)))

    # 히스토그램 빈 수 조정
    n_bins = min(50, max(10, int(n ** 0.5)))

    # 1. T_c 분포 히스토그램
    ax1 = axes[0, 0]
    ax1.hist(df["Tc"], bins=n_bins, color="#42A5F5", edgecolor="white", alpha=0.8)
    ax1.set_xlabel("Tc (K)")
    ax1.set_ylabel("Count")
    ax1.set_title(f"Tc Distribution (n={n:,})")
    ax1.axvline(df["Tc"].median(), color="red", linestyle="--",
                label=f"Median={df['Tc'].median():.1f}K")
    ax1.legend()

    # 2. 평균원자질량 vs T_c
    ax2 = axes[0, 1]
    mass_col = "평균원자질량"
    ax2.scatter(df[mass_col], df["Tc"], c=colors, s=point_size,
                alpha=alpha, edgecolors="none", zorder=5)
    a, b, r2 = fit_regression(df, mass_col)
    x_fit = np.linspace(df[mass_col].min(), df[mass_col].max(), 100)
    ax2.plot(x_fit, linear_model(x_fit, a, b), "r--", alpha=0.7, label=f"R²={r2:.3f}")
    ax2.set_xlabel("Avg Atomic Mass (amu)")
    ax2.set_ylabel("Tc (K)")
    ax2.set_title("Atomic Mass vs Tc")
    ax2.legend()

    # 3. 유형별 T_c 박스플롯
    ax3 = axes[1, 0]
    type_order = ["원소", "합금", "화합물", "고온", "수소화물"]
    existing_types = [t for t in type_order if t in df["유형"].values]
    data_by_type = [df[df["유형"] == t]["Tc"].values for t in existing_types]
    bp = ax3.boxplot(data_by_type, tick_labels=existing_types, patch_artist=True)
    for patch, t in zip(bp["boxes"], existing_types):
        patch.set_facecolor(type_colors.get(t, "#999999"))
        patch.set_alpha(0.7)
    ax3.set_ylabel("Tc (K)")
    ax3.set_title("Tc by Material Type")

    # 4. 밀도 vs T_c
    ax4 = axes[1, 1]
    ax4.scatter(df["밀도"], df["Tc"], c=colors, s=point_size,
                alpha=alpha, edgecolors="none", zorder=5)
    a, b, r2 = fit_regression(df, "밀도")
    x_fit = np.linspace(df["밀도"].min(), df["밀도"].max(), 100)
    ax4.plot(x_fit, linear_model(x_fit, a, b), "r--", alpha=0.7, label=f"R²={r2:.3f}")
    ax4.set_xlabel("Density (g/cm³)")
    ax4.set_ylabel("Tc (K)")
    ax4.set_title("Density vs Tc")
    ax4.legend()

    # 범례 (유형별 색상)
    for t, c in type_colors.items():
        if t in df["유형"].values:
            ax2.scatter([], [], c=c, s=60, label=t)
    ax2.legend(fontsize=8)

    plt.suptitle(f"Superconductor Tc Data Analysis (n={n:,})", fontsize=15, y=1.01)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"그래프가 '{save_path}'에 저장되었습니다.")
    else:
        plt.show()

    return fig, axes


def run_tc_analysis():
    """임계 온도 예측 데이터 분석 실행 (대화형)."""
    print("--- 임계 온도 예측 데이터 분석 ---")
    print("초전도체의 물리적 성질과 임계 온도(Tc) 관계를 분석합니다.\n")

    # 1. 데이터 소스 선택
    print("[ 데이터 소스 선택 ]")
    print(f"  1. CSV 파일 불러오기 (기본: {DEFAULT_CSV_PATH})")
    print("  2. 내장 데이터셋 사용 (20개 물질)")

    source_choice = input("선택 (기본값 1): ").strip() or "1"

    if source_choice == "1":
        csv_path = input(f"CSV 파일 경로 (기본값: {DEFAULT_CSV_PATH}): ").strip()
        csv_path = csv_path or DEFAULT_CSV_PATH
        try:
            df = load_csv(csv_path)
            print(f"  ✔ CSV 로드 완료: {len(df):,}개 데이터")
        except (FileNotFoundError, ValueError) as e:
            print(f"  오류: {e}")
            print("  → 내장 데이터셋으로 전환합니다.")
            df = load_dataset()
    else:
        df = load_dataset()
        print(f"  내장 데이터셋 로드: {len(df)}개 물질")

    # 수치 열 목록 파악
    numeric_cols = get_numeric_columns(df)

    while True:
        print("\n[ 분석 메뉴 ]")
        print("  1. 데이터 테이블 보기")
        print("  2. 기본 통계 보기")
        print("  3. 상관 분석 (변수별 Tc 상관계수)")
        print("  4. 회귀 분석 (변수 선택 → 기울기, R²)")
        print("  5. 그래프 저장 (4종 분석 차트)")
        print("  6. 유형별 Tc 요약")
        print("  0. 메인 메뉴로 돌아가기")

        choice = input("분석 번호를 선택하세요: ").strip()

        if choice == "1":
            show_data_table(df)
        elif choice == "2":
            show_basic_stats(df)
        elif choice == "3":
            compute_correlation(df)
        elif choice == "4":
            print("\n회귀 분석할 변수를 선택하세요:")
            var_map = {}
            for i, col in enumerate(numeric_cols, 1):
                print(f"  {i}. {col}")
                var_map[str(i)] = col
            var_choice = input("변수 번호 (기본값 1): ").strip() or "1"
            col = var_map.get(var_choice, numeric_cols[0])
            a, b, r2 = fit_regression(df, col)
            print(f"\n[ 회귀 결과: {col} → Tc ]")
            print(f"  Tc = {a:.4f} × {col} + {b:.4f}")
            print(f"  R² = {r2:.4f}")
            if r2 < 0.3:
                print("  → 선형 관계가 약합니다. 비선형 모델이 더 적합할 수 있습니다.")
            elif r2 < 0.7:
                print("  → 약한 선형 관계가 있습니다.")
            else:
                print("  → 강한 선형 관계가 있습니다.")
        elif choice == "5":
            plot_analysis(df, save_path="tc_analysis.png")
            print("분석 완료!")
        elif choice == "6":
            show_type_summary(df)
        elif choice == "0":
            break
        else:
            print("올바른 번호를 입력해 주세요. (0~6)")
