# Configuring the gateway from files and the REST API

Ignition 8.3 keeps its whole gateway configuration as files on disk and exposes
it through a REST API. In 8.1 it lived in an internal SQLite database. That
change is what makes Ignition workable from scripts, git and Claude Code. This
page records how it works in this lab, as verified on 8.3.10.

## The resource model

Everything configurable is a **resource**:

```
ignition/data/config/resources/<collection>/<module-id>/<resource-type>/<name>/
    config.json      the settings (what the web UI form edits)
    resource.json    metadata: scope, version, files, last modification actor/time
    (other files)    data files for some types, e.g. tags.json, CSS for themes
```

- **Collections**: `core` is the shared config, versioned in git. `local` is
  per-gateway and git-ignored. `external` is not used here. Singleton types
  (e.g. `ignition/security-properties`) have no `<name>` level.
- **Extension-point resources** (devices, user sources, API tokens,
  identity providers…) have `{"profile": {"type": …}, "settings": {…}}`.
  `profile.type` selects the implementation (`ModbusTcp`, `basic-token`…).
- **Tags** live in `core/ignition/tag-definition/<provider>/<folder>/tags.json`,
  one file per folder.
- `config/resources/.resources/` is a content-addressed cache maintained by
  the gateway: never edit it, and it is git-ignored.

Two ways to change config:

| Way | How | When to use |
|---|---|---|
| REST API | `scripts/ign post/put …`. The gateway validates the body, writes the files and applies the change live. | Default. Errors come back immediately. |
| Edit files, then scan | edit `config.json` / `tags.json`, then `scripts/ign scan config` (or `projects`) | Bulk or structural edits, or restoring from git. Some changes, such as API tokens and security levels, have only been confirmed to apply after `docker compose restart gateway`. |

## scripts/ign

`scripts/ign` wraps the REST API (stdlib Python; reads `.env`). Run
`scripts/ign help` for the full list. The most useful commands:

```bash
scripts/ign info                                   # gateway info + licence state
scripts/ign routes 'device|database'               # search the 588 routes of the saved OpenAPI spec
scripts/ign schema resources/ignition/database-connection --depth 12   # body schema
scripts/ign names com.inductiveautomation.opcua/device
scripts/ign find  com.inductiveautomation.opcua/device IO01
scripts/ign post  resources/com.inductiveautomation.opcua/device gateway-config/device-io01.json
scripts/ign scan  both
scripts/ign tags-export default Cell > /tmp/cell-tags.json
scripts/ign tags-import tags.json default --policy MergeOverwrite
```

The OpenAPI spec is saved in `docs/system/reference/gateway-openapi-8.3.10.json`.
It is also browsable live at http://127.0.0.1:8088/openapi (needs the token
header or a logged-in admin session).

## API token

REST calls need the header `X-Ignition-API-Token: <name>:<key>`.

`scripts/bootstrap_token.py` creates it (idempotent; `--force` rotates the key),
then `docker compose restart gateway`. What the script does (8.3.10):

1. Resource `core/ignition/api-token/claude-lab/config.json`:
   ```json
   {"profile": {"type": "basic-token", "secureChannelRequired": false,
                "securityLevels": [{"name": "Authenticated", "children": [{"name": "ApiAutomation", "children": []}]}],
                "timestamp": 0},
    "settings": {"tokenHash": "<base64url(sha256(key)) without padding>"}}
   ```
   `key` is 32 random bytes; the token sent is `claude-lab:<base64url(key) without padding>`.
   This is the same scheme as `POST /data/api/v1/api-token/generate`, which
   returns a key/hash pair.
2. Tokens cannot be granted `Authenticated/Roles/*` levels. The gateway logs
   *"Security level 'Authenticated/Roles' cannot be granted via config"*. So the
   lab defines a custom level `Authenticated/ApiAutomation` in
   `core/ignition/security-levels/config.json` and adds it to `readPermissions`
   and `writePermissions` (type `AnyOf`) in `core/ignition/security-properties/config.json`.
3. Restart the gateway. The token is stored in `.env` as `IGNITION_API_TOKEN`.

Response codes: 401 means the token is missing or invalid, 403 means it is valid
but lacks the permission.

## Recipes (all verified on 8.3.10)

### Database connection with an encrypted password

Secrets are JWE objects encrypted with the gateway key. Ask the gateway to encrypt:

```bash
curl -s -X POST -H "X-Ignition-API-Token: $IGNITION_API_TOKEN" -H 'Content-Type: text/plain' \
     --data-binary "$POSTGRES_PASSWORD" http://127.0.0.1:8088/data/api/v1/encryption/encrypt
# -> {"protected": …, "encrypted_key": …, "iv": …, "ciphertext": …, "tag": …}
```

