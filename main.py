# 초전도체 시뮬레이션 프로그램 - 메인 메뉴

from superconductor import check_superconductivity
from meissner import run_meissner_simulation

def show_menu():
    print("=" * 50)
    print("  초전도체(Superconductor) 시뮬레이션")
    print("=" * 50)
    print("  1. 초전도 상태 변화 판독기 (조건문 활용)")
    print("  2. 마이스너 효과 시뮬레이션 (반복문 & 리스트)")
    print("  3. (준비 중)")
    print("  4. (준비 중)")
    print("  0. 종료")
    print("=" * 50)

def main():
    while True:
        show_menu()
        choice = input("실행할 프로그램 번호를 선택하세요: ").strip()

        if choice == "1":
            print()
            check_superconductivity()
        elif choice == "2":
            print()
            run_meissner_simulation()
        elif choice in ("3", "4"):
            print("아직 준비 중인 프로그램입니다.")
        elif choice == "0":
            print("프로그램을 종료합니다.")
            break
        else:
            print("올바른 번호를 입력해 주세요. (0~4)")

        print()  # 메뉴 반복 전 빈 줄

if __name__ == "__main__":
    main()
