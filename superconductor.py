"""
초전도체 상태 변화 판독기 (Superconductor State Change Reader)

특정 온도(T)와 자기장(B) 값에 따라 물질이 '초전도 상태'인지
'일반 상태'인지 판별하는 프로그램.

임계 자기장 곡선 방정식:
    B_c(T) = B_0 * [1 - (T / T_c)^2]

- T_c: 임계 온도 (Critical Temperature) [K]
- B_0: 0K에서의 임계 자기장 (Critical Magnetic Field at 0K) [T]
- T  : 현재 온도 [K]
- B  : 현재 자기장 [T]
"""

# ──────────────────────────────────────────────
# 물질별 임계값 (단위: T_c [K], B_0 [T])
# ──────────────────────────────────────────────
MATERIALS = {
    "Pb":    {"name": "납 (Lead)",              "T_c": 7.19,  "B_0": 0.0803},
    "Nb":    {"name": "나이오븀 (Niobium)",      "T_c": 9.26,  "B_0": 0.1991},
    "Sn":    {"name": "주석 (Tin)",              "T_c": 3.72,  "B_0": 0.0305},
    "Al":    {"name": "알루미늄 (Aluminium)",     "T_c": 1.18,  "B_0": 0.0105},
    "Hg":    {"name": "수은 (Mercury)",           "T_c": 4.15,  "B_0": 0.0411},
}


def critical_magnetic_field(T, T_c, B_0):
    """임계 자기장 곡선: B_c(T) = B_0 * [1 - (T/T_c)^2]

    Args:
        T: 현재 온도 [K] (0 이상)
        T_c: 임계 온도 [K]
        B_0: 0K에서의 임계 자기장 [T]

    Returns:
        해당 온도에서의 임계 자기장 값 [T].
        T >= T_c 이면 0.0을 반환한다.
    """
    if T < 0:
        raise ValueError(f"온도는 0K 이상이어야 합니다. 입력값: {T}K")
    if T >= T_c:
        return 0.0
    return B_0 * (1 - (T / T_c) ** 2)


def determine_state(T, B, T_c, B_0):
    """현재 온도와 자기장으로 초전도 상태를 판별한다.

    Args:
        T: 현재 온도 [K]
        B: 현재 자기장 [T] (0 이상)
        T_c: 임계 온도 [K]
        B_0: 0K에서의 임계 자기장 [T]

    Returns:
        ("초전도 상태", B_c) 또는 ("일반 상태", B_c)
        B_c는 해당 온도에서의 임계 자기장 값이다.
    """
    if B < 0:
        raise ValueError(f"자기장은 0T 이상이어야 합니다. 입력값: {B}T")

    B_c = critical_magnetic_field(T, T_c, B_0)

    if T < T_c and B < B_c:
        state = "초전도 상태 (Superconducting)"
    else:
        state = "일반 상태 (Normal)"

    return state, B_c


def display_materials():
    """선택 가능한 물질 목록을 출력한다."""
    print("\n[ 물질 목록 ]")
    print("-" * 50)
    for symbol, info in MATERIALS.items():
        print(f"  {symbol:4s} | {info['name']:24s} | T_c={info['T_c']:.2f}K, B_0={info['B_0']:.4f}T")
    print("-" * 50)


def get_float_input(prompt):
    """숫자 입력을 받아 float으로 변환한다."""
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("  [오류] 올바른 숫자를 입력해 주세요.")


def main():
    print("=" * 50)
    print("  초전도체 상태 변화 판독기")
    print("  Superconductor State Change Reader")
    print("=" * 50)

    # 물질 선택
    display_materials()
    symbols = list(MATERIALS.keys())

    while True:
        choice = input(f"\n물질 기호를 입력하세요 ({', '.join(symbols)}): ").strip()
        if choice in MATERIALS:
            break
        print("  [오류] 목록에 있는 기호를 입력해 주세요.")

    material = MATERIALS[choice]
    T_c = material["T_c"]
    B_0 = material["B_0"]

    print(f"\n선택: {material['name']}")
    print(f"  임계 온도  T_c = {T_c} K")
    print(f"  임계 자기장 B_0 = {B_0} T")

    # 현재 조건 입력
    print("\n[ 현재 조건 입력 ]")
    T = get_float_input("  현재 온도 T (K): ")
    B = get_float_input("  현재 자기장 B (T): ")

    # 상태 판별
    try:
        state, B_c = determine_state(T, B, T_c, B_0)
    except ValueError as e:
        print(f"\n  [오류] {e}")
        return

    # 결과 출력
    print("\n" + "=" * 50)
    print("  [ 판정 결과 ]")
    print(f"  물질       : {material['name']}")
    print(f"  현재 온도   : {T} K")
    print(f"  현재 자기장  : {B} T")
    print(f"  임계 자기장  : {B_c:.6f} T  (이 온도에서)")
    print(f"  상태       : ★ {state} ★")
    print("=" * 50)

    # 판정 근거 설명
    print("\n[ 판정 근거 ]")
    if T >= T_c:
        print(f"  → 온도({T}K)가 임계 온도({T_c}K) 이상이므로 초전도 불가.")
    elif B >= B_c:
        print(f"  → 자기장({B}T)이 임계 자기장({B_c:.6f}T) 이상이므로 초전도 파괴.")
    else:
        print(f"  → 온도({T}K) < T_c({T_c}K) 이고,")
        print(f"    자기장({B}T) < B_c({B_c:.6f}T) 이므로 초전도 유지.")


if __name__ == "__main__":
    main()
