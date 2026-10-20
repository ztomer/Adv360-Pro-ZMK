#!/usr/bin/env python3
"""Every gate in tools/ must be WIRED into the sequencer, and the proofs must run in CI.

    check_gate_wiring.py [root]     # check the tree (default: the repo root)
    check_gate_wiring.py --probe    # prove this check goes red on each defect it claims to catch

A gate that exists and is never run is indistinguishable from a gate that passes. The house layer
finds every `tools/check_*` and runs its self-proof (gates_of_heck's "gate self-proofs still pass")
and sweeps it over an empty tree ("gates refuse to pass over an empty tree"), so a gate wired to
NOTHING is still exercised -- against its own fixtures, never against this tree. The sequencer
(`tools/repo_gates.sh`) is the only thing that runs a gate against the tree that ships, and
nothing proved that the sequencer runs every gate there is. A new check added to tools/ and
forgotten in the sequencer would be green forever.

What holds after this check passes:
  1. Every `tools/check_*` is named in `tools/repo_gates.sh` -- a gate nobody runs cannot fail.
  2. The sequencer names no gate that is not there -- a gate that died is not a pass.
  3. Every gate the sequencer runs has its failure GUARDED (`|| failed+=(...)`): an invocation
     whose exit code is thrown away is a gate whose red is swallowed.
  4. `tools/gate.sh --full` runs the sequencer: the entry point is where the pre-push hook lands.
  5. CI runs the proofs on every push (`.github/workflows/*.yml` runs `tools/run_proofs.sh`), so
     "the proof runs on every push" is a fact about the tree and not a habit.

The behavioural half -- the sequencer really runs what it names, and a red gate makes it red --
is this check's own --probe, which drives the sequencer in a scratch tree with stub gates.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.environ.get("GOH_DIR", os.path.expanduser("~/Projects/gates_of_heck")))
from tui.lib import err, ok  # noqa: E402

SEQUENCER = "tools/repo_gates.sh"
ENTRY = "tools/gate.sh"
GATESRC = ".gatesrc"
PROOFS = "tools/run_proofs.sh"
WORKFLOWS = ".github/workflows"
GATE = re.compile(r"tools/(check_[A-Za-z0-9_]+\.(?:py|sh))")
# A gate invocation whose failure is thrown away: the sequencer would report green over a red.
GUARDED = re.compile(r"\|\|\s*(failed\+=|warn\b)")
# The step list the gate of record runs (GOH_CI_STEPS in .gatesrc), read the way the house reads
# it: the value of one key, in one line.
STEPS = re.compile(r"^GOH_CI_STEPS=(.+)$", re.M)


def gates_in(root):
    """[name] for every gate file under tools/, sorted."""
    tools = os.path.join(root, "tools")
    if not os.path.isdir(tools):
        return []
    return sorted(
        name
        for name in os.listdir(tools)
        if name.startswith("check_") and name.endswith((".py", ".sh"))
    )


def read(root, rel):
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def workflows(root):
    directory = os.path.join(root, WORKFLOWS)
    if not os.path.isdir(directory):
        return []
    return sorted(n for n in os.listdir(directory) if n.endswith((".yml", ".yaml")))


def workflow_runs_proofs(root, name):
    """True when this workflow runs the proof runner, and triggers on push."""
    text = read(root, f"{WORKFLOWS}/{name}") or ""
    if PROOFS not in text:
        return False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("on:") and "push" in stripped:
            return True
        if stripped == "push:":
            return True
    return False


def declared_steps(root):
    """The step list .gatesrc declares (GOH_CI_STEPS), as one string."""
    text = read(root, GATESRC)
    if not text:
        return ""
    match = STEPS.search(text)
    if not match:
        return ""
    return match.group(1).strip().strip("'\"")


def problems(root):
    """The structural findings: what makes this gate red."""
    found = []
    sequencer = read(root, SEQUENCER)
    if sequencer is None:
        return [f"{SEQUENCER} is missing -- the scan lost its subject"]
    entry = read(root, ENTRY)
    if entry is None:
        return [f"{ENTRY} is missing -- the scan lost its subject"]
    gates = gates_in(root)
    if not gates:
        return ["no gates under tools/ -- the scan lost its subject"]

    named = set(GATE.findall(sequencer))
    for gate in gates:
        if gate not in named:
            found.append(
                f"{gate} is not run by {SEQUENCER}; a gate nobody runs cannot fail -- wire it in"
            )
    for gate in sorted(named):
        if gate not in gates:
            found.append(f"{SEQUENCER} runs {gate}, which does not exist")

    # Every gate the sequencer runs must have its failure guarded, and the guard must be on the
    # SAME line as the invocation: a guard on the next line guards nothing, and no guard at all
    # swallows the red.
    for number, line in enumerate(sequencer.splitlines(), 1):
        match = GATE.search(line)
        if not match:
            continue
        if not GUARDED.search(line):
            found.append(
                f"{SEQUENCER}:{number}: {match.group(1)} is run with its failure "
                "thrown away; a swallowed red is a green that means nothing"
            )

    # The sequencer has to be reachable from the gate of record: named by the entry point, or
    # declared as a step in .gatesrc (the house's local_ci.sh runs that list).
    steps = declared_steps(root)
    if SEQUENCER not in entry and SEQUENCER not in steps:
        found.append(
            f"neither {ENTRY} nor {GATESRC}'s step list runs {SEQUENCER}; the pre-push hook "
            "lands on the entry point"
        )

    if not any(workflow_runs_proofs(root, name) for name in workflows(root)):
        found.append(
            f"no workflow under {WORKFLOWS}/ runs {PROOFS} on every push; the proofs run only "
            "on a maintainer's machine"
        )
    return found


def run(root):
    found = problems(root)
    for line in found:
        err(f"gate wiring: {line}")
    if found:
        return 1
    ok(f"gate wiring: {len(gates_in(root))} gate(s) wired into {SEQUENCER}, and CI runs the proofs")
    return 0


# --- self-proof: the rules over fixtures, and the sequencer driven for real ------------------
# The stubs answer every gate the sequencer names, so the sequencer's OWN behaviour is what is
# under test: it runs each gate, and a gate that fails makes the sequencer red.
STUB_PY = """import os
import sys

