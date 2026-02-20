"""터널링 업적 연동 통합 테스트.

check_achievements("tunneling", ...) 호출 시 8개 터널링 업적의
해금 조건, 경계값, 중복 방지, 파일 저장을 체계적으로 검증합니다.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# GUI 의존성 mock
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

from achievements import _T, ACHIEVEMENTS, check_achievements


def _tn_ach(ach_id: str) -> dict:
    """터널링 업적 1개를 ID로 조회."""
    return next(a for a in ACHIEVEMENTS if a["id"] == ach_id)


def _make_session(**kwargs) -> dict:
    """터널링 세션 데이터를 생성하는 헬퍼.

    기본값: 아무 업적도 해금되지 않는 최소 데이터.
    """
    defaults = {
        "total_attempts": 0,
        "tunnel_count": 0,
        "reflect_count": 0,
        "tunnel_rate": 0.0,
        "barrier_width": 12,
        "tunnel_prob": 0.10,
        "elapsed_time": 120.0,
        "max_tunnel_barrier": 0,
        "barrier_configs_tried": 0,
        "peak_rate": 0.0,
        "avg_barrier_width": 12.0,
        "trials_per_minute": 0.0,
        "speed_mult": 1.0,
        "difficulty": "normal",
        "trial_history": [],
    }
    defaults.update(kwargs)
    return defaults


# ═══════════════════════════════════════════════════════
# 1. 개별 업적 조건 람다 검증
# ═══════════════════════════════════════════════════════


class TestTnFirstTunnel(unittest.TestCase):
    """tn_first_tunnel: 첫 터널링 성공 (tunnel_count >= 1)."""

    def setUp(self):
        self.ach = _tn_ach("tn_first_tunnel")

    def test_zero_tunnels_not_unlocked(self):
        self.assertFalse(self.ach["condition"](_make_session(tunnel_count=0)))

    def test_one_tunnel_unlocks(self):
        self.assertTrue(self.ach["condition"](_make_session(tunnel_count=1)))

    def test_many_tunnels_unlocks(self):
        self.assertTrue(self.ach["condition"](_make_session(tunnel_count=999)))

    def test_empty_dict_safe(self):
        self.assertFalse(self.ach["condition"]({}))


class TestTnLucky10(unittest.TestCase):
    """tn_lucky_10: 터널링 10회 성공 (tunnel_count >= 10)."""

    def setUp(self):
        self.ach = _tn_ach("tn_lucky_10")
        self.threshold = _T["tn_tunnel_streak"]

    def test_below_threshold(self):
        self.assertFalse(self.ach["condition"](_make_session(tunnel_count=self.threshold - 1)))

    def test_at_threshold(self):
        self.assertTrue(self.ach["condition"](_make_session(tunnel_count=self.threshold)))

    def test_above_threshold(self):
        self.assertTrue(self.ach["condition"](_make_session(tunnel_count=self.threshold + 50)))


class TestTnRate50(unittest.TestCase):
    """tn_rate_50: 성공률 50% AND 최소 시행 10회."""

    def setUp(self):
        self.ach = _tn_ach("tn_rate_50")
        self.rate = _T["tn_rate_threshold"]
        self.min_att = _T["tn_rate_min_attempts"]

    def test_high_rate_but_too_few_attempts(self):
        """성공률은 충분하지만 시행 횟수 부족 → 미해금."""
        self.assertFalse(self.ach["condition"](_make_session(tunnel_rate=0.9, total_attempts=self.min_att - 1)))

    def test_enough_attempts_but_low_rate(self):
        """시행 횟수는 충분하지만 성공률 부족 → 미해금."""
        self.assertFalse(
            self.ach["condition"](_make_session(tunnel_rate=self.rate - 0.01, total_attempts=self.min_att))
        )

    def test_exact_boundary(self):
        """정확히 경계값 → 해금."""
        self.assertTrue(self.ach["condition"](_make_session(tunnel_rate=self.rate, total_attempts=self.min_att)))

    def test_both_exceeded(self):
        self.assertTrue(self.ach["condition"](_make_session(tunnel_rate=0.8, total_attempts=100)))


class TestTnRate75(unittest.TestCase):
    """tn_rate_75: 성공률 75% AND 최소 시행 10회."""

    def setUp(self):
        self.ach = _tn_ach("tn_rate_75")
        self.rate = _T["tn_rate_high"]
        self.min_att = _T["tn_rate_min_attempts"]

    def test_below_rate(self):
        self.assertFalse(self.ach["condition"](_make_session(tunnel_rate=self.rate - 0.01, total_attempts=50)))

    def test_at_boundary(self):
        self.assertTrue(self.ach["condition"](_make_session(tunnel_rate=self.rate, total_attempts=self.min_att)))

    def test_too_few_attempts(self):
        self.assertFalse(self.ach["condition"](_make_session(tunnel_rate=1.0, total_attempts=self.min_att - 1)))


class TestTnSpeedRun(unittest.TestCase):
    """tn_speed_run: 30초 이내 20회 터널링."""

    def setUp(self):
        self.ach = _tn_ach("tn_speed_run")
        self.count = _T["tn_speed_run_count"]
        self.time_limit = _T["tn_speed_run_time"]

    def test_fast_enough_and_enough_tunnels(self):
        self.assertTrue(self.ach["condition"](_make_session(tunnel_count=self.count, elapsed_time=self.time_limit)))

    def test_enough_tunnels_but_too_slow(self):
        self.assertFalse(
            self.ach["condition"](_make_session(tunnel_count=self.count, elapsed_time=self.time_limit + 0.1))
        )

    def test_fast_but_not_enough_tunnels(self):
        self.assertFalse(self.ach["condition"](_make_session(tunnel_count=self.count - 1, elapsed_time=10.0)))

    def test_very_fast_run(self):
        self.assertTrue(self.ach["condition"](_make_session(tunnel_count=50, elapsed_time=5.0)))


class TestTnQuantumAdvantage(unittest.TestCase):
    """tn_quantum_advantage: 실측 성공률 > 이론 확률 AND 최소 20회 시행."""

    def setUp(self):
        self.ach = _tn_ach("tn_quantum_advantage")
        self.min_att = _T["tn_qa_min_attempts"]

    def test_rate_exceeds_prob(self):
        """실측 > 이론 + 충분한 시행 → 해금."""
        self.assertTrue(
            self.ach["condition"](_make_session(tunnel_rate=0.15, tunnel_prob=0.10, total_attempts=self.min_att))
        )

    def test_rate_equals_prob(self):
        """실측 == 이론 → 미해금 (> 이어야 함)."""
        self.assertFalse(
            self.ach["condition"](_make_session(tunnel_rate=0.10, tunnel_prob=0.10, total_attempts=self.min_att))
        )

    def test_rate_below_prob(self):
        self.assertFalse(self.ach["condition"](_make_session(tunnel_rate=0.05, tunnel_prob=0.10, total_attempts=50)))

    def test_exceeds_but_too_few_attempts(self):
        self.assertFalse(
            self.ach["condition"](_make_session(tunnel_rate=0.90, tunnel_prob=0.10, total_attempts=self.min_att - 1))
        )

    def test_edge_case_very_small_advantage(self):
        """극소 차이라도 초과 시 해금."""
        self.assertTrue(
            self.ach["condition"](_make_session(tunnel_rate=0.1001, tunnel_prob=0.10, total_attempts=self.min_att))
        )


class TestTnCompareMaster(unittest.TestCase):
    """tn_compare_master: 3가지 이상 장벽 설정 비교."""

    def setUp(self):
        self.ach = _tn_ach("tn_compare_master")
        self.threshold = _T["tn_compare_configs"]

    def test_below_threshold(self):
        self.assertFalse(self.ach["condition"](_make_session(barrier_configs_tried=self.threshold - 1)))

    def test_at_threshold(self):
        self.assertTrue(self.ach["condition"](_make_session(barrier_configs_tried=self.threshold)))

    def test_well_above(self):
        self.assertTrue(self.ach["condition"](_make_session(barrier_configs_tried=20)))


class TestTnBarrierMaster(unittest.TestCase):
    """tn_barrier_master: 장벽 두께 100px 이상에서 터널링 성공."""

    def setUp(self):
        self.ach = _tn_ach("tn_barrier_master")
        self.threshold = _T["tn_barrier_master_width"]

    def test_below_threshold(self):
        self.assertFalse(self.ach["condition"](_make_session(max_tunnel_barrier=self.threshold - 1)))

    def test_at_threshold(self):
        self.assertTrue(self.ach["condition"](_make_session(max_tunnel_barrier=self.threshold)))

    def test_way_above(self):
        self.assertTrue(self.ach["condition"](_make_session(max_tunnel_barrier=200)))

    def test_zero_barrier(self):
        self.assertFalse(self.ach["condition"](_make_session(max_tunnel_barrier=0)))


# ═══════════════════════════════════════════════════════
# 2. check_achievements() 통합 테스트
# ═══════════════════════════════════════════════════════


class TestCheckAchievementsIntegration(unittest.TestCase):
    """check_achievements("tunneling", data) 통합 호출 검증."""

    def setUp(self):
        """각 테스트마다 빈 임시 파일로 업적 상태 초기화."""
        self._tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self._tmp.write("[]")
        self._tmp.close()
        self._patcher = patch("achievements._SAVE_PATH", self._tmp.name)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        if os.path.exists(self._tmp.name):
            os.unlink(self._tmp.name)

    def test_no_achievements_on_empty_session(self):
        """빈 세션 → 업적 0개."""
        result = check_achievements("tunneling", _make_session())
        self.assertEqual(len(result), 0)

    def test_first_tunnel_unlocks(self):
        """tunnel_count=1 → tn_first_tunnel 해금."""
        result = check_achievements("tunneling", _make_session(tunnel_count=1))
        ids = [a["id"] for a in result]
        self.assertIn("tn_first_tunnel", ids)

    def test_multiple_achievements_at_once(self):
        """한 세션에서 여러 업적 동시 해금."""
        data = _make_session(
            tunnel_count=25,
            total_attempts=30,
            tunnel_rate=25 / 30,  # ~83%
            elapsed_time=20.0,
            barrier_configs_tried=5,
            max_tunnel_barrier=120,
            tunnel_prob=0.10,
        )
        result = check_achievements("tunneling", data)
        ids = {a["id"] for a in result}

        # 이 데이터로 해금 가능한 업적들
        self.assertIn("tn_first_tunnel", ids)
        self.assertIn("tn_lucky_10", ids)
        self.assertIn("tn_rate_50", ids)
        self.assertIn("tn_rate_75", ids)
        self.assertIn("tn_speed_run", ids)
        self.assertIn("tn_quantum_advantage", ids)
        self.assertIn("tn_compare_master", ids)
        self.assertIn("tn_barrier_master", ids)

    def test_no_duplicate_unlock(self):
        """이미 해금된 업적은 다시 반환되지 않음."""
        data = _make_session(tunnel_count=1)

        first = check_achievements("tunneling", data)
        first_ids = [a["id"] for a in first]
        self.assertIn("tn_first_tunnel", first_ids)

        second = check_achievements("tunneling", data)
        second_ids = [a["id"] for a in second]
        self.assertNotIn("tn_first_tunnel", second_ids)

    def test_incremental_unlock(self):
        """세션마다 점진적으로 업적 해금."""
        # 1차: 첫 터널링만
        r1 = check_achievements("tunneling", _make_session(tunnel_count=1))
        ids1 = {a["id"] for a in r1}
        self.assertIn("tn_first_tunnel", ids1)
        self.assertNotIn("tn_lucky_10", ids1)

        # 2차: 10회 달성
        r2 = check_achievements("tunneling", _make_session(tunnel_count=15))
        ids2 = {a["id"] for a in r2}
        self.assertIn("tn_lucky_10", ids2)
        self.assertNotIn("tn_first_tunnel", ids2)  # 이미 해금됨

    def test_other_module_not_affected(self):
        """tunneling 업적만 확인, 다른 모듈 업적은 무시."""
        data = _make_session(tunnel_count=100, survival_time=999)
        result = check_achievements("tunneling", data)
        ids = [a["id"] for a in result]
        # qc_* 업적이 포함되면 안 됨
        for ach_id in ids:
            self.assertTrue(
                ach_id.startswith("tn_") or ach_id.startswith("global_"),
                f"Non-tunneling achievement leaked: {ach_id}",
            )

    def test_achievements_persisted_to_file(self):
        """업적 해금 후 JSON 파일에 저장됨."""
        check_achievements("tunneling", _make_session(tunnel_count=1))

        with open(self._tmp.name, encoding="utf-8") as f:
            saved = json.load(f)

        self.assertIn("tn_first_tunnel", saved)

    def test_pre_unlocked_not_returned(self):
        """파일에 미리 저장된 업적은 반환하지 않음."""
        with open(self._tmp.name, "w", encoding="utf-8") as f:
            json.dump(["tn_first_tunnel", "tn_lucky_10"], f)

        result = check_achievements("tunneling", _make_session(tunnel_count=50))
        ids = [a["id"] for a in result]
        self.assertNotIn("tn_first_tunnel", ids)
        self.assertNotIn("tn_lucky_10", ids)


# ═══════════════════════════════════════════════════════
# 3. 시나리오 기반 통합 테스트
# ═══════════════════════════════════════════════════════


class TestTunnelingSessionScenarios(unittest.TestCase):
    """실제 게임 플레이 시나리오 기반 업적 해금 검증."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self._tmp.write("[]")
        self._tmp.close()
        self._patcher = patch("achievements._SAVE_PATH", self._tmp.name)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        if os.path.exists(self._tmp.name):
            os.unlink(self._tmp.name)

    def test_beginner_scenario(self):
        """초보자: 3번 시도, 1번 터널링 → tn_first_tunnel만 해금."""
        data = _make_session(
            tunnel_count=1,
            reflect_count=2,
            total_attempts=3,
            tunnel_rate=1 / 3,
            elapsed_time=60.0,
            max_tunnel_barrier=12,
            barrier_configs_tried=1,
        )
        result = check_achievements("tunneling", data)
        ids = {a["id"] for a in result}
        self.assertIn("tn_first_tunnel", ids)
        self.assertNotIn("tn_lucky_10", ids)
        self.assertNotIn("tn_rate_50", ids)
        self.assertNotIn("tn_speed_run", ids)

    def test_speed_runner_scenario(self):
        """스피드런: 25초에 22번 터널링 → speed_run + first + lucky10."""
        data = _make_session(
            tunnel_count=22,
            total_attempts=40,
            tunnel_rate=22 / 40,
            elapsed_time=25.0,
            barrier_configs_tried=1,
            max_tunnel_barrier=12,
        )
        result = check_achievements("tunneling", data)
        ids = {a["id"] for a in result}
        self.assertIn("tn_first_tunnel", ids)
        self.assertIn("tn_lucky_10", ids)
        self.assertIn("tn_speed_run", ids)
        self.assertIn("tn_rate_50", ids)

    def test_experimenter_scenario(self):
        """실험가: 여러 장벽 설정 시도, 두꺼운 장벽 돌파."""
        data = _make_session(
            tunnel_count=8,
            total_attempts=50,
            tunnel_rate=8 / 50,
            elapsed_time=180.0,
            barrier_configs_tried=7,
            max_tunnel_barrier=150,
        )
        result = check_achievements("tunneling", data)
        ids = {a["id"] for a in result}
        self.assertIn("tn_first_tunnel", ids)
        self.assertIn("tn_compare_master", ids)
        self.assertIn("tn_barrier_master", ids)
        self.assertNotIn("tn_speed_run", ids)  # 시간 초과
        self.assertNotIn("tn_rate_50", ids)  # 성공률 16%

    def test_quantum_advantage_scenario(self):
        """양자 우위: 이론 확률 10%인데 실측 15%."""
        data = _make_session(
            tunnel_count=15,
            total_attempts=100,
            tunnel_rate=0.15,
            tunnel_prob=0.10,
            elapsed_time=120.0,
            barrier_configs_tried=1,
            max_tunnel_barrier=12,
        )
        result = check_achievements("tunneling", data)
        ids = {a["id"] for a in result}
        self.assertIn("tn_quantum_advantage", ids)
        self.assertIn("tn_first_tunnel", ids)
        self.assertIn("tn_lucky_10", ids)

    def test_unlucky_session(self):
        """불운한 세션: 100번 시도, 0번 터널링."""
        data = _make_session(
            tunnel_count=0,
            reflect_count=100,
            total_attempts=100,
            tunnel_rate=0.0,
            elapsed_time=300.0,
            barrier_configs_tried=1,
            max_tunnel_barrier=0,
        )
        result = check_achievements("tunneling", data)
        ids = {a["id"] for a in result}
        # 아무 업적도 해금 안 됨
        self.assertEqual(len(ids), 0)

    def test_perfect_session(self):
        """완벽한 세션: 모든 업적 동시 해금."""
        data = _make_session(
            tunnel_count=30,
            total_attempts=35,
            tunnel_rate=30 / 35,  # ~85.7%
            tunnel_prob=0.10,
            elapsed_time=25.0,
            barrier_configs_tried=5,
            max_tunnel_barrier=120,
        )
        result = check_achievements("tunneling", data)
        ids = {a["id"] for a in result}

        all_tn = {a["id"] for a in ACHIEVEMENTS if a["module"] == "tunneling"}
        self.assertEqual(ids & all_tn, all_tn, f"Missing: {all_tn - ids}")

    def test_multi_session_progressive_unlock(self):
        """여러 세션에 걸친 점진적 해금."""
        # 세션 1: 초보
        r1 = check_achievements(
            "tunneling",
            _make_session(
                tunnel_count=1,
                total_attempts=5,
                tunnel_rate=0.2,
                elapsed_time=60.0,
                barrier_configs_tried=1,
                max_tunnel_barrier=12,
            ),
        )
        ids1 = {a["id"] for a in r1}
        self.assertEqual(ids1, {"tn_first_tunnel"})

        # 세션 2: 숙련
        r2 = check_achievements(
            "tunneling",
            _make_session(
                tunnel_count=12,
                total_attempts=20,
                tunnel_rate=0.6,
                tunnel_prob=0.10,
                elapsed_time=45.0,
                barrier_configs_tried=4,
                max_tunnel_barrier=50,
            ),
        )
        ids2 = {a["id"] for a in r2}
        self.assertIn("tn_lucky_10", ids2)
        self.assertIn("tn_rate_50", ids2)
        self.assertIn("tn_quantum_advantage", ids2)
        self.assertIn("tn_compare_master", ids2)
        self.assertNotIn("tn_first_tunnel", ids2)  # 이미 해금

        # 세션 3: 마스터
        r3 = check_achievements(
            "tunneling",
            _make_session(
                tunnel_count=25,
                total_attempts=30,
                tunnel_rate=25 / 30,
                tunnel_prob=0.10,
                elapsed_time=20.0,
                barrier_configs_tried=2,
                max_tunnel_barrier=150,
            ),
        )
        ids3 = {a["id"] for a in r3}
        self.assertIn("tn_rate_75", ids3)
        self.assertIn("tn_speed_run", ids3)
        self.assertIn("tn_barrier_master", ids3)
        # 이전에 해금된 것들은 없어야 함
        self.assertNotIn("tn_first_tunnel", ids3)
        self.assertNotIn("tn_lucky_10", ids3)


