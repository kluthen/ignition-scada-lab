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
scripts/ign find  com.inductiveautomation.opcua/device plc_modbus
scripts/ign post  resources/com.inductiveautomation.opcua/device gateway-config/device-plc-modbus.json
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

### Modbus TCP device

`gateway-config/device-plc-modbus.json`. **Pitfall**: give every settings group
(`connectivity`, `requestOptimization`, `writeRequests`, `readRequests`,
`advanced`, `stringHandling`). Leaving one out gives HTTP 500
`NullPointerException … requestOptimization is null`: schema defaults are not
applied to missing groups.

`advanced.zeroBasedAddressing: true` makes Ignition addresses equal the Modbus
PDU addresses (`HR0` = first holding register), as documented in the
registers maps.

Ignition Modbus item syntax, under `ns=1;s=[<device>]`. Verified here: `C0`,
`DI0`, `HR1`, `IR4`, `IRUS0`. The other type suffixes come from the Ignition
Modbus driver documentation:

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

Tag JSON, as produced by Designer export or `scripts/ign tags-export`:

```json
{"tags": [{"name": "Cell", "tagType": "Folder", "tags": [
  {"name": "TankLevel", "tagType": "AtomicTag", "valueSource": "opc",
   "opcServer": "Ignition OPC UA Server", "opcItemPath": "ns=1;s=[plc_modbus]IRUS0",
   "dataType": "Float4", "engUnit": "%",
   "scaleMode": "Linear", "rawLow": 0, "rawHigh": 1000, "scaledLow": 0, "scaledHigh": 100}]}]}
```

Import with `scripts/ign tags-import file.json default --policy Overwrite|MergeOverwrite|Ignore|Abort`.

### Reading values from outside (verification)

There is no REST route for tag values. Read them through the OPC UA server.
`scripts/opc` does this from the workspace container:

```bash
scripts/opc read 'ns=1;s=[plc_modbus]IRUS0' 'ns=2;s=[default]/_probe/TankLevel'
scripts/opc browse 'ns=2;s=Tag Providers' --depth 3
scripts/opc watch 'ns=2;s=[default]/_probe/TankLevel' --period 0.5
```

Exposed tag node ids, as browsed, are `ns=2;s=[provider]/path/to/tag`.
`[provider]path` without the slash also resolves. In Python (asyncua):

```python
from asyncua import Client
async with Client("opc.tcp://gateway:62541") as c:
    await c.get_node("ns=1;s=[plc_modbus]IRUS0").read_value()    # raw device value
    await c.get_node("ns=2;s=[default]/Cell/TankLevel").read_value()  # tag value, scaled
```

## Projects (Perspective, scripts)

Projects live in `ignition/data/projects/<project>/`. Each resource
(Perspective view, script module, named query…) is a folder with
`resource.json` plus content files: `view.json` for views, `code.py` for
scripts. After editing files, run `scripts/ign scan projects`. Project scripts
run on Jython 2.7: Python 2 syntax, Java classes importable, no CPython packages.
