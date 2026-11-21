#!/usr/bin/env python3
"""ign: small CLI for the Ignition 8.3 gateway REST API (stdlib only).

Reads IGNITION_URL (default http://127.0.0.1:8088) and IGNITION_API_TOKEN
from the environment or from the repo's .env file.

  ign info                              gateway name, version, edition, trial/licence
  ign routes [REGEX]                    list REST routes from the saved OpenAPI spec
  ign schema ROUTE [METHOD] [--depth N] request body schema of a route (default POST)
  ign get PATH                          GET any path (prefix /data/api/v1 is optional)
  ign post|put PATH [FILE|-]            send JSON body from FILE or stdin
  ign delete PATH
  ign names TYPE                        resource names, TYPE like ignition/database-connection
  ign find TYPE NAME                    one resource (config + signature)
  ign scan [config|projects|both]       ask the gateway to rescan files on disk
  ign tags-export [PROVIDER] [PATH]     tag export as JSON (default provider "default")
  ign tags-import FILE [PROVIDER] [--policy Overwrite|MergeOverwrite|Ignore|Abort]
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs/system/reference/gateway-openapi-8.3.10.json"
API = "/data/api/v1"


def load_env() -> dict[str, str]:
    env = {}
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith("IGNITION_")})
    return env


ENV = load_env()
BASE = ENV.get("IGNITION_URL", "http://127.0.0.1:8088").rstrip("/")


def url(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    if not path.startswith(("/data/", "/openapi", "/StatusPing", "/system/")):
        path = API + path
    return BASE + path


def call(method: str, path: str, body=None, raw: bool = False, ctype: str | None = None):
    data = None
    headers = {"Accept": "application/json"}
    token = ENV.get("IGNITION_API_TOKEN")
    if token:
        headers["X-Ignition-API-Token"] = token
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        headers["Content-Type"] = ctype or "application/json"
    req = urllib.request.Request(url(path), data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = r.read()
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")
        m = re.search(r"<td>([^<]*)</td>\s*</tr>\s*</table>", msg)
        sys.exit(f"HTTP {e.code} {method} {path}: {m.group(1) if m else msg[:2000]}")
    if raw:
        return payload
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return payload.decode("utf-8", "replace")


def show(obj) -> None:
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    elif obj is not None:
        print(obj)


def read_body(arg: str | None):
    if arg in (None, "-"):
        return json.load(sys.stdin)
    return json.loads(pathlib.Path(arg).read_text())


def spec() -> dict:
    if not SPEC.exists():
        SPEC.parent.mkdir(parents=True, exist_ok=True)
        SPEC.write_bytes(call("GET", "/openapi.json", raw=True))
    return json.loads(SPEC.read_text())


def resolve(s, comp, depth, seen=()):
    if depth <= 0:
        return "..."
    if isinstance(s, dict):
        if "$ref" in s:
            n = s["$ref"].split("/")[-1]
            if n in seen:
                return f"<recursive {n}>"
            return resolve(comp.get(n, {}), comp, depth, seen + (n,))
        return {k: resolve(v, comp, depth - 1, seen) for k, v in s.items() if k not in ("example", "examples")}
    if isinstance(s, list):
        return [resolve(x, comp, depth - 1, seen) for x in s]
    return s


def main(argv: list[str]) -> None:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd, args = argv[0], argv[1:]
    if cmd == "info":
        show(call("GET", "/gateway-info"))
    elif cmd == "routes":
        rx = re.compile(args[0] if args else ".")
        for p, ops in sorted(spec()["paths"].items()):
            if rx.search(p):
                print(",".join(m.upper() for m in ops if m in ("get", "post", "put", "delete", "patch")).ljust(18), p)
    elif cmd == "schema":
        depth = 8
        if "--depth" in args:
            i = args.index("--depth")
            depth = int(args[i + 1])
            args = args[:i] + args[i + 2:]
        route = args[0] if args[0].startswith("/data/") else API + "/" + args[0].lstrip("/")
        method = (args[1] if len(args) > 1 else "post").lower()
        d = spec()
        op = d["paths"][route][method]
        content = op.get("requestBody", {}).get("content", {})
        print(f"# {method.upper()} {route}: {op.get('summary', '')}")
        for p in op.get("parameters", []):
            print(f"#   param {p.get('in')} {p.get('name')} {'(required)' if p.get('required') else ''}")
        for ctype, c in content.items():
            print(f"# body {ctype}")
            if "schema" in c:
                show(resolve(c["schema"], d.get("components", {}).get("schemas", {}), depth))
    elif cmd in ("get", "delete"):
        show(call(cmd.upper(), args[0]))
    elif cmd in ("post", "put"):
        show(call(cmd.upper(), args[0], read_body(args[1] if len(args) > 1 else None)))
    elif cmd == "names":
        show(call("GET", f"/resources/names/{args[0]}"))
    elif cmd == "find":
        show(call("GET", f"/resources/find/{args[0]}/{urllib.parse.quote(args[1])}"))
    elif cmd == "scan":
        what = args[0] if args else "both"
        for w in (["config", "projects"] if what == "both" else [what]):
            print(f"scan {w}:", json.dumps(call("POST", f"/scan/{w}")))
    elif cmd == "tags-export":
        provider = args[0] if args else "default"
        q = {"provider": provider, "type": "json", "recursive": "true"}
        if len(args) > 1:
            q["path"] = args[1]
        show(call("GET", "/tags/export?" + urllib.parse.urlencode(q)))
    elif cmd == "tags-import":
        policy = "MergeOverwrite"
        if "--policy" in args:
            i = args.index("--policy")
            policy = args[i + 1]
            args = args[:i] + args[i + 2:]
        provider = args[1] if len(args) > 1 else "default"
        q = urllib.parse.urlencode({"provider": provider, "type": "json", "collisionPolicy": policy})
        show(call("POST", f"/tags/import?{q}", pathlib.Path(args[0]).read_bytes()))
    else:
        sys.exit(f"unknown command {cmd!r}; try: ign help")


if __name__ == "__main__":
    main(sys.argv[1:])
