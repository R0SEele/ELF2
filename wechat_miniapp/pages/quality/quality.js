const app = getApp();

function itemMap(items) {
  const map = {};
  (items || []).forEach((item) => {
    map[item.code] = item;
  });
  return map;
}

function display(map, code, fallback = "--") {
  return map[code] ? map[code].display : fallback;
}

function findItems(items, codes) {
  const wanted = {};
  codes.forEach((code) => {
    wanted[code] = true;
  });
  return (items || []).filter((item) => wanted[item.code]);
}

Page({
  data: {
    connected: false,
    loading: false,
    lastUpdated: "--",
    headline: {
      mangoId: "--",
      grade: "--",
      channel: "--",
      conclusion: "--"
    },
    maturity: [],
    sugar: [],
    rot: [],
    vision: [],
    data: []
  },

  onLoad() {
    this.refreshStatus();
    this.timer = setInterval(() => this.refreshStatus(), 3000);
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
      .then((payload) => {
        const quality = payload.groups.quality || [];
        const map = itemMap(quality);
        this.setData({
          connected: true,
          loading: false,
          lastUpdated: this.formatTime(payload.updated_at),
          headline: {
            mangoId: display(map, "mango_id"),
            grade: display(map, "quality_grade"),
            channel: display(map, "suggested_channel"),
            conclusion: display(map, "final_status")
          },
          maturity: findItems(quality, ["maturity_label", "maturity_score", "maturity_confidence"]),
          sugar: findItems(quality, ["sugar_label", "sugar_score"]),
          rot: findItems(quality, ["rot_status", "rot_score"]),
          vision: findItems(quality, ["yolo_label", "yolo_confidence"]),
          data: findItems(quality, ["data_status", "last_update"])
        });
      })
      .catch((err) => {
        this.setData({ connected: false, loading: false });
        if (err && err.error) {
          wx.showToast({ title: err.error, icon: "none" });
        }
      });
  },

  onRefreshTap() {
    this.refreshStatus();
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
