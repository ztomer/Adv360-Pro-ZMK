#!/usr/bin/env python3
"""The ZMK base pin and the build image must be the same Zephyr line, and the pin's kind named.

    check_zmk_base.py [root]     # check the tree (default: the repo root)
    check_zmk_base.py --probe    # prove this check goes red on each defect it claims to catch

`config/west.yml` pins the base: `refil/zmk` at `adv360-z3.5-2`, a branch whose name says the
Zephyr line it runs (3.5). The build image says the same thing in its tag
(`3.5-branch-20250930025731-3.5.0-0.16.3-f93290b3ab1a-18117245422`: the Zephyr branch, the build
stamp, the Zephyr version, the SDK, the zmk-docker commit). Two facts can drift apart silently:
the base can move to another Zephyr line while the image stays, or the image can be re-pinned
while the base stays. Then the firmware is built with a base the toolchain was not built for, and
nothing says so.

THE PIN'S KIND IS NAMED, AND ITS LINE IS READ FROM THE RESOLVED MANIFEST. A pin is either a
COMMIT -- an id nothing can move -- or a BRANCH -- a name its upstream moves under the build.
The house names the two apart (gates_of_heck's `goh moving-tags`, 2026-10-21): a gate that cannot
EXPRESS a pin cannot accept one. This check used to read the Zephyr line out of the revision's
NAME (`adv360-z3.5-2` -> 3.5), so a commit was "a revision that names no Zephyr line", the gate
went red before it got there, and the commit branch of its own report was dead code. So the KIND
is what the REMOTE says -- a name under refs/heads is a branch, a name under refs/tags is a tag, a
commit id is a commit, and never the name alone: a branch called `d93499bb` is a branch, and a
commit the remote does not have is a pin of nothing. The LINE is read from the RESOLVED MANIFEST
-- the manifest the resolved commit carries (`app/west.yml` at that commit), never from a working
tree and never from a copy of the pin. A resolution that fails is NAMED, never a silent green.

What holds after this check passes:
  1. the pin is resolved against the remote it names, and the kind of pin it is is reported.
  2. the Zephyr line is read from the manifest at the resolved commit -- a line this check cannot
     read is refused, not passed: an undetermined pairing is not a pairing.
  3. the build image's tag names that same Zephyr line, the image's Zephyr version belongs to it,
     and the Dockerfile and both CI jobs carry the SAME image tag (one pin, three places).

What this check reports but does not block on: a MOVING pin. A branch follows its upstream and can
move under the build; a commit cannot move, but it does not follow its upstream either. Which pin
a repository must use is the owner's ruling (ROADMAP P1.3), not this gate's.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.environ.get("GOH_DIR", os.path.expanduser("~/Projects/gates_of_heck")))
from tui.lib import err, ok, warn  # noqa: E402

WEST = "config/west.yml"
DOCKERFILE = "Dockerfile"
WORKFLOWS = ".github/workflows"
PROJECT = "zmk"
# The manifest the zmk project imports, read AT the commit the pin resolves to.
IMPORTED = "app/west.yml"
# The file in the zephyr project that carries its version, read at a commit pin.
ZEPHYR_VERSION = "VERSION"
# The image tag: <zephyr>-branch-<stamp>-<zephyr version>-<sdk>-<zmk-docker commit>-<build>.
TAG = re.compile(
    r"^(?P<line>\d+\.\d+)-branch-(?P<stamp>\d{14})-(?P<zephyr>\d+\.\d+\.\d+)"
    r"-(?P<sdk>\d+\.\d+\.\d+)-(?P<docker>[0-9a-f]+)-(?P<build>\d+)$"
)
# A Zephyr line, as the version a manifest names carries it: v3.5.0+zmk-fixes -> 3.5.
VERSION = re.compile(r"^v?(?P<line>\d+\.\d+)")
# A commit id: the shape git gives a commit, and the one pin nothing can move.
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")


# --- the manifest -----------------------------------------------------------------------------
def manifest_project(text, name):
    """(remote, revision) for one project in a west manifest."""
    projects = re.search(r"^\s*projects:\s*$(.*?)(?=^\s*self:|\Z)", text, flags=re.M | re.S)
    block = projects.group(1) if projects else ""
    entry = re.search(
        rf"-\s*name:\s*{re.escape(name)}(?![-\w])(.*?)(?=\n\s*-\s*name:|\Z)", block, flags=re.S
    )
    if not entry:
        return None, None
    fields = entry.group(1)
    remote = re.search(r"remote:\s*(\S+)", fields)
    revision = re.search(r"revision:\s*(\S+)", fields)
    return (remote.group(1) if remote else None, revision.group(1) if revision else None)


def manifest_remotes(text):
    """{name: url-base} for the remotes in a west manifest."""
    remotes = re.search(r"^\s*remotes:\s*$(.*?)(?=^\s*projects:|\Z)", text, flags=re.M | re.S)
    block = remotes.group(1) if remotes else ""
    return dict(re.findall(r"-\s*name:\s*(\S+)\s*\n\s*url-base:\s*(\S+)", block))


def west_pin(text):
    """(remote, url_base, revision) for the zmk project in the repo's own manifest."""
    remote, revision = manifest_project(text, PROJECT)
    return remote, manifest_remotes(text).get(remote), revision


