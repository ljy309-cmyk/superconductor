# 임계 온도(Tc) 예측 머신러닝 모델
# 학습 포인트: scikit-learn 활용, 모델 학습/평가/예측 파이프라인
# CSV 데이터(21,263행)로 학습하여 새로운 물질의 Tc를 예측

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from tc_prediction import load_csv, load_dataset, get_numeric_columns, DEFAULT_CSV_PATH


# ── 데이터 전처리 ────────────────────────────────────────


def prepare_features(df):
    """DataFrame에서 학습용 특성(X)과 목표 변수(y)를 추출한다.

    수치형 열 + 유형(라벨 인코딩)을 특성으로, Tc를 목표 변수로 사용.

    Returns:
        (X, y, feature_names, label_encoder) 튜플
    """
    numeric_cols = get_numeric_columns(df)

    # 유형 → 숫자로 인코딩
    le = LabelEncoder()
    type_encoded = le.fit_transform(df["유형"])

    # 특성 행렬 구성
    X = df[numeric_cols].copy()
    X["유형_코드"] = type_encoded
    feature_names = list(X.columns)

    y = df["Tc"].values

    return X.values, y, feature_names, le


# ── 모델 학습 ────────────────────────────────────────────


MODELS = {
    "선형회귀": LinearRegression,
    "랜덤포레스트": RandomForestRegressor,
    "그래디언트부스팅": GradientBoostingRegressor,
}

DEFAULT_MODEL_PARAMS = {
    "선형회귀": {},
    "랜덤포레스트": {"n_estimators": 100, "random_state": 42, "n_jobs": -1},
    "그래디언트부스팅": {"n_estimators": 100, "random_state": 42, "max_depth": 5},
}


