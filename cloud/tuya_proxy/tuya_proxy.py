#!/usr/bin/env python3
"""Local Tuya Cloud proxy for the RK3588 mango inspection mini program."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "tuya_cloud.json"
DEFAULT_SECRET_CONFIG = PROJECT_ROOT / "config" / "tuya_cloud_secrets.json"


DP_META: dict[str, dict[str, Any]] = {
    "temperature_c": {"label": "温度", "group": "environment", "type": "value", "scale": 1, "unit": "℃"},
    "humidity_rh": {"label": "湿度", "group": "environment", "type": "value", "scale": 1, "unit": "%RH"},
    "co2_ppm": {"label": "CO2", "group": "environment", "type": "value", "unit": "ppm"},
    "light_lux": {"label": "光照", "group": "environment", "type": "value", "unit": "lux"},
    "air_quality_ppm": {"label": "空气质量", "group": "environment", "type": "value", "unit": "ppm"},
    "env_status": {
        "label": "环境状态",
        "group": "environment",
        "type": "enum",
        "enum": {"normal": "正常", "partial_error": "部分异常", "error": "异常", "unknown": "未知"},
    },
    "mango_id": {"label": "芒果编号", "group": "quality", "type": "string"},
    "quality_grade": {
        "label": "品质等级",
        "group": "quality",
        "type": "enum",
        "enum": {"unknown": "未知", "a": "A级", "b": "B级", "c": "C级", "reject": "剔除"},
    },
    "maturity_label": {
        "label": "成熟度",
        "group": "quality",
        "type": "enum",
        "enum": {"none": "未检测", "unripe": "未熟", "ripe": "成熟", "overripe": "过熟", "unknown": "未知"},
    },
    "maturity_confidence": {"label": "成熟置信度", "group": "quality", "type": "value", "scale": 1, "unit": "%"},
    "sugar_label": {
        "label": "糖度判断",
        "group": "quality",
        "type": "enum",
        "enum": {"unknown": "未知", "low": "偏低", "normal": "正常", "high": "偏高", "unable": "无法评估"},
    },
    "sugar_score": {"label": "糖度评分", "group": "quality", "type": "value", "scale": 1},
    "rot_status": {
        "label": "腐烂状态",
        "group": "quality",
        "type": "enum",
        "enum": {"unknown": "未知", "normal": "正常", "suspect": "疑似", "rotten": "腐烂", "unable": "无法评估"},
    },
    "rot_score": {"label": "腐烂评分", "group": "quality", "type": "value", "scale": 1},
    "final_status": {"label": "综合结论", "group": "quality", "type": "string"},
    "yolo_label": {"label": "YOLO结果", "group": "quality", "type": "string"},
    "yolo_confidence": {"label": "YOLO置信度", "group": "quality", "type": "value", "scale": 1, "unit": "%"},
    "data_status": {"label": "数据状态", "group": "quality", "type": "string"},
    "last_update": {"label": "更新时间", "group": "quality", "type": "string"},
    "batch_total": {"label": "批次总数", "group": "batch", "type": "value", "unit": "个"},
    "batch_a_count": {"label": "A级数量", "group": "batch", "type": "value", "unit": "个"},
    "batch_b_count": {"label": "B级数量", "group": "batch", "type": "value", "unit": "个"},
    "batch_reject_count": {"label": "剔除数量", "group": "batch", "type": "value", "unit": "个"},
    "conveyor_cmd": {
        "label": "传送带",
        "group": "control",
        "type": "enum",
        "writable": True,
        "enum": {"stop": "停止", "forward": "正转", "reverse": "反转"},
    },
    "conveyor_speed": {
        "label": "传送速度",
        "group": "control",
        "type": "enum",
        "writable": True,
        "enum": {"slow": "慢速", "medium": "中速", "fast": "快速"},
    },
    "sorter_position": {
        "label": "分拣位置",
        "group": "control",
        "type": "enum",
        "writable": True,
        "enum": {"left": "左", "center": "中", "right": "右"},
    },
    "led_switch": {"label": "补光灯", "group": "control", "type": "bool", "writable": True},
    "led_brightness": {"label": "亮度", "group": "control", "type": "value", "unit": "%", "writable": True},
    "detect_cmd": {
        "label": "检测命令",
        "group": "control",
        "type": "enum",
        "writable": True,
        "enum": {"idle": "空闲", "start": "开始", "stop": "停止", "snapshot": "抓拍"},
    },
    "auto_sort_enable": {"label": "自动分拣", "group": "control", "type": "bool", "writable": True},
    "device_status": {
        "label": "设备状态",
        "group": "device",
        "type": "enum",
        "enum": {"idle": "空闲", "running": "运行中", "error": "故障", "offline": "离线", "unknown": "未知"},
    },
    "error_message": {"label": "错误信息", "group": "device", "type": "string"},
}

GROUP_LABELS = {
    "device": "设备",
    "quality": "当前芒果",
    "environment": "环境",
    "batch": "批次",
    "control": "控制",
}


class ProxyError(RuntimeError):
    def __init__(self, message: str, status: int = 500, detail: Any = None):
        super().__init__(message)
        self.status = status
        self.detail = detail


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def load_config(config_path: Path, secret_path: Path) -> dict[str, Any]:
    config = read_json_file(config_path)
    secret_config = read_json_file(secret_path)
    client_secret = os.environ.get("TUYA_CLIENT_SECRET") or secret_config.get("client_secret")
    config["client_secret"] = client_secret
    config.setdefault("endpoint", "https://openapi.tuyacn.com")
    config.setdefault("api_variant", "iot-03")
    return config


def compact_json(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def tuya_url_path(path: str, query: dict[str, Any] | None = None) -> str:
    if not query:
        return path
    parts = []
    for key in sorted(query):
        value = query[key]
        if value is None:
            parts.append(urllib.parse.quote(str(key), safe=""))
        else:
            parts.append(f"{urllib.parse.quote(str(key), safe='')}={urllib.parse.quote(str(value), safe='')}")
    return f"{path}?{'&'.join(parts)}"


class TuyaOpenApi:
    def __init__(self, config: dict[str, Any]):
        self.endpoint = str(config.get("endpoint", "")).rstrip("/")
        self.client_id = str(config.get("client_id", ""))
        self.client_secret = str(config.get("client_secret", "") or "")
        self.device_id = str(config.get("device_id", ""))
        self.api_variant = str(config.get("api_variant", "iot-03"))
        self._token = ""
        self._token_expire_at = 0.0
        if not self.endpoint or not self.client_id or not self.device_id:
            raise ProxyError("Tuya config is incomplete", 500)
        if not self.client_secret:
            raise ProxyError("TUYA_CLIENT_SECRET or config/tuya_cloud_secrets.json is required", 500)

    def _sign_headers(self, method: str, url_path: str, body: bytes = b"", token: str = "") -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        nonce = uuid.uuid4().hex
        content_sha256 = hashlib.sha256(body).hexdigest()
        string_to_sign = f"{method.upper()}\n{content_sha256}\n\n{url_path}"
        sign_source = f"{self.client_id}{token}{timestamp}{nonce}{string_to_sign}"
        sign = hmac.new(self.client_secret.encode("utf-8"), sign_source.encode("utf-8"), hashlib.sha256)
        headers = {
            "client_id": self.client_id,
            "sign": sign.hexdigest().upper(),
            "t": timestamp,
            "nonce": nonce,
            "sign_method": "HMAC-SHA256",
        }
        if token:
            headers["access_token"] = token
        if body:
            headers["Content-Type"] = "application/json"
        return headers

    def _request_once(self, method: str, path: str, query: dict[str, Any] | None = None,
                      body_obj: Any = None, token: str = "") -> dict[str, Any]:
        url_path = tuya_url_path(path, query)
        body = b"" if body_obj is None else compact_json(body_obj)
        headers = self._sign_headers(method, url_path, body, token)
        request = urllib.request.Request(
            self.endpoint + url_path,
            data=None if method.upper() == "GET" else body,
            headers=headers,
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            try:
                detail = json.loads(payload.decode("utf-8"))
            except Exception:
                detail = payload.decode("utf-8", errors="replace")
            raise ProxyError(f"Tuya HTTP error {exc.code}", 502, detail)
        except urllib.error.URLError as exc:
            raise ProxyError(f"Tuya network error: {exc.reason}", 502)

        try:
            data = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ProxyError(f"Tuya returned invalid JSON: {exc}", 502)
        return data

    def token(self, force_refresh: bool = False) -> str:
        if not force_refresh and self._token and time.time() < self._token_expire_at - 60:
            return self._token
        data = self._request_once("GET", "/v1.0/token", {"grant_type": 1})
        if not data.get("success"):
            raise ProxyError("Failed to get Tuya access token", 502, data)
        result = data.get("result") or {}
        access_token = result.get("access_token")
        if not access_token:
            raise ProxyError("Tuya token response has no access_token", 502, data)
        self._token = str(access_token)
        self._token_expire_at = time.time() + int(result.get("expire_time") or 3600)
        return self._token

    def request(self, method: str, path: str, query: dict[str, Any] | None = None,
                body_obj: Any = None, retry_token: bool = True) -> dict[str, Any]:
        token = self.token()
        data = self._request_once(method, path, query, body_obj, token)
        if retry_token and not data.get("success") and str(data.get("code")) in {"1010", "1011", "1012", "1013"}:
            token = self.token(force_refresh=True)
            data = self._request_once(method, path, query, body_obj, token)
        return data

    def _candidate_paths(self, suffix: str) -> list[str]:
        iot03 = f"/v1.0/iot-03/devices/{self.device_id}{suffix}"
        legacy = f"/v1.0/devices/{self.device_id}{suffix}"
        if self.api_variant == "legacy":
            return [legacy, iot03]
        return [iot03, legacy]

    def device_status(self) -> dict[str, Any]:
        errors = []
        for path in self._candidate_paths("/status"):
            data = self.request("GET", path)
            if data.get("success"):
                return data
            errors.append({"path": path, "response": data})
        raise ProxyError("Failed to read Tuya device status", 502, errors)

    def send_commands(self, commands: list[dict[str, Any]]) -> dict[str, Any]:
        body = {"commands": commands}
        errors = []
        for path in self._candidate_paths("/commands"):
            data = self.request("POST", path, body_obj=body)
            if data.get("success"):
                return data
            errors.append({"path": path, "response": data})
        raise ProxyError("Failed to send Tuya commands", 502, errors)


def normalize_value(code: str, value: Any) -> tuple[Any, str]:
    meta = DP_META.get(code, {})
    value_type = meta.get("type")
    if value_type == "bool":
        return bool(value), "开启" if value else "关闭"
    if value_type == "enum":
        text = meta.get("enum", {}).get(str(value), str(value))
        return value, text
    if value_type == "value":
        numeric = value
        if isinstance(value, (int, float)) and int(meta.get("scale", 0)) > 0:
            numeric = value / (10 ** int(meta.get("scale", 0)))
        unit = meta.get("unit", "")
        if isinstance(numeric, float) and numeric.is_integer():
            display_num = str(int(numeric))
        else:
            display_num = f"{numeric:.1f}" if isinstance(numeric, float) else str(numeric)
        return numeric, f"{display_num}{unit}"
    text = "" if value is None else str(value)
    return value, text or "--"


def build_status_payload(device_id: str, tuya_response: dict[str, Any], source: str = "tuya") -> dict[str, Any]:
    result = tuya_response.get("result") or []
    status_map: dict[str, Any] = {}
    if isinstance(result, list):
        for item in result:
            code = item.get("code")
            if code:
                status_map[str(code)] = item.get("value")
    elif isinstance(result, dict):
        for key, value in result.items():
            status_map[str(key)] = value

    groups: dict[str, list[dict[str, Any]]] = {name: [] for name in GROUP_LABELS}
    items = []
    for code, meta in DP_META.items():
        if code not in status_map:
            continue
        normalized, display = normalize_value(code, status_map[code])
        item = {
            "code": code,
            "label": meta.get("label", code),
            "group": meta.get("group", "device"),
            "value": normalized,
            "raw_value": status_map[code],
            "display": display,
            "writable": bool(meta.get("writable")),
        }
        items.append(item)
        groups.setdefault(item["group"], []).append(item)

    return {
        "ok": True,
        "source": source,
        "device_id": device_id,
        "updated_at": int(time.time() * 1000),
        "status": status_map,
        "items": items,
        "groups": groups,
        "group_labels": GROUP_LABELS,
    }


def validate_commands(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean_commands = []
    for command in commands:
        code = str(command.get("code", ""))
        if code not in DP_META or not DP_META[code].get("writable"):
            raise ProxyError(f"DP is not writable: {code}", 400)
        meta = DP_META[code]
        value = command.get("value")
        if meta["type"] == "bool":
            if not isinstance(value, bool):
                raise ProxyError(f"{code} expects boolean", 400)
        elif meta["type"] == "enum":
            allowed = set(meta.get("enum", {}).keys())
            if str(value) not in allowed:
                raise ProxyError(f"{code} expects one of {sorted(allowed)}", 400)
            value = str(value)
        elif meta["type"] == "value":
            if not isinstance(value, (int, float)):
                raise ProxyError(f"{code} expects number", 400)
            if code == "led_brightness":
                value = max(0, min(100, int(value)))
        clean_commands.append({"code": code, "value": value})
    return clean_commands


def mock_tuya_response() -> dict[str, Any]:
    return {
        "success": True,
        "result": [
            {"code": "device_status", "value": "running"},
            {"code": "temperature_c", "value": 262},
            {"code": "humidity_rh", "value": 588},
            {"code": "co2_ppm", "value": 612},
            {"code": "light_lux", "value": 1250},
            {"code": "air_quality_ppm", "value": 35},
            {"code": "env_status", "value": "normal"},
            {"code": "mango_id", "value": "M-0001"},
            {"code": "quality_grade", "value": "a"},
            {"code": "maturity_label", "value": "ripe"},
            {"code": "maturity_confidence", "value": 924},
            {"code": "sugar_label", "value": "normal"},
            {"code": "sugar_score", "value": 842},
            {"code": "rot_status", "value": "normal"},
            {"code": "rot_score", "value": 51},
            {"code": "final_status", "value": "可销售"},
            {"code": "yolo_label", "value": "mango_ripe"},
            {"code": "yolo_confidence", "value": 938},
            {"code": "data_status", "value": "vision_ok,spectrum_ok"},
            {"code": "last_update", "value": time.strftime("%Y-%m-%d %H:%M:%S")},
            {"code": "batch_total", "value": 18},
            {"code": "batch_a_count", "value": 9},
            {"code": "batch_b_count", "value": 6},
            {"code": "batch_reject_count", "value": 1},
            {"code": "conveyor_cmd", "value": "stop"},
            {"code": "conveyor_speed", "value": "medium"},
            {"code": "sorter_position", "value": "center"},
            {"code": "led_switch", "value": True},
            {"code": "led_brightness", "value": 40},
            {"code": "detect_cmd", "value": "idle"},
            {"code": "auto_sort_enable", "value": True},
        ],
    }


class ProxyState:
    def __init__(self, config: dict[str, Any], mock: bool):
        self.config = config
        self.mock = mock
        self.api = None if mock else TuyaOpenApi(config)


class ProxyHandler(BaseHTTPRequestHandler):
    server_version = "MangoTuyaProxy/0.1"

    @property
    def state(self) -> ProxyState:
        return self.server.state  # type: ignore[attr-defined]

    def do_OPTIONS(self) -> None:
        self.send_json({"ok": True})

    def do_GET(self) -> None:
        try:
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/health":
                self.send_json({
                    "ok": True,
                    "mode": "mock" if self.state.mock else "tuya",
                    "device_id": self.state.config.get("device_id"),
                })
            elif path == "/api/device/config":
                writable = {code: meta for code, meta in DP_META.items() if meta.get("writable")}
                self.send_json({
                    "ok": True,
                    "device_id": self.state.config.get("device_id"),
                    "endpoint": self.state.config.get("endpoint"),
                    "dp_meta": DP_META,
                    "writable": writable,
                    "group_labels": GROUP_LABELS,
                })
            elif path == "/api/device/status":
                response = mock_tuya_response() if self.state.mock else self.state.api.device_status()
                payload = build_status_payload(str(self.state.config.get("device_id")), response,
                                               "mock" if self.state.mock else "tuya")
                self.send_json(payload)
            else:
                raise ProxyError("Not found", 404)
        except ProxyError as exc:
            self.send_error_json(exc)
        except Exception as exc:
            self.send_error_json(ProxyError(str(exc), 500))

    def do_POST(self) -> None:
        try:
            path = urllib.parse.urlparse(self.path).path
            body = self.read_body_json()
            if path == "/api/device/command":
                commands = validate_commands([body])
            elif path == "/api/device/commands":
                commands = validate_commands(body.get("commands") or [])
            else:
                raise ProxyError("Not found", 404)

            response = {"success": True, "result": True} if self.state.mock else self.state.api.send_commands(commands)
            if not response.get("success"):
                raise ProxyError("Tuya rejected command", 502, response)
            self.send_json({"ok": True, "commands": commands, "tuya": response})
        except ProxyError as exc:
            self.send_error_json(exc)
        except Exception as exc:
            self.send_error_json(ProxyError(str(exc), 500))

    def read_body_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            raise ProxyError("Invalid JSON body", 400)
        if not isinstance(data, dict):
            raise ProxyError("JSON body must be an object", 400)
        return data

    def send_json(self, data: Any, status: int = 200) -> None:
        payload = compact_json(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def send_error_json(self, exc: ProxyError) -> None:
        self.send_json({"ok": False, "error": str(exc), "detail": exc.detail}, exc.status)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


class ProxyServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], state: ProxyState):
        super().__init__(server_address, ProxyHandler)
        self.state = state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tuya Cloud proxy for mango inspection mini program.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--secret-config", type=Path, default=DEFAULT_SECRET_CONFIG)
    parser.add_argument("--mock", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config, args.secret_config)
    state = ProxyState(config, args.mock)
    server = ProxyServer((args.host, args.port), state)
    print(f"Tuya proxy listening on http://{args.host}:{args.port} ({'mock' if args.mock else 'tuya'} mode)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping Tuya proxy")


if __name__ == "__main__":
    main()
