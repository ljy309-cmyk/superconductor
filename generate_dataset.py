# 초전도체 실험 데이터 CSV 생성 스크립트
# UCI Superconductor Dataset 패턴을 참고하여 합성 데이터 생성
# 실행 후 superconductor_data.csv (21,263행) 생성

import numpy as np
import pandas as pd

np.random.seed(42)

N = 21263  # UCI 데이터셋과 유사한 규모

# ── 유형 분포 (실제 초전도체 연구 비율 반영) ──────────────
types = np.random.choice(
    ["원소", "합금", "화합물", "고온", "수소화물"],
    size=N,
    p=[0.08, 0.20, 0.45, 0.22, 0.05],
)

# ── 원소 개수 (물질을 구성하는 원소 수) ───────────────────
num_elements = np.where(
    types == "원소", 1,
    np.where(types == "합금", np.random.choice([2, 3], size=N, p=[0.6, 0.4]),
    np.where(types == "화합물", np.random.choice([2, 3, 4], size=N, p=[0.3, 0.4, 0.3]),
    np.where(types == "고온", np.random.choice([4, 5, 6], size=N, p=[0.3, 0.4, 0.3]),
    np.random.choice([2, 3], size=N, p=[0.7, 0.3])  # 수소화물
))))

# ── 평균 원자 질량 (amu) ─────────────────────────────────
mean_atomic_mass = np.where(
    types == "원소", np.random.uniform(6.9, 238.0, N),
    np.where(types == "합금", np.random.uniform(20.0, 180.0, N),
    np.where(types == "화합물", np.random.uniform(10.0, 160.0, N),
    np.where(types == "고온", np.random.uniform(30.0, 140.0, N),
    np.random.uniform(1.0, 60.0, N)  # 수소화물 (수소 포함으로 낮음)
))))

# ── 평균 가전자 수 ───────────────────────────────────────
mean_valence = np.where(
    types == "원소", np.random.choice([1, 2, 3, 4, 5], size=N, p=[0.1, 0.2, 0.3, 0.2, 0.2]).astype(float),
    np.random.uniform(1.5, 6.0, N),
)
# 소수점 한 자리로 반올림
mean_valence = np.round(mean_valence, 1)

# ── 밀도 (g/cm³) ─────────────────────────────────────────
density = np.where(
    types == "원소", np.random.uniform(0.5, 22.0, N),
    np.where(types == "합금", np.random.uniform(2.0, 16.0, N),
    np.where(types == "화합물", np.random.uniform(1.5, 14.0, N),
    np.where(types == "고온", np.random.uniform(3.0, 9.0, N),
    np.random.uniform(1.0, 8.0, N)  # 수소화물
))))

# ── 열전도도 (W/(m·K)) ──────────────────────────────────
thermal_conductivity = np.where(
    types == "원소", np.random.uniform(1.0, 400.0, N),
    np.where(types == "합금", np.random.uniform(5.0, 150.0, N),
    np.where(types == "화합물", np.random.uniform(0.5, 50.0, N),
    np.where(types == "고온", np.random.uniform(1.0, 15.0, N),
    np.random.uniform(5.0, 80.0, N)
))))

# ── 전자비열계수 (mJ/(mol·K²)) ──────────────────────────
electron_affinity = np.where(
    types == "원소", np.random.uniform(0.5, 10.0, N),
    np.random.uniform(0.1, 15.0, N),
)

# ── 임계 온도 Tc (K) — 물리적으로 현실적인 분포 ──────────
# 유형별 기본 Tc 범위 + 다른 변수들의 약한 영향
base_tc = np.where(
    types == "원소", np.random.exponential(2.5, N),               # 0~15K 범위, 대부분 낮음
    np.where(types == "합금", np.random.exponential(5.0, N) + 1,  # 1~30K
    np.where(types == "화합물", np.random.exponential(8.0, N) + 2, # 2~50K
    np.where(types == "고온", np.random.uniform(30.0, 165.0, N),   # 30~165K
    np.random.uniform(100.0, 290.0, N)                            # 수소화물: 100~290K
))))

# 가전자수 영향 (약한 양의 상관)
valence_effect = (mean_valence - 3.0) * np.random.uniform(0.5, 2.0, N)

# 밀도 영향 (매우 약한 상관)
density_effect = (density - 5.0) * np.random.uniform(-0.2, 0.3, N)

# 노이즈
noise = np.random.normal(0, 2.0, N)

tc = base_tc + valence_effect + density_effect + noise
tc = np.clip(tc, 0.001, 300.0)  # 물리적 범위로 클리핑
tc = np.round(tc, 2)

# ── 물질명 생성 ──────────────────────────────────────────
elements = [
    "H", "Li", "Be", "B", "C", "N", "O", "F",
    "Na", "Mg", "Al", "Si", "P", "S", "K", "Ca",
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Rb", "Sr", "Y", "Zr", "Nb", "Mo",
    "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te",
    "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Sm", "Eu", "Gd",
    "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu",
    "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
    "Tl", "Pb", "Bi", "Th", "U",
]

subscripts = ["", "2", "3", "4", "5", "6", "7", "8"]

material_names = []
for i in range(N):
    n_elem = int(num_elements[i])
    chosen = np.random.choice(elements, size=n_elem, replace=False)
    name = ""
    for elem in chosen:
        sub = np.random.choice(subscripts[:4], p=[0.4, 0.3, 0.2, 0.1])
        name += elem + sub
    # 중복 방지를 위해 인덱스 추가 (큰 데이터셋)
    material_names.append(name)

# ── DataFrame 생성 ───────────────────────────────────────
df = pd.DataFrame({
    "물질명": material_names,
    "유형": types,
    "원소수": num_elements.astype(int),
    "평균원자질량": np.round(mean_atomic_mass, 2),
    "평균가전자수": mean_valence,
    "밀도": np.round(density, 2),
    "열전도도": np.round(thermal_conductivity, 2),
    "전자비열계수": np.round(electron_affinity, 2),
    "Tc": tc,
})

# ── CSV 저장 ─────────────────────────────────────────────
csv_path = "superconductor_data.csv"
df.to_csv(csv_path, index=False, encoding="utf-8-sig")

print(f"데이터셋 생성 완료!")
print(f"  파일: {csv_path}")
print(f"  행 수: {len(df):,}개")
print(f"  열: {list(df.columns)}")
print(f"\n유형별 분포:")
print(df["유형"].value_counts().to_string())
print(f"\nTc 통계:")
print(df["Tc"].describe().to_string())
