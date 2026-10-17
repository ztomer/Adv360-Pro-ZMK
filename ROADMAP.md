# Roadmap

The one forward-looking plan for this fork. Closed work lives in git history; this file
keeps only what someone could pick up tomorrow. `README.md`, `UPGRADE.md` and
`CHANGELOG.md` are upstream (Kinesis) reference docs, not plans. The 2026-10-12 consolidation
record is `git show 79ade96:ROADMAP.md` ("Sources consolidated"). Item ids are stable across
rephasing: a P0.x item now sits in Phase 1.

## Context (measured 2026-10-12; gate and upstream re-measured 2026-10-14)

- Personal fork of `KinesisCorporation/Adv360-Pro-ZMK`, branch `V3.0`. The fork patch is ONE
  commit (`7a19473`) on top of `upstream/V3.0` (`97f5d73`, unmoved on 2026-10-17); the
  commits after it are this plan, gates, hooks and CI/build pins: 0 behind upstream.
- What the fork changes: `config/adv360.keymap` (personal keymap), the README keymap
  tables, house gates (`.gatesrc`, `tools/`, `.githooks/`), the build-image pin
  (`Dockerfile`, `Makefile`, CI), and in `.github/workflows/build.yml`
  `persist-credentials: false`, `runs-on: ubuntu-26.04` and actions at named releases.
  Every other file is upstream's.
- Firmware builds on GitHub Actions (two jobs, Legacy and Clique) and locally via
  `make` (Docker or Podman). The last CI run (38573181276, 2026-10-14, `dd31797`) is green.
- Local gate: goh stock hooks, reinstalled at goh 0.29.2 on 2026-10-17. `tools/gate.sh --full`
  runs goh's structural layer, then `tools/repo_gates.sh`: the build-image pin, the README
  remap tables (derived from the keymap's diff against upstream), and a build of both halves
  in the pinned image, cached by the content of `config/` (about 20 s warm on arm64 colima).
- ZMK base: the Kinesis fork `refil/zmk` at `adv360-z3.5-2` (Zephyr 3.5).

## Rulings (standing)

- **R1 (2026-10-11, `7a19473`).** The fork is a single patch on top of upstream history.
  The 2026-09-04 flatten broke the shared history (no merge-base; GitHub read
  "3 ahead / 108 behind"). Do not flatten again; to sync, fetch upstream and replay the patch.
- **R2 (2026-10-08).** Every `actions/checkout` sets `persist-credentials: false`, so the job
  token never stays in git config. The goh structural gate enforces this.
- **R3 (2026-10-11).** The goh install receipts (`.githooks/.goh-installed/*.sha256`) stay
  on the local machine and are never committed.
- **Non-goal: Rust.** `RUSTIFICATION_ROADMAP.md` §6 (2026-09-25) lists this repo as
  "explicitly not Rust" because it is ZMK devicetree. Revisit only if the platform changes.

## Phase 0: wire in goh 0.27.0 (size S, one short session)

Goal: `tools/gate.sh --full` green at HEAD with every scanner floor set, the hooks commit
pushed, and the runner pinned before `ubuntu-latest` moves.
Exit: G0.1 proven both ways; `git push` passes the pre-push gate; `git status -s` empty.

- **G0.1 Set the scanner floors.** Closed `2f12587`.
- **G0.2 The install receipts are untracked noise (R3, was P1.4).** Closed `6f1a66a`:
  `/.githooks/.goh-installed/` is in `.gitignore`, and `git status -s` is empty after
  `install.sh .`. goh's Downstream text tells consumers to COMMIT the receipts; R3 is this
  repo's standing exception to that.
- **G0.3 Pin a named runner before 2026-10-19.** Closed `dd31797` (CI 38573181276 green).
- **G0.4 Push** G0.1 and G0.3. Closed `dd31797`.

## Phase 1: live defects and gate holes (size S-M, one session)

Goal: CI has no deprecation warnings, every pin is a named release, the README describes
the keymap that is actually flashed, and a broken keymap fails before it is pushed.
Exit: all P0 items meet their acceptance tests, the CI run on the last commit is green and
has no annotations, and the P0.5 gate has been shown to go red.

- **P0.2c The moving-image-tag class belongs in goh.** P0.2 pinned this repo's build image
  (`tools/check_image_pin.py` holds the one-pin invariant locally), but goh has no step that
  refuses a moving image tag (`:stable`, `:latest`, a bare `-branch`) in any repo. Not written
  from this repo's session because goh had another session committing on 2026-10-17.
  *Accept:* a goh structural step goes red on `image: x:stable` and green on `x:tag@sha256:...`.
- **P0.4 The documented helper software is not what runs (needs the user).** No Hammerspoon
  is installed (no `~/.hammerspoon`). The machine runs ZoneWM (Swift), not ZoneTilerWM
  (Lua/Hammerspoon), and both appear in the README's "Recommended supporting software".
  The (2) macro's single tap sends `HYP(MINUS)`, documented as "Hammerspoon Vim-Expose".
  A grep of ZoneWM `Sources` for a Hyper-Minus or expose binding was inconclusive.
  *Accept:* on the real machine, Hyper-Minus does something documented, or the key is
  rebound. The README names the software that actually serves each binding (`HYP(F1)`,
  `HYP(F2)`, `HYP(MINUS)`), and a key that does nothing is not left in place.

## Phase 2: fork hygiene and drift (size S, one session; after P0.2 and P0.3)

Goal: one source of truth for the keymap, upstream drift is reported by a tool rather than
remembered.
Exit: P1 acceptance tests pass.

- **P1.1 `config/keymap.json` is stale.** It is byte-identical to upstream (no diff over
  `97f5d73..HEAD`), while `config/adv360.keymap` is customized, so the two disagree.
  Decide (user ruling): delete it (the README's recommended editor reads `.keymap`), or
  regenerate it. Deleting widens the surface for conflicts with upstream.
  *Accept:* one source of truth, plus a check that fails if both files exist and disagree.

## Phase 3: parked, waiting on upstream

- **P2.1 ZMK base is Zephyr 3.5.** `config/west.yml` pins `refil/zmk` `adv360-z3.5-2`.
  ZMK images exist for Zephyr 4.1 and 4.4. Moving to base ZMK would lose the 360 Pro
  indicator LEDs (README "Note"), so this follows Kinesis. This is a stated exception to
  the cutting-edge rule, not a silent lag.
  *Trigger:* `upstream/V3.0` gets a newer adv360 branch. `tools/check_upstream_drift.sh` (run
  by every gate) reports it; then re-pin the build image (`Dockerfile`, both CI jobs) to match.
