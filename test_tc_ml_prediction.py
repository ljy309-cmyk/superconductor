"""머신러닝 Tc 예측 모델 테스트."""

import os
import numpy as np
import pandas as pd
import pytest

from tc_prediction import load_dataset, load_csv
from tc_ml_prediction import (
    prepare_features, train_model, evaluate_model,
    cross_validate_model, get_feature_importance, predict_tc,
    show_evaluation, show_feature_importance, show_cross_validation,
    run_ml_prediction, MODELS, DEFAULT_MODEL_PARAMS,
)


CSV_TEST_PATH = os.path.join(os.path.dirname(__file__), "test_superconductor_data.csv")


# ── 데이터 전처리 테스트 ─────────────────────────────────


class TestPrepareFeatures:
    """prepare_features() 함수 테스트."""

    def test_builtin_returns_correct_shapes(self):
        """내장 데이터에서 올바른 형태를 반환한다."""
        df = load_dataset()
        X, y, names, le = prepare_features(df)
        assert X.shape[0] == len(df)
        assert X.shape[0] == len(y)
        assert len(names) == X.shape[1]

    def test_csv_returns_correct_shapes(self):
        """CSV 데이터에서 올바른 형태를 반환한다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, names, le = prepare_features(df)
        assert X.shape[0] == 20
        assert len(y) == 20

    def test_includes_type_encoding(self):
        """유형_코드가 특성에 포함된다."""
        df = load_dataset()
        X, y, names, le = prepare_features(df)
        assert "유형_코드" in names

    def test_label_encoder_works(self):
        """LabelEncoder가 유형을 올바르게 인코딩한다."""
        df = load_dataset()
        _, _, _, le = prepare_features(df)
        # 인코딩 후 역변환 가능
        encoded = le.transform(["원소"])
        decoded = le.inverse_transform(encoded)
        assert decoded[0] == "원소"

    def test_y_is_tc_values(self):
        """y가 Tc 값과 일치한다."""
        df = load_dataset()
        X, y, _, _ = prepare_features(df)
        np.testing.assert_array_equal(y, df["Tc"].values)

    def test_csv_more_features_than_builtin(self):
        """CSV 데이터는 내장 데이터보다 더 많은 특성을 가진다."""
        df_builtin = load_dataset()
        df_csv = load_csv(CSV_TEST_PATH)
        _, _, names_b, _ = prepare_features(df_builtin)
        _, _, names_c, _ = prepare_features(df_csv)
        assert len(names_c) > len(names_b)


# ── 모델 학습 테스트 ─────────────────────────────────────


class TestTrainModel:
    """train_model() 함수 테스트."""

    @pytest.fixture
    def training_data(self):
        df = load_csv(CSV_TEST_PATH)
        return prepare_features(df)

    def test_random_forest_trains(self, training_data):
        """랜덤포레스트 모델이 학습된다."""
        X, y, _, _ = training_data
        model, X_tr, X_te, y_tr, y_te = train_model(X, y, "랜덤포레스트")
        assert hasattr(model, "predict")
        assert len(X_tr) + len(X_te) == len(X)

    def test_gradient_boosting_trains(self, training_data):
        """그래디언트부스팅 모델이 학습된다."""
        X, y, _, _ = training_data
        model, _, _, _, _ = train_model(X, y, "그래디언트부스팅")
        assert hasattr(model, "predict")

    def test_linear_regression_trains(self, training_data):
        """선형회귀 모델이 학습된다."""
        X, y, _, _ = training_data
        model, _, _, _, _ = train_model(X, y, "선형회귀")
        assert hasattr(model, "predict")

    def test_test_size_split(self, training_data):
        """학습/테스트 세트가 올바르게 분할된다."""
        X, y, _, _ = training_data
        model, X_tr, X_te, y_tr, y_te = train_model(X, y, test_size=0.3)
        # 약 30%가 테스트셋 (20개 중 6개)
        assert len(X_te) == int(len(X) * 0.3) or abs(len(X_te) - len(X) * 0.3) <= 1


# ── 모델 평가 테스트 ─────────────────────────────────────


class TestEvaluateModel:
    """evaluate_model() 함수 테스트."""

    @pytest.fixture
    def trained_model(self):
        df = load_csv(CSV_TEST_PATH)
        X, y, names, _ = prepare_features(df)
        model, _, X_test, _, y_test = train_model(X, y, "랜덤포레스트")
        return model, X_test, y_test

    def test_returns_metrics_dict(self, trained_model):
        """R², MAE, RMSE 키를 가진 딕셔너리를 반환한다."""
        model, X_test, y_test = trained_model
        metrics = evaluate_model(model, X_test, y_test)
        assert "R²" in metrics
        assert "MAE" in metrics
        assert "RMSE" in metrics

    def test_mae_non_negative(self, trained_model):
        """MAE가 0 이상이다."""
        model, X_test, y_test = trained_model
        metrics = evaluate_model(model, X_test, y_test)
        assert metrics["MAE"] >= 0

    def test_rmse_non_negative(self, trained_model):
        """RMSE가 0 이상이다."""
        model, X_test, y_test = trained_model
        metrics = evaluate_model(model, X_test, y_test)
        assert metrics["RMSE"] >= 0

    def test_rmse_gte_mae(self, trained_model):
        """RMSE >= MAE (항상 성립)."""
        model, X_test, y_test = trained_model
        metrics = evaluate_model(model, X_test, y_test)
        assert metrics["RMSE"] >= metrics["MAE"] - 1e-10


# ── 교차 검증 테스트 ─────────────────────────────────────


class TestCrossValidation:
    """cross_validate_model() 함수 테스트."""

    def test_returns_correct_keys(self):
        """평균R², 표준편차, 각_폴드 키를 반환한다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, _, _ = prepare_features(df)
        from sklearn.linear_model import LinearRegression
        model = LinearRegression()
        result = cross_validate_model(model, X, y, cv=3)
        assert "평균R²" in result
        assert "표준편차" in result
        assert "각_폴드" in result

    def test_fold_count_matches_cv(self):
        """폴드 수가 cv 파라미터와 일치한다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, _, _ = prepare_features(df)
        from sklearn.linear_model import LinearRegression
        model = LinearRegression()
        result = cross_validate_model(model, X, y, cv=3)
        assert len(result["각_폴드"]) == 3

    def test_std_non_negative(self):
        """표준편차가 0 이상이다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, _, _ = prepare_features(df)
        from sklearn.linear_model import LinearRegression
        model = LinearRegression()
        result = cross_validate_model(model, X, y, cv=3)
        assert result["표준편차"] >= 0


