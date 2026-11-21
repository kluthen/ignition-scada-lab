#!/usr/bin/env python3
"""Generate and import the Ignition tags of the finishing area from the registry.

docs/opcua-registry.csv describes one PIC-200 cell (written for C01): it becomes
two UDTs (Ignition user-defined types), and docs/cells.csv lists their instances.

  [default]_types_/PIC200_Cell   parameters CellId, OpcServer, IoDevice
      OPC UA members  -> opcServer {OpcServer}, item path = CSV node_id with the cell's own
                         nodes as s={CellId}.… (plc/instance.py names them that way)
      Modbus members  -> Ignition's own OPC UA server, item path ns=1;s=[{IoDevice}]<address>,
                         Linear scaling when modbus_scale != 1
      MES members     -> MES/AutoRun (memory), MES/Tick (expression, 1 s) and tag event scripts
                         calling the project library of project "plant" (mes.cell, labsim.autopilot)
      history         -> HISTORY below, to the SQL Historian "Historian"
  [default]ANN/FIN/C01..C05      instances
  [sim]_types_/PIC200_Sim        parameter OpcServer; Sim.* rows (instructor signals)
  [sim]C01..C05                  instances

- Tag groups: Fast 250 ms (cell/robot/camera), Default 1000 ms (Identification, Admin, MES),
  Modbus 500 ms (IO01 signals), as recommended in scenario.md section 7.
- R rows are readOnly tags; description -> documentation; min/max -> engLow/engHigh.

Writes gateway-config/tags/<provider>.json (generated, reviewable), then imports
them with collision policy Overwrite. Members removed from the CSV are not
deleted in Ignition; delete them in the Designer or under
ignition/data/config/resources/core/ignition/tag-type-definition.

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
CELLS = ign.ROOT / "docs/cells.csv"
OUT = ign.ROOT / "gateway-config/tags"
TAG_GROUP_DIR = ign.ROOT / "ignition/data/config/resources/core/ignition/tag-group"
TEMPLATE_CELL = "C01"
CELL_ROOT, SIM_ROOT = "[default]ANN/FIN/C01/", "[sim]Sim/"
CELL_UDT, SIM_UDT = "PIC200_Cell", "PIC200_Sim"
AREA = ["ANN", "FIN"]
HISTORIAN = "Historian"
TAG_GROUPS = {"Fast": 250, "Modbus": 500}            # "Default" (1000 ms) exists already
DATATYPES = {"Boolean": "Boolean", "Byte": "Int2", "UInt16": "Int4", "Int32": "Int4", "UInt32": "Int8",
             "Double": "Float8", "String": "String", "DateTime": "DateTime"}

# Members stored by the historian (template signal name -> analog deadband, None = on every change).
HISTORY = {
    "C01.Status.StateCurrent": None, "C01.Status.UnitModeCurrent": None, "C01.Admin.StopReason": None,
    "C01.Status.CurMachSpeed": 0.1, "C01.Admin.ProdProcessedCount": None, "C01.Admin.ProdDefectiveCount": None,
    "C01.Admin.ProdConsumedCount": None, "C01.Order.Active.OrderId": None, "C01.Order.Active.PartType": None,
    "C01.Order.Active.GoodCount": None, "C01.Order.Active.RejectCount": None,
    "C01.Traceability.BufferCount": None, "C01.Traceability.LostCount": None,
    "QS01.Status.LastMeasurement": None, "RB01.Status.LastCycleTime": None,
    "CV01.Status.PartsOnConveyor": None, "CV01.Status.MotorCurrent": 0.02, "CV02.Status.MotorCurrent": 0.02,
    "RJ01.Status.Count": None, "UT01.Status.AirPressure": 0.02, "UT01.Status.ActivePower": 0.02,
    "UT01.Status.EnergyTotal": None,
}

# Tag event scripts (body of valueChanged(tag, tagPath, previousValue, currentValue, initialChange,
# missedEvents)). Every scripted member sits two levels below the instance, so the instance path
# is tagPath minus its last two segments.
BASE = 'str(tagPath).rsplit("/", 2)[0]'
EVENT_SCRIPTS = {
    "C01.Traceability.DataReady": f"\tif currentValue.value:\n\t\tmes.cell.store_record({BASE})",
    "C01.Status.StateCurrent": f"\tmes.cell.log_state({BASE}, currentValue)",
}
MES_MEMBERS = [
    {"name": "AutoRun", "tagType": "AtomicTag", "valueSource": "memory", "dataType": "Boolean", "value": True,
     "documentation": "Lab autopilot drives this cell (labsim.autopilot): dispatch, start, reset, empty the "
                      "reject bin. Set false to drive the cell by hand (HMI, smoke test)."},
    {"name": "Tick", "tagType": "AtomicTag", "valueSource": "expr", "dataType": "DateTime",
     "expression": "now(1000)", "tagGroup": "Default",
     "documentation": "Changes every second; its value-changed script runs the cell's MES cycle (mes.cell.tick).",
     "eventScripts": [{"eventid": "valueChanged", "script": f"\tmes.cell.tick({BASE})"}]},
]


def param(binding: str) -> dict:
    return {"bindType": "parameter", "binding": binding}


def member(row: dict) -> dict:
    tag = {"name": row["ignition_tag_path"].rsplit("/", 1)[-1], "tagType": "AtomicTag", "valueSource": "opc",
           "dataType": DATATYPES[row["data_type"]], "documentation": row["description"]}
    if row["protocol"] == "opcua":
        node = row["node_id"]
        if row["signal"] == TEMPLATE_CELL or row["signal"].startswith(TEMPLATE_CELL + "."):
            node = node.replace(f";s={TEMPLATE_CELL}", ";s={CellId}", 1)
        tag.update(opcServer=param("{OpcServer}"), opcItemPath=param(node))
        folders = row["signal"].split(".")
        tag["tagGroup"] = "Default" if len(folders) > 1 and folders[1] in ("Identification", "Admin") else "Fast"
    else:
        tag.update(opcServer="Ignition OPC UA Server",
                   opcItemPath=param(f"ns=1;s=[{{IoDevice}}]{row['ignition_modbus_address']}"), tagGroup="Modbus")
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
    if row["signal"] in HISTORY:
        tag.update(historyEnabled=True, historyProvider=HISTORIAN)
        if HISTORY[row["signal"]] is not None:
            tag.update(historicalDeadbandStyle="Analog", historicalDeadband=HISTORY[row["signal"]])
    if row["signal"] in EVENT_SCRIPTS:
        tag["eventScripts"] = [{"eventid": "valueChanged", "script": EVENT_SCRIPTS[row["signal"]]}]
    return tag


def folder(node: dict, name: str) -> dict:
    child = next((t for t in node["tags"] if t["name"] == name), None)
    if child is None:
        child = {"name": name, "tagType": "Folder", "tags": []}
        node["tags"].append(child)
    return child


def udt(name: str, parameters: dict, rows: list[dict], root: str) -> dict:
    """UDT definition from the CSV rows below `root` (an Ignition tag path prefix)."""
    t = {"name": name, "tagType": "UdtType", "tags": [],
         "parameters": {k: {"dataType": "String", "value": v} for k, v in parameters.items()}}
    for row in rows:
        path = row["ignition_tag_path"]
        if not path.startswith(root):
            continue
        parts = path[len(root):].split("/")
        node = t
        for name_ in parts if row["node_class"] == "Object" else parts[:-1]:
            node = folder(node, name_)
        if row["node_class"] != "Object":
            node["tags"].append(member(row))
    return t


def instance(name: str, type_id: str, parameters: dict) -> dict:
    return {"name": name, "tagType": "UdtInstance", "typeId": type_id,
            "parameters": {k: {"dataType": "String", "value": v} for k, v in parameters.items()}}


def build() -> dict[str, dict]:
    with open(CSV, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["ignition_tag_path"]]
    with open(CELLS, newline="", encoding="utf-8") as f:
        cells = list(csv.DictReader(f))
    first = cells[0]
    cell_type = udt(CELL_UDT, {"CellId": first["cell"], "OpcServer": first["cell"], "IoDevice": first["io_device"]},
                    rows, CELL_ROOT)
    folder(cell_type, "MES")["tags"].extend(MES_MEMBERS)
    sim_type = udt(SIM_UDT, {"OpcServer": first["cell"]}, rows, SIM_ROOT)

    default = {"tags": [{"name": "_types_", "tagType": "Folder", "tags": [cell_type]}]}
    area = default
    for name in AREA:
        area = folder(area, name)
    area["tags"].extend(instance(c["cell"], CELL_UDT, {"CellId": c["cell"], "OpcServer": c["cell"],
                                                       "IoDevice": c["io_device"]}) for c in cells)
    sim = {"tags": [{"name": "_types_", "tagType": "Folder", "tags": [sim_type]}]}
    sim["tags"].extend(instance(c["cell"], SIM_UDT, {"OpcServer": c["cell"]}) for c in cells)
    return {"default": default, "sim": sim}


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


def count(tree: dict, tag_type: str) -> int:
    return json.dumps(tree).count(f'"tagType": "{tag_type}"')


def main() -> None:
    providers = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for provider, tree in providers.items():
        (OUT / f"{provider}.json").write_text(json.dumps(tree, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote gateway-config/tags/{provider}.json: 1 UDT with {count(tree, 'AtomicTag')} members, "
              f"{count(tree, 'UdtInstance')} instances")
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
