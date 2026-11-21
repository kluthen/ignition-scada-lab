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
| PLC Modbus TCP | `127.0.0.1:5020` (host) / `plc:502` (containers) | none |

Quick checks:

```bash
scripts/ign info                                   # name, version, edition, licence/trial
docker compose exec db psql -U ignition -d mes     # SQL shell
docker compose logs -f plc                         # PLC scan/network log
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

## Editing the simulated PLC

`plc/` is mounted read-only into the `plc` container. After editing it:

```bash
docker compose restart plc && docker compose logs --tail 20 plc
```

`PLC_PROGRAM` (in `compose.yaml`) selects the module under `plc/programs/`, and
`PLC_SCAN_MS` sets the scan period.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `gateway` restarts in a loop, log says `cannot stat …/data/gateway.xml_clean` | `ignition/data` was not seeded: a bind mount hides the image's data dir. `gateway-init` handles it; if the dir holds a half-written state, empty it and `docker compose up -d` again. |
| Device `plc_modbus` shows Disconnected | `docker compose ps plc`; check the `plc` log for a traceback after a code change. |
| REST API answers 401 | missing or wrong `X-Ignition-API-Token`. |
| REST API answers 403 | the token's security level is not in the gateway read/write permissions. See [gateway-automation.md](gateway-automation.md#api-token). |
| Everything stops after about 2 h | trial expired: reset it from the web UI banner. |
