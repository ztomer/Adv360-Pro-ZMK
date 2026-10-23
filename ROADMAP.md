# Roadmap

The one forward-looking plan for this fork. Closed work lives in git history; this file
keeps only what someone could pick up tomorrow. `README.md`, `UPGRADE.md` and
`CHANGELOG.md` are upstream (Kinesis) reference docs, not plans. The 2026-10-12 consolidation
record is `git show 79ade96:ROADMAP.md` ("Sources consolidated"). Item ids are stable across
rephasing: a P0.x item now sits in Phase 1.

## Context (measured 2026-10-20; gate, CI and upstream re-measured 2026-10-20)

- Personal fork of `KinesisCorporation/Adv360-Pro-ZMK`, branch `V3.0`. The fork patch is ONE
  commit (`7a19473`) on top of `upstream/V3.0` (`97f5d73`, unmoved on 2026-10-20); the
  commits after it are this plan, gates, hooks and CI/build pins: 0 behind upstream.
- What the fork changes: `config/adv360.keymap` (personal keymap), the README keymap and
  host-chord tables, house gates (`.gatesrc`, `tools/`, `.githooks/`), the build-image pin
  (`Dockerfile`, `Makefile`, CI), and in `.github/workflows/build.yml`
  `persist-credentials: false`, `runs-on: ubuntu-26.04`, actions at named releases, and the
  `Gate proofs` job. Every other file is upstream's.
- Firmware builds on GitHub Actions (two jobs, Legacy and Clique) and locally via `make`
  (Docker or Podman). CI run 39421244616 (2026-10-20, `378b07e`) is green with no
  annotations: the two firmware jobs upload their artifacts, and the third job runs the proofs.
- Local gate: goh 0.42.0 from `~/Projects/gates_of_heck` (`v0.32.0-18-g1f951ac`), stock
  hooks. `tools/gate.sh --full` runs goh's structural layer, then the house's
  `gates/local_ci.sh` over the step list `.gatesrc` declares (`GOH_CI_STEPS`): every gate's
  self-proof (`tools/run_proofs.sh`), the repo gates (`tools/repo_gates.sh`: the build-image
  pin, the README remap tables derived from the keymap's diff against upstream, the README
  host-chord table, the one keymap source, the ZMK base pin against the build image -- the
  pin's kind is resolved against the remote and named, and the Zephyr line is read from the
  resolved manifest -- and a build of both halves in the pinned image, cached by the content
  of `config/`), and the house's CI/local parity check. The build is about 20 s warm on arm64
  colima.
- CI runs the SAME proofs on every push: the `Gate proofs` job checks the gate harness out
  beside the repo and runs `tools/run_proofs.sh`. The fork's gate is therefore in CI, not only
  on the maintainer's machine, and a push cannot be made with a broken proof.
- Every gate carries a red-before/green-after proof, and `tools/check_probe_bite.py` keeps
  them biting: it plants each gate's pre-fix defect into a COPY of the gate and requires the
  gate's own proof to go red. `tools/check_gate_wiring.py` keeps every gate wired into the
  sequencer, keeps a swallowed failure from passing, and keeps CI running the proofs.
- Host software: no Hammerspoon is installed. The app that answers the keyboard's host
  chords is ZoneWM v2 (the native rewrite of the public ZoneTilerWM); it reads
  `~/.config/zonewm/config.toml`, where `HYPER` is Shift+Ctrl+Option+Cmd.
- ZMK base: the Kinesis fork `refil/zmk` at `adv360-z3.5-2` (Zephyr 3.5), head `d93499bb`
  (2026-08-27, unmoved since). The pinned image (`3.5-branch-20250930025731`) is the newest
  `3.5-branch` image ZMK publishes, and it carries no ZMK copy of its own: the copy is
  fetched by this repo's Dockerfile. See P1.3 for what that means for the two builds.

## Rulings (standing)

- **R1 (2026-10-11, `7a19473`).** The fork is a single patch on top of upstream history.
  The 2026-09-04 flatten broke the shared history (no merge-base; GitHub read
  "3 ahead / 108 behind"). Do not flatten again; to sync, fetch upstream and replay the patch.
- **R2 (2026-10-08).** Every `actions/checkout` sets `persist-credentials: false`, so the job
  token never stays in git config. The goh structural gate enforces this.
