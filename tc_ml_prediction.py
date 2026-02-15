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


# ── 가상 물질 설계 ───────────────────────────────────────


def get_feature_ranges(df, feature_names, le):
    """학습 데이터에서 각 특성의 범위(최솟값, 최댓값, 평균)를 반환한다.

    Returns:
        {특성이름: {"min": float, "max": float, "mean": float}} 딕셔너리
    """
    numeric_cols = get_numeric_columns(df)
    ranges = {}
    for fname in feature_names:
        if fname == "유형_코드":
            ranges[fname] = {"유형목록": list(le.classes_)}
        elif fname in df.columns:
            col = df[fname]
            ranges[fname] = {
                "min": float(col.min()),
                "max": float(col.max()),
                "mean": float(col.mean()),
            }
    return ranges


# 유형별 프리셋 — 각 유형의 대표적 물성 (내장 데이터 기반 참고값)
MATERIAL_PRESETS = {
    "원소": {
        "설명": "단일 원소 초전도체 (Al, Nb, Pb 등)",
        "평균원자질량": 100.0, "가전자수": 4.0, "밀도": 8.0,
        "원소수": 1, "평균가전자수": 4.0, "열전도도": 50.0, "전자비열계수": 3.5,
    },
    "합금": {
        "설명": "2~3종 원소 합금 (NbTi 등)",
        "평균원자질량": 70.0, "가전자수": 5.0, "밀도": 7.0,
        "원소수": 2, "평균가전자수": 4.5, "열전도도": 30.0, "전자비열계수": 5.0,
    },
    "화합물": {
        "설명": "화학적 화합물 (Nb3Sn, MgB2 등)",
        "평균원자질량": 50.0, "가전자수": 4.0, "밀도": 6.0,
        "원소수": 2, "평균가전자수": 4.0, "열전도도": 20.0, "전자비열계수": 5.0,
    },
    "고온": {
        "설명": "고온 초전도체 (YBCO, BSCCO 등)",
        "평균원자질량": 100.0, "가전자수": 3.0, "밀도": 6.5,
        "원소수": 5, "평균가전자수": 3.0, "열전도도": 4.0, "전자비열계수": 8.0,
    },
    "수소화물": {
        "설명": "고압 수소화물 (LaH10, YH6 등)",
        "평균원자질량": 15.0, "가전자수": 3.0, "밀도": 5.0,
        "원소수": 2, "평균가전자수": 3.0, "열전도도": 35.0, "전자비열계수": 4.0,
    },
}


def find_similar_materials(df, features, feature_names, le, n=5):
    """입력 특성과 가장 유사한 기존 물질 n개를 찾는다.

    유클리드 거리 기반 (특성값 정규화 후 비교).

    Returns:
        [(물질명, 유형, Tc, 거리)] 리스트 (거리 오름차순)
    """
    numeric_cols = get_numeric_columns(df)

    # 비교용 특성 행렬 구성 (유형 인코딩 포함)
    X_db = df[numeric_cols].copy()
    X_db["유형_코드"] = le.transform(df["유형"])
    X_db = X_db[feature_names].values

    # 정규화 (0~1 범위)
    col_min = X_db.min(axis=0)
    col_max = X_db.max(axis=0)
    col_range = col_max - col_min
    col_range[col_range == 0] = 1  # 0 나누기 방지

    X_norm = (X_db - col_min) / col_range
    feat_norm = (np.array(features) - col_min) / col_range

    # 유클리드 거리
    distances = np.sqrt(np.sum((X_norm - feat_norm) ** 2, axis=1))

    # 상위 n개
    top_idx = np.argsort(distances)[:n]
    results = []
    for idx in top_idx:
        results.append((
            df.iloc[idx]["물질명"],
            df.iloc[idx]["유형"],
            float(df.iloc[idx]["Tc"]),
            float(distances[idx]),
        ))
    return results


def build_features_from_input(feature_names, ranges, le, preset=None):
    """대화형으로 특성값을 입력받아 특성 벡터를 구성한다.

    Args:
        feature_names: 특성 이름 리스트
        ranges: get_feature_ranges() 결과
        le: LabelEncoder
        preset: 프리셋 딕셔너리 (기본값 제공용, None이면 기본값 없음)

    Returns:
        (features_list, valid) 튜플. valid=False면 입력 오류.
    """
    features = []
    for fname in feature_names:
        if fname == "유형_코드":
            type_list = ranges[fname]["유형목록"]
            print(f"\n  유형 선택: {type_list}")
            if preset:
                # 프리셋에서 유형 이름 추출 (프리셋 키가 유형명)
                default_type = None
                for t in type_list:
                    if preset.get("_유형") == t:
                        default_type = t
                        break
                if default_type:
                    type_input = input(f"  유형 (기본값: {default_type}): ").strip()
                    type_input = type_input or default_type
                else:
                    type_input = input(f"  유형: ").strip()
            else:
                type_input = input(f"  유형: ").strip()
            try:
                code = le.transform([type_input])[0]
                features.append(code)
            except ValueError:
                print(f"  오류: 알 수 없는 유형 '{type_input}'")
                return features, False
        else:
            r = ranges.get(fname, {})
            hint = ""
            default_val = ""
            if "min" in r:
                hint = f" (범위: {r['min']:.1f} ~ {r['max']:.1f}, 평균: {r['mean']:.1f})"
            if preset and fname in preset:
                default_val = str(preset[fname])
                prompt = f"  {fname}{hint}\n    값 (기본값: {default_val}): "
            else:
                prompt = f"  {fname}{hint}: "
            val_str = input(prompt).strip()
            val_str = val_str or default_val
            try:
                features.append(float(val_str))
            except ValueError:
                print(f"  오류: 숫자를 입력해 주세요.")
                return features, False
    return features, True


