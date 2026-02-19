"""냉각기 히스테리시스 제어 단위 테스트."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scada.cooler import CoolerState, CoolingSystem


class TestCoolerState(unittest.TestCase):
    """CoolerState 데이터클래스."""

    def test_creation(self):
        state = CoolerState(-196.0, -196.0, True, False, True)
        self.assertEqual(state.temperature, -196.0)
        self.assertTrue(state.cooling_on)

    def test_equality(self):
        s1 = CoolerState(-196.0, -196.0, True, False, True)
        s2 = CoolerState(-196.0, -196.0, True, False, True)
        self.assertEqual(s1, s2)


class TestCoolingSystemInit(unittest.TestCase):
    """CoolingSystem 초기화."""

    def test_default_params(self):
        cs = CoolingSystem()
        self.assertEqual(cs.target, -196.0)
        self.assertEqual(cs.hysteresis, 2.0)
        self.assertEqual(cs.emergency_threshold, 6.0)

    def test_custom_params(self):
        cs = CoolingSystem(target_temp=-100.0, hysteresis=5.0)
        self.assertEqual(cs.target, -100.0)
        self.assertEqual(cs.hysteresis, 5.0)

    def test_initial_state(self):
        cs = CoolingSystem()
        state = cs.get_state()
        self.assertEqual(state.temperature, 25.0)
        self.assertFalse(state.cooling_on)
        self.assertFalse(state.emergency)
        self.assertFalse(state.running)


class TestCoolingSystemTick(unittest.TestCase):
    """_tick() 히스테리시스 제어 로직."""

    def test_heat_leak(self):
        cs = CoolingSystem(heat_leak=0.5)
        cs._temperature = -200.0
        initial = cs._temperature
        cs._tick()
        self.assertEqual(cs._temperature, initial + 0.5)

    def test_cooling_activates_above_upper(self):
        cs = CoolingSystem(target_temp=-196.0, hysteresis=2.0, heat_leak=0.0)
        cs._temperature = -193.5  # above -194 (upper)
        cs._cooling_on = False
        cs._tick()
        self.assertTrue(cs._cooling_on)

    def test_cooling_deactivates_at_target(self):
        cs = CoolingSystem(target_temp=-196.0, heat_leak=0.0)
        cs._temperature = -197.0
        cs._cooling_on = True
        cs._tick()
        self.assertFalse(cs._cooling_on)

    def test_emergency_activates(self):
        cs = CoolingSystem(target_temp=-196.0, emergency_threshold=6.0, heat_leak=0.0)
        cs._temperature = -189.0  # above -190 (emergency line)
        cs._tick()
        self.assertTrue(cs._emergency)
        self.assertTrue(cs._cooling_on)

    def test_emergency_stronger_power(self):
        cs = CoolingSystem(
            target_temp=-196.0,
            cooling_power=-1.5,
            emergency_power=-3.0,
            heat_leak=0.0,
        )
        cs._temperature = -189.0
        cs._tick()
        self.assertAlmostEqual(cs._temperature, -192.0)

    def test_normal_cooling_power(self):
        cs = CoolingSystem(
            target_temp=-196.0,
            hysteresis=2.0,
            cooling_power=-1.5,
            heat_leak=0.0,
        )
        cs._temperature = -193.0
        cs._cooling_on = False
        cs._tick()
        self.assertAlmostEqual(cs._temperature, -194.5)

    def test_cooling_cycle(self):
        """냉각 → 중지 → 재냉각 사이클.

        _tick() 순서: heat → 히스테리시스 제어 → 냉각 적용
        제어는 heat 후 온도를 보고 판단, 냉각은 그 뒤에 적용.
        """
        cs = CoolingSystem(
            target_temp=-196.0,
            hysteresis=2.0,
            cooling_power=-2.0,
            heat_leak=1.0,
        )
        cs._temperature = -195.0
        cs._cooling_on = True

        # tick 1: heat→-194, control(already on, no change), cool→-196
        cs._tick()
        self.assertAlmostEqual(cs._temperature, -196.0)
        self.assertTrue(cs._cooling_on)  # 아직 켜짐 (다음 틱에서 꺼짐)

        # tick 2: heat→-195, control(not<=target), cool→-197
        cs._tick()
        self.assertAlmostEqual(cs._temperature, -197.0)
        self.assertTrue(cs._cooling_on)

        # tick 3: heat→-196, control(-196<=target→off), no cool
        cs._tick()
        self.assertAlmostEqual(cs._temperature, -196.0)
        self.assertFalse(cs._cooling_on)

        # tick 4: heat→-195, no cool
        cs._tick()
        self.assertAlmostEqual(cs._temperature, -195.0)
        self.assertFalse(cs._cooling_on)

        # tick 5: heat→-194, control(>=upper, not on→on), cool→-196
        cs._tick()
        self.assertAlmostEqual(cs._temperature, -196.0)
        self.assertTrue(cs._cooling_on)  # 재활성화

    def test_emergency_clears_at_target(self):
        cs = CoolingSystem(target_temp=-196.0, heat_leak=0.0)
        cs._temperature = -197.0
        cs._emergency = True
        cs._cooling_on = True
        cs._tick()
        self.assertFalse(cs._emergency)
        self.assertFalse(cs._cooling_on)


class TestCoolingSystemStartStop(unittest.TestCase):
    """시뮬레이션 시작/중지."""

    def test_start_sets_running(self):
        cs = CoolingSystem(tick_interval=0.01)
        cs.start()
        self.assertTrue(cs._running)
        cs.stop()
        self.assertFalse(cs._running)

    def test_stop_resets_thread(self):
        cs = CoolingSystem(tick_interval=0.01)
        cs.start()
        cs.stop()
        self.assertIsNone(cs._thread)

    def test_double_start(self):
        cs = CoolingSystem(tick_interval=0.01)
        cs.start()
        thread1 = cs._thread
        cs.start()
        self.assertIs(cs._thread, thread1)
        cs.stop()

    def test_listener_callback(self):
        cs = CoolingSystem(tick_interval=0.01)
        states = []
        cs.add_listener(lambda s: states.append(s))
        cs.start()
        import time

        time.sleep(0.1)
        cs.stop()
        self.assertGreater(len(states), 0)
        self.assertIsInstance(states[0], CoolerState)


if __name__ == "__main__":
    unittest.main()
