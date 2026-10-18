#!/usr/bin/env python3
"""The keymap has ONE source: `config/adv360.keymap`.

    check_keymap_source.py [root]     # check the tree (default: the repo root)
    check_keymap_source.py --probe    # prove this check goes red on each defect it claims to catch

Upstream ships the layout twice, as `config/adv360.keymap` (what the firmware builds) and
`config/keymap.json` (for Kinesis's web editor). This fork customizes the `.keymap` only, so the
JSON sat byte-identical to upstream and disagreed with the board's real layout (ROADMAP P1.1). By
owner ruling (2026-10-18) the JSON is deleted; the README's recommended editor reads `.keymap`.

What holds after this check passes:
  1. `config/adv360.keymap` exists (a scan with no keymap has lost its subject).
  2. `config/keymap.json` does not. The only way it returns is an upstream merge, and whatever
     it then holds is upstream's layout, not this board's -- so its presence alone is the defect.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.environ.get("GOH_DIR", os.path.expanduser("~/Projects/gates_of_heck")))
from tui.lib import err, ok  # noqa: E402

SOURCE = "config/adv360.keymap"
SECOND = "config/keymap.json"


def problems(root):
    found = []
    if not os.path.isfile(os.path.join(root, SOURCE)):
        found.append(f"{SOURCE} is missing -- the scan lost its subject")
    if os.path.exists(os.path.join(root, SECOND)):
        found.append(f"{SECOND} is back (an upstream merge?); delete it -- {SOURCE} is the one source")
    return found


def run(root):
    found = problems(root)
    for line in found:
        err(f"keymap source: {line}")
    if not found:
        ok(f"keymap source: {SOURCE} is the only keymap")
    return 1 if found else 0


def probe():
    """Each defect in the docstring goes red alone; the clean fixture is green."""
    cases = {
        "clean": ((SOURCE,), False),
        "json back": ((SOURCE, SECOND), True),
        "empty scope": ((), True),
    }
    failed = []
    for name, (files, want_red) in cases.items():
        with tempfile.TemporaryDirectory(prefix="keymap-source-probe-") as root:
            os.makedirs(os.path.join(root, "config"))
            for rel in files:
                with open(os.path.join(root, rel), "w", encoding="utf-8") as handle:
                    handle.write("x\n")
            red = bool(problems(root))
        if red != want_red:
            failed.append(f"{name}: expected {'red' if want_red else 'green'}, got {'red' if red else 'green'}")
    for line in failed:
        err(f"keymap source probe: {line}")
    if not failed:
        ok(f"keymap source probe: {len(cases)} fixtures, each defect red and the clean tree green")
    return 1 if failed else 0


def main(argv):
    if "--probe" in argv:
        return probe()
    root = argv[1] if len(argv) > 1 else subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], stdin=subprocess.DEVNULL,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return run(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
