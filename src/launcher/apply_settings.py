#!/usr/bin/env python3
"""Runs INSIDE the sandbox just before the editor starts, and writes the editor's settings.json.

  * initial-settings.json: starting choices (like the theme), used only where you haven't chosen yourself.
  * your own settings: kept as they are.
  * default-settings.json: locked privacy settings, always win.

It runs inside the sandbox on purpose (security review finding #1). If sandboxed code replaced settings.json with a
link, the link can only point at files the sandbox can already see, never at your real home folder.
Standard library only.
"""
import json
import os
import sys
import tempfile
import time

LOCKED = "/run/linux-studio/locked-settings.json"
INITIAL = "/run/linux-studio/initial-settings.json"
SETTINGS = "/home/user/.config/linux-studio/User/settings.json"


def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("//")}


def main():
    locked, initial = load(LOCKED), load(INITIAL)
    folder = os.path.dirname(SETTINGS)
    os.makedirs(folder, exist_ok=True)
    user = {}
    if os.path.islink(SETTINGS):
        os.unlink(SETTINGS)                       # never follow a planted link
    elif os.path.exists(SETTINGS):
        try:
            with open(SETTINGS, encoding="utf-8") as f:
                user = json.load(f)
            if not isinstance(user, dict):
                raise ValueError("not an object")
        except (OSError, ValueError):
            backup = f"{SETTINGS}.bak-{time.strftime('%Y%m%d%H%M%S')}"
            os.replace(SETTINGS, backup)
            print(f"linux-studio: settings.json had comments or errors; saved it as {backup} and started fresh",
                  file=sys.stderr)
            user = {}
    merged = {**initial, **user, **locked}
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".settings.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, SETTINGS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
