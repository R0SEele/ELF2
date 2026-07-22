const crypto = require("crypto");
const https = require("https");
const cloud = require("wx-server-sdk");

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });

const database = cloud.database();
const dbCommand = database.command;
const ENVIRONMENT_COLLECTION = "environment_history";
const ENVIRONMENT_RETENTION_MS = 7 * 24 * 60 * 60 * 1000;
const ENVIRONMENT_CODES = [
  "temperature_c",
  "humidity_rh",
  "co2_ppm",
  "light_lux",
  "air_quality_ppm"
];

const DP_META = {
  temperature_c: { label: "温度", group: "environment", type: "value", scale: 1, unit: "℃" },
  humidity_rh: { label: "湿度", group: "environment", type: "value", scale: 1, unit: "%RH" },
  co2_ppm: { label: "CO2", group: "environment", type: "value", unit: "ppm" },
  light_lux: { label: "光照", group: "environment", type: "value", unit: "lux" },
  air_quality_ppm: { label: "空气质量相对值", group: "environment", type: "value", unit: "%" },
  env_status: {
    label: "传感器状态",
    group: "environment",
    type: "enum",
    enum: { normal: "正常", partial_error: "部分异常", error: "异常", unknown: "未知" }
  },
  mango_id: { label: "芒果编号", group: "quality", type: "string" },
  quality_grade: {
    label: "品质等级",
    group: "quality",
    type: "enum",
    enum: { unknown: "未知", a: "A级", b: "B级", c: "C级", reject: "剔除" }
  },
  maturity_label: {
    label: "成熟度",
    group: "quality",
    type: "enum",
    enum: { none: "未检测", unripe: "未熟", ripe: "成熟", overripe: "过熟", unknown: "未知" }
  },
  maturity_score: { label: "成熟度评分", group: "quality", type: "value", scale: 1 },
  maturity_confidence: { label: "成熟置信度", group: "quality", type: "value", scale: 1, unit: "%" },
  sugar_label: {
    label: "糖度判断",
    group: "quality",
    type: "enum",
    enum: { unknown: "未知", low: "偏低", normal: "正常", high: "偏高", unable: "无法评估" }
  },
  sugar_score: { label: "糖度评分", group: "quality", type: "value", scale: 1 },
  rot_status: {
    label: "腐烂状态",
    group: "quality",
    type: "enum",
    enum: { unknown: "未知", normal: "正常", suspect: "疑似", rotten: "腐烂", unable: "无法评估" }
  },
  rot_score: { label: "腐烂评分", group: "quality", type: "value", scale: 1 },
  final_status: { label: "综合结论", group: "quality", type: "string" },
  yolo_label: { label: "YOLO结果", group: "quality", type: "string" },
  yolo_confidence: { label: "YOLO置信度", group: "quality", type: "value", scale: 1, unit: "%" },
  data_status: { label: "数据状态", group: "quality", type: "string" },
  last_update: { label: "品质更新时间", group: "quality", type: "string" },
  suggested_channel: {
    label: "建议通道",
    group: "quality",
    type: "enum",
    enum: { sales: "销售通道", ripen: "催熟通道", process: "加工通道", recheck: "复检通道", reject: "剔除通道", unknown: "未知" }
  },
  batch_total: { label: "批次总数", group: "batch", type: "value", unit: "个" },
  batch_a_count: { label: "A级数量", group: "batch", type: "value", unit: "个" },
  batch_b_count: { label: "B级数量", group: "batch", type: "value", unit: "个" },
  batch_reject_count: { label: "剔除数量", group: "batch", type: "value", unit: "个" },
  conveyor_cmd: {
    label: "传送带",
    group: "control",
    type: "enum",
    writable: true,
    enum: { stop: "停止", forward: "正转", reverse: "反转" }
  },
  conveyor_speed: {
    label: "传送速度",
    group: "control",
    type: "enum",
    writable: true,
    enum: { slow: "慢速", medium: "中速", fast: "快速" }
  },
  sorter_position: {
    label: "分拣位置",
    group: "control",
    type: "enum",
    writable: true,
    enum: { left: "左", center: "中", right: "右" }
  },
  led_switch: { label: "补光灯", group: "control", type: "bool", writable: true },
  led_brightness: { label: "亮度", group: "control", type: "value", unit: "%", writable: true },
  detect_cmd: {
    label: "检测命令",
    group: "control",
    type: "enum",
    writable: true,
    enum: { idle: "空闲", start: "开始", stop: "停止", snapshot: "抓拍" }
  },
  auto_sort_enable: { label: "自动分拣", group: "control", type: "bool", writable: true },
  fan_switch: { label: "通风风扇", group: "control", type: "bool", writable: true },
  fan_auto_enable: { label: "自动通风", group: "control", type: "bool", writable: true },
  fan_temperature_threshold: { label: "风扇温度阈值", group: "control", type: "value", unit: "℃", writable: true },
  fan_humidity_threshold: { label: "风扇湿度阈值", group: "control", type: "value", unit: "%RH", writable: true },
  fan_auto_reason: { label: "自动通风原因", group: "control", type: "string" },
  detect_request_id: { label: "检测请求号", group: "control", type: "string" },
  detect_status: {
    label: "检测状态",
    group: "control",
    type: "enum",
    enum: {
      idle: "空闲",
      starting: "启动中",
      running: "运行中",
      stopping: "停止中",
      snapshotting: "抓拍中",
      snapshot_done: "抓拍完成",
      failed: "失败"
    }
  },
  detect_result: { label: "检测执行结果", group: "control", type: "string" },
  device_status: {
    label: "设备状态",
    group: "device",
    type: "enum",
    enum: { idle: "空闲", running: "运行中", error: "故障", offline: "离线", unknown: "未知" }
  },
  error_message: { label: "错误信息", group: "device", type: "string" }
};

