"""초전도체 샘플 데이터 생성 → Excel 파일로 저장.

특성 컬럼: density, atomic_mass, electron_affinity, thermal_conductivity,
           valence, electronegativity
타깃: critical_temp (Tc, K)

데이터 모드:
  - "synthetic": 합성 데이터 200개 + 실제 원소 12종 (기본)
  - "supercon": SuperCon 실제 데이터셋 스타일의 확장 데이터 (화합물 기반)
"""

import os

from config_loader import cfg

SAMPLE_SIZE = cfg("data_gen", "sample_size", 200)
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "superconductor_data.xlsx")
CSV_PATH = os.path.join(os.path.dirname(__file__), "superconductor_data.csv")
SUPERCON_PATH = os.path.join(os.path.dirname(__file__), "supercon_data.csv")

# ── 실제 초전도체 원소 데이터 (구글링 기반) ──────
REAL_SUPERCONDUCTORS = [
    # name      density  mass    e_aff   therm_k  valence  electroneg  Tc(K)
    ("Al", 2.70, 26.98, 42.5, 237.0, 3, 1.61, 1.18),
    ("Sn", 7.31, 118.71, 107.3, 66.8, 4, 1.96, 3.72),
    ("Pb", 11.34, 207.20, 35.1, 35.3, 4, 2.33, 7.19),
    ("Nb", 8.57, 92.91, 86.1, 53.7, 5, 1.60, 9.25),
    ("V", 6.11, 50.94, 50.9, 30.7, 5, 1.63, 5.40),
    ("Hg", 13.53, 200.59, 34.2, 8.3, 2, 2.00, 4.15),
    ("In", 7.31, 114.82, 28.9, 81.8, 3, 1.78, 3.41),
    ("Ta", 16.65, 180.95, 31.0, 57.5, 5, 1.50, 4.47),
    ("Zn", 7.13, 65.38, 9.4, 116.0, 2, 1.65, 0.85),
    ("Ti", 4.51, 47.87, 7.6, 21.9, 4, 1.54, 0.40),
    ("Ga", 5.91, 69.72, 28.9, 40.6, 3, 1.81, 1.08),
    ("Tc", 11.00, 97.00, 53.0, 50.6, 7, 1.90, 7.77),
]