def image_tags(root):
    """{tag: [where]} for every image the build pulls."""
    sources = [(DOCKERFILE, re.compile(r"\s*FROM\s+(\S+)", re.IGNORECASE))]
    workflows = os.path.join(root, WORKFLOWS)
    for name in sorted(os.listdir(workflows)) if os.path.isdir(workflows) else []:
        if name.endswith((".yml", ".yaml")):
            sources.append((f"{WORKFLOWS}/{name}", re.compile(r"\s*image:\s*['\"]?([^'\"\s#]+)")))
    tags = {}
    for rel, pattern in sources:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            for no, line in enumerate(handle, 1):
                match = pattern.match(line)
                if match:
                    ref = match.group(1)
                    tags.setdefault(ref.split("@", 1)[0].rsplit(":", 1)[-1], []).append(f"{rel}:{no}")
    return tags


# --- the seam: git, aimed at a remote or a scratch tree ----------------------------------------
def _git(args, cwd=None, env=None):
    """(code, stdout, stderr) for a git call."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def foreign_env():
    """The environment for a git call aimed elsewhere: git's own local vars dropped.

    A hook exports GIT_DIR, and git ignores `-C` and `cwd` once it is set, so a call aimed at a
    fixture would answer about the repository the caller is in (house contract 12).
    """
    code, out, _ = _git(["rev-parse", "--local-env-vars"])
    drop = {line.strip() for line in out.splitlines()} if code == 0 else set()
    env = dict(os.environ)
    for key in [key for key in env if key in drop]:
        del env[key]
    return env


def _last(text):
    """The last line of a git message, or the whole of it when it is one line."""
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""


# --- the resolution: what the pin is, and what it resolves to ----------------------------------
def resolve_pin(url, revision, env):
    """(kind, error): what kind of pin this revision is, according to the remote it names.

    A name under refs/heads is a branch, a name under refs/tags is a tag, and a commit id is a
    commit. The name is never the judge on its own: a branch called `d93499bb` is a branch, and
    a commit id the remote does not have is a pin of nothing.
    """
    code, out, errout = _git(["ls-remote", "--heads", "--tags", url, revision], env=env)
    if code != 0:
        return "none", f"the remote could not be read ({_last(errout)})"
    for line in out.splitlines():
        _, _, ref = line.partition("\t")
        ref = ref.strip()
        if ref in (f"refs/heads/{revision}", f"refs/heads/{revision}^{{}}"):
            return "branch", ""
        if ref in (f"refs/tags/{revision}", f"refs/tags/{revision}^{{}}"):
            return "tag", ""
    if COMMIT.match(revision):
        return "commit", ""
    return "none", "no branch, no tag and no commit on the remote carries that name"


def fetch_commit(url, revision, work, env):
    """(commit, error): the commit the pin resolves to, fetched so its tree can be read."""
    code, _, errout = _git(["fetch", "--depth", "1", url, revision], cwd=work, env=env)
    if code != 0:
        return None, f"it could not be fetched ({_last(errout)})"
    code, out, _ = _git(["rev-parse", "FETCH_HEAD"], cwd=work, env=env)
    if code != 0:
        return None, "the fetched commit could not be named"
    return out.strip(), ""


def read_at(work, commit, path, env):
    """The text of a file at a commit, or None when the commit does not carry it."""
    code, out, _ = _git(["show", f"{commit}:{path}"], cwd=work, env=env)
    return out if code == 0 else None


def zephyr_line(manifest, remotes, work, env):
    """(line, error): the Zephyr line the resolved manifest names.

    The manifest names the zephyr project at a version (`v3.5.0+zmk-fixes`) or at a commit. A
    commit is read where it is: the zephyr tree at that commit carries the version in its VERSION
    file, and the version is read THERE, not from a working tree.
    """
    remote, revision = manifest_project(manifest, "zephyr")
    if not revision:
        return None, "the resolved manifest names no zephyr revision"
    version = VERSION.match(revision)
    if version:
        return version.group("line"), ""
    if COMMIT.match(revision):
        base = remotes.get(remote)
        if not base:
            return None, f"the resolved manifest names the zephyr remote '{remote}', which it lacks"
        commit, error = fetch_commit(f"{base.rstrip('/')}/zephyr", revision, work, env)
        if error:
            return None, f"the zephyr pin could not be resolved ({error})"
        text = read_at(work, commit, ZEPHYR_VERSION, env)
        if text is None:
            return None, f"the zephyr commit {commit[:7]} carries no {ZEPHYR_VERSION} file"
        version = VERSION.match(text.strip())
        if version:
            return version.group("line"), ""
        return None, f"the zephyr commit {commit[:7]} names no Zephyr version"
    return None, f"the resolved manifest names zephyr at '{revision}', which carries no Zephyr version"


# --- the findings -----------------------------------------------------------------------------
def resolve(root):
    """(facts, findings): what the pin is, and what makes this gate red."""
    facts = {}
    found = []
    west_path = os.path.join(root, WEST)
    if not os.path.isfile(west_path):
        return facts, [f"{WEST} is missing -- the scan lost its subject"]
    with open(west_path, encoding="utf-8") as handle:
        remote, url_base, revision = west_pin(handle.read())
    if not revision:
        return facts, [f"{WEST} pins no zmk revision"]
    if not url_base:
        who = f"the remote '{remote}'" if remote else "its remote"
        return facts, [f"{WEST} pins the zmk project at {who}, and the manifest gives it no url"]
    url = f"{url_base.rstrip('/')}/{PROJECT}"
    facts = {"url": url, "revision": revision}
    env = foreign_env()
    with tempfile.TemporaryDirectory(prefix="zmk-pin-") as work:
        _git(["init", "-q", work], env=env)
        kind, error = resolve_pin(url, revision, env)
        commit = None
        if not error:
            commit, error = fetch_commit(url, revision, work, env)
        if error:
            return facts, [f"{WEST} pins '{revision}', and {error}"]
        facts["kind"] = kind
        facts["commit"] = commit
        manifest = read_at(work, commit, IMPORTED, env)
        if manifest is None:
            return facts, [f"the manifest {IMPORTED} could not be read at {commit[:7]}"]
        line, error = zephyr_line(manifest, manifest_remotes(manifest), work, env)
        if error:
            return facts, [f"{WEST} pins '{revision}' at {commit[:7]}, and {error}"]
        facts["line"] = line
        code, out, _ = _git(["show", "-s", "--format=%cI", commit], cwd=work, env=env)
        try:
            facts["date"] = datetime.fromisoformat(out.strip()) if code == 0 else None
        except ValueError:
            facts["date"] = None

    tags = image_tags(root)
    if not tags:
        return facts, [f"no FROM in {DOCKERFILE} and no image: in {WORKFLOWS} -- the scan lost its subject"]
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
    return facts, found


def problems(root):
    """The structural findings: what makes this gate red."""
    return resolve(root)[1]


def local_base(root):
    """(when, sha) the local build baked, or (None, None): the newest keymap-build stamp.

    The build gate writes one stamp per build it made, and the stamp carries the base the image
    baked -- the commit `west update` fetched when the image was built. A MOVING pin means the
    local build's base and the head CI builds are two different facts, and the gap between them is
    what the owner is asked to rule on.
    """
    common = _git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=root)
    if common[0]:
        return None, None
    stamps = os.path.join(common[1].strip(), "keymap-build-stamps")
    names = os.listdir(stamps) if os.path.isdir(stamps) else []
    entries = [os.path.join(stamps, n) for n in names
               if not n.endswith(".log") and not n.startswith("stage.")]
    if not entries:
        return None, None
    newest = max(entries, key=os.path.getmtime)
    try:
        with open(newest, encoding="utf-8") as handle:
            fields = handle.read().split()
    except OSError:
        return None, None
    return (fields[0] if fields else None, fields[1] if len(fields) > 1 else None)


# --- the report -------------------------------------------------------------------------------
def report(root, facts):
    """Say what the pin is and how far it has moved. Warnings, never a red gate."""
    commit = facts.get("commit") or ""
    dated = facts.get("date")
    when = dated.strftime("%Y-%m-%d") if dated else "an unknown date"
    kind = facts.get("kind")
    if kind == "commit":
        ok(
            f"zmk base: {facts['url']} is pinned at commit {commit[:7]} ({when}); a commit pin cannot "
            "move, so the build is reproducible"
        )
    elif kind == "tag":
        warn(
            f"zmk base: {facts['url']} {facts['revision']} is a TAG ({commit[:7]}, {when}); its "
            "maintainer can re-point it, so the build is not reproducible"
        )
    else:
        warn(
            f"zmk base: {facts['url']} {facts['revision']} is a MOVING branch (head {commit[:7]}, "
            f"{when}); west update builds whatever its head was"
        )
    stamp = None
    for tag in image_tags(root):
        parsed = TAG.match(tag)
        if parsed:
            stamp = datetime.strptime(parsed.group("stamp"), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            break
    if stamp and dated and dated > stamp:
        warn(
            f"zmk base: the pin's commit {commit[:7]} ({when}) is newer than the build image "
            f"({stamp.strftime('%Y-%m-%d')}); CI builds the pin, the local image builds the copy "
            "baked into it"
        )
    built, baked = local_base(root)
    if not baked:
        warn("zmk base: the local build's base is not recorded (no keymap build stamp found)")
    elif baked == commit:
        ok(f"zmk base: the local build's base is {baked[:7]} too -- the same base CI builds")
    else:
        warn(
            f"zmk base: the local build's base is {baked[:7]} (built {built}), the pin resolves to "
            f"{commit[:7]} ({when}); the local image is behind the pin"
        )


def run(root):
    facts, found = resolve(root)
    for line in found:
        err(f"zmk base: {line}")
    if found:
        return 1
    report(root, facts)
    ok(f"zmk base: the pinned base is Zephyr {facts['line']} and the build image builds that line")
    return 0


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
    path = os.path.join(root, "remote", PROJECT)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    env = foreign_env()
    _git(["init", "-q", "-b", "base", path], env=env)
    for branch, zephyr in BASES:
        _write(os.path.join(path, "app", "west.yml"),
               _manifest("zmkfirmware", "https://github.com/zmkfirmware", "zephyr", zephyr, "app"))
        _git(["add", "-A"], cwd=path, env=env)
        _git(["-c", "user.name=gate", "-c", "user.email=gate@example.invalid",
              "commit", "-q", "-m", branch], cwd=path, env=env)
        _git(["branch", "-f", branch], cwd=path, env=env)
    return {b: _git(["rev-parse", b], cwd=path, env=env)[1].strip() for b, _ in BASES}


def _fixture(root, url_base, revision, dockerfile, workflow):
    """Write the tree a fixture is: the manifest, the Dockerfile and the workflow."""
    if revision is not None:
        _write(os.path.join(root, WEST),
               _manifest("refil", url_base, PROJECT, revision, "config", "      import: app/west.yml\n"))
    _write(os.path.join(root, DOCKERFILE), dockerfile)
    _write(os.path.join(root, ".github", "workflows", "build.yml"), workflow)


def probe():
    """Each defect in the docstring goes red alone; the clean fixture is green."""
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
            "a branch whose name looks like a commit": ("d93499bb", dockerfile, workflow, False),
            # The line comes from the manifest at the PINNED commit: this one names another line.
            "a commit pin on another Zephyr line": (commits["other"], dockerfile, workflow, True),
            "a commit the remote does not have": ("0" * 40, dockerfile, workflow, True),
            "a revision that names nothing": ("no-such-pin", dockerfile, workflow, True),
            "the resolved manifest names no Zephyr version": ("noline", dockerfile, workflow, True),
            # ONE pin, on another Zephyr line than the base: the Dockerfile and the CI job agree,
            # and the pair is still wrong. (The case below this one is a different defect: two pins.)
            "the image is on another Zephyr line": (GOOD_REVISION, other_dockerfile, other_workflow, True),
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
                red = bool(problems(root))
            if red != want_red:
                failed.append(
                    f"{name}: expected {'red' if want_red else 'green'}, got {'red' if red else 'green'}"
                )
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
