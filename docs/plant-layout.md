# Finishing area layout: six PIC-200 cells

Brevent's finishing area (FIN) at the Annecy site runs six identical
pick-and-inspect cells, model PIC-200, side by side in bays 1 to 6. Each cell is
the cell of [scenario.md](scenario.md): same equipment, same controller program,
same signal interface ([opcua-registry.md](opcua-registry.md)). They differ by
identity, upstream rate, gauge condition and the part types they are qualified for.
That gives the MES and the HMI data that differs from cell to cell.

C06 was delivered in 2026-11. Its controller runs (`plc-c06`), but its Ignition
side (connections, tags, MES master data) is commissioned by hand in the
training week ([training/week-48.md](training/week-48.md), day 3). Until then
the gateway, the MES and the HMI know five cells.

```
                     deburring line (upstream), one feed per bay
        ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
        ▼         ▼         ▼         ▼         ▼         ▼         │
   ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
   │  C01   ││  C02   ││  C03   ││  C04   ││  C05   ││  C06   │   FIN area, bays 1..6
   │ BAY1   ││ BAY2   ││ BAY3   ││ BAY4   ││ BAY5   ││ BAY6   │   each: CV01 → QS01/RB01 → CV02, RJ01 bin,
   └───┬────┘└───┬────┘└───┬────┘└───┬────┘└───┬────┘└───┬────┘   AN01 andon station
       ▼         ▼         ▼         ▼         ▼         ▼
   ═════════════════════ packing conveyor (good parts) ═════════════════════
```

## The instance table: [cells.csv](cells.csv)

docs/cells.csv is the single source of truth for the cell instances, as
docs/opcua-registry.csv is for the signals of one cell. One row per cell:

| Column | Used by | Meaning |
|---|---|---|
| `cell` | everything | cell id, `C01`..`C06`: OPC connection name, UDT instance name, `mes.cell` key |
| `bay` | controller, MES | `Identification/Location` = `ANN/FIN/<bay>` |
| `controller_host` | compose, gateway | container / hostname of the cell's controller (`plc-c0n`) |
| `opcua_host_port`, `modbus_host_port` | compose | ports published on 127.0.0.1 (484n, 502n) |
| `io_device` | gateway, UDT | Ignition Modbus device name of the cell's I/O coupler (`C0n_IO01`) |
| `serial_number`, `year_of_construction`, `month_of_construction`, `robot_serial`, `camera_serial` | controller | identification nodes (OPC 40001 / 40010) |
| `feed_interval`, `reject_every_n`, `auto_empty_reject_bin` | controller | start values of `Sim.Process.*` (instructor can change them) |
| `qualified_part_types` | MES | part types the cell may run (`mes.cell.qualified_part_types`) |
| `notes` | MES, docs | the cell's character |

| Cell | Bay | Upstream feed | Rejects | Bin | Part types | Character |
|---|---|---|---|---|---|---|
| C01 | BAY1 | 2.5 s | 1 in 25 | manual | 1, 2 | reference cell |
| C02 | BAY2 | 2.5 s | 1 in 40 | manual | 1, 2 | twin of C01, better gauge |
| C03 | BAY3 | 3.0 s | 1 in 20 | manual | 3 | large housings only, slower upstream |
| C04 | BAY4 | 2.5 s | 1 in 15 | manual | 1, 2, 3 | flexible cell, worn gauge fixture |
| C05 | BAY5 | 2.0 s | 1 in 50 | automatic chute | 1 | robot-limited |
| C06 | BAY6 | 2.5 s | 1 in 30 | manual | 2, 3 | newest (2026-11), medium and large housings |

Expected rates follow scenario.md section 6: feed-limited at 2.5 s (24
parts/min), robot-limited with HSG-A20 at 2.0 s feed (25 parts/min), slower
with HSG-B32/HSG-C45 (robot cycle 2.6 / 2.8 s). Cells with a manual bin hold
when it is full (50 parts) until someone empties it: the lab autopilot does so
after 1 to 4 minutes, which gives availability losses for OEE.

## How one cell type becomes six cells

| Layer | Type (one definition) | Instances |
|---|---|---|
| Controller | `plc/` program + docs/opcua-registry.csv, one Docker image `ignition-lab-plc` | services `plc-c01`..`plc-c06`, `CELL_ID` env selects the row of cells.csv (`plc/instance.py`) |
| OPC UA address space | registry, written for C01 | the cell's own nodes carry its id: `nsu=urn:ignition-lab:cell;s=C03.Status.StateCurrent`. Equipment inside the cell keeps its local name (`RB01`, `CV01`, ...) and `Sim.*` is unchanged; each controller is its own server |
| Part serials | scenario.md 4.1 | serials of cell *k* start at *k* × 10⁸ (C03 → `P3xxxxxxxx`), so part ids stay unique across cells |
| Ignition connections | `gateway-config/opc-connection.template.json`, `device.template.json` | `C01`..`C05`, `C01_IO01`..`C05_IO01` (`scripts/apply_gateway_config.py`) |
| Ignition tags | UDT `[default]_types_/PIC200_Cell` (parameters `CellId`, `OpcServer`, `IoDevice`), UDT `[sim]_types_/PIC200_Sim` (`OpcServer`) | `[default]ANN/FIN/C01`..`C05`, `[sim]C01`..`C05` (`scripts/generate_tags.py`) |
| MES master data | `mes.cell` | one row per cell, loaded from cells.csv (`scripts/db_apply.py`) |
| HMI | Perspective views `Cell/Tile`, `Cell/Detail`, `Sim/CellRow` with a `cell` parameter | one per row of `mes.cell` (flex repeaters) |

The PLC program addresses signals by their registry names (`C01.Status.StateCurrent`)
whatever the instance, as a real PLC program uses its own symbol names; only
the published NodeIds change.

## Adding a cell

1. Add a row to docs/cells.csv (bay, host `plc-c0n`, ports 484n/502n, device `C0n_IO01`, ...).
2. Add a `plc-c0n` service to compose.yaml (copy the last one), and to `runServices` in `.devcontainer/devcontainer.json`.
3. `docker compose up -d plc-c0n`, then `scripts/db_apply.py`, `scripts/apply_gateway_config.py`, `scripts/generate_tags.py`.

The HMI and the MES pick it up from `mes.cell` without any change. C06 went
through steps 1 and 2 in 2026-11. Step 3 is done by hand in the gateway web UI and
the Designer in the training week, as a commissioning exercise. The scripts
are run afterwards: they update what exists, so `git diff` shows where the
hand-made configuration differs from the scripted one.
