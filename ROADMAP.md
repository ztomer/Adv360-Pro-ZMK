# Roadmap

The one forward-looking plan for this fork. Closed work lives in git history; this file
keeps only what someone could pick up tomorrow. `README.md`, `UPGRADE.md` and
`CHANGELOG.md` are upstream (Kinesis) reference docs, not plans. The 2026-10-12 consolidation
record is `git show 79ade96:ROADMAP.md` ("Sources consolidated"). Item ids are stable across
rephasing: a P0.x item now sits in Phase 1.

## Context (measured 2026-10-19; gate, CI and upstream re-measured 2026-10-19)

- Personal fork of `KinesisCorporation/Adv360-Pro-ZMK`, branch `V3.0`. The fork patch is ONE
  commit (`7a19473`) on top of `upstream/V3.0` (`97f5d73`, unmoved on 2026-10-19); the
  commits after it are this plan, gates, hooks and CI/build pins: 0 behind upstream.
- What the fork changes: `config/adv360.keymap` (personal keymap), the README keymap and
  host-chord tables, house gates (`.gatesrc`, `tools/`, `.githooks/`), the build-image pin
  (`Dockerfile`, `Makefile`, CI), and in `.github/workflows/build.yml`
  `persist-credentials: false`, `runs-on: ubuntu-26.04` and actions at named releases.
  Every other file is upstream's.
- Firmware builds on GitHub Actions (two jobs, Legacy and Clique) and locally via `make`
  (Docker or Podman). CI run 39335380855 (2026-10-19, `c1197ff`) is green with no
  annotations, and both jobs upload their artifacts.
- Local gate: goh 0.41.0 from `~/Projects/gates_of_heck` (`v0.32.0-16-g16e3119`), stock
  hooks. `tools/gate.sh --full` runs goh's structural layer, then `tools/repo_gates.sh`: the
  build-image pin, the README remap tables (derived from the keymap's diff against upstream),
  the README host-chord table (derived from the keymap), the one keymap source, the ZMK base
  pin against the build image, and a build of both halves in the pinned image, cached by the
  content of `config/` (about 20 s warm on arm64 colima).
- Host software: no Hammerspoon is installed. The app that answers the keyboard's host
  chords is ZoneWM v2 (the native rewrite of the public ZoneTilerWM); it reads
  `~/.config/zonewm/config.toml`, where `HYPER` is Shift+Ctrl+Option+Cmd.
- ZMK base: the Kinesis fork `refil/zmk` at `adv360-z3.5-2` (Zephyr 3.5), head `d93499bb`
  (2026-08-27). The pinned image (`3.5-branch-20250930025731`) is the newest `3.5-branch`
  image ZMK publishes.

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
  ZoneWM v2 answers `HYP(MINUS)` (window hints), `HYP(F1)` (Gemini) and `HYP(F2)` (Claude);
  Hammerspoon and the Hammerspoon-era ZoneTilerWM are gone from the README, and the keymap
  comment above `VIMPOSE` names ZoneWM too. What no gate can do is press the key. The owner
  must confirm on the machine that (2) Macro once opens ZoneWM's window hints, that (4)
  Macro once opens Gemini and twice opens Claude, and that Karabiner still maps CAPSLOCK
  to FN. If a chord does nothing, the fix is a rebind in `config/adv360.keymap`, and the
  README and `HOST_SOFTWARE` change with it.
  *Accept:* the owner reports what the three chords do on the real keyboard.
- **P0.5 Every gate keeps a red-before/green-after proof that runs on every push.** The
  house gate runs each `tools/check_*.py --probe` ("gate self-proofs still pass") and every
  gate against an empty tree ("gates refuse to pass over an empty tree"); the host-software
  and base-pin checks carry 15 and 8 fixtures, each defect red and the clean tree green. A
  new check without a probe is not a check.

## Phase 2: fork hygiene and drift (size S, one session)

Goal: the fork's own pins are the ones the build uses, and what moves upstream is reported
by a tool rather than remembered.
Exit: P1.3 has a ruling, and the ruling is in the tree.

- **P1.3 The base pin is a moving branch, so the build is not reproducible.** Measured
  2026-10-19: `config/west.yml` pins `refil/zmk` at the BRANCH `adv360-z3.5-2`, so `west
  update` builds whatever the branch head was when the build ran. CI builds the head
  (`d93499bb`, 2026-08-27); a local `make` builds the copy baked into the pinned image
  (2025-09-30) and keeps it for as long as `config/` does not change.
  `tools/check_zmk_base.py` reports the head and the gap on every gate run, and refuses a
  base and an image that are not the same Zephyr line.
  *Decision needed:* pinning the revision to a commit sha makes the build reproducible and
  costs the fork its "follows Kinesis's branch" property, because upstream's
  `config/west.yml` pins the branch. That is the owner's ruling, not a cleanup.
  *Trigger:* the owner rules on it, or upstream re-pins `adv360-z3.5-2` to a commit, in
  which case follow it.

## Phase 3: parked, waiting on upstream

- **P2.1 ZMK base is Zephyr 3.5.** `config/west.yml` pins `refil/zmk` `adv360-z3.5-2`.
  ZMK images exist for Zephyr 4.1 and 4.4. Moving to base ZMK would lose the 360 Pro
  indicator LEDs (README "Note"), so this follows Kinesis. This is a stated exception to
  the cutting-edge rule, not a silent lag.
  *Measured 2026-10-19:* the trigger has NOT fired, so the base does not move today.
  `refil/zmk` has no newer `adv360-z*` branch (`adv360-z3.5-2`, head `d93499bb`, is the
  newest); Kinesis's own `V3.0` (`97f5d73`, 2026-06-14) still pins `adv360-z3.5-2`; the
  pinned image is the newest `3.5-branch` image ZMK publishes (ZMK stopped publishing them
  on 2025-09-30). What changed is that the state is no longer remembered:
  `tools/check_zmk_base.py` fails if the pinned base and the build image stop being the
  same Zephyr line, and reports the head's drift from the image on every gate run.
  *Trigger:* `upstream/V3.0` gets a newer adv360 branch. `tools/check_upstream_drift.sh`
  (run by every gate) reports it; then re-pin the build image (`Dockerfile`, both CI jobs)
  to match.
