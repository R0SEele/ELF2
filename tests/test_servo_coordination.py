import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVO_DIR = PROJECT_ROOT / "src" / "hardware" / "servo"
if str(SERVO_DIR) not in sys.path:
    sys.path.insert(0, str(SERVO_DIR))

import sorter


class ServoCoordinationTests(unittest.TestCase):
    def test_lock_rejects_overlapping_servo_command(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "servo.lock"
            with sorter._servo_lock(lock_path, timeout_s=0.0):
                with self.assertRaisesRegex(sorter.SorterServoError, "servo is busy"):
                    with sorter._servo_lock(lock_path, timeout_s=0.0):
                        pass

    def test_lock_is_released_after_command_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "servo.lock"
            with sorter._servo_lock(lock_path, timeout_s=0.0):
                pass
            with sorter._servo_lock(lock_path, timeout_s=0.0):
                pass


if __name__ == "__main__":
    unittest.main()
