"""메인 메뉴 시스템 테스트."""

import matplotlib
matplotlib.use("Agg")
import pytest
from main import show_menu, main


class TestShowMenu:
    """메뉴 출력 확인."""

    def test_displays_all_options(self, capsys):
        """4개 프로그램 항목과 종료 옵션이 모두 표시된다."""
        show_menu()
        output = capsys.readouterr().out
        assert "1." in output
        assert "2." in output
        assert "3." in output
        assert "4." in output
        assert "0. 종료" in output

    def test_displays_title(self, capsys):
        """메뉴 상단에 프로그램 제목이 표시된다."""
        show_menu()
        output = capsys.readouterr().out
        assert "초전도체" in output


class TestMainMenu:
    """메인 메뉴 선택 동작 확인."""

    def test_select_1_runs_superconductor(self, monkeypatch, capsys):
        """1 선택 → 초전도 상태 판독기 실행 후 메뉴 복귀."""
        # 1 선택 → 온도/자기장 입력 → 0으로 종료
        inputs = iter(["1", "2", "0.01", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        main()
        output = capsys.readouterr().out
        assert "초전도 상태" in output
        assert "프로그램을 종료합니다" in output

    def test_select_2_runs_meissner(self, monkeypatch, capsys, tmp_path):
        """2 선택 → 마이스너 시뮬레이션 실행."""
        monkeypatch.chdir(tmp_path)
        inputs = iter(["2", "1.0", "10", "1.0", "1", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        main()
        output = capsys.readouterr().out
        assert "마이스너" in output
        assert "프로그램을 종료합니다" in output

    def test_select_3_runs_tc_analysis(self, monkeypatch, capsys):
        """3 선택 → 임계 온도 데이터 분석 실행."""
        # 3 선택 → 데이터소스 2(내장) → 분석 메뉴 2(통계) → 0(돌아가기) → 0(종료)
        inputs = iter(["3", "2", "2", "0", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        main()
        output = capsys.readouterr().out
        assert "총 물질 수" in output
        assert "프로그램을 종료합니다" in output

    def test_select_4_runs_ml_prediction(self, monkeypatch, capsys):
        """4 선택 → 머신러닝 Tc 예측 실행."""
        # 4 선택 → 데이터소스 2(내장) → 모델 1(랜덤포레스트) → 0(돌아가기) → 0(종료)
        inputs = iter(["4", "2", "1", "0", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        main()
        output = capsys.readouterr().out
        assert "머신러닝" in output
        assert "프로그램을 종료합니다" in output

    def test_select_0_exits(self, monkeypatch, capsys):
        """0 선택 → 즉시 종료."""
        inputs = iter(["0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        main()
        output = capsys.readouterr().out
        assert "프로그램을 종료합니다" in output

    def test_invalid_input_shows_error(self, monkeypatch, capsys):
        """잘못된 입력 → 오류 메시지 후 메뉴 반복."""
        inputs = iter(["9", "abc", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        main()
        output = capsys.readouterr().out
        assert "올바른 번호" in output
