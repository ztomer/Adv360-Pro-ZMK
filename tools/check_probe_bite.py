#!/usr/bin/env python3
"""Every gate's self-proof must still go RED when the gate's pre-fix behaviour is planted back.

    check_probe_bite.py [root]     # check the tree (default: the repo root)
    check_probe_bite.py --probe    # prove this check goes red on each defect it claims to catch

A proof that has stopped biting is worse than no proof: the gate keeps printing OK, the tree keeps
being green, and the defect the proof was written for walks back in. The house layer runs every
self-proof (gates_of_heck's "gate self-proofs still pass"), but it can only see a proof that is
BROKEN -- a probe that raises, a fixture that was renamed. It cannot see a proof that has quietly
stopped detecting: the check was weakened, the probe still runs, the probe still passes, and the
fixture it once caught is now green.

So this gate plants the pre-fix behaviour -- the defect each check was written to catch -- into a
COPY of the check, runs the copy's own probe, and requires the probe to go red. The copy lives in
a scratch directory; the tree is never touched.

The mutations are one line each, and each names the defect it plants. A mutation whose text is no
longer in the source is a RED finding, not a skip: the proof's subject has moved, and the table
here is what says where it went.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.environ.get("GOH_DIR", os.path.expanduser("~/Projects/gates_of_heck")))
from tui.lib import err, ok  # noqa: E402

TOOLS = "tools"
TIMEOUT = 120
CRASH = "Traceback (most recent call last)"


class Mutation:
    """One planted pre-fix behaviour: the lines it replaces, and what it replaces them with."""

    def __init__(self, label, *edits):
        self.label = label
        self.edits = list(edits)

    def apply(self, text):
        """(the mutated text, why not) for this mutation."""
        for old, new in self.edits:
            if old not in text:
                if new in text:
                    return None, "the pre-fix behaviour is ALREADY planted -- the proof does not bite"
                return None, "the mutation no longer applies -- the gate's source has moved"
            text = text.replace(old, new, 1)
        return text, ""


# The pre-fix behaviour of each gate, as the gate was before the fix it exists for. The old text
# is quoted from the gate's own source; the new text is the behaviour BEFORE the fix.
MUTATIONS = {
    "check_image_pin.py": [
        Mutation(
            "the image is pinned on a moving tag and the check cannot tell",
            ('elif MOVING.match(match.group("tag")):', "elif False:"),
        )
    ],
    "check_readme_keymap.py": [
        Mutation(
            "the README's binding column is not compared with the keymap",
            ('elif " ".join(cells[0].split()) != binding:', "elif False:"),
        )
    ],
    "check_keymap_source.py": [
        Mutation(
            "config/keymap.json is back and the check does not see it",
            ("if os.path.exists(os.path.join(root, SECOND)):", "if False:"),
        )
    ],
    "check_host_software.py": [
        Mutation(
            "the README names the wrong software for a host chord",
            ("if software != recorded:", "if False:"),
            ("if software not in names:", "if False:"),
        )
    ],
    "check_zmk_base.py": [
        Mutation(
            "the base and the build image are on different Zephyr lines",
            ('if parsed.group("line") != line:', "if False:"),
            ('if not parsed.group("zephyr").startswith(line + "."):', "if False:"),
        ),
        Mutation(
            # The pre-fix behaviour: a commit id is a revision that names no Zephyr line, so the
            # gate went red before it got to its own commit-pin branch (P1.3).
            "a commit pin is refused",
            ('    if COMMIT.match(revision):\n        return "commit", ""',
             '    if False:\n        return "commit", ""'),
        ),
        Mutation(
            # The pre-fix behaviour: the Zephyr line came from the revision's NAME, so the gate
            # approved a pin whose resolved manifest named another line.
            "the Zephyr line is not read from the resolved manifest",
            ("line, error = zephyr_line(manifest, manifest_remotes(manifest), work, env)",
             'line, error = "3.5", ""'),
        ),
    ],
    "check_gate_wiring.py": [
        Mutation(
            "a gate nobody runs is not noticed",
            ("if gate not in named:", "if False:"),
        )
    ],
    "check_probe_bite.py": [
        Mutation(
            "a proof that stopped biting is not reported",
            (
                "            if not bit:\n"
                '                found.append(f"{name}: {mutation.label}: {why}")',
                "            if False:\n"
                '                found.append(f"{name}: {mutation.label}: {why}")',
            ),
        )
    ],
    "check_keymap_build.sh": [
        Mutation(
            "no container engine is a skip, not a red",
            (
                '        err "keymap build: no container engine (podman or docker) on PATH'
                '${DOCKER:+ (DOCKER=$DOCKER)}"\n'
                '        err "  install one (brew install docker colima), or set DOCKER; '
                'this gate never skips"\n'
                "        return 1",
                '        ok "keymap build: no container engine; skipping"\n        return 0',
            ),
        )
    ],
    "check_upstream_drift.sh": [
        Mutation(
            "drift behind the fork is not counted",
            ('if [ "$count" -gt 0 ]; then', "if false; then"),
        )
    ],
}


def gates_in(root):
    """[name] for every gate file under tools/, sorted."""
    tools = os.path.join(root, TOOLS)
    if not os.path.isdir(tools):
        return []
    return sorted(
        name
        for name in os.listdir(tools)
        if name.startswith("check_") and name.endswith((".py", ".sh"))
    )


def _child_env():
    """The child's environment, without the hook's GIT_* variables: a probe that runs `git init`
    in a scratch directory must not answer with the real repository."""
    env = dict(os.environ)
    for key in [k for k in env if k.startswith("GIT_")]:
        del env[key]
    env.setdefault(
        "GOH_DIR", os.environ.get("GOH_DIR", os.path.expanduser("~/Projects/gates_of_heck"))
    )
    return env


def _run_probe(path, cwd):
    """(exit code, output) for the gate's own --probe."""
    command = [sys.executable, path, "--probe"] if path.endswith(".py") else ["bash", path, "--probe"]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            env=_child_env(),
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return 124, f"the probe did not finish within {TIMEOUT}s"
    return result.returncode, result.stdout + result.stderr


