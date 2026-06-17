const DEFAULT_CLOUD_ENV = "cloud1-d3gawfd5o88014f88";

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
    if (stored) {
      this.configureEndpoint(stored, false);
    } else {
      this.enableCloud(DEFAULT_CLOUD_ENV, false);
    }
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

  sendDeviceCommand(code, value) {
    return this.request("/api/device/command", {
      method: "POST",
      data: { code, value }
    });
  }
});
