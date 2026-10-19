#!/usr/bin/env python3
"""The ZMK base pin and the build image must be the same Zephyr line, and the pin's drift reported.

    check_zmk_base.py [root]     # check the tree (default: the repo root)
    check_zmk_base.py --probe    # prove this check goes red on each defect it claims to catch

`config/west.yml` pins the base: `refil/zmk` at `adv360-z3.5-2`, a branch whose name says the
Zephyr line it runs (3.5). The build image says the same thing in its tag
(`3.5-branch-20250930025731-3.5.0-0.16.3-f93290b3ab1a-18117245422`: the Zephyr branch, the build
stamp, the Zephyr version, the SDK, the zmk-docker commit). Two facts can drift apart silently:
the base can move to another Zephyr line while the image stays, or the image can be re-pinned
while the base stays. Then the firmware is built with a base the toolchain was not built for, and
nothing says so.

What holds after this check passes:
  1. `config/west.yml` pins a zmk revision whose Zephyr line can be READ. A revision this check
     cannot read is refused, not passed: an undetermined pairing is not a pairing.
  2. The build image's tag names that same Zephyr line, and the image's Zephyr version belongs
     to it.
  3. The Dockerfile and both CI jobs carry the SAME image tag (one pin, three places).

What this check reports but does not block on: the pin is a MOVING branch, so `west update`
takes whatever the branch head was when the build ran. The check resolves the head
(`git ls-remote`) and dates it, and says so when the head is newer than the image. Re-pinning
the base to a commit is the owner's ruling, not this gate's (ROADMAP P2.1 follows Kinesis).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.environ.get("GOH_DIR", os.path.expanduser("~/Projects/gates_of_heck")))
from tui.lib import err, ok, warn  # noqa: E402

WEST = "config/west.yml"
DOCKERFILE = "Dockerfile"
WORKFLOWS = ".github/workflows"
PROJECT = "zmk"  # the manifest's project name; the remote names where it comes from
# The image tag: <zephyr>-branch-<stamp>-<zephyr version>-<sdk>-<zmk-docker commit>-<build>.
TAG = re.compile(
    r"^(?P<line>\d+\.\d+)-branch-(?P<stamp>\d{14})-(?P<zephyr>\d+\.\d+\.\d+)"
    r"-(?P<sdk>\d+\.\d+\.\d+)-(?P<docker>[0-9a-f]+)-(?P<build>\d+)$"
)
# The base revision names its Zephyr line: adv360-z3.5-2 -> 3.5.
REVISION = re.compile(r"^adv360-z(?P<line>\d+\.\d+)(?:-\d+)?$")


def west_pin(text):
    """(remote, url_base, revision) for the zmk project in a west manifest."""
    remote = url_base = revision = None
    projects = re.search(r"^\s*projects:\s*$(.*?)(?=^\s*self:|\Z)", text, flags=re.M | re.S)
    block = projects.group(1) if projects else ""
    entry = re.search(r"-\s*name:\s*zmk\b(.*?)(?=\n\s*-\s*name:|\Z)", block, flags=re.S)
    if entry:
        fields = entry.group(1)
        remote_match = re.search(r"remote:\s*(\S+)", fields)
        revision_match = re.search(r"revision:\s*(\S+)", fields)
        remote = remote_match.group(1) if remote_match else None
        revision = revision_match.group(1) if revision_match else None
    remotes = re.search(r"^\s*remotes:\s*$(.*?)(?=^\s*projects:|\Z)", text, flags=re.M | re.S)
    for name, url in re.findall(r"-\s*name:\s*(\S+)\s*\n\s*url-base:\s*(\S+)", remotes.group(1) if remotes else ""):
        if name == remote:
            url_base = url
    return remote, url_base, revision


def image_references(root):
    """[(file, line_no, reference)] for every image the build pulls."""
    refs = []
    dockerfile = os.path.join(root, DOCKERFILE)
    if os.path.isfile(dockerfile):
        with open(dockerfile, encoding="utf-8") as handle:
            for no, line in enumerate(handle, 1):
                match = re.match(r"\s*FROM\s+(\S+)", line, re.IGNORECASE)
                if match:
                    refs.append((DOCKERFILE, no, match.group(1)))
    workflows = os.path.join(root, WORKFLOWS)
    if os.path.isdir(workflows):
        for name in sorted(os.listdir(workflows)):
            if not name.endswith((".yml", ".yaml")):
                continue
            rel = f"{WORKFLOWS}/{name}"
            with open(os.path.join(root, rel), encoding="utf-8") as handle:
                for no, line in enumerate(handle, 1):
                    match = re.match(r"\s*image:\s*['\"]?([^'\"\s#]+)", line)
                    if match:
                        refs.append((rel, no, match.group(1)))
    return refs


def problems(root):
    """The structural findings: what makes this gate red."""
    found = []
    west_path = os.path.join(root, WEST)
    if not os.path.isfile(west_path):
        return [f"{WEST} is missing -- the scan lost its subject"]
    with open(west_path, encoding="utf-8") as handle:
        remote, url_base, revision = west_pin(handle.read())
    if not revision:
        found.append(f"{WEST} pins no zmk revision")
        return found
    match = REVISION.match(revision)
    if not match:
        found.append(
            f"{WEST} pins revision '{revision}', which names no Zephyr line; this check cannot tell "
            "which build image belongs to it -- re-pin the image and this check together"
        )
        return found
    line = match.group("line")

    refs = image_references(root)
    if not refs:
        found.append(f"no FROM in {DOCKERFILE} and no image: in {WORKFLOWS} -- the scan lost its subject")
        return found
    tags = {}
    for rel, no, ref in refs:
        tag = ref.split("@", 1)[0].rsplit(":", 1)[-1]
        tags.setdefault(tag, []).append(f"{rel}:{no}")
    if len(tags) > 1:
        where = "; ".join(f"{tag} in {', '.join(where)}" for tag, where in sorted(tags.items()))
        found.append(f"the build image is pinned {len(tags)} ways ({where}); there must be one pin")
    for tag, where in sorted(tags.items()):
        parsed = TAG.match(tag)
        if not parsed:
            found.append(
                f"image tag '{tag}' ({', '.join(where)}) does not name a Zephyr line; this check "
                "cannot tell which Zephyr the image builds"
            )
            continue
        if parsed.group("line") != line:
            found.append(
                f"the base is Zephyr {line} but the image builds Zephyr {parsed.group('line')} "
                f"({', '.join(where)}); re-pin the image to match the base"
            )
        if not parsed.group("zephyr").startswith(line + "."):
            found.append(
                f"image tag '{tag}' carries Zephyr {parsed.group('zephyr')}, which is not the base's "
                f"Zephyr {line} line"
            )
    return found


def resolve_head(url, revision):
    """The commit the pinned branch points at, or None when it cannot be reached."""
    out = subprocess.run(
        ["git", "ls-remote", "--heads", url, revision],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        return None
    for line in out.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.strip().endswith("/" + revision):
            return sha.strip()
    return None


def head_date(repo, sha):
    """The head's commit date, or None when the API cannot say."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/commits/{sha}",
        headers={"User-Agent": "adv360-pro-zmk-gate"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.load(response)
        return datetime.fromisoformat(data["commit"]["committer"]["date"].replace("Z", "+00:00"))
    except (urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError):
        return None


def report(root):
    """Say what the pin is and how far it has moved. Warnings, never a red gate."""
    with open(os.path.join(root, WEST), encoding="utf-8") as handle:
        remote, url_base, revision = west_pin(handle.read())
    if not (remote and url_base and revision):
        return
    url = f"{url_base.rstrip('/')}/{PROJECT}"
    refs = image_references(root)
    stamp = None
    for _, _, ref in refs:
        tag = ref.split("@", 1)[0].rsplit(":", 1)[-1]
        parsed = TAG.match(tag)
        if parsed:
            stamp = datetime.strptime(parsed.group("stamp"), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            break
    if re.fullmatch(r"[0-9a-f]{40}", revision):
        ok(f"zmk base: {url} {revision} (a commit pin); the build is reproducible")
        return
    warn(f"zmk base: {url} {revision} is a MOVING branch; west update builds whatever its head was")
    head = resolve_head(url, revision)
    if not head:
        warn("zmk base: the head could not be resolved (offline?); the drift is unknown")
        return
    dated = head_date(url.split("github.com/")[-1], head)
    when = dated.strftime("%Y-%m-%d") if dated else "an unknown date"
    if stamp and dated and dated > stamp:
        warn(
            f"zmk base: the head {head[:7]} ({when}) is newer than the build image "
            f"({stamp.strftime('%Y-%m-%d')}); CI builds the head, the local image builds the copy "
            "baked into it"
        )
    else:
        warn(f"zmk base: the head is {head[:7]} ({when})")


def run(root):
    found = problems(root)
    for line in found:
        err(f"zmk base: {line}")
    if found:
        return 1
    report(root)
    ok("zmk base: the pinned base and the build image are the same Zephyr line")
    return 0


GOOD_TAG = "3.5-branch-20250930025731-3.5.0-0.16.3-f93290b3ab1a-18117245422"
GOOD_DIGEST = "sha256:" + "a" * 64
GOOD_WEST = """manifest:
  remotes:
    - name: refil
      url-base: https://github.com/refil
  projects:
    - name: zmk
      remote: refil
      revision: adv360-z3.5-2
      import: app/west.yml
  self:
    path: config
"""


def _fixture(root, west, dockerfile, workflow):
    os.makedirs(os.path.join(root, "config"))
    os.makedirs(os.path.join(root, ".github", "workflows"))
    for rel, text in (
        ("config/west.yml", west),
        ("Dockerfile", dockerfile),
        (".github/workflows/build.yml", workflow),
    ):
        with open(os.path.join(root, rel), "w", encoding="utf-8") as handle:
            handle.write(text)


def probe():
    """Each defect in the docstring goes red alone; the clean fixture is green."""
    ref = f"zmkfirmware/zmk-build-arm:{GOOD_TAG}@{GOOD_DIGEST}"
    workflow = f"jobs:\n  build:\n    container:\n      image: {ref}\n"
    cases = {
        "clean": (GOOD_WEST, f"FROM {ref}\n", workflow, False),
        "no west.yml": ("", f"FROM {ref}\n", workflow, True),
        "no revision": (GOOD_WEST.replace("      revision: adv360-z3.5-2\n", ""), f"FROM {ref}\n", workflow, True),
        "revision names no line": (
            GOOD_WEST.replace("adv360-z3.5-2", "main"), f"FROM {ref}\n", workflow, True
        ),
        "image on another Zephyr line": (
            GOOD_WEST,
            f"FROM zmkfirmware/zmk-build-arm:4.1-branch-20251204031905-4.1.0-0.16.9-29d0ea120dcc-19916495446@{GOOD_DIGEST}\n",
            workflow,
            True,
        ),
        "the CI job pins another image": (
            GOOD_WEST,
            f"FROM {ref}\n",
            f"jobs:\n  build:\n    container:\n      image: zmkfirmware/zmk-build-arm:4.4-branch-x@{GOOD_DIGEST}\n",
            True,
        ),
        "no image at all": (GOOD_WEST, "", "", True),
        "empty scope": ("", "", "", True),
    }
    failed = []
    for name, (west, dockerfile, workflow_text, want_red) in cases.items():
        with tempfile.TemporaryDirectory(prefix="zmk-base-probe-") as root:
            _fixture(root, west, dockerfile, workflow_text)
            red = bool(problems(root))
        if red != want_red:
            failed.append(f"{name}: expected {'red' if want_red else 'green'}, got {'red' if red else 'green'}")
    for line in failed:
        err(f"zmk base probe: {line}")
    if not failed:
        ok(f"zmk base probe: {len(cases)} fixtures, each defect red and the clean fixture green")
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
