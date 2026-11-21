"""Cell instance: which of the identical PIC-200 cells this controller runs (docs/cells.csv).

The registry (docs/opcua-registry.csv) is the type definition of one PIC-200
cell, written for the template instance C01. For another cell:
- the cell's own nodes (signal names "C01" and "C01.*") get the cell id in
  their NodeId and BrowsePath: C03 serves "nsu=urn:ignition-lab:cell;s=C03.Status.StateCurrent";
- equipment inside the cell (CV01, QS01, RB01, ...) and Sim.* keep their names,
  which are local to the cell (scenario.md 2.1);
- identification and simulation defaults come from the cell's row of cells.csv.
The program keeps addressing signals by their template names (tags["C01.Status.StateCurrent"]).
"""

from __future__ import annotations

import csv
import dataclasses
import os

from registry import Signal

TEMPLATE_CELL = "C01"
DEFAULT_PATH = os.environ.get("CELLS_CSV", "/registry/cells.csv")


def load(cell: str, path: str = DEFAULT_PATH) -> dict[str, str]:
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["cell"] == cell:
                return row
    raise KeyError(f"cell {cell!r} not found in {path}")


def initial_values(row: dict[str, str]) -> dict[str, str]:
    """Registry signal name -> initial value (CSV text form) for this instance."""
    cell, serial = row["cell"], row["serial_number"]
    return {
        "C01.Identification.SerialNumber": serial,
        "C01.Identification.ProductInstanceUri": f"urn:ignition-lab:machine:{serial}",
        "C01.Identification.YearOfConstruction": row["year_of_construction"],
        "C01.Identification.MonthOfConstruction": row["month_of_construction"],
        "C01.Identification.AssetId": f"ANN-FIN-{cell}",
        "C01.Identification.ComponentName": f"Cell {cell[1:]} - housing inspection and sorting",
        "C01.Identification.Location": f"ANN/FIN/{row['bay']}",
        "RB01.Identification.SerialNumber": row["robot_serial"],
        "QS01.Identification.SerialNumber": row["camera_serial"],
        "Sim.Process.FeedInterval": row["feed_interval"],
        "Sim.Process.RejectEveryN": row["reject_every_n"],
        "Sim.Process.AutoEmptyRejectBin": row["auto_empty_reject_bin"],
    }


def apply(signals: dict[str, Signal], row: dict[str, str]) -> dict[str, Signal]:
    cell = row["cell"]
    values = initial_values(row)
    out: dict[str, Signal] = {}
    for name, s in signals.items():
        changes: dict[str, str] = {}
        if s.protocol == "opcua" and (name == TEMPLATE_CELL or name.startswith(TEMPLATE_CELL + ".")):
            changes["node_name"] = cell + name[len(TEMPLATE_CELL):]
            changes["browse_path"] = s.browse_path.replace(f"/Machines/{TEMPLATE_CELL}", f"/Machines/{cell}", 1)
        if name in values:
            changes["initial_raw"] = values[name]
        out[name] = dataclasses.replace(s, **changes) if changes else s
    return out


def number(cell: str) -> int:
    """C03 -> 3 (used to keep part serials unique across cells, scenario.md 4.1)."""
    return int(cell[1:])
