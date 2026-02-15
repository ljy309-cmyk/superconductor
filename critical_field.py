# 임계 자기장 시뮬레이션 — 체스 전략 스타일
# 학습 포인트: 2차원 배열, 조건문, 전략 탐색 알고리즘
# 온도(T)와 자기장(B)의 상(phase) 공간을 체스판처럼 표현하고,
# 초전도 상태를 유지하기에 가장 '유리한 수'를 찾아낸다.


# ── 핵심 물리 공식 ───────────────────────────────────────


# 지원하는 초전도체 물질 목록
MATERIALS = {
    "Hg":  {"T_c": 4.15,  "B_0": 0.041,  "이름": "수은"},
    "Pb":  {"T_c": 7.19,  "B_0": 0.080,  "이름": "납"},
    "Nb":  {"T_c": 9.26,  "B_0": 0.206,  "이름": "니오븀"},
    "NbTi": {"T_c": 10.0, "B_0": 15.0,   "이름": "니오븀-티타늄 합금"},
    "Nb3Sn": {"T_c": 18.3, "B_0": 30.0,  "이름": "니오븀주석"},
    "MgB2": {"T_c": 39.0, "B_0": 16.0,   "이름": "이붕소마그네슘"},
    "YBCO": {"T_c": 93.0, "B_0": 100.0,  "이름": "이트륨바륨구리산화물"},
}


def critical_field(T, T_c, B_0):
    """온도 T에서의 임계 자기장 B_c(T)를 계산한다.

    공식: B_c(T) = B_0 × [1 - (T / T_c)²]
    T >= T_c이면 0을 반환한다.

    Args:
        T: 현재 온도 (K)
        T_c: 임계 온도 (K)
        B_0: 0K에서의 임계 자기장 (T)

    Returns:
        B_c(T) (float, >= 0)
    """
    if T >= T_c:
        return 0.0
    return B_0 * (1 - (T / T_c) ** 2)


def check_state(T, B, T_c, B_0):
    """주어진 (T, B) 좌표에서 초전도 상태를 판별한다.

    Returns:
        1 (초전도 상태) 또는 0 (일반 상태)
    """
    if T < 0 or B < 0:
        return 0
    B_c = critical_field(T, T_c, B_0)
    if B < B_c:
        return 1
    return 0


# ── 체스판 생성 ──────────────────────────────────────────


def generate_phase_board(T_c, B_0, t_steps=10, b_steps=10):
    """온도-자기장 상(phase) 공간을 체스판 형태의 2D 배열로 생성한다.

    행(row) = 자기장 (위에서 아래로 감소), 열(col) = 온도 (왼쪽→오른쪽 증가)
    각 칸은 1(초전도) 또는 0(일반).

    Args:
        T_c: 임계 온도 (K)
        B_0: 0K에서의 임계 자기장 (T)
        t_steps: 온도 분할 수 (열 수)
        b_steps: 자기장 분할 수 (행 수)

    Returns:
        (board, t_values, b_values) 튜플
        board: 2D 리스트 [b_steps][t_steps], 값은 0 또는 1
        t_values: 온도 값 리스트 (왼→오른쪽 증가)
        b_values: 자기장 값 리스트 (위→아래 감소)
    """
    # 온도: 0 ~ T_c 범위를 t_steps 등분
    t_values = [T_c * i / t_steps for i in range(t_steps)]
    # 자기장: B_0 ~ 0 범위를 b_steps 등분 (위에서 아래로 감소)
    b_values = [B_0 * (b_steps - i) / b_steps for i in range(b_steps)]

    board = []
    for b in b_values:
        row = []
        for t in t_values:
            row.append(check_state(t, b, T_c, B_0))
        board.append(row)

    return board, t_values, b_values


# ── 체스판 출력 ──────────────────────────────────────────


