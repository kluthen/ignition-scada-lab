#!/usr/bin/env python3
"""Generate and import the Ignition tags of the plant from docs/opcua-registry.csv.

- OPC UA rows    -> OPC tags on connection "C01", item path = CSV node_id (nsu= form)
- Modbus rows    -> OPC tags on Ignition's own server, item path ns=1;s=[IO01]<address>,
                    Linear scaling when modbus_scale != 1
- Sim rows       -> tag provider "sim" (created if missing), kept out of [default]
- Tag groups     -> Fast 250 ms (cell/robot/camera), Default 1000 ms (Identification, Admin),
                    Modbus 500 ms (IO01 signals), as recommended in scenario.md section 7
- R rows are readOnly tags; description -> documentation; min/max -> engLow/engHigh

Writes gateway-config/tags/<provider>.json (generated, reviewable), then imports
them with collision policy Overwrite. Tags removed from the CSV are not deleted
in Ignition; delete them by hand (Designer) or from ignition/data/config/.../tag-definition.

Usage: scripts/generate_tags.py [--no-import]
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ign  # noqa: E402

CSV = ign.ROOT / "docs/opcua-registry.csv"
OUT = ign.ROOT / "gateway-config/tags"
TAG_GROUP_DIR = ign.ROOT / "ignition/data/config/resources/core/ignition/tag-group"
OPC_CONNECTION, MODBUS_DEVICE = "C01", "IO01"
TAG_GROUPS = {"Fast": 250, "Modbus": 500}            # "Default" (1000 ms) exists already
DATATYPES = {"Boolean": "Boolean", "Byte": "Int2", "UInt16": "Int4", "Int32": "Int4", "UInt32": "Int8",
             "Double": "Float8", "String": "String", "DateTime": "DateTime"}


def tag_for(row: dict) -> dict:
    tag = {"name": row["ignition_tag_path"].rsplit("/", 1)[-1], "tagType": "AtomicTag", "valueSource": "opc",
           "dataType": DATATYPES[row["data_type"]], "documentation": row["description"]}
    if row["protocol"] == "opcua":
        tag.update(opcServer=OPC_CONNECTION, opcItemPath=row["node_id"])
        folders = row["signal"].split(".")
        tag["tagGroup"] = "Default" if len(folders) > 1 and folders[1] in ("Identification", "Admin") else "Fast"
    else:
        tag.update(opcServer="Ignition OPC UA Server",
                   opcItemPath=f"ns=1;s=[{MODBUS_DEVICE}]{row['ignition_modbus_address']}", tagGroup="Modbus")
        scale = float(row["modbus_scale"] or 1)
        if scale != 1:
            tag.update(scaleMode="Linear", rawLow=0, rawHigh=1000, scaledLow=0, scaledHigh=round(1000 * scale, 6))
    if row["eng_unit"]:
        tag["engUnit"] = row["eng_unit"]
    if row["data_type"] not in ("Boolean", "String", "DateTime"):
        for key, col in (("engLow", "min"), ("engHigh", "max")):
            if row[col]:
                tag[key] = float(row[col])
    if row["access"] == "R":
        tag["readOnly"] = True
    return tag


def build() -> dict[str, dict]:
    providers: dict[str, dict] = {}
    with open(CSV, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["ignition_tag_path"]]
    for row in rows:
        provider, path = row["ignition_tag_path"][1:].split("]", 1)
        root = providers.setdefault(provider, {"tags": []})
        node = root
        parts = path.split("/")
        is_folder = row["node_class"] == "Object"
        for name in parts if is_folder else parts[:-1]:
            child = next((t for t in node["tags"] if t["name"] == name), None)
            if child is None:
                child = {"name": name, "tagType": "Folder", "tags": []}
                node["tags"].append(child)
            node = child
        if not is_folder:
            node["tags"].append(tag_for(row))
    return providers


def ensure_provider(name: str) -> None:
    names = {i["name"] for i in ign.call("GET", "/resources/names/ignition/tag-provider")["items"]}
    if name in names:
        return
    default = ign.call("GET", "/resources/find/ignition/tag-provider/default")["config"]
    ign.call("POST", "/resources/ignition/tag-provider",
             [{"name": name, "enabled": True, "description": "Simulation-only signals (instructor). Not part of the plant.",
               "config": default}])
    print(f"created tag provider {name!r}")


def ensure_tag_groups(providers: list[str]) -> bool:
    created = False
    for provider in providers:
        for group, rate in TAG_GROUPS.items():
            d = TAG_GROUP_DIR / provider / group
            if d.exists():
                continue
            d.mkdir(parents=True)
            (d / "config.json").write_text(json.dumps({"config": {
                "mode": "Direct", "oneShot": False, "opcDataMode": "Subscribed", "optWriteTimeout": 60000,
                "optWrites": False, "rate": rate, "readAfterWrite": False}}, indent=2) + "\n")
            (d / "resource.json").write_text(json.dumps({"scope": "A", "version": 1, "restricted": False,
                                                         "overridable": True, "files": ["config.json"],
                                                         "attributes": {}}, indent=2) + "\n")
            print(f"created tag group {provider}/{group} ({rate} ms)")
            created = True
    return created


def main() -> None:
    providers = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for provider, tree in providers.items():
        (OUT / f"{provider}.json").write_text(json.dumps(tree, indent=2, ensure_ascii=False) + "\n")
        count = json.dumps(tree).count('"AtomicTag"')
        print(f"wrote gateway-config/tags/{provider}.json ({count} tags)")
    if "--no-import" in sys.argv:
        return
    for provider in providers:
        if provider != "default":
            ensure_provider(provider)
    if ensure_tag_groups(list(providers)):
        ign.call("POST", "/scan/config")
    for provider in providers:
        r = ign.call("POST", "/tags/import?provider=" + provider + "&type=json&collisionPolicy=Overwrite",
                     (OUT / f"{provider}.json").read_bytes())
        print(f"import [{provider}]: {r['successCount']} ok, {r['failureCount']} failed",
              *(f"\n  {x}" for x in r.get("failures", [])[:10]))


if __name__ == "__main__":
    main()
