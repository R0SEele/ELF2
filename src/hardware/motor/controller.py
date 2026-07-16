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


class MotorCommandRejectedError(MotorControllerError):
    def __init__(self, command: int, status: int, reply: bytes):
        self.command = command
        self.status = status
        self.reply = reply
        super().__init__(
            f"command 0x{command:02X} failed, status=0x{status:02X}, reply={reply.hex(' ')}"
        )


@dataclass
class MotorLimits:
    max_speed_rpm: float = 3000.0
    max_accel: int = 0xFFFF
    pulses_per_rev: int = 3200


class ZDTMotorController:
    def __init__(
        self,
        address: int = 0x01,
        serial_config: SerialConfig | None = None,
        limits: MotorLimits | None = None,
        protocol_variant: str = "zdt_v2",
    ):
        self.address = address & 0xFF
        self.protocol = ZDTV2Protocol(variant=protocol_variant)
        self.bus = UARTBus(serial_config or SerialConfig())
        self.limits = limits or MotorLimits()

    def close(self) -> None:
        self.bus.close()

    def _check_ack(self, reply: bytes, command: int) -> None:
        try:
            status = self.protocol.parse_status_code(reply, command)
        except ProtocolError as exc:
            # 某些固件使能命令回包命令字固定为 0x48，做兼容尝试。
            if command == self.protocol.CMD_ENABLE:
                try:
                    status = self.protocol.parse_status_code(reply, 0x48)
                except ProtocolError:
                    raise MotorControllerError(f"ack parse failed for 0x{command:02X}: {exc}") from exc
            else:
                raise MotorControllerError(f"ack parse failed for 0x{command:02X}: {exc}") from exc

        # 0x02 成功，0xE2 条件不满足，0xEE 命令错误
        if status != 0x02:
            raise MotorCommandRejectedError(command, status, reply)

    def read_version(self) -> tuple[int, int]:
        req = self.protocol.cmd_read_version(self.address)
        reply = self.bus.exchange_min(req, min_size=7, read_timeout_s=0.8)
        try:
            return self.protocol.parse_read_version(reply)
        except ProtocolError as exc:
            raise MotorControllerError(f"read_version parse failed: {exc}") from exc

    def enable(self, enabled: bool = True, sync: int = 0x00, wait_ack: bool = True) -> None:
        req = self.protocol.cmd_enable(self.address, enabled, sync=sync)
        if not wait_ack:
            self.bus.write_only(req)
            return
        reply = self.bus.exchange_min(req, min_size=4, read_timeout_s=0.8)
        self._check_ack(reply, self.protocol.CMD_ENABLE)

    def stop(self, wait_ack: bool = True) -> None:
        req = self.protocol.cmd_stop(self.address)
        if not wait_ack:
            self.bus.write_only(req)
            return
        reply = self.bus.exchange_min(req, min_size=4, read_timeout_s=0.8)
        self._check_ack(reply, self.protocol.CMD_STOP)

    def run_speed(
        self,
        direction: int,
        speed_rpm: float,
        accel: int = 10,
        sync: int = 0x00,
        wait_ack: bool = True,
    ) -> None:
        if abs(speed_rpm) > self.limits.max_speed_rpm:
            raise MotorControllerError(f"speed_rpm out of range: {speed_rpm}")
        if accel < 0 or accel > self.limits.max_accel:
            raise MotorControllerError(f"accel out of range: {accel}")

        req = self.protocol.cmd_speed_mode(
            self.address,
            direction=direction,
            speed_rpm=speed_rpm,
            accel=accel,
            sync=sync,
        )
        if not wait_ack:
            self.bus.write_only(req)
            return
        reply = self.bus.exchange_min(req, min_size=4, read_timeout_s=0.8)
        self._check_ack(reply, self.protocol.CMD_SPEED_MODE)

    def move_relative(
        self,
        direction: int,
        speed_rpm: float,
        accel: int,
        pulses: int,
        sync: int = 0x00,
        wait_ack: bool = True,
    ) -> None:
        if pulses < 0:
            raise MotorControllerError("pulses must be >= 0")
        if abs(speed_rpm) > self.limits.max_speed_rpm:
            raise MotorControllerError(f"speed_rpm out of range: {speed_rpm}")
        if accel < 0 or accel > self.limits.max_accel:
            raise MotorControllerError(f"accel out of range: {accel}")

        req = self.protocol.cmd_pos_mode(
            self.address,
            direction=direction,
            speed_rpm=speed_rpm,
            accel=accel,
            pulses=pulses,
            absolute=False,
            sync=sync,
        )
        if not wait_ack:
            self.bus.write_only(req)
            return
        reply = self.bus.exchange_min(req, min_size=4, read_timeout_s=0.8)
        self._check_ack(reply, self.protocol.CMD_POS_MODE)

    def read_speed_rpm(self) -> float:
        req = self.protocol.cmd_read_speed(self.address)
        reply = self.bus.exchange_min(req, min_size=6, read_timeout_s=0.8)
        try:
            return self.protocol.parse_read_speed(reply)
        except ProtocolError as exc:
            raise MotorControllerError(f"read_speed parse failed: {exc}") from exc

    def read_position_x10_deg(self) -> int:
        req = self.protocol.cmd_read_position(self.address)
        reply = self.bus.exchange_min(req, min_size=8, read_timeout_s=0.8)
        try:
            return self.protocol.parse_read_position_x10_deg(reply)
        except ProtocolError as exc:
            raise MotorControllerError(f"read_position parse failed: {exc}") from exc

    def read_status_raw(self) -> bytes:
        req = self.protocol.cmd_read_status(self.address)
        return self.bus.exchange_min(req, min_size=4, read_timeout_s=0.8)
