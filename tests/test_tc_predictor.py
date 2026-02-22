"""TC Predictor 및 generate_sample_data 단위 테스트.

ML 라이브러리(sklearn, matplotlib)가 없는 환경에서도
데이터 생성 로직과 설정값을 검증합니다.
sklearn이 있는 경우 모델 학습/평가 함수도 테스트합니다.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Tkinter / Pygame mock (GUI 불필요)
for mod in (
    "pygame",
    "tkinter",
    "tkinter.messagebox",
    "tkinter.ttk",
    "matplotlib",
    "matplotlib.backends",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.figure",
):
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSuperConCompounds(unittest.TestCase):
    """SUPERCON_COMPOUNDS 데이터 무결성."""

    def test_import(self):
        from data_ai.generate_sample_data import SUPERCON_COMPOUNDS

        self.assertIsInstance(SUPERCON_COMPOUNDS, list)
        self.assertGreater(len(SUPERCON_COMPOUNDS), 20)

    def test_compound_tuple_length(self):
        from data_ai.generate_sample_data import SUPERCON_COMPOUNDS

        for i, entry in enumerate(SUPERCON_COMPOUNDS):
            self.assertEqual(len(entry), 8, f"Compound {i} ({entry[0]}): expected 8 fields, got {len(entry)}")

    def test_tc_positive(self):
        """모든 화합물의 Tc는 양수여야 한다."""
        from data_ai.generate_sample_data import SUPERCON_COMPOUNDS

        for entry in SUPERCON_COMPOUNDS:
            name, *_, tc = entry
            self.assertGreater(tc, 0, f"{name}: Tc should be positive, got {tc}")

    def test_density_positive(self):
        """밀도는 양수여야 한다."""
        from data_ai.generate_sample_data import SUPERCON_COMPOUNDS

        for entry in SUPERCON_COMPOUNDS:
            name, density = entry[0], entry[1]
            self.assertGreater(density, 0, f"{name}: density should be positive")

    def test_high_tc_compounds_present(self):
        """고온 초전도체(Tc > 77K)가 포함되어야 한다."""
        from data_ai.generate_sample_data import SUPERCON_COMPOUNDS

        high_tc = [e for e in SUPERCON_COMPOUNDS if e[-1] > 77]
        self.assertGreater(len(high_tc), 3, "At least 3 high-Tc compounds expected")

    def test_hydride_compounds_present(self):
        """수소화물 초전도체(Tc > 150K)가 포함되어야 한다."""
        from data_ai.generate_sample_data import SUPERCON_COMPOUNDS

        hydrides = [e for e in SUPERCON_COMPOUNDS if e[-1] > 150]
        self.assertGreater(len(hydrides), 0, "Hydride superconductors expected")


class TestRealSuperconductors(unittest.TestCase):
    """REAL_SUPERCONDUCTORS 데이터 무결성."""

    def test_count(self):
        from data_ai.generate_sample_data import REAL_SUPERCONDUCTORS

        self.assertEqual(len(REAL_SUPERCONDUCTORS), 12)

    def test_nb_tc(self):
        """Nb의 Tc는 약 9.25K."""
        from data_ai.generate_sample_data import REAL_SUPERCONDUCTORS

        nb = [e for e in REAL_SUPERCONDUCTORS if e[0] == "Nb"]
        self.assertEqual(len(nb), 1)
        self.assertAlmostEqual(nb[0][-1], 9.25, delta=0.1)


class TestModelConfigs(unittest.TestCase):
    """MODEL_CONFIGS 설정 검증."""

    def test_three_models(self):
        from data_ai.tc_predictor import MODEL_CONFIGS

        self.assertEqual(len(MODEL_CONFIGS), 3)
        self.assertIn("RandomForest", MODEL_CONFIGS)
        self.assertIn("GradientBoosting", MODEL_CONFIGS)
        self.assertIn("SVR", MODEL_CONFIGS)

    def test_config_fields(self):
        from data_ai.tc_predictor import MODEL_CONFIGS

        for name, conf in MODEL_CONFIGS.items():
            self.assertIn("label", conf, f"{name} missing 'label'")
            self.assertIn("color", conf, f"{name} missing 'color'")
            self.assertIn("short", conf, f"{name} missing 'short'")

    def test_features_list(self):
        from data_ai.tc_predictor import FEATURES, TARGET

        self.assertEqual(len(FEATURES), 6)
        self.assertEqual(TARGET, "critical_temp")
        self.assertIn("electronegativity", FEATURES)


class TestBuildModel(unittest.TestCase):
    """_build_model 함수 테스트 (sklearn 의존)."""

    def setUp(self):
        try:
            import sklearn  # noqa: F401

            self.sklearn_available = True
        except ImportError:  # pragma: no cover
            self.sklearn_available = False

    def test_random_forest(self):
        if not self.sklearn_available:  # pragma: no cover
            self.skipTest("sklearn not installed")
        from data_ai.tc_predictor import _build_model

        model = _build_model("RandomForest", 42, 50)
        self.assertEqual(model.n_estimators, 50)

    def test_gradient_boosting(self):
        if not self.sklearn_available:  # pragma: no cover
            self.skipTest("sklearn not installed")
        from data_ai.tc_predictor import _build_model

        model = _build_model("GradientBoosting", 42, 50)
        self.assertEqual(model.n_estimators, 50)

    def test_svr(self):
        if not self.sklearn_available:  # pragma: no cover
            self.skipTest("sklearn not installed")
        from data_ai.tc_predictor import _build_model

        model = _build_model("SVR", 42, 50)
        self.assertEqual(model.kernel, "rbf")

    def test_unknown_raises(self):
        if not self.sklearn_available:  # pragma: no cover
            self.skipTest("sklearn not installed")
        from data_ai.tc_predictor import _build_model

        with self.assertRaises(ValueError):
            _build_model("Unknown", 42, 50)


class TestTrainAndEvaluate(unittest.TestCase):
    """train_and_evaluate 함수 통합 테스트 (sklearn + pandas 의존)."""

    def setUp(self):
        try:
            import numpy  # noqa: F401
            import pandas  # noqa: F401
            import sklearn  # noqa: F401

            self.deps_available = True
        except ImportError:  # pragma: no cover
            self.deps_available = False

    def _make_df(self):
        import numpy as np
        import pandas as pd

        rng = np.random.default_rng(42)
        n = 100
        return pd.DataFrame(
            {
                "density": rng.uniform(2, 12, n),
                "atomic_mass": rng.uniform(20, 210, n),
                "electron_affinity": rng.uniform(10, 200, n),
                "thermal_conductivity": rng.uniform(0.1, 500, n),
                "valence": rng.integers(1, 8, n).astype(float),
                "electronegativity": rng.uniform(0.7, 3.5, n),
                "critical_temp": rng.uniform(0.5, 150, n),
            }
        )

    def test_rf_returns_metrics(self):
        if not self.deps_available:  # pragma: no cover
            self.skipTest("sklearn/pandas not installed")
        from data_ai.tc_predictor import train_and_evaluate

        df = self._make_df()
        result = train_and_evaluate(df, "RandomForest")
        self.assertIn("r2", result)
        self.assertIn("mae", result)
        self.assertIn("rmse", result)
        self.assertIn("importances", result)
        self.assertEqual(len(result["importances"]), 6)

    def test_gbr_returns_metrics(self):
        if not self.deps_available:  # pragma: no cover
            self.skipTest("sklearn/pandas not installed")
        from data_ai.tc_predictor import train_and_evaluate

        df = self._make_df()
        result = train_and_evaluate(df, "GradientBoosting")
        self.assertIn("r2", result)
        self.assertIsNotNone(result["model"])

    def test_svr_has_scaler(self):
        if not self.deps_available:  # pragma: no cover
            self.skipTest("sklearn/pandas not installed")
        from data_ai.tc_predictor import train_and_evaluate

        df = self._make_df()
        result = train_and_evaluate(df, "SVR")
        self.assertIsNotNone(result["scaler"], "SVR should use StandardScaler")

    def test_rf_no_scaler(self):
        if not self.deps_available:  # pragma: no cover
            self.skipTest("sklearn/pandas not installed")
        from data_ai.tc_predictor import train_and_evaluate

        df = self._make_df()
        result = train_and_evaluate(df, "RandomForest")
        self.assertIsNone(result["scaler"], "RF should not use scaler")


class TestGenerateSupercon(unittest.TestCase):
    """generate_supercon 함수 테스트 (numpy + pandas 의존)."""

    def setUp(self):
        try:
            import numpy  # noqa: F401
            import pandas  # noqa: F401

            self.deps_available = True
        except ImportError:  # pragma: no cover
            self.deps_available = False

    def test_generates_csv(self):
        if not self.deps_available:  # pragma: no cover
            self.skipTest("numpy/pandas not installed")
        import pandas as pd

        from data_ai.generate_sample_data import SUPERCON_PATH, generate_supercon

        path = generate_supercon()
        self.assertEqual(path, SUPERCON_PATH)
        self.assertTrue(os.path.exists(path))
        df = pd.read_csv(path)
        # 실제 화합물(33) + 합성(295) = 328+
        self.assertGreater(len(df), 300)
        # 필수 컬럼 확인
        for col in (
            "density",
            "atomic_mass",
            "electron_affinity",
            "thermal_conductivity",
            "valence",
            "electronegativity",
            "critical_temp",
            "name",
        ):
            self.assertIn(col, df.columns, f"Missing column: {col}")

    def test_tc_range(self):
        """SuperCon 데이터의 Tc 범위가 넓어야 한다 (0~260K)."""
        if not self.deps_available:  # pragma: no cover
            self.skipTest("numpy/pandas not installed")
        import pandas as pd

        from data_ai.generate_sample_data import SUPERCON_PATH, generate_supercon

        generate_supercon()
        df = pd.read_csv(SUPERCON_PATH)
        self.assertGreater(df["critical_temp"].max(), 200, "Should include high-Tc hydrides")
        self.assertLess(df["critical_temp"].min(), 1, "Should include low-Tc elements")


if __name__ == "__main__":
    unittest.main()