then POST to `resources/ignition/database-connection`:

```json
[{"name": "mes", "enabled": true, "config": {
  "driver": "PostgreSQL", "translator": "POSTGRES",
  "connectURL": "jdbc:postgresql://db:5432/mes", "username": "ignition",
  "password": {"type": "Embedded", "data": { …output of /encryption/encrypt… }},
  "validationQuery": "SELECT 1"}}]
```

Driver names come from `scripts/ign names ignition/database-driver`, translators
from `ignition/database-translator`.

### Applying gateway-config/ in one go

`scripts/apply_gateway_config.py` creates or updates, with PUT and the current
signature:
- one OPC connection and one Modbus device per row of `docs/cells.csv`, from
  `opc-connection.template.json` and `device.template.json` (placeholders
  `{cell}`, `{bay}`, `{host}`, `{io_device}`), plus any plain
  `opc-connection-*.json` / `device-*.json`;
- historian providers (`historian-provider-*.json`);
- `system-properties.patch.json`, merged into the `ignition/system-properties`
  singleton (sets the gateway scripting project);
- the OPC UA server singleton.

Resources listed in its `RETIRED` table are deleted (`DELETE
/resources/<type>/<name>/<signature>`); the single-cell device `IO01` is one.
It is idempotent; `--dry-run` shows what it would do.

### OPC UA client connection (to the cell controller)

`gateway-config/opc-connection.template.json` (one connection per cell, named
like the cell): type `com.inductiveautomation.OpcUaServerType`, endpoint
`opc.tcp://plc-c03:4840/ignition-lab/`, security `None`/`None`,
`authenticationType: ANONYMOUS`, `hostOverride: plc-c03`. The asyncua server
advertises `0.0.0.0` in its endpoints, and the override replaces it.

**Pitfall**: even with security None, the connection needs
`security.keyStoreAliasPassword`. Without it the connection faults with
*"Unable to retrieve KeyPair for alias 'client'. Incorrect password?"*. The
value is Ignition's default `password` as an embedded secret, so the apply
script encrypts it through `/encryption/encrypt` at apply time and no
ciphertext sits in git.

Item paths: Ignition 8.3.10 accepts the namespace-URI form
`nsu=urn:ignition-lab:cell;s=C01.Status.Heartbeat` (verified, same value as
`ns=2;s=…`). Prefer it: it survives a change of namespace order on the server.

### Modbus TCP device

`gateway-config/device.template.json` (one device per cell, `C03_IO01`). **Pitfall**: give every settings group
(`connectivity`, `requestOptimization`, `writeRequests`, `readRequests`,
`advanced`, `stringHandling`). Leaving one out gives HTTP 500
`NullPointerException … requestOptimization is null`: schema defaults are not
applied to missing groups.

The devices keep Ignition's default **one-based** addressing
(`advanced.zeroBasedAddressing: false`): `C1` is coil 0 on the wire and `HRUS1`
is holding register 0. That matches the `ignition_modbus_address` column of the
registry. 32-bit values (`IRUI12`) read high word first with
`reverseWordOrder: false`, the default. This is verified on
`UT01.Status.EnergyTotal`.

Ignition Modbus item syntax, under `ns=1;s=[<device>]`. Verified here: `C1`,
`DI4`, `HRUS1`, `IRUS14`, `IRUI12`. The other type suffixes come from the
Ignition Modbus driver documentation:

| Table | Address examples |
|---|---|
| Coils (FC1/5/15) | `C0` |
| Discrete inputs (FC2) | `DI0` |
| Holding registers (FC3/6/16) | `HR0` (Int16), `HRUS0` (UInt16), `HRF0` (Float32, 2 regs), `HRI0` (Int32), `HRBCD0` |
| Input registers (FC4) | `IR0`, `IRUS0`, `IRF0`, `IRI0` |
| Bit in a register | `HR0.3` |

### OPC UA server (lab relaxation)

`gateway-config/opcua-server-config.json` is a PUT of the singleton
`com.inductiveautomation.opcua/server-config`. For PUT, fetch the current
`signature` first (`scripts/ign get /resources/singleton/<type>`): the API
uses it for optimistic locking.

Namespaces of Ignition's OPC UA server: `ns=1` devices (`[device]address`),
`ns=2` exposed tag providers (`[provider]path/to/tag`).

### Tags: UDTs and instances