def format_board(board, t_values, b_values, T_c, B_0):
    """체스판을 문자열로 포맷팅한다.

    Returns:
        포맷팅된 문자열 (여러 줄)
    """
    lines = []
    t_steps = len(t_values)
    b_steps = len(b_values)

    # 상단 헤더 (온도 축)
    header = "  B\\T  │"
    for t in t_values:
        header += f" {t:5.1f}"
    header += f"  (K)"
    lines.append(header)
    lines.append("  " + "─" * 6 + "┼" + "─" * (t_steps * 6 + 4))

    # 각 행 (자기장 레벨)
    for i, b in enumerate(b_values):
        row_str = f"  {b:5.3f}│"
        for j, t in enumerate(t_values):
            cell = board[i][j]
            if cell == 1:
                row_str += "   ■ "  # 초전도 (체스 말 있음)
            else:
                row_str += "   · "  # 일반 (빈 칸)
        lines.append(row_str)

    lines.append("  " + "─" * 6 + "┴" + "─" * (t_steps * 6 + 4))
    lines.append(f"  (T)     ■ = 초전도(1)    · = 일반(0)")

    return "\n".join(lines)


def show_board(board, t_values, b_values, T_c, B_0):
    """체스판을 화면에 출력한다."""
    formatted = format_board(board, t_values, b_values, T_c, B_0)
    print(formatted)


# ── 전략 분석 ────────────────────────────────────────────


def count_states(board):
    """보드에서 초전도(1) 칸과 일반(0) 칸의 수를 센다.

    Returns:
        (superconducting_count, normal_count) 튜플
    """
    sc = 0
    nm = 0
    for row in board:
        for cell in row:
            if cell == 1:
                sc += 1
            else:
                nm += 1
    return sc, nm


def find_boundary(board, t_values, b_values):
    """초전도 영역과 일반 영역의 경계선 좌표를 찾는다.

    각 온도 열에서 초전도 상태인 가장 높은 자기장 값을 찾는다.
    (체스에서 '전선(front line)'에 해당)

    Returns:
        [(T, B_경계)] 리스트 (경계가 존재하는 열만 포함)
    """
    boundary = []
    t_steps = len(t_values)
    b_steps = len(b_values)

    for j in range(t_steps):
        # 위에서 아래로 탐색 (높은 B → 낮은 B)
        # 처음으로 1이 나오는 행 = 경계
        found = False
        for i in range(b_steps):
            if board[i][j] == 1:
                boundary.append((t_values[j], b_values[i]))
                found = True
                break
        # 해당 열에 초전도 칸이 없으면 건너뜀

    return boundary


def find_best_move(board, t_values, b_values, T_c, B_0):
    """초전도 상태를 유지하면서 경계로부터 가장 먼 '최적의 수'를 찾는다.

    마진 = min(B_c(T) - B, T_c - T)을 최대화하는 (T, B) 좌표.
    (체스에서 가장 안전한 포지션)

    Returns:
        {"T": float, "B": float, "마진_T": float, "마진_B": float,
         "안전도": float} 딕셔너리. 초전도 칸이 없으면 None.
    """
    best = None
    best_safety = -1

    for i, b in enumerate(b_values):
        for j, t in enumerate(t_values):
            if board[i][j] == 1:
                B_c = critical_field(t, T_c, B_0)
                margin_b = B_c - b   # 자기장 여유분
                margin_t = T_c - t   # 온도 여유분
                # 안전도: 두 마진의 기하평균 (둘 다 충분해야 높음)
                safety = (margin_b * margin_t) ** 0.5
                if safety > best_safety:
                    best_safety = safety
                    best = {
                        "T": t,
                        "B": b,
                        "마진_T": margin_t,
                        "마진_B": margin_b,
                        "안전도": safety,
                    }
    return best


def find_critical_moves(board, t_values, b_values):
    """경계 바로 안쪽의 '위험한 수'를 찾는다.

    인접 칸에 일반(0)이 있는 초전도(1) 칸 = 위험 포지션.
    (체스에서 상대 말에 위협받는 포지션)

    Returns:
        [(T, B)] 리스트 (위험도 높은 칸)
    """
    critical = []
    b_steps = len(b_values)
    t_steps = len(t_values)

    for i in range(b_steps):
        for j in range(t_steps):
            if board[i][j] == 1:
                # 상하좌우 인접 칸 확인
                neighbors = []
                if i > 0:
                    neighbors.append(board[i - 1][j])
                if i < b_steps - 1:
                    neighbors.append(board[i + 1][j])
                if j > 0:
                    neighbors.append(board[i][j - 1])
                if j < t_steps - 1:
                    neighbors.append(board[i][j + 1])
                # 인접 칸 중 일반(0)이 있으면 위험
                if 0 in neighbors:
                    critical.append((t_values[j], b_values[i]))

    return critical


