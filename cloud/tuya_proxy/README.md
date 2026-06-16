# Tuya Cloud Proxy

This small backend keeps Tuya Cloud credentials away from the WeChat Mini Program.
It signs Tuya OpenAPI requests, reads device DP status, and forwards validated
control commands.

## Run

Mock mode, no Tuya credentials required:

```bash
python3 /home/elf/projects/cloud/tuya_proxy/tuya_proxy.py --mock --host 0.0.0.0 --port 8765
```

Real Tuya Cloud mode:

```bash
export TUYA_CLIENT_SECRET='your-access-secret'
python3 /home/elf/projects/cloud/tuya_proxy/tuya_proxy.py --host 0.0.0.0 --port 8765
```

Alternatively create `/home/elf/projects/config/tuya_cloud_secrets.json` from
`tuya_cloud_secrets.json.example`. That file is ignored by git.

The proxy API used by the mini program:

- `GET /api/health`
- `GET /api/device/config`
- `GET /api/device/status`
- `POST /api/device/command`
- `POST /api/device/commands`
