#!/usr/bin/env python3

from __future__ import annotations

import argparse
import glob
import sys
import time
from pathlib import Path

import serial
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "config" / "motor.yaml"
DEFAULT_BAUDS = (115200, 57600, 38400, 25000, 19200, 9600)
READ_COMMANDS = {
    "version": 0x1F,
    "speed": 0x35,
    "position": 0x36,
    "status": 0x3A,
}
ZDT_READ_FRAMES = {
    "zdt_status": bytes.fromhex("01 43 7A 6B"),
}


def _pack(address: int, command: int, payload: bytes = b"") -> bytes:
    return bytes([address & 0xFF, command & 0xFF]) + payload + b"\x6b"


def _read_config():
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            return (yaml.safe_load(handle) or {}).get("motor", {})
    except FileNotFoundError:
        return {}


def _to_int_addr(value):
    if isinstance(value, str):
        return int(value, 0)
    return int(value)


def _parse_csv_ints(text):
    result = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        result.append(int(item, 0))
    return result


def _xor_checksum(data: bytes) -> int:
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum & 0xFF


def _crc8_maxim_checksum(data: bytes) -> int:
    crc = data[0] if data else 0
    for byte in data[1:]:
        crc ^= byte
        for _ in range(8):
            if crc & 0x01:
                crc = (crc >> 1) ^ 0x8C
            else:
                crc >>= 1
            crc &= 0xFF
    return crc & 0xFF


def _checksum(data: bytes, mode: str) -> int:
    if mode == "fixed":
        return 0x6B
    if mode == "xor":
        return _xor_checksum(data)
    if mode == "crc8":
        return _crc8_maxim_checksum(data)
    raise ValueError(f"unsupported checksum mode: {mode}")


def _frame(address: int, command: int, checksum_mode: str) -> bytes:
    body = bytes([address & 0xFF, command & 0xFF])
    return body + bytes([_checksum(body, checksum_mode)])


def _zdt_fixed_frame(address: int, template: bytes) -> bytes:
    frame = bytearray(template)
    frame[0] = address & 0xFF
    return bytes(frame)


def _motion_frames(address: int, protocol_variant: str, direction: int, speed_rpm: float, accel: int, sync: int):
    enable = _pack(address, 0xF3, bytes([0xAB, 0x01, sync & 0xFF]))
    if protocol_variant == "emm_v5":
        speed = _pack(
            address,
            0xF6,
            bytes([direction & 0x01])
            + int(round(abs(speed_rpm))).to_bytes(2, "big")
            + bytes([accel & 0xFF, sync & 0xFF]),
        )
    else:
        speed = _pack(
            address,
            0xF6,
            bytes([direction & 0x01])
            + int(accel).to_bytes(2, "big")
            + int(round(abs(speed_rpm) * 10.0)).to_bytes(2, "big")
            + bytes([sync & 0xFF]),
        )
    stop = _pack(address, 0xFE, bytes([0x98, sync & 0xFF]))
    return enable, speed, stop


def _read_window(ser: serial.Serial, timeout_s: float) -> bytes:
    deadline = time.monotonic() + timeout_s
    data = bytearray()
    while time.monotonic() < deadline:
        waiting = ser.in_waiting
        if waiting > 0:
            data.extend(ser.read(waiting))
            continue
        chunk = ser.read(1)
        if chunk:
            data.extend(chunk)
        else:
            time.sleep(0.002)
    return bytes(data)


def _classify(tx: bytes, rx: bytes, address: int, command: int) -> str:
    if not rx:
        return "no_rx"
    if rx == tx:
        return "echo_only"
    if rx.startswith(tx):
        tail = rx[len(tx):]
        if len(tail) >= 3 and tail[0] == (address & 0xFF) and tail[1] == (command & 0xFF):
            return "echo_plus_reply"
        return "echo_plus_unknown"
    if len(rx) >= 3 and rx[0] == (address & 0xFF) and rx[1] == (command & 0xFF):
        return "reply"
    if len(rx) >= 4 and rx[0] == (address & 0xFF) and rx[1] == 0x00 and rx[2] == 0xEE:
        return "driver_format_error"
    return "unknown_rx"


def _candidate_ports(configured_port: str, scan_ports: bool) -> list[str]:
    if not scan_ports:
        return [configured_port]

    ports = set()
    patterns = ("/dev/ttyS*", "/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyAMA*")
    for pattern in patterns:
        ports.update(glob.glob(pattern))
    ports.add(configured_port)
    return sorted(ports)


