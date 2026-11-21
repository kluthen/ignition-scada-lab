# ignition-scada-lab

> **Test project.** This is a personal research and learning sandbox for
> Inductive Automation **Ignition 8.3**. It is not a product, not a customer
> deliverable, and not production-ready. Its security settings are deliberately
> relaxed for local experiments (see [lab-only relaxations](docs/system/architecture.md#lab-only-relaxations-do-not-copy-to-a-customer-system)).
> Not affiliated with or endorsed by Inductive Automation. "Ignition" is a
> trademark of Inductive Automation.

A self-contained Docker lab for learning Ignition on a small simulated plant:
a finishing area of five identical robot cells, each driven by its own
simulated PLC, supervised by Ignition, and feeding a small MES on PostgreSQL.
A lab autopilot keeps the cells producing, so orders, part records, state logs
and tag history accumulate on their own. Everything is configured as code
through Ignition 8.3's file-based configuration and REST API, which also makes
it workable with an AI coding assistant (Claude Code).

## What's inside

| Component | Details |
|---|---|
| Ignition Gateway 8.3.10 | official `inductiveautomation/ignition` image, Maker Edition (or the standard edition in trial mode) |
| PostgreSQL 19 | database `mes`: MES tables (schema `mes`), tag history (schema `historian`), alarm journal later |
| Simulated cell controllers (×5) | one container per cell (`plc-c01`..`plc-c05`), a Python process with a 100 ms scan running a robot cell (PackML state machine, conveyors, camera, SCARA robot, reject bin, order and traceability handshakes). Each serves an OPC UA server generated from the signal registry (asyncua) and a stdlib Modbus TCP I/O coupler (`plc/`) |
| Plant design | scenario, plant layout and cell instance table, OPC UA / Modbus signal registry (CSV, single source of truth), fault catalogue, MES customer requirements (`docs/`) |
| Ignition config as code | 5 OPC UA connections and 5 Modbus devices from templates, a cell UDT and its 5 instances generated from the registry, tag groups, a `sim` tag provider, SQL Historian (`gateway-config/`, `scripts/`) |
| Ignition project `plant` | Perspective HMI (area overview, KPI page, cell page with mimic, commands and trends, instructor page), named queries, the MES script library (traceability, state log, orders) and the lab autopilot (`ignition/data/projects/plant/`) |
| KPIs and daily export | OEE, downtime Pareto, rejects, hourly production as SQL functions (`db/init/20-kpi.sql`), shown on the KPI page and exported every night by the `exporter` service: PDF report, XLSX, CSVs and a manifest in `exports/daily/<date>/` |
| Devcontainer | Python 3.13 workspace with pymodbus, asyncua and psql (`.devcontainer/`) |
| Tooling | `scripts/ign` (gateway REST API CLI), `scripts/opc` (OPC UA browse/read/watch), bootstrap/apply/generate scripts, `scripts/cell_smoke_test.py` |

All ports bind to `127.0.0.1`:

| Port | Service |
|---|---|
| 8088 | gateway |
| 62541 | Ignition OPC UA server |
| 4841..4845 | cell controllers C01..C05, OPC UA |
| 5021..5025 | cell controllers C01..C05, Modbus TCP |
| 5432 | PostgreSQL |

## Quick start

Requirements: Docker with Compose v2, Python 3 on the host (for the scripts).

```bash
git clone https://github.com/kluthen/ignition-scada-lab.git && cd ignition-scada-lab
cp .env.example .env               # set HOST_UID/HOST_GID (`id -u`/`id -g`) and both passwords
docker compose up -d               # seeds ignition/data, commissions the gateway (about 30 s)
scripts/bootstrap_token.py         # creates the REST API token, stores it in .env
docker compose restart gateway
scripts/create_db_connection.py    # gateway DB connections "mes" and "historian" (password from .env)
scripts/db_apply.py                # MES tables, cell master data from docs/cells.csv
scripts/apply_gateway_config.py    # OPC connections C01..C05, Modbus devices, historian, OPC UA server settings
scripts/ign info                   # should print the gateway info
```

The cells start producing within seconds (lab autopilot). Then:

- HMI: http://127.0.0.1:8088/data/perspective/client/plant (overview, `/kpi`, `/cell/C03`, `/instructor`)
- Daily export: `exports/daily/<date>/` after 00:10 for the previous day, or now with
  `docker compose run --rm exporter python daily_export.py run today` (partial day)
- Gateway: http://127.0.0.1:8088, log in with `GATEWAY_ADMIN_USERNAME` / `GATEWAY_ADMIN_PASSWORD` from `.env`
- Data: `docker compose exec db psql -U ignition -d mes` (see [docs/system/mes.md](docs/system/mes.md#looking-at-the-data))
- Smoke test of one controller: set `[default]ANN/FIN/C03/MES/AutoRun` false (HMI cell page), then
  `docker compose --profile dev up -d workspace && docker compose exec workspace python scripts/cell_smoke_test.py C03`

Or open the folder in VS Code and choose "Dev Containers: Reopen in Container".

By running the gateway image you accept the
[Inductive Automation software license](https://inductiveautomation.com/ignition/license)
(`ACCEPT_IGNITION_EULA=Y` in `compose.yaml`). The lab runs Ignition Maker
Edition: free, no time limit, for personal, non-commercial use only. It needs
your own Maker licence key and activation token in `.env`. Without them, set
`IGNITION_EDITION=standard`: the trial then needs a reset every 2 hours from
the gateway web UI, and until then Modbus, the historian and Perspective stop
([docs/system/operations.md](docs/system/operations.md#licence-maker-edition-trial-demo-mode)).

## Documentation

| Document | What it covers |
|---|---|
| [docs/system/architecture.md](docs/system/architecture.md) | containers, ports, data flow, versions, lab-only security relaxations, repo layout |
| [docs/system/operations.md](docs/system/operations.md) | start/stop, URLs and credentials, Maker Edition / trial / demo mode, switching edition, reset, backups, running a cell by hand, troubleshooting |
| [docs/system/gateway-automation.md](docs/system/gateway-automation.md) | 8.3 file-based config and REST API, API tokens, verified recipes (DB connections, OPC connections, Modbus devices, UDTs, historian, projects, views, named queries) |
| [docs/system/mes.md](docs/system/mes.md) | MES first slice (tables, traceability, state log, orders) and the lab autopilot |
| [docs/system/hmi.md](docs/system/hmi.md) | Perspective project `plant`: pages, parameterised views, charts, named queries |
| [docs/system/kpi.md](docs/system/kpi.md) | KPI definitions (OEE, downtime, production day), SQL functions, KPI screen and graphs, daily production export (folder layout, manifest, schedule, shipping) |
| [docs/system/panorama-e2-to-ignition.md](docs/system/panorama-e2-to-ignition.md) | concept map for engineers coming from Codra Panorama E2 |
| [docs/system/status.md](docs/system/status.md) | progress, next steps, open decisions |
| [docs/README.md](docs/README.md) | plant design index: [plant layout](docs/plant-layout.md) ([cells.csv](docs/cells.csv)), [scenario](docs/scenario.md), [OPC UA registry](docs/opcua-registry.md) ([CSV](docs/opcua-registry.csv)), [fault catalogue](docs/fault-catalogue.md), [MES requirements](docs/mes-requirements.md) |
| [CLAUDE.md](CLAUDE.md) | working rules for Claude Code in this repo |

The plant (Brevent Hydraulics, finishing area, cells C01..C05) and the customer are fictional.

## What is versioned

From the gateway data dir, only `ignition/data/config/resources/core/**` and
`ignition/data/projects/**` are committed. Runtime state, caches, certificates,
per-gateway config, built-in Inductive Automation assets, and every
secret-bearing resource (user password hashes, API token, DB connection) are
git-ignored. The bootstrap scripts recreate the secrets from `.env`.

## License

Lab code and documentation: no license chosen yet, so all rights reserved by
default. Ignition itself is proprietary software from Inductive Automation and
is not included in this repository: the official Docker image is pulled at
runtime.
