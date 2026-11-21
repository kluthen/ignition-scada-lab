#!/usr/bin/env python3
"""Apply db/init/*.sql to the running database and load the cell master data (idempotent).

PostgreSQL runs db/init only when the pgdata volume is created. This script
replays the same files on an existing database (they are written to be
re-runnable), then upserts mes.cell from docs/cells.csv, the single source of
the cell instances. Runs psql inside the db container.

Usage: scripts/db_apply.py
"""

from __future__ import annotations

import csv
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ign  # noqa: E402  (ROOT, ENV)


def quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def cells_sql() -> str:
    rows = []
    with open(ign.ROOT / "docs/cells.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            types = ",".join(r["qualified_part_types"].split())
            rows.append(f"({quote(r['cell'])}, {quote(r['bay'])}, '{{{types}}}', {quote(r['notes'])})")
    return ("INSERT INTO mes.cell (cell, bay, qualified_part_types, notes) VALUES\n  " + ",\n  ".join(rows) +
            "\nON CONFLICT (cell) DO UPDATE SET bay = EXCLUDED.bay, "
            "qualified_part_types = EXCLUDED.qualified_part_types, notes = EXCLUDED.notes;\n")


def main() -> None:
    sql = "".join(p.read_text() for p in sorted((ign.ROOT / "db/init").glob("*.sql"))) + cells_sql()
    env = ign.ENV
    cmd = ["docker", "compose", "exec", "-T", "-e", "PGOPTIONS=-c client_min_messages=warning", "db",
           "psql", "-q", "-v", "ON_ERROR_STOP=1",
           "-U", env.get("POSTGRES_USER", "ignition"), "-d", env.get("POSTGRES_DB", "mes")]
    subprocess.run(cmd, input=sql.encode(), cwd=ign.ROOT, check=True)
    print("database schema applied, mes.cell loaded from docs/cells.csv")


if __name__ == "__main__":
    main()