# ═══════════════════════════════════════════════════════
# 4. 에지 케이스 & 방어 테스트
# ═══════════════════════════════════════════════════════


class TestAchievementEdgeCases(unittest.TestCase):
    """경계값, 타입 안전성, 파일 손상 등 에지 케이스."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self._tmp.write("[]")
        self._tmp.close()
        self._patcher = patch("achievements._SAVE_PATH", self._tmp.name)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        if os.path.exists(self._tmp.name):
            os.unlink(self._tmp.name)

    def test_all_tunneling_conditions_safe_with_empty_dict(self):
        """모든 터널링 업적 조건이 빈 dict에서 안전."""
        for ach in ACHIEVEMENTS:
            if ach["module"] != "tunneling":
                continue
            try:
                result = ach["condition"]({})
                self.assertIsInstance(result, bool)
            except Exception as e:
                self.fail(f"{ach['id']} raised {e} on empty dict")

    def test_corrupted_save_file(self):
        """손상된 저장 파일에서도 정상 동작."""
        with open(self._tmp.name, "w") as f:
            f.write("{corrupted json!!!")

        # 에러 없이 정상 동작해야 함
        result = check_achievements("tunneling", _make_session(tunnel_count=1))
        ids = [a["id"] for a in result]
        self.assertIn("tn_first_tunnel", ids)

    def test_nonexistent_save_file(self):
        """저장 파일이 없을 때도 정상 동작."""
        os.unlink(self._tmp.name)
        result = check_achievements("tunneling", _make_session(tunnel_count=1))
        ids = [a["id"] for a in result]
        self.assertIn("tn_first_tunnel", ids)

    def test_float_boundary_precision(self):
        """부동소수점 경계값 테스트."""
        ach = _tn_ach("tn_rate_50")
        rate = _T["tn_rate_threshold"]
        min_att = _T["tn_rate_min_attempts"]

        # 아주 약간 미달
        self.assertFalse(ach["condition"](_make_session(tunnel_rate=rate - 1e-10, total_attempts=min_att)))
        # 정확히 달성
        self.assertTrue(ach["condition"](_make_session(tunnel_rate=rate, total_attempts=min_att)))

    def test_speed_run_exact_time_boundary(self):
        """speed_run: elapsed_time == time_limit → 해금."""
        ach = _tn_ach("tn_speed_run")
        count = _T["tn_speed_run_count"]
        time_limit = _T["tn_speed_run_time"]

        self.assertTrue(ach["condition"](_make_session(tunnel_count=count, elapsed_time=float(time_limit))))
        self.assertFalse(ach["condition"](_make_session(tunnel_count=count, elapsed_time=float(time_limit) + 0.001)))

    def test_quantum_advantage_default_prob(self):
        """tunnel_prob 누락 시 기본값 1.0 → 해금 불가."""
        ach = _tn_ach("tn_quantum_advantage")
        # tunnel_prob가 없으면 d.get("tunnel_prob", 1.0) → 1.0
        self.assertFalse(ach["condition"]({"tunnel_rate": 0.5, "total_attempts": 100}))

    def test_achievement_structure_completeness(self):
        """모든 터널링 업적에 필수 키가 있는지 확인."""
        required_keys = {"id", "module", "title", "desc", "icon", "condition"}
        for ach in ACHIEVEMENTS:
            if ach["module"] != "tunneling":
                continue
            missing = required_keys - set(ach.keys())
            self.assertEqual(missing, set(), f"{ach['id']} missing keys: {missing}")

    def test_all_8_tunneling_achievements_exist(self):
        """터널링 업적이 정확히 8개인지 확인."""
        tn_achs = [a for a in ACHIEVEMENTS if a["module"] == "tunneling"]
        expected_ids = {
            "tn_first_tunnel",
            "tn_lucky_10",
            "tn_rate_50",
            "tn_rate_75",
            "tn_speed_run",
            "tn_quantum_advantage",
            "tn_compare_master",
            "tn_barrier_master",
        }
        actual_ids = {a["id"] for a in tn_achs}
        self.assertEqual(actual_ids, expected_ids)


if __name__ == "__main__":
    unittest.main()
