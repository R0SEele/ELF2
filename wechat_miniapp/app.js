const DEFAULT_CLOUD_ENV = "cloud1-d3gawfd5o88014f88";
const CONNECTION_STORAGE_VERSION = 2;
const COMMAND_ACK_TIMEOUT_MS = 7000;
const COMMAND_ACK_POLL_MS = 500;

function sameControlValue(left, right) {
  if (typeof right === "boolean") {
    return Boolean(left) === right;
  }
  if (typeof right === "number") {
    return Number(left) === right;
  }
  return String(left) === String(right);
}

App({
  globalData: {
    apiBase: `cloud://${DEFAULT_CLOUD_ENV}`,
    cloudEnv: DEFAULT_CLOUD_ENV,
    useCloud: false,
    accessToken: ""
  },

  onLaunch() {
    const storedToken = wx.getStorageSync("accessToken");
    if (storedToken) {
      this.globalData.accessToken = storedToken;
    }

    const stored = wx.getStorageSync("apiBase");
    const storageVersion = Number(wx.getStorageSync("connectionStorageVersion") || 0);
    if (stored && storageVersion >= CONNECTION_STORAGE_VERSION) {
      this.configureEndpoint(stored, false);
    } else {
      // Older releases defaulted to 127.0.0.1 and persisted that address. On a
      // phone it points back to the phone, so migrate once to the cloud route.
      wx.removeStorageSync("apiBase");
      wx.removeStorageSync("cloudEnv");
      this.enableCloud(DEFAULT_CLOUD_ENV, true);
    }
    wx.setStorageSync("connectionStorageVersion", CONNECTION_STORAGE_VERSION);
  },

  normalizeCloudEnv(value) {
    return String(value || "").replace(/^cloud:\/\//, "").replace(/^env:/, "").trim();
  },

  configureEndpoint(value, persist = true) {
    const endpoint = String(value || "").trim();
    if (endpoint.indexOf("cloud://") === 0 || endpoint.indexOf("env:") === 0 || endpoint === DEFAULT_CLOUD_ENV) {
      return this.enableCloud(endpoint, persist);
    }
    this.disableCloud(endpoint, persist);
    return true;
  },

  enableCloud(envId, persist = true) {
    const normalized = String(envId || "").replace(/^cloud:\/\//, "").replace(/^env:/, "").trim();
    if (!normalized || !wx.cloud) {
      return false;
    }
    wx.cloud.init({
      env: normalized,
      traceUser: true
    });
    this.globalData.cloudEnv = normalized;
    this.globalData.useCloud = true;
    this.globalData.apiBase = `cloud://${normalized}`;
    if (persist) {
      wx.setStorageSync("cloudEnv", normalized);
      wx.setStorageSync("apiBase", this.globalData.apiBase);
      wx.setStorageSync("connectionStorageVersion", CONNECTION_STORAGE_VERSION);
    }
    return true;
  },

  disableCloud(apiBase, persist = true) {
    this.globalData.cloudEnv = "";
    this.globalData.useCloud = false;
    this.globalData.apiBase = apiBase || "http://127.0.0.1:8765";
    if (persist) {
      wx.removeStorageSync("cloudEnv");
      wx.setStorageSync("apiBase", this.globalData.apiBase);
      wx.setStorageSync("connectionStorageVersion", CONNECTION_STORAGE_VERSION);
    }
  },

  setAccessToken(token) {
    const value = String(token || "").trim();
    this.globalData.accessToken = value;
    if (value) {
      wx.setStorageSync("accessToken", value);
    } else {
      wx.removeStorageSync("accessToken");
    }
  },

  request(path, options = {}) {
    if (this.globalData.useCloud) {
      const action = path.indexOf("/api/device/status") >= 0 ? "status" : "command";
      const data = action === "status"
        ? { action, access_token: this.globalData.accessToken }
        : { action, command: options.data || {}, access_token: this.globalData.accessToken };

      return new Promise((resolve, reject) => {
        wx.cloud.callFunction({
          name: "tuyaDevice",
          data,
          success: (res) => {
            const result = res.result || {};
            if (result.ok !== false) {
              resolve(result);
            } else {
              reject(result);
            }
          },
          fail: reject
        });
      });
    }

    const base = (this.globalData.apiBase || "").replace(/\/$/, "");
    return new Promise((resolve, reject) => {
      wx.request({
        url: base + path,
        method: options.method || "GET",
        data: options.data || {},
        timeout: 8000,
        header: this.globalData.accessToken ? { "X-Access-Token": this.globalData.accessToken } : {},
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

  requestDeviceStatus() {
    return this.request("/api/device/status");
  },

  waitForDeviceCommand(code, value, baselineUpdatedAt, deadline) {
    return this.requestDeviceStatus().then((payload) => {
      const status = payload.status || {};
      const updatedAt = payload.status_updated_at || {};
      const hasDeviceTimestamps = Object.keys(updatedAt).length > 0;
      const isNewer = (key) => Number(updatedAt[key] || 0) > Number(baselineUpdatedAt[key] || 0);
      const deviceResultFresh = !hasDeviceTimestamps
        || (isNewer(code) && isNewer("device_status") && isNewer("error_message"));

      if (deviceResultFresh) {
        if (status.device_status === "error" || status.error_message) {
          throw { error: status.error_message || "设备执行命令失败" };
        }
        if (Object.prototype.hasOwnProperty.call(status, code) && sameControlValue(status[code], value)) {
          return { acknowledged: true, code, value, status, status_updated_at: updatedAt };
        }
      }
      if (Date.now() >= deadline) {
        throw { error: `设备未在 ${COMMAND_ACK_TIMEOUT_MS / 1000} 秒内确认命令` };
      }
      return new Promise((resolve) => setTimeout(resolve, COMMAND_ACK_POLL_MS))
        .then(() => this.waitForDeviceCommand(code, value, baselineUpdatedAt, deadline));
    });
  },

  sendDeviceCommand(code, value) {
    return this.requestDeviceStatus().then((before) => {
      const baselineUpdatedAt = before.status_updated_at || {};
      return this.request("/api/device/command", {
        method: "POST",
        data: { code, value }
      }).then((result) => this.waitForDeviceCommand(
        code,
        value,
        baselineUpdatedAt,
        Date.now() + COMMAND_ACK_TIMEOUT_MS
      ).then((acknowledgement) => Object.assign({}, result, { acknowledgement })));
    });
  }
});
