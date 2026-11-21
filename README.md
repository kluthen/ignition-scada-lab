# ignition-scada-lab

> **Test project.** This is a personal research and learning sandbox for
> Inductive Automation **Ignition 8.3**. It is not a product, not a customer
> deliverable, and not production-ready. Its security settings are deliberately
> relaxed for local experiments (see [lab-only relaxations](docs/system/architecture.md#lab-only-relaxations-do-not-copy-to-a-customer-system)).
> Not affiliated with or endorsed by Inductive Automation. "Ignition" is a
> trademark of Inductive Automation.

A self-contained Docker lab for learning Ignition on a small simulated plant: a
robot cell driven by a simulated PLC, supervised by Ignition, and feeding a
small MES on PostgreSQL. Everything is configured as code through Ignition 8.3's
file-based configuration and REST API, which also makes it workable with an AI
coding assistant (Claude Code).

## What's inside

| Component | Details |
|---|---|
| Ignition Gateway 8.3.10 | official `inductiveautomation/ignition` image, standard edition in trial mode (or Maker Edition) |
| PostgreSQL 19 | database `mes` for the MES model, tag history and alarm journal |
| Simulated PLC | stdlib-only Python Modbus TCP server with a PLC-style scan cycle (`plc/`) |
| Devcontainer | Python 3.13 workspace with pymodbus, asyncua and psql (`.devcontainer/`) |
| Tooling | `scripts/ign` (gateway REST API CLI), `scripts/opc` (OPC UA browse/read/watch), bootstrap scripts |

All ports bind to `127.0.0.1`: 8088 (gateway), 62541 (OPC UA), 5432 (PostgreSQL), 5020 (Modbus).

## Quick start

Requirements: Docker with Compose v2, Python 3 on the host (for the scripts).

```bash
git clone https://github.com/kluthen/ignition-scada-lab.git && cd ignition-scada-lab
cp .env.example .env               # set HOST_UID/HOST_GID (`id -u`/`id -g`) and both passwords
docker compose up -d               # seeds ignition/data, commissions the gateway (about 30 s)
scripts/bootstrap_token.py         # creates the REST API token, stores it in .env
docker compose restart gateway
scripts/create_db_connection.py    # gateway DB connection "mes" (password from .env)
scripts/ign info                   # should print the gateway info
```

Open http://127.0.0.1:8088 and log in with `GATEWAY_ADMIN_USERNAME` /
`GATEWAY_ADMIN_PASSWORD` from `.env`. Or open the folder in VS Code and choose
"Dev Containers: Reopen in Container".

By running the gateway image you accept the
[Inductive Automation software license](https://inductiveautomation.com/ignition/license)
(`ACCEPT_IGNITION_EULA=Y` in `compose.yaml`). The trial needs a reset every
2 hours from the gateway web UI. Maker Edition is free for personal,
non-commercial use only.

## Documentation

| Document | What it covers |
|---|---|
| [docs/system/architecture.md](docs/system/architecture.md) | containers, ports, data flow, versions, lab-only security relaxations, repo layout |
| [docs/system/operations.md](docs/system/operations.md) | start/stop, URLs and credentials, trial mode, Maker Edition, reset, backups, troubleshooting |
| [docs/system/gateway-automation.md](docs/system/gateway-automation.md) | 8.3 file-based config and REST API, API tokens, verified recipes (DB connection, Modbus device, OPC UA server, tags) |
| [docs/system/panorama-e2-to-ignition.md](docs/system/panorama-e2-to-ignition.md) | concept map for engineers coming from Codra Panorama E2 |
| [docs/system/status.md](docs/system/status.md) | progress, next steps, open decisions |
| [CLAUDE.md](CLAUDE.md) | working rules for Claude Code in this repo |

The plant scenario, OPC UA registry, fault catalogue and MES requirements are
being written and will land in `docs/`.

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
