# Lab status

Last updated: 2026-11-21 (five-cell plant).

## Done

**Phase 0: environment and plumbing (verified)**

- [x] Compose stack / devcontainer: Ignition 8.3.10 (Maker Edition since 2026-11-21),
      PostgreSQL 19, simulated controller, workspace shell (uid-mapped,
      asyncua, pymodbus, psql).
- [x] Gateway commissioned from `.env`; `ignition/data` bind-mounted, owned by
      the host user, seeded by `gateway-init` (fresh clone verified).
- [x] REST API token (`scripts/bootstrap_token.py`), `scripts/ign` CLI, OpenAPI spec saved.
- [x] DB connection `mes` (gateway-encrypted password, `scripts/create_db_connection.py`).
- [x] Ignition OPC UA server opened for lab verification (anonymous read,
      exposed tags), `scripts/opc`.
- [x] System documentation: architecture, operations, gateway automation,
      Panorama E2 concept map.
- [x] Published: https://github.com/kluthen/ignition-scada-lab (public test
      project; lab code and docs: no licence, all rights reserved).

**Plant design (docs/)**

- [x] Scenario: Cell 01 pick-and-inspect cell (CV01, QS01, RB01, CV02, RJ01,
      SF01, UT01, IO01), PackML, orders, traceability.
- [x] OPC UA registry: 193 OPC UA nodes + 36 Modbus points, CSV as single source of truth.
- [x] Fault catalogue (14 faults, phase 2) and MES customer requirements (65 requirements).
- [x] Open design questions decided (docs/README.md).

**Phase 1: simulator and Ignition connectivity (verified)**

- [x] Controller `plc/`: OPC UA address space generated from the CSV,
      Modbus map IO01, `programs/cell.py` implementing scenario.md (phase-1 rows).
- [x] `scripts/cell_smoke_test.py` passes: Reset → Idle, Start refused
      without an order (CmdResult 3), 10-part order Complete in 38 s, 10
      traceability records acknowledged.
- [x] Further checks against scenario.md (ad hoc, 2026-11-21):

      | Check | Result |
      |---|---|
      | PartType 2 rate | 23.23 parts/min (spec 23.24) |
      | Robot cycle | 2.4 s |
      | Rejects | 1 in 25, alternating undersize/oversize at nominal ± 1.6 × tolerance |
      | Hold / Unhold, Abort / Clear, unit modes, invalid command | as specified |
      | Order load during Execute | refused (2) |
      | Starvation | Suspending (10), auto-resume |
      | Reject bin full | Held (20), Unhold refused until BinEmptied |
      | Energy | power 2.16 kW in Execute, 32-bit energy counter high word first |
- [x] Ignition: OPC connection `C01` (anonymous, None), Modbus device `IO01`
      (one-based), `scripts/apply_gateway_config.py`.
- [x] Tags generated from the CSV (`scripts/generate_tags.py`): 164 in
      `[default]ANN/FIN/C01`, 23 in `[sim]Sim`, tag groups Fast / Default /
      Modbus. All 187 read Good. Writes through Ignition tags reach the
      controller; read-only tags refuse writes.

**Phase 2: five cells, UDTs, MES first slice, HMI, history (verified 2026-11-21)**

- [x] Plant layout: five PIC-200 cells C01..C05 in bays 1..5
      (docs/plant-layout.md), instance table docs/cells.csv (identity,
      upstream rate, reject rate, bin chute, qualified part types).
- [x] Controllers: services `plc-c01`..`plc-c05` from one image; `CELL_ID`
      renames the cell's nodes (`C03.*`), applies identification and
      simulation start values; part serials unique across cells (k × 10⁸).
      Smoke test passes on C02, C03 and C05 (`cell_smoke_test.py C0n`).
- [x] Ignition: OPC connections C01..C05 and Modbus devices C01_IO01..C05_IO01
      from templates; UDT `PIC200_Cell` (parameters CellId, OpcServer,
      IoDevice) with 5 instances, UDT `PIC200_Sim` with 5 instances. The
      single-cell device `IO01` and the atomic C01 tags are retired.
- [x] SQL Historian `Historian` on DB connection `historian` (schema
      `historian`), 22 members per cell; storing (96 tags registered after
      30 min, the rest register on their first change).
- [x] MES first slice (docs/system/mes.md): schema `mes`, traceability with
      ack after commit, PackML state log with PLC timestamps, order status
      following the cell, orders replaced on a cell closed short. MES good and
      reject counts equal the PLC counts on all 19 orders completed in the
      first 35 min.
- [x] Lab autopilot: planner and operator stand-in, per-cell `MES/AutoRun`.
- [x] Perspective project `plant` (docs/system/hmi.md): area overview,
      cell page with mimic and PackML commands, instructor page. Checked by
      screenshots (Playwright).
- [x] Behaviour without a trial licence measured (operations.md): OPC UA
      and scripts keep running; Modbus, historian, Perspective stop.
- [x] Moved to Maker Edition (2026-11-21): licence activated, gateway
      re-commissioned from the versioned config, all five cells producing,
      Modbus, historian and HMI running. No part record lost across the
      switch (controller buffers, sequences without gaps).

## Next (recommended order)

1. **Trends and OEE**: Power Chart on the historised members; OEE per cell
   from `mes.cell_state` and `mes.part_result` (availability, performance
   from ideal cycle time, quality), first without the shift calendar.
2. **Alarms** on `Alarms/*`, `RJ01`, `SF01` in the UDT (fault-catalogue.md
   priorities), alarm journal in schema `alarms`, alarm table on the HMI.
3. **MES operator screens**: order list, release, dispatch by hand, close
   short (MES-ORD-03/04/08, DSP-01/02), product check after load (DSP-03).
4. **Phase 2 faults**: fault injection, one fault at a time
   (fault-catalogue.md), driven from the instructor page.
5. Conveyor UDT: not possible cleanly with the current Modbus map, because
   CV01 and CV02 signals are interleaved (C1/C2, DI1-4/DI5-8...). A real
   project would map I/O per equipment block so that one UDT with a base
   address fits; a learning point to keep.

## Open decisions

- MES shift calendar (docs/README.md decision 7) is to be settled with the OEE work.
