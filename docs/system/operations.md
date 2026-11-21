# Operating the lab

## Start and stop

Two equivalent ways to run the stack.

**Plain Docker Compose (host shell)**

```bash
cd ~/work/ignition
cp -n .env.example .env        # first time only, then edit uid/passwords
docker compose up -d           # gateway-init, gateway, db, plc
docker compose ps
docker compose down            # stop (data persists)
```

**VS Code devcontainer**: open the folder, then "Dev Containers: Reopen in
Container". It starts the same services plus `workspace`, a Python 3.13 shell
with git, curl, jq, netcat and pymodbus, with the repo mounted at `/workspace`.
Closing the window stops the stack (`shutdownAction: stopCompose`). From inside
the workspace, services are reached by name: `gateway:8088`, `db:5432`, `plc:502`.

First start takes about 30 s: `gateway-init` seeds `ignition/data`, then the
gateway commissions itself from `.env` (EULA, admin user, edition) and loads
its modules. It is ready when `docker compose ps` shows `gateway` as `healthy`,
or when `curl -s http://127.0.0.1:8088/StatusPing` answers `{"state":"RUNNING"}`.

## Addresses and credentials

| What | Where | Credentials |
|---|---|---|
| Gateway web UI | http://127.0.0.1:8088 | `GATEWAY_ADMIN_USERNAME` / `GATEWAY_ADMIN_PASSWORD` in `.env` |
| Perspective sessions | http://127.0.0.1:8088/data/perspective/client/&lt;project&gt; | per project security |
| Designer | install the Designer Launcher from the gateway home page, add gateway `http://127.0.0.1:8088` | same admin user |
| Gateway REST API | http://127.0.0.1:8088/data/api/v1/…, OpenAPI at `/openapi` | header `X-Ignition-API-Token: $IGNITION_API_TOKEN` (`.env`) |
| Ignition OPC UA server | `opc.tcp://127.0.0.1:62541` (host) / `opc.tcp://gateway:62541` (containers) | anonymous read, security None allowed (lab only) |
| PostgreSQL | `127.0.0.1:5432`, db `mes` | `POSTGRES_USER` / `POSTGRES_PASSWORD` in `.env` |
| Cell controller OPC UA | `opc.tcp://127.0.0.1:4840/ignition-lab/` (host) / `opc.tcp://plc:4840/ignition-lab/` (containers) | anonymous, security None |
| Cell I/O coupler IO01 (Modbus TCP) | `127.0.0.1:5020` (host) / `plc:502` (containers), unit 1 | none |

Quick checks:

```bash
scripts/ign info                                   # name, version, edition, licence/trial
docker compose exec db psql -U ignition -d mes     # SQL shell
docker compose logs -f plc                         # controller log: state changes, commands, order loads
docker compose exec workspace python scripts/cell_smoke_test.py   # 10-part order end to end (about 45 s)
docker compose logs -f gateway                     # gateway log (also: Status > Logs in the web UI)
```

## Trial mode (standard edition)

Without a licence, the standard edition runs in trial mode: every module works,
and after 2 hours the gateway stops running the licensed modules (devices stop
polling, Perspective sessions stop) until the trial is reset. Reset it from the
banner in the gateway web UI. There is no REST route for it. Reset when the
timer has run out; Inductive Automation does not want early resets used to keep
a system running continuously. A gateway restart does not reset the timer.

## Switching to Maker Edition

The edition is chosen when the gateway is first commissioned. To switch:

