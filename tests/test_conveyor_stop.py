import unittest

from src.hardware.motor import controller, conveyor_cli


class FakeController:
    def __init__(self, stop_error=None, speed_rpm=0.0):
        self.stop_error = stop_error
        self.speed_rpm = speed_rpm
        self.disable_calls = 0

    def stop(self, wait_ack=True):
        if self.stop_error:
            raise self.stop_error

    def enable(self, enabled, sync=0, wait_ack=True):
        if not enabled:
            self.disable_calls += 1

    def read_speed_rpm(self):
        return self.speed_rpm


class ConveyorStopTests(unittest.TestCase):
    def condition_error(self):
        return controller.MotorCommandRejectedError(0xFE, 0xE2, bytes.fromhex("01 fe e2 6b"))

    def test_already_stopped_condition_is_idempotent(self):
        ctrl = FakeController(self.condition_error(), speed_rpm=0.0)

        conveyor_cli._stop_conveyor(ctrl, wait_ack=True, sync=0)

        self.assertEqual(ctrl.disable_calls, 1)

    def test_condition_error_is_preserved_when_motor_is_moving(self):
        error = self.condition_error()
        ctrl = FakeController(error, speed_rpm=25.0)

        with self.assertRaises(controller.MotorCommandRejectedError):
            conveyor_cli._stop_conveyor(ctrl, wait_ack=True, sync=0)

        self.assertEqual(ctrl.disable_calls, 1)


if __name__ == "__main__":
    unittest.main()
