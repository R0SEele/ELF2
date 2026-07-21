const STORAGE_KEY = "environmentHistoryV1";
const RETENTION_MS = 24 * 60 * 60 * 1000;
const MAX_POINTS = 9000;

const METRICS = [
  {
    code: "temperature_c",
    label: "温度",
    unit: "℃",
    decimals: 1,
    color: "#c75b50",
    min: 10,
    max: 35,
    rule: "10–35℃"
  },
  {
    code: "humidity_rh",
    label: "湿度",
    unit: "%RH",
    decimals: 1,
    color: "#2f7a62",
    min: 30,
    max: 85,
    rule: "30–85%RH"
  },
  {
    code: "co2_ppm",
    label: "CO₂",
    unit: "ppm",
    decimals: 0,
    color: "#536d7a",
    max: 1500,
    rule: "≤1500ppm"
  },
  {
    code: "light_lux",
    label: "光照",
    unit: "lux",
    decimals: 0,
    color: "#b9852b",
    rule: "仅记录趋势"
  },
  {
    code: "air_quality_ppm",
    label: "空气质量",
    unit: "%",
    decimals: 1,
    color: "#7a5c78",
    max: 70,
    rule: "≤70%（相对值）"
  }
];

function normalizedTimestamp(value) {
  const timestamp = Number(value || 0);
  if (!Number.isFinite(timestamp) || timestamp <= 0) {
    return 0;
  }
  return timestamp < 1000000000000 ? timestamp * 1000 : timestamp;
}

function itemMap(items) {
  const map = {};
  (items || []).forEach((item) => {
    map[item.code] = item;
  });
  return map;
}

function readHistory() {
  try {
    const stored = wx.getStorageSync(STORAGE_KEY);
    const points = stored && Array.isArray(stored.points) ? stored.points : [];
    return points.filter((point) => point && Number.isFinite(Number(point.timestamp)));
  } catch (_err) {
    return [];
  }
}

function writeHistory(points) {
  try {
    wx.setStorageSync(STORAGE_KEY, { version: 1, points });
    return true;
  } catch (_err) {
    return false;
  }
}

function mergeCloudPoints(points) {
  const mergedByTimestamp = {};
  readHistory().forEach((point) => {
    mergedByTimestamp[Number(point.timestamp)] = point;
  });
  (points || []).forEach((point) => {
    const timestamp = normalizedTimestamp(point && point.timestamp);
    const sourceValues = (point && point.values) || {};
    const values = {};
    METRICS.forEach((metric) => {
      const value = Number(sourceValues[metric.code]);
      if (Number.isFinite(value)) {
        values[metric.code] = value;
      }
    });
    if (timestamp > 0 && Object.keys(values).length) {
      mergedByTimestamp[timestamp] = {
        timestamp,
        values,
        envStatus: String(point.env_status || point.envStatus || "unknown")
      };
    }
  });
  const cutoff = Date.now() - RETENTION_MS;
  let merged = Object.keys(mergedByTimestamp)
    .map((timestamp) => mergedByTimestamp[timestamp])
    .filter((point) => Number(point.timestamp) >= cutoff)
    .sort((left, right) => Number(left.timestamp) - Number(right.timestamp));
  if (merged.length > MAX_POINTS) {
    merged = merged.slice(merged.length - MAX_POINTS);
  }
  writeHistory(merged);
  return merged;
}

function sameValues(left, right) {
  return METRICS.every((metric) => Number(left[metric.code]) === Number(right[metric.code]));
}

function recordPayload(payload) {
  const environment = itemMap(payload && payload.groups ? payload.groups.environment : []);
  const values = {};
  let validCount = 0;
  METRICS.forEach((metric) => {
    const item = environment[metric.code];
    const value = item ? Number(item.value) : NaN;
    if (Number.isFinite(value)) {
      values[metric.code] = value;
      validCount += 1;
    }
  });
  if (!validCount) {
    return { recorded: false, history: readHistory(), alarms: [] };
  }

  const updatedAt = (payload && payload.status_updated_at) || {};
  const timestamps = METRICS
    .map((metric) => normalizedTimestamp(updatedAt[metric.code]))
    .filter((timestamp) => timestamp > 0);
  const hasDeviceTimestamp = timestamps.length > 0;
  const timestamp = hasDeviceTimestamp ? Math.max.apply(null, timestamps) : Date.now();
  const envStatusItem = environment.env_status;
  const envStatus = envStatusItem ? String(envStatusItem.raw_value || envStatusItem.value || "unknown") : "";
  const nextPoint = { timestamp, values, envStatus };
  const history = readHistory();
  const latest = history.length ? history[history.length - 1] : null;

  if (latest) {
    if (hasDeviceTimestamp && timestamp <= Number(latest.timestamp)) {
      return { recorded: false, history, alarms: evaluateAlarms(nextPoint) };
    }
    if (!hasDeviceTimestamp && sameValues(latest.values || {}, values)
      && timestamp - Number(latest.timestamp) < 8000) {
      return { recorded: false, history, alarms: evaluateAlarms(nextPoint) };
    }
  }

  const cutoff = timestamp - RETENTION_MS;
  const retained = history.filter((point) => Number(point.timestamp) >= cutoff);
  retained.push(nextPoint);
  const bounded = retained.length > MAX_POINTS ? retained.slice(retained.length - MAX_POINTS) : retained;
  writeHistory(bounded);
  return { recorded: true, history: bounded, alarms: evaluateAlarms(nextPoint) };
}

function evaluateAlarms(point) {
  const alarms = [];
  const values = (point && point.values) || {};
  METRICS.forEach((metric) => {
    const value = Number(values[metric.code]);
    if (!Number.isFinite(value)) {
      return;
    }
    if (Number.isFinite(metric.min) && value < metric.min) {
      alarms.push({
        code: metric.code,
        label: metric.label,
        level: "warning",
        message: `${metric.label} ${formatValue(value, metric)}，低于规则下限 ${formatValue(metric.min, metric)}`
      });
    } else if (Number.isFinite(metric.max) && value > metric.max) {
      alarms.push({
        code: metric.code,
        label: metric.label,
        level: "warning",
        message: `${metric.label} ${formatValue(value, metric)}，超过规则上限 ${formatValue(metric.max, metric)}`
      });
    }
  });
  if (point && point.envStatus && point.envStatus !== "normal" && point.envStatus !== "正常") {
    alarms.unshift({
      code: "env_status",
      label: "传感器",
      level: "danger",
      message: "环境传感器报告异常，请检查设备连接"
    });
  }
  return alarms;
}

function latestAlarms() {
  const history = readHistory();
  return history.length ? evaluateAlarms(history[history.length - 1]) : [];
}

function pointsFor(code, rangeMinutes) {
  const history = readHistory();
  if (!history.length) {
    return [];
  }
  const end = Number(history[history.length - 1].timestamp);
  const cutoff = rangeMinutes > 0 ? end - rangeMinutes * 60 * 1000 : 0;
  return history
    .filter((point) => Number(point.timestamp) >= cutoff)
    .map((point) => ({ timestamp: Number(point.timestamp), value: Number((point.values || {})[code]) }))
    .filter((point) => Number.isFinite(point.value));
}

function formatValue(value, metric) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "--";
  }
  return `${number.toFixed(metric.decimals)}${metric.unit}`;
}

module.exports = {
  METRICS,
  evaluateAlarms,
  formatValue,
  latestAlarms,
  mergeCloudPoints,
  pointsFor,
  readHistory,
  recordPayload
};
