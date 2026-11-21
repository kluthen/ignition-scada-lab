#!/usr/bin/env python3
"""Apply the reproducible gateway configuration in gateway-config/ (idempotent).

  opc-connection-*.json  -> ignition/opc-connection
  device-*.json          -> com.inductiveautomation.opcua/device
  opcua-server-config.json -> com.inductiveautomation.opcua/server-config (singleton PUT)

Existing resources are updated (PUT with their current signature), missing ones
created. OPC connections get the client keystore alias password, Ignition's
default "password", encrypted by this gateway, so no ciphertext sits in git.

Usage: scripts/apply_gateway_config.py [--dry-run]
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ign  # noqa: E402

CONFIG = ign.ROOT / "gateway-config"
KEYSTORE_ALIAS_PASSWORD = "password"     # Ignition default for the "client" keystore alias


def encrypt(text: str) -> dict:
    return {"type": "Embedded",
            "data": json.loads(ign.call("POST", "/encryption/encrypt", text.encode(), raw=True, ctype="text/plain"))}


def upsert(rtype: str, items: list[dict], dry: bool) -> None:
    existing = {i["name"] for i in ign.call("GET", f"/resources/names/{rtype}")["items"]}
    create = [i for i in items if i["name"] not in existing]
    update = [i for i in items if i["name"] in existing]
    for i in update:
        i["signature"] = ign.call("GET", f"/resources/find/{rtype}/{i['name']}")["signature"]
    for method, batch in (("POST", create), ("PUT", update)):
        if not batch:
            continue
        names = ", ".join(i["name"] for i in batch)
        if dry:
            print(f"would {method} {rtype}: {names}")
            continue
        r = ign.call(method, f"/resources/{rtype}", batch)
        print(f"{method} {rtype}: {names} -> {'ok' if r.get('success') else r}")


def main() -> None:
    dry = "--dry-run" in sys.argv
    conns = []
    for f in sorted(CONFIG.glob("opc-connection-*.json")):
        for item in json.loads(f.read_text()):
            item["config"]["settings"].setdefault("security", {})["keyStoreAliasPassword"] = \
                None if dry else encrypt(KEYSTORE_ALIAS_PASSWORD)
            conns.append(item)
    upsert("ignition/opc-connection", conns, dry)
    devices = [item for f in sorted(CONFIG.glob("device-*.json")) for item in json.loads(f.read_text())]
    upsert("com.inductiveautomation.opcua/device", devices, dry)
    f = CONFIG / "opcua-server-config.json"
    if f.exists():
        body = json.loads(f.read_text())
        current = ign.call("GET", "/resources/singleton/com.inductiveautomation.opcua/server-config")
        body[0]["signature"] = current["signature"]
        if current["config"] == body[0]["config"]:
            print("server-config: unchanged")
        elif dry:
            print("would PUT com.inductiveautomation.opcua/server-config")
        else:
            r = ign.call("PUT", "/resources/com.inductiveautomation.opcua/server-config", body)
            print("PUT server-config ->", "ok" if r.get("success") else r)


if __name__ == "__main__":
    main()
