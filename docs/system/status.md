# Lab status

Last updated: 2026-11-21.

## Done

**Phase 0: environment and plumbing (verified)**

- [x] Compose stack / devcontainer: Ignition 8.3.10 (standard, trial),
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

## Next (recommended order)

1. **UDTs**: turn CV01/CV02 (identical conveyors) and the cell's PackML block
   into UDTs, the key Ignition reuse concept (Panorama E2: classes and instances).
2. **First Perspective project**: a cell overview (state, order, counters,
   conveyors with parts, robot step), command buttons with CmdResult
   feedback, and an instructor view on `[sim]`.
3. **Alarms** on `C01/Alarms/*`, `RJ01`, `SF01` (fault-catalogue.md priorities),
   alarm journal in `mes`.
4. **Tag history** to PostgreSQL (SQL Historian) for counters, speeds,
   energy; trends.
5. **MES MVP** (docs/mes-requirements.md): order table and dispatch, the
   traceability transaction group with the DataReady/AckSequence handshake,
   downtime with StopReason, OEE per shift.
6. **Phase 2**: fault injection, one fault at a time (fault-catalogue.md).

## Open decisions

- Licence path: standard edition in trial mode (2 h resets). Maker Edition is
  possible for purely personal tests; switching requires re-commissioning
  (docs/system/operations.md).
- MES shift calendar (docs/README.md decision 7) is to be settled with the MES work.
