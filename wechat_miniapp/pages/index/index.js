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
    { label: "开始", value: "start" },
    { label: "停止", value: "stop" },
    { label: "抓拍", value: "snapshot" }
  ]
};

function itemMap(items) {
  const map = {};
  (items || []).forEach((item) => {
    map[item.code] = item;
  });
  return map;
}

Page({
  data: {
    apiBaseInput: "",
    connected: false,
    loading: false,
    lastUpdated: "--",
    deviceStatus: "未知",
    quality: [],
    environment: [],
    batch: [],
    control: [],
    device: [],
    status: {},
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
    this.setData({ apiBaseInput: app.globalData.apiBase });
    this.refreshStatus();
    this.timer = setInterval(() => this.refreshStatus(), 3000);
  },

  onUnload() {
    if (this.timer) {
      clearInterval(this.timer);
    }
  },

  request(path, options = {}) {
    const base = (app.globalData.apiBase || "").replace(/\/$/, "");
    return new Promise((resolve, reject) => {
      wx.request({
        url: base + path,
        method: options.method || "GET",
        data: options.data || {},
        timeout: 8000,
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.ok !== false) {
            resolve(res.data);
          } else {
            reject(res.data || { error: "request failed" });
          }
        },
        fail: reject
      });
    });
  },

  refreshStatus() {
    if (this.data.loading) {
      return;
    }
    this.setData({ loading: true });
    this.request("/api/device/status")
      .then((data) => {
        const control = itemMap(data.groups.control);
        const device = itemMap(data.groups.device);
        const conveyorValue = control.conveyor_cmd ? control.conveyor_cmd.raw_value : "stop";
        const speedValue = control.conveyor_speed ? control.conveyor_speed.raw_value : "medium";
        const sorterValue = control.sorter_position ? control.sorter_position.raw_value : "center";
        this.setData({
          connected: true,
          loading: false,
          status: data.status || {},
          deviceStatus: device.device_status ? device.device_status.display : "在线",
          lastUpdated: this.formatTime(data.updated_at),
          quality: data.groups.quality || [],
          environment: data.groups.environment || [],
          batch: data.groups.batch || [],
          control: data.groups.control || [],
          device: data.groups.device || [],
          ledOn: control.led_switch ? !!control.led_switch.value : this.data.ledOn,
          ledBrightness: control.led_brightness ? Number(control.led_brightness.value) : this.data.ledBrightness,
          autoSort: control.auto_sort_enable ? !!control.auto_sort_enable.value : this.data.autoSort,
          conveyorIndex: this.indexFor("conveyor_cmd", conveyorValue),
          speedIndex: this.indexFor("conveyor_speed", speedValue),
          sorterIndex: this.indexFor("sorter_position", sorterValue)
        });
      })
      .catch(() => {
        this.setData({ connected: false, loading: false, deviceStatus: "未连接" });
      });
  },

  sendCommand(code, value) {
    this.request("/api/device/command", {
      method: "POST",
      data: { code, value }
    })
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

  onApiBaseInput(event) {
    this.setData({ apiBaseInput: event.detail.value });
  },

  saveApiBase() {
    const value = this.data.apiBaseInput.trim();
    if (!value) {
      return;
    }
    app.globalData.apiBase = value;
    wx.setStorageSync("apiBase", value);
    this.refreshStatus();
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

  onAutoSortChange(event) {
    const value = !!event.detail.value;
    this.setData({ autoSort: value });
    this.sendCommand("auto_sort_enable", value);
  },

  onConveyorChange(event) {
    const index = Number(event.detail.value);
    this.setData({ conveyorIndex: index });
    this.sendCommand("conveyor_cmd", optionSets.conveyor_cmd[index].value);
  },

  onSpeedChange(event) {
    const index = Number(event.detail.value);
    this.setData({ speedIndex: index });
    this.sendCommand("conveyor_speed", optionSets.conveyor_speed[index].value);
  },

  onSorterChange(event) {
    const index = Number(event.detail.value);
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