const GROUP_LABELS = {
  device: "设备",
  quality: "当前芒果",
  environment: "环境",
  batch: "批次",
  control: "控制"
};

let cachedToken = "";
let cachedTokenExpireAt = 0;

function config() {
  const endpoint = process.env.TUYA_ENDPOINT || "https://openapi.tuyacn.com";
  const clientId = process.env.TUYA_CLIENT_ID;
  const clientSecret = process.env.TUYA_CLIENT_SECRET;
  const deviceId = process.env.TUYA_DEVICE_ID;
  if (!clientId || !clientSecret || !deviceId) {
    throw new Error("Missing TUYA_CLIENT_ID/TUYA_CLIENT_SECRET/TUYA_DEVICE_ID environment variables");
  }
  return { endpoint: endpoint.replace(/\/$/, ""), clientId, clientSecret, deviceId };
}

function compactJson(value) {
  return JSON.stringify(value);
}

function urlPath(path, query) {
  if (!query) {
    return path;
  }
  const parts = Object.keys(query)
    .sort()
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(query[key])}`);
  return `${path}?${parts.join("&")}`;
}

function signHeaders(cfg, method, pathWithQuery, body, token) {
  const timestamp = String(Date.now());
  const nonce = crypto.randomBytes(16).toString("hex");
  const bodyHash = crypto.createHash("sha256").update(body).digest("hex");
  const stringToSign = `${method.toUpperCase()}\n${bodyHash}\n\n${pathWithQuery}`;
  const signSource = `${cfg.clientId}${token || ""}${timestamp}${nonce}${stringToSign}`;
  const sign = crypto.createHmac("sha256", cfg.clientSecret).update(signSource).digest("hex").toUpperCase();
  const headers = {
    client_id: cfg.clientId,
    sign,
    t: timestamp,
    nonce,
    sign_method: "HMAC-SHA256"
  };
  if (token) {
    headers.access_token = token;
  }
  if (body) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

function tuyaRequest(method, path, query, bodyObj, token) {
  const cfg = config();
  const pathWithQuery = urlPath(path, query);
  const body = bodyObj === undefined || bodyObj === null ? "" : compactJson(bodyObj);
  const headers = signHeaders(cfg, method, pathWithQuery, body, token);
  const url = new URL(cfg.endpoint + pathWithQuery);

  return new Promise((resolve, reject) => {
    const req = https.request(
      {
        hostname: url.hostname,
        path: url.pathname + url.search,
        method: method.toUpperCase(),
        headers,
        timeout: 12000
      },
      (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          try {
            const data = JSON.parse(text || "{}");
            resolve(data);
          } catch (err) {
            reject(new Error(`Tuya returned invalid JSON: ${text}`));
          }
        });
      }
    );
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy(new Error("Tuya request timeout"));
    });
    if (body) {
      req.write(body);
    }
    req.end();
  });
}

async function token() {
  if (cachedToken && Date.now() < cachedTokenExpireAt - 60000) {
    return cachedToken;
  }
  const data = await tuyaRequest("GET", "/v1.0/token", { grant_type: 1 });
  if (!data.success || !data.result || !data.result.access_token) {
    throw new Error(`Failed to get Tuya token: ${JSON.stringify(data)}`);
  }
  cachedToken = data.result.access_token;
  cachedTokenExpireAt = Date.now() + Number(data.result.expire_time || 3600) * 1000;
  return cachedToken;
}

async function tuyaAuthedRequest(method, path, query, bodyObj) {
  let accessToken = await token();
  let data = await tuyaRequest(method, path, query, bodyObj, accessToken);
  if (!data.success && ["1010", "1011", "1012", "1013"].includes(String(data.code))) {
    cachedToken = "";
    accessToken = await token();
    data = await tuyaRequest(method, path, query, bodyObj, accessToken);
  }
  return data;
}

function normalizeValue(code, value) {
  const meta = DP_META[code] || {};
  if (meta.type === "bool") {
    return { value: !!value, display: value ? "开启" : "关闭" };
  }
  if (meta.type === "enum") {
    return { value, display: (meta.enum || {})[String(value)] || String(value) };
  }
  if (meta.type === "value") {
    let numeric = value;
    if (typeof value === "number" && Number(meta.scale || 0) > 0) {
      numeric = value / Math.pow(10, Number(meta.scale || 0));
    }
    const displayNum = typeof numeric === "number" && Number.isInteger(numeric) ? String(numeric) : String(numeric);
    return { value: numeric, display: `${displayNum}${meta.unit || ""}` };
  }
  const text = value === undefined || value === null ? "" : String(value);
  return { value: text, display: text || "--" };
}

function buildStatusPayload(deviceId, properties) {
  const status = {};
  const statusUpdatedAt = {};
  for (const item of properties || []) {
    if (item && item.code) {
      status[item.code] = item.value;
      const updatedAt = Number(item.time || item.update_time || 0);
      if (updatedAt > 0) {
        statusUpdatedAt[item.code] = updatedAt;
      }
    }
  }

  const groups = {};
  for (const group of Object.keys(GROUP_LABELS)) {
    groups[group] = [];
  }

  const items = [];
  for (const code of Object.keys(DP_META)) {
    if (!(code in status)) {
      continue;
    }
    const meta = DP_META[code];
    const normalized = normalizeValue(code, status[code]);
    const item = {
      code,
      label: meta.label || code,
      group: meta.group || "device",
      value: normalized.value,
      raw_value: status[code],
      display: normalized.display,
      writable: !!meta.writable
    };
    items.push(item);
    groups[item.group].push(item);
  }

  return {
    ok: true,
    source: "tuya",
    device_id: deviceId,
    updated_at: Date.now(),
    status,
    status_updated_at: statusUpdatedAt,
    items,
    groups,
    group_labels: GROUP_LABELS
  };
}

async function getStatus() {
  const cfg = config();
  const data = await tuyaAuthedRequest("GET", `/v2.0/cloud/thing/${cfg.deviceId}/shadow/properties`);
  if (!data.success) {
    return { ok: false, error: "Failed to read Tuya device status", detail: data };
  }
  const properties = (data.result && data.result.properties) || [];
  return buildStatusPayload(cfg.deviceId, properties);
}

function normalizeTimestamp(value) {
  const timestamp = Number(value || 0);
  if (!Number.isFinite(timestamp) || timestamp <= 0) {
    return 0;
  }
  return timestamp < 1000000000000 ? timestamp * 1000 : timestamp;
}

function environmentRecord(payload) {
  const environmentItems = ((payload.groups || {}).environment || []);
  const itemByCode = {};
  environmentItems.forEach((item) => {
    itemByCode[item.code] = item;
  });

  const values = {};
  ENVIRONMENT_CODES.forEach((code) => {
    const item = itemByCode[code];
    const value = item ? Number(item.value) : NaN;
    if (Number.isFinite(value)) {
      values[code] = value;
    }
  });
  if (!Object.keys(values).length) {
    return null;
  }

  const statusUpdatedAt = payload.status_updated_at || {};
  const timestamps = ENVIRONMENT_CODES
    .map((code) => normalizeTimestamp(statusUpdatedAt[code]))
    .filter((timestamp) => timestamp > 0);
  const timestamp = timestamps.length ? Math.max(...timestamps) : Date.now();
  const envStatusItem = itemByCode.env_status;
  const envStatus = envStatusItem
    ? String(envStatusItem.raw_value || envStatusItem.value || "unknown")
    : "unknown";

  return {
    device_id: payload.device_id,
    timestamp,
    values,
    env_status: envStatus
  };
}

async function saveEnvironmentSnapshot(payload) {
  const record = environmentRecord(payload);
  if (!record) {
    return { ok: false, error: "No valid environment values" };
  }

  const collection = database.collection(ENVIRONMENT_COLLECTION);
  const latestResult = await collection
    .where({ device_id: record.device_id })
    .orderBy("timestamp", "desc")
    .limit(1)
    .get();
  const latest = (latestResult.data || [])[0];
  if (latest && Number(latest.timestamp) >= record.timestamp) {
    return {
      ok: true,
      source: "cloud_history",
      recorded: false,
      timestamp: record.timestamp,
      reason: "duplicate"
    };
  }

  await collection.add({
    data: Object.assign({}, record, { created_at: database.serverDate() })
  });

  if (Math.floor(record.timestamp / 60000) % 60 === 0) {
    await collection.where({
      device_id: record.device_id,
      timestamp: dbCommand.lt(Date.now() - ENVIRONMENT_RETENTION_MS)
    }).remove();
  }

  return {
    ok: true,
    source: "cloud_history",
    recorded: true,
    timestamp: record.timestamp
  };
}

async function collectEnvironmentSnapshot() {
  const payload = await getStatus();
  if (!payload.ok) {
    return payload;
  }
  return saveEnvironmentSnapshot(payload);
}

async function getEnvironmentHistory(rangeMinutes) {
  const cfg = config();
  const minutes = Math.max(10, Math.min(10080, Math.trunc(Number(rangeMinutes) || 60)));
  const latestResult = await database.collection(ENVIRONMENT_COLLECTION)
    .where({ device_id: cfg.deviceId })
    .orderBy("timestamp", "desc")
    .limit(1)
    .get();
  const latest = (latestResult.data || [])[0];
  if (!latest) {
    return {
      ok: true,
      source: "cloud_history",
      device_id: cfg.deviceId,
      range_minutes: minutes,
      start_at: 0,
      end_at: 0,
      points: []
    };
  }
  const endTimestamp = Number(latest.timestamp);
  const cutoff = endTimestamp - minutes * 60 * 1000;
  const pageSize = 500;
  const points = [];
  let offset = 0;

  while (true) {
    const result = await database.collection(ENVIRONMENT_COLLECTION)
      .where({
        device_id: cfg.deviceId,
        timestamp: dbCommand.gte(cutoff)
      })
      .orderBy("timestamp", "asc")
      .skip(offset)
      .limit(pageSize)
      .get();
    const page = result.data || [];
    page.forEach((record) => {
      points.push({
        timestamp: Number(record.timestamp),
        values: record.values || {},
        env_status: record.env_status || "unknown"
      });
    });
    if (page.length < pageSize) {
      break;
    }
    offset += page.length;
  }

  return {
    ok: true,
    source: "cloud_history",
    device_id: cfg.deviceId,
    range_minutes: minutes,
    start_at: points.length ? points[0].timestamp : 0,
    end_at: points.length ? points[points.length - 1].timestamp : 0,
    points
  };
}

function isTimerEvent(event) {
  return String((event || {}).Type || (event || {}).type || "").toLowerCase() === "timer";
}

function validateCommand(command) {
  const code = String(command.code || "");
  const meta = DP_META[code];
  if (!meta || !meta.writable) {
    throw new Error(`DP is not writable: ${code}`);
  }
  let value = command.value;
  if (meta.type === "bool" && typeof value !== "boolean") {
    throw new Error(`${code} expects boolean`);
  }
  if (meta.type === "enum") {
    const allowed = Object.keys(meta.enum || {});
    if (!allowed.includes(String(value))) {
      throw new Error(`${code} expects one of ${allowed.join(",")}`);
    }
    value = String(value);
  }
  if (meta.type === "value") {
    if (typeof value !== "number") {
      throw new Error(`${code} expects number`);
    }
    if (code === "led_brightness") {
      value = Math.max(0, Math.min(100, Math.trunc(value)));
    }
    if (code === "fan_temperature_threshold") {
      value = Math.max(0, Math.min(60, Math.trunc(value)));
    }
    if (code === "fan_humidity_threshold") {
      value = Math.max(0, Math.min(100, Math.trunc(value)));
    }
  }
  return { code, value };
}

async function sendCommand(command) {
  const cfg = config();
  const clean = validateCommand(command);
  const data = await tuyaAuthedRequest("POST", `/v2.0/cloud/thing/${cfg.deviceId}/shadow/properties/issue`, null, {
    properties: {
      [clean.code]: clean.value
    }
  });
  if (!data.success) {
    return { ok: false, error: "Tuya rejected command", detail: data };
  }
  return { ok: true, source: "tuya", commands: [clean], tuya: data };
}

exports.main = async (event) => {
  try {
    event = event || {};
    if (isTimerEvent(event)) {
      return await collectEnvironmentSnapshot();
    }
    const expectedToken = process.env.APP_ACCESS_TOKEN || "";
    if (expectedToken && event.access_token !== expectedToken) {
      return { ok: false, error: "访问口令错误" };
    }
    if (event.action === "status") {
      return await getStatus();
    }
    if (event.action === "environment_history") {
      return await getEnvironmentHistory(event.range_minutes);
    }
    if (event.action === "collect_environment") {
      return await collectEnvironmentSnapshot();
    }
    if (event.action === "command") {
      return await sendCommand(event.command || event);
    }
    return { ok: false, error: "Unknown action" };
  } catch (err) {
    return { ok: false, error: err.message || String(err) };
  }
};
