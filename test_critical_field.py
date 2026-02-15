"""임계 자기장 체스 전략 시뮬레이션 테스트."""

import pytest

from critical_field import (
    critical_field, check_state,
    generate_phase_board, format_board, show_board,
    count_states, find_boundary, find_best_move, find_critical_moves,
    show_strategy_analysis, show_single_check,
    run_critical_field_simulation, MATERIALS,
)


# ── 핵심 공식 테스트 ─────────────────────────────────────


class TestCriticalField:
    """critical_field() 함수 테스트."""

    def test_zero_temperature(self):
        """T=0에서 Bc = B0이다."""
        assert critical_field(0, 4.2, 0.04) == pytest.approx(0.04)

    def test_at_tc(self):
        """T=Tc에서 Bc = 0이다."""
        assert critical_field(4.2, 4.2, 0.04) == pytest.approx(0.0)

    def test_above_tc(self):
        """T > Tc에서 Bc = 0이다."""
        assert critical_field(10.0, 4.2, 0.04) == pytest.approx(0.0)

    def test_half_tc(self):
        """T = Tc/2에서 Bc = B0 * 0.75이다."""
        T_c, B_0 = 4.2, 0.04
        expected = B_0 * (1 - (0.5) ** 2)  # 0.75 * B_0
        assert critical_field(T_c / 2, T_c, B_0) == pytest.approx(expected)

    def test_near_tc(self):
        """T ≈ Tc에서 Bc ≈ 0이다."""
        T_c, B_0 = 9.26, 0.206
        result = critical_field(9.25, T_c, B_0)
        assert result > 0
        assert result < 0.001  # 매우 작은 값

    def test_different_materials(self):
        """서로 다른 물질에서 올바른 값을 반환한다."""
        # Nb: Tc=9.26, B0=0.206
        assert critical_field(0, 9.26, 0.206) == pytest.approx(0.206)
        # YBCO: Tc=93, B0=100
        assert critical_field(0, 93.0, 100.0) == pytest.approx(100.0)


# ── 상태 판별 테스트 ─────────────────────────────────────


class TestCheckState:
    """check_state() 함수 테스트."""

    def test_superconducting_low_t_low_b(self):
        """낮은 T, 낮은 B → 1 (초전도)."""
        assert check_state(1.0, 0.01, 4.2, 0.04) == 1

    def test_normal_high_t(self):
        """T >= Tc → 0 (일반)."""
        assert check_state(4.2, 0.0, 4.2, 0.04) == 0

    def test_normal_high_b(self):
        """B >= Bc → 0 (일반)."""
        assert check_state(0.0, 0.04, 4.2, 0.04) == 0

    def test_normal_above_tc(self):
        """T > Tc → 0 (일반)."""
        assert check_state(10.0, 0.0, 4.2, 0.04) == 0

    def test_zero_zero(self):
        """T=0, B=0 → 1 (초전도)."""
        assert check_state(0.0, 0.0, 4.2, 0.04) == 1

    def test_negative_t(self):
        """음수 온도 → 0 (잘못된 입력)."""
        assert check_state(-1.0, 0.01, 4.2, 0.04) == 0

    def test_negative_b(self):
        """음수 자기장 → 0 (잘못된 입력)."""
        assert check_state(1.0, -0.01, 4.2, 0.04) == 0

    def test_boundary_exact(self):
        """정확히 경계선 위 (B == Bc) → 0 (일반)."""
        T_c, B_0 = 4.2, 0.04
        B_c = critical_field(2.0, T_c, B_0)
        assert check_state(2.0, B_c, T_c, B_0) == 0


# ── 체스판 생성 테스트 ───────────────────────────────────


