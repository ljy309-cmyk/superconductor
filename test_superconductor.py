"""초전도체 상태 변화 판독기 테스트.

check_superconductivity()는 input()을 사용하므로,
monkeypatch로 사용자 입력을 시뮬레이션하고 capsys로 출력을 검증한다.
"""

import pytest
from superconductor import check_superconductivity


# ── 수은 기준 임계값 (프로그램에 하드코딩된 값) ──────────
T_c = 4.2   # 임계 온도 (K)
B_0 = 0.04  # 0K에서의 임계 자기장 (T)


# ── 임계 자기장 공식 검증 ────────────────────────────────


class TestCriticalFieldFormula:
    """B_c(T) = B_0 * [1 - (T/T_c)^2] 공식 검증."""

    def test_at_zero_kelvin(self):
        """T=0K → B_c = B_0."""
        B_c = B_0 * (1 - (0 / T_c)**2)
        assert B_c == pytest.approx(0.04)

    def test_at_half_tc(self):
        """T=T_c/2 → B_c = B_0 * 0.75."""
        T = T_c / 2  # 2.1K
        B_c = B_0 * (1 - (T / T_c)**2)
        assert B_c == pytest.approx(B_0 * 0.75)

    def test_near_tc(self):
        """T가 T_c에 가까우면 B_c → 0에 수렴."""
        T = 4.19
        B_c = B_0 * (1 - (T / T_c)**2)
        assert B_c > 0
        assert B_c < 0.001  # 매우 작은 값

    def test_at_tc(self):
        """T=T_c → B_c = 0."""
        B_c = B_0 * (1 - (T_c / T_c)**2)
        assert B_c == pytest.approx(0.0)


# ── 초전도 상태 판별 (프로그램 출력 검증) ────────────────


class TestSuperconductingState:
    """낮은 온도 + 낮은 자기장 → 초전도 상태."""

    def test_zero_temp_zero_field(self, monkeypatch, capsys):
        """T=0K, B=0T → 초전도 상태."""
        inputs = iter(["0", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        check_superconductivity()
        output = capsys.readouterr().out
        assert "초전도 상태" in output

    def test_low_temp_low_field(self, monkeypatch, capsys):
        """T=2K, B=0.01T → 초전도 상태."""
        inputs = iter(["2", "0.01"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        check_superconductivity()
        output = capsys.readouterr().out
        assert "초전도 상태" in output
        assert "마이스너 효과" in output

    def test_shows_critical_field_value(self, monkeypatch, capsys):
        """초전도 상태일 때 임계 자기장 한계치를 출력한다."""
        inputs = iter(["2", "0.01"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        check_superconductivity()
        output = capsys.readouterr().out
        expected_Bc = B_0 * (1 - (2.0 / T_c)**2)
        assert f"{expected_Bc:.4f}" in output


# ── 일반 상태 판별: 온도 초과 ────────────────────────────


class TestNormalStateHighTemp:
    """온도가 T_c 이상 → 일반 상태."""

    def test_above_tc(self, monkeypatch, capsys):
        """T=5K > T_c=4.2K → 일반 상태."""
        inputs = iter(["5", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        check_superconductivity()
        output = capsys.readouterr().out
        assert "일반 상태" in output
        assert "임계 온도" in output

    def test_at_tc_exactly(self, monkeypatch, capsys):
        """T=T_c 경계 → 일반 상태."""
        inputs = iter(["4.2", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        check_superconductivity()
        output = capsys.readouterr().out
        assert "일반 상태" in output

    def test_far_above_tc(self, monkeypatch, capsys):
        """T=300K (실온) → 일반 상태."""
        inputs = iter(["300", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        check_superconductivity()
        output = capsys.readouterr().out
        assert "일반 상태" in output


# ── 일반 상태 판별: 자기장 초과 ──────────────────────────


class TestNormalStateHighField:
    """온도는 낮지만 자기장이 B_c 이상 → 일반 상태."""

    def test_field_exceeds_bc(self, monkeypatch, capsys):
        """T=2K, B=0.05T > B_c → 일반 상태."""
        inputs = iter(["2", "0.05"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        check_superconductivity()
        output = capsys.readouterr().out
        assert "일반 상태" in output
        assert "초전도성이 파괴" in output

    def test_field_at_bc_exactly(self, monkeypatch, capsys):
        """B = B_c(T) 정확히 경계 → 일반 상태."""
        T = 2.0
        B_c = B_0 * (1 - (T / T_c)**2)
        inputs = iter([str(T), str(B_c)])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        check_superconductivity()
        output = capsys.readouterr().out
        assert "일반 상태" in output


# ── 입력 오류 처리 ───────────────────────────────────────


class TestInvalidInput:
    """잘못된 입력 처리 확인."""

    def test_non_numeric_temperature(self, monkeypatch, capsys):
        """온도에 문자를 입력하면 오류 메시지 출력."""
        inputs = iter(["abc", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        check_superconductivity()
        output = capsys.readouterr().out
        assert "오류" in output

    def test_non_numeric_field(self, monkeypatch, capsys):
        """자기장에 문자를 입력하면 오류 메시지 출력."""
        inputs = iter(["2", "xyz"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        check_superconductivity()
        output = capsys.readouterr().out
        assert "오류" in output


# ── 헤더 출력 확인 ───────────────────────────────────────


class TestHeaderOutput:
    """프로그램 시작 시 기준값이 출력되는지 확인."""

    def test_shows_tc_and_b0(self, monkeypatch, capsys):
        """헤더에 T_c와 B_0 기준값이 표시된다."""
        inputs = iter(["0", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        check_superconductivity()
        output = capsys.readouterr().out
        assert "Tc=4.2K" in output
        assert "B0=0.04T" in output
