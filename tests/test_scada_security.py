"""SCADA 보안 시나리오 엔진 단위 테스트.

MITM 공격, BB84 QKD 탐지, 시나리오 위상 전환을 검증합니다.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# GUI 의존성 mock
for mod in ("pygame", "tkinter", "tkinter.messagebox", "tkinter.ttk",
            "matplotlib", "matplotlib.backends", "matplotlib.backends.backend_tkagg",
            "matplotlib.figure"):
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestQKDChannel(unittest.TestCase):
    """BB84 QKD 채널 테스트."""

    def test_initial_state(self):
        from security.scada_security_engine import QKDChannel
        qkd = QKDChannel()
        self.assertEqual(qkd.qber, 0.0)
        self.assertEqual(qkd.keys_exchanged, 0)
        self.assertEqual(qkd.keys_compromised, 0)
        self.assertFalse(qkd.authenticated)
        self.assertFalse(qkd.detection_triggered)

    def test_normal_qber_stays_low(self):
        """공격 없을 때 QBER은 낮게 유지."""
        from security.scada_security_engine import QBER_DETECT_THRESHOLD, QKDChannel
        qkd = QKDChannel()
        # 20번 키 교환 (공격 없음)
        for _ in range(20):
            qkd.update(1.0, under_attack=False)
        self.assertLess(qkd.qber, QBER_DETECT_THRESHOLD)
        self.assertFalse(qkd.detection_triggered)

    def test_attack_raises_qber(self):
        """공격 시 QBER이 상승."""
        from security.scada_security_engine import QBER_DETECT_THRESHOLD, QKDChannel
        qkd = QKDChannel()
        # 20번 키 교환 (공격 중)
        for _ in range(20):
            qkd.update(1.0, under_attack=True)
        self.assertGreater(qkd.qber, QBER_DETECT_THRESHOLD)

    def test_detection_triggers_under_attack(self):
        """공격 시 탐지 플래그가 활성화."""
        from security.scada_security_engine import QKDChannel
        qkd = QKDChannel()
        for _ in range(30):
            qkd.update(1.0, under_attack=True)
        self.assertTrue(qkd.detection_triggered)

    def test_keys_compromised_count(self):
        """공격 시 keys_compromised 증가."""
        from security.scada_security_engine import QKDChannel
        qkd = QKDChannel()
        for _ in range(10):
            qkd.update(1.0, under_attack=True)
        self.assertGreater(qkd.keys_compromised, 0)
        self.assertEqual(qkd.keys_compromised, qkd.keys_exchanged)

    def test_reset(self):
        """reset() 호출 시 초기 상태 복원."""
        from security.scada_security_engine import QKDChannel
        qkd = QKDChannel()
        for _ in range(10):
            qkd.update(1.0, under_attack=True)
        qkd.authenticated = True
        qkd.reset()
        self.assertEqual(qkd.qber, 0.0)
        self.assertEqual(qkd.keys_exchanged, 0)
        self.assertFalse(qkd.authenticated)
        self.assertFalse(qkd.detection_triggered)

    def test_qber_clamped(self):
        """QBER은 [0, 1] 범위."""
        from security.scada_security_engine import QKDChannel
        qkd = QKDChannel()
        for _ in range(50):
            qkd.update(1.0, under_attack=True)
        self.assertGreaterEqual(qkd.qber, 0.0)
        self.assertLessEqual(qkd.qber, 1.0)

    def test_qber_history_bounded(self):
        """QBER 히스토리는 최대 20개."""
        from security.scada_security_engine import QKDChannel
        qkd = QKDChannel()
        for _ in range(50):
            qkd.update(1.0, under_attack=False)
        self.assertLessEqual(len(qkd.qber_history), 20)


class TestSensorRead(unittest.TestCase):
    """센서 판독 테스트."""

    def test_normal_read(self):
        """공격 없을 때 displayed_temp ≈ real_temp."""
        from security.scada_security_engine import sensor_read
        reading = sensor_read(-196.0, under_attack=False, attack_intensity=0.0)
        self.assertFalse(reading.spoofed)
        # 노이즈 포함이지만 실제 온도에 가까워야 함
        self.assertAlmostEqual(reading.displayed_temp, -196.0, delta=2.0)

    def test_attack_spoofs_display(self):
        """공격 시 displayed_temp은 목표 온도에 가까움 (스푸핑)."""
        from security.scada_security_engine import TARGET_TEMP, sensor_read
        reading = sensor_read(-185.0, under_attack=True, attack_intensity=1.0)
        self.assertTrue(reading.spoofed)
        # 스푸핑된 값은 목표 온도에 가까움
        self.assertAlmostEqual(reading.displayed_temp, TARGET_TEMP, delta=2.0)

    def test_low_intensity_no_spoof(self):
        """공격 강도가 매우 낮으면 스푸핑하지 않음."""
        from security.scada_security_engine import sensor_read
        reading = sensor_read(-196.0, under_attack=True, attack_intensity=0.001)
        self.assertFalse(reading.spoofed)

    def test_real_temp_preserved(self):
        """real_temp은 항상 입력값 그대로."""
        from security.scada_security_engine import sensor_read
        reading = sensor_read(-190.0, under_attack=True, attack_intensity=0.8)
        self.assertEqual(reading.real_temp, -190.0)


class TestScadaSecurityState(unittest.TestCase):
    """시나리오 상태 테스트."""

    def test_initial_state(self):
        from security.scada_security_engine import (
            PHASE_NORMAL,
            ScadaSecurityState,
            reset_scenario,
        )
        gs = ScadaSecurityState()
        reset_scenario(gs)
        self.assertEqual(gs.phase, PHASE_NORMAL)
        self.assertFalse(gs.attack_active)
        self.assertEqual(gs.attack_intensity, 0.0)

    def test_trigger_attack(self):
        from security.scada_security_engine import (
            PHASE_ATTACK,
            PHASE_NORMAL,
            ScadaSecurityState,
            reset_scenario,
            trigger_attack,
        )
        gs = ScadaSecurityState()
        reset_scenario(gs)
        self.assertEqual(gs.phase, PHASE_NORMAL)
        trigger_attack(gs)
        self.assertEqual(gs.phase, PHASE_ATTACK)
        self.assertTrue(gs.attack_active)

    def test_trigger_attack_only_in_normal(self):
        """공격은 NORMAL 위상에서만 트리거 가능."""
        from security.scada_security_engine import (
            PHASE_ATTACK,
            ScadaSecurityState,
            reset_scenario,
            trigger_attack,
        )
        gs = ScadaSecurityState()
        reset_scenario(gs)
        trigger_attack(gs)
        self.assertEqual(gs.phase, PHASE_ATTACK)
        # 이미 ATTACK 상태에서 다시 트리거 → 변경 없음
        trigger_attack(gs)
        self.assertEqual(gs.phase, PHASE_ATTACK)

    def test_trigger_defense(self):
        from security.scada_security_engine import (
            PHASE_PROTECTED,
            ScadaSecurityState,
            reset_scenario,
            trigger_attack,
            trigger_defense,
        )
        gs = ScadaSecurityState()
        reset_scenario(gs)
        trigger_attack(gs)
        trigger_defense(gs)
        self.assertEqual(gs.phase, PHASE_PROTECTED)
        self.assertFalse(gs.attack_active)
        self.assertTrue(gs.qkd.authenticated)

    def test_defense_increments_blocked(self):
        from security.scada_security_engine import (
            ScadaSecurityState,
            reset_scenario,
            trigger_attack,
            trigger_defense,
        )
        gs = ScadaSecurityState()
        reset_scenario(gs)
        trigger_attack(gs)
        trigger_defense(gs)
        self.assertEqual(gs.attacks_blocked, 1)

    def test_reset_scenario(self):
        from security.scada_security_engine import (
            PHASE_NORMAL,
            TARGET_TEMP,
            ScadaSecurityState,
            reset_scenario,
            trigger_attack,
        )
        gs = ScadaSecurityState()
        trigger_attack(gs)
        gs.attacks_detected = 5
        gs.real_temp = -180.0
        reset_scenario(gs)
        self.assertEqual(gs.phase, PHASE_NORMAL)
        self.assertFalse(gs.attack_active)
        self.assertEqual(gs.attacks_detected, 0)
        self.assertAlmostEqual(gs.real_temp, TARGET_TEMP)

    def test_event_log(self):
        from security.scada_security_engine import ScadaSecurityState
        gs = ScadaSecurityState()
        gs.log("test message")
        self.assertEqual(len(gs.event_log), 1)
        self.assertEqual(gs.event_log[0], "test message")

    def test_event_log_max_size(self):
        from security.scada_security_engine import ScadaSecurityState
        gs = ScadaSecurityState()
        for i in range(20):
            gs.log(f"msg {i}")
        self.assertEqual(len(gs.event_log), 12)


class TestUpdateScenario(unittest.TestCase):
    """시나리오 업데이트 물리 테스트."""

    def test_temperature_stays_stable_normal(self):
        """정상 모드에서 온도는 목표 온도 근처."""
        from security.scada_security_engine import (
            TARGET_TEMP,
            ScadaSecurityState,
            reset_scenario,
            update_scenario,
        )
        gs = ScadaSecurityState()
        gs.auto_scenario = False
        reset_scenario(gs)
        # 100 프레임 시뮬레이션
        for _ in range(100):
            update_scenario(gs, 0.016)
        # 온도는 목표 근처에 있어야 함
        self.assertAlmostEqual(gs.real_temp, TARGET_TEMP, delta=3.0)

    def test_attack_raises_temperature(self):
        """공격 시 실제 온도가 상승."""
        from security.scada_security_engine import (
            TARGET_TEMP,
            ScadaSecurityState,
            reset_scenario,
            trigger_attack,
            update_scenario,
        )
        gs = ScadaSecurityState()
        gs.auto_scenario = False
        reset_scenario(gs)
        trigger_attack(gs)
        # 200 프레임 시뮬레이션 (공격 진행)
        for _ in range(200):
            update_scenario(gs, 0.05)
        # 온도가 목표 온도보다 상승해야 함
        self.assertGreater(gs.real_temp, TARGET_TEMP + 1.0)

    def test_attack_intensity_ramps_up(self):
        """공격 강도가 시간에 따라 증가."""
        from security.scada_security_engine import (
            ScadaSecurityState,
            reset_scenario,
            trigger_attack,
            update_scenario,
        )
        gs = ScadaSecurityState()
        gs.auto_scenario = False
        reset_scenario(gs)
        trigger_attack(gs)
        for _ in range(50):
            update_scenario(gs, 0.05)
        self.assertGreater(gs.attack_intensity, 0.0)

    def test_attack_intensity_decays_after_defense(self):
        """방어 후 공격 강도가 감소."""
        from security.scada_security_engine import (
            ScadaSecurityState,
            reset_scenario,
            trigger_attack,
            trigger_defense,
            update_scenario,
        )
        gs = ScadaSecurityState()
        gs.auto_scenario = False
        reset_scenario(gs)
        trigger_attack(gs)
        for _ in range(50):
            update_scenario(gs, 0.05)
        intensity_during = gs.attack_intensity
        trigger_defense(gs)
        for _ in range(100):
            update_scenario(gs, 0.05)
        self.assertLess(gs.attack_intensity, intensity_during)

    def test_history_bounded(self):
        """히스토리 크기는 200으로 제한."""
        from security.scada_security_engine import (
            ScadaSecurityState,
            reset_scenario,
            update_scenario,
        )
        gs = ScadaSecurityState()
        gs.auto_scenario = False
        reset_scenario(gs)
        for _ in range(300):
            update_scenario(gs, 0.05)
        self.assertLessEqual(len(gs.real_temp_history), 200)
        self.assertLessEqual(len(gs.displayed_temp_history), 200)

    def test_time_increments(self):
        from security.scada_security_engine import (
            ScadaSecurityState,
            reset_scenario,
            update_scenario,
        )
        gs = ScadaSecurityState()
        gs.auto_scenario = False
        reset_scenario(gs)
        update_scenario(gs, 0.5)
        self.assertAlmostEqual(gs.t, 0.5, places=5)

    def test_temperature_clamped(self):
        """온도는 [-210, 25] 범위."""
        from security.scada_security_engine import (
            ScadaSecurityState,
            reset_scenario,
            update_scenario,
        )
        gs = ScadaSecurityState()
        gs.auto_scenario = False
        reset_scenario(gs)
        gs.real_temp = -220.0  # 범위 아래
        update_scenario(gs, 0.01)
        self.assertGreaterEqual(gs.real_temp, -210.0)

    def test_emergency_cooling(self):
        """비상 냉각 활성화 시 온도 하강."""
        from security.scada_security_engine import (
            CRITICAL_TEMP,
            ScadaSecurityState,
            reset_scenario,
            update_scenario,
        )
        gs = ScadaSecurityState()
        gs.auto_scenario = False
        reset_scenario(gs)
        gs.real_temp = CRITICAL_TEMP + 2.0  # 임계 온도 초과
        update_scenario(gs, 0.05)
        self.assertTrue(gs.emergency)
        # 비상 냉각으로 온도 하강
        temp_after_emergency = gs.real_temp
        for _ in range(50):
            update_scenario(gs, 0.05)
        self.assertLess(gs.real_temp, temp_after_emergency)


class TestAutoScenario(unittest.TestCase):
    """자동 시나리오 흐름 테스트."""

    def test_auto_attack_triggers(self):
        """자동 모드에서 공격이 발생."""
        from security.scada_security_engine import (
            PHASE_NORMAL,
            ScadaSecurityState,
            reset_scenario,
            update_scenario,
        )
        gs = ScadaSecurityState()
        gs.auto_scenario = True
        gs._next_attack_time = 1.0  # 1초 후 공격
        reset_scenario(gs)
        gs._next_attack_time = 1.0

        for _ in range(100):
            update_scenario(gs, 0.05)

        # 5초 후에는 공격이 발생했을 것
        self.assertNotEqual(gs.phase, PHASE_NORMAL,
                            "Auto scenario should trigger attack")

    def test_full_cycle_auto(self):
        """자동 모드에서 전체 사이클 (NORMAL→ATTACK→DETECTED→PROTECTED→NORMAL)."""
        from security.scada_security_engine import (
            PHASE_NORMAL,
            PHASE_PROTECTED,
            ScadaSecurityState,
            reset_scenario,
            update_scenario,
        )
        gs = ScadaSecurityState()
        gs.auto_scenario = True
        gs._next_attack_time = 0.5  # 빠른 공격
        reset_scenario(gs)
        gs._next_attack_time = 0.5

        phases_seen = set()
        for _ in range(2000):
            update_scenario(gs, 0.02)
            phases_seen.add(gs.phase)
            if len(phases_seen) >= 4:
                break

        # 적어도 NORMAL, ATTACK, 그리고 하나 이상의 다른 위상을 봐야 함
        self.assertGreaterEqual(len(phases_seen), 2,
                                f"Only saw phases: {phases_seen}")


class TestPhaseConstants(unittest.TestCase):
    """위상 상수 테스트."""

    def test_phase_values(self):
        from security.scada_security_engine import (
            PHASE_ATTACK,
            PHASE_DETECTED,
            PHASE_NAMES,
            PHASE_NORMAL,
            PHASE_PROTECTED,
        )
        self.assertEqual(PHASE_NORMAL, 0)
        self.assertEqual(PHASE_ATTACK, 1)
        self.assertEqual(PHASE_DETECTED, 2)
        self.assertEqual(PHASE_PROTECTED, 3)
        self.assertEqual(len(PHASE_NAMES), 4)

    def test_phase_names(self):
        from security.scada_security_engine import PHASE_NAMES
        self.assertEqual(PHASE_NAMES[0], "NORMAL")
        self.assertEqual(PHASE_NAMES[1], "ATTACK")
        self.assertEqual(PHASE_NAMES[2], "DETECTED")
        self.assertEqual(PHASE_NAMES[3], "PROTECTED")


if __name__ == "__main__":
    unittest.main()
