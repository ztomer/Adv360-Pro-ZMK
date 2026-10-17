#!/usr/bin/env python3
"""The build image is ONE named release, pinned by digest, spelled in the places that cannot derive it.

    check_image_pin.py [root]     # check the tree (default: the repo root)
    check_image_pin.py --probe    # prove this check goes red on each defect it claims to catch

The firmware is built from `zmkfirmware/zmk-build-arm` in three places: the Dockerfile (local
`make` and the keymap build gate) and the two CI jobs. Until P0.2 all three read `:stable`, a
moving tag, so a CI run and a local build could use different toolchains with nothing saying so.

What holds after this check passes:
  1. Every `FROM` in `Dockerfile` and every `image:` in `.github/workflows/*.yml` carries a tag AND
     an `@sha256:` digest (the house rule: a named release, pinned by digest plus its tag).
  2. The tag is not a moving name (`stable`, `latest`, `main`, a bare `<zephyr>-branch`, ...).
  3. All of them are the same reference -- one pin, not three that can drift.
  4. No other build file spells the image; `Makefile` derives it from the Dockerfile.

The generic "no moving image tag" class belongs in gates_of_heck (ROADMAP P0.2 class note); this
check holds this repo's single-pin invariant, which is local by nature.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.environ.get("GOH_DIR", os.path.expanduser("~/Projects/gates_of_heck")))
from tui.lib import err, ok  # noqa: E402

IMAGE = "zmkfirmware/zmk-build-"
MOVING = re.compile(r"^(latest|stable|main|master|edge|nightly|dev|\d+(\.\d+)*-branch)$")
PINNED = re.compile(r"^(?:docker\.io/)?(?P<name>[\w./-]+):(?P<tag>[\w.-]+)@sha256:[0-9a-f]{64}$")
# Files that may not hold the pin: they read it from the Dockerfile instead.
DERIVED = ("Makefile", "bin/build.sh")


def references(root):
    """[(file, line_no, ref)] for every image the build pulls."""
    refs = []
    dockerfile = os.path.join(root, "Dockerfile")
    if os.path.isfile(dockerfile):
        with open(dockerfile, encoding="utf-8") as handle:
            for no, line in enumerate(handle, 1):
                match = re.match(r"\s*FROM\s+(\S+)", line, re.IGNORECASE)
                if match:
                    refs.append(("Dockerfile", no, match.group(1)))
    workflows = os.path.join(root, ".github", "workflows")
    if os.path.isdir(workflows):
        for name in sorted(os.listdir(workflows)):
            if not name.endswith((".yml", ".yaml")):
                continue
            rel = f".github/workflows/{name}"
            with open(os.path.join(workflows, name), encoding="utf-8") as handle:
                for no, line in enumerate(handle, 1):
                    match = re.match(r"\s*image:\s*['\"]?([^'\"\s#]+)", line)
                    if match:
                        refs.append((rel, no, match.group(1)))
    return refs


def problems(root):
    found = []
    refs = references(root)
    if not refs:
        return ["no FROM in Dockerfile and no image: in .github/workflows -- the scan lost its subject"]
    for rel, no, ref in refs:
        match = PINNED.match(ref)
        if not match:
            found.append(f"{rel}:{no}: '{ref}' is not <image>:<tag>@sha256:<digest>")
        elif MOVING.match(match.group("tag")):
            found.append(f"{rel}:{no}: tag '{match.group('tag')}' is a moving name; pin a dated release tag")
    distinct = {re.sub(r"^docker\.io/", "", ref) for _, _, ref in refs}
    if len(distinct) > 1:
        where = ", ".join(f"{rel}:{no}" for rel, no, _ in refs)
        found.append(f"{len(distinct)} different images across {where}; there must be one pin")
    for rel in DERIVED:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            for no, line in enumerate(handle, 1):
                if IMAGE in line:
                    found.append(f"{rel}:{no}: spells the image; derive it from the Dockerfile")
    return found


def run(root):
    found = problems(root)
    for line in found:
        err(f"image pin: {line}")
    if not found:
        ok(f"image pin: {len(references(root))} build image references, one digest-pinned release")
    return 1 if found else 0


GOOD = "docker.io/zmkfirmware/zmk-build-arm:3.5-branch-20250930-x@sha256:" + "a" * 64


def _fixture(root, dockerfile, workflow, makefile):
    os.makedirs(os.path.join(root, ".github", "workflows"))
    for rel, text in (
        ("Dockerfile", dockerfile),
        (".github/workflows/build.yml", workflow),
        ("Makefile", makefile),
    ):
        with open(os.path.join(root, rel), "w", encoding="utf-8") as handle:
            handle.write(text)


def probe():
    """Each defect in the docstring goes red alone; the clean fixture is green."""
    ref = GOOD.removeprefix("docker.io/")
    make_ok = "IMAGE := $(shell sed -n 's/^FROM //p' Dockerfile)\n"
    cases = {
        "clean": (f"FROM {GOOD}\n", f"    image: {ref}\n", make_ok, False),
        "no digest": ("FROM zmkfirmware/zmk-build-arm:3.5-branch-x\n", "    image: zmkfirmware/zmk-build-arm:3.5-branch-x\n", make_ok, True),
        "moving tag": (f"FROM {GOOD.replace('3.5-branch-20250930-x', 'stable')}\n", f"    image: {ref.replace('3.5-branch-20250930-x', 'stable')}\n", make_ok, True),
        "two pins": (f"FROM {GOOD}\n", f"    image: {ref.replace('a' * 64, 'b' * 64)}\n", make_ok, True),
        "makefile literal": (f"FROM {GOOD}\n", f"    image: {ref}\n", f"rm {GOOD}\n", True),
        "empty scope": ("", "", make_ok, True),
    }
    failed = []
    for name, (dockerfile, workflow, makefile, want_red) in cases.items():
        with tempfile.TemporaryDirectory(prefix="image-pin-probe-") as root:
            _fixture(root, dockerfile, workflow, makefile)
            red = bool(problems(root))
        if red != want_red:
            failed.append(f"{name}: expected {'red' if want_red else 'green'}, got {'red' if red else 'green'}")
    for line in failed:
        err(f"image pin probe: {line}")
    if not failed:
        ok(f"image pin probe: {len(cases)} fixtures, each defect red and the clean tree green")
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