1. Get a Maker licence key and activation token from your Inductive Automation
   account (https://inductiveautomation.com/ignition/maker-edition).
2. Set `IGNITION_EDITION=maker`, `IGNITION_LICENSE_KEY=…`, `IGNITION_ACTIVATION_TOKEN=…` in `.env`.
3. Re-commission from a clean data dir (see "Reset the gateway" below), then
   re-apply the configuration (`gateway-config/` JSON through `scripts/ign`, or
   restore the versioned `ignition/data/config` and `projects` from git).

Maker is for personal, non-commercial use only (10,000 tags, 10 sessions, a
subset of modules, no redundancy). Use the standard trial for anything that
might feed a customer mission.

## Reset the gateway

```bash
docker compose down
cp -a ignition/data /tmp/ignition-data-backup   # optional safety copy
rm -rf ignition/data && mkdir ignition/data
docker compose up -d                   # gateway-init re-seeds, gateway re-commissions
```

The API token is part of the gateway config. After a reset, recreate it:

```bash
scripts/bootstrap_token.py --force && docker compose restart gateway
```

The database lives in the Docker volume `ignition-lab_pgdata`; `docker compose
down -v` deletes it too. `db/init/*.sql` re-runs only on a fresh volume.

## Backups

- Gateway backup (`.gwbk`): web UI, Platform > Backup/Restore, or
  `GET /data/api/v1/backup` (see `scripts/ign routes backup`).
- Versioned config: `ignition/data/config/resources/core/**` and
  `ignition/data/projects/**` (see `.gitignore` for what is excluded).
- Embedded secrets (e.g. the DB password in `database-connection/mes/config.json`)
  are encrypted with this gateway's own key, kept under the git-ignored
  `config/local`. They do not decrypt on another gateway: re-enter them there.

## Gateway configuration after a fresh clone or reset

The versioned part of `ignition/data` already holds the Modbus device `IO01`,
the tags, the tag groups and the `sim` tag provider. The secret-bearing
resources are recreated from `.env`:

```bash
scripts/bootstrap_token.py && docker compose restart gateway   # REST API token
scripts/create_db_connection.py                                 # DB connection "mes"
scripts/apply_gateway_config.py                                 # OPC connection C01, device IO01, OPC UA server settings
scripts/generate_tags.py                                        # (re)generate tags from docs/opcua-registry.csv
```

All four are idempotent.

## Running the cell

The controller starts in **Stopped** with no order, robot not homed, conveyors
empty. A typical session, writing tags (Designer tag browser, a Perspective
screen, or any OPC UA client on `plc:4840`):

| Step | Write | Expect |
|---|---|---|
| Reset | `C01/Command/CntrlCmd` = 1 | `CmdResult` 1, state Resetting (2 s) → Idle |
| Load an order (MES side) | `Order/Request/OrderId` = `OF-0001`, `PartType` = 1, `TargetQuantity` = 50, then `LoadRequest` = true | `LoadResult` 1, `Order/Active/OrderStatus` 1 |
| Start | `CntrlCmd` = 2 | Starting (1 s) → Execute; first part placed about 10 s later, then 24 parts/min |
| Traceability (MES side) | when `Traceability/DataReady` is true, write `Traceability/Sequence` into `AckSequence` | next record presented; `BufferCount` shows the backlog (200 max) |
| Reject bin full (about every 52 min) | `RJ01/Command/BinEmptied` = true, then `CntrlCmd` = 5 (Unhold) | count back to 0, Execute |
| End of order | n/a | Completing (CV02 empties) → Complete, `OrderStatus` 3 |

Command codes: 1 Reset, 2 Start, 3 Stop, 4 Hold, 5 Unhold, 6 Suspend,
7 Unsuspend, 8 Abort, 9 Clear. `CmdResult`: 1 accepted, 2 wrong state,
3 interlock, 4 invalid value. See scenario.md section 5.

Instructor knobs live in `[sim]Sim/Process`:
- `FeedInterval`
- `UpstreamFeedEnable` (false starves the cell, which suspends after 10 s)
- `RejectEveryN`
- `AutoEmptyRejectBin`

Nothing persists across a `plc` restart: counters restart at 0 and
`Admin/StartUpTime` changes.

## Editing the simulated controller

`plc/` and `docs/opcua-registry.csv` are mounted read-only into the `plc`
container. After editing either:

```bash
docker compose restart plc && docker compose logs --tail 20 plc
docker compose exec workspace python scripts/cell_smoke_test.py
```

After changing the CSV, also run `scripts/generate_tags.py` so the Ignition
tags follow. `PLC_PROGRAM` selects the module under `plc/programs/` (default
`cell`), and `PLC_SCAN_MS` sets the scan period. Rebuild the image
(`docker compose build plc`) only when `plc/Dockerfile` changes.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `gateway` restarts in a loop, log says `cannot stat …/data/gateway.xml_clean` | `ignition/data` was not seeded: a bind mount hides the image's data dir. `gateway-init` handles it; if the dir holds a half-written state, empty it and `docker compose up -d` again. |
| Device `IO01` or OPC connection `C01` disconnected, tags Bad | `docker compose ps plc`; check the `plc` log for a traceback after a code change. |
| OPC connection `C01` faulted with "Unable to retrieve KeyPair for alias 'client'" | the connection has no keystore alias password; run `scripts/apply_gateway_config.py` |
| `scan error` lines in the `plc` log | the program raised; the controller keeps scanning, so read the traceback |
| REST API answers 401 | missing or wrong `X-Ignition-API-Token`. |
| REST API answers 403 | the token's security level is not in the gateway read/write permissions. See [gateway-automation.md](gateway-automation.md#api-token). |
| Everything stops after about 2 h | trial expired: reset it from the web UI banner. |
