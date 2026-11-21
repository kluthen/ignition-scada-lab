# Lab architecture

Research lab for learning Inductive Automation Ignition 8.3 on a small simulated
plant: Cell 01, a pick-and-inspect robot cell (see [../scenario.md](../scenario.md)).
Everything runs in Docker on one host, orchestrated by `compose.yaml`, which is
also the VS Code devcontainer.

## Components

```
                              host (127.0.0.1 only)
  browser / Designer ─► :8088   OPC UA client ─► :62541   psql ─► :5432   UaExpert ─► :4840   Modbus tool ─► :5020
                          │                        │                │                 │                     │
 ┌────────────────────────┼────────────────────────┼────────────────┼─────────────────┼─────────────────────┼───┐
 │ docker network ignition-lab_default             │                │                 │                     │   │
 │                        ▼                        ▼                ▼                 ▼                     ▼   │
 │  ┌──────────────────────────────────────────────────────┐  ┌────────────┐  ┌─────────────────────────────────┐│
 │  │ gateway (Ignition 8.3.10)                             │  │ db         │  │ plc  (Cell 01 controller, sim)  ││
 │  │  web UI / Perspective / Designer launcher  :8088      │  │ PostgreSQL │  │  OPC UA server :4840 (asyncua)  ││
 │  │  OPC UA server :62541 (devices + exposed tags)        │  │ 19, db mes │  │   ns cell / robot / sim         ││
 │  │  OPC connection "C01"  ─── OPC UA client ──────────────────────────────►  │  Modbus TCP :502 (device IO01)  ││
 │  │  Modbus device "IO01"  ─── Modbus TCP ─────────────────────────────────►  │  scan 100 ms: programs/cell.py  ││
 │  │  DB connection "mes"   ─── JDBC ─────────────────────►│            │  │  address space from registry CSV││
 │  │  tag providers [default] (plant), [sim] (instructor)  │  └────────────┘  └─────────────────────────────────┘│
 │  │  data dir bind-mounted from ./ignition/data           │                                                    │
 │  └──────────────────────────────────────────────────────┘   workspace: devcontainer shell (profile "dev")      │
 │  gateway-init: one-shot, seeds ./ignition/data from the image                                                  │
 └────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Service | Image | Role | Ports (host → container) |
|---|---|---|---|
| `gateway-init` | ignition:8.3.10 | Seeds `./ignition/data` from the image until the gateway is initialised, never overwriting existing (versioned) files; chowns to your uid. Exits. | none |
| `gateway` | ignition:8.3.10 | Ignition Gateway, standard edition in trial mode | `8088→8088` HTTP, `62541→62541` OPC UA |
| `db` | postgres:19 | Database `mes` (schemas `mes`, `historian`, `alarms`) | `5432→5432` |
| `plc` | built from `plc/Dockerfile` (python 3.13 + asyncua 2.1.0) | Simulated cell controller: `plc/main.py` runs `programs/cell.py` every 100 ms and serves the same process image over OPC UA and Modbus TCP | `4840→4840` OPC UA, `5020→502` Modbus |
| `workspace` | built from `.devcontainer/` | Dev shell: Python 3.13, asyncua, pymodbus, psql (profile `dev`) | none |

All published ports bind to 127.0.0.1, so nothing in the lab is reachable from the LAN.

## The simulated controller (`plc/`)

| File | Role |
|---|---|
| `registry.py` | loads `docs/opcua-registry.csv` (mounted read-only at `/registry/`); the CSV is the single source of truth for every signal |
| `tags.py` | one name space for all 229 signals: OPC UA signals in a dict, Modbus signals as scaled views on the I/O image (32-bit = 2 registers, high word first) |
| `opcua_server.py` | builds the address space from the CSV (193 nodes, namespaces `urn:ignition-lab:cell` = 2, `robot` = 3, `sim` = 4, string NodeIds = signal names), and syncs client writes / published values every scan |
| `modbus_server.py`, `io_image.py` | stdlib Modbus TCP server (FC 1–6, 15, 16) over the four tables of device IO01 |
| `programs/cell.py` | the cell logic of scenario.md: PackML state machine (17 states, CntrlCmd/CmdResult handshake), unit modes, upstream feed, CV01/CV02 kinematics, QS01 inspection, RB01 cycle with speed override, reject bin, order download and traceability handshakes, counters, energy |
| `main.py` | scan loop: pull OPC UA writes → `program.scan(dt)` → publish |

Phase 1 is deterministic and fault-free. Phase-2 nodes (alarms other than the
reject bin, `Sim.Panel.*`, `Sim.Faults.*`) exist but have no effect yet.

## Data flow

1. Ignition's **OPC connection `C01`** (OPC UA client, security None, anonymous)
   subscribes to the controller's nodes. Tag item paths use the namespace URI
   form `nsu=urn:ignition-lab:cell;s=C01.Status.StateCurrent`, which Ignition
   8.3.10 accepts, so tags do not depend on namespace indexes.
2. Ignition's **Modbus device `IO01`** polls `plc:502` (unit 1, one-based
   addressing, Ignition default) for the field-level signals: conveyors,
   photo-eyes, reject bin, safety status, air and energy. Its items appear in
   Ignition's own OPC UA server as `ns=1;s=[IO01]DI4`, `[IO01]IRUI12`, etc.
3. **Tags** are generated from the registry by `scripts/generate_tags.py`:
   - 164 tags in `[default]ANN/FIN/C01/...` (ISA-95 path: site / area / cell)
   - 23 simulation tags in `[sim]Sim/...`
   - tag groups: `Fast` 250 ms (cell, robot, camera), `Default` 1 s
     (identification, admin), `Modbus` 500 ms
   - read-only where the registry says R
4. HMI or MES writes go the other way: a write to an Ignition tag, e.g.
   `[default]ANN/FIN/C01/Command/CntrlCmd`, goes to the controller's node. The
   controller answers through `CmdResult` and `CmdCounter`.
5. The DB connection `mes` (PostgreSQL) is ready for the historian, alarm journal
   and MES tables. Nothing writes to it yet.
6. With "exposed tags" on, outside OPC UA clients see the tags as
   `ns=2;s=[default]/ANN/FIN/C01/...` on `:62541`. This is the lab's verification path.

## Versions

| Item | Version | Where pinned |
|---|---|---|
| Ignition | 8.3.10 (b2026100610), standard edition, trial | `.env` `IGNITION_VERSION` |
| PostgreSQL | 19 (19.0 at setup) | `.env` `POSTGRES_VERSION` |
| Python (plc, workspace) | 3.13 | `plc/Dockerfile`, `.devcontainer/Dockerfile` |
| asyncua (plc server, workspace client) | 2.1.0 | `plc/Dockerfile`, `.devcontainer/Dockerfile` |
| pymodbus (workspace only, test client) | 3.16.2 | `.devcontainer/Dockerfile` |

The Modbus server is hand-written, stdlib only. pymodbus 3.16 is half-way
through its v4 API migration and deprecates its server datastore classes.

## Lab-only relaxations (do not copy to a customer system)

| Setting | Lab value | Why | Production practice |
|---|---|---|---|
| Ignition OPC UA server | bind `0.0.0.0`, policies `None` + `Basic256Sha256`, anonymous read | lets scripts read devices and tags without certificates | `SignAndEncrypt` only, no anonymous, trusted client certificates |
| Exposed tag providers | on | read tags from external clients for verification | off unless a consumer needs it |
| Controller OPC UA server and connection `C01` | security None, anonymous, certificate validation off | simple simulator | `SignAndEncrypt`, trusted certificates, user or certificate authentication |
| API token `claude-lab` | gateway read + write (`Authenticated/ApiAutomation`) | lets `scripts/` and Claude Code configure the gateway | scoped tokens, `secureChannelRequired` with HTTPS |
| Gateway | HTTP only | localhost only | HTTPS with a real certificate |
| `opcuauser` / `password` | Ignition's default OPC UA user, unchanged | used by tests to write through Ignition's server | change or disable it |

Anonymous clients of Ignition's OPC UA server can browse and read, but not
write. Write and call are granted to `AuthenticatedUser` only, which is
Ignition's default access control.

## Repository layout

```
compose.yaml              the stack (also the devcontainer's compose file)
.env / .env.example       versions, uid, passwords, API token (.env is git-ignored)
.devcontainer/            devcontainer.json + workspace image
plc/                      simulated cell controller (see above)
db/init/                  SQL run once when the PostgreSQL volume is created
ignition/data/            Ignition data dir (bind mount); config/resources/core and projects are versioned
gateway-config/           reproducible gateway config: OPC connection, Modbus device, OPC UA server,
                          tags/<provider>.json generated from the registry
scripts/                  ign (REST CLI), opc (OPC UA tool), bootstrap and apply scripts,
                          generate_tags.py, cell_smoke_test.py
docs/                     plant design: scenario, OPC UA registry (CSV), fault catalogue, MES requirements
docs/system/              this documentation: architecture, operations, automation, glossary, status
```