`scripts/generate_tags.py` builds the plant's tags from `docs/opcua-registry.csv`
(one cell type) and `docs/cells.csv` (the instances). It writes
`gateway-config/tags/default.json` and `sim.json`, then imports them through
`POST /tags/import` (collision policy Overwrite). Tag JSON is the same format as
a Designer export or `scripts/ign tags-export`. UDT definitions go in the
`_types_` folder; parameter-bound properties are objects
`{"bindType": "parameter", "binding": "…{Param}…"}`:

```json
{"tags": [
  {"name": "_types_", "tagType": "Folder", "tags": [
    {"name": "PIC200_Cell", "tagType": "UdtType",
     "parameters": {"CellId": {"dataType": "String", "value": "C01"},
                    "OpcServer": {"dataType": "String", "value": "C01"},
                    "IoDevice": {"dataType": "String", "value": "C01_IO01"}},
     "tags": [ … {"name": "StateCurrent", "tagType": "AtomicTag", "valueSource": "opc", "dataType": "Int4",
        "opcServer": {"bindType": "parameter", "binding": "{OpcServer}"},
        "opcItemPath": {"bindType": "parameter", "binding": "nsu=urn:ignition-lab:cell;s={CellId}.Status.StateCurrent"},
        "tagGroup": "Fast", "readOnly": true, "historyEnabled": true, "historyProvider": "Historian",
        "eventScripts": [{"eventid": "valueChanged",
                          "script": "\tmes.cell.log_state(str(tagPath).rsplit(\"/\", 2)[0], currentValue)"}]} … ]}]},
  {"name": "ANN", "tagType": "Folder", "tags": [{"name": "FIN", "tagType": "Folder", "tags": [
    {"name": "C03", "tagType": "UdtInstance", "typeId": "PIC200_Cell",
     "parameters": {"CellId": {"dataType": "String", "value": "C03"}, "OpcServer": {…}, "IoDevice": {…}}} ]}]}]}
```

- Modbus members: `"opcServer": "Ignition OPC UA Server"`, item path
  `ns=1;s=[{IoDevice}]IRUI12`, `scaleMode` Linear where the registry scales.
- Data types: UInt16 → `Int4`, UInt32 → `Int8` (Ignition has no unsigned
  types), Double → `Float8`, Byte → `Int2`.
- History: `historyEnabled`, `historyProvider`, and for analog values
  `historicalDeadbandStyle: Analog` + `historicalDeadband`.
- Tag event scripts: `eventScripts` with the body of
  `valueChanged(tag, tagPath, previousValue, currentValue, initialChange, missedEvents)`,
  tab-indented. They run in gateway scope and reach project library scripts
  only through the **gateway scripting project** (`gatewayScriptingProject` in
  `ignition/system-properties`, set by `system-properties.patch.json`).
- Expression member ticking every second: `"valueSource": "expr", "expression": "now(1000)"`.
- On disk (8.3), definitions land in
  `core/ignition/tag-type-definition/<provider>/udts.json` and instances in
  `core/ignition/tag-definition/<provider>/<folder>/udts.json`.
- There is **no REST route to delete tags**. Removing a member from the CSV
  does not delete it in Ignition: delete it in the Designer, or edit/remove the
  files under `tag-type-definition/` / `tag-definition/` and run `scripts/ign scan config`.
- Manual import: `scripts/ign tags-import file.json default --policy Overwrite|MergeOverwrite|Ignore|Abort`.

**Tag providers** are REST resources (`ignition/tag-provider`). The generator
creates `sim` with the same config as `default`. **Tag groups** have no REST
route. They are plain resources under
`core/ignition/tag-group/<provider>/<group>/config.json`
(`{"config": {"mode": "Direct", "rate": 250, …}}`). The generator writes them,
then runs `scan config`.

### SQL Historian

`gateway-config/historian-provider-historian.json`: resource type
`com.inductiveautomation.historian/historian-provider`, profile `SqlHistorian`,
`settings.database` = the DB connection `historian`, monthly partitions,
pruning after 6 months. The connection sets `connectionProps:
currentSchema=historian`, so the historian creates its `sqlth_*` tables and
`sqlt_data_<drv>_<yyyy>_<mm>` partitions in schema `historian`, apart from the
MES tables. Other 8.3 historian types (same resource): `CoreHistorian` (built-in
QuestDB-based store, the 8.3 default recommendation), `InternalHistorian`,
`RemoteHistorian`, `HistorySplitter`, `CsvHistorian`, `WideDbHistorian`.

### Reading values from outside (verification)

There is no REST route for tag values. Read them through the OPC UA server.
`scripts/opc` does this from the workspace container:

