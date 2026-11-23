# Lab architecture

Research lab for learning Inductive Automation Ignition 8.3 on a small simulated
plant: the finishing area of Brevent Hydraulics, five identical pick-and-inspect
robot cells C01..C05 ([../plant-layout.md](../plant-layout.md), one cell is
described in [../scenario.md](../scenario.md)). Everything runs in Docker on one
host, orchestrated by `compose.yaml`, which is also the VS Code devcontainer.

## Components

```
                                   host (127.0.0.1 only)
  browser: web UI, Perspective, Designer ─► :8088    OPC UA client ─► :62541    psql ─► :5432
  UaExpert ─► :4841..4846 (cell controllers)          Modbus tool ─► :5021..5026
                     │
 ┌───────────────────┼──────────────────────────────────────────────────────────────────────────────┐
 │ docker network    ▼                                                                               │
 │  ┌────────────────────────────────────────────────────────────┐        ┌─────────────────────────┐ │
 │  │ gateway (Ignition 8.3.10)                                   │        │ plc-c01 .. plc-c06      │ │
 │  │  OPC connections C01..C05 ── OPC UA client ──────────────────────────► OPC UA :4840 (asyncua)  │ │
 │  │  Modbus devices C01_IO01..C05_IO01 ── Modbus TCP ────────────────────► Modbus :502 (IO01)      │ │
 │  │  tags: UDT PIC200_Cell → [default]ANN/FIN/C01..C05                 │  scan 100 ms:            │ │
 │  │        UDT PIC200_Sim  → [sim]C01..C05                             │  programs/cell.py        │ │
 │  │  tag event scripts → project library "plant": mes.cell,     │        │  CELL_ID → docs/cells.csv│ │
 │  │        labsim.autopilot ──────────── JDBC "mes" ──────┐     │        └─────────────────────────┘ │
 │  │  SQL Historian "Historian" ── JDBC "historian" ──────┐│     │        ┌─────────────────────────┐ │
 │  │  Perspective project "plant" (HMI) ── named queries ─┼┼─────────────► db: PostgreSQL 19, db mes │ │
 │  │  OPC UA server :62541 (devices + exposed tags)       └┴─────────────►  schemas mes, historian, │ │
 │  │  data dir bind-mounted from ./ignition/data                 │        │  alarms                  │ │
 │  └────────────────────────────────────────────────────────────┘        └─────────────────────────┘ │
 │  gateway-init: one-shot, seeds ./ignition/data      workspace: devcontainer shell (profile "dev")  │
 │  exporter: daily production export, reads the mes.* KPI functions ─► ./exports/daily/<date>/       │
 └──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Service | Image | Role | Ports (host → container) |
|---|---|---|---|
| `gateway-init` | ignition:8.3.10 | Seeds `./ignition/data` from the image until the gateway is initialised, never overwriting existing (versioned) files; chowns to your uid. Exits. | none |
| `gateway` | ignition:8.3.10 | Ignition Gateway, Maker Edition | `8088→8088` HTTP, `62541→62541` OPC UA |
| `db` | postgres:19 | Database `mes` (schemas `mes`, `historian`, `alarms`) | `5432→5432` |
| `plc-c01` .. `plc-c06` | built from `plc/Dockerfile` (python 3.13 + asyncua 2.1.0), image `ignition-lab-plc` | One simulated cell controller each: `plc/main.py` runs `programs/cell.py` every 100 ms and serves the same process image over OPC UA and Modbus TCP. `CELL_ID` selects the row of docs/cells.csv | `484n→4840` OPC UA, `502n→502` Modbus |
| `exporter` | built from `exporter/Dockerfile` (python 3.13 + psycopg, openpyxl, reportlab), image `ignition-lab-exporter` | Daily production export: one folder per production day (PDF, XLSX, CSVs, manifest) in `./exports/daily/`, runs as your uid ([kpi.md](kpi.md)) | none |
| `workspace` | built from `.devcontainer/` | Dev shell: Python 3.13, asyncua, pymodbus, psql (profile `dev`) | none |

Outside Docker, a **Windows PC on the LAN** is the PLC engineering station
(TIA Portal, PLCSIM Advanced, Machine Expert – Basic). The gateway reaches
the PLC simulated there over the LAN or Tailscale through a Windows port
proxy ([plc-engineering.md](plc-engineering.md)); its address is
`PLC_PC_HOST` in `.env`. The leak test station LT01 controlled by that PLC is
specified in [../lt01-leak-test.md](../lt01-leak-test.md).

All published ports bind to 127.0.0.1, so nothing in the lab is reachable from the LAN.

## The simulated controller (`plc/`)

| File | Role |
|---|---|
| `registry.py` | loads `docs/opcua-registry.csv` (mounted read-only at `/registry/`); the CSV is the single source of truth for the signals of one cell |
| `instance.py` | applies the cell's row of `docs/cells.csv`: renames the cell's own nodes (`C01.*` → `C03.*` in NodeId and BrowsePath), sets identification and `Sim.Process.*` start values |
| `tags.py` | one name space for all 246 signals: OPC UA signals in a dict, Modbus signals as scaled views on the I/O image (32-bit = 2 registers, high word first) |
| `opcua_server.py` | builds the address space from the registry (210 nodes, namespaces `urn:ignition-lab:cell` = 2, `robot` = 3, `sim` = 4, string NodeIds), and syncs client writes / published values every scan. Application URI `urn:ignition-lab:plc-sim:c03` |
| `modbus_server.py`, `io_image.py` | stdlib Modbus TCP server (FC 1–6, 15, 16) over the four tables of the cell's I/O coupler IO01 |
| `programs/cell.py` | the cell logic of scenario.md: PackML state machine (17 states, CntrlCmd/CmdResult handshake), unit modes, upstream feed, CV01/CV02 kinematics, QS01 inspection, RB01 cycle with speed override, reject bin, order download and traceability handshakes, counters, energy. Addresses signals by their registry (template) names |
| `main.py` | scan loop: pull OPC UA writes → `program.scan(dt)` → publish |

Phase 1 is deterministic and fault-free. Phase-2 nodes (alarms other than the
reject bin, `Sim.Panel.*`, `Sim.Faults.*`) exist but have no effect yet.

`plc-c06` (cell C06, delivered 2026-11) and the andon station `AN01` of every
cell (stack light and operator calls, scenario.md 4.10) run in the controllers
but are not in Ignition yet: they are commissioned and bound by hand in the
training week ([../training/week-48.md](../training/week-48.md)). The gateway,
the MES and the HMI below still describe five cells.

## Data flow

1. Ignition's **OPC connections `C01`..`C05`** (OPC UA client, security None,
   anonymous) subscribe to the controllers. UDT members use item paths
   `nsu=urn:ignition-lab:cell;s={CellId}.Status.StateCurrent` (namespace URI
   form, which Ignition 8.3.10 accepts) on server `{OpcServer}`.
2. Ignition's **Modbus devices `C0n_IO01`** poll `plc-c0n:502` (unit 1,
   one-based addressing, Ignition default) for the field-level signals:
   conveyors, photo-eyes, reject bin, safety status, air and energy. UDT members
   read them through Ignition's own OPC UA server as `ns=1;s=[{IoDevice}]DI4`.
3. **Tags**, generated by `scripts/generate_tags.py` from the registry and
   docs/cells.csv:
   - UDT `PIC200_Cell` (166 OPC members + MES members) and 5 instances
     `[default]ANN/FIN/C01`..`C05` (ISA-95 path: site / area / cell)
   - UDT `PIC200_Sim` (23 members) and 5 instances `[sim]C01`..`C05`
   - tag groups: `Fast` 250 ms (cell, robot, camera), `Default` 1 s
     (identification, admin, MES tick), `Modbus` 500 ms
   - read-only where the registry says R; 22 members per cell historised
4. **MES and autopilot** ([mes.md](mes.md)): tag event scripts of the UDT
   (`MES/Tick` every second, `Traceability/DataReady`, `Status/StateCurrent`)
   call the project library of `plant` (the gateway scripting project). They
   store part records, the state log and order status in schema `mes`, and the
   lab autopilot dispatches orders and operates the cells.
5. **Tag history**: SQL Historian provider `Historian` on DB connection
   `historian` (`currentSchema=historian`): tables `sqlth_*` and monthly
   partitions `sqlt_data_1_<yyyy>_<mm>`.
6. **HMI** ([hmi.md](hmi.md)): Perspective project `plant`, views parameterised
   by cell, tag bindings to the UDT instances, named queries on `mes`, tag
   history on the cell page.
7. **KPIs and daily export** ([kpi.md](kpi.md)): SQL functions in schema `mes`
   (`oee`, `downtime`, `rejects`, `production`, `hourly`, `orders`) compute the
   KPIs from the state log and the part records. The KPI page reads them
   through named queries; the `exporter` service reads them over SQL and writes
   each finished day to `./exports/daily/<date>/`.
8. With "exposed tags" on, outside OPC UA clients see the tags as
   `ns=2;s=[default]/ANN/FIN/C03/...` on `:62541`.

## Versions

| Item | Version | Where pinned |
|---|---|---|
| Ignition | 8.3.10 (b2026100610), Maker Edition (activated licence, 10,000 tags) since 2026-11-21 | `.env` `IGNITION_VERSION`, `IGNITION_EDITION` |
| PostgreSQL | 19 (19.0 at setup) | `.env` `POSTGRES_VERSION` |
| Python (plc, workspace) | 3.13 | `plc/Dockerfile`, `.devcontainer/Dockerfile` |
| asyncua (plc server, workspace client) | 2.1.0 | `plc/Dockerfile`, `.devcontainer/Dockerfile` |
| pymodbus (workspace only, test client) | 3.16.2 | `.devcontainer/Dockerfile` |
| psycopg / openpyxl / reportlab (exporter) | 3.3.9 / 3.1.5 / 5.1.0 | `exporter/Dockerfile` |

The Modbus server is hand-written, stdlib only. pymodbus 3.16 is half-way
through its v4 API migration and deprecates its server datastore classes.

## Lab-only relaxations (do not copy to a customer system)

| Setting | Lab value | Why | Production practice |
|---|---|---|---|
| Ignition OPC UA server | bind `0.0.0.0`, policies `None` + `Basic256Sha256`, anonymous read | lets scripts read devices and tags without certificates | `SignAndEncrypt` only, no anonymous, trusted client certificates |
| Exposed tag providers | on | read tags from external clients for verification | off unless a consumer needs it |
| Controller OPC UA servers and connections `C0n` | security None, anonymous, certificate validation off | simple simulator | `SignAndEncrypt`, trusted certificates, user or certificate authentication |
| API token `claude-lab` | gateway read + write (`Authenticated/ApiAutomation`) | lets `scripts/` and Claude Code configure the gateway | scoped tokens, `secureChannelRequired` with HTTPS |
| Gateway | HTTP only | localhost only | HTTPS with a real certificate |
| `opcuauser` / `password` | Ignition's default OPC UA user, unchanged | used by tests to write through Ignition's server | change or disable it |
| Perspective project `plant` | no login, any session may write commands | screens for one person on localhost | identity provider, roles per action (operator, shift lead), audit |
| Lab autopilot | operates the cells from gateway scripts | data generation | does not exist on a real plant |
| Exporter database role | the database owner (`POSTGRES_USER`) | one role for everything | a read-only role for the export |

Anonymous clients of Ignition's OPC UA server can browse and read, but not
write. Write and call are granted to `AuthenticatedUser` only, which is
Ignition's default access control.

## Repository layout

```
compose.yaml              the stack (also the devcontainer's compose file)
.env / .env.example       versions, uid, passwords, API token (.env is git-ignored)
.devcontainer/            devcontainer.json + workspace image
plc/                      simulated cell controller (see above)
plc-training/             PLC training material: LT01 SCL sources + tag table (siemens/lt01), your exports
                          (*/work), Windows port proxy script; synced with the PLC PC by scripts/plc-pc
exporter/                 daily production export (daily_export.py, Dockerfile)
exports/daily/            export output, one folder per production day (git-ignored)
db/init/                  SQL: schemas (00), MES tables (10), KPI functions (20); re-runnable with scripts/db_apply.py
ignition/data/            Ignition data dir (bind mount); config/resources/core and projects are versioned
  projects/plant/         Perspective views (overview, cell, KPI, instructor), named queries, script library (mes, labsim)
gateway-config/           reproducible gateway config: OPC connection and Modbus device templates (per cell),
                          historian provider, system-properties patch, OPC UA server,
                          tags/<provider>.json generated from the registry and cells.csv
scripts/                  ign (REST CLI), opc (OPC UA tool), bootstrap, apply, db_apply,
                          generate_tags.py, cell_smoke_test.py, plc-pc (PLC PC sync / PowerShell)
docs/                     plant design: scenario, plant layout + cells.csv, OPC UA registry (CSV),
                          fault catalogue, MES requirements, LT01 leak test station
docs/training/            training weeks 48 (Ignition) and 49 (PLC), PLC options research
docs/system/              this documentation: architecture, operations, automation, MES, HMI,
                          KPIs and export, Panorama concept map, status
```