- **R3 (2026-10-11).** The goh install receipts (`.githooks/.goh-installed/*.sha256`) stay
  on the local machine and are never committed.
- **R4 (2026-10-19).** The software that answers a host chord is recorded in
  `tools/check_host_software.py` (`HOST_SOFTWARE`) and named in README.md's "Host chords"
  table. The two change together, in one commit: the table is the record, the README is the
  prose about it. A chord with nothing behind it is a bug, not a configuration choice.
- **R5 (2026-10-21; RULED 2026-10-23: Option B, follow Kinesis).** The ZMK base pin is
  either a BRANCH (`adv360-z3.5-2`, a name Kinesis moves) or a COMMIT (a sha, a pin nothing
  can move). The owner ruled Option B (2026-10-23: "follow kinesis"): keep the branch
  (`adv360-z3.5-2`). The build follows Kinesis: every upstream fix arrives on the next build,
  and `config/west.yml` stays byte-identical to upstream's. The gate reports the head, its date,
  and the base the local image baked on every run (`tools/check_zmk_base.py`).
- **Non-goal: Rust.** `RUSTIFICATION_ROADMAP.md` §6 (2026-09-25) lists this repo as
  "explicitly not Rust" because it is ZMK devicetree. Revisit only if the platform changes.

## Phase 1: live defects and gate holes (size S-M, one session)

Goal: CI has no deprecation warnings, every pin is a named release, the README describes
the keymap that is actually flashed, and a broken keymap fails before it is pushed.
Exit: all P0 items meet their acceptance tests, the CI run on the last commit is green and
has no annotations, and the P0.5 gate has been shown to go red.

- **P0.4 The documented helper software is not what runs (BLOCKED on the owner).** The
  software is now named correctly and a gate keeps it named: README.md's "Host chords" table
  and `tools/check_host_software.py` (in `repo_gates.sh`, `--probe` self-proof) say that
  ZoneWM v2 answers `HYP(MINUS)` (window hints), `HYP(F1)` (Gemini) and `HYP(F2)` (Claude).
  Hammerspoon is no longer recommended and no row names it; the README mentions the public
  ZoneTilerWM once, as ZoneWM's Lua/Hammerspoon predecessor, and the keymap comment above
  `VIMPOSE` names ZoneWM too. What no gate can do is press the key. The owner
  must confirm on the machine that (2) Macro once opens ZoneWM's window hints, that (4)
  Macro once opens Gemini and twice opens Claude, and that Karabiner still maps CAPSLOCK
  to FN. If a chord does nothing, the fix is a rebind in `config/adv360.keymap`, and the
  README and `HOST_SOFTWARE` change with it.
  *Accept:* the owner reports what the three chords do on the real keyboard.

## Phase 2: fork hygiene and drift (size S, one session)

Goal: the fork's own pins are the ones the build uses, and what moves upstream is reported
by a tool rather than remembered.
Exit: P1.3 has a ruling, and the ruling is in the tree.

