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
signature, every OPC connection (`opc-connection-*.json`) and device
(`device-*.json`) in `gateway-config/`, then the OPC UA server singleton. It is
idempotent; `--dry-run` shows what it would do.

### OPC UA client connection (to the cell controller)

`gateway-config/opc-connection-c01.json`: type `com.inductiveautomation.OpcUaServerType`,
endpoint `opc.tcp://plc:4840/ignition-lab/`, security `None`/`None`,
`authenticationType: ANONYMOUS`, `hostOverride: plc`. The asyncua server
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

`gateway-config/device-io01.json`. **Pitfall**: give every settings group
(`connectivity`, `requestOptimization`, `writeRequests`, `readRequests`,
`advanced`, `stringHandling`). Leaving one out gives HTTP 500
`NullPointerException … requestOptimization is null`: schema defaults are not
applied to missing groups.

`IO01` keeps Ignition's default **one-based** addressing
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

### Tags

`scripts/generate_tags.py` builds the plant's tags from `docs/opcua-registry.csv`.
It writes `gateway-config/tags/default.json` and `sim.json`, then imports them
(collision policy Overwrite). Tag JSON is the same format as a Designer export
or `scripts/ign tags-export`:

```json
{"tags": [{"name": "ANN", "tagType": "Folder", "tags": [ … {"name": "EnergyTotal", "tagType": "AtomicTag",
   "valueSource": "opc", "opcServer": "Ignition OPC UA Server", "opcItemPath": "ns=1;s=[IO01]IRUI12",
   "dataType": "Float8", "tagGroup": "Modbus", "engUnit": "kWh", "readOnly": true,
   "scaleMode": "Linear", "rawLow": 0, "rawHigh": 1000, "scaledLow": 0, "scaledHigh": 1.0,
   "documentation": "Energy counter since controller start …"} … ]}]}
```

- OPC UA tags use `"opcServer": "C01"` (the connection name) and the `nsu=` item path.
- Data types: UInt16 → `Int4`, UInt32 → `Int8` (Ignition has no unsigned
  types), Double → `Float8`, Byte → `Int2`.
- Removing a row from the CSV does not delete the tag in Ignition. Delete it
  in the Designer, or remove its folder under `tag-definition/` and run a config scan.
- Manual import: `scripts/ign tags-import file.json default --policy Overwrite|MergeOverwrite|Ignore|Abort`.

**Tag providers** are REST resources (`ignition/tag-provider`). The generator
creates `sim` with the same config as `default`. **Tag groups** have no REST
route. They are plain resources under
`core/ignition/tag-group/<provider>/<group>/config.json`
(`{"config": {"mode": "Direct", "rate": 250, …}}`). The generator writes them,
then runs `scan config`.

### Reading values from outside (verification)

There is no REST route for tag values. Read them through the OPC UA server.
`scripts/opc` does this from the workspace container:

```bash
scripts/opc read 'ns=1;s=[IO01]IRUS14' 'ns=2;s=[default]/ANN/FIN/C01/Status/StateCurrentName'
scripts/opc browse 'ns=2;s=[default]/ANN/FIN/C01/RB01' --depth 2
scripts/opc watch 'ns=2;s=[default]/ANN/FIN/C01/Order/Active/GoodCount' --period 0.5
OPCUA_URL=opc.tcp://plc:4840/ignition-lab/ scripts/opc browse   # the controller itself (inside workspace)
```

Exposed tag node ids, as browsed, are `ns=2;s=[provider]/path/to/tag`.
`[provider]path` without the slash also resolves. In Python (asyncua):

```python
from asyncua import Client
async with Client("opc.tcp://gateway:62541") as c:
    await c.get_node("ns=1;s=[IO01]IRUI12").read_value()                       # raw device value (Wh)
    await c.get_node("ns=2;s=[default]/ANN/FIN/C01/UT01/Status/EnergyTotal").read_value()  # tag, kWh
```

Writing through Ignition's server needs an authenticated user. The lab tests
use Ignition's default OPC UA user `opcuauser` / `password`. Tags marked
`readOnly` refuse writes with `BadUserAccessDenied`:

```python
c = Client("opc.tcp://gateway:62541"); c.set_user("opcuauser"); c.set_password("password")
```

## Projects (Perspective, scripts)

Projects live in `ignition/data/projects/<project>/`. Each resource
(Perspective view, script module, named query…) is a folder with
`resource.json` plus content files: `view.json` for views, `code.py` for
scripts. After editing files, run `scripts/ign scan projects`. Project scripts
run on Jython 2.7: Python 2 syntax, Java classes importable, no CPython packages.
