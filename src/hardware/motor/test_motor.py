#!/usr/bin/env python3

import sys
import time

try:
	from .controller import ZDTMotorController
	from .serial_bus import SerialConfig
except ImportError:
	from controller import ZDTMotorController
	from serial_bus import SerialConfig


def main():
	port = "/dev/ttyS9"
	baud = 115200
	addr = 0x01

	ctrl = ZDTMotorController(
		address=addr,
		serial_config=SerialConfig(port=port, baudrate=baud, timeout_s=0.5, write_timeout_s=0.5),
	)

	try:
		print("[1/7] read version (handshake)")
		req = ctrl.protocol.cmd_read_version(addr)
		print(f"tx(read_version)={req.hex(' ')}")
		fw, hw = ctrl.read_version()
		print(f"fw={fw} hw={hw}")

		print("[2/7] enable")
		req = ctrl.protocol.cmd_enable(addr, True)
		print(f"tx(enable)={req.hex(' ')}")
		ctrl.enable(True)
		time.sleep(0.2)

		print("[3/7] move relative: dir=0 speed=500rpm pulse=2000")
		req = ctrl.protocol.cmd_move_limit(
			addr,
			direction=0,
			speed_x10_rpm=5000,
			angle_x10_deg=int(round(2000 * 3600.0 / ctrl.limits.pulses_per_rev)),
			absolute=False,
		)
		print(f"tx(move_rel)={req.hex(' ')}")
		ctrl.move_relative(direction=0, speed=500, pulses=2000)
		time.sleep(1.0)

		print("[4/7] read speed")
		req = ctrl.protocol.cmd_read_speed(addr)
		print(f"tx(read_speed)={req.hex(' ')}")
		speed = ctrl.read_speed()
		print(f"speed_rpm={speed}")

		print("[5/7] read pulse")
		req = ctrl.protocol.cmd_read_pulse(addr)
		print(f"tx(read_pulse)={req.hex(' ')}")
		pulse = ctrl.read_pulse()
		print(f"pulse={pulse}")

		print("[6/7] read position")
		req = ctrl.protocol.cmd_read_position(addr)
		print(f"tx(read_position)={req.hex(' ')}")
		pos = ctrl.read_position_x10_deg()
		print(f"position_x10_deg={pos}")

		print("[7/7] estop + disable")
		req = ctrl.protocol.cmd_estop(addr)
		print(f"tx(estop)={req.hex(' ')}")
		ctrl.estop()
		time.sleep(0.2)
		req = ctrl.protocol.cmd_enable(addr, False)
		print(f"tx(disable)={req.hex(' ')}")
		ctrl.enable(False)

		print("test done")
	except Exception as exc:
		print(f"test failed: {exc}")
		return 1
	finally:
		ctrl.close()

	return 0


if __name__ == "__main__":
	sys.exit(main())
