#!/usr/bin/env python3
"""Apply the reproducible gateway configuration in gateway-config/ (idempotent).

  opc-connection.template.json -> ignition/opc-connection, one per cell of docs/cells.csv ("C01".."C05")
  device.template.json         -> com.inductiveautomation.opcua/device, one per cell ("C01_IO01"..)
  opc-connection-*.json, device-*.json -> applied as they are (other, non-cell resources)
  historian-provider-*.json    -> com.inductiveautomation.historian/historian-provider
  opcua-server-config.json     -> com.inductiveautomation.opcua/server-config (singleton PUT)
  system-properties.patch.json -> ignition/system-properties (singleton, keys merged into the current config)

Templates use the placeholders {cell}, {bay}, {host} (controller_host) and
{io_device} from cells.csv. Existing resources are updated (PUT with their
current signature), missing ones created, RETIRED ones deleted. OPC
connections get the client keystore alias password, Ignition's default
"password", encrypted by this gateway, so no ciphertext sits in git.

Usage: scripts/apply_gateway_config.py [--dry-run]
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ign  # noqa: E402

CONFIG = ign.ROOT / "gateway-config"
CELLS = ign.ROOT / "docs/cells.csv"
KEYSTORE_ALIAS_PASSWORD = "password"     # Ignition default for the "client" keystore alias
RETIRED = {"com.inductiveautomation.opcua/device": ["IO01"]}   # single-cell lab (before the 5-cell layout)


def from_template(name: str) -> list[dict]:
    template = (CONFIG / name).read_text()
    items = []
    with open(CELLS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            text = template
            for key, value in (("cell", row["cell"]), ("bay", row["bay"]), ("host", row["controller_host"]),
                               ("io_device", row["io_device"])):
                text = text.replace("{" + key + "}", value)
            items.extend(json.loads(text))
    return items


def load(template: str, pattern: str) -> list[dict]:
    items = from_template(template)
    for f in sorted(CONFIG.glob(pattern)):
        items.extend(json.loads(f.read_text()))
    return items


def retire(rtype: str, dry: bool) -> None:
    existing = {i["name"] for i in ign.call("GET", f"/resources/names/{rtype}")["items"]}
    for name in RETIRED.get(rtype, []):
        if name not in existing:
            continue
        if dry:
            print(f"would DELETE {rtype}: {name}")
            continue
        sig = ign.call("GET", f"/resources/find/{rtype}/{name}")["signature"]
        ign.call("DELETE", f"/resources/{rtype}/{name}/{sig}")
        print(f"DELETE {rtype}: {name} (retired)")


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
    conns = load("opc-connection.template.json", "opc-connection-*.json")
    for item in conns:
        item["config"]["settings"].setdefault("security", {})["keyStoreAliasPassword"] = \
            None if dry else encrypt(KEYSTORE_ALIAS_PASSWORD)
    upsert("ignition/opc-connection", conns, dry)
    retire("com.inductiveautomation.opcua/device", dry)
    upsert("com.inductiveautomation.opcua/device", load("device.template.json", "device-*.json"), dry)
    historians = [item for f in sorted(CONFIG.glob("historian-provider-*.json")) for item in json.loads(f.read_text())]
    upsert("com.inductiveautomation.historian/historian-provider", historians, dry)
    f = CONFIG / "system-properties.patch.json"
    if f.exists():
        patch = json.loads(f.read_text())
        current = ign.call("GET", "/resources/singleton/ignition/system-properties")
        config = dict(current["config"], **patch)
        if config == current["config"]:
            print("system-properties: unchanged")
        elif dry:
            print(f"would PATCH ignition/system-properties: {patch}")
        else:
            r = ign.call("PUT", "/resources/ignition/system-properties",
                         [{"collection": "core", "enabled": True, "config": config, "signature": current["signature"]}])
            print("PUT system-properties ->", "ok" if r.get("success") else r)
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
