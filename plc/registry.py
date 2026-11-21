"""Load docs/opcua-registry.csv, the single source of truth for every signal."""

from __future__ import annotations

import csv
import datetime as dt
import os
from dataclasses import dataclass

UTC = dt.timezone.utc
NULL_DATETIME = dt.datetime(1601, 1, 1, tzinfo=UTC)   # OPC UA "null" DateTime
DEFAULT_PATH = os.environ.get("REGISTRY_CSV", "/registry/opcua-registry.csv")


@dataclass(frozen=True)
class Signal:
    name: str
    protocol: str            # "opcua" | "modbus"
    namespace_uri: str
    browse_path: str
    node_class: str          # "Object" | "Variable" | "" (modbus)
    type_definition: str     # FolderType | BaseObjectType | BaseDataVariableType | PropertyType
    data_type: str
    access: str              # "R" | "RW"
    writer: str
    initial_raw: str
    modbus_table: str        # coil | discrete_input | holding | input
    modbus_address: str      # "3" or "11-12"
    modbus_scale: float
    phase: int
    description: str

    @property
    def is_variable(self) -> bool:
        return self.protocol == "modbus" or self.node_class == "Variable"

    def initial_value(self, startup: dt.datetime):
        return parse_value(self.data_type, self.initial_raw, startup)


def parse_value(data_type: str, raw: str, startup: dt.datetime):
    if data_type == "Boolean":
        return raw.strip().lower() == "true"
    if data_type == "String":
        return raw
    if data_type == "DateTime":
        if raw == "@startup":
            return startup
        if not raw:
            return NULL_DATETIME
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if data_type == "Double":
        return float(raw) if raw else 0.0
    return int(float(raw)) if raw else 0     # Byte, UInt16, Int32, UInt32


def load(path: str = DEFAULT_PATH) -> dict[str, Signal]:
    signals: dict[str, Signal] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            s = Signal(
                name=row["signal"], protocol=row["protocol"], namespace_uri=row["namespace_uri"],
                browse_path=row["browse_path"], node_class=row["node_class"],
                type_definition=row["type_definition"], data_type=row["data_type"],
                access=row["access"], writer=row["writer"], initial_raw=row["initial_value"],
                modbus_table=row["modbus_table"], modbus_address=row["modbus_address"],
                modbus_scale=float(row["modbus_scale"] or 1), phase=int(row["phase"] or 1),
                description=row["description"])
            if s.name in signals:
                raise ValueError(f"duplicate signal {s.name} in {path}")
            signals[s.name] = s
    return signals
