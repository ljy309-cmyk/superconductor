"""초전도체 샘플 데이터 생성 → Excel 파일로 저장.

특성 컬럼: density, atomic_mass, electron_affinity, thermal_conductivity, valence
타깃: critical_temp (Tc, K)
"""

import os
import random

import pandas as pd
import numpy as np

SAMPLE_SIZE = 200
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "superconductor_data.xlsx")


def generate():
    """샘플 데이터를 생성하여 Excel로 저장."""
    rng = np.random.default_rng(42)

    density = rng.uniform(2.0, 12.0, SAMPLE_SIZE)
    atomic_mass = rng.uniform(20.0, 210.0, SAMPLE_SIZE)
    electron_affinity = rng.uniform(10.0, 200.0, SAMPLE_SIZE)
    thermal_conductivity = rng.uniform(0.1, 500.0, SAMPLE_SIZE)
    valence = rng.integers(1, 8, SAMPLE_SIZE).astype(float)

    # Tc 합성 (비선형 관계 + 노이즈)
    critical_temp = (
        0.5 * density
        + 0.15 * electron_affinity
        - 0.02 * atomic_mass
        + 0.005 * thermal_conductivity
        + 3.0 * valence
        + rng.normal(0, 5, SAMPLE_SIZE)
    )
    critical_temp = np.clip(critical_temp, 0.5, 180.0)

    df = pd.DataFrame({
        "density": np.round(density, 2),
        "atomic_mass": np.round(atomic_mass, 2),
        "electron_affinity": np.round(electron_affinity, 2),
        "thermal_conductivity": np.round(thermal_conductivity, 2),
        "valence": valence.astype(int),
        "critical_temp": np.round(critical_temp, 2),
    })

    df.to_excel(OUTPUT_PATH, index=False)
    return OUTPUT_PATH


if __name__ == "__main__":
    path = generate()
    print(f"Sample data saved to {path}")
