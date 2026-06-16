App({
  globalData: {
    apiBase: "http://127.0.0.1:8765"
  },

  onLaunch() {
    const stored = wx.getStorageSync("apiBase");
    if (stored) {
      this.globalData.apiBase = stored;
    }
  }
});
