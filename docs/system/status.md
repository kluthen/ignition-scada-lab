# Lab status

Last updated: 2026-11-21.

## Done

**Phase 0: environment and plumbing (verified)**

- [x] Compose stack / devcontainer: Ignition 8.3.10 (standard, trial),
      PostgreSQL 19, PLC simulator, workspace shell (uid-mapped, asyncua,
      pymodbus, psql).
- [x] Gateway commissioned from `.env` (EULA, admin user, edition; quick-start skipped).
- [x] `ignition/data` bind-mounted and owned by the host user, seeded by `gateway-init`.
- [x] REST API token `claude-lab` (custom security level `Authenticated/ApiAutomation`),
      `scripts/bootstrap_token.py` to recreate it, `scripts/ign` CLI, OpenAPI spec saved.
- [x] DB connection `mes` → `db:5432/mes`, healthy. Password stored as a gateway-encrypted secret.
- [x] Modbus TCP device `plc_modbus` → `plc:502`, healthy, zero-based addressing.
- [x] Ignition OPC UA server opened for lab verification (anonymous read, exposed tags), `scripts/opc`.
- [x] Probe tags `[default]_probe/TankLevel` (scaled) and `Heartbeat` read end-to-end
      PLC → Modbus → device → tag → OPC UA client.
- [x] System documentation: architecture, operations, gateway automation, Panorama E2 concept map.

## In progress

- [ ] Plant scenario (robot cell), OPC UA registry, fault catalogue, MES
      customer requirements, written by a design agent in `docs/`.

## Next (recommended order)

1. Implement the phase-1 simulator from `docs/opcua-registry.csv` (replace the `tank` placeholder).
2. Generate Ignition tags (UDTs per equipment type) from the registry, then delete `_probe`.
3. First Perspective project: cell overview screen, equipment faceplates.
4. Alarms on the registry's alarm signals, alarm journal in `mes`.
5. Tag history to PostgreSQL (SQL Historian), trends.
6. MES MVP: orders, counting, downtime, OEE (see `docs/mes-requirements.md`).
7. Fault injection (fault catalogue), one fault at a time.

## Open decisions

- Licence path: the lab runs the standard edition in trial mode (full features,
  2 h resets). Maker Edition stays an option for purely personal tests; switching
  requires re-commissioning (docs/system/operations.md).
- Nothing is committed to git yet. The repo is initialised and `.gitignore` is ready.
