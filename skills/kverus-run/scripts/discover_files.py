#!/usr/bin/env python3
"""Directory walker for the kverus-run pipeline (pinned machine asset).

Usage: python3 discover_files.py <target>

Discovers the pipeline's per-file work list from the invocation target:
- target is an existing file        -> mode "file",      files=[target]
- target is an existing directory   -> mode "directory", files=sorted *.rs walk
- anything else                     -> mode "missing",   files=[]

Prints exactly one line of sorted-key JSON on stdout and exits 0, so the
calling spec's machine step can parse_json it. Any internal failure also
prints a "missing" payload with rc 0 — discovery never crashes the caller;
the spec's mode gate routes "missing" to the honest-stop exit.

Paths are emitted exactly as given (workspace-relative in, workspace-relative
out). Comma characters in paths are not escaped; the calling spec treats the
file list as a typed line list, not a CSV, so this is safe.
"""
import json
import os
import sys


def discover(target: str):
    if os.path.isfile(target):
        return {"mode": "file", "files": [target], "original": target}
    if os.path.isdir(target):
        found = []
        for root, dirs, names in os.walk(target):
            dirs.sort()
            for name in sorted(names):
                if name.endswith(".rs"):
                    found.append(os.path.join(root, name))
        found.sort()
        return {"mode": "directory", "files": found, "original": target}
    return {"mode": "missing", "files": [], "original": target}


def main(argv):
    target = argv[1] if len(argv) > 1 else ""
    try:
        payload = discover(target)
    except Exception as exc:  # never crash the caller: report missing honestly
        payload = {
            "mode": "missing",
            "files": [],
            "original": target,
            "error": str(exc),
        }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