# ── SuperCon 실제 화합물 데이터 (문헌 기반 대표 초전도체) ──
# 고온 초전도체, A15 화합물, MgB2, 철계 등 다양한 계열 포함
SUPERCON_COMPOUNDS = [
    # name                density  mass    e_aff   therm_k  valence  electroneg  Tc(K)
    # ── 원소 초전도체 ──
    ("Nb", 8.57, 92.91, 86.1, 53.7, 5, 1.60, 9.25),
    ("Pb", 11.34, 207.20, 35.1, 35.3, 4, 2.33, 7.19),
    ("V", 6.11, 50.94, 50.9, 30.7, 5, 1.63, 5.40),
    ("Hg", 13.53, 200.59, 34.2, 8.3, 2, 2.00, 4.15),
    ("Sn", 7.31, 118.71, 107.3, 66.8, 4, 1.96, 3.72),
    # ── A15 화합물 ──
    ("Nb3Sn", 8.90, 98.0, 72.0, 25.0, 4, 1.72, 18.3),
    ("Nb3Ge", 8.60, 88.5, 68.0, 20.0, 4, 1.68, 23.2),
    ("Nb3Al", 7.80, 73.0, 56.0, 30.0, 4, 1.62, 18.9),
    ("V3Si", 5.70, 52.0, 45.0, 35.0, 4, 1.68, 17.1),
    ("V3Ga", 6.20, 58.0, 48.0, 28.0, 4, 1.70, 16.8),
    # ── MgB2 ──
    ("MgB2", 2.57, 22.8, 26.0, 40.0, 3, 1.55, 39.0),
    # ── 쿠프레이트 고온 초전도체 ──
    ("YBa2Cu3O7", 6.38, 88.5, 52.0, 5.0, 3, 1.82, 92.0),
    ("Bi2Sr2CaCu2O8", 6.50, 105.0, 48.0, 3.5, 3, 1.90, 85.0),
    ("Bi2Sr2Ca2Cu3O10", 6.60, 108.0, 46.0, 3.0, 3, 1.92, 110.0),
    ("Tl2Ba2Ca2Cu3O10", 8.20, 140.0, 40.0, 4.0, 3, 1.95, 125.0),
    ("HgBa2Ca2Cu3O8", 8.80, 152.0, 38.0, 3.5, 3, 1.98, 133.0),
    ("La1.85Sr0.15CuO4", 6.80, 98.0, 50.0, 6.0, 3, 1.78, 38.0),
    ("La1.85Ba0.15CuO4", 6.90, 100.0, 49.0, 5.5, 3, 1.76, 30.0),
    # ── 철계 초전도체 (Iron pnictide / chalcogenide) ──
    ("LaFeAsO0.9F0.1", 6.15, 78.0, 55.0, 12.0, 3, 1.72, 26.0),
    ("SmFeAsO0.85", 7.10, 82.0, 58.0, 10.0, 3, 1.75, 55.0),
    ("BaFe2As2 (K-doped)", 6.40, 85.0, 54.0, 15.0, 3, 1.70, 38.0),
    ("FeSe", 4.80, 66.0, 62.0, 10.0, 3, 1.80, 8.0),
    ("FeSe (pressured)", 4.80, 66.0, 62.0, 10.0, 3, 1.80, 37.0),
    ("NdFeAsO0.85", 7.20, 80.0, 57.0, 11.0, 3, 1.74, 52.0),
    # ── 기타 화합물 ──
    ("NbN", 8.47, 55.0, 72.0, 15.0, 4, 1.68, 16.0),
    ("NbC", 7.82, 53.0, 68.0, 14.0, 4, 1.65, 11.5),
    ("MoN", 9.20, 55.0, 65.0, 12.0, 4, 1.72, 12.0),
    ("PbMo6S8", 8.50, 110.0, 55.0, 8.0, 4, 1.85, 15.2),
    ("Ba0.6K0.4BiO3", 6.80, 95.0, 42.0, 7.0, 3, 1.88, 30.0),
    # ── 중페르미온 초전도체 ──
    ("CeCoIn5", 8.10, 82.0, 45.0, 8.0, 3, 1.72, 2.3),
    ("UPt3", 19.40, 205.0, 30.0, 6.0, 4, 1.50, 0.48),
    ("CeCu2Si2", 7.50, 78.0, 40.0, 10.0, 3, 1.70, 0.65),
    # ── 최근 발견 초전도체 ──
    ("H3S (200GPa)", 3.10, 17.0, 72.5, 20.0, 2, 2.10, 203.0),
    ("LaH10 (170GPa)", 5.50, 57.0, 48.0, 15.0, 3, 1.65, 250.0),
    ("CaH6 (172GPa)", 3.80, 24.0, 60.0, 18.0, 3, 1.50, 215.0),
]


def generate():
    """샘플 데이터를 생성하여 Excel + CSV로 저장.

    미션1: 실제 원소 데이터를 맨 위에 포함
    미션2: electronegativity 컬럼 추가
    """
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(42)

    # ── 실제 데이터 (미션1) ──
    real_rows = []
    for name, dens, mass, ea, tk, val, en, tc in REAL_SUPERCONDUCTORS:
        real_rows.append(
            {
                "name": name,
                "density": dens,
                "atomic_mass": mass,
                "electron_affinity": ea,
                "thermal_conductivity": tk,
                "valence": val,
                "electronegativity": en,
                "critical_temp": tc,
            }
        )
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

    df_synth = pd.DataFrame(
        {
            "name": [f"Synth-{i:03d}" for i in range(SAMPLE_SIZE)],
            "density": np.round(density, 2),
            "atomic_mass": np.round(atomic_mass, 2),
            "electron_affinity": np.round(electron_affinity, 2),
            "thermal_conductivity": np.round(thermal_conductivity, 2),
            "valence": valence.astype(int),
            "electronegativity": np.round(electronegativity, 2),
            "critical_temp": np.round(critical_temp, 2),
        }
    )

    # 실제 + 합성 결합
    df = pd.concat([df_real, df_synth], ignore_index=True)

    # 엑셀 + CSV 동시 저장
    df.to_excel(OUTPUT_PATH, index=False)
    df.to_csv(CSV_PATH, index=False)
    return OUTPUT_PATH


