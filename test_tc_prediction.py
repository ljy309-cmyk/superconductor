"""임계 온도 예측 데이터 분석 테스트."""

import os
import numpy as np
import pandas as pd
import pytest
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from tc_prediction import (
    load_dataset, load_csv, get_numeric_columns,
    show_basic_stats, show_data_table, show_type_summary,
    compute_correlation, linear_model, fit_regression,
    plot_analysis, run_tc_analysis,
    SUPERCONDUCTOR_DATA, COLUMNS,
)


# ── 데이터셋 로드 테스트 ─────────────────────────────────


class TestLoadDataset:
    """load_dataset() 함수 테스트."""

    def test_returns_dataframe(self):
        """pandas DataFrame을 반환한다."""
        df = load_dataset()
        assert isinstance(df, pd.DataFrame)

    def test_correct_columns(self):
        """올바른 열 이름을 가진다."""
        df = load_dataset()
        assert list(df.columns) == COLUMNS

    def test_correct_row_count(self):
        """SUPERCONDUCTOR_DATA와 같은 행 수를 가진다."""
        df = load_dataset()
        assert len(df) == len(SUPERCONDUCTOR_DATA)

    def test_tc_all_positive(self):
        """모든 Tc 값이 양수이다."""
        df = load_dataset()
        assert (df["Tc"] > 0).all()

    def test_contains_known_materials(self):
        """알려진 물질이 포함되어 있다."""
        df = load_dataset()
        names = df["물질명"].tolist()
        assert "Nb" in names
        assert "Pb" in names
        assert "MgB2" in names

    def test_types_are_valid(self):
        """유형이 정해진 범위 내에 있다."""
        df = load_dataset()
        valid_types = {"원소", "화합물", "합금", "고온", "수소화물"}
        assert set(df["유형"].unique()).issubset(valid_types)


# ── CSV 로드 테스트 ──────────────────────────────────────


CSV_TEST_PATH = os.path.join(os.path.dirname(__file__), "test_superconductor_data.csv")


