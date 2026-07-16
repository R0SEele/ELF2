const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");


const APP_JS = path.resolve(__dirname, "../wechat_miniapp/app.js");

function loadApp(initialStorage = {}) {
  const storage = Object.assign({}, initialStorage);
  let app = null;
  const wx = {
    cloud: { init() {} },
    getStorageSync(key) { return storage[key]; },
    setStorageSync(key, value) { storage[key] = value; },
    removeStorageSync(key) { delete storage[key]; }
  };
  const context = {
    App(definition) { app = definition; },
    Object,
    Promise,
    String,
    Number,
    Boolean,
    Date,
    setTimeout(callback) { callback(); return 1; },
    wx
  };
  vm.runInNewContext(fs.readFileSync(APP_JS, "utf8"), context, { filename: APP_JS });
  return { app, storage };
}

async function main() {
  {
    const { app, storage } = loadApp({ apiBase: "http://127.0.0.1:8765" });
    app.onLaunch();
    assert.strictEqual(app.globalData.useCloud, true);
    assert.strictEqual(app.globalData.apiBase, "cloud://cloud1-d3gawfd5o88014f88");
    assert.strictEqual(storage.connectionStorageVersion, 2);
  }

  {
    const { app } = loadApp({
      apiBase: "http://192.168.1.20:8765",
      connectionStorageVersion: 2
    });
    app.onLaunch();
    assert.strictEqual(app.globalData.useCloud, false);
    assert.strictEqual(app.globalData.apiBase, "http://192.168.1.20:8765");
  }

  {
    const { app } = loadApp();
    const responses = [
      { status: { sorter_position: "center", device_status: "running" } },
      { status: { sorter_position: "right", device_status: "running" } }
    ];
    app.request = (requestPath) => requestPath === "/api/device/command"
      ? Promise.resolve({ ok: true })
      : Promise.resolve(responses.shift());
    const result = await app.sendDeviceCommand("sorter_position", "right");
    assert.strictEqual(result.acknowledgement.acknowledged, true);
    assert.strictEqual(result.acknowledgement.value, "right");
  }

  {
    const { app } = loadApp();
    app.request = (requestPath) => requestPath === "/api/device/command"
      ? Promise.resolve({ ok: true })
      : Promise.resolve({ status: { device_status: "error", error_message: "motor timeout" } });
    await assert.rejects(
      app.sendDeviceCommand("conveyor_cmd", "forward"),
      (error) => error && error.error === "motor timeout"
    );
  }

  {
    const { app } = loadApp();
    let statusCall = 0;
    app.request = (requestPath) => {
      if (requestPath === "/api/device/command") {
        return Promise.resolve({ ok: true });
      }
      statusCall += 1;
      if (statusCall === 1) {
        return Promise.resolve({
          status: { conveyor_cmd: "stop", device_status: "running", error_message: "" },
          status_updated_at: { conveyor_cmd: 100, device_status: 100, error_message: 100 }
        });
      }
      if (statusCall === 2) {
        return Promise.resolve({
          status: { conveyor_cmd: "forward", device_status: "running", error_message: "" },
          status_updated_at: { conveyor_cmd: 200, device_status: 100, error_message: 100 }
        });
      }
      return Promise.resolve({
        status: { conveyor_cmd: "forward", device_status: "error", error_message: "motor rejected" },
        status_updated_at: { conveyor_cmd: 200, device_status: 201, error_message: 201 }
      });
    };
    await assert.rejects(
      app.sendDeviceCommand("conveyor_cmd", "forward"),
      (error) => error && error.error === "motor rejected"
    );
  }

  console.log("miniapp connection tests: OK");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