def train_model(X, y, model_name="랜덤포레스트", test_size=0.2):
    """모델을 학습하고 학습/테스트 세트 성능을 반환한다.

    Args:
        X: 특성 행렬
        y: 목표 변수 (Tc)
        model_name: 모델 이름 ("선형회귀", "랜덤포레스트", "그래디언트부스팅")
        test_size: 테스트 데이터 비율

    Returns:
        (model, X_train, X_test, y_train, y_test) 튜플
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42
    )

    model_class = MODELS[model_name]
    params = DEFAULT_MODEL_PARAMS[model_name]
    model = model_class(**params)
    model.fit(X_train, y_train)

    return model, X_train, X_test, y_train, y_test


def evaluate_model(model, X_test, y_test):
    """모델 성능을 평가하여 딕셔너리로 반환한다.

    Returns:
        {"R²": float, "MAE": float, "RMSE": float}
    """
    y_pred = model.predict(X_test)

    metrics = {
        "R²": r2_score(y_test, y_pred),
        "MAE": mean_absolute_error(y_test, y_pred),
        "RMSE": np.sqrt(mean_squared_error(y_test, y_pred)),
    }
    return metrics


def cross_validate_model(model, X, y, cv=5):
    """k-fold 교차 검증을 수행한다.

    Returns:
        {"평균R²": float, "표준편차": float, "각_폴드": list}
    """
    scores = cross_val_score(model, X, y, cv=cv, scoring="r2")
    return {
        "평균R²": scores.mean(),
        "표준편차": scores.std(),
        "각_폴드": scores.tolist(),
    }


def get_feature_importance(model, feature_names):
    """특성 중요도를 (이름, 중요도) 리스트로 반환한다 (내림차순)."""
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "coef_"):
        # 선형 모델: 계수의 절대값을 중요도로 사용
        importances = np.abs(model.coef_)
    else:
        return []

    pairs = list(zip(feature_names, importances))
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs


def predict_tc(model, features):
    """단일 샘플의 Tc를 예측한다.

    Args:
        model: 학습된 모델
        features: 1D 배열 (특성 값)

    Returns:
        예측된 Tc (float)
    """
    X = np.array(features).reshape(1, -1)
    return float(model.predict(X)[0])


# ── 출력 함수 ────────────────────────────────────────────


def show_evaluation(metrics):
    """모델 평가 결과를 출력한다."""
    print("\n[ 모델 평가 결과 ]")
    print(f"  R² (결정계수): {metrics['R²']:.4f}")
    print(f"  MAE (평균절대오차): {metrics['MAE']:.2f} K")
    print(f"  RMSE (평균제곱근오차): {metrics['RMSE']:.2f} K")

    if metrics["R²"] >= 0.8:
        print("  → 모델 성능이 우수합니다.")
    elif metrics["R²"] >= 0.5:
        print("  → 보통 수준의 예측 성능입니다.")
    else:
        print("  → 예측 성능이 낮습니다. 더 많은 데이터나 다른 모델을 시도해 보세요.")


def show_feature_importance(importances):
    """특성 중요도를 출력한다."""
    print("\n[ 특성 중요도 ]")
    print("-" * 45)
    total = sum(imp for _, imp in importances)
    for name, imp in importances:
        if total > 0:
            pct = imp / total * 100
            bar = "█" * int(pct / 3)
            print(f"  {name:12s}: {imp:.4f} ({pct:5.1f}%) {bar}")
        else:
            print(f"  {name:12s}: {imp:.4f}")
    print("-" * 45)


def show_cross_validation(cv_result):
    """교차 검증 결과를 출력한다."""
    print(f"\n[ {len(cv_result['각_폴드'])}겹 교차 검증 결과 ]")
    for i, score in enumerate(cv_result["각_폴드"], 1):
        print(f"  폴드 {i}: R² = {score:.4f}")
    print(f"  ─────────────────")
    print(f"  평균 R²: {cv_result['평균R²']:.4f} (±{cv_result['표준편차']:.4f})")


# ── 대화형 실행 ──────────────────────────────────────────


def run_ml_prediction():
    """머신러닝 기반 Tc 예측 프로그램 (대화형)."""
    print("--- 머신러닝 Tc 예측 모델 ---")
    print("초전도체 데이터를 학습하여 새로운 물질의 Tc를 예측합니다.\n")

    # 1. 데이터 로드
    print("[ 데이터 소스 선택 ]")
    print(f"  1. CSV 파일 ({DEFAULT_CSV_PATH})")
    print("  2. 내장 데이터셋 (20개 물질)")

    source = input("선택 (기본값 1): ").strip() or "1"

    if source == "1":
        csv_path = input(f"CSV 경로 (기본값: {DEFAULT_CSV_PATH}): ").strip()
        csv_path = csv_path or DEFAULT_CSV_PATH
        try:
            df = load_csv(csv_path)
            print(f"  데이터 로드 완료: {len(df):,}개")
        except (FileNotFoundError, ValueError) as e:
            print(f"  오류: {e}")
            print("  → 내장 데이터셋으로 전환합니다.")
            df = load_dataset()
    else:
        df = load_dataset()
        print(f"  내장 데이터셋 로드: {len(df)}개 물질")

    # 2. 데이터 전처리
    X, y, feature_names, le = prepare_features(df)
    print(f"  특성 수: {len(feature_names)}개 ({', '.join(feature_names)})")

    # 3. 모델 선택 및 학습
    print("\n[ 모델 선택 ]")
    print("  1. 랜덤포레스트 (추천)")
    print("  2. 그래디언트부스팅")
    print("  3. 선형회귀")

    model_choice = input("모델 번호 (기본값 1): ").strip() or "1"
    model_map = {"1": "랜덤포레스트", "2": "그래디언트부스팅", "3": "선형회귀"}
    model_name = model_map.get(model_choice, "랜덤포레스트")

    print(f"\n  {model_name} 모델 학습 중...")
    model, X_train, X_test, y_train, y_test = train_model(X, y, model_name)
    metrics = evaluate_model(model, X_test, y_test)
    show_evaluation(metrics)

    while True:
        print("\n[ ML 분석 메뉴 ]")
        print("  1. 새로운 물질의 Tc 예측")
        print("  2. 특성 중요도 보기")
        print("  3. 교차 검증 수행")
        print("  4. 다른 모델로 재학습")
        print("  0. 메인 메뉴로 돌아가기")

        choice = input("번호를 선택하세요: ").strip()

        if choice == "1":
            # 새 물질 예측
            print(f"\n[ 새로운 물질의 특성 입력 ]")
            print(f"  특성 순서: {', '.join(feature_names)}")

            new_features = []
            valid = True
            for fname in feature_names:
                if fname == "유형_코드":
                    print(f"  유형 목록: {list(le.classes_)}")
                    type_input = input(f"  유형: ").strip()
                    try:
                        code = le.transform([type_input])[0]
                        new_features.append(code)
                    except ValueError:
                        print(f"  오류: 알 수 없는 유형 '{type_input}'")
                        valid = False
                        break
                else:
                    val_str = input(f"  {fname}: ").strip()
                    try:
                        new_features.append(float(val_str))
                    except ValueError:
                        print(f"  오류: 숫자를 입력해 주세요.")
                        valid = False
                        break

            if valid:
                pred_tc = predict_tc(model, new_features)
                print(f"\n  ★ 예측된 Tc: {pred_tc:.2f} K")
                if pred_tc > 77:
                    print("  → 고온 초전도체 가능성! (액체 질소 온도 이상)")
                elif pred_tc > 20:
                    print("  → 중간 수준의 Tc입니다.")
                else:
                    print("  → 저온 초전도체 영역입니다.")

        elif choice == "2":
            importances = get_feature_importance(model, feature_names)
            show_feature_importance(importances)

        elif choice == "3":
            print("\n  교차 검증 수행 중...")
            model_class = MODELS[model_name]
            params = DEFAULT_MODEL_PARAMS[model_name]
            cv_model = model_class(**params)
            cv_result = cross_validate_model(cv_model, X, y)
            show_cross_validation(cv_result)

        elif choice == "4":
            print("\n[ 모델 선택 ]")
            print("  1. 랜덤포레스트")
            print("  2. 그래디언트부스팅")
            print("  3. 선형회귀")
            new_choice = input("모델 번호: ").strip()
            model_name = model_map.get(new_choice, model_name)
            print(f"\n  {model_name} 모델 재학습 중...")
            model, X_train, X_test, y_train, y_test = train_model(X, y, model_name)
            metrics = evaluate_model(model, X_test, y_test)
            show_evaluation(metrics)

        elif choice == "0":
            break
        else:
            print("올바른 번호를 입력해 주세요. (0~4)")
