# Operating the lab

## Start and stop

Two equivalent ways to run the stack.

**Plain Docker Compose (host shell)**

```bash
cd ~/work/ignition
cp -n .env.example .env        # first time only, then edit uid/passwords
docker compose up -d           # gateway-init, gateway, db, plc-c01 .. plc-c06, exporter
docker compose ps
docker compose down            # stop (data persists)
```

**VS Code devcontainer**: open the folder, then "Dev Containers: Reopen in
Container". It starts the same services plus `workspace`, a Python 3.13 shell
with git, curl, jq, netcat, psql, asyncua and pymodbus, with the repo mounted at
`/workspace`. Closing the window stops the stack (`shutdownAction: stopCompose`).
From inside the workspace, services are reached by name: `gateway:8088`,
`db:5432`, `plc-c03:4840`, `plc-c03:502`.

First start takes about 30 s: `gateway-init` seeds `ignition/data`, then the
gateway commissions itself from `.env` (EULA, admin user, edition) and loads
its modules. It is ready when `docker compose ps` shows `gateway` as `healthy`,
or when `curl -s http://127.0.0.1:8088/StatusPing` answers `{"state":"RUNNING"}`.

As soon as the gateway runs, the lab autopilot makes the cells known to
Ignition produce (C01..C05; C06 once commissioned, training week day 3)
(see [mes.md](mes.md)): orders, part records and state changes accumulate in
PostgreSQL, and tag history in the `historian` schema. Ten minutes after
midnight, the `exporter` writes the previous day's export to
`exports/daily/<date>/` ([kpi.md](kpi.md)).

## Addresses and credentials

| What | Where | Credentials |
|---|---|---|
| Gateway web UI | http://127.0.0.1:8088 | `GATEWAY_ADMIN_USERNAME` / `GATEWAY_ADMIN_PASSWORD` in `.env` |
| HMI (Perspective, project `plant`) | http://127.0.0.1:8088/data/perspective/client/plant (overview), `…/kpi`, `…/cell/C03`, `…/instructor` | none (lab) |
| Daily production exports | `exports/daily/<YYYY-MM-DD>/` on the host (PDF, XLSX, CSVs, `manifest.json`) | files, owned by your uid |
| Designer | install the Designer Launcher from the gateway home page, add gateway `http://127.0.0.1:8088` | same admin user |
| Gateway REST API | http://127.0.0.1:8088/data/api/v1/…, OpenAPI at `/openapi` | header `X-Ignition-API-Token: $IGNITION_API_TOKEN` (`.env`) |
| Ignition OPC UA server | `opc.tcp://127.0.0.1:62541` (host) / `opc.tcp://gateway:62541` (containers) | anonymous read, security None allowed (lab only) |
| PostgreSQL | `127.0.0.1:5432`, db `mes` (schemas `mes`, `historian`, `alarms`) | `POSTGRES_USER` / `POSTGRES_PASSWORD` in `.env` |
| Cell Cn controller OPC UA | `opc.tcp://127.0.0.1:484n/ignition-lab/` (host) / `opc.tcp://plc-c0n:4840/ignition-lab/` (containers) | anonymous, security None |
| Cell Cn I/O coupler IO01 (Modbus TCP) | `127.0.0.1:502n` (host) / `plc-c0n:502` (containers), unit 1 | none |

Ports per cell are listed in [docs/cells.csv](../cells.csv).

Quick checks:

```bash
scripts/ign info                                   # name, version, edition, licence/trial
scripts/ign get /trial                             # trial seconds left (standard edition only)
docker compose exec db psql -U ignition -d mes     # SQL shell
docker compose logs -f plc-c03                     # controller log: state changes, commands, order loads
docker compose logs -f gateway | grep -E 'm.cell|autopilot'   # MES and autopilot activity
docker compose logs exporter                       # "exported <day> (complete) to /exports/daily/<day>"
ls exports/daily/                                  # one folder per exported production day
docker compose run --rm exporter python daily_export.py run today   # partial export of today, now
```

