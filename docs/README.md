# Ignition lab: design documents

Design of the simulated plant (the finishing area of the fictional Brevent Hydraulics: six
identical cells, each described by Cell 01) and of the small MES to be built on Ignition 8.3. The
simulation in `plc/` and the Ignition project are built from these documents.

| Document | Content |
|---|---|
| [scenario.md](scenario.md) | The plant. A pick-and-inspect cell: infeed conveyor, camera (DataMatrix + bore gauge), SCARA robot with vacuum gripper, reject bin, outfeed conveyor. It covers the equipment list and naming convention, the OPC UA / Modbus split, the part types (recipes), the physical model of each item with exact timings and formulas, the PackML state model (states, commands, internal transitions, interlocks), unit modes and the OPC 40001 machinery state mapping, the order download handshake, the traceability handshake, the expected production rates, and the restart rules. Phase 1 is deterministic and fault-free. |
| [plant-layout.md](plant-layout.md) | The finishing area: six PIC-200 cells C01..C06 in bays 1..6 (C06 delivered 2026-11, its Ignition side commissioned in the training week), what differs between them, how one cell type becomes six instances at every layer (controller, OPC UA, Ignition UDT, MES, HMI), and how to add a cell. |
| [cells.csv](cells.csv) | **Single source of truth** for the cell instances: id, bay, controller host and ports, Modbus device name, serial numbers, simulation start values, qualified part types. |
| [opcua-registry.md](opcua-registry.md) | Human-readable registry: server endpoint, the three namespaces, the NodeId convention (`nsu=<uri>;s=<signal>`), the address space tree, the CSV column definitions, all enumerations, the alignment with OPC 40001-1 / 40010-1 / 30050 and where it diverges, and one table per equipment (generated from the CSV). |
| [opcua-registry.csv](opcua-registry.csv) | **Single source of truth** for every signal: 210 OPC UA nodes (46 objects/folders, 164 variables; 122 in `urn:ignition-lab:cell`, 57 in `urn:ignition-lab:robot`, 31 in `urn:ignition-lab:sim`) and 36 Modbus TCP points. It is meant to drive the generation of the OPC UA address space, the Modbus map and later the Ignition tags. Each row has a `phase` column: 1 = behaviour now, 2 = node exists now, behaviour comes with faults. |
| [fault-catalogue.md](fault-catalogue.md) | 14 faults (e-stop, guard door, vacuum loss, pick failure, jam, drive trip, stuck sensor, camera, unreadable DataMatrix, quality drift, low air, robot comms, downstream blocked, SCADA comms loss). Each comes with its injection node in the simulation-only `Sim` namespace, its detection signals, its effect on the state machine and StopReason, the reset procedure, and the Ignition alarm with its priority. |
| [training/week-48.md](training/week-48.md) | Training week 2026-11-23..27 (user at the controls, 2 h a day): Designer UI changes, a new view, commissioning cell C06 by hand, binding the andon station AN01. |
| [mes-requirements.md](mes-requirements.md) | Customer URS for the MES, written by the fictional customer: context, ISA-95 positioning, shift calendar, personas, and 65 numbered requirements (orders, dispatch, counting, OEE, downtime with reason codes, traceability, quality, alarms/events, reports, users/roles, HMI, non-functional), each with MVP/Later priority and acceptance criteria tied to the simulator. It also gives the core-Ignition implementation map, the Sepasoft modules that would normally be used, and an indicative schema. |

## Phase 1 scope (what to implement first in `plc/`)

> Implemented and verified on 2026-11-21. See [system/status.md](system/status.md).

1. **OPC UA server** (`asyncua`) in the `plc` process, endpoint `opc.tcp://0.0.0.0:4840/ignition-lab/`, security None, anonymous.
   - Register the namespaces in the order cell, robot, sim.
   - Build the address space from `opcua-registry.csv` at startup: all rows, phase 1 and 2. Write the Descriptions, and make RW nodes writable.
   - Compose: publish `127.0.0.1:4840:4840`, and provide `asyncua` (the image is `python:3.13-slim` with `./plc` mounted read-only).
