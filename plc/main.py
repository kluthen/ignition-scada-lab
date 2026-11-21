"""Simulated cell controller: one process serving OPC UA and Modbus TCP.

Every scan:  OPC UA client writes -> program.scan(dt) -> OPC UA publish.
Modbus clients read/write the I/O image directly (tags.py maps it to signals).

Environment:
  PLC_PROGRAM      module under programs/ (default: cell)
  PLC_SCAN_MS      scan period in ms (default: 100)
  MODBUS_PORT      Modbus TCP port (default: 502)
  OPCUA_ENDPOINT   default opc.tcp://0.0.0.0:4840/ignition-lab/
  REGISTRY_CSV     default /registry/opcua-registry.csv (docs/opcua-registry.csv, mounted)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import importlib
import logging
import os
import time

import registry
from io_image import IOImage
from modbus_server import start_server
from opcua_server import OpcUaServer
from tags import Tags

log = logging.getLogger("plc")


async def scan_loop(program, opc: OpcUaServer, period: float) -> None:
    last = time.monotonic()
    overruns = 0
    while True:
        await asyncio.sleep(max(0.0, period - (time.monotonic() - last)))
        now = time.monotonic()
        dt_s, last = now - last, now
        try:
            opc.pull()
            program.scan(dt_s)
            await opc.push()
        except Exception:
            log.exception("scan error (controller keeps running)")
        if time.monotonic() - now > period:
            overruns += 1
            if overruns % 50 == 1:
                log.warning("scan overrun: %.0f ms (period %.0f ms), %d so far",
                            (time.monotonic() - now) * 1000, period * 1000, overruns)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    for noisy in ("asyncua", "asyncua.server", "asyncua.common"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    name = os.environ.get("PLC_PROGRAM", "cell")
    period = int(os.environ.get("PLC_SCAN_MS", "100")) / 1000.0
    port = int(os.environ.get("MODBUS_PORT", "502"))
    endpoint = os.environ.get("OPCUA_ENDPOINT", "opc.tcp://0.0.0.0:4840/ignition-lab/")

    signals = registry.load()
    log.info("registry: %d signals (%d OPC UA, %d Modbus)", len(signals),
             sum(s.protocol == "opcua" for s in signals.values()),
             sum(s.protocol == "modbus" for s in signals.values()))
    io = IOImage()
    tags = Tags(signals, io, dt.datetime.now(dt.timezone.utc))
    program = importlib.import_module(f"programs.{name}").Program(tags)

    opc = OpcUaServer(tags, endpoint)
    await opc.start()
    modbus = await start_server(io, "0.0.0.0", port)
    log.info("program '%s' running, scan %.0f ms", name, period * 1000)
    async with modbus:
        await asyncio.gather(modbus.serve_forever(), scan_loop(program, opc, period))


if __name__ == "__main__":
    asyncio.run(main())
