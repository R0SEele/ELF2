const app = getApp();

const optionSets = {
  conveyor_cmd: [
    { label: "停止", value: "stop" },
    { label: "正转", value: "forward" },
    { label: "反转", value: "reverse" }
  ],
  conveyor_speed: [
    { label: "慢速", value: "slow" },
    { label: "中速", value: "medium" },
    { label: "快速", value: "fast" }
  ],
  sorter_position: [
    { label: "左", value: "left" },
    { label: "中", value: "center" },
    { label: "右", value: "right" }
  ],
  detect_cmd: [
    { label: "开始检测", value: "start", kind: "primary" },
    { label: "停止", value: "stop", kind: "ghost" },
    { label: "抓拍", value: "snapshot", kind: "outline" }
  ]
};

// raw_value -> semantic style class
const GRADE_CLASS = { a: "ok", b: "warn", c: "info", reject: "danger", unknown: "muted" };
const CHANNEL_CLASS = {
  sales: "ok",
  ripen: "warn",
  process: "info",
  recheck: "info",
  reject: "danger",
  unknown: "muted"
};
const ENV_CLASS = { normal: "ok", partial_error: "warn", error: "danger", unknown: "muted" };

const ENV_ICON = {
  temperature_c: "🌡️",
  humidity_rh: "💧",
  co2_ppm: "🫧",
  light_lux: "☀️",
  air_quality_ppm: "🍃"
};

function itemMap(items) {
  const map = {};
  (items || []).forEach((item) => {
    map[item.code] = item;
  });
  return map;
}

function pickDisplay(map, code, fallback = "--") {
  return map[code] ? map[code].display : fallback;
}

function rawOf(map, code) {
  return map[code] ? String(map[code].raw_value) : "unknown";
}

function classFrom(table, raw) {
  return table[raw] || "muted";
}

function numOf(map, code) {
  const item = map[code];
  const n = item ? Number(item.value) : 0;
  return isFinite(n) ? n : 0;
}