class TestGeneratePhaseBoard:
    """generate_phase_board() 함수 테스트."""

    def test_returns_correct_dimensions(self):
        """지정한 크기의 보드를 반환한다."""
        board, t_vals, b_vals = generate_phase_board(4.2, 0.04, 8, 6)
        assert len(board) == 6  # 행 = b_steps
        assert len(board[0]) == 8  # 열 = t_steps
        assert len(t_vals) == 8
        assert len(b_vals) == 6

    def test_board_contains_only_0_and_1(self):
        """보드의 모든 값이 0 또는 1이다."""
        board, _, _ = generate_phase_board(9.26, 0.206, 10, 10)
        for row in board:
            for cell in row:
                assert cell in (0, 1)

    def test_top_left_is_superconducting(self):
        """좌상단 (T=0, B 낮음) 영역은 초전도일 수 있다."""
        # T=0이고 B가 충분히 낮으면 초전도
        board, t_vals, b_vals = generate_phase_board(9.26, 0.206, 10, 10)
        # T=0 열(j=0), B가 가장 낮은 행(마지막 행)
        assert board[-1][0] == 1

    def test_bottom_right_is_normal(self):
        """우하단 (T 높음) 영역은 일반 상태이다."""
        board, t_vals, b_vals = generate_phase_board(4.2, 0.04, 10, 10)
        # T가 가장 높은 열(마지막)은 Tc에 가까움
        # 마지막 열의 상단(B 높음)은 확실히 일반
        assert board[0][-1] == 0

    def test_t_values_ascending(self):
        """온도 값이 오름차순이다."""
        _, t_vals, _ = generate_phase_board(4.2, 0.04, 10, 10)
        assert t_vals == sorted(t_vals)

    def test_b_values_descending(self):
        """자기장 값이 내림차순이다."""
        _, _, b_vals = generate_phase_board(4.2, 0.04, 10, 10)
        assert b_vals == sorted(b_vals, reverse=True)

    def test_small_board(self):
        """3×3 최소 크기 보드가 생성된다."""
        board, t_vals, b_vals = generate_phase_board(4.2, 0.04, 3, 3)
        assert len(board) == 3
        assert len(board[0]) == 3


# ── 보드 출력 테스트 ─────────────────────────────────────


class TestFormatBoard:
    """format_board(), show_board() 함수 테스트."""

    def test_format_contains_symbols(self):
        """포맷에 ■(초전도)와 ·(일반) 기호가 포함된다."""
        board, t_vals, b_vals = generate_phase_board(9.26, 0.206, 5, 5)
        result = format_board(board, t_vals, b_vals, 9.26, 0.206)
        # 보드에 초전도 영역이 있으므로 ■가 있어야 함
        assert "■" in result
        assert "·" in result

    def test_format_contains_legend(self):
        """범례가 포함된다."""
        board, t_vals, b_vals = generate_phase_board(4.2, 0.04, 5, 5)
        result = format_board(board, t_vals, b_vals, 4.2, 0.04)
        assert "초전도" in result
        assert "일반" in result

    def test_show_board_prints(self, capsys):
        """show_board()가 화면에 출력한다."""
        board, t_vals, b_vals = generate_phase_board(4.2, 0.04, 5, 5)
        show_board(board, t_vals, b_vals, 4.2, 0.04)
        output = capsys.readouterr().out
        assert "■" in output or "·" in output


# ── 전략 분석 테스트 ─────────────────────────────────────


class TestCountStates:
    """count_states() 함수 테스트."""

    def test_total_equals_board_size(self):
        """초전도 + 일반 = 전체 칸 수."""
        board, _, _ = generate_phase_board(9.26, 0.206, 8, 8)
        sc, nm = count_states(board)
        assert sc + nm == 64

    def test_has_both_states(self):
        """보드에 초전도와 일반 상태가 모두 존재한다."""
        board, _, _ = generate_phase_board(9.26, 0.206, 10, 10)
        sc, nm = count_states(board)
        assert sc > 0
        assert nm > 0

    def test_all_normal_board(self):
        """모든 칸이 일반 상태인 보드."""
        # Tc와 B0이 극히 작으면 거의 모든 칸이 일반
        board = [[0, 0], [0, 0]]
        sc, nm = count_states(board)
        assert sc == 0
        assert nm == 4


class TestFindBoundary:
    """find_boundary() 함수 테스트."""

    def test_returns_list(self):
        """리스트를 반환한다."""
        board, t_vals, b_vals = generate_phase_board(9.26, 0.206, 10, 10)
        boundary = find_boundary(board, t_vals, b_vals)
        assert isinstance(boundary, list)

    def test_boundary_has_tuples(self):
        """경계선 요소가 (T, B) 튜플이다."""
        board, t_vals, b_vals = generate_phase_board(9.26, 0.206, 10, 10)
        boundary = find_boundary(board, t_vals, b_vals)
        assert len(boundary) > 0
        for item in boundary:
            assert len(item) == 2

    def test_boundary_t_values_match(self):
        """경계선의 T 값이 보드의 t_values에 포함된다."""
        board, t_vals, b_vals = generate_phase_board(9.26, 0.206, 10, 10)
        boundary = find_boundary(board, t_vals, b_vals)
        for t, b in boundary:
            assert t in t_vals


