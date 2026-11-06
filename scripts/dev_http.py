"""Trust the local reverse proxy (Codespaces / VS Code port forwarding).

Run with .venv/bin/python before starting Home Assistant. The forwarder sends
X-Forwarded-For from 127.0.0.1/::1, which Home Assistant answers with
"400: Bad Request" unless the HTTP settings trust it. Those settings live in
Settings > System > Network (stored in config/.storage/http), which can't be
reached through the proxy before they are set, so seed them here.
"""

import json
import sys
from pathlib import Path

from homeassistant.components.http import config as http_config

PROXIES = ["127.0.0.1", "::1"]

path = Path(sys.argv[1] if len(sys.argv) > 1 else "config") / ".storage" / "http"
if path.exists():
    store = json.loads(path.read_text())
else:
    store = {
        "version": http_config.STORAGE_VERSION,
        "minor_version": http_config.STORAGE_MINOR_VERSION,
        "key": http_config.STORAGE_KEY,
        "data": {
            "stable": {**http_config._DEFAULT_CONFIG},
            "pending": None,
            "yaml_migration_done": True,
        },
    }

changed = False
for slot in ("stable", "pending"):
    conf = store["data"].get(slot)
    if conf is None:
        continue
    if not conf.get("use_x_forwarded_for"):
        conf["use_x_forwarded_for"] = True
        changed = True
    trusted = conf.setdefault("trusted_proxies", [])
    for proxy in PROXIES:
        if proxy not in trusted:
            trusted.append(proxy)
            changed = True

if changed:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, default=str) + "\n")
    print(f"Trusting the local proxy ({', '.join(PROXIES)}) in {path}")
