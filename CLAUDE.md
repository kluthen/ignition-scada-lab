# Ignition lab: instructions for Claude Code

Research lab for learning Ignition 8.3 (see README.md). Not an ATD project: no
intent or data registers. The user is an automation engineer coming from Codra
Panorama E2. Relate Ignition concepts to Panorama when it helps
(docs/system/panorama-e2-to-ignition.md).

## Keep the documentation whole

Every change to the stack, the gateway config, the PLC simulator or the plant
model updates the matching document in the same task:
`docs/system/*.md` for the system, `docs/*.md` for the plant and MES, and
`docs/system/status.md` for progress and open decisions. Documentation of the
system as a whole is an explicit requirement of the user.

## Stack

- `compose.yaml` services: `gateway` (Ignition 8.3.10), `db` (PostgreSQL 19),
  `plc` (Python simulator), `gateway-init` (seeds `ignition/data`), `workspace`
  (devcontainer, profile `dev`). Host ports are on 127.0.0.1: 8088, 62541, 5432, 5020.
- Secrets and versions live in `.env` (git-ignored). Never print passwords or
  the API token in docs or commit messages.

## Driving the gateway

- Use `scripts/ign` (REST API, token from `.env`). Look routes up with
  `scripts/ign routes REGEX` and body schemas with `scripts/ign schema ROUTE --depth N`.
  Don't guess field names.
- Prefer the REST API (validated, applied live) to editing files under
  `ignition/data/config/resources/`. If you do edit files, run
  `scripts/ign scan config` (or `projects`). For API tokens and security levels,
  restart the gateway.
- Never touch `ignition/data/config/resources/.resources/` (gateway cache).
- Keep reproducible request bodies in `gateway-config/*.json`.
- Known pitfalls are listed in docs/system/gateway-automation.md (e.g. Modbus
  device bodies need every settings group).

## Ignition specifics

- Project scripts run on **Jython 2.7**: Python 2 syntax (`print x` works, no
  f-strings, no type hints), Java classes importable, `system.*` API.
- Perspective views are `view.json` under `ignition/data/projects/<project>/com.inductiveautomation.perspective/views/…`.
- Tags: `[provider]Folder/Tag`. Device items in Ignition's OPC UA server are
  `ns=1;s=[device]ADDR`, exposed tags `ns=2;s=[provider]path`.
- Verify values through the OPC UA server with `scripts/opc read|browse|watch`
  (runs asyncua in the workspace container). The REST API has no tag-value route.

## PLC simulator

- `plc/` (stdlib Python 3.13): `modbus_server.py` (Modbus TCP, FC 1–6, 15, 16),
  `io_image.py` (the four tables), `programs/<name>.py` (class `Program` with
  `scan(dt)`), `main.py` (scan loop). Select the program with `PLC_PROGRAM`.
- Signals must match `docs/opcua-registry.csv`, the single source of truth for
  the plant's signals.
- After editing: `docker compose restart plc && docker compose logs --tail 20 plc`.

## Git

Commit only when the user asks. `.gitignore` keeps only `ignition/data/config/resources/core`
and `ignition/data/projects` from the gateway data dir.