name = os.path.basename(__file__)
with open(os.environ["GATE_STUB_LOG"], "a", encoding="utf-8") as handle:
    handle.write(name + "\\n")
if os.environ.get("GATE_STUB_FAIL", "") == name:
    sys.stderr.write("GATE STUB FAILED: " + name + "\\n")
    sys.exit(1)
sys.exit(0)
"""

STUB_SH = """#!/usr/bin/env bash
name="$(basename "$0")"
printf '%s\\n' "$name" >>"$GATE_STUB_LOG"
if [ "${GATE_STUB_FAIL:-}" = "$name" ]; then
    echo "GATE STUB FAILED: $name" >&2
    exit 1
fi
exit 0
"""

FIXTURE_SEQUENCER = """#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
failed=()
bash "$GOH/gates/python.sh" tools/check_one.py || failed+=("one")
tools/check_two.sh || failed+=("two")
if [ "${#failed[@]}" -gt 0 ]; then
    echo "repo gates: ${#failed[@]} failed: ${failed[*]}" >&2
    exit 1
fi
echo "repo gates: all passed"
"""

FIXTURE_WORKFLOW = """on: [push, pull_request]
jobs:
  proofs:
    steps:
      - run: bash tools/run_proofs.sh
"""

FIXTURE_GATESRC = "GOH_CI_STEPS='./tools/run_proofs.sh:./tools/repo_gates.sh'\n"


def _fixture(
    root,
    sequencer=FIXTURE_SEQUENCER,
    entry=None,
    workflow=FIXTURE_WORKFLOW,
    gatesrc=FIXTURE_GATESRC,
    extra=None,
):
    """A tree the rules can be judged against."""
    tools = os.path.join(root, "tools")
    os.makedirs(tools, exist_ok=True)
    for name in ("check_one.py", "check_two.sh"):
        path = os.path.join(tools, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("x\n")
    if extra:
        for name in extra:
            with open(os.path.join(tools, name), "w", encoding="utf-8") as handle:
                handle.write("x\n")
    with open(os.path.join(tools, "repo_gates.sh"), "w", encoding="utf-8") as handle:
        handle.write(sequencer)
    with open(os.path.join(tools, "gate.sh"), "w", encoding="utf-8") as handle:
        handle.write(
            entry if entry is not None else "#!/usr/bin/env bash\n./tools/repo_gates.sh\n"
        )
    if gatesrc is not None:
        with open(os.path.join(root, GATESRC), "w", encoding="utf-8") as handle:
            handle.write(gatesrc)
    if workflow is not None:
        directory = os.path.join(root, WORKFLOWS)
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, "ci.yml"), "w", encoding="utf-8") as handle:
            handle.write(workflow)
    return root


def _rule_cases():
    """[(name, fixture kwargs, want_red)] for every rule this check claims to catch."""
    unguarded = FIXTURE_SEQUENCER.replace(
        'bash "$GOH/gates/python.sh" tools/check_one.py || failed+=("one")',
        'bash "$GOH/gates/python.sh" tools/check_one.py',
    )
    return [
        ("clean", {}, False),
        ("a gate nobody runs", {"extra": ["check_three.py"]}, True),
        ("the sequencer runs a gate that is not there", {
            "sequencer": FIXTURE_SEQUENCER.replace(
                'tools/check_two.sh', 'tools/check_gone.sh'
            )
        }, True),
        ("a gate whose failure is thrown away", {"sequencer": unguarded}, True),
        ("the entry point does not run the sequencer", {
            "entry": "#!/usr/bin/env bash\nexit 0\n",
            "gatesrc": "GOH_CI_STEPS='./tools/run_proofs.sh'\n",
        }, True),
        ("CI runs no proofs", {"workflow": "on: [push]\njobs: {}\n"}, True),
    ]


def _scratch_tree(sequencer_text):
    """A scratch git repo holding the sequencer and a stub for every gate it names."""
    scratch = tempfile.mkdtemp(prefix="gate-wiring-probe.")
    subprocess.run(
        ["git", "init", "-q", scratch],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    tools = os.path.join(scratch, "tools")
    os.makedirs(tools)
    with open(os.path.join(tools, "repo_gates.sh"), "w", encoding="utf-8") as handle:
        handle.write(sequencer_text)
    os.chmod(os.path.join(tools, "repo_gates.sh"), 0o755)
    # Only the GATES are stubbed: the sequencer itself, and the file that holds it, stay the real
    # ones -- a stub in the sequencer's place would prove that a stub passes, which is nothing.
    names = {f"tools/{name}" for name in GATE.findall(sequencer_text)}
    if PROOFS in sequencer_text:
        names.add(PROOFS)
    for rel in sorted(names):
        path = os.path.join(tools, rel.split("/", 1)[1])
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(STUB_PY if rel.endswith(".py") else STUB_SH)
        if rel.endswith(".sh"):
            os.chmod(path, 0o755)
    return scratch, sorted(rel.split("/", 1)[1] for rel in names)


def _run_sequencer(scratch, fail=""):
    log = os.path.join(scratch, "calls.log")
    env = dict(os.environ)
    env["GATE_STUB_LOG"] = log
    env["GATE_STUB_FAIL"] = fail
    result = subprocess.run(
        ["bash", "tools/repo_gates.sh"],
        cwd=scratch,
        capture_output=True,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
        env=env,
    )
    called = []
    if os.path.isfile(log):
        with open(log, encoding="utf-8") as handle:
            called = [line.strip() for line in handle if line.strip()]
    return result, called


def probe():
    """Every rule goes red on its own fixture, and the sequencer is driven for real."""
    failed = []
    for name, kwargs, want_red in _rule_cases():
        with tempfile.TemporaryDirectory(prefix="gate-wiring-rule.") as root:
            _fixture(root, **kwargs)
            red = bool(problems(root))
        if red != want_red:
            failed.append(
                f"{name}: expected {'red' if want_red else 'green'}, got {'red' if red else 'green'}"
            )
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sequencer = read(root, SEQUENCER)
    if sequencer is None:
        err(f"gate wiring probe: {SEQUENCER} is missing")
        return 1
    scratch, stubs = _scratch_tree(sequencer)
    try:
        result, called = _run_sequencer(scratch)
        if result.returncode != 0:
            failed.append(
                "the sequencer is red over a tree of stub gates: "
                f"{result.stdout[-200:]}{result.stderr[-200:]}"
            )
        missing = [name for name in stubs if name not in called]
        if missing:
            failed.append(f"the sequencer did not run: {', '.join(missing)}")
        if stubs:
            one = stubs[0]
            result, called = _run_sequencer(scratch, fail=one)
            if result.returncode == 0:
                failed.append(f"the sequencer is GREEN with {one} failing")
            if one not in called:
                failed.append(f"the sequencer did not run {one} at all")
            if f"GATE STUB FAILED: {one}" not in (result.stdout + result.stderr):
                failed.append(f"the sequencer's red did not name {one}")
    finally:
        subprocess.run(
            ["rm", "-rf", scratch],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
    for line in failed:
        err(f"gate wiring probe: {line}")
    if not failed:
        ok(
            "gate wiring probe: every rule red on its fixture, and the sequencer runs every gate "
            "it names"
        )
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
