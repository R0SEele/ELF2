from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class ProtocolError(Exception):
    pass


@dataclass(frozen=True)
class Frame:
    address: int
    command: int
    payload: bytes
    checksum_tail: int = 0x6B

    def to_bytes(self) -> bytes:
        return bytes([self.address & 0xFF, self.command & 0xFF]) + self.payload + bytes([self.checksum_tail & 0xFF])


class ZDTV2Protocol:
    """ZDT_X 系列 V2 串口协议封装。

    默认校验字节固定为 0x6B（说明书默认模式）。
    """

    CMD_ENABLE = 0xF3
    CMD_SPEED = 0xF6
    CMD_POS_LIMIT = 0xFB
    CMD_POS_TRAP = 0xFD
    CMD_ESTOP = 0xFE
    CMD_HOME = 0x9A

    CMD_READ_VERSION = 0x1F
    CMD_READ_PULSE_RT = 0x30
    CMD_READ_SPEED_RT = 0x35
    CMD_READ_POS_RT = 0x36
    CMD_READ_STATUS = 0x3A

    CMD_SYNC_START = 0xFF

    def __init__(self, checksum_tail: int = 0x6B):
        self.checksum_tail = checksum_tail & 0xFF

    @staticmethod
    def _u16(value: int) -> bytes:
        if value < 0 or value > 0xFFFF:
            raise ProtocolError(f"u16 overflow: {value}")
        return value.to_bytes(2, byteorder="big", signed=False)

    @staticmethod
    def _u32(value: int) -> bytes:
        if value < 0 or value > 0xFFFFFFFF:
            raise ProtocolError(f"u32 overflow: {value}")
        return value.to_bytes(4, byteorder="big", signed=False)

    @staticmethod
    def _signed_by_sign_magnitude(sign: int, magnitude: int) -> int:
        return -magnitude if (sign & 0x01) else magnitude

    def pack(self, address: int, command: int, payload: Iterable[int] | bytes = b"") -> bytes:
        payload_bytes = bytes(payload)
        return Frame(address=address, command=command, payload=payload_bytes, checksum_tail=self.checksum_tail).to_bytes()

    def verify(self, frame: bytes) -> None:
        if len(frame) < 3:
            raise ProtocolError("frame too short")
        if frame[-1] != self.checksum_tail:
            raise ProtocolError(f"tail mismatch: expect=0x{self.checksum_tail:02X}, got=0x{frame[-1]:02X}")

    def parse_status_reply(self, frame: bytes, command: int) -> int:
        self.verify(frame)
        if len(frame) < 4:
            raise ProtocolError(f"reply too short for status: {len(frame)}")
        if frame[1] == 0x00 and frame[2] == 0xEE:
            raise ProtocolError("driver returned protocol error (0xEE)")
        if frame[1] != (command & 0xFF):
            raise ProtocolError(f"unexpected command in reply: 0x{frame[1]:02X}")
        return frame[2]

    def parse_signed_u16_reply(self, frame: bytes, command: int) -> int:
        self.verify(frame)
        if len(frame) < 6:
            raise ProtocolError(f"reply too short for signed_u16: {len(frame)}")
        if frame[1] != (command & 0xFF):
            raise ProtocolError(f"unexpected command in reply: 0x{frame[1]:02X}")
        sign = frame[2]
        mag = int.from_bytes(frame[3:5], byteorder="big", signed=False)
        return self._signed_by_sign_magnitude(sign, mag)

    def parse_signed_u32_reply(self, frame: bytes, command: int) -> int:
        self.verify(frame)
        if len(frame) < 8:
            raise ProtocolError(f"reply too short for signed_u32: {len(frame)}")
        if frame[1] != (command & 0xFF):
            raise ProtocolError(f"unexpected command in reply: 0x{frame[1]:02X}")
        sign = frame[2]
        mag = int.from_bytes(frame[3:7], byteorder="big", signed=False)
        return self._signed_by_sign_magnitude(sign, mag)

    def parse_version_reply(self, frame: bytes) -> tuple[int, int]:
        self.verify(frame)
        if len(frame) < 7:
            raise ProtocolError(f"reply too short for version: {len(frame)}")
        if frame[1] != self.CMD_READ_VERSION:
            raise ProtocolError(f"unexpected command in reply: 0x{frame[1]:02X}")
        fw = int.from_bytes(frame[2:4], byteorder="big", signed=False)
        hw = int.from_bytes(frame[4:6], byteorder="big", signed=False)
        return fw, hw

    def cmd_enable(self, address: int, enabled: bool, sync: int = 0x00) -> bytes:
        en = 0x01 if enabled else 0x00
        return self.pack(address, self.CMD_ENABLE, [0xAB, en, sync & 0xFF])

    def cmd_estop(self, address: int, sync: int = 0x00) -> bytes:
        return self.pack(address, self.CMD_ESTOP, [0x98, sync & 0xFF])

    def cmd_home(self, address: int, mode: int = 0x00, sync: int = 0x00) -> bytes:
        return self.pack(address, self.CMD_HOME, [mode & 0xFF, sync & 0xFF])

    def cmd_speed(self, address: int, direction: int, slope_rpm_s: int, speed_x10_rpm: int, sync: int = 0x00) -> bytes:
        payload = bytes([direction & 0xFF]) + self._u16(slope_rpm_s) + self._u16(speed_x10_rpm) + bytes([sync & 0xFF])
        return self.pack(address, self.CMD_SPEED, payload)

    def cmd_move_limit(self, address: int, direction: int, speed_x10_rpm: int, angle_x10_deg: int, absolute: bool, sync: int = 0x00) -> bytes:
        rel_abs = 0x01 if absolute else 0x00
        payload = bytes([direction & 0xFF]) + self._u16(speed_x10_rpm) + self._u32(angle_x10_deg) + bytes([rel_abs, sync & 0xFF])
        return self.pack(address, self.CMD_POS_LIMIT, payload)

    def cmd_move_trap(
        self,
        address: int,
        direction: int,
        accel_up_rpm_s: int,
        accel_down_rpm_s: int,
        max_speed_x10_rpm: int,
        angle_x10_deg: int,
        absolute: bool,
        sync: int = 0x00,
    ) -> bytes:
        rel_abs = 0x01 if absolute else 0x00
        payload = (
            bytes([direction & 0xFF])
            + self._u16(accel_up_rpm_s)
            + self._u16(accel_down_rpm_s)
            + self._u16(max_speed_x10_rpm)
            + self._u32(angle_x10_deg)
            + bytes([rel_abs, sync & 0xFF])
        )
        return self.pack(address, self.CMD_POS_TRAP, payload)

    def cmd_sync_start(self, address: int = 0x00) -> bytes:
        return self.pack(address, self.CMD_SYNC_START, [0x66])

    def cmd_read_version(self, address: int) -> bytes:
        return self.pack(address, self.CMD_READ_VERSION)

    def cmd_read_pulse(self, address: int) -> bytes:
        return self.pack(address, self.CMD_READ_PULSE_RT)

    def cmd_read_speed(self, address: int) -> bytes:
        return self.pack(address, self.CMD_READ_SPEED_RT)

    def cmd_read_position(self, address: int) -> bytes:
        return self.pack(address, self.CMD_READ_POS_RT)

    def cmd_read_status(self, address: int) -> bytes:
        return self.pack(address, self.CMD_READ_STATUS)
