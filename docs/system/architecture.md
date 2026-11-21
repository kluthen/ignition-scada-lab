# Lab architecture

Research lab for learning Inductive Automation Ignition 8.3 on a small simulated
plant. Everything runs in Docker on one host, orchestrated by `compose.yaml`
(also used as a VS Code devcontainer).

## Components

```
                         host (127.0.0.1 only)
   browser / Designer ──► :8088      OPC UA client ──► :62541     psql ──► :5432     Modbus tool ──► :5020
                            │                            │                  │                       │
 ┌──────────────────────────┼────────────────────────────┼──────────────────┼───────────────────────┼─────┐
 │ docker network ignition-lab_default                   │                  │                       │     │
 │                          ▼                            ▼                  ▼                       ▼     │
 │   ┌──────────────────────────────────────────────────────────┐   ┌──────────────┐     ┌──────────────┐ │
 │   │ gateway  (inductiveautomation/ignition:8.3.10)           │   │ db           │     │ plc          │ │
 │   │  • Gateway web UI, Perspective, Designer launcher :8088   │──►│ PostgreSQL 19│     │ python 3.13  │ │
 │   │  • OPC UA server :62541 (devices + exposed tag providers) │   │ db "mes"     │     │ Modbus TCP   │ │
 │   │  • Modbus TCP driver: device "plc_modbus" ───────────────────────────────────────►│ :502         │ │
 │   │  • DB connection "mes" ─────────────────────────────────────►                     │ scan cycle   │ │
 │   │  • data dir bind-mounted from ./ignition/data             │   └──────────────┘     └──────────────┘ │
 │   └──────────────────────────────────────────────────────────┘                                          │
 │   gateway-init (one-shot: seeds ./ignition/data on first start)   workspace (devcontainer shell, "dev")  │
 └──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Service | Image | Role | Ports (host → container) |
|---|---|---|---|
| `gateway-init` | ignition:8.3.10 | Copies the image's default data dir into `./ignition/data` when it is empty, then chowns it to your uid. Exits. | none |
| `gateway` | ignition:8.3.10 | Ignition Gateway, standard edition in trial mode by default | `127.0.0.1:8088→8088` (HTTP), `127.0.0.1:62541→62541` (OPC UA) |
| `db` | postgres:19 | MES / historian / alarm journal database `mes` (schemas `mes`, `historian`, `alarms`) | `127.0.0.1:5432→5432` |
| `plc` | python:3.13-slim | Simulated PLC: `plc/main.py`, a scan cycle running one program from `plc/programs/`, serving its I/O image over Modbus TCP | `127.0.0.1:5020→502` |
| `workspace` | built from `.devcontainer/` | Dev shell for VS Code "Reopen in Container" (profile `dev`, not started by plain `docker compose up`) | none |

All published ports bind to 127.0.0.1: nothing in the lab is reachable from the LAN.

## Data flow (phase 0, plumbing proof)

1. `plc` runs the placeholder `tank` program every 100 ms and updates its
   Modbus tables (coils, discrete inputs, holding and input registers).
2. Ignition's Modbus TCP driver polls `plc:502` through the device connection
   `plc_modbus` (zero-based addressing). The device appears in Ignition's
   OPC UA server as `ns=1;s=[plc_modbus]<address>`, e.g. `[plc_modbus]IRUS0`.
3. OPC tags in the `default` tag provider point at those items (Ignition is
   an OPC UA *client of its own server*, the normal Ignition pattern).
4. With "exposed tags" enabled, tags are visible to outside OPC UA clients as
   `ns=2;s=[default]<path>`.
5. The DB connection `mes` (PostgreSQL JDBC) serves the historian, alarm
   journal, transaction groups and MES scripts once they are configured.

The target plant (robot cell + MES) is described in [../README.md](../README.md);
the PLC/OPC UA layer for it replaces the `tank` placeholder.

## Versions

| Item | Version | Where pinned |
|---|---|---|
| Ignition | 8.3.10 (b2026100610), standard edition, trial | `.env` `IGNITION_VERSION` |
| PostgreSQL | 19 (19.0 at setup) | `.env` `POSTGRES_VERSION` |
| Python (PLC, workspace) | 3.13 | `compose.yaml`, `.devcontainer/Dockerfile` |
| pymodbus (workspace only, client for tests) | 3.16.2 | `.devcontainer/Dockerfile` |
| asyncua (used for tests so far) | 2.1.0 | ad hoc |

The PLC's Modbus server is hand-written (`plc/modbus_server.py`, stdlib only).
pymodbus 3.16 is half-way through its v4 API migration and deprecates its server
datastore classes, so the lab does not depend on it server-side.

## Lab-only relaxations (do not copy to a customer system)

| Setting | Lab value | Why | Production practice |
|---|---|---|---|
| OPC UA server endpoint | bind `0.0.0.0`, security policies `None` + `Basic256Sha256`, anonymous access on | lets scripts read devices/tags without certificates | `SignAndEncrypt` only, no anonymous, trusted client certs |
| Exposed tag providers | on | read tags from external OPC UA clients for verification | off unless a consumer needs it |
| API token `claude-lab` | gateway read + write (`Authenticated/ApiAutomation`) | lets `scripts/ign` and Claude Code configure the gateway | scoped tokens per integration, `secureChannelRequired` with HTTPS |
| Gateway HTTP only | no TLS | localhost only | HTTPS with a real certificate |

Anonymous OPC UA clients can browse and read, but not write: write/call is
granted only to `AuthenticatedUser` (Ignition default access-control).

## Repository layout

```
compose.yaml              the stack (also the devcontainer's compose file)
.env / .env.example       versions, uid, passwords, API token (.env is git-ignored)
.devcontainer/            devcontainer.json + workspace image
plc/                      simulated PLC (Modbus server, I/O image, programs/)
db/init/                  SQL run once when the PostgreSQL volume is created
ignition/data/            Ignition data dir (bind mount); config/resources/core and projects are versioned
gateway-config/           JSON bodies sent to the gateway REST API (reproducible config)
scripts/ign               CLI for the gateway REST API
docs/                     scenario, OPC UA registry, MES requirements (see docs/README.md)
docs/system/              this documentation: architecture, operations, automation, glossary
```