class TestLoadCsv:
    """load_csv() 함수 테스트."""

    def test_loads_csv_file(self):
        """CSV 파일을 정상적으로 로드한다."""
        df = load_csv(CSV_TEST_PATH)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 20

    def test_csv_has_required_columns(self):
        """필수 열(물질명, 유형, Tc)이 포함되어 있다."""
        df = load_csv(CSV_TEST_PATH)
        assert "물질명" in df.columns
        assert "유형" in df.columns
        assert "Tc" in df.columns

    def test_csv_has_extended_columns(self):
        """확장 열(원소수, 열전도도, 전자비열계수 등)이 포함되어 있다."""
        df = load_csv(CSV_TEST_PATH)
        assert "원소수" in df.columns
        assert "열전도도" in df.columns
        assert "전자비열계수" in df.columns

    def test_csv_tc_all_positive(self):
        """CSV의 모든 Tc 값이 양수이다."""
        df = load_csv(CSV_TEST_PATH)
        assert (df["Tc"] > 0).all()

    def test_csv_contains_known_materials(self):
        """CSV에 알려진 물질이 포함되어 있다."""
        df = load_csv(CSV_TEST_PATH)
        names = df["물질명"].tolist()
        assert "Nb" in names
        assert "MgB2" in names

    def test_file_not_found_raises(self):
        """존재하지 않는 파일 → FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_csv("nonexistent_file.csv")

    def test_missing_column_raises(self, tmp_path):
        """필수 열이 없는 CSV → ValueError."""
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("이름,값\nA,1\n")
        with pytest.raises(ValueError, match="필수 열"):
            load_csv(str(bad_csv))

    def test_csv_types_are_valid(self):
        """CSV의 유형이 정해진 범위 내에 있다."""
        df = load_csv(CSV_TEST_PATH)
        valid_types = {"원소", "화합물", "합금", "고온", "수소화물"}
        assert set(df["유형"].unique()).issubset(valid_types)


# ── get_numeric_columns 테스트 ────────────────────────────


class TestGetNumericColumns:
    """get_numeric_columns() 함수 테스트."""

    def test_builtin_dataset(self):
        """내장 데이터셋의 수치 열은 3개이다."""
        df = load_dataset()
        cols = get_numeric_columns(df)
        assert len(cols) == 3
        assert "Tc" not in cols

    def test_csv_dataset(self):
        """CSV 데이터셋의 수치 열은 6개이다."""
        df = load_csv(CSV_TEST_PATH)
        cols = get_numeric_columns(df)
        assert len(cols) == 6
        assert "Tc" not in cols
        assert "평균원자질량" in cols
        assert "열전도도" in cols


# ── 통계 출력 테스트 ─────────────────────────────────────


class TestBasicStats:
    """show_basic_stats() 함수 테스트."""

    def test_prints_stats(self, capsys):
        """기본 통계가 출력된다."""
        df = load_dataset()
        show_basic_stats(df)
        output = capsys.readouterr().out
        assert "총 물질 수" in output
        assert "최솟값" in output
        assert "최댓값" in output
        assert "평균값" in output

    def test_csv_stats_with_quantiles(self, capsys):
        """대규모 데이터셋(100개 초과)에서 분위수가 출력된다."""
        # 200행짜리 가짜 데이터
        df = pd.DataFrame({
            "물질명": [f"M{i}" for i in range(200)],
            "유형": ["원소"] * 200,
            "평균원자질량": np.random.uniform(10, 200, 200),
            "밀도": np.random.uniform(1, 15, 200),
            "Tc": np.random.uniform(0.1, 100, 200),
        })
        show_basic_stats(df)
        output = capsys.readouterr().out
        assert "분위수" in output
        assert "25.0%" in output
        assert "99.0%" in output


class TestDataTable:
    """show_data_table() 함수 테스트."""

    def test_prints_all_materials(self, capsys):
        """모든 물질이 출력된다 (소규모 데이터)."""
        df = load_dataset()
        show_data_table(df)
        output = capsys.readouterr().out
        assert "Nb" in output
        assert "Pb" in output
        assert "MgB2" in output

    def test_large_data_truncated(self, capsys):
        """대규모 데이터는 앞뒤만 출력되고 생략 표시가 나온다."""
        df = pd.DataFrame({
            "물질명": [f"Mat{i}" for i in range(100)],
            "유형": ["화합물"] * 100,
            "평균원자질량": np.random.uniform(10, 200, 100),
            "밀도": np.random.uniform(1, 15, 100),
            "Tc": np.random.uniform(0.1, 100, 100),
        })
        show_data_table(df)
        output = capsys.readouterr().out
        assert "생략" in output
        assert "총 100개" in output


# ── 유형별 요약 테스트 ────────────────────────────────────


class TestTypeSummary:
    """show_type_summary() 함수 테스트."""

    def test_prints_type_summary(self, capsys):
        """유형별 요약이 출력된다."""
        df = load_dataset()
        show_type_summary(df)
        output = capsys.readouterr().out
        assert "유형별 Tc 요약" in output
        assert "원소" in output
        assert "전체" in output

    def test_csv_type_summary(self, capsys):
        """CSV 데이터에 대해 유형별 요약이 동작한다."""
        df = load_csv(CSV_TEST_PATH)
        show_type_summary(df)
        output = capsys.readouterr().out
        assert "고온" in output
        assert "수소화물" in output


# ── 상관 분석 테스트 ─────────────────────────────────────


class TestCorrelation:
    """compute_correlation() 함수 테스트."""

    def test_returns_dataframe(self, capsys):
        """결과를 DataFrame으로 반환한다."""
        df = load_dataset()
        result = compute_correlation(df)
        assert isinstance(result, pd.DataFrame)

    def test_three_correlations(self, capsys):
        """내장 데이터: 3개 변수에 대한 상관계수를 계산한다."""
        df = load_dataset()
        result = compute_correlation(df)
        assert len(result) == 3

    def test_csv_six_correlations(self, capsys):
        """CSV 데이터: 6개 변수에 대한 상관계수를 계산한다."""
        df = load_csv(CSV_TEST_PATH)
        result = compute_correlation(df)
        assert len(result) == 6

    def test_correlation_range(self, capsys):
        """상관계수가 -1 ~ +1 범위이다."""
        df = load_dataset()
        result = compute_correlation(df)
        assert (result["상관계수(r)"].abs() <= 1.0).all()

    def test_prints_output(self, capsys):
        """상관 분석 결과가 출력된다."""
        df = load_dataset()
        compute_correlation(df)
        output = capsys.readouterr().out
        assert "상관" in output


# ── 회귀 분석 테스트 ─────────────────────────────────────


class TestRegression:
    """fit_regression() 및 linear_model() 테스트."""

    def test_linear_model(self):
        """linear_model이 y = a*x + b를 올바르게 계산한다."""
        assert linear_model(0, 2.0, 3.0) == pytest.approx(3.0)
        assert linear_model(1, 2.0, 3.0) == pytest.approx(5.0)
        assert linear_model(5, 0.5, 1.0) == pytest.approx(3.5)

    def test_returns_three_values(self):
        """(기울기, 절편, R²) 3개 값을 반환한다."""
        df = load_dataset()
        result = fit_regression(df, "평균원자질량")
        assert len(result) == 3

    def test_r_squared_range(self):
        """R² 값이 합리적 범위이다."""
        df = load_dataset()
        _, _, r2 = fit_regression(df, "평균원자질량")
        assert -1.0 <= r2 <= 1.0

    def test_perfect_fit(self):
        """완벽한 선형 데이터에서 R² ≈ 1."""
        df = pd.DataFrame({
            "x": [1, 2, 3, 4, 5],
            "Tc": [2, 4, 6, 8, 10],  # y = 2x
        })
        a, b, r2 = fit_regression(df, "x")
        assert a == pytest.approx(2.0, abs=0.01)
        assert b == pytest.approx(0.0, abs=0.01)
        assert r2 == pytest.approx(1.0, abs=0.01)

    def test_all_columns(self):
        """모든 수치 열에 대해 회귀가 동작한다."""
        df = load_dataset()
        for col in ["평균원자질량", "가전자수", "밀도"]:
            a, b, r2 = fit_regression(df, col)
            assert isinstance(a, float)
            assert isinstance(b, float)

    def test_csv_regression(self):
        """CSV 데이터의 확장 열에 대해 회귀가 동작한다."""
        df = load_csv(CSV_TEST_PATH)
        for col in ["열전도도", "전자비열계수", "원소수"]:
            a, b, r2 = fit_regression(df, col)
            assert isinstance(a, float)
            assert -1.0 <= r2 <= 1.0


# ── 시각화 테스트 ────────────────────────────────────────


class TestPlotAnalysis:
    """plot_analysis() 시각화 테스트."""

    def test_returns_fig_and_axes(self):
        """fig, axes 객체를 반환한다."""
        df = load_dataset()
        fig, axes = plot_analysis(df)
        assert fig is not None
        assert axes.shape == (2, 2)
        plt.close(fig)

    def test_save_to_file(self, tmp_path):
        """파일로 저장할 수 있다."""
        df = load_dataset()
        save_path = str(tmp_path / "test_tc.png")
        fig, _ = plot_analysis(df, save_path=save_path)
        assert os.path.exists(save_path)
        plt.close(fig)

    def test_csv_data_plot(self, tmp_path):
        """CSV 데이터로 그래프를 생성할 수 있다."""
        df = load_csv(CSV_TEST_PATH)
        save_path = str(tmp_path / "test_csv_tc.png")
        fig, axes = plot_analysis(df, save_path=save_path)
        assert fig is not None
        assert axes.shape == (2, 2)
        assert os.path.exists(save_path)
        plt.close(fig)


# ── 대화형 실행 테스트 ───────────────────────────────────


class TestRunAnalysis:
    """run_tc_analysis() 대화형 실행 테스트."""

    def test_builtin_view_table(self, monkeypatch, capsys):
        """내장 데이터 → 메뉴 1 → 데이터 테이블 출력."""
        # "2" = 내장 데이터 선택, "1" = 테이블 보기, "0" = 종료
        inputs = iter(["2", "1", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_tc_analysis()
        output = capsys.readouterr().out
        assert "Nb" in output

    def test_builtin_view_stats(self, monkeypatch, capsys):
        """내장 데이터 → 메뉴 2 → 기본 통계 출력."""
        inputs = iter(["2", "2", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_tc_analysis()
        output = capsys.readouterr().out
        assert "총 물질 수" in output

    def test_builtin_correlation(self, monkeypatch, capsys):
        """내장 데이터 → 메뉴 3 → 상관 분석 출력."""
        inputs = iter(["2", "3", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_tc_analysis()
        output = capsys.readouterr().out
        assert "상관" in output

    def test_builtin_regression(self, monkeypatch, capsys):
        """내장 데이터 → 메뉴 4 → 회귀 분석 출력."""
        inputs = iter(["2", "4", "1", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_tc_analysis()
        output = capsys.readouterr().out
        assert "R²" in output

    def test_builtin_save_plot(self, monkeypatch, capsys, tmp_path):
        """내장 데이터 → 메뉴 5 → 그래프 저장."""
        monkeypatch.chdir(tmp_path)
        inputs = iter(["2", "5", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_tc_analysis()
        output = capsys.readouterr().out
        assert "분석 완료" in output

    def test_builtin_type_summary(self, monkeypatch, capsys):
        """내장 데이터 → 메뉴 6 → 유형별 요약."""
        inputs = iter(["2", "6", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_tc_analysis()
        output = capsys.readouterr().out
        assert "유형별 Tc 요약" in output

    def test_invalid_then_exit(self, monkeypatch, capsys):
        """잘못된 입력 → 오류 메시지 후 0으로 종료."""
        inputs = iter(["2", "99", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_tc_analysis()
        output = capsys.readouterr().out
        assert "올바른 번호" in output

    def test_csv_load_and_stats(self, monkeypatch, capsys):
        """CSV 파일 로드 → 기본 통계 출력."""
        # "1" = CSV 선택, CSV_TEST_PATH = 파일 경로, "2" = 통계, "0" = 종료
        inputs = iter(["1", CSV_TEST_PATH, "2", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_tc_analysis()
        output = capsys.readouterr().out
        assert "CSV 로드 완료" in output
        assert "총 물질 수" in output
        assert "20" in output

    def test_csv_correlation_six_vars(self, monkeypatch, capsys):
        """CSV 파일 → 상관 분석 시 6개 변수."""
        inputs = iter(["1", CSV_TEST_PATH, "3", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_tc_analysis()
        output = capsys.readouterr().out
        assert "열전도도" in output
        assert "전자비열계수" in output

    def test_csv_not_found_fallback(self, monkeypatch, capsys):
        """존재하지 않는 CSV → 내장 데이터셋으로 전환."""
        inputs = iter(["1", "없는파일.csv", "2", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_tc_analysis()
        output = capsys.readouterr().out
        assert "오류" in output
        assert "내장 데이터셋으로 전환" in output
        assert "총 물질 수" in output
