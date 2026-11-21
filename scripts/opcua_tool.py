#!/usr/bin/env python3
"""Browse / read / write OPC UA nodes (asyncua). Runs in the workspace container.

  scripts/opc browse [NODEID] [--depth N]      default: Objects folder, depth 2
  scripts/opc read NODEID [NODEID…]
  scripts/opc write NODEID VALUE [--type Boolean|Int16|UInt16|Int32|Float|Double|String]
  scripts/opc watch NODEID [NODEID…] [--period 1]

Endpoint: $OPCUA_URL, default opc.tcp://gateway:62541 (Ignition's server).
Examples:
  scripts/opc read 'ns=1;s=[plc_modbus]IRUS0' 'ns=2;s=[default]_probe/TankLevel'
  scripts/opc browse 'ns=2;s=Tag Providers' --depth 3
Anonymous sessions can read but not write on Ignition's server. Writes are
meant for simulator servers that allow them.
"""

from __future__ import annotations

import argparse
import asyncio
import os

from asyncua import Client, ua

URL = os.environ.get("OPCUA_URL", "opc.tcp://gateway:62541")


async def browse(c: Client, nodeid: str | None, depth: int) -> None:
    node = c.get_node(nodeid) if nodeid else c.nodes.objects

    async def walk(n, level):
        for ch in await n.get_children():
            name = (await ch.read_browse_name()).to_string()
            cls = (await ch.read_node_class()).name
            val = ""
            if cls == "Variable":
                try:
                    val = f" = {await ch.read_value()!r}"
                except Exception as e:  # noqa: BLE001 - show any read failure inline
                    val = f" (read error: {e})"
            print(f"{'  ' * level}{name}  [{cls}]  {ch.nodeid.to_string()}{val}")
            if level + 1 < depth:
                await walk(ch, level + 1)

    await walk(node, 0)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["browse", "read", "write", "watch"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--type", default=None)
    ap.add_argument("--period", type=float, default=1.0)
    a = ap.parse_args()
    async with Client(URL) as c:
        if a.cmd == "browse":
            await browse(c, a.args[0] if a.args else None, a.depth)
        elif a.cmd == "read":
            for nid in a.args:
                dv = await c.get_node(nid).read_data_value()
                print(f"{nid} = {dv.Value.Value!r}  ({dv.StatusCode.name}, {dv.SourceTimestamp})")
        elif a.cmd == "write":
            nid, raw = a.args[0], a.args[1]
            node = c.get_node(nid)
            vtype = ua.VariantType[a.type] if a.type else await node.read_data_type_as_variant_type()
            conv = {ua.VariantType.Boolean: lambda s: s.lower() in ("1", "true", "yes", "on"),
                    ua.VariantType.Float: float, ua.VariantType.Double: float, ua.VariantType.String: str}
            value = conv.get(vtype, int)(raw)
            await node.write_value(ua.DataValue(ua.Variant(value, vtype)))
            print(f"{nid} <- {value!r} ({vtype.name})")
        elif a.cmd == "watch":
            nodes = [c.get_node(n) for n in a.args]
            while True:
                vals = [await n.read_value() for n in nodes]
                print("  ".join(f"{n}={v!r}" for n, v in zip(a.args, vals)), flush=True)
                await asyncio.sleep(a.period)


if __name__ == "__main__":
    asyncio.run(main())
