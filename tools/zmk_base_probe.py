"""The --probe of check_zmk_base.py: its fixtures and the cases that must go red.

Split out to keep check_zmk_base.py under the line cap. The check passes ITSELF in, so the probe
exercises whichever copy is running -- check_probe_bite.py runs a MUTATED copy from a scratch
directory (it copies this sibling beside it) and needs that copy's logic, not the tree's.
"""

from __future__ import annotations

import os
import tempfile

from tui.lib import err, ok

_c = None  # the running check module; set by probe()


# --- the fixtures -----------------------------------------------------------------------------
GOOD_TAG = "3.5-branch-20250930025731-3.5.0-0.16.3-f93290b3ab1a-18117245422"
OTHER_TAG = "4.1-branch-20251204031905-4.1.0-0.16.9-29d0ea120dcc-19916495446"
GOOD_DIGEST = "sha256:" + "a" * 64
GOOD_REVISION = "adv360-z3.5-2"
# The bases the fake remote carries, one per branch: the Zephyr line a manifest names.
BASES = (
    (GOOD_REVISION, "v3.5.0+zmk-fixes"),
    ("d93499bb", "v3.5.0+zmk-fixes"),  # a branch whose NAME looks like a commit id
    ("other", "v4.1.0"),
    ("noline", "main"),  # a manifest that names no Zephyr version
)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _manifest(remote, url_base, project, revision, path, extra=""):
    """A west manifest: one remote, one project pinned at `revision`."""
    pinned = f"      revision: {revision}\n" if revision else ""
    return (
        f"manifest:\n  remotes:\n    - name: {remote}\n      url-base: {url_base}\n"
        f"  projects:\n    - name: {project}\n      remote: {remote}\n{pinned}{extra}"
        f"  self:\n    path: {path}\n"
    )


def fake_remote(root):
    """A git repo standing in for the zmk remote: one branch per base.

    Returns {branch: commit}. The commits are what the branches name, so a fixture can pin one
    of them by its sha -- the pin a commit id is.
    """
    path = os.path.join(root, "remote", _c.PROJECT)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    env = _c.foreign_env()
    _c._git(["init", "-q", "-b", "base", path], env=env)
    for branch, zephyr in BASES:
        _write(
            os.path.join(path, "app", "west.yml"),
            _manifest(
                "zmkfirmware", "https://github.com/zmkfirmware", "zephyr", zephyr, "app"
            ),
        )
        _c._git(["add", "-A"], cwd=path, env=env)
        _c._git(
            [
                "-c",
                "user.name=gate",
                "-c",
                "user.email=gate@example.invalid",
                "commit",
                "-q",
                "-m",
                branch,
            ],
            cwd=path,
            env=env,
        )
        _c._git(["branch", "-f", branch], cwd=path, env=env)
    return {
        b: _c._git(["rev-parse", b], cwd=path, env=env)[1].strip() for b, _ in BASES
    }


def _fixture(root, url_base, revision, dockerfile, workflow):
    """Write the tree a fixture is: the manifest, the Dockerfile and the workflow."""
    if revision is not None:
        _write(
            os.path.join(root, _c.WEST),
            _manifest(
                "refil",
                url_base,
                _c.PROJECT,
                revision,
                "config",
                "      import: app/west.yml\n",
            ),
        )
    _write(os.path.join(root, _c.DOCKERFILE), dockerfile)
    _write(os.path.join(root, ".github", "workflows", "build.yml"), workflow)


def probe(check):
    """Each defect in the docstring goes red alone; the clean fixture is green."""
    global _c
    _c = check
    ref = f"zmkfirmware/zmk-build-arm:{GOOD_TAG}@{GOOD_DIGEST}"
    other = f"zmkfirmware/zmk-build-arm:{OTHER_TAG}@{GOOD_DIGEST}"
    dockerfile, other_dockerfile = f"FROM {ref}\n", f"FROM {other}\n"
    workflow = f"jobs:\n  build:\n    container:\n      image: {ref}\n"
    other_workflow = f"jobs:\n  build:\n    container:\n      image: {other}\n"
    odd_job = f"jobs:\n  build:\n    container:\n      image: zmkfirmware/zmk-build-arm:4.4-branch-x@{GOOD_DIGEST}\n"
    failed = []
    with tempfile.TemporaryDirectory(prefix="zmk-base-probe-") as scratch:
        commits = fake_remote(scratch)
        url_base = os.path.join(scratch, "remote")
        cases = {
            "clean": (GOOD_REVISION, dockerfile, workflow, False),
            # The pin a commit id is: the gate accepts it and reads the line at that commit.
            "a commit pin": (commits[GOOD_REVISION], dockerfile, workflow, False),
            # A name that looks like a commit id is a BRANCH, because the remote says so.
            "a branch whose name looks like a commit": (
                "d93499bb",
                dockerfile,
                workflow,
                False,
            ),
            # The line comes from the manifest at the PINNED commit: this one names another line.
            "a commit pin on another Zephyr line": (
                commits["other"],
                dockerfile,
                workflow,
                True,
            ),
            "a commit the remote does not have": ("0" * 40, dockerfile, workflow, True),
            "a revision that names nothing": (
                "no-such-pin",
                dockerfile,
                workflow,
                True,
            ),
            "the resolved manifest names no Zephyr version": (
                "noline",
                dockerfile,
                workflow,
                True,
            ),
            # ONE pin, on another Zephyr line than the base: the Dockerfile and the CI job agree,
            # and the pair is still wrong. (The case below this one is a different defect: two pins.)
            "the image is on another Zephyr line": (
                GOOD_REVISION,
                other_dockerfile,
                other_workflow,
                True,
            ),
            "two pins": (GOOD_REVISION, other_dockerfile, workflow, True),
            "the CI job pins another image": (GOOD_REVISION, dockerfile, odd_job, True),
            "no west.yml": (None, dockerfile, workflow, True),
            "no revision": ("", dockerfile, workflow, True),
            "no image at all": (GOOD_REVISION, "", "", True),
            "empty scope": (None, "", "", True),
        }
        for name, (revision, dockerfile_text, workflow_text, want_red) in cases.items():
            with tempfile.TemporaryDirectory(prefix="zmk-base-case-") as root:
                _fixture(root, url_base, revision, dockerfile_text, workflow_text)
                red = bool(_c.problems(root))
            if red != want_red:
                failed.append(
                    f"{name}: expected {'red' if want_red else 'green'}, got {'red' if red else 'green'}"
                )
    for line in failed:
        err(f"zmk base probe: {line}")
    if not failed:
        ok(
            f"zmk base probe: {len(cases)} fixtures, each defect red and the clean fixture green"
        )
    return 1 if failed else 0
