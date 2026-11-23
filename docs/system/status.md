# Lab status

Last updated: 2026-11-23 (PLC training week 50 prepared: research, LT01 station program, Windows PLC station).

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

**Phase 3: KPIs, graphs, daily export (verified 2026-11-21, docs/system/kpi.md)**

- [x] KPI functions in schema `mes` (`db/init/20-kpi.sql`): OEE with A / P / Q
      per cell and area, hourly OEE trend, downtime per StopReason category
      (URS reason table), rejects by defect, production per product, hourly
      counts, orders per period; production day from `mes.site` (calendar
      day, Europe/Paris, DST-safe). Checked: downtime per cell adds up to
      planned minus run time.
- [x] KPI page `/kpi`: period and cell selectors, tiles, OEE per hour,
      production per hour, downtime Pareto, rejects by defect, two tables
      (named queries `Kpi/*`). Cell page: 30-min tag-history trend (power,
      speed, measured bore), today's OEE / A / P / Q and hourly production.
      Checked by screenshots.
- [x] Daily export service `exporter`: PDF report, XLSX, 7 CSVs (including
      part records), `manifest.json` with SHA-256 per file, atomic folder in
      `exports/daily/<date>/`, 10 min after the day ends, catch-up of missed
      days. Scheduler checked with a temporary 15:00 day start (one complete
      day exported unattended); partial export of 2026-11-21 checked by eye.
      The first real complete day is 2026-11-21, due at 2026-11-22 00:10.

**Training week 48 prepared (2026-11-21, [../training/week-48.md](../training/week-48.md))**

- [x] Cell C06: row in docs/cells.csv, service `plc-c06` (ports 4846 / 5026)
      running. Not in Ignition: commissioned by hand on day 3.
- [x] Andon station AN01 in every controller (scenario.md 4.10): stack
      light, buzzer, operator calls, acknowledge; `Sim.Andon.*` for the
      simulated operator (calls, auto-clear, random calls). 17 new nodes,
      `ignition_tag_path` empty so the generator skips them; bound by hand on
      days 4 and 5.
- [x] Smoke test extended with the andon; PASS on C06 and C02. Random calls
      and the auto-clear checked on C06.

**PLC training week 50 prepared (2026-11-23, [../training/week-50.md](../training/week-50.md))**

- [x] Research with sources ([../training/plc-options.md](../training/plc-options.md)):
      Siemens TIA Portal V21 + PLCSIM Advanced V8.0 trials (21 days, one-time),
      Schneider Machine Expert – Basic V1.4 (free), Control Expert (30-day
      trial), Machine Expert (42-day trial, no network in simulation), CODESYS
      (free IDE, 2-hour demo runtime), OpenPLC v4, Windows on Linux, Ignition
      drivers on Maker (legacy Siemens driver and OPC UA; no symbolic driver).
- [x] Leak test station LT01 specified ([../lt01-leak-test.md](../lt01-leak-test.md)) and
      programmed as TIA external sources (`plc-training/siemens/lt01/`):
      UDTs, FB sequence, FB plant model, DBs (HMI DB non-optimized, DB10),
      I/O FCs, OB1; tag table as xlsx. Logic checked with a Python mirror
      (reference values in the spec, section 10). **Not compiled in TIA yet**
      (no TIA on Linux): first compile on day 2.
- [x] PLC engineering station ([plc-engineering.md](plc-engineering.md)): the
      Windows 11 Pro PC on the LAN (16 GB) as main station, `C:\PLC-Training`
      synced by `scripts/plc-pc`; gateway network → PC port proxy → listener
      tested over LAN and Tailscale with `plcsim-portproxy.ps1` (firewall
      limited to the lab host), then removed. A Windows VM on the lab host
      (dockur/windows) was tried and removed completely (6 GB max, below
      Siemens' minimum).
- [ ] Your part before Monday 2026-12-07: Siemens ID, TIA Portal V21 trial and
      PLCSIM Advanced V8.0 trial downloaded and installed on the PC; Machine
      Expert – Basic by Thursday.

## Next (recommended order)

0. **PLC training week 2026-12-07..12-11** (week-50.md): the user programs,
   Claude reviews the exported sources (`scripts/plc-pc pull`), opens the port
   proxy on day 4 and checks the OPC UA path, records the TIA compile fixes
   back into `plc-training/siemens/lt01/`.
0. **Training week 2026-11-23..27** (the user makes the Ignition changes):
   day 1 UI changes, day 2 Orders page, day 3 C06 commissioning, days 4-5
   AN01 tags and screens. After it: fill `ignition_tag_path` for AN01,
   reconcile the hand-made C06 config with the scripts, update hmi.md,
   plant-layout.md, architecture.md.
1. **Alarms** on `Alarms/*`, `RJ01`, `SF01` in the UDT (fault-catalogue.md
   priorities), alarm journal in schema `alarms`, alarm table on the HMI;
   alarm count in the daily report.
2. **Shift calendar** (decision 7): OEE per shift, shift report 10 min after
   each shift end (MES-RPT-01/02), maintenance mode out of planned time.
3. **MES operator screens**: order list, release, dispatch by hand, close
   short (MES-ORD-03/04/08, DSP-01/02), product check after load (DSP-03),
   downtime classification (MES-DT-04).
4. **Phase 2 faults**: fault injection, one fault at a time
   (fault-catalogue.md), driven from the instructor page. Fault stops then
   show in the downtime Pareto.
5. Export shipping channel (e-mail or SFTP) once a receiver is defined;
   Designer exercise: the same daily report with the Reporting module.
6. Conveyor UDT: not possible cleanly with the current Modbus map, because
   CV01 and CV02 signals are interleaved (C1/C2, DI1-4/DI5-8...). A real
   project would map I/O per equipment block so that one UDT with a base
   address fits; a learning point to keep.

## Open decisions

- MES shift calendar (docs/README.md decision 7). Until then the production
  day is the calendar day (`mes.site.day_start` 00:00).
- Daily export delivery: a finished folder in `exports/daily/`; e-mail or SFTP
  needs a target from the user.
