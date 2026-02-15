# 마이스너 효과(자기장 배척) 시뮬레이션
# 학습 포인트: 반복문(for), 리스트(list), matplotlib 시각화

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.colors as mcolors


def create_grid(x_range, y_range, n_points):
    """격자(Grid) 좌표를 생성한다.

    Args:
        x_range: (x_min, x_max) 튜플
        y_range: (y_min, y_max) 튜플
        n_points: 한 축당 격자점 개수

    Returns:
        X, Y 메쉬그리드 (numpy 2D 배열)
    """
    x = np.linspace(x_range[0], x_range[1], n_points)
    y = np.linspace(y_range[0], y_range[1], n_points)
    X, Y = np.meshgrid(x, y)
    return X, Y


def compute_field_with_meissner(X, Y, sc_center, sc_radius, B_ext_direction):
    """마이스너 효과를 반영한 자기장 벡터를 계산한다.

    초전도체를 완전 반자성체(자기 쌍극자)로 모델링한다.
    외부 자기장 B_ext에 대해 초전도체 내부의 자기장은 0이 되고,
    외부에서는 쌍극자 필드가 더해져 자기장이 휘어진다.

    Args:
        X, Y: 격자 좌표 (2D 배열)
        sc_center: 초전도체 중심 (cx, cy)
        sc_radius: 초전도체 반지름
        B_ext_direction: 외부 자기장 방향 (Bx, By)

    Returns:
        Bx, By: 자기장의 x, y 성분 (2D 배열)
        inside_mask: 초전도체 내부 영역 마스크 (bool 2D 배열)
    """
    cx, cy = sc_center
    Bx_ext, By_ext = B_ext_direction

    # 1. 각 격자점에서 초전도체 중심까지의 상대 좌표 계산
    dx = X - cx
    dy = Y - cy
    r_squared = dx**2 + dy**2
    r = np.sqrt(r_squared)

    # 2. 초전도체 내부/외부 판별
    inside_mask = r <= sc_radius

    # 3. 외부 자기장으로 초기화
    Bx = np.full_like(X, Bx_ext, dtype=float)
    By = np.full_like(Y, By_ext, dtype=float)

    # 4. 초전도체 외부: 자기 쌍극자 필드 추가 (자기장이 휘어지는 효과)
    # 쌍극자 모멘트: m = -B_ext * R^2 (2D 원통 모델)
    outside_mask = ~inside_mask
    r_sq_safe = np.where(outside_mask, r_squared, 1.0)  # 0 나누기 방지

    R2 = sc_radius ** 2

    # 쌍극자 필드 성분 (2D)
    # Bx_dip = R^2 * (2*dx*dy*By_ext + (dx^2 - dy^2)*Bx_ext) / r^4
    # By_dip = R^2 * (2*dx*dy*Bx_ext - (dx^2 - dy^2)*By_ext) / r^4
    # 간소화: 외부 자기장이 y방향(위쪽)일 때의 쌍극자 응답
    cos_theta = dx / np.sqrt(r_sq_safe)
    sin_theta = dy / np.sqrt(r_sq_safe)
    cos2_theta = cos_theta**2 - sin_theta**2
    sin2_theta = 2 * cos_theta * sin_theta

    factor = R2 / r_sq_safe

    # 쌍극자 보정 (외부만 적용)
    Bx_dipole = factor * (Bx_ext * cos2_theta + By_ext * sin2_theta)
    By_dipole = factor * (Bx_ext * sin2_theta - By_ext * cos2_theta)

    Bx = np.where(outside_mask, Bx - Bx_dipole, 0.0)
    By = np.where(outside_mask, By - By_dipole, 0.0)

    return Bx, By, inside_mask


# 사용 가능한 컬러맵 목록
COLORMAPS = {
    "1": {"name": "plasma",   "label": "plasma (보라→노랑, 세기 차이가 뚜렷함)"},
    "2": {"name": "hot",      "label": "hot (검정→빨강→노랑→흰색, 열 분포 느낌)"},
    "3": {"name": "coolwarm", "label": "coolwarm (파랑→빨강, 약↔강 대비)"},
    "4": {"name": "viridis",  "label": "viridis (보라→초록→노랑, 기본 과학용)"},
}