class TestFindBestMove:
    """find_best_move() 함수 테스트."""

    def test_returns_dict(self):
        """딕셔너리를 반환한다."""
        T_c, B_0 = 9.26, 0.206
        board, t_vals, b_vals = generate_phase_board(T_c, B_0, 10, 10)
        best = find_best_move(board, t_vals, b_vals, T_c, B_0)
        assert best is not None
        assert "T" in best
        assert "B" in best
        assert "안전도" in best

    def test_best_move_is_superconducting(self):
        """최적의 수는 초전도 상태여야 한다."""
        T_c, B_0 = 9.26, 0.206
        board, t_vals, b_vals = generate_phase_board(T_c, B_0, 10, 10)
        best = find_best_move(board, t_vals, b_vals, T_c, B_0)
        assert check_state(best["T"], best["B"], T_c, B_0) == 1

    def test_best_move_has_positive_margins(self):
        """최적의 수는 양의 마진을 가진다."""
        T_c, B_0 = 9.26, 0.206
        board, t_vals, b_vals = generate_phase_board(T_c, B_0, 10, 10)
        best = find_best_move(board, t_vals, b_vals, T_c, B_0)
        assert best["마진_T"] > 0
        assert best["마진_B"] > 0
        assert best["안전도"] > 0

    def test_returns_none_for_all_normal(self):
        """초전도 칸이 없으면 None을 반환한다."""
        board = [[0, 0], [0, 0]]
        best = find_best_move(board, [0, 1], [1, 0], 1.0, 1.0)
        assert best is None


class TestFindCriticalMoves:
    """find_critical_moves() 함수 테스트."""

    def test_returns_list(self):
        """리스트를 반환한다."""
        board, t_vals, b_vals = generate_phase_board(9.26, 0.206, 10, 10)
        critical = find_critical_moves(board, t_vals, b_vals)
        assert isinstance(critical, list)

    def test_critical_moves_are_superconducting(self):
        """위험한 수는 초전도 칸이다."""
        T_c, B_0 = 9.26, 0.206
        board, t_vals, b_vals = generate_phase_board(T_c, B_0, 10, 10)
        critical = find_critical_moves(board, t_vals, b_vals)
        for t, b in critical:
            assert check_state(t, b, T_c, B_0) == 1

    def test_critical_moves_adjacent_to_normal(self):
        """위험한 수는 일반 칸에 인접해 있다."""
        # 수동 검증: 작은 보드에서 확인
        board = [[0, 0], [1, 0]]
        t_vals = [0.0, 1.0]
        b_vals = [1.0, 0.0]
        critical = find_critical_moves(board, t_vals, b_vals)
        # (0.0, 0.0)은 초전도이고 인접에 0이 있음
        assert (0.0, 0.0) in critical


# ── 전략 분석 출력 테스트 ─────────────────────────────────


class TestShowStrategyAnalysis:
    """show_strategy_analysis() 출력 테스트."""

    def test_shows_statistics(self, capsys):
        """통계 정보가 출력된다."""
        T_c, B_0 = 9.26, 0.206
        board, t_vals, b_vals = generate_phase_board(T_c, B_0, 10, 10)
        show_strategy_analysis(board, t_vals, b_vals, T_c, B_0)
        output = capsys.readouterr().out
        assert "전략 분석" in output
        assert "초전도 영역" in output
        assert "점유율" in output

    def test_shows_best_move(self, capsys):
        """최적의 수가 출력된다."""
        T_c, B_0 = 9.26, 0.206
        board, t_vals, b_vals = generate_phase_board(T_c, B_0, 10, 10)
        show_strategy_analysis(board, t_vals, b_vals, T_c, B_0)
        output = capsys.readouterr().out
        assert "최적의 수" in output
        assert "안전도" in output

    def test_shows_boundary(self, capsys):
        """경계선이 출력된다."""
        T_c, B_0 = 9.26, 0.206
        board, t_vals, b_vals = generate_phase_board(T_c, B_0, 10, 10)
        show_strategy_analysis(board, t_vals, b_vals, T_c, B_0)
        output = capsys.readouterr().out
        assert "경계선" in output