Useful SQL (more in [mes.md](mes.md#looking-at-the-data)):

```sql
SELECT cell, count(*) FILTER (WHERE result = 1) good, count(*) FILTER (WHERE result <> 1) rej
FROM mes.part_result GROUP BY cell ORDER BY cell;
SELECT order_id, product_code, target_qty, status, cell FROM mes.work_order ORDER BY seq DESC LIMIT 10;
```

## Licence: Maker Edition, trial, demo mode

**The lab runs Maker Edition** (since 2026-11-21, `scripts/ign info` shows
`"edition": "maker"`, licence `Activated`, restriction `tags 10000`). Everything
used here is on the 8.3 Maker module list (OPC UA, Modbus driver, Perspective,
SQL Historian; also SQL Bridge, Reporting, Alarm Notification). Limits and
differences:

- 10,000 tags (the lab uses about 1,000), 10 Perspective sessions, no redundancy.
- No Vision module (the gateway home page shows only Designer and
  Perspective), no Perspective Workstation.
- Every new Perspective session first shows a "Personal Use Only" notice to
  accept ("Agree & close").
- Terms: "strictly available for non-commercial and personal educational use",
  so no customer or paid work on this gateway.

The licence key and activation token come from the user's Inductive Automation
account (https://account.inductiveautomation.com/maker-licenses) and live in
`.env` (`IGNITION_LICENSE_KEY`, `IGNITION_ACTIVATION_TOKEN`). The gateway
activates them online when it is commissioned.

### Switching edition

`IGNITION_EDITION` is applied only when the gateway is commissioned, so a
switch needs a fresh data dir. This is how the switch to Maker was done
(2026-11-21). It keeps the versioned config of the working tree, including
changes not yet committed, which `git checkout` would not:

```bash
docker compose stop gateway
B=~/work/ignition-data-backup-$(date +%F)          # full copy of the old gateway
git ls-files -co --exclude-standard ignition/data | while read -r f; do [ -e "$f" ] && echo "$f"; done > /tmp/keep.txt
mv ignition/data "$B" && mkdir ignition/data
(cd "$B" && sed 's#^ignition/data/##' /tmp/keep.txt | while read -r f; do cp -a --parents "$f" ~/work/ignition/ignition/data/; done)
# set IGNITION_EDITION (and the Maker key/token) in .env, then:
docker compose up -d gateway-init gateway
```

Then follow "Gateway configuration after a fresh clone or reset" below. The
database volume is not touched. The controllers keep running meanwhile; the
part records they produce while the gateway is down wait in their
traceability buffer and reach `mes.part_result` once the MES runs again (no
sequence gap at the switch). Orders running at the time continue.

### Standard edition: trial and demo mode

Without a licence, the standard edition runs in trial mode: every module works
for 2 hours, then the licensed modules go into "demo expired" until the trial
is reset (gateway web UI banner; a gateway restart does not reset it, and there
is no REST route). What happens to the lab when the trial expires (verified
2026-11-21):

| Part | Trial expired |
|---|---|
| OPC UA connections C01..C05 (platform OPC UA client) | keep working |
| Tag event scripts, gateway scripting: MES and autopilot | keep working (part records, orders, state log keep accumulating) |
| Modbus devices Cn_IO01 (driver module) | `Bad_TrialExpired`: conveyors, bin, safety, energy members are Bad |
| SQL Historian | stops storing ("Demo_Expired") |
| Perspective | sessions refused ("Trial Expired" page) |
| Ignition's own OPC UA server (exposed tags, device items) | Bad |

So data generation partly continues without the trial, but trends and the HMI
need it. Do not script trial resets: the expiry is deliberate, so that the trial
is not used as a pseudo-production system. That is why the lab moved to Maker.

## Certification gateway (`gateway-cert`)

An empty Standard Edition gateway for the Core Certification
([../training/core-certification.md](../training/core-certification.md)):
Vision, Reporting, SQL Bridge, alarm notification and the other default
modules, in trial mode. It is not part of the lab: no tags, no project, no
API token; it only shares the PostgreSQL server (database `cert`).

```bash
docker compose --profile cert up -d gateway-cert   # about 20 s; also starts db
curl -s http://127.0.0.1:8089/StatusPing           # {"state":"RUNNING"}
docker compose stop gateway-cert                   # stop it (data kept in the volume)
```

| What | Where | Credentials |
|---|---|---|
| Web UI, Designer Launcher | http://127.0.0.1:8089 (add this gateway in the Designer Launcher) | `GATEWAY_ADMIN_USERNAME` / `GATEWAY_ADMIN_PASSWORD` from `.env`, until a restored backup brings its own users |
| Database for exercises | from the cert gateway: `jdbc:postgresql://db:5432/cert` | `POSTGRES_USER` / `POSTGRES_PASSWORD` |

- **Trial**: 2 hours, then reset from the banner of its web page. By hand
  only, never scripted. Expired trial: see the table above.
- **Fresh install** (what the practice backup and the exam ask for): drop
  the volume, the image seeds a new data dir on the next start.

  ```bash
  docker compose stop gateway-cert && docker compose rm -f gateway-cert
  docker volume rm ignition-lab_certdata
  docker compose --profile cert up -d gateway-cert
  ```
- **Restore a backup** (`Core_Certification.gwbk` or your own): web UI,
  Platform > Backup/Restore. Keep the files outside the repo or let
  `.gitignore` (`*.gwbk`) hide them.
- Memory: the host has about 11 GB; lab gateway (2 GB heap) and cert gateway
  (1.5 GB) run together. Stop the one you do not use if the host gets short.
- `docker compose down` without `--profile cert` leaves it running: use
  `docker compose --profile cert down` to stop everything.

## Reset the gateway

```bash
docker compose down
cp -a ignition/data /tmp/ignition-data-backup   # optional safety copy
rm -rf ignition/data && git checkout ignition/data   # keep the versioned config
docker compose up -d                   # gateway-init seeds the rest, gateway re-commissions
```

Then recreate the secret-bearing resources (next section). The database lives
in the Docker volume `ignition-lab_pgdata`; `docker compose down -v` deletes it
too. `db/init/*.sql` runs by itself only on a fresh volume; `scripts/db_apply.py`
replays it on an existing one.

## Backups

- Gateway backup (`.gwbk`): web UI, Platform > Backup/Restore, or
  `GET /data/api/v1/backup` (see `scripts/ign routes backup`).
- Versioned config: `ignition/data/config/resources/core/**` and
  `ignition/data/projects/**` (see `.gitignore` for what is excluded).
- Embedded secrets (e.g. the DB passwords in `database-connection/*/config.json`)
  are encrypted with this gateway's own key, kept under the git-ignored
  `config/local`. They do not decrypt on another gateway: re-enter them there.
- Data: `docker compose exec db pg_dump -U ignition mes > mes.sql`.
- Daily exports: `exports/daily/` is plain files on the host, outside git and
  outside the database volume. The service never deletes them.

## Gateway configuration after a fresh clone or reset

The versioned part of `ignition/data` already holds the Modbus devices, the
UDTs and their instances, the tag groups, the `sim` tag provider, the
historian provider and the project `plant`. The secret-bearing resources are
recreated from `.env`:

```bash
scripts/bootstrap_token.py && docker compose restart gateway   # REST API token
scripts/create_db_connection.py      # DB connections "mes" and "historian"
scripts/db_apply.py                  # MES tables; mes.cell from docs/cells.csv
scripts/apply_gateway_config.py      # OPC connections C0n, devices C0n_IO01 (rows of cells.csv), historian,
                                     # gateway scripting project, OPC UA server settings
scripts/generate_tags.py             # (re)generate the UDTs and instances from the CSVs
```

All of them are idempotent.

Commissioning on top of the versioned config creates a `temp` user source and
identity provider, because the versioned `default` user source has no
`users.json` (password hashes are git-ignored). The admin user from `.env`
goes into `temp`, and `security-properties` points the gateway login at it. That
works, but do not commit the changed `security-properties/config.json` from such
a gateway. When the old data dir is still at hand (edition switch), restore the
`default` arrangement instead, as done on 2026-11-21:

```bash
C=ignition/data/config/resources/core/ignition
cp -a "$B"/config/resources/core/ignition/user-source/default/users.json $C/user-source/default/
git checkout -- $C/security-properties/config.json
rm -rf $C/user-source/temp $C/identity-provider/temp
scripts/ign scan config
```

The licence itself appears as system tags under
`tag-definition/System/Gateway/Licenses/<licence id>/`, which is git-ignored:
the folder name comes from the licence key.

## Running a cell by hand

The autopilot drives every cell whose `MES/AutoRun` tag is true (default).
To drive one yourself, switch it off first: HMI cell page ("Lab autopilot"
toggle), the instructor page, or the tag `[default]ANN/FIN/C03/MES/AutoRun`.
The MES functions (part records, state log, order status) keep running.

Each controller starts in **Stopped** with no order, robot not homed, conveyors
empty. A typical session, writing tags (HMI cell page, Designer tag browser,
or any OPC UA client on `plc-c03:4840`):

| Step | Write | Expect |
|---|---|---|
| Reset | `Command/CntrlCmd` = 1 | `CmdResult` 1, state Resetting (2 s) → Idle |
| Load an order (MES side) | `Order/Request/OrderId` = `OF-0001`, `PartType` = 1, `TargetQuantity` = 50, then `LoadRequest` = true | `LoadResult` 1, `Order/Active/OrderStatus` 1 |
| Start | `CntrlCmd` = 2 | Starting (1 s) → Execute; first part placed about 10 s later, then 24 parts/min |
| Traceability (MES side) | done by the MES (`mes.cell.store_record`) even with the autopilot off | `BufferCount` stays at 0 or 1 |
| Reject bin full | `RJ01/Command/BinEmptied` = true, then `CntrlCmd` = 5 (Unhold) | count back to 0, Execute |
| End of order | n/a | Completing (CV02 empties) → Complete, `OrderStatus` 3 |

Command codes: 1 Reset, 2 Start, 3 Stop, 4 Hold, 5 Unhold, 6 Suspend,
7 Unsuspend, 8 Abort, 9 Clear. `CmdResult`: 1 accepted, 2 wrong state,
3 interlock, 4 invalid value. See scenario.md section 5.

Instructor knobs live in `[sim]C0n/Process` (HMI page `/instructor`):
- `FeedInterval`
- `UpstreamFeedEnable` (false starves the cell, which suspends after 10 s)
- `RejectEveryN`
- `AutoEmptyRejectBin`

Their start values come from docs/cells.csv. Nothing persists across a
controller restart: counters restart at 0 and `Admin/StartUpTime` changes.

## Editing the simulated controller

`plc/`, `docs/opcua-registry.csv` and `docs/cells.csv` are mounted read-only
into the six `plc-c0n` containers (same image `ignition-lab-plc`). After
editing:

```bash
docker compose restart plc-c01 plc-c02 plc-c03 plc-c04 plc-c05 plc-c06
docker compose logs --tail 20 plc-c03
# smoke test on a cell whose autopilot is off:
docker compose exec workspace python scripts/cell_smoke_test.py C03
```

After changing the registry CSV, also run `scripts/generate_tags.py` so the
UDT follows (rows with an empty `ignition_tag_path`, such as the andon station
AN01 until the training week, are skipped). A new cell is a new row in docs/cells.csv, a new `plc-c0n`
service in compose.yaml, then `scripts/db_apply.py`,
`scripts/apply_gateway_config.py` and `scripts/generate_tags.py`
(see [../plant-layout.md](../plant-layout.md)). Rebuild the image
(`docker compose build plc-c01`) only when `plc/Dockerfile` changes.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `gateway` restarts in a loop, log says `cannot stat …/data/gateway.xml_clean` | `ignition/data` was not seeded: a bind mount hides the image's data dir. `gateway-init` handles it; if the dir holds a half-written state, empty it and `docker compose up -d` again. |
| A device `C0n_IO01` or OPC connection `C0n` disconnected, tags Bad | `docker compose ps`; check the `plc-c0n` log for a traceback after a code change. |
| Modbus members `Bad_TrialExpired`, HMI shows "Trial Expired" | the gateway runs the standard edition and its trial expired: reset it from the web UI banner, or check that `.env` has `IGNITION_EDITION=maker` and switch (see Licence above). |
| Maker licence not activated after commissioning | activation is online: the gateway needs internet access at commissioning; check the key and token in `.env`, `scripts/ign info` |
| Gateway log: `C03: MES cycle skipped, not good: …` (every 5 min) | an OPC UA member the MES needs is Bad: controller down or connection faulted. |
| OPC connection faulted with "Unable to retrieve KeyPair for alias 'client'" | the connection has no keystore alias password; run `scripts/apply_gateway_config.py` |
| `scan error` lines in a `plc-c0n` log | the program raised; the controller keeps scanning, so read the traceback |
| Smoke test fails or the cell does unexpected things | the autopilot is driving the same cell: set its `MES/AutoRun` false. |
| Fresh gateway log: `database 'historian' does not exist`, `Server "C01" does not exist`, one `Error forwarding data` | normal until `create_db_connection.py` and `apply_gateway_config.py` have run; the historian and the MES recover by themselves (verified on a fresh clone) |
| No export folder for yesterday after 00:10 | `docker compose ps exporter` (running?), `docker compose logs exporter` (traceback after "export failed"; the next poll in 5 min retries). Folders starting with a dot are unfinished exports, left by an interrupted run: delete them. Run the day by hand: `docker compose run --rm exporter python daily_export.py run YYYY-MM-DD` |
| `exporter` cannot write to `/exports` | `exports/` was created by Docker as root (missing from the clone): `sudo chown -R $(id -u):$(id -g) exports` |
| KPI page tiles show `-` | no state log or parts in the chosen period (e.g. Yesterday on the lab's first day) |
| REST API answers 401 | missing or wrong `X-Ignition-API-Token`. |
| REST API answers 403 | the token's security level is not in the gateway read/write permissions. See [gateway-automation.md](gateway-automation.md#api-token). |
