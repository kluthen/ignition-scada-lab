"""One namespace for every signal of the registry, whatever its protocol.

The cell program reads and writes `tags["C01.Status.StateCurrent"]`.
- OPC UA signals live in a dict, synchronised with the OPC UA server by opcua_server.py.
- Modbus signals are views on the IOImage tables: engineering value = raw x scale,
  32-bit values span two registers, high word first.
Unknown names raise KeyError, so a typo in the program fails loudly.
"""

from __future__ import annotations

import datetime as dt

from io_image import IOImage
from registry import Signal

_TABLES = {"coil": "coils", "discrete_input": "discrete_inputs", "holding": "holding", "input": "input_regs"}
_INT_MAX = {"Byte": 0xFF, "UInt16": 0xFFFF, "UInt32": 0xFFFFFFFF, "Int32": None}


class Tags:
    def __init__(self, signals: dict[str, Signal], io: IOImage, startup: dt.datetime):
        self.signals = signals
        self.io = io
        self.values: dict[str, object] = {}
        for s in signals.values():
            if s.is_variable:
                self[s.name] = s.initial_value(startup)

    # -- access ---------------------------------------------------------------
    def __getitem__(self, name: str):
        s = self.signals[name]
        if s.protocol == "modbus":
            return self._mb_read(s)
        return self.values[name]

    def __setitem__(self, name: str, value) -> None:
        s = self.signals[name]
        if s.protocol == "modbus":
            self._mb_write(s, value)
            return
        if s.data_type in _INT_MAX:
            value = int(value)
            if _INT_MAX[s.data_type] is not None:
                value &= _INT_MAX[s.data_type]
        elif s.data_type == "Double":
            value = float(value)
        elif s.data_type == "Boolean":
            value = bool(value)
        self.values[name] = value

    def inc(self, name: str, step: int = 1) -> None:
        self[name] = self[name] + step

    # -- Modbus mapping -------------------------------------------------------
    def _addr(self, s: Signal) -> list[int]:
        a = s.modbus_address
        if "-" in a:
            lo, hi = (int(x) for x in a.split("-"))
            return list(range(lo, hi + 1))
        return [int(a)]

    def _mb_read(self, s: Signal):
        table = getattr(self.io, _TABLES[s.modbus_table])
        addrs = self._addr(s)
        if s.modbus_table in ("coil", "discrete_input"):
            return bool(table[addrs[0]])
        raw = 0
        for a in addrs:                      # high word first
            raw = (raw << 16) | (table[a] & 0xFFFF)
        if s.data_type == "Double":
            return raw * s.modbus_scale
        return raw

    def _mb_write(self, s: Signal, value) -> None:
        table = getattr(self.io, _TABLES[s.modbus_table])
        addrs = self._addr(s)
        if s.modbus_table in ("coil", "discrete_input"):
            table[addrs[0]] = bool(value)
            return
        raw = int(round(value / s.modbus_scale)) if s.data_type == "Double" else int(value)
        raw = max(0, min(raw, (1 << (16 * len(addrs))) - 1))
        for a in reversed(addrs):            # low word in the last register
            table[a] = raw & 0xFFFF
            raw >>= 16
