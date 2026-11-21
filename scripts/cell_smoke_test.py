#!/usr/bin/env python3
"""Phase-1 smoke test of the simulated cell, over OPC UA (asyncua).

  1. Reset -> Idle (from Stopped or Complete; Clear first if Aborted)
  2. Start without a runnable order -> CmdResult 3 (RejectedInterlock)
  3. Load order TEST-<n> (PartType 1, 10 parts) -> LoadResult 1
  4. Start -> Execute, acknowledge every traceability record like the MES would
  5. Expect Complete within 60 s, GoodCount = 10, acknowledged records = new ProdProcessedCount

Run in the workspace container:  docker compose exec workspace python scripts/cell_smoke_test.py
Endpoint: $PLC_OPCUA_URL, default opc.tcp://plc:4840/ignition-lab/
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from asyncua import Client, ua

URL = os.environ.get("PLC_OPCUA_URL", "opc.tcp://plc:4840/ignition-lab/")
CELL = "urn:ignition-lab:cell"
ROBOT = "urn:ignition-lab:robot"
STATES = {2: "Stopped", 4: "Idle", 6: "Execute", 9: "Aborted", 17: "Complete"}


class Cell:
    def __init__(self, client: Client, ns: int):
        self.c, self.ns = client, ns

    def node(self, name: str):
        return self.c.get_node(ua.NodeId(name, self.ns))

    async def get(self, name: str):
        return await self.node(name).read_value()

    async def put(self, name: str, value, vtype: ua.VariantType) -> None:
        await self.node(name).write_value(ua.DataValue(ua.Variant(value, vtype)))

    async def command(self, code: int) -> int:
        before = await self.get("C01.Command.CmdCounter")
        await self.put("C01.Command.CntrlCmd", code, ua.VariantType.Int32)
        deadline = time.monotonic() + 2.0
        while await self.get("C01.Command.CmdCounter") == before:
            if time.monotonic() > deadline:
                raise AssertionError(f"CntrlCmd {code}: no CmdCounter change within 2 s")
            await asyncio.sleep(0.05)
        return await self.get("C01.Command.CmdResult")

    async def wait_state(self, state: int, timeout: float, ack=None) -> float:
        start = time.monotonic()
        while (current := await self.get("C01.Status.StateCurrent")) != state:
            if time.monotonic() - start > timeout:
                raise AssertionError(f"state {current}, expected {state} within {timeout} s")
            if ack:
                await ack()
            await asyncio.sleep(0.1)
        return time.monotonic() - start


def check(cond: bool, msg: str) -> None:
    print(("  ok    " if cond else "  FAIL  ") + msg)
    if not cond:
        raise SystemExit(1)


async def main() -> None:
    async with Client(URL) as client:
        cell = Cell(client, await client.get_namespace_index(CELL))
        state = await cell.get("C01.Status.StateCurrent")
        print(f"connected to {URL}, state {state} {await cell.get('C01.Status.StateCurrentName')}")

        if state == 9:
            check(await cell.command(9) == 1, "Clear accepted")
            await cell.wait_state(2, 5)
        elif state not in (2, 17, 4):
            check(await cell.command(3) == 1, "Stop accepted")
            await cell.wait_state(2, 30)
        if await cell.get("C01.Status.StateCurrent") in (2, 17):
            check(await cell.command(1) == 1, "Reset accepted")
            took = await cell.wait_state(4, 10)
            check(1.5 <= took <= 4.5, f"Resetting -> Idle in {took:.1f} s (2.0 s homing, +1.0 s if purging)")

        status = await cell.get("C01.Order.Active.OrderStatus")
        if status not in (1, 2):
            check(await cell.command(2) == 3, "Start without a runnable order -> CmdResult 3 RejectedInterlock")

        order_id = f"TEST-{int(time.time()) % 100000:05d}"
        await cell.put("C01.Order.Request.OrderId", order_id, ua.VariantType.String)
        await cell.put("C01.Order.Request.PartType", 1, ua.VariantType.Int32)
        await cell.put("C01.Order.Request.TargetQuantity", 10, ua.VariantType.UInt32)
        await cell.put("C01.Order.Request.LoadRequest", True, ua.VariantType.Boolean)
        await asyncio.sleep(0.4)
        check(await cell.get("C01.Order.Request.LoadResult") == 1, f"order {order_id} loaded (LoadResult 1)")
        check(not await cell.get("C01.Order.Request.LoadRequest"), "LoadRequest reset by the PLC")
        check(await cell.get("C01.Order.Active.OrderStatus") == 1, "OrderStatus 1 Loaded")

        processed0 = await cell.get("C01.Admin.ProdProcessedCount")
        acked: list[tuple] = []

        async def ack() -> None:
            if await cell.get("C01.Traceability.DataReady"):
                seq = await cell.get("C01.Traceability.Sequence")
                if not acked or acked[-1][0] != seq:
                    rec = (seq, await cell.get("C01.Traceability.PartId"), await cell.get("C01.Traceability.OrderId"),
                           await cell.get("C01.Traceability.Result"), await cell.get("C01.Traceability.MeasuredDiameter"))
                    acked.append(rec)
                    await cell.put("C01.Traceability.AckSequence", seq, ua.VariantType.UInt32)

        # drain records left over from earlier runs, so the count below is ours
        t0 = time.monotonic()
        while await cell.get("C01.Traceability.BufferCount") and time.monotonic() - t0 < 30:
            await ack()
            await asyncio.sleep(0.1)
        pre = len(acked)
        processed0 = await cell.get("C01.Admin.ProdProcessedCount")

        check(await cell.command(2) == 1, "Start accepted")
        await cell.wait_state(6, 3)
        print("  ..    Execute; waiting for Complete")
        took = await cell.wait_state(17, 60, ack)
        print(f"  ..    Complete after {took:.1f} s in Execute/Completing")
        t0 = time.monotonic()
        while (await cell.get("C01.Traceability.BufferCount") or await cell.get("C01.Traceability.DataReady")) \
                and time.monotonic() - t0 < 10:
            await ack()
            await asyncio.sleep(0.1)

        good = await cell.get("C01.Order.Active.GoodCount")
        rejects = await cell.get("C01.Order.Active.RejectCount")
        processed = await cell.get("C01.Admin.ProdProcessedCount") - processed0
        mine = acked[pre:]
        check(good == 10, f"GoodCount = {good}")
        check(await cell.get("C01.Order.Active.OrderStatus") == 3, "OrderStatus 3 Complete")
        check(len(mine) == processed, f"acknowledged records {len(mine)} = ProdProcessedCount delta {processed}")
        check(all(r[2] == order_id for r in mine), "every record belongs to the order")
        check(sum(r[3] == 1 for r in mine) == 10 and sum(r[3] == 2 for r in mine) == rejects,
              f"records: 10 Good, {rejects} Reject")

        robot = client.get_node(ua.NodeId("RB01.Status.CycleCount", await client.get_namespace_index(ROBOT)))
        print(f"PASS  ({good} good, {rejects} reject, {took:.1f} s; robot cycles since start {await robot.read_value()}, "
              f"last cycle {await client.get_node(ua.NodeId('RB01.Status.LastCycleTime', robot.nodeid.NamespaceIndex)).read_value()} s)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AssertionError as e:
        print(f"  FAIL  {e}")
        sys.exit(1)
