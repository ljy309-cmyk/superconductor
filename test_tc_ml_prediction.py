"""머신러닝 Tc 예측 모델 테스트."""

import os
import numpy as np
import pandas as pd
import pytest

from tc_prediction import load_dataset, load_csv
from tc_ml_prediction import (
    prepare_features, train_model, evaluate_model,
    cross_validate_model, get_feature_importance, predict_tc,
    get_feature_ranges, find_similar_materials,
    build_features_from_input, show_prediction_result,
    show_evaluation, show_feature_importance, show_cross_validation,
    run_ml_prediction, MODELS, DEFAULT_MODEL_PARAMS, MATERIAL_PRESETS,
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
        """예측값이 합리적 범위이다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, names, _ = prepare_features(df)
        model, _, _, _, _ = train_model(X, y, "랜덤포레스트")
        pred = predict_tc(model, X[0])
        assert -50 < pred < 500


# ── 특성 범위 테스트 ─────────────────────────────────────


class TestGetFeatureRanges:
    """get_feature_ranges() 함수 테스트."""

    def test_returns_dict(self):
        """딕셔너리를 반환한다."""
        df = load_csv(CSV_TEST_PATH)
        _, _, names, le = prepare_features(df)
        ranges = get_feature_ranges(df, names, le)
        assert isinstance(ranges, dict)

    def test_numeric_features_have_min_max_mean(self):
        """수치 특성에 min, max, mean이 있다."""
        df = load_csv(CSV_TEST_PATH)
        _, _, names, le = prepare_features(df)
        ranges = get_feature_ranges(df, names, le)
        for fname in names:
            if fname != "유형_코드":
                if fname in ranges:
                    assert "min" in ranges[fname]
                    assert "max" in ranges[fname]
                    assert "mean" in ranges[fname]

    def test_type_code_has_type_list(self):
        """유형_코드에 유형목록이 있다."""
        df = load_csv(CSV_TEST_PATH)
        _, _, names, le = prepare_features(df)
        ranges = get_feature_ranges(df, names, le)
        assert "유형_코드" in ranges
        assert "유형목록" in ranges["유형_코드"]
        assert len(ranges["유형_코드"]["유형목록"]) > 0

    def test_min_lte_max(self):
        """min <= max가 성립한다."""
        df = load_csv(CSV_TEST_PATH)
        _, _, names, le = prepare_features(df)
        ranges = get_feature_ranges(df, names, le)
        for fname in names:
            if fname != "유형_코드" and fname in ranges:
                assert ranges[fname]["min"] <= ranges[fname]["max"]


# ── 유사 물질 검색 테스트 ─────────────────────────────────


class TestFindSimilarMaterials:
    """find_similar_materials() 함수 테스트."""

    def test_returns_correct_count(self):
        """요청한 n개의 결과를 반환한다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, names, le = prepare_features(df)
        # 첫 번째 샘플과 유사한 물질 3개
        similar = find_similar_materials(df, X[0], names, le, n=3)
        assert len(similar) == 3

    def test_result_contains_four_elements(self):
        """각 결과가 (물질명, 유형, Tc, 거리) 4개 요소를 가진다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, names, le = prepare_features(df)
        similar = find_similar_materials(df, X[0], names, le, n=1)
        assert len(similar[0]) == 4

    def test_first_result_is_most_similar(self):
        """첫 번째 결과가 가장 가까운 물질이다 (거리 오름차순)."""
        df = load_csv(CSV_TEST_PATH)
        X, y, names, le = prepare_features(df)
        similar = find_similar_materials(df, X[0], names, le, n=5)
        distances = [s[3] for s in similar]
        assert distances == sorted(distances)

    def test_same_sample_has_zero_distance(self):
        """동일한 샘플을 넣으면 거리가 0이다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, names, le = prepare_features(df)
        similar = find_similar_materials(df, X[0], names, le, n=1)
        assert similar[0][3] == pytest.approx(0.0, abs=1e-10)

    def test_distances_non_negative(self):
        """모든 거리가 0 이상이다."""
        df = load_csv(CSV_TEST_PATH)
        X, y, names, le = prepare_features(df)
        similar = find_similar_materials(df, X[5], names, le, n=5)
        for _, _, _, dist in similar:
            assert dist >= 0


# ── 프리셋 테스트 ────────────────────────────────────────


class TestMaterialPresets:
    """MATERIAL_PRESETS 프리셋 테스트."""

    def test_five_presets_exist(self):
        """5개 유형에 대한 프리셋이 존재한다."""
        assert len(MATERIAL_PRESETS) == 5
        for ptype in ["원소", "합금", "화합물", "고온", "수소화물"]:
            assert ptype in MATERIAL_PRESETS

    def test_each_preset_has_description(self):
        """각 프리셋에 설명이 있다."""
        for ptype, preset in MATERIAL_PRESETS.items():
            assert "설명" in preset
            assert len(preset["설명"]) > 0

    def test_each_preset_has_numeric_values(self):
        """각 프리셋에 평균원자질량, 밀도 등 수치값이 있다."""
        for ptype, preset in MATERIAL_PRESETS.items():
            assert "평균원자질량" in preset
            assert "밀도" in preset
            assert isinstance(preset["평균원자질량"], (int, float))


# ── build_features_from_input 테스트 ─────────────────────


class TestBuildFeaturesFromInput:
    """build_features_from_input() 대화형 입력 테스트."""

    def test_with_preset_defaults(self, monkeypatch):
        """프리셋 기본값으로 특성 벡터를 구성한다."""
        df = load_dataset()
        _, _, names, le = prepare_features(df)
        ranges = get_feature_ranges(df, names, le)
        preset = dict(MATERIAL_PRESETS["원소"])
        preset["_유형"] = "원소"
        # 모든 입력에 빈 문자열 → 기본값 사용
        inputs = iter([""] * len(names))
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        features, valid = build_features_from_input(names, ranges, le, preset)
        assert valid is True
        assert len(features) == len(names)

    def test_invalid_type_returns_false(self, monkeypatch):
        """잘못된 유형 입력 시 valid=False를 반환한다."""
        df = load_dataset()
        _, _, names, le = prepare_features(df)
        ranges = get_feature_ranges(df, names, le)
        # 숫자 특성들은 유효하게, 유형에서 오류 발생
        inputs = iter(["50.0", "3", "5.0", "없는유형"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        features, valid = build_features_from_input(names, ranges, le, None)
        assert valid is False

    def test_invalid_number_returns_false(self, monkeypatch):
        """숫자가 아닌 입력 시 valid=False를 반환한다."""
        df = load_dataset()
        _, _, names, le = prepare_features(df)
        ranges = get_feature_ranges(df, names, le)
        inputs = iter(["abc"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        features, valid = build_features_from_input(names, ranges, le, None)
        assert valid is False


# ── show_prediction_result 테스트 ─────────────────────────


class TestShowPredictionResult:
    """show_prediction_result() 출력 테스트."""

    def test_shows_name_and_tc(self, capsys):
        """물질 이름과 예측 Tc가 출력된다."""
        similar = [("Nb", "원소", 9.26, 0.1)]
        show_prediction_result("TestMat", 42.5, similar)
        output = capsys.readouterr().out
        assert "TestMat" in output
        assert "42.50" in output

    def test_high_tc_message(self, capsys):
        """Tc > 77K일 때 고온 초전도체 메시지가 출력된다."""
        show_prediction_result("HighTc", 100.0, [])
        output = capsys.readouterr().out
        assert "고온" in output

    def test_low_tc_message(self, capsys):
        """Tc < 4.2K일 때 극저온 메시지가 출력된다."""
        show_prediction_result("LowTc", 2.0, [])
        output = capsys.readouterr().out
        assert "극저온" in output

    def test_shows_similar_materials(self, capsys):
        """유사 물질 목록이 출력된다."""
        similar = [
            ("Nb", "원소", 9.26, 0.1),
            ("NbTi", "합금", 9.80, 0.2),
        ]
        show_prediction_result("MyMat", 10.0, similar)
        output = capsys.readouterr().out
        assert "유사한 기존 물질" in output
        assert "Nb" in output
        assert "NbTi" in output

    def test_empty_similar_no_crash(self, capsys):
        """유사 물질이 없어도 오류 없이 출력된다."""
        show_prediction_result("Solo", 50.0, [])
        output = capsys.readouterr().out
        assert "Solo" in output
        assert "유사" not in output


# ── 출력 함수 테스트 ─────────────────────────────────────


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
        """메뉴 3 → 특성 중요도 출력."""
        inputs = iter(["2", "1", "3", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "특성 중요도" in output

    def test_cross_validation_menu(self, monkeypatch, capsys):
        """메뉴 4 → 교차 검증 수행."""
        inputs = iter(["2", "1", "4", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "교차 검증" in output

    def test_retrain_with_different_model(self, monkeypatch, capsys):
        """메뉴 5 → 다른 모델로 재학습."""
        inputs = iter(["2", "1", "5", "3", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "선형회귀" in output
        assert "재학습" in output

    def test_direct_predict(self, monkeypatch, capsys):
        """메뉴 2 → 직접 입력으로 Tc 예측."""
        # 내장 데이터(3특성+유형코드) → 랜덤포레스트 → 직접 입력
        inputs = iter(["2", "1", "2", "50.0", "3", "5.0", "원소", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "예측된 Tc" in output

    def test_virtual_material_no_preset(self, monkeypatch, capsys):
        """메뉴 1 → 프리셋 없이 가상 물질 설계."""
        # 내장: 평균원자질량, 가전자수, 밀도, 유형
        inputs = iter([
            "2", "1",       # 내장 데이터, 랜덤포레스트
            "1",            # 메뉴 1: 가상 물질 설계
            "SuperAlloy-X", # 물질 이름
            "0",            # 프리셋 없음
            "60.0", "4", "7.0", "합금",  # 특성 입력
            "0",            # 종료
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "SuperAlloy-X" in output
        assert "예측된 Tc" in output
        assert "유사한 기존 물질" in output

    def test_virtual_material_with_preset(self, monkeypatch, capsys):
        """메뉴 1 → 프리셋 사용 가상 물질 설계."""
        # 내장: 평균원자질량, 가전자수, 밀도, 유형
        inputs = iter([
            "2", "1",       # 내장 데이터, 랜덤포레스트
            "1",            # 메뉴 1: 가상 물질 설계
            "TestMat",      # 물질 이름
            "1",            # 프리셋 1번 (원소)
            "", "", "", "",  # 모두 기본값 사용
            "0",            # 종료
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "TestMat" in output
        assert "예측된 Tc" in output
        assert "프리셋 로드" in output

    def test_predict_invalid_type(self, monkeypatch, capsys):
        """직접 입력에서 잘못된 유형 → 오류 메시지."""
        inputs = iter(["2", "1", "2", "50.0", "3", "5.0", "없는유형", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_ml_prediction()
        output = capsys.readouterr().out
        assert "오류" in output

    def test_predict_invalid_number(self, monkeypatch, capsys):
        """직접 입력에서 숫자가 아닌 특성 → 오류 메시지."""
        inputs = iter(["2", "1", "2", "abc", "0"])
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