```bash
scripts/opc read 'ns=1;s=[C03_IO01]IRUS14' 'ns=2;s=[default]/ANN/FIN/C03/Status/StateCurrentName'
scripts/opc browse 'ns=2;s=[default]/ANN/FIN/C03/RB01' --depth 2
scripts/opc watch 'ns=2;s=[default]/ANN/FIN/C03/Order/Active/GoodCount' --period 0.5
OPCUA_URL=opc.tcp://plc-c03:4840/ignition-lab/ scripts/opc read 'ns=2;s=C03.Status.StateCurrent'   # the controller itself
```

Exposed tag node ids, as browsed, are `ns=2;s=[provider]/path/to/tag`.
`[provider]path` without the slash also resolves. In Python (asyncua):

```python
from asyncua import Client
async with Client("opc.tcp://gateway:62541") as c:
    await c.get_node("ns=1;s=[C03_IO01]IRUI12").read_value()                   # raw device value (Wh)
    await c.get_node("ns=2;s=[default]/ANN/FIN/C03/UT01/Status/EnergyTotal").read_value()  # tag, kWh
```

Writing through Ignition's server needs an authenticated user. The lab tests
use Ignition's default OPC UA user `opcuauser` / `password`. Tags marked
`readOnly` refuse writes with `BadUserAccessDenied`:

```python
c = Client("opc.tcp://gateway:62541"); c.set_user("opcuauser"); c.set_password("password")
```

## Projects (Perspective, scripts)

Projects live in `ignition/data/projects/<project>/`. Create one with
`POST /projects` (`{"name", "title", "description", "defaultDb", "tagProvider"}`;
`scripts/ign post /projects -` reads the body from stdin). Each resource is a
folder with `resource.json` plus content files. After editing files, run
`scripts/ign scan projects`; a script library change restarts the project's
gateway scripts within a second. Verified on 8.3.10 in project `plant`:

| Resource | Path under the project | Content | Writable as code |
|---|---|---|---|
| Script library module `mes.cell` | `ignition/script-python/mes/cell/code.py` | Jython 2.7 source; `resource.json` lists `code.py` | yes |
| Named query `Cell/LastParts` | `ignition/named-query/Cell/LastParts/query.sql` | SQL with `:param`; `resource.json` attributes hold `database`, `type: Query`, `parameters` (`sqlType` 7 = String) | yes |
| Perspective view `Cell/Detail` | `com.inductiveautomation.perspective/views/Cell/Detail/view.json` | component tree, `params`, `custom`, `propConfig` (bindings) | yes |
| Perspective pages and docks | `com.inductiveautomation.perspective/page-config/config.json` | `pages` (`/cell/:cell` → view param `cell`), `sharedDocks` | yes |
| Project properties | `ignition/global-props/data.bin` | gzip'ed binary serialisation | no: set them through `POST /projects` or the Designer |
| Gateway event scripts (timer, startup, tag change) | `ignition/event-scripts/data.bin` (8.1 layout; not tried on 8.3) | binary, like `global-props` | not attempted: this lab uses tag event scripts in the UDT instead (docs/system/mes.md) |

Binding JSON used in the views (see docs/system/hmi.md):

```json
"propConfig": {
  "custom.state": {"binding": {"type": "tag", "config": {"mode": "indirect",
      "tagPath": "[default]ANN/FIN/{cell}/Status/StateCurrent", "references": {"cell": "{view.params.cell}"},
      "fallbackDelay": 2.5}}},
  "props.text": {"binding": {"type": "expr", "config": {"expression": "{view.custom.stateName}"}}},
  "props.data": {"binding": {"type": "query", "config": {"queryPath": "Cell/LastParts", "returnFormat": "json",
      "parameters": {"cell": "{view.params.cell}"}, "polling": {"enabled": true, "rate": "3"}}}}
}
```

Tag bindings that write back (toggles, numeric fields) add `"bidirectional": true`.
Project scripts and tag event scripts run on Jython 2.7: Python 2 syntax, Java
classes importable, no CPython packages.

## What still works when the trial expires

Verified 2026-11-21 with the standard edition in demo-expired state: OPC UA
client connections, tag event scripts, project library scripts and database
access keep running. The Modbus driver (`Bad_TrialExpired`), the SQL Historian
("Demo_Expired"), Perspective sessions and Ignition's own OPC UA server stop.
Configuration (REST API, file scans, tag import) works in both states. The lab
now runs Maker Edition, so this applies only if it goes back to the standard
edition. The edition (`IGNITION_EDITION`) is read only at commissioning, and
there is no REST route to change it: switching means a fresh data dir
(operations.md, "Switching edition").
