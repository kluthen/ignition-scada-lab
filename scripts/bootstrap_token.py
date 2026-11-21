#!/usr/bin/env python3
"""Create the lab API token as gateway config files (idempotent).

Writes, under ignition/data/config/resources/core/ignition/:
  security-levels       adds Authenticated/ApiAutomation
  security-properties   grants it gateway read + write (AnyOf)
  api-token/<name>      basic-token whose hash matches a fresh random key
and stores IGNITION_API_TOKEN=<name>:<key> in .env.

API tokens cannot hold Authenticated/Roles/* levels, hence the custom level.
Restart the gateway afterwards: docker compose restart gateway

Usage: scripts/bootstrap_token.py [--name claude-lab] [--force]
  --force   replace an existing token (new key)
"""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import pathlib
import secrets
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORE = ROOT / "ignition/data/config/resources/core/ignition"
LEVEL = "ApiAutomation"
GRANT = {"name": "Authenticated", "children": [{"name": LEVEL, "children": []}]}


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def load(p: pathlib.Path) -> dict:
    return json.loads(p.read_text())


def save(p: pathlib.Path, obj: dict) -> None:
    p.write_text(json.dumps(obj, indent=2) + "\n")


def resource_json(path: pathlib.Path) -> None:
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    save(path, {"scope": "A", "version": 1, "restricted": False, "overridable": True,
                "files": ["config.json"],
                "attributes": {"lastModification": {"actor": "bootstrap_token", "timestamp": ts}}})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="claude-lab")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if not (CORE / "security-levels/config.json").exists():
        sys.exit("gateway data not initialised yet: start the stack once (docker compose up -d)")

    p = CORE / "security-levels/config.json"
    c = load(p)
    auth = next(lv for lv in c["securityLevels"] if lv["name"] == "Authenticated")
    if not any(ch["name"] == LEVEL for ch in auth["children"]):
        auth["children"].append({"name": LEVEL, "children": [],
                                 "description": "Lab: granted to API tokens used by scripts/Claude Code (gateway read/write)."})
        save(p, c)
        print("added security level Authenticated/" + LEVEL)

    p = CORE / "security-properties/config.json"
    c = load(p)
    changed = False
    for k in ("readPermissions", "writePermissions"):
        if c[k]["type"] != "AnyOf":
            sys.exit(f"{k} is {c[k]['type']}, expected AnyOf: adding a level would not widen access")
        if GRANT not in c[k]["securityLevels"]:
            c[k]["securityLevels"].append(GRANT)
            changed = True
    if changed:
        save(p, c)
        print("granted gateway read/write to Authenticated/" + LEVEL)

    d = CORE / "api-token" / a.name
    env = ROOT / ".env"
    env_lines = env.read_text().splitlines() if env.exists() else []
    has_env = any(line.startswith("IGNITION_API_TOKEN=") for line in env_lines)
    if (d / "config.json").exists() and has_env and not a.force:
        print(f"token {a.name} already exists (use --force to rotate)")
        return
    key = secrets.token_bytes(32)
    d.mkdir(parents=True, exist_ok=True)
    save(d / "config.json", {
        "profile": {"type": "basic-token", "secureChannelRequired": False, "securityLevels": [GRANT],
                    "timestamp": int(datetime.datetime.now().timestamp() * 1000)},
        "settings": {"tokenHash": b64(hashlib.sha256(key).digest())}})
    resource_json(d / "resource.json")
    env_lines = [line for line in env_lines if not line.startswith("IGNITION_API_TOKEN=")]
    env_lines.append(f"IGNITION_API_TOKEN={a.name}:{b64(key)}")
    env.write_text("\n".join(env_lines) + "\n")
    print(f"token {a.name} written; IGNITION_API_TOKEN stored in .env. Now: docker compose restart gateway")


if __name__ == "__main__":
    main()