def plot_meissner(sc_radius, n_grid, B_ext_direction, save_path=None, cmap_name="plasma"):
    """마이스너 효과 시뮬레이션 결과를 시각화한다.

    Args:
        sc_radius: 초전도체 반지름
        n_grid: 격자점 개수 (한 축당)
        B_ext_direction: 외부 자기장 방향 (Bx, By)
        save_path: 저장 경로 (None이면 화면에 표시)
        cmap_name: matplotlib 컬러맵 이름 (기본값 "plasma")

    Returns:
        fig, ax: matplotlib Figure와 Axes 객체
    """
    # 1. 격자 생성
    margin = sc_radius * 2.5
    sc_center = (0.0, 0.0)
    X, Y = create_grid((-margin, margin), (-margin, margin), n_grid)

    # 2. 자기장 계산
    Bx, By, inside_mask = compute_field_with_meissner(
        X, Y, sc_center, sc_radius, B_ext_direction
    )

    # 3. 시각화
    fig, ax = plt.subplots(1, 1, figsize=(8, 8))

    # 자기장 크기 계산 (색상용)
    B_magnitude = np.sqrt(Bx**2 + By**2)

    # 색상 정규화 — 세기 차이가 뚜렷하게 보이도록 범위를 설정
    B_ext_magnitude = np.sqrt(B_ext_direction[0]**2 + B_ext_direction[1]**2)
    norm = mcolors.Normalize(vmin=0, vmax=B_ext_magnitude * 1.5)

    # 화살표(quiver) 그리기 — 초전도체 내부는 이미 0이므로 화살표 없음
    quiver = ax.quiver(
        X, Y, Bx, By,
        B_magnitude,
        cmap=cmap_name,
        norm=norm,
        scale=25,
        width=0.004,
        headwidth=3,
        headlength=4,
    )

    # 초전도체 영역 (원) 표시
    circle = patches.Circle(
        sc_center, sc_radius,
        fill=True,
        facecolor="#4FC3F7",
        edgecolor="#0277BD",
        linewidth=2.5,
        alpha=0.6,
        label="초전도체 영역",
    )
    ax.add_patch(circle)

    # 컬러바
    cbar = plt.colorbar(quiver, ax=ax, shrink=0.8)
    cbar.set_label("자기장 크기 |B|", fontsize=11)

    # 제목 및 축 설정
    ax.set_title(
        f"마이스너 효과 시뮬레이션\n(초전도체 내부: B = 0, 컬러맵: {cmap_name})",
        fontsize=14,
    )
    ax.set_xlabel("x", fontsize=12)
    ax.set_ylabel("y", fontsize=12)
    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=10)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)
        print(f"그래프가 '{save_path}'에 저장되었습니다.")
    else:
        plt.show()

    return fig, ax


def run_meissner_simulation():
    """마이스너 효과 시뮬레이션 실행 (대화형)."""
    print("--- 마이스너 효과(자기장 배척) 시뮬레이션 ---")
    print("초전도체 내부에서 자기장이 배척되는 현상을 시각화합니다.\n")

    try:
        # 사용자 입력
        sc_radius = float(input("초전도체 반지름을 입력하세요 (기본값 1.0): ") or "1.0")
        n_grid = int(input("격자 밀도를 입력하세요 (기본값 20): ") or "20")
        B_strength = float(input("외부 자기장 세기를 입력하세요 (기본값 1.0): ") or "1.0")

        if sc_radius <= 0:
            print("오류: 반지름은 양수여야 합니다.")
            return
        if n_grid < 5:
            print("오류: 격자 밀도는 5 이상이어야 합니다.")
            return

        # 컬러맵 선택
        print("\n[ 컬러맵 선택 — 자기장 세기 표현 방식 ]")
        for key, info in COLORMAPS.items():
            print(f"  {key}. {info['label']}")
        cmap_choice = input("컬러맵 번호를 선택하세요 (기본값 1): ").strip() or "1"

        if cmap_choice in COLORMAPS:
            cmap_name = COLORMAPS[cmap_choice]["name"]
        else:
            print(f"알 수 없는 선택 '{cmap_choice}', 기본값(plasma)을 사용합니다.")
            cmap_name = "plasma"

        print(f"\n설정: 반지름={sc_radius}, 격자={n_grid}x{n_grid}, "
              f"외부 자기장 세기={B_strength}, 컬러맵={cmap_name}")
        print("그래프를 생성합니다...\n")

        # 외부 자기장: 위쪽(+y) 방향
        B_ext_direction = (0.0, B_strength)

        plot_meissner(
            sc_radius=sc_radius,
            n_grid=n_grid,
            B_ext_direction=B_ext_direction,
            save_path="meissner_result.png",
            cmap_name=cmap_name,
        )

        print("시뮬레이션 완료!")

    except ValueError:
        print("오류: 숫자 형태로 입력해 주세요.")
