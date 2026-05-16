from __future__ import annotations

from dataclasses import dataclass

try:
    from .protocol import ProtocolError, ZDTV2Protocol
    from .serial_bus import SerialConfig, UARTBus
except ImportError:
    from protocol import ProtocolError, ZDTV2Protocol
    from serial_bus import SerialConfig, UARTBus


class MotorControllerError(Exception):
    pass


@dataclass
class MotorLimits:
    max_speed_rpm: int = 3000
    max_slope_rpm_s: int = 65535
    max_angle_x10_deg: int = 0xFFFFFFFF
    pulses_per_rev: int = 3200


class ZDTMotorController:
    def __init__(
        self,
        address: int = 0x01,
        serial_config: SerialConfig | None = None,
        limits: MotorLimits | None = None,
        checksum_tail: int = 0x6B,
    ):
        self.address = address & 0xFF
        self.protocol = ZDTV2Protocol(checksum_tail=checksum_tail)
        self.bus = UARTBus(serial_config or SerialConfig())
        self.limits = limits or MotorLimits()

    def close(self) -> None:
        self.bus.close()

    def _to_speed_x10(self, rpm: int) -> int:
        if rpm < 0 or rpm > self.limits.max_speed_rpm:
            raise MotorControllerError(f"speed(rpm) out of range: {rpm}, max={self.limits.max_speed_rpm}")
        return rpm * 10

    def _to_angle_x10_from_pulse(self, pulses: int) -> int:
        if pulses < 0:
            raise MotorControllerError("pulses must be >= 0")
        ppr = self.limits.pulses_per_rev
        if ppr <= 0:
            raise MotorControllerError("pulses_per_rev must be > 0")
        angle_x10 = int(round(pulses * 3600.0 / ppr))
        if angle_x10 < 0 or angle_x10 > self.limits.max_angle_x10_deg:
            raise MotorControllerError(f"angle_x10 out of range after pulse conversion: {angle_x10}")
        return angle_x10

    def _check_ack(self, reply: bytes, command: int) -> None:
        try:
            status = self.protocol.parse_status_reply(reply, command=command)
        except ProtocolError as exc:
            raise MotorControllerError(f"invalid ack for 0x{command:02X}: {exc}") from exc

        if status != 0x02:
            raise MotorControllerError(f"command 0x{command:02X} rejected, status=0x{status:02X}")

    def _write_with_ack(self, req: bytes, command: int, timeout_s: float = 0.5) -> None:
        reply = self.bus.exchange_min(req, min_size=4, read_timeout_s=timeout_s)
        self._check_ack(reply, command=command)

    def read_version(self) -> tuple[int, int]:
        req = self.protocol.cmd_read_version(self.address)
        reply = self.bus.exchange_min(req, min_size=7, read_timeout_s=0.5)
        try:
            return self.protocol.parse_version_reply(reply)
        except ProtocolError as exc:
            raise MotorControllerError(f"version parse failed: {exc}") from exc

    def enable(self, enabled: bool = True, sync: int = 0x00) -> None:
        req = self.protocol.cmd_enable(self.address, enabled, sync=sync)
        self._write_with_ack(req, command=self.protocol.CMD_ENABLE)

    def estop(self, sync: int = 0x00) -> None:
        req = self.protocol.cmd_estop(self.address, sync=sync)
        self._write_with_ack(req, command=self.protocol.CMD_ESTOP)

    def home(self, mode: int = 0x00, sync: int = 0x00) -> None:
        req = self.protocol.cmd_home(self.address, mode=mode, sync=sync)
        self._write_with_ack(req, command=self.protocol.CMD_HOME)

    def run_speed(self, direction: int, speed: int, slope: int = 1000, sync: int = 0x00) -> None:
        if slope < 0 or slope > self.limits.max_slope_rpm_s:
            raise MotorControllerError(f"slope out of range: {slope}")
        speed_x10 = self._to_speed_x10(speed)
        req = self.protocol.cmd_speed(
            self.address,
            direction=direction,
            slope_rpm_s=slope,
            speed_x10_rpm=speed_x10,
            sync=sync,
        )
        self._write_with_ack(req, command=self.protocol.CMD_SPEED)

    def move_relative(self, direction: int, speed: int, pulses: int, sync: int = 0x00) -> None:
        speed_x10 = self._to_speed_x10(speed)
        angle_x10 = self._to_angle_x10_from_pulse(pulses)
        req = self.protocol.cmd_move_limit(
            self.address,
            direction=direction,
            speed_x10_rpm=speed_x10,
            angle_x10_deg=angle_x10,
            absolute=False,
            sync=sync,
        )
        self._write_with_ack(req, command=self.protocol.CMD_POS_LIMIT)

    def move_absolute(self, direction: int, speed: int, pulses: int, sync: int = 0x00) -> None:
        speed_x10 = self._to_speed_x10(speed)
        angle_x10 = self._to_angle_x10_from_pulse(pulses)
        req = self.protocol.cmd_move_limit(
            self.address,
            direction=direction,
            speed_x10_rpm=speed_x10,
            angle_x10_deg=angle_x10,
            absolute=True,
            sync=sync,
        )
        self._write_with_ack(req, command=self.protocol.CMD_POS_LIMIT)

    def read_pulse(self) -> int:
        req = self.protocol.cmd_read_pulse(self.address)
        reply = self.bus.exchange_min(req, min_size=8, read_timeout_s=0.5)
        try:
            return self.protocol.parse_signed_u32_reply(reply, command=self.protocol.CMD_READ_PULSE_RT)
        except ProtocolError as exc:
            raise MotorControllerError(f"pulse parse failed: {exc}") from exc

    def read_speed(self) -> int:
        req = self.protocol.cmd_read_speed(self.address)
        reply = self.bus.exchange_min(req, min_size=6, read_timeout_s=0.5)
        try:
            speed_x10 = self.protocol.parse_signed_u16_reply(reply, command=self.protocol.CMD_READ_SPEED_RT)
            return int(round(speed_x10 / 10.0))
        except ProtocolError as exc:
            raise MotorControllerError(f"speed parse failed: {exc}") from exc

    def read_position_x10_deg(self) -> int:
        req = self.protocol.cmd_read_position(self.address)
        reply = self.bus.exchange_min(req, min_size=8, read_timeout_s=0.5)
        try:
            return self.protocol.parse_signed_u32_reply(reply, command=self.protocol.CMD_READ_POS_RT)
        except ProtocolError as exc:
            raise MotorControllerError(f"position parse failed: {exc}") from exc

    def read_status_raw(self) -> bytes:
        req = self.protocol.cmd_read_status(self.address)
        return self.bus.exchange_min(req, min_size=4, read_timeout_s=0.5)
