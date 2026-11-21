"""Simulated PLC: runs a program's scan cycle and serves its I/O over Modbus TCP.

Environment:
  PLC_PROGRAM   module under programs/ to run (default: tank)
  PLC_SCAN_MS   scan period in milliseconds (default: 100)
  MODBUS_PORT   listening port (default: 502)
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import time

from io_image import IOImage
from modbus_server import start_server

log = logging.getLogger("plc")


async def scan_loop(program, period: float) -> None:
    last = time.monotonic()
    while True:
        await asyncio.sleep(period)
        now = time.monotonic()
        try:
            program.scan(now - last)
        except Exception:
            log.exception("scan error (program keeps running)")
        last = now


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    name = os.environ.get("PLC_PROGRAM", "tank")
    period = int(os.environ.get("PLC_SCAN_MS", "100")) / 1000.0
    port = int(os.environ.get("MODBUS_PORT", "502"))

    io = IOImage()
    program = importlib.import_module(f"programs.{name}").Program(io)
    log.info("program '%s' loaded, scan %.0f ms", name, period * 1000)

    server = await start_server(io, "0.0.0.0", port)
    async with server:
        await asyncio.gather(server.serve_forever(), scan_loop(program, period))


if __name__ == "__main__":
    asyncio.run(main())
