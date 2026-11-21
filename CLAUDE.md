# Ignition lab: instructions for Claude Code

Research lab for learning Ignition 8.3 (see README.md). Not an ATD project: no
intent or data registers. The user is an automation engineer coming from Codra
Panorama E2. Relate Ignition concepts to Panorama when it helps
(docs/system/panorama-e2-to-ignition.md).

## Keep the documentation whole

Every change to the stack, the gateway config, the PLC simulator or the plant
model updates the matching document in the same task:
`docs/system/*.md` for the system, `docs/*.md` for the plant and MES, and
`docs/system/status.md` for progress and open decisions. Documentation of the
system as a whole is an explicit requirement of the user.

## Stack

- `compose.yaml` services: `gateway` (Ignition 8.3.10), `db` (PostgreSQL 19),
  `plc-c01`..`plc-c06` (one Python cell controller per cell), `gateway-init`
  (seeds `ignition/data`), `exporter` (daily production export to
  `exports/daily/`, git-ignored), `workspace` (devcontainer, profile `dev`). Host ports
  are on 127.0.0.1: 8088, 62541, 5432, 4841-4846 (OPC UA), 5021-5026 (Modbus).
- The plant is six identical cells (docs/plant-layout.md). `docs/cells.csv` is
  the single source of truth for the instances, `docs/opcua-registry.csv` for
  the signals of one cell (the type, written for C01).
- **Training week (docs/training/week-48.md): the user makes the Ignition
  changes, Claude prepares the simulator and reviews.** Cell C06 and the andon
  station AN01 exist in the controllers only. Do not create them in Ignition, and
  do not run `scripts/db_apply.py`, `apply_gateway_config.py` or
  `generate_tags.py` before the user has finished day 3 (they would commission
  C06 from cells.csv). The AN01 rows have an empty `ignition_tag_path` on
  purpose, so the generator skips them.
- Ignition project `plant`: Perspective HMI (docs/system/hmi.md), named queries,
  and the script library `mes.cell` / `labsim.autopilot` (docs/system/mes.md),
  triggered by tag event scripts in the UDT `PIC200_Cell`. Views are now
  Designer-owned: edit `view.json` by hand only for small fixes.
- KPIs (OEE, downtime, rejects, hourly production) are SQL functions in schema
  `mes` (`db/init/20-kpi.sql`, docs/system/kpi.md). The KPI page and the daily
  export both read them: change a definition there, never in a view or in the
  exporter alone.
- The lab autopilot drives every cell whose `[default]ANN/FIN/<cell>/MES/AutoRun`
  is true. Set it false before driving a cell yourself or running the smoke test.
- The gateway runs Maker Edition (since 2026-11-21; `IGNITION_EDITION=maker`,
  licence key and activation token in `.env`): no time limit, 10,000 tags,
  10 Perspective sessions, no Vision, personal and non-commercial use only.
  Nothing for a customer goes on this gateway. If it ever runs the standard
  trial again, never script trial resets.
- Secrets and versions live in `.env` (git-ignored). Never print passwords or
  the API token in docs or commit messages.

## Driving the gateway

- Use `scripts/ign` (REST API, token from `.env`). Look routes up with
  `scripts/ign routes REGEX` and body schemas with `scripts/ign schema ROUTE --depth N`.
  Don't guess field names.
- Prefer the REST API (validated, applied live) to editing files under
  `ignition/data/config/resources/`. If you do edit files, run
  `scripts/ign scan config` (or `projects`). For API tokens and security levels,
  restart the gateway.
- Never touch `ignition/data/config/resources/.resources/` (gateway cache).
- Keep reproducible request bodies in `gateway-config/*.json`.
- Known pitfalls are listed in docs/system/gateway-automation.md (e.g. Modbus
  device bodies need every settings group).

## Ignition specifics

- Project scripts run on **Jython 2.7**: Python 2 syntax (`print x` works, no
  f-strings, no type hints), Java classes importable, `system.*` API.
- Perspective views are `view.json` under `ignition/data/projects/<project>/com.inductiveautomation.perspective/views/…`.
- Tags: `[provider]Folder/Tag`. Device items in Ignition's OPC UA server are
  `ns=1;s=[device]ADDR`, exposed tags `ns=2;s=[provider]path`.
- Verify values through the OPC UA server with `scripts/opc read|browse|watch`
  (runs asyncua in the workspace container). The REST API has no tag-value route.

## Simulated cell controller (`plc/`)

- One process: an asyncua OPC UA server on :4840 (address space generated from
  `docs/opcua-registry.csv`) plus a stdlib Modbus TCP server on :502 (device
  IO01), with `programs/cell.py` scanned every 100 ms. Layout is in
  docs/system/architecture.md.
- `docs/opcua-registry.csv` is the **single source of truth**: the program
  addresses signals by name (`tags["C01.Status.StateCurrent"]`), so unknown
  names raise. A new signal goes into the CSV first, then the code, then
  `scripts/generate_tags.py`. Keep scenario.md, opcua-registry.md and
  fault-catalogue.md consistent with the CSV. The tables in opcua-registry.md
  are maintained by hand.
- Behaviour is specified in docs/scenario.md, with section numbers cited in
  code comments. Phase 2 (faults) is reserved in docs/fault-catalogue.md.
- After editing: `docker compose restart plc-c01 plc-c02 plc-c03 plc-c04 plc-c05 plc-c06`,
  switch off one cell's autopilot (`MES/AutoRun`), then
  `docker compose exec workspace python scripts/cell_smoke_test.py C0n`. It must PASS.
  Switch the autopilot back on.

## Git

Commit only when the user asks. `.gitignore` keeps only `ignition/data/config/resources/core`
and `ignition/data/projects` from the gateway data dir.
