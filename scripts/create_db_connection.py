#!/usr/bin/env python3
"""Create the gateway DB connection "mes" to the compose PostgreSQL (idempotent).

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

NAME = "mes"
TYPE = "ignition/database-connection"


def main() -> None:
    env = ign.ENV
    names = [i["name"] for i in ign.call("GET", f"/resources/names/{TYPE}")["items"]]
    exists = NAME in names
    if exists and "--replace" not in sys.argv:
        print(f"database connection {NAME!r} already exists (use --replace to rewrite it)")
        return
    secret = ign.call("POST", "/encryption/encrypt", env["POSTGRES_PASSWORD"].encode(), raw=True, ctype="text/plain")
    item = {"name": NAME, "enabled": True, "config": {
        "driver": "PostgreSQL", "translator": "POSTGRES",
        "connectURL": f"jdbc:postgresql://db:5432/{env.get('POSTGRES_DB', 'mes')}",
        "username": env.get("POSTGRES_USER", "ignition"),
        "password": {"type": "Embedded", "data": json.loads(secret)},
        "validationQuery": "SELECT 1"}}
    if exists:
        item["signature"] = ign.call("GET", f"/resources/find/{TYPE}/{NAME}")["signature"]
        ign.show(ign.call("PUT", f"/resources/{TYPE}", [item]))
    else:
        ign.show(ign.call("POST", f"/resources/{TYPE}", [item]))


if __name__ == "__main__":
    main()
