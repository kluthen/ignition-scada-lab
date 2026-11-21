"""Minimal Modbus TCP server (no dependencies).

Supports FC 1, 2, 3, 4, 5, 6, 15, 16 over a single I/O image shared by every
unit id. Addresses are zero-based on the wire (Modbus PDU addressing).
"""

from __future__ import annotations

import asyncio
import logging
import struct

from io_image import IOImage

log = logging.getLogger("modbus")

ILLEGAL_FUNCTION = 1
ILLEGAL_ADDRESS = 2
ILLEGAL_VALUE = 3


class ModbusError(Exception):
    def __init__(self, code: int):
        self.code = code


def _check_range(table: list, start: int, qty: int, max_qty: int) -> None:
    if not 1 <= qty <= max_qty:
        raise ModbusError(ILLEGAL_VALUE)
    if start < 0 or start + qty > len(table):
        raise ModbusError(ILLEGAL_ADDRESS)


def _pack_bits(bits: list[bool]) -> bytes:
    out = bytearray((len(bits) + 7) // 8)
    for i, b in enumerate(bits):
        if b:
            out[i // 8] |= 1 << (i % 8)
    return bytes(out)


def _unpack_bits(data: bytes, qty: int) -> list[bool]:
    return [bool(data[i // 8] >> (i % 8) & 1) for i in range(qty)]


def handle_pdu(io: IOImage, pdu: bytes) -> bytes:
    fc = pdu[0]
    body = pdu[1:]
    try:
        if fc in (1, 2):
            start, qty = struct.unpack(">HH", body[:4])
            table = io.coils if fc == 1 else io.discrete_inputs
            _check_range(table, start, qty, 2000)
            data = _pack_bits(table[start:start + qty])
            return bytes([fc, len(data)]) + data
        if fc in (3, 4):
            start, qty = struct.unpack(">HH", body[:4])
            table = io.holding if fc == 3 else io.input_regs
            _check_range(table, start, qty, 125)
            data = struct.pack(f">{qty}H", *(v & 0xFFFF for v in table[start:start + qty]))
            return bytes([fc, len(data)]) + data
        if fc == 5:
            addr, value = struct.unpack(">HH", body[:4])
            if value not in (0x0000, 0xFF00):
                raise ModbusError(ILLEGAL_VALUE)
            _check_range(io.coils, addr, 1, 1)
            io.write_coils(addr, [value == 0xFF00])
            return pdu[:5]
        if fc == 6:
            addr, value = struct.unpack(">HH", body[:4])
            _check_range(io.holding, addr, 1, 1)
            io.write_holding(addr, [value])
            return pdu[:5]
        if fc == 15:
            start, qty, nbytes = struct.unpack(">HHB", body[:5])
            _check_range(io.coils, start, qty, 1968)
            if nbytes != (qty + 7) // 8 or len(body) < 5 + nbytes:
                raise ModbusError(ILLEGAL_VALUE)
            io.write_coils(start, _unpack_bits(body[5:5 + nbytes], qty))
            return bytes([fc]) + struct.pack(">HH", start, qty)
        if fc == 16:
            start, qty, nbytes = struct.unpack(">HHB", body[:5])
            _check_range(io.holding, start, qty, 123)
            if nbytes != qty * 2 or len(body) < 5 + nbytes:
                raise ModbusError(ILLEGAL_VALUE)
            io.write_holding(start, list(struct.unpack(f">{qty}H", body[5:5 + nbytes])))
            return bytes([fc]) + struct.pack(">HH", start, qty)
        raise ModbusError(ILLEGAL_FUNCTION)
    except struct.error:
        return bytes([fc | 0x80, ILLEGAL_VALUE])
    except ModbusError as e:
        return bytes([fc | 0x80, e.code])


async def _serve_client(io: IOImage, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    peer = writer.get_extra_info("peername")
    log.info("client connected: %s", peer)
    try:
        while True:
            header = await reader.readexactly(7)
            tid, pid, length, unit = struct.unpack(">HHHB", header)
            if pid != 0 or not 2 <= length <= 254:
                log.warning("bad MBAP header from %s, closing", peer)
                break
            pdu = await reader.readexactly(length - 1)
            reply = handle_pdu(io, pdu)
            writer.write(struct.pack(">HHHB", tid, 0, len(reply) + 1, unit) + reply)
            await writer.drain()
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    finally:
        log.info("client disconnected: %s", peer)
        writer.close()


async def start_server(io: IOImage, host: str, port: int) -> asyncio.base_events.Server:
    server = await asyncio.start_server(lambda r, w: _serve_client(io, r, w), host, port)
    log.info("Modbus TCP listening on %s:%d", host, port)
    return server
