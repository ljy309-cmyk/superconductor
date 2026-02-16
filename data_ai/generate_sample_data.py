"""초전도체 샘플 데이터 생성 → Excel 파일로 저장.

특성 컬럼: density, atomic_mass, electron_affinity, thermal_conductivity,
           valence, electronegativity (미션2)
타깃: critical_temp (Tc, K)

미션1: 실제 초전도체 원소 데이터 포함 (Al, Sn, Pb, Nb, V, Hg, In, Ta)
미션2: electronegativity 컬럼 추가 → AI 힌트 6개
"""

import os

import pandas as pd
import numpy as np

from config_loader import cfg

SAMPLE_SIZE = cfg("data_gen", "sample_size", 200)
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "superconductor_data.xlsx")
CSV_PATH = os.path.join(os.path.dirname(__file__), "superconductor_data.csv")

# ── 미션1: 실제 초전도체 원소 데이터 (구글링 기반) ──────
#  이름, 밀도, 원자질량, 전자친화도, 열전도도, 원자가전자, 전기음성도, 임계온도
REAL_SUPERCONDUCTORS = [
    # name      density  mass    e_aff   therm_k  valence  electroneg  Tc(K)
    ("Al",       2.70,   26.98,  42.5,   237.0,   3,       1.61,       1.18),
    ("Sn",       7.31,  118.71,  107.3,   66.8,   4,       1.96,       3.72),
    ("Pb",      11.34,  207.20,  35.1,    35.3,   4,       2.33,       7.19),
    ("Nb",       8.57,   92.91,  86.1,    53.7,   5,       1.60,       9.25),
    ("V",        6.11,   50.94,  50.9,    30.7,   5,       1.63,       5.40),
    ("Hg",      13.53,  200.59,  34.2,     8.3,   2,       2.00,       4.15),
    ("In",       7.31,  114.82,  28.9,    81.8,   3,       1.78,       3.41),
    ("Ta",      16.65,  180.95,  31.0,    57.5,   5,       1.50,       4.47),
    ("Zn",       7.13,   65.38,   9.4,   116.0,   2,       1.65,       0.85),
    ("Ti",       4.51,   47.87,   7.6,    21.9,   4,       1.54,       0.40),
    ("Ga",       5.91,   69.72,  28.9,    40.6,   3,       1.81,       1.08),
    ("Tc",      11.00,   97.00,  53.0,    50.6,   7,       1.90,       7.77),
]


def generate():
    """샘플 데이터를 생성하여 Excel + CSV로 저장.

    미션1: 실제 원소 데이터를 맨 위에 포함
    미션2: electronegativity 컬럼 추가
    """
    rng = np.random.default_rng(42)

    # ── 실제 데이터 (미션1) ──
    real_rows = []
    for name, dens, mass, ea, tk, val, en, tc in REAL_SUPERCONDUCTORS:
        real_rows.append({
            "name": name,
            "density": dens,
            "atomic_mass": mass,
            "electron_affinity": ea,
            "thermal_conductivity": tk,
            "valence": val,
            "electronegativity": en,
            "critical_temp": tc,
        })
    df_real = pd.DataFrame(real_rows)

    # ── 합성 데이터 ──
    density = rng.uniform(2.0, 12.0, SAMPLE_SIZE)
    atomic_mass = rng.uniform(20.0, 210.0, SAMPLE_SIZE)
    electron_affinity = rng.uniform(10.0, 200.0, SAMPLE_SIZE)
    thermal_conductivity = rng.uniform(0.1, 500.0, SAMPLE_SIZE)
    valence = rng.integers(1, 8, SAMPLE_SIZE).astype(float)
    electronegativity = rng.uniform(0.7, 3.5, SAMPLE_SIZE)  # 미션2

    # Tc 합성 (비선형 관계 + 노이즈 — 전기음성도도 반영)
    critical_temp = (
        0.5 * density
        + 0.15 * electron_affinity
        - 0.02 * atomic_mass
        + 0.005 * thermal_conductivity
        + 3.0 * valence
        - 2.0 * electronegativity  # 미션2: 전기음성도 높으면 Tc 낮아지는 경향
        + rng.normal(0, 5, SAMPLE_SIZE)
    )
    critical_temp = np.clip(critical_temp, 0.5, 180.0)

    df_synth = pd.DataFrame({
        "name": [f"Synth-{i:03d}" for i in range(SAMPLE_SIZE)],
        "density": np.round(density, 2),
        "atomic_mass": np.round(atomic_mass, 2),
        "electron_affinity": np.round(electron_affinity, 2),
        "thermal_conductivity": np.round(thermal_conductivity, 2),
        "valence": valence.astype(int),
        "electronegativity": np.round(electronegativity, 2),
        "critical_temp": np.round(critical_temp, 2),
    })

    # 실제 + 합성 결합
    df = pd.concat([df_real, df_synth], ignore_index=True)

    # 엑셀 + CSV 동시 저장
    df.to_excel(OUTPUT_PATH, index=False)
    df.to_csv(CSV_PATH, index=False)
    return OUTPUT_PATH


def load_from_csv(path: str) -> pd.DataFrame:
    """미션1: 외부 CSV 파일에서 데이터 로드."""
    return pd.read_csv(path)


if __name__ == "__main__":
    path = generate()
    df = pd.read_excel(path)
    print(f"Sample data saved to {path}")
    print(f"  Total rows: {len(df)}")
    print(f"  Real superconductors: {len(REAL_SUPERCONDUCTORS)}")
    print(f"  Columns: {list(df.columns)}")
    print(df.head(15))
