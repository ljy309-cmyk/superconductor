# 초전도 상태 판독 프로그램

def check_superconductivity():
    # 1. 임계값 설정 (예: 수은의 경우 Tc = 4.2K, B0 = 0.04T)
    T_c = 4.2  # 임계 온도 (Kelvin)
    B_0 = 0.04 # 0K에서의 임계 자기장 (Tesla)

    print(f"--- 초전도 상태 판독기 (기준: Tc={T_c}K, B0={B_0}T) ---")

    try:
        # 2. 사용자로부터 현재 상태 입력 받기
        current_T = float(input("현재 온도(K)를 입력하세요: "))
        current_B = float(input("현재 자기장(T)을 입력하세요: "))

        # 3. 온도 조건 먼저 확인
        if current_T >= T_c:
            print("결과: [일반 상태] 온도가 임계 온도를 넘었습니다.")
        else:
            # 4. 온도에 따른 임계 자기장(Bc) 계산 (응용 공식 적용)
            # 공식: Bc = B0 * (1 - (T/Tc)^2)
            critical_B_at_T = B_0 * (1 - (current_T / T_c)**2)

            print(f"현재 온도에서의 임계 자기장 한계치는 약 {critical_B_at_T:.4f}T 입니다.")

            # 5. 자기장 조건 확인
            if current_B < critical_B_at_T:
                print("결과: [초전도 상태] 저항이 0이며 마이스너 효과가 나타납니다!")
            else:
                print("결과: [일반 상태] 자기장이 임계치를 초과하여 초전도성이 파괴되었습니다.")

    except ValueError:
        print("오류: 숫자 형태로 입력해 주세요.")