# ── 전략 분석 출력 ───────────────────────────────────────


def show_strategy_analysis(board, t_values, b_values, T_c, B_0):
    """체스판 전략 분석 결과를 출력한다."""
    sc, nm = count_states(board)
    total = sc + nm

    print(f"\n[ 전략 분석 — 상(Phase) 공간 평가 ]")
    print(f"  총 칸 수: {total}  (초전도 영역: {sc}칸, 일반 영역: {nm}칸)")
    if total > 0:
        print(f"  초전도 점유율: {sc / total * 100:.1f}%")

    # 최적의 수
    best = find_best_move(board, t_values, b_values, T_c, B_0)
    if best:
        print(f"\n  ★ 최적의 수 (가장 안전한 포지션)")
        print(f"    온도 T = {best['T']:.2f} K,  자기장 B = {best['B']:.4f} T")
        print(f"    온도 여유: {best['마진_T']:.2f} K  (Tc까지 {best['마진_T']:.2f} K 남음)")
        print(f"    자기장 여유: {best['마진_B']:.4f} T  (Bc까지 {best['마진_B']:.4f} T 남음)")
        print(f"    안전도 점수: {best['안전도']:.4f}")
    else:
        print("\n  ※ 이 보드에 초전도 영역이 없습니다.")

    # 경계선 (전선)
    boundary = find_boundary(board, t_values, b_values)
    if boundary:
        print(f"\n  ─ 경계선 (전선 위치) ─")
        for t, b in boundary:
            print(f"    T = {t:5.2f} K  →  Bc 경계 ≈ {b:.4f} T")

    # 위험한 수
    critical = find_critical_moves(board, t_values, b_values)
    if critical:
        print(f"\n  ⚠ 위험한 수 ({len(critical)}개 — 경계 인접 칸)")
        shown = critical[:5]
        for t, b in shown:
            print(f"    T = {t:5.2f} K, B = {b:.4f} T")
        if len(critical) > 5:
            print(f"    ... 외 {len(critical) - 5}개")


# ── 단일 좌표 판별 ───────────────────────────────────────


def show_single_check(T_c, B_0):
    """사용자가 입력한 단일 (T, B) 좌표의 상태를 출력한다."""
    try:
        current_T = float(input("  현재 온도(K): "))
        current_B = float(input("  현재 자기장(T): "))
    except ValueError:
        print("  오류: 숫자를 입력해 주세요.")
        return

    state = check_state(current_T, current_B, T_c, B_0)
    B_c = critical_field(current_T, T_c, B_0)

    print(f"\n  좌표: T = {current_T:.2f} K, B = {current_B:.4f} T")
    print(f"  해당 온도의 임계 자기장: Bc = {B_c:.4f} T")
    if state == 1:
        margin_b = B_c - current_B
        margin_t = T_c - current_T
        print(f"  판정: [1] 초전도 상태")
        print(f"  온도 여유: {margin_t:.2f} K,  자기장 여유: {margin_b:.4f} T")
    else:
        print(f"  판정: [0] 일반 상태")
        if current_T >= T_c:
            print(f"  원인: 온도가 Tc({T_c} K) 이상입니다.")
        else:
            print(f"  원인: 자기장이 Bc({B_c:.4f} T) 이상입니다.")


# ── 대화형 실행 ──────────────────────────────────────────


