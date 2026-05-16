from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import serial


class SerialBusError(Exception):
    pass


@dataclass
class SerialConfig:
    port: str = "/dev/ttyS9"
    baudrate: int = 115200
    bytesize: int = serial.EIGHTBITS
    parity: str = serial.PARITY_NONE
    stopbits: int = serial.STOPBITS_ONE
    timeout_s: float = 0.2
    write_timeout_s: float = 0.2


class UARTBus:
    def __init__(self, config: SerialConfig):
        self._cfg = config
        self._lock = threading.Lock()
        self._ser = serial.Serial(
            port=config.port,
            baudrate=config.baudrate,
            bytesize=config.bytesize,
            parity=config.parity,
            stopbits=config.stopbits,
            timeout=config.timeout_s,
            write_timeout=config.write_timeout_s,
        )

    def close(self) -> None:
        with self._lock:
            if self._ser.is_open:
                self._ser.close()

    def exchange(self, req: bytes, read_size: int, read_timeout_s: float | None = None) -> bytes:
        with self._lock:
            if not self._ser.is_open:
                raise SerialBusError("serial port is closed")

            self._ser.reset_input_buffer()
            self._ser.write(req)
            self._ser.flush()

            timeout_s = self._cfg.timeout_s if read_timeout_s is None else read_timeout_s
            deadline = time.monotonic() + timeout_s
            data = bytearray()

            while len(data) < read_size and time.monotonic() < deadline:
                chunk = self._ser.read(read_size - len(data))
                if chunk:
                    data.extend(chunk)

            if len(data) < read_size:
                raise SerialBusError(f"read timeout: expect={read_size}, got={len(data)}")

            return bytes(data)

    def exchange_min(self, req: bytes, min_size: int, read_timeout_s: float | None = None) -> bytes:
        with self._lock:
            if not self._ser.is_open:
                raise SerialBusError("serial port is closed")

            self._ser.reset_input_buffer()
            self._ser.write(req)
            self._ser.flush()

            timeout_s = self._cfg.timeout_s if read_timeout_s is None else read_timeout_s
            deadline = time.monotonic() + timeout_s
            data = bytearray()

            while time.monotonic() < deadline:
                waiting = self._ser.in_waiting
                if waiting > 0:
                    data.extend(self._ser.read(waiting))
                    # 连续等待一个短空闲窗口，尽量收全一帧
                    idle_deadline = time.monotonic() + 0.02
                    while time.monotonic() < idle_deadline:
                        waiting2 = self._ser.in_waiting
                        if waiting2 > 0:
                            data.extend(self._ser.read(waiting2))
                            idle_deadline = time.monotonic() + 0.02
                        else:
                            time.sleep(0.001)
                    break
                time.sleep(0.001)

            if len(data) < min_size:
                raise SerialBusError(f"read timeout: min_expect={min_size}, got={len(data)}")

            return bytes(data)

    def write_only(self, req: bytes) -> None:
        with self._lock:
            if not self._ser.is_open:
                raise SerialBusError("serial port is closed")
            self._ser.write(req)
            self._ser.flush()

    def probe(self, req: bytes, read_timeout_s: float | None = None) -> bytes:
        with self._lock:
            if not self._ser.is_open:
                raise SerialBusError("serial port is closed")

            self._ser.reset_input_buffer()
            self._ser.write(req)
            self._ser.flush()

            timeout_s = self._cfg.timeout_s if read_timeout_s is None else read_timeout_s
            deadline = time.monotonic() + timeout_s
            data = bytearray()
            while time.monotonic() < deadline:
                waiting = self._ser.in_waiting
                if waiting > 0:
                    data.extend(self._ser.read(waiting))
                else:
                    time.sleep(0.001)
            return bytes(data)
