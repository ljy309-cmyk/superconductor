"""초전도체 상태 변화 판독기 테스트."""

import pytest
from superconductor import critical_magnetic_field, determine_state, MATERIALS


# ── critical_magnetic_field 테스트 ──────────────────────


class TestCriticalMagneticField:
    """임계 자기장 곡선 B_c(T) = B_0 * [1 - (T/T_c)^2] 테스트."""

    def test_at_zero_kelvin(self):
        """T=0K 이면 B_c = B_0."""
        assert critical_magnetic_field(0, T_c=9.26, B_0=0.1991) == pytest.approx(0.1991)

    def test_at_critical_temperature(self):
        """T=T_c 이면 B_c = 0."""
        assert critical_magnetic_field(9.26, T_c=9.26, B_0=0.1991) == 0.0

    def test_above_critical_temperature(self):
        """T > T_c 이면 B_c = 0."""
        assert critical_magnetic_field(15.0, T_c=9.26, B_0=0.1991) == 0.0

    def test_mid_temperature(self):
        """T_c 의 절반 온도에서의 임계 자기장 확인."""
        T_c = 10.0
        B_0 = 0.2
        T = 5.0  # T/T_c = 0.5 → B_c = 0.2 * (1 - 0.25) = 0.15
        assert critical_magnetic_field(T, T_c, B_0) == pytest.approx(0.15)

    def test_negative_temperature_raises(self):
        """음수 온도는 ValueError."""
        with pytest.raises(ValueError, match="0K 이상"):
            critical_magnetic_field(-1, T_c=9.26, B_0=0.1991)

    def test_lead_values(self):
        """납(Pb)의 실제 값으로 계산 확인."""
        Pb = MATERIALS["Pb"]
        T = 3.0
        expected = Pb["B_0"] * (1 - (T / Pb["T_c"]) ** 2)
        assert critical_magnetic_field(T, Pb["T_c"], Pb["B_0"]) == pytest.approx(expected)


# ── determine_state 테스트 ──────────────────────────────


class TestDetermineState:
    """초전도 / 일반 상태 판별 테스트."""

    T_c = 10.0
    B_0 = 0.2

    def test_superconducting_state(self):
        """낮은 온도 + 낮은 자기장 → 초전도 상태."""
        state, _ = determine_state(T=2.0, B=0.01, T_c=self.T_c, B_0=self.B_0)
        assert "초전도" in state

    def test_normal_state_high_temperature(self):
        """높은 온도 → 일반 상태."""
        state, _ = determine_state(T=12.0, B=0.0, T_c=self.T_c, B_0=self.B_0)
        assert "일반" in state

    def test_normal_state_high_field(self):
        """높은 자기장 → 일반 상태."""
        state, _ = determine_state(T=2.0, B=0.5, T_c=self.T_c, B_0=self.B_0)
        assert "일반" in state

    def test_boundary_at_critical_temperature(self):
        """T = T_c 경계 → 일반 상태."""
        state, B_c = determine_state(T=self.T_c, B=0.0, T_c=self.T_c, B_0=self.B_0)
        assert "일반" in state
        assert B_c == 0.0

    def test_boundary_at_critical_field(self):
        """B = B_c 경계 → 일반 상태 (같을 때는 초전도 아님)."""
        T = 5.0
        B_c_expected = self.B_0 * (1 - (T / self.T_c) ** 2)
        state, B_c = determine_state(T=T, B=B_c_expected, T_c=self.T_c, B_0=self.B_0)
        assert "일반" in state
        assert B_c == pytest.approx(B_c_expected)

    def test_just_below_boundary(self):
        """B_c 바로 아래 → 초전도 상태."""
        T = 5.0
        B_c_val = self.B_0 * (1 - (T / self.T_c) ** 2)
        state, _ = determine_state(T=T, B=B_c_val - 1e-10, T_c=self.T_c, B_0=self.B_0)
        assert "초전도" in state

    def test_negative_field_raises(self):
        """음수 자기장은 ValueError."""
        with pytest.raises(ValueError, match="0T 이상"):
            determine_state(T=2.0, B=-0.1, T_c=self.T_c, B_0=self.B_0)

    def test_returns_critical_field_value(self):
        """반환된 B_c 값이 올바른지 확인."""
        T = 3.0
        _, B_c = determine_state(T=T, B=0.01, T_c=self.T_c, B_0=self.B_0)
        expected = self.B_0 * (1 - (T / self.T_c) ** 2)
        assert B_c == pytest.approx(expected)


# ── 실제 물질 데이터 통합 테스트 ────────────────────────


class TestWithRealMaterials:
    """MATERIALS 딕셔너리의 실제 물질값을 사용한 통합 테스트."""

    def test_all_materials_superconducting_at_zero(self):
        """모든 물질: T=0K, B=0T → 초전도 상태."""
        for symbol, mat in MATERIALS.items():
            state, B_c = determine_state(0, 0, mat["T_c"], mat["B_0"])
            assert "초전도" in state, f"{symbol} 실패"
            assert B_c == pytest.approx(mat["B_0"])

    def test_all_materials_normal_above_tc(self):
        """모든 물질: T > T_c → 일반 상태."""
        for symbol, mat in MATERIALS.items():
            state, _ = determine_state(mat["T_c"] + 1, 0, mat["T_c"], mat["B_0"])
            assert "일반" in state, f"{symbol} 실패"

    def test_niobium_mid_range(self):
        """나이오븀(Nb): T=4K, B=0.05T 에서의 판별."""
        Nb = MATERIALS["Nb"]
        B_c = Nb["B_0"] * (1 - (4.0 / Nb["T_c"]) ** 2)
        # B_c ≈ 0.1991 * (1 - 0.1866) ≈ 0.1619
        state, returned_B_c = determine_state(4.0, 0.05, Nb["T_c"], Nb["B_0"])
        assert "초전도" in state
        assert returned_B_c == pytest.approx(B_c)
