#!/usr/bin/env python3
"""Create the gateway DB connections to the compose PostgreSQL (idempotent).

  mes        default schema search path; MES queries name their schema (mes.work_order)
  historian  currentSchema=historian, so the SQL Historian creates its sqlth_* tables there

The password comes from .env (POSTGRES_PASSWORD). The gateway encrypts it with
its own key (POST /encryption/encrypt), so no secret is stored in git.
Usage: scripts/create_db_connection.py [--replace]
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ign  # noqa: E402  (same folder)

CONNECTIONS = {"mes": "", "historian": "currentSchema=historian"}   # name -> JDBC connection properties
TYPE = "ignition/database-connection"


def main() -> None:
    env = ign.ENV
    names = [i["name"] for i in ign.call("GET", f"/resources/names/{TYPE}")["items"]]
    for name, props in CONNECTIONS.items():
        exists = name in names
        if exists and "--replace" not in sys.argv:
            print(f"database connection {name!r} already exists (use --replace to rewrite it)")
            continue
        secret = ign.call("POST", "/encryption/encrypt", env["POSTGRES_PASSWORD"].encode(), raw=True,
                          ctype="text/plain")
        item = {"name": name, "enabled": True, "config": {
            "driver": "PostgreSQL", "translator": "POSTGRES",
            "connectURL": f"jdbc:postgresql://db:5432/{env.get('POSTGRES_DB', 'mes')}",
            "username": env.get("POSTGRES_USER", "ignition"),
            "password": {"type": "Embedded", "data": json.loads(secret)},
            "connectionProps": props,
            "validationQuery": "SELECT 1"}}
        if exists:
            item["signature"] = ign.call("GET", f"/resources/find/{TYPE}/{name}")["signature"]
        r = ign.call("PUT" if exists else "POST", f"/resources/{TYPE}", [item])
        print(f"{'PUT' if exists else 'POST'} {name}: {'ok' if r.get('success') else r}")


if __name__ == "__main__":
    main()