def show_prediction_result(name, pred_tc, similar):
    """예측 결과와 유사 물질을 출력한다."""
    print(f"\n{'=' * 55}")
    print(f"  가상 물질: {name}")
    print(f"  ★ 예측된 Tc: {pred_tc:.2f} K")

    if pred_tc > 77:
        print("  → 고온 초전도체 가능성! (액체 질소 온도 77K 이상)")
    elif pred_tc > 20:
        print("  → 중간 수준의 Tc입니다.")
    elif pred_tc > 4.2:
        print("  → 저온 초전도체 (액체 헬륨 온도 4.2K 이상)")
    else:
        print("  → 극저온 영역입니다.")
    print(f"{'=' * 55}")

    if similar:
        print(f"\n[ 가장 유사한 기존 물질 (상위 {len(similar)}개) ]")
        print(f"  {'물질명':16s} {'유형':8s} {'Tc(K)':>8s} {'유사도':>8s}")
        print(f"  {'-' * 44}")
        for mat_name, mat_type, mat_tc, dist in similar:
            similarity = max(0, (1 - dist) * 100)
            print(f"  {mat_name:16s} {mat_type:8s} {mat_tc:8.2f} {similarity:7.1f}%")


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

    # 특성 범위 계산 (가상 물질 설계 시 참고용)
    ranges = get_feature_ranges(df, feature_names, le)

    while True:
        print("\n[ ML 분석 메뉴 ]")
        print("  1. 가상 물질 설계 및 Tc 예측")
        print("  2. 특성 직접 입력으로 Tc 예측")
        print("  3. 특성 중요도 보기")
        print("  4. 교차 검증 수행")
        print("  5. 다른 모델로 재학습")
        print("  0. 메인 메뉴로 돌아가기")

        choice = input("번호를 선택하세요: ").strip()

        if choice == "1":
            # 가상 물질 설계
            print(f"\n[ 가상 물질 설계 ]")
            mat_name = input("  물질 이름 (예: MyAlloy-1): ").strip() or "가상물질"

            print("\n  프리셋을 선택하면 기본값이 제공됩니다.")
            print("  0. 프리셋 없이 직접 입력")
            preset_types = list(MATERIAL_PRESETS.keys())
            for i, ptype in enumerate(preset_types, 1):
                desc = MATERIAL_PRESETS[ptype]["설명"]
                print(f"  {i}. {ptype} — {desc}")

            preset_choice = input("  프리셋 번호 (기본값 0): ").strip() or "0"

            preset = None
            if preset_choice != "0":
                idx = int(preset_choice) - 1 if preset_choice.isdigit() else -1
                if 0 <= idx < len(preset_types):
                    selected_type = preset_types[idx]
                    preset = dict(MATERIAL_PRESETS[selected_type])
                    preset["_유형"] = selected_type
                    print(f"  → {selected_type} 프리셋 로드 완료")

            print(f"\n  특성값을 입력하세요 (프리셋이 있으면 Enter로 기본값 사용):")
            new_features, valid = build_features_from_input(
                feature_names, ranges, le, preset
            )

            if valid:
                pred_tc = predict_tc(model, new_features)
                similar = find_similar_materials(
                    df, new_features, feature_names, le, n=5
                )
                show_prediction_result(mat_name, pred_tc, similar)

        elif choice == "2":
            # 직접 입력 예측
            print(f"\n[ 특성 직접 입력 ]")
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

        elif choice == "3":
            importances = get_feature_importance(model, feature_names)
            show_feature_importance(importances)

        elif choice == "4":
            print("\n  교차 검증 수행 중...")
            model_class = MODELS[model_name]
            params = DEFAULT_MODEL_PARAMS[model_name]
            cv_model = model_class(**params)
            cv_result = cross_validate_model(cv_model, X, y)
            show_cross_validation(cv_result)

        elif choice == "5":
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
            print("올바른 번호를 입력해 주세요. (0~5)")