def generate_supercon():
    """SuperCon 실제 데이터셋 스타일의 확장 데이터 생성.

    문헌 기반 실제 화합물 데이터 + 계열별 합성 확장을 결합합니다.
    고온 초전도체, A15, 철계, 중페르미온, 수소화물 등 포함.
    """
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(2024)

    # ── 실제 화합물 데이터 ──
    real_rows = []
    for entry in SUPERCON_COMPOUNDS:
        name, dens, mass, ea, tk, val, en, tc = entry
        real_rows.append(
            {
                "name": name,
                "density": dens,
                "atomic_mass": mass,
                "electron_affinity": ea,
                "thermal_conductivity": tk,
                "valence": val,
                "electronegativity": en,
                "critical_temp": tc,
            }
        )
    df_real = pd.DataFrame(real_rows)

    # ── 계열별 합성 확장 (각 계열의 특성 범위를 기반으로 변이체 생성) ──
    families = [
        # (label, count, dens_range, mass_range, ea_range, tk_range, val, en_range, tc_range)
        ("Elem", 30, (2.5, 17.0), (25, 210), (7, 110), (5, 240), (2, 7), (1.4, 2.4), (0.3, 10)),
        ("A15", 40, (5.5, 9.5), (50, 110), (40, 90), (10, 40), (4, 5), (1.55, 1.80), (12, 25)),
        ("Cuprate", 80, (5.8, 8.8), (80, 160), (30, 60), (2, 8), (3, 3), (1.70, 2.05), (25, 140)),
        ("FeAs", 50, (4.5, 7.5), (60, 90), (50, 70), (8, 18), (3, 3), (1.65, 1.85), (6, 58)),
        ("MgB2-like", 20, (2.0, 4.5), (18, 35), (20, 40), (25, 60), (3, 3), (1.40, 1.70), (30, 45)),
        ("Chevrel", 25, (7.0, 10.0), (90, 130), (45, 65), (5, 12), (4, 4), (1.75, 1.95), (10, 18)),
        ("HeavyF", 20, (7.0, 20.0), (70, 210), (25, 50), (4, 12), (3, 4), (1.45, 1.75), (0.3, 3)),
        ("Hydride", 30, (2.5, 6.0), (15, 60), (45, 80), (12, 25), (2, 3), (1.40, 2.15), (150, 260)),
    ]

    synth_rows = []
    idx = 0
    for fam, count, dr, mr, ear, tkr, vr, enr, tcr in families:
        density = rng.uniform(*dr, count)
        mass = rng.uniform(*mr, count)
        ea = rng.uniform(*ear, count)
        tk = rng.uniform(*tkr, count)
        val = rng.integers(vr[0], vr[1] + 1, count).astype(float)
        en = rng.uniform(*enr, count)

        # Tc: 계열 범위 내에서 특성 상관 + 노이즈
        base_tc = rng.uniform(*tcr, count)
        tc_noise = rng.normal(0, (tcr[1] - tcr[0]) * 0.08, count)
        tc = np.clip(base_tc + tc_noise, tcr[0] * 0.5, tcr[1] * 1.1)

        for i in range(count):
            synth_rows.append(
                {
                    "name": f"{fam}-{idx:03d}",
                    "density": round(float(density[i]), 2),
                    "atomic_mass": round(float(mass[i]), 2),
                    "electron_affinity": round(float(ea[i]), 2),
                    "thermal_conductivity": round(float(tk[i]), 2),
                    "valence": int(val[i]),
                    "electronegativity": round(float(en[i]), 2),
                    "critical_temp": round(float(tc[i]), 2),
                }
            )
            idx += 1

    df_synth = pd.DataFrame(synth_rows)
    df = pd.concat([df_real, df_synth], ignore_index=True)
    df.to_csv(SUPERCON_PATH, index=False)
    return SUPERCON_PATH


def load_from_csv(path: str):
    """외부 CSV 파일에서 데이터 로드."""
    import pandas as pd
    return pd.read_csv(path)


if __name__ == "__main__":
    import pandas as pd

    path = generate()
    df = pd.read_excel(path)
    print(f"Sample data saved to {path}")
    print(f"  Total rows: {len(df)}")
    print(f"  Real superconductors: {len(REAL_SUPERCONDUCTORS)}")
    print(f"  Columns: {list(df.columns)}")
    print(df.head(15))

    sc_path = generate_supercon()
    df_sc = pd.read_csv(sc_path)
    print(f"\nSuperCon data saved to {sc_path}")
    print(f"  Total rows: {len(df_sc)}")
    print(f"  Compounds: {len(SUPERCON_COMPOUNDS)}")
