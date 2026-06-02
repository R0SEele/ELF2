from __future__ import annotations

from dataclasses import dataclass


class ProtocolError(Exception):
    pass


@dataclass(frozen=True)
class Frame:
    address: int
    command: int
    payload: bytes
    tail: int = 0x6B

    def to_bytes(self) -> bytes:
        # 实测格式：地址 + 命令 + 数据 + 0x6B
        return bytes([self.address & 0xFF, self.command & 0xFF]) + self.payload + bytes([self.tail & 0xFF])


class ZDTV2Protocol:
    """ZDT_X/Emm 串口协议（单字节地址 + 固定尾字节 0x6B）。"""

    CMD_READ_VERSION = 0x1F
    CMD_READ_ENCODER_RAW = 0x30
    CMD_READ_SPEED = 0x35
    CMD_READ_POSITION = 0x36
    CMD_READ_STATUS = 0x3A

    CMD_ENABLE = 0xF3
    CMD_SPEED_MODE = 0xF6
    CMD_POS_MODE = 0xFD
    CMD_STOP = 0xFE

    def __init__(self, tail: int = 0x6B, variant: str = "zdt_v2"):
        self.tail = tail & 0xFF
        self.variant = variant

    def pack(self, address: int, command: int, payload: bytes = b"") -> bytes:
        return Frame(address=address, command=command, payload=payload, tail=self.tail).to_bytes()

    def verify_tail(self, frame: bytes) -> None:
        if len(frame) < 4:
            raise ProtocolError(f"reply too short: {len(frame)}")
        if frame[-1] != self.tail:
            raise ProtocolError(f"tail mismatch: expect=0x{self.tail:02X}, got=0x{frame[-1]:02X}")

    def parse_status_code(self, frame: bytes, command: int) -> int:
        # ACK 兼容两种格式：
        # 1) 地址 命令 状态 6B
        # 2) 地址 命令 功能字节 状态 6B（如 F3 回包含 0xAB）
        self.verify_tail(frame)
        if len(frame) < 4:
            raise ProtocolError(f"ack too short: {len(frame)}")
        if frame[1] == 0x00 and frame[2] == 0xEE:
            raise ProtocolError("driver returned command error (0xEE)")
        if frame[1] != (command & 0xFF):
            raise ProtocolError(f"unexpected command in ack: 0x{frame[1]:02X}")
        return frame[-2]

    def parse_read_speed(self, frame: bytes) -> float:
        # 返回：地址 35 符号 速度u16(RPM) 6B
        self.verify_tail(frame)
        if len(frame) < 6:
            raise ProtocolError(f"speed reply too short: {len(frame)}")
        if frame[1] != self.CMD_READ_SPEED:
            raise ProtocolError(f"unexpected speed cmd: 0x{frame[1]:02X}")
        sign = frame[2]
        mag = int.from_bytes(frame[3:5], byteorder="big", signed=False)
        val = -mag if (sign & 0x01) else mag
        return float(val)

    def parse_read_position_x10_deg(self, frame: bytes) -> int:
        # 返回：地址 36 符号 位置u32 6B，角度放大10倍
        self.verify_tail(frame)
        if len(frame) < 8:
            raise ProtocolError(f"position reply too short: {len(frame)}")
        if frame[1] != self.CMD_READ_POSITION:
            raise ProtocolError(f"unexpected position cmd: 0x{frame[1]:02X}")
        sign = frame[2]
        mag = int.from_bytes(frame[3:7], byteorder="big", signed=False)
        return -mag if (sign & 0x01) else mag

    def parse_read_version(self, frame: bytes) -> tuple[int, int]:
        # 返回：地址 1F 固件u16 硬件u16 6B
        self.verify_tail(frame)
        if len(frame) < 7:
            raise ProtocolError(f"version reply too short: {len(frame)}")
        if frame[1] != self.CMD_READ_VERSION:
            raise ProtocolError(f"unexpected version cmd: 0x{frame[1]:02X}")
        fw = int.from_bytes(frame[2:4], byteorder="big", signed=False)
        hw = int.from_bytes(frame[4:6], byteorder="big", signed=False)
        return fw, hw

    def cmd_read_version(self, address: int) -> bytes:
        return self.pack(address, self.CMD_READ_VERSION)

    def cmd_read_speed(self, address: int) -> bytes:
        return self.pack(address, self.CMD_READ_SPEED)

    def cmd_read_position(self, address: int) -> bytes:
        return self.pack(address, self.CMD_READ_POSITION)

    def cmd_read_status(self, address: int) -> bytes:
        return self.pack(address, self.CMD_READ_STATUS)

    def cmd_enable(self, address: int, enabled: bool, sync: int = 0x00) -> bytes:
        # 地址 + F3 + AB + 使能状态 + 同步标志 + 6B
        en = 0x01 if enabled else 0x00
        return self.pack(address, self.CMD_ENABLE, bytes([0xAB, en, sync & 0xFF]))

    def cmd_stop(self, address: int) -> bytes:
        # 地址 + FE + 98 + 同步标志 + 6B
        return self.pack(address, self.CMD_STOP, bytes([0x98, 0x00]))

    def cmd_speed_mode(
        self,
        address: int,
        direction: int,
        speed_rpm: float,
        accel: int = 10,
        sync: int = 0x00,
    ) -> bytes:
        if self.variant == "emm_v5":
            return self._cmd_speed_mode_emm_v5(address, direction, speed_rpm, accel, sync)
        return self._cmd_speed_mode_zdt_v2(address, direction, speed_rpm, accel, sync)

    def _cmd_speed_mode_zdt_v2(
        self,
        address: int,
        direction: int,
        speed_rpm: float,
        accel: int,
        sync: int,
    ) -> bytes:
        # ZDT_X V2：地址 + F6 + 符号 + 速度斜率u16(RPM/s) + 速度u16(0.1RPM) + 同步标志 + 6B
        if accel < 0 or accel > 0xFFFF:
            raise ProtocolError(f"speed slope out of range: {accel}")
        speed_x10 = int(round(abs(speed_rpm) * 10.0))
        if speed_x10 > 0xFFFF:
            raise ProtocolError(f"speed out of range: {speed_rpm}")
        payload = (
            bytes([direction & 0x01])
            + int(accel).to_bytes(2, "big")
            + speed_x10.to_bytes(2, "big")
            + bytes([sync & 0xFF])
        )
        return self.pack(address, self.CMD_SPEED_MODE, payload)

    def _cmd_speed_mode_emm_v5(
        self,
        address: int,
        direction: int,
        speed_rpm: float,
        accel: int,
        sync: int,
    ) -> bytes:
        # Emm_V5：地址 + F6 + 方向 + 速度u16(RPM) + 加速度u8 + 同步标志 + 6B
        if accel < 0 or accel > 0xFF:
            raise ProtocolError(f"accel out of range: {accel}")
        speed_u16 = int(round(abs(speed_rpm)))
        if speed_u16 > 0xFFFF:
            raise ProtocolError(f"speed out of range: {speed_rpm}")
        payload = (
            bytes([direction & 0x01])
            + speed_u16.to_bytes(2, "big")
            + bytes([accel & 0xFF])
            + bytes([sync & 0xFF])
        )
        return self.pack(address, self.CMD_SPEED_MODE, payload)

    def cmd_pos_mode(
        self,
        address: int,
        direction: int,
        speed_rpm: float,
        accel: int,
        pulses: int,
        absolute: bool,
        sync: int = 0x00,
    ) -> bytes:
        # 地址 + FD + 方向 + 速度u16 + 加速度u16 + 脉冲u32 + 相对/绝对 + 同步 + 6B
        speed_u16 = int(round(abs(speed_rpm)))
        if speed_u16 < 0 or speed_u16 > 0xFFFF:
            raise ProtocolError(f"speed out of range: {speed_rpm}")
        if accel < 0 or accel > 0xFFFF:
            raise ProtocolError(f"accel out of range: {accel}")
        if pulses < 0 or pulses > 0xFFFFFFFF:
            raise ProtocolError(f"pulses out of range: {pulses}")
        rel_abs = 0x01 if absolute else 0x00
        payload = (
            bytes([direction & 0x01])
            + speed_u16.to_bytes(2, "big")
            + int(accel).to_bytes(2, "big")
            + pulses.to_bytes(4, "big")
            + bytes([rel_abs, sync & 0xFF])
        )
        return self.pack(address, self.CMD_POS_MODE, payload)