# ── 특성 중요도 테스트 ────────────────────────────────────


class TestFeatureImportance:
    """get_feature_importance() 함수 테스트."""

    def test_random_forest_importance(self):
        """랜덤포레스트의 특성 중요도를 반환한다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, names, _ = prepare_features(df)
        model, _, _, _, _ = train_model(X, y, "랜덤포레스트")
        importances = get_feature_importance(model, names)
        assert len(importances) == len(names)
        # 중요도 합이 1에 가까움 (랜덤포레스트)
        total = sum(imp for _, imp in importances)
        assert abs(total - 1.0) < 0.01

    def test_linear_regression_importance(self):
        """선형회귀의 계수 기반 중요도를 반환한다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, names, _ = prepare_features(df)
        model, _, _, _, _ = train_model(X, y, "선형회귀")
        importances = get_feature_importance(model, names)
        assert len(importances) == len(names)

    def test_sorted_descending(self):
        """중요도가 내림차순으로 정렬된다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, names, _ = prepare_features(df)
        model, _, _, _, _ = train_model(X, y, "랜덤포레스트")
        importances = get_feature_importance(model, names)
        values = [imp for _, imp in importances]
        assert values == sorted(values, reverse=True)


# ── 예측 테스트 ──────────────────────────────────────────


class TestPredictTc:
    """predict_tc() 함수 테스트."""

    def test_returns_float(self):
        """float 값을 반환한다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, names, _ = prepare_features(df)
        model, _, _, _, _ = train_model(X, y, "랜덤포레스트")
        pred = predict_tc(model, X[0])
        assert isinstance(pred, float)

    def test_prediction_non_negative(self):
        """예측값이 음수가 아닌 합리적 범위이다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, names, _ = prepare_features(df)
        model, _, _, _, _ = train_model(X, y, "랜덤포레스트")
        # 학습 데이터의 첫 번째 샘플로 예측
        pred = predict_tc(model, X[0])
        # 예측값이 극단적이지 않아야 함
        assert -50 < pred < 500


# ── 출력 테스트 ──────────────────────────────────────────


class TestShowEvaluation:
    """출력 함수 테스트."""

    def test_show_evaluation(self, capsys):
        """평가 결과가 올바르게 출력된다."""
        metrics = {"R²": 0.85, "MAE": 10.5, "RMSE": 15.2}
        show_evaluation(metrics)
        output = capsys.readouterr().out
        assert "R²" in output
        assert "MAE" in output
        assert "RMSE" in output
        assert "우수" in output

    def test_show_evaluation_low(self, capsys):
        """낮은 R²에서 적절한 메시지가 출력된다."""
        metrics = {"R²": 0.3, "MAE": 50.0, "RMSE": 70.0}
        show_evaluation(metrics)
        output = capsys.readouterr().out
        assert "낮습니다" in output

    def test_show_feature_importance(self, capsys):
        """특성 중요도가 출력된다."""
        importances = [("밀도", 0.4), ("질량", 0.35), ("가전자수", 0.25)]
        show_feature_importance(importances)
        output = capsys.readouterr().out
        assert "밀도" in output
        assert "질량" in output

    def test_show_cross_validation(self, capsys):
        """교차 검증 결과가 출력된다."""
        result = {"평균R²": 0.75, "표준편차": 0.05, "각_폴드": [0.7, 0.8, 0.75]}
        show_cross_validation(result)
        output = capsys.readouterr().out
        assert "교차 검증" in output
        assert "폴드 1" in output
        assert "평균" in output


# ── 대화형 실행 테스트 ───────────────────────────────────


class TestRunMlPrediction:
    """run_ml_prediction() 대화형 실행 테스트."""

    def test_builtin_train_and_exit(self, monkeypatch, capsys):
        """내장 데이터로 학습 → 바로 종료."""
        inputs = iter(["2", "1", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "모델 학습 중" in output
        assert "R²" in output

    def test_csv_train_and_exit(self, monkeypatch, capsys):
        """CSV 데이터로 학습 → 종료."""
        inputs = iter(["1", CSV_TEST_PATH, "1", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "데이터 로드 완료" in output
        assert "R²" in output

    def test_feature_importance_menu(self, monkeypatch, capsys):
        """메뉴 2 → 특성 중요도 출력."""
        inputs = iter(["2", "1", "2", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "특성 중요도" in output

    def test_cross_validation_menu(self, monkeypatch, capsys):
        """메뉴 3 → 교차 검증 수행."""
        inputs = iter(["2", "1", "3", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "교차 검증" in output

    def test_retrain_with_different_model(self, monkeypatch, capsys):
        """메뉴 4 → 다른 모델로 재학습."""
        inputs = iter(["2", "1", "4", "3", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "선형회귀" in output
        assert "재학습" in output

    def test_predict_new_material(self, monkeypatch, capsys):
        """메뉴 1 → 새 물질 Tc 예측."""
        # 내장 데이터(3특성+유형코드) → 랜덤포레스트 → 예측 입력
        # 특성: 평균원자질량, 가전자수, 밀도, 유형_코드(유형 입력)
        inputs = iter(["2", "1", "1", "50.0", "3", "5.0", "원소", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "예측된 Tc" in output

    def test_predict_invalid_type(self, monkeypatch, capsys):
        """잘못된 유형 입력 → 오류 메시지."""
        inputs = iter(["2", "1", "1", "50.0", "3", "5.0", "없는유형", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "오류" in output

    def test_predict_invalid_number(self, monkeypatch, capsys):
        """숫자가 아닌 특성 입력 → 오류 메시지."""
        inputs = iter(["2", "1", "1", "abc", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "오류" in output

    def test_csv_not_found_fallback(self, monkeypatch, capsys):
        """존재하지 않는 CSV → 내장 데이터로 전환."""
        inputs = iter(["1", "없는파일.csv", "1", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "오류" in output
        assert "내장 데이터셋으로 전환" in output

    def test_invalid_menu_choice(self, monkeypatch, capsys):
        """잘못된 메뉴 번호 → 오류 메시지."""
        inputs = iter(["2", "1", "99", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "올바른 번호" in output
