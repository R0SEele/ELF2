const app = getApp();
const environmentHistory = require("../../utils/environmentHistory");

const RANGE_OPTIONS = [
  { label: "10分钟", value: 10 },
  { label: "1小时", value: 60 },
  { label: "24小时", value: 1440 }
];

Page({
  data: {
    connected: false,
    lastUpdated: "--",
    metrics: environmentHistory.METRICS,
    metricIndex: 0,
    ranges: RANGE_OPTIONS,
    rangeIndex: 1,
    current: "--",
    minimum: "--",
    maximum: "--",
    average: "--",
    sampleCount: 0,
    activeRule: environmentHistory.METRICS[0].rule,
    alarms: [],
    empty: true
  },

  onReady() {
    this.prepareCanvas();
  },

  onShow() {
    this.startPolling();
  },

  onHide() {
    this.stopPolling();
  },

  onUnload() {
    this.stopPolling();
  },

  prepareCanvas() {
    wx.createSelectorQuery()
      .in(this)
      .select("#trendCanvas")
      .fields({ node: true, size: true })
      .exec((result) => {
        const target = result && result[0];
        if (!target || !target.node) {
          return;
        }
        const pixelRatio = wx.getWindowInfo ? wx.getWindowInfo().pixelRatio : wx.getSystemInfoSync().pixelRatio;
        this.canvas = target.node;
        this.canvasWidth = target.width;
        this.canvasHeight = target.height;
        this.context = this.canvas.getContext("2d");
        this.canvas.width = target.width * pixelRatio;
        this.canvas.height = target.height * pixelRatio;
        this.context.scale(pixelRatio, pixelRatio);
        this.renderTrend();
      });
  },

  startPolling() {
    this.stopPolling();
    this.refreshStatus();
    this.timer = setInterval(() => this.refreshStatus(), 3000);
  },

  stopPolling() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  },

  refreshStatus() {
    const now = Date.now();
    if (this._inflight && now - this._inflightAt < 10000) {
      return;
    }
    this._inflight = true;
    this._inflightAt = now;
    app.requestDeviceStatus()
      .then((payload) => {
        this._inflight = false;
        const result = environmentHistory.recordPayload(payload);
        this.setData({
          connected: true,
          lastUpdated: this.formatTime(payload.updated_at),
          alarms: result.alarms
        });
        this.renderTrend();
      })
      .catch((err) => {
        this._inflight = false;
        this.setData({ connected: false });
        if (err && err.error) {
          wx.showToast({ title: err.error, icon: "none" });
        }
        this.renderTrend();
      });
  },

  onMetricTap(event) {
    const index = Number(event.currentTarget.dataset.index);
    const metric = environmentHistory.METRICS[index];
    if (!metric) {
      return;
    }
    this.setData({ metricIndex: index, activeRule: metric.rule });
    this.renderTrend();
  },

  onRangeTap(event) {
    const index = Number(event.currentTarget.dataset.index);
    if (!RANGE_OPTIONS[index]) {
      return;
    }
    this.setData({ rangeIndex: index });
    this.renderTrend();
  },

  renderTrend() {
    const metric = environmentHistory.METRICS[this.data.metricIndex];
    const range = RANGE_OPTIONS[this.data.rangeIndex];
    if (!metric || !range) {
      return;
    }
    const points = environmentHistory.pointsFor(metric.code, range.value);
    this.updateSummary(points, metric);
    if (!this.context || !this.canvasWidth || !this.canvasHeight) {
      return;
    }
    this.drawChart(this.downsamplePoints(points, 420), metric);
  },

  downsamplePoints(points, limit) {
    if (points.length <= limit || limit < 4) {
      return points;
    }
    const bucketCount = Math.floor((limit - 2) / 2);
    const bucketSize = Math.ceil((points.length - 2) / bucketCount);
    const sampled = [points[0]];
    for (let start = 1; start < points.length - 1; start += bucketSize) {
      const bucket = points.slice(start, Math.min(start + bucketSize, points.length - 1));
      let minimum = bucket[0];
      let maximum = bucket[0];
      bucket.forEach((point) => {
        if (point.value < minimum.value) minimum = point;
        if (point.value > maximum.value) maximum = point;
      });
      if (minimum.timestamp <= maximum.timestamp) {
        sampled.push(minimum);
        if (maximum !== minimum) sampled.push(maximum);
      } else {
        sampled.push(maximum);
        if (maximum !== minimum) sampled.push(minimum);
      }
    }
    sampled.push(points[points.length - 1]);
    return sampled;
  },

  updateSummary(points, metric) {
    if (!points.length) {
      this.setData({
        current: "--",
        minimum: "--",
        maximum: "--",
        average: "--",
        sampleCount: 0,
        empty: true
      });
      return;
    }
    const values = points.map((point) => point.value);
    const sum = values.reduce((total, value) => total + value, 0);
    this.setData({
      current: environmentHistory.formatValue(values[values.length - 1], metric),
      minimum: environmentHistory.formatValue(Math.min.apply(null, values), metric),
      maximum: environmentHistory.formatValue(Math.max.apply(null, values), metric),
      average: environmentHistory.formatValue(sum / values.length, metric),
      sampleCount: points.length,
      empty: false
    });
  },

  drawChart(points, metric) {
    const ctx = this.context;
    const width = this.canvasWidth;
    const height = this.canvasHeight;
    const plot = { left: 46, top: 20, right: width - 14, bottom: height - 34 };
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);

    if (!points.length) {
      ctx.fillStyle = "#93a49e";
      ctx.font = "14px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("等待环境数据上报", width / 2, height / 2);
      return;
    }

    const values = points.map((point) => point.value);
    let minValue = Math.min.apply(null, values);
    let maxValue = Math.max.apply(null, values);
    if (Number.isFinite(metric.min)) minValue = Math.min(minValue, metric.min);
    if (Number.isFinite(metric.max)) maxValue = Math.max(maxValue, metric.max);
    const span = Math.max(maxValue - minValue, Math.max(Math.abs(maxValue) * 0.05, 1));
    const yMin = minValue - span * 0.12;
    const yMax = maxValue + span * 0.12;
    const startTime = points[0].timestamp;
    const endTime = points[points.length - 1].timestamp;
    const timeSpan = Math.max(endTime - startTime, 1);
    const xAt = points.length === 1
      ? () => (plot.left + plot.right) / 2
      : (timestamp) => plot.left + ((timestamp - startTime) / timeSpan) * (plot.right - plot.left);
    const yAt = (value) => plot.bottom - ((value - yMin) / (yMax - yMin)) * (plot.bottom - plot.top);

    ctx.strokeStyle = "#e7ecea";
    ctx.lineWidth = 1;
    ctx.fillStyle = "#7f918b";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "right";
    for (let index = 0; index <= 3; index += 1) {
      const ratio = index / 3;
      const y = plot.top + ratio * (plot.bottom - plot.top);
      const labelValue = yMax - ratio * (yMax - yMin);
      ctx.beginPath();
      ctx.moveTo(plot.left, y);
      ctx.lineTo(plot.right, y);
      ctx.stroke();
      ctx.fillText(labelValue.toFixed(metric.decimals), plot.left - 7, y + 4);
    }

    [metric.min, metric.max].forEach((threshold) => {
      if (!Number.isFinite(threshold)) {
        return;
      }
      const y = yAt(threshold);
      ctx.save();
      ctx.setLineDash([5, 4]);
      ctx.strokeStyle = "#e1543b";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(plot.left, y);
      ctx.lineTo(plot.right, y);
      ctx.stroke();
      ctx.restore();
    });

    ctx.strokeStyle = metric.color;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    points.forEach((point, index) => {
      const x = xAt(point.timestamp);
      const y = yAt(point.value);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    const latest = points[points.length - 1];
    ctx.fillStyle = metric.color;
    ctx.beginPath();
    ctx.arc(xAt(latest.timestamp), yAt(latest.value), 3.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#7f918b";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(this.formatAxisTime(startTime), plot.left, height - 10);
    ctx.textAlign = "right";
    ctx.fillText(this.formatAxisTime(endTime), plot.right, height - 10);
  },

  formatAxisTime(timestamp) {
    const date = new Date(timestamp);
    const pad = (value) => String(value).padStart(2, "0");
    return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  },

  formatTime(timestamp) {
    if (!timestamp) {
      return "--";
    }
    const date = new Date(timestamp);
    const pad = (value) => String(value).padStart(2, "0");
    return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  }
});