def main() -> int:
    cfg = _read_config()
    serial_cfg = cfg.get("serial", {})
    driver_cfg = cfg.get("driver", {})

    configured_port = str(serial_cfg.get("port", "/dev/ttyS9"))
    configured_baud = int(serial_cfg.get("baudrate", 115200))
    configured_addr = _to_int_addr(driver_cfg.get("address", "0x01"))
    configured_protocol = str(driver_cfg.get("protocol", "zdt_v2"))
    configured_sync = int(driver_cfg.get("sync", 0))
    kctrl_cfg = cfg.get("kctrl", {})
    configured_accel = int(kctrl_cfg.get("accel", 100))

    parser = argparse.ArgumentParser(description="Probe ZDT/Emm motor serial responses without moving the motor")
    parser.add_argument("--port", default=configured_port)
    parser.add_argument("--scan-ports", action="store_true", help="Probe /dev/ttyS*, /dev/ttyUSB*, /dev/ttyACM*, /dev/ttyAMA*")
    parser.add_argument("--bauds", default=str(configured_baud), help="Comma-separated baud rates, or 'common'")
    parser.add_argument("--addresses", default=str(configured_addr), help="Comma-separated motor addresses")
    parser.add_argument("--checksums", default="fixed,xor,crc8", help="Comma-separated: fixed,xor,crc8")
    parser.add_argument("--timeout-s", type=float, default=0.25)
    parser.add_argument("--show-motion-frame", action="store_true", help="Only print configured enable/speed/stop frames; do not open serial")
    parser.add_argument("--raw-zdt-status", action="store_true", help="Send ZDT status read frame once and print raw RX")
    parser.add_argument("--speed-rpm", type=float, default=1000.0)
    parser.add_argument("--direction", type=int, default=0)
    args = parser.parse_args()

    if args.show_motion_frame:
        enable, speed, stop = _motion_frames(
            configured_addr,
            configured_protocol,
            args.direction,
            args.speed_rpm,
            configured_accel,
            configured_sync,
        )
        print(f"protocol={configured_protocol} addr=0x{configured_addr:02X} speed_rpm={args.speed_rpm:.1f} accel={configured_accel}")
        print(f"enable={enable.hex(' ')}")
        print(f"speed={speed.hex(' ')}")
        print(f"stop={stop.hex(' ')}")
        return 0

    if args.raw_zdt_status:
        tx = _zdt_fixed_frame(configured_addr, ZDT_READ_FRAMES["zdt_status"])
        with serial.Serial(
            port=args.port,
            baudrate=configured_baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.02,
            write_timeout=0.2,
        ) as ser:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write(tx)
            ser.flush()
            rx = _read_window(ser, args.timeout_s)
        print(f"port={args.port} baud={configured_baud} addr=0x{configured_addr:02X}")
        print(f"tx={tx.hex(' ')}")
        print(f"rx={rx.hex(' ') if rx else '<none>'}")
        if rx == tx:
            print("result=echo_only")
        elif rx:
            print("result=non_echo_rx")
        else:
            print("result=no_rx")
        return 0

    bauds = list(DEFAULT_BAUDS) if args.bauds == "common" else _parse_csv_ints(args.bauds)
    addresses = _parse_csv_ints(args.addresses)
    checksum_modes = [item.strip() for item in args.checksums.split(",") if item.strip()]
    ports = _candidate_ports(args.port, args.scan_ports)

    found_reply = False
    for port in ports:
        for baud in bauds:
            try:
                ser = serial.Serial(
                    port=port,
                    baudrate=baud,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.02,
                    write_timeout=0.2,
                )
            except Exception as exc:
                print(f"port={port} baud={baud} open_error={exc}")
                continue

            try:
                for address in addresses:
                    for checksum_mode in checksum_modes:
                        for name, command in READ_COMMANDS.items():
                            tx = _frame(address, command, checksum_mode)
                            ser.reset_input_buffer()
                            ser.reset_output_buffer()
                            ser.write(tx)
                            ser.flush()
                            rx = _read_window(ser, args.timeout_s)
                            kind = _classify(tx, rx, address, command)
                            if kind in {"reply", "echo_plus_reply", "driver_format_error"}:
                                found_reply = True
                            print(
                                f"port={port} baud={baud} addr=0x{address:02X} "
                                f"checksum={checksum_mode} cmd={name} kind={kind} "
                                f"tx={tx.hex(' ')} rx={rx.hex(' ')}"
                            )
                            time.sleep(0.03)
                    if "fixed" in checksum_modes:
                        for name, template in ZDT_READ_FRAMES.items():
                            tx = _zdt_fixed_frame(address, template)
                            ser.reset_input_buffer()
                            ser.reset_output_buffer()
                            ser.write(tx)
                            ser.flush()
                            rx = _read_window(ser, args.timeout_s)
                            kind = _classify(tx, rx, address, tx[1])
                            if kind in {"reply", "echo_plus_reply", "driver_format_error"}:
                                found_reply = True
                            print(
                                f"port={port} baud={baud} addr=0x{address:02X} "
                                f"checksum=fixed cmd={name} kind={kind} "
                                f"tx={tx.hex(' ')} rx={rx.hex(' ')}"
                            )
                            time.sleep(0.03)
            finally:
                ser.close()

    return 0 if found_reply else 2


if __name__ == "__main__":
    sys.exit(main())