2. **Modbus map** of device IO01 per the registry (coils 0-4, discrete inputs 0-13, holding 0-3, input registers 0-13). The existing `modbus_server.py` is kept.
3. **Cell program** `programs/cell.py`, replacing `tank`, implementing scenario.md for phase-1 rows:
   - upstream feed; CV01 and CV02 kinematics and sensors; QS01 deterministic measurement;
   - robot cycle with speed override and step timers that carry overshoot;
   - RJ01 counting, the bin-full Hold, and `RJ01.Command.BinEmptied`;
   - the full PackML state machine with commands, interlocks, CmdResult and CmdCounter, and Production/Maintenance modes with conveyor jog;
   - starvation suspend and auto-resume;
   - order load handshake, purge, order counters and times;
   - traceability FIFO (200) with the DataReady/AckSequence handshake;
   - Admin counters, StopReason, MachineryItemState/OperationMode mapping, heartbeats, energy model;
   - `Sim.Process.*` parameters live.
4. **Phase-2 nodes inert**: alarm bits false except `C01.Alarms.RejectBinNearFull` and `C01.Alarms.RejectBinFull`; `Sim.Panel.*` and `Sim.Faults.*` present and writable but without effect.
5. **Smoke test script** (e.g. `scripts/`), an OPC UA client that:
   - runs Reset; waits for Idle; loads order `TEST-0001` (PartType 1, 10 parts); runs Start;
   - acknowledges traceability records as they come;
   - expects Complete within 60 s, `C01.Order.Active.GoodCount` = 10, and as many acknowledged records as `C01.Admin.ProdProcessedCount`.

   Second check: with no order, Start gives CmdResult 3.

The Ignition work comes after: OPC UA connection, Modbus device, UDTs and tags from the CSV, then
the cell overview screen. The MES MVP (mes-requirements.md) follows; PostgreSQL 19 is already in the stack.

## Decisions on the open questions (2026-11-21)

The user delegated these choices. Recorded here; revisit any of them when the lab grows.

| # | Decision |
|---|---|
| 1 | One OPC UA endpoint for phase 1 (cell + robot namespaces). A second endpoint for the robot is a later exercise in multiple connections. |
| 2 | `Sim` stays on the same endpoint. Ignition keeps it apart with its own tag provider `[sim]`. |
| 3 | No persistence: a `plc` restart resets counters and loses the active order (`StartUpTime` changes). |
| 4 | Traceability buffer full: drop the oldest and count `LostCount`, as designed. Holding the cell instead is a candidate requirement for the MES phase. |
| 5 | No time acceleration in phase 1. |
| 6 | Reject-bin holds stay on by default (`AutoEmptyRejectBin` false). |
| 7 | Shift calendar: decided with the MES work. |
| 8 | **Verified**: Ignition 8.3.10 accepts `nsu=<uri>;s=<id>` item paths. The generated tags use them. |
| 9 | Companion NodeSets and PackML methods: later. |
| 10 | The CSV is mounted read-only into the `plc` container (`/registry/opcua-registry.csv`). No copy, a single source. |
| 11 | HMI in English first. |

## Open questions as originally raised

1. **One OPC UA endpoint or two?** Phase 1 serves cell and robot from one endpoint (two namespaces). A real cell has two servers (PLC and robot controller); a second endpoint on port 4841 would also teach multiple Ignition connections.
2. **Sim isolation:** keep `Sim` on the same endpoint (simple), or serve it on a separate port so the "production" Ignition connection cannot see it?
3. **Persistence:** nothing survives a `plc` restart (counters restart at 0, the active order is lost; part ids stay unique). Is that acceptable, or should a writable state volume keep the order and counters?
4. **Traceability buffer full** (> 200 records, about 8 min without MES): the current design drops the oldest records and keeps producing. A customer with a 10-year traceability obligation might prefer the cell to Hold instead. Which do you want?
5. **Time acceleration:** a ×10 simulation clock would make shift reports and OEE testable in minutes, but would make timestamps unrealistic. Include it?
6. **Reject bin holds** every ~52 min by default (`Sim.Process.AutoEmptyRejectBin` false). Good material for downtime analysis, but it needs an operator. Keep this default?
7. **Lab shift calendar:** the customer's 2 × 8 h Mon-Fri, or 24/7 so that any session falls in a shift?
8. **Ignition item paths:** the registry uses `nsu=<uri>;s=<id>`. Check on 8.3.10 that the OPC UA client accepts it; otherwise fall back to `ns=<index>;s=<id>` (indexes 2/3/4 are guaranteed by the registration order).
9. **Companion-spec fidelity, later:** import the official Machinery/Robotics/PackML NodeSet2 files and type the instances (e.g. MotionDeviceSystemType)? Expose the PackML commands as OPC UA methods as well? Both are good exercises, but they cost more on the server side.
10. **Where the CSV lives for the `plc` container:** `docs/` is not mounted in it. Mount `docs/` read-only, or copy the CSV into `plc/` as part of a build step?
11. **HMI language:** English only for now, French later (as in the URS)?