Page({
  data: {
    endpointInput: "",
    accessTokenInput: "",
    connected: false,
    loading: false,
    showSettings: false,
    lastUpdated: "--",
    deviceStatus: "未知",
    deviceStatusClass: "muted",
    cloudMode: true,
    overview: {
      grade: "--",
      gradeClass: "muted",
      channel: "--",
      channelClass: "muted",
      conclusion: "--",
      mangoId: "--"
    },
    envStatus: { display: "--", class: "muted" },
    environment: [],
    batch: {
      total: 0,
      a: 0,
      b: 0,
      reject: 0,
      aPct: 0,
      bPct: 0,
      rejectPct: 0,
      otherPct: 0
    },
    ledOn: false,
    ledBrightness: 40,
    autoSort: true,
    conveyorOptions: optionSets.conveyor_cmd,
    speedOptions: optionSets.conveyor_speed,
    sorterOptions: optionSets.sorter_position,
    detectOptions: optionSets.detect_cmd,
    conveyorIndex: 0,
    speedIndex: 1,
    sorterIndex: 1
  },

  onLoad() {
    this.setData({
      endpointInput: app.globalData.apiBase,
      accessTokenInput: app.globalData.accessToken,
      cloudMode: app.globalData.useCloud
    });
    this.refreshStatus();
    this.timer = setInterval(() => this.refreshStatus(), 3000);
  },

  onShow() {
    this.setData({
      endpointInput: app.globalData.apiBase,
      accessTokenInput: app.globalData.accessToken,
      cloudMode: app.globalData.useCloud
    });
  },

  onUnload() {
    if (this.timer) {
      clearInterval(this.timer);
    }
  },

  refreshStatus() {
    if (this.data.loading) {
      return;
    }
    this.setData({ loading: true });
    app.requestDeviceStatus()
      .then((data) => {
        const quality = itemMap(data.groups.quality);
        const control = itemMap(data.groups.control);
        const device = itemMap(data.groups.device);
        const conveyorValue = control.conveyor_cmd ? control.conveyor_cmd.raw_value : "stop";
        const speedValue = control.conveyor_speed ? control.conveyor_speed.raw_value : "medium";
        const sorterValue = control.sorter_position ? control.sorter_position.raw_value : "center";

        const environment = (data.groups.environment || []).filter((item) => item.code !== "env_status");
        environment.forEach((item) => {
          item.icon = ENV_ICON[item.code] || "📊";
        });
        const envMap = itemMap(data.groups.environment);

        this.setData({
          connected: true,
          loading: false,
          cloudMode: data.source === "tuya",
          deviceStatus: device.device_status ? device.device_status.display : "在线",
          deviceStatusClass: this.deviceClass(rawOf(device, "device_status")),
          lastUpdated: this.formatTime(data.updated_at),
          overview: {
            grade: pickDisplay(quality, "quality_grade"),
            gradeClass: classFrom(GRADE_CLASS, rawOf(quality, "quality_grade")),
            channel: pickDisplay(quality, "suggested_channel"),
            channelClass: classFrom(CHANNEL_CLASS, rawOf(quality, "suggested_channel")),
            conclusion: pickDisplay(quality, "final_status"),
            mangoId: pickDisplay(quality, "mango_id")
          },
          envStatus: {
            display: pickDisplay(envMap, "env_status", "正常"),
            class: classFrom(ENV_CLASS, rawOf(envMap, "env_status"))
          },
          environment,
          batch: this.buildBatch(itemMap(data.groups.batch)),
          ledOn: control.led_switch ? !!control.led_switch.value : this.data.ledOn,
          ledBrightness: control.led_brightness ? Number(control.led_brightness.value) : this.data.ledBrightness,
          autoSort: control.auto_sort_enable ? !!control.auto_sort_enable.value : this.data.autoSort,
          conveyorIndex: this.indexFor("conveyor_cmd", conveyorValue),
          speedIndex: this.indexFor("conveyor_speed", speedValue),
          sorterIndex: this.indexFor("sorter_position", sorterValue)
        });
      })
      .catch((err) => {
        this.setData({
          connected: false,
          loading: false,
          deviceStatus: "未连接",
          deviceStatusClass: "danger"
        });
        if (err && err.error) {
          wx.showToast({ title: err.error, icon: "none" });
        }
      });
  },

  buildBatch(map) {
    const total = numOf(map, "batch_total");
    const a = numOf(map, "batch_a_count");
    const b = numOf(map, "batch_b_count");
    const reject = numOf(map, "batch_reject_count");
    const base = total > 0 ? total : 0;
    const pct = (n) => (base > 0 ? Math.round((n / base) * 100) : 0);
    const aPct = pct(a);
    const bPct = pct(b);
    const rejectPct = pct(reject);
    const otherPct = Math.max(0, 100 - aPct - bPct - rejectPct);
    return { total, a, b, reject, aPct, bPct, rejectPct, otherPct };
  },

  deviceClass(raw) {
    if (raw === "running") return "ok";
    if (raw === "error") return "danger";
    if (raw === "offline") return "muted";
    if (raw === "idle") return "info";
    return "muted";
  },

  sendCommand(code, value) {
    app.sendDeviceCommand(code, value)
      .then(() => {
        this.refreshStatus();
      })
      .catch((err) => {
        wx.showToast({
          title: err && err.error ? err.error : "命令失败",
          icon: "none"
        });
      });
  },

  toggleSettings() {
    this.setData({ showSettings: !this.data.showSettings });
  },

  onEndpointInput(event) {
    this.setData({ endpointInput: event.detail.value });
  },

  onAccessTokenInput(event) {
    this.setData({ accessTokenInput: event.detail.value });
  },

  saveConnection() {
    const endpoint = this.data.endpointInput.trim();
    if (!endpoint) {
      return;
    }
    if (!app.configureEndpoint(endpoint)) {
      wx.showToast({ title: "云环境无效", icon: "none" });
      return;
    }
    app.setAccessToken(this.data.accessTokenInput);
    this.setData({
      endpointInput: app.globalData.apiBase,
      accessTokenInput: app.globalData.accessToken,
      cloudMode: app.globalData.useCloud,
      showSettings: false
    });
    wx.showToast({ title: "已保存", icon: "success" });
    this.refreshStatus();
  },

  openQualityPage() {
    wx.navigateTo({
      url: "/pages/quality/quality"
    });
  },

  onLedSwitch(event) {
    const value = !!event.detail.value;
    this.setData({ ledOn: value });
    this.sendCommand("led_switch", value);
  },

  onBrightnessChange(event) {
    const value = Number(event.detail.value);
    this.setData({ ledBrightness: value });
    this.sendCommand("led_brightness", value);
  },

  onBrightnessChanging(event) {
    this.setData({ ledBrightness: Number(event.detail.value) });
  },

  onAutoSortChange(event) {
    const value = !!event.detail.value;
    this.setData({ autoSort: value });
    this.sendCommand("auto_sort_enable", value);
  },

  onConveyorTap(event) {
    const index = Number(event.currentTarget.dataset.index);
    this.setData({ conveyorIndex: index });
    this.sendCommand("conveyor_cmd", optionSets.conveyor_cmd[index].value);
  },

  onSpeedTap(event) {
    const index = Number(event.currentTarget.dataset.index);
    this.setData({ speedIndex: index });
    this.sendCommand("conveyor_speed", optionSets.conveyor_speed[index].value);
  },

  onSorterTap(event) {
    const index = Number(event.currentTarget.dataset.index);
    this.setData({ sorterIndex: index });
    this.sendCommand("sorter_position", optionSets.sorter_position[index].value);
  },

  onDetectTap(event) {
    this.sendCommand("detect_cmd", event.currentTarget.dataset.value);
  },

  indexFor(name, value) {
    const list = optionSets[name] || [];
    const index = list.findIndex((item) => item.value === value);
    return index < 0 ? 0 : index;
  },

  formatTime(ms) {
    if (!ms) {
      return "--";
    }
    const date = new Date(ms);
    const pad = (num) => String(num).padStart(2, "0");
    return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  }
});