# ── 단일 좌표 판별 테스트 ─────────────────────────────────


class TestShowSingleCheck:
    """show_single_check() 함수 테스트."""

    def test_superconducting_check(self, monkeypatch, capsys):
        """초전도 상태 좌표를 올바르게 출력한다."""
        inputs = iter(["1.0", "0.01"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        show_single_check(4.2, 0.04)
        output = capsys.readouterr().out
        assert "[1]" in output
        assert "초전도" in output

    def test_normal_check(self, monkeypatch, capsys):
        """일반 상태 좌표를 올바르게 출력한다."""
        inputs = iter(["10.0", "0.01"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        show_single_check(4.2, 0.04)
        output = capsys.readouterr().out
        assert "[0]" in output
        assert "일반" in output

    def test_invalid_input(self, monkeypatch, capsys):
        """잘못된 입력 시 오류 메시지."""
        inputs = iter(["abc", "0.01"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        show_single_check(4.2, 0.04)
        output = capsys.readouterr().out
        assert "오류" in output


# ── 물질 목록 테스트 ─────────────────────────────────────


class TestMaterials:
    """MATERIALS 딕셔너리 테스트."""

    def test_has_standard_materials(self):
        """표준 초전도체 물질이 포함되어 있다."""
        assert "Hg" in MATERIALS
        assert "Nb" in MATERIALS
        assert "YBCO" in MATERIALS

    def test_each_has_tc_and_b0(self):
        """각 물질에 T_c, B_0, 이름이 있다."""
        for key, mat in MATERIALS.items():
            assert "T_c" in mat
            assert "B_0" in mat
            assert "이름" in mat
            assert mat["T_c"] > 0
            assert mat["B_0"] > 0


# ── 대화형 실행 테스트 ───────────────────────────────────


class TestRunCriticalFieldSimulation:
    """run_critical_field_simulation() 대화형 실행 테스트."""

    def test_default_material_and_exit(self, monkeypatch, capsys):
        """기본 물질(Nb) 선택 → 보드 출력 → 종료."""
        inputs = iter(["3", "5", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_critical_field_simulation()
        output = capsys.readouterr().out
        assert "체스 전략" in output
        assert "■" in output
        assert "전략 분석" in output

    def test_select_ybco(self, monkeypatch, capsys):
        """YBCO 선택 → 보드 출력."""
        inputs = iter(["7", "5", "0"])  # 7번 = YBCO
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_critical_field_simulation()
        output = capsys.readouterr().out
        assert "YBCO" in output

    def test_custom_material(self, monkeypatch, capsys):
        """직접 입력으로 사용자 정의 물질."""
        inputs = iter(["0", "10.0", "0.5", "5", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_critical_field_simulation()
        output = capsys.readouterr().out
        assert "사용자 정의" in output

    def test_single_check_menu(self, monkeypatch, capsys):
        """추가 분석 → 좌표 판별."""
        inputs = iter(["3", "5", "1", "1.0", "0.05", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_critical_field_simulation()
        output = capsys.readouterr().out
        assert "좌표" in output

    def test_resize_board(self, monkeypatch, capsys):
        """추가 분석 → 보드 크기 변경."""
        inputs = iter(["3", "5", "3", "8", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_critical_field_simulation()
        output = capsys.readouterr().out
        assert "8×8" in output

    def test_change_material(self, monkeypatch, capsys):
        """추가 분석 → 물질 변경."""
        inputs = iter(["3", "5", "4", "1", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_critical_field_simulation()
        output = capsys.readouterr().out
        assert "Hg" in output

    def test_review_board(self, monkeypatch, capsys):
        """추가 분석 → 보드 다시 보기."""
        inputs = iter(["3", "5", "2", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_critical_field_simulation()
        output = capsys.readouterr().out
        # 보드가 두 번 출력됨 (초기 + 다시 보기)
        assert output.count("전략 분석") >= 2

    def test_invalid_menu(self, monkeypatch, capsys):
        """잘못된 메뉴 번호."""
        inputs = iter(["3", "5", "99", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_critical_field_simulation()
        output = capsys.readouterr().out
        assert "올바른 번호" in output

    def test_invalid_custom_input(self, monkeypatch, capsys):
        """직접 입력에서 숫자가 아닌 값."""
        inputs = iter(["0", "abc", "0.5"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        run_critical_field_simulation()
        output = capsys.readouterr().out
        assert "오류" in output
