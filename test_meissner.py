"""마이스너 효과 시뮬레이션 테스트."""

import numpy as np
import pytest
import matplotlib
matplotlib.use("Agg")  # GUI 없이 테스트
import matplotlib.pyplot as plt

from meissner import create_grid, compute_field_with_meissner, plot_meissner, run_meissner_simulation


# ── 격자 생성 테스트 ─────────────────────────────────────


class TestCreateGrid:
    """create_grid() 함수 테스트."""

    def test_grid_shape(self):
        """n_points에 맞는 크기의 격자가 생성된다."""
        X, Y = create_grid((-2, 2), (-2, 2), 10)
        assert X.shape == (10, 10)
        assert Y.shape == (10, 10)

    def test_grid_range(self):
        """격자가 지정된 범위를 커버한다."""
        X, Y = create_grid((-3, 3), (-5, 5), 20)
        assert X.min() == pytest.approx(-3)
        assert X.max() == pytest.approx(3)
        assert Y.min() == pytest.approx(-5)
        assert Y.max() == pytest.approx(5)

    def test_grid_symmetry(self):
        """대칭 범위에서 격자 중심이 0에 가깝다."""
        X, Y = create_grid((-2, 2), (-2, 2), 21)  # 홀수로 정확히 0 포함
        # 중앙 행/열에 0이 포함
        center_idx = 10
        assert X[center_idx, center_idx] == pytest.approx(0.0)
        assert Y[center_idx, center_idx] == pytest.approx(0.0)


# ── 자기장 계산 테스트 ───────────────────────────────────


class TestComputeField:
    """compute_field_with_meissner() 함수 테스트."""

    def setup_method(self):
        """공통 설정."""
        self.sc_center = (0.0, 0.0)
        self.sc_radius = 1.0
        self.B_ext = (0.0, 1.0)  # +y 방향 외부 자기장
        self.X, self.Y = create_grid((-3, 3), (-3, 3), 25)

    def test_inside_field_is_zero(self):
        """초전도체 내부의 자기장은 0이다 (마이스너 효과 핵심)."""
        Bx, By, inside = compute_field_with_meissner(
            self.X, self.Y, self.sc_center, self.sc_radius, self.B_ext
        )
        # 내부 영역의 모든 자기장 성분이 0
        assert np.allclose(Bx[inside], 0.0)
        assert np.allclose(By[inside], 0.0)

    def test_inside_mask_correct(self):
        """내부 마스크가 반지름 기준으로 올바르게 생성된다."""
        _, _, inside = compute_field_with_meissner(
            self.X, self.Y, self.sc_center, self.sc_radius, self.B_ext
        )
        # 원점은 반드시 내부
        r = np.sqrt(self.X**2 + self.Y**2)
        for i in range(self.X.shape[0]):
            for j in range(self.X.shape[1]):
                if r[i, j] <= self.sc_radius:
                    assert inside[i, j], f"({self.X[i,j]:.2f}, {self.Y[i,j]:.2f})은 내부여야 함"

    def test_far_field_approaches_external(self):
        """초전도체에서 멀리 떨어진 곳은 외부 자기장에 수렴한다."""
        X, Y = create_grid((-20, 20), (-20, 20), 15)
        Bx, By, _ = compute_field_with_meissner(
            X, Y, self.sc_center, self.sc_radius, self.B_ext
        )
        # 가장자리 (r >> R) 에서는 외부 자기장과 거의 같아야 한다
        far_mask = (X**2 + Y**2) > 100  # r > 10
        assert np.allclose(Bx[far_mask], 0.0, atol=0.01)
        assert np.allclose(By[far_mask], 1.0, atol=0.01)

    def test_output_shapes_match_input(self):
        """출력 배열이 입력 격자와 같은 크기이다."""
        Bx, By, inside = compute_field_with_meissner(
            self.X, self.Y, self.sc_center, self.sc_radius, self.B_ext
        )
        assert Bx.shape == self.X.shape
        assert By.shape == self.Y.shape
        assert inside.shape == self.X.shape

    def test_field_deflection_near_surface(self):
        """초전도체 표면 근처에서 자기장이 휘어진다 (Bx ≠ 0)."""
        # 대각선 위치에서 자기장의 x성분이 생겨야 한다 (비대칭 위치)
        X = np.array([[self.sc_radius * 1.3]])
        Y = np.array([[self.sc_radius * 0.5]])
        Bx, By, _ = compute_field_with_meissner(
            X, Y, self.sc_center, self.sc_radius, self.B_ext
        )
        # 대각선 위치에서는 쌍극자 효과로 Bx 성분이 0이 아니다
        assert abs(Bx[0, 0]) > 0.01

    def test_different_radius(self):
        """반지름이 커지면 내부 영역도 커진다."""
        big_radius = 2.0
        _, _, inside_small = compute_field_with_meissner(
            self.X, self.Y, self.sc_center, 1.0, self.B_ext
        )
        _, _, inside_big = compute_field_with_meissner(
            self.X, self.Y, self.sc_center, big_radius, self.B_ext
        )
        assert inside_big.sum() > inside_small.sum()


# ── 시각화 함수 테스트 ───────────────────────────────────


class TestPlotMeissner:
    """plot_meissner() 시각화 테스트."""

    def test_returns_fig_and_ax(self):
        """fig, ax 객체를 반환한다."""
        fig, ax = plot_meissner(
            sc_radius=1.0, n_grid=10,
            B_ext_direction=(0.0, 1.0), save_path=None
        )
        assert fig is not None
        assert ax is not None
        plt.close(fig)

    def test_save_to_file(self, tmp_path):
        """파일로 저장할 수 있다."""
        save_path = str(tmp_path / "test_meissner.png")
        fig, _ = plot_meissner(
            sc_radius=1.0, n_grid=10,
            B_ext_direction=(0.0, 1.0), save_path=save_path
        )
        import os
        assert os.path.exists(save_path)
        plt.close(fig)


# ── 대화형 실행 테스트 ───────────────────────────────────


class TestRunSimulation:
    """run_meissner_simulation() 대화형 실행 테스트."""

    def test_default_inputs(self, monkeypatch, capsys, tmp_path):
        """기본값 입력으로 정상 실행된다."""
        monkeypatch.chdir(tmp_path)
        inputs = iter(["1.0", "10", "1.0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_meissner_simulation()
        output = capsys.readouterr().out
        assert "시뮬레이션 완료" in output

    def test_empty_inputs_use_defaults(self, monkeypatch, capsys, tmp_path):
        """빈 입력 시 기본값이 사용된다."""
        monkeypatch.chdir(tmp_path)
        inputs = iter(["", "", ""])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_meissner_simulation()
        output = capsys.readouterr().out
        assert "시뮬레이션 완료" in output

    def test_negative_radius_error(self, monkeypatch, capsys):
        """음수 반지름 → 오류 메시지."""
        inputs = iter(["-1", "10", "1.0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_meissner_simulation()
        output = capsys.readouterr().out
        assert "양수" in output

    def test_small_grid_error(self, monkeypatch, capsys):
        """격자 밀도 5 미만 → 오류 메시지."""
        inputs = iter(["1.0", "3", "1.0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_meissner_simulation()
        output = capsys.readouterr().out
        assert "5 이상" in output

    def test_non_numeric_input(self, monkeypatch, capsys):
        """문자 입력 → 오류 메시지."""
        inputs = iter(["abc", "10", "1.0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_meissner_simulation()
        output = capsys.readouterr().out
        assert "오류" in output