- **P1.3 The base pin is a moving branch, so the build is not reproducible.** MEASURED
  2026-10-20, so the owner can rule in a minute:

  - **What CI builds.** `west update` resolves the branch per run: `refil/zmk`
    `adv360-z3.5-2` = `d93499bb877f2711989e6cbbe1feed9e9a792ca3`, committed 2026-08-27
    21:46:27 +0100 ("Fallback to trans if possible"). It has not moved since (54 days).
  - **What a local build builds.** The pinned image
    `zmkfirmware/zmk-build-arm:3.5-branch-20250930025731` (created 2025-09-30) carries NO
    ZMK copy of its own -- it is the Zephyr 3.5 SDK and nothing else (measured: no `/zmk` in
    it). The copy is fetched by THIS repo's Dockerfile (`RUN west update`), so the base a
    local build uses is the branch head as of the last image build, and the image is not
    rebuilt until `config/` changes (the build gate caches on the content of `config/`, and
    docker caches the `west update` layer on `config/west.yml` besides). Measured: the local
    image `adv360-zmk-gate` (built 2026-10-17) bakes `d93499bb` -- the same commit CI
    resolves. **So today the two builds differ by 0 commits.** The difference is the policy:
    CI resolves the branch per run, the local image freezes it at the last build. The branch
    moved 6 times in the last 12 months (492 commits in 2024, 37 in 2025, 6 in 2026, none
    since 2026-08-27), so the next move is a local build that is silently behind, until
    `config/` changes.
  - **What a commit pin would change.** `git fetch <url> <sha>` works on GitHub (measured on
    this branch's head), so `west update` can take a sha. The costs, all measured:
    (a) the fork's `config/west.yml` stops being byte-identical to upstream's -- it IS
    identical today (`git diff upstream/V3.0 -- config/west.yml` is empty) -- so the fork
    patch gains a second hunk and every upstream sync (R1) has to re-pin;
    (b) Kinesis re-pins the branch NAME 4 times in 3.6 years (2022-09, 2024-01, 2024-04,
    2025-02; the current name has stood 20 months), so tracking Kinesis is about 1.1
    re-pins a year, each costing a re-pin plus a full rebuild of both halves (the image's
    `west update` layer is invalidated by the change: about 6 minutes measured);
    (c) upstream ZMK fixes reach the fork only when the pin is moved, so "follows Kinesis"
    becomes "follows Kinesis when someone moves the pin";
    (d) the gate could not EXPRESS a sha pin (CLOSED 2026-10-21, see below): it read the
    Zephyr line out of the revision NAME (`adv360-z3.5-2`), so a sha was "a revision that
    names no Zephyr line" and the gate went red before its own commit-pin branch could run.
  - **The gate can now express either pin (2026-10-21).** `tools/check_zmk_base.py` resolves
    the pin against the remote it names: the KIND is what the remote says (a name under
    `refs/heads` is a branch, a name under `refs/tags` is a tag, a commit id is a commit --
    never the name alone, so a branch called `d93499bb` is a branch and a commit nobody has is
    a pin of nothing), and the Zephyr LINE is read from the RESOLVED MANIFEST -- the manifest
    the resolved commit carries (`app/west.yml` at that commit), not the revision's name, not a
    working tree, not a copy of the pin. A resolution that fails is named, never a silent
    green. The kind of pin is reported on every run.
    *Red-before/green-after:* the gate as it was (`git show <parent>:tools/check_zmk_base.py`)
    went RED on a commit pin -- "a revision that names no Zephyr line" -- and the gate as it
    is now is GREEN on the same pin, and RED on a revision that names nothing at all.
  - **The tool reports it.** `tools/check_zmk_base.py` reports the kind of pin, the head (or
    the commit), its date, and the base the local build actually baked (the build gate writes
    that commit into its stamp), on every gate run -- so the gap is read, not remembered.

  *Ruling:* Option B ruled by owner on 2026-10-23 ("follow kinesis"). Keep the branch
  `adv360-z3.5-2` in `config/west.yml` (byte-identical to upstream); `tools/check_zmk_base.py`
  monitors and reports the head and baked base on every gate run. CLOSED.

## Phase 3: parked, waiting on upstream

- **P2.1 ZMK base is Zephyr 3.5.** `config/west.yml` pins `refil/zmk` `adv360-z3.5-2`.
  ZMK images exist for Zephyr 4.1 and 4.4. Moving to base ZMK would lose the 360 Pro
  indicator LEDs (README "Note"), so this follows Kinesis. This is a stated exception to
  the cutting-edge rule, not a silent lag.
  *Measured 2026-10-20:* the trigger has NOT fired, so the base does not move today.
  `refil/zmk` has no newer `adv360-z*` branch (`adv360-z3.5-2`, head `d93499bb`, is the
  newest); Kinesis's own `V3.0` (`97f5d73`, 2026-06-14) still pins `adv360-z3.5-2`; the
  pinned image is the newest `3.5-branch` image ZMK publishes (ZMK stopped publishing them
  on 2025-09-30). What changed is that the state is no longer remembered:
  `tools/check_zmk_base.py` fails if the pinned base and the build image stop being the
  same Zephyr line, and reports the head, its date, and the base the local build baked, on
  every gate run.
  *Trigger:* `upstream/V3.0` gets a newer adv360 branch. `tools/check_upstream_drift.sh`
  (run by every gate) reports it; then re-pin the build image (`Dockerfile`, both CI jobs)
  to match.