def _bites(root, name, mutation):
    """(bit, why) for one mutation: does the mutated gate's own probe go red?"""
    source = os.path.join(root, TOOLS, name)
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    mutated, why = mutation.apply(text)
    if mutated is None:
        return False, why
    with tempfile.TemporaryDirectory(prefix="probe-bite.") as scratch:
        copy = os.path.join(scratch, name)
        with open(copy, "w", encoding="utf-8") as handle:
            handle.write(mutated)
        if name.endswith(".sh"):
            os.chmod(copy, 0o755)
        code, output = _run_probe(copy, scratch)
    if code == 0:
        return False, "the probe stayed GREEN over the planted defect"
    if CRASH in output:
        return False, f"the probe crashed instead of reporting the planted defect: {output[:200]}"
    return True, ""


def problems(root, mutations=None):
    """The findings: every gate whose proof has stopped biting."""
    found = []
    table = MUTATIONS if mutations is None else mutations
    gates = gates_in(root)
    if not gates:
        return ["no gates under tools/ -- the scan lost its subject"]
    for name in gates:
        if name not in table:
            found.append(
                f"{name} has no planted pre-fix behaviour here; a gate with no mutation is a "
                "gate nobody has checked can still fail"
            )
            continue
        for mutation in table[name]:
            bit, why = _bites(root, name, mutation)
            if not bit:
                found.append(f"{name}: {mutation.label}: {why}")
    return found


def run(root):
    found = problems(root)
    for line in found:
        err(f"probe bite: {line}")
    if found:
        return 1
    ok(
        f"probe bite: {len(gates_in(root))} gate(s), every planted pre-fix behaviour caught by "
        "its own proof"
    )
    return 0


# --- self-proof: the machinery, over fixtures ------------------------------------------------
FIXTURE_GATE = """import sys

if "--probe" in sys.argv:
    print("the fixture defect is red")
    sys.exit(1)
sys.exit(0)
"""


def probe():
    """Three fixtures: a proof that bites, a proof that does not, and a mutation that no longer
    applies."""
    failed = []
    with tempfile.TemporaryDirectory(prefix="probe-bite-probe.") as scratch:
        tools = os.path.join(scratch, TOOLS)
        os.makedirs(tools)
        with open(os.path.join(tools, "check_fake.py"), "w", encoding="utf-8") as handle:
            handle.write(FIXTURE_GATE)
        # 1. A mutation that removes the detection: the proof must stop biting, and be reported.
        bites = {
            "check_fake.py": [Mutation("the fixture defect", ("sys.exit(1)", "sys.exit(0)"))]
        }
        found = problems(scratch, bites)
        if not found:
            failed.append("a proof that no longer bites was not reported")
        # 2. A mutation that keeps the detection: the proof still bites, and nothing is reported.
        keeps = {
            "check_fake.py": [Mutation("the fixture defect", ("sys.exit(1)", "sys.exit(1) "))]
        }
        found = problems(scratch, keeps)
        if found:
            failed.append(f"a proof that still bites was reported: {found}")
        # 3. A mutation whose text is gone: reported, not skipped.
        gone = {
            "check_fake.py": [Mutation("the fixture defect", ("no such text", "not-in-the-fixture"))]
        }
        found = problems(scratch, gone)
        if not found or "source has moved" not in found[0]:
            failed.append("a mutation that no longer applies was not reported")
        # 4. A mutation whose pre-fix behaviour is already there: reported as such.
        planted = {
            "check_fake.py": [Mutation("the fixture defect", ("no such text", "sys.exit(1)"))]
        }
        found = problems(scratch, planted)
        if not found or "ALREADY planted" not in found[0]:
            failed.append("a pre-fix behaviour that is already planted was not reported")
    for line in failed:
        err(f"probe bite probe: {line}")
    if not failed:
        ok("probe bite probe: a proof that stopped biting is red, and a proof that bites is green")
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