def run_critical_field_simulation():
    """임계 자기장 체스 전략 시뮬레이션 (대화형)."""
    print("--- 임계 자기장 시뮬레이션 (체스 전략) ---")
    print("온도(T)와 자기장(B)의 상 공간을 체스판처럼 분석합니다.\n")

    # 1. 물질 선택
    print("[ 물질 선택 ]")
    mat_keys = list(MATERIALS.keys())
    for i, key in enumerate(mat_keys, 1):
        m = MATERIALS[key]
        print(f"  {i}. {key} ({m['이름']})  — Tc={m['T_c']}K, B0={m['B_0']}T")
    print(f"  0. 직접 입력")

    mat_choice = input("번호 (기본값 3): ").strip() or "3"

    if mat_choice == "0":
        try:
            T_c = float(input("  임계 온도 Tc (K): "))
            B_0 = float(input("  임계 자기장 B0 (T): "))
            if T_c <= 0 or B_0 <= 0:
                print("  오류: 양수를 입력해 주세요.")
                return
        except ValueError:
            print("  오류: 숫자를 입력해 주세요.")
            return
        mat_name = "사용자 정의"
    else:
        idx = int(mat_choice) - 1 if mat_choice.isdigit() else 2
        if 0 <= idx < len(mat_keys):
            key = mat_keys[idx]
            T_c = MATERIALS[key]["T_c"]
            B_0 = MATERIALS[key]["B_0"]
            mat_name = f"{key} ({MATERIALS[key]['이름']})"
        else:
            key = "Nb"
            T_c = MATERIALS[key]["T_c"]
            B_0 = MATERIALS[key]["B_0"]
            mat_name = f"{key} ({MATERIALS[key]['이름']})"

    print(f"\n  선택된 물질: {mat_name}")
    print(f"  Tc = {T_c} K, B0 = {B_0} T\n")

    # 2. 보드 크기
    size_input = input("보드 크기 (기본값 10): ").strip() or "10"
    try:
        board_size = int(size_input)
        if board_size < 3:
            board_size = 3
        elif board_size > 20:
            board_size = 20
    except ValueError:
        board_size = 10

    # 3. 보드 생성 및 출력
    board, t_values, b_values = generate_phase_board(T_c, B_0, board_size, board_size)

    print(f"\n[ 상(Phase) 공간 보드 — {board_size}×{board_size} ]")
    show_board(board, t_values, b_values, T_c, B_0)

    # 4. 전략 분석
    show_strategy_analysis(board, t_values, b_values, T_c, B_0)

    # 5. 세부 메뉴
    while True:
        print("\n[ 추가 분석 ]")
        print("  1. 특정 좌표 판별 (0/1)")
        print("  2. 보드 다시 보기")
        print("  3. 보드 크기 변경")
        print("  4. 물질 변경")
        print("  0. 메인 메뉴로 돌아가기")

        choice = input("번호: ").strip()

        if choice == "1":
            show_single_check(T_c, B_0)

        elif choice == "2":
            print(f"\n[ 상(Phase) 공간 보드 — {board_size}×{board_size} ]")
            show_board(board, t_values, b_values, T_c, B_0)
            show_strategy_analysis(board, t_values, b_values, T_c, B_0)

        elif choice == "3":
            new_size = input("새 보드 크기 (3~20): ").strip()
            try:
                board_size = max(3, min(20, int(new_size)))
            except ValueError:
                board_size = 10
            board, t_values, b_values = generate_phase_board(
                T_c, B_0, board_size, board_size
            )
            print(f"\n[ 상(Phase) 공간 보드 — {board_size}×{board_size} ]")
            show_board(board, t_values, b_values, T_c, B_0)
            show_strategy_analysis(board, t_values, b_values, T_c, B_0)

        elif choice == "4":
            print("\n[ 물질 선택 ]")
            for i, key in enumerate(mat_keys, 1):
                m = MATERIALS[key]
                print(f"  {i}. {key} ({m['이름']})")
            new_mat = input("번호: ").strip()
            idx = int(new_mat) - 1 if new_mat.isdigit() else -1
            if 0 <= idx < len(mat_keys):
                key = mat_keys[idx]
                T_c = MATERIALS[key]["T_c"]
                B_0 = MATERIALS[key]["B_0"]
                mat_name = f"{key} ({MATERIALS[key]['이름']})"
                print(f"  → {mat_name} (Tc={T_c}K, B0={B_0}T)")
                board, t_values, b_values = generate_phase_board(
                    T_c, B_0, board_size, board_size
                )
                print(f"\n[ 상(Phase) 공간 보드 — {board_size}×{board_size} ]")
                show_board(board, t_values, b_values, T_c, B_0)
                show_strategy_analysis(board, t_values, b_values, T_c, B_0)
            else:
                print("  올바른 번호를 입력해 주세요.")

        elif choice == "0":
            break
        else:
            print("올바른 번호를 입력해 주세요. (0~4)")
