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

## Simulated cell controller (`plc/`)

- One process: an asyncua OPC UA server on :4840 (address space generated from
  `docs/opcua-registry.csv`) plus a stdlib Modbus TCP server on :502 (device
  IO01), with `programs/cell.py` scanned every 100 ms. Layout is in
  docs/system/architecture.md.
- `docs/opcua-registry.csv` is the **single source of truth**: the program
  addresses signals by name (`tags["C01.Status.StateCurrent"]`), so unknown
  names raise. A new signal goes into the CSV first, then the code, then
  `scripts/generate_tags.py`. Keep scenario.md, opcua-registry.md and
  fault-catalogue.md consistent with the CSV. The tables in opcua-registry.md
  are maintained by hand.
- Behaviour is specified in docs/scenario.md, with section numbers cited in
  code comments. Phase 2 (faults) is reserved in docs/fault-catalogue.md.
- After editing: `docker compose restart plc`, then
  `docker compose exec workspace python scripts/cell_smoke_test.py`. It must PASS.

## Git

Commit only when the user asks. `.gitignore` keeps only `ignition/data/config/resources/core`
and `ignition/data/projects` from the gateway data dir.
