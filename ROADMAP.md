# Roadmap

The one forward-looking plan for this fork. Closed work lives in git history; this file
keeps only what someone could pick up tomorrow. `README.md`, `UPGRADE.md` and
`CHANGELOG.md` are upstream (Kinesis) reference docs, not plans. The 2026-10-12 consolidation
record is `git show 79ade96:ROADMAP.md` ("Sources consolidated"). Item ids are stable across
rephasing: a P0.x item now sits in Phase 1.

## Context (measured 2026-10-12; gate and upstream re-measured 2026-10-14)

- Personal fork of `KinesisCorporation/Adv360-Pro-ZMK`, branch `V3.0`. The fork patch is ONE
  commit (`7a19473`) on top of `upstream/V3.0` (`97f5d73`, unmoved on 2026-10-14); the
  commits after it are this plan, `.gatesrc`, hooks and the runner pin: 0 behind, 10 ahead.
- What the fork changes: `config/adv360.keymap` (personal keymap), the README keymap
  tables, house gates (`.gatesrc`, `tools/gate.sh`, `.githooks/`), and
  `persist-credentials: false` and `runs-on: ubuntu-26.04` in `.github/workflows/build.yml`.
  Every other file is upstream's.
- Firmware builds on GitHub Actions (two jobs, Legacy and Clique) and locally via
  `make` (Docker or Podman). The last CI run (38573181276, 2026-10-14, `dd31797`) is green.
- Local gate: goh 0.27.0 stock hooks (`79ade96`). `tools/gate.sh --full` runs the structural
  layer only and is GREEN at `dd31797` (1 s), every scanner floor set (`2f12587`). It does not
  build or parse the keymap (see P0.5).
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

- **P0.2 The build image is a moving tag.** `zmkfirmware/zmk-build-arm:stable` is used in
  `Dockerfile` and in both CI jobs, which violates the house "named release, never a moving
  tag" rule. On 2026-10-12 `stable` pointed at digest `sha256:edb1c953…`, last moved
  2025-10-03. Pin the tag that matches the Zephyr version of the ZMK branch (`3.5-branch`,
  digest `sha256:840526f0…`) by digest plus tag. Also fix `clean_image` in `Makefile`.
  *Accept:* `grep -rn ':stable' Dockerfile Makefile .github` finds nothing, CI is green, and a
  local `make` is green. *Risk:* a toolchain that does not match the branch breaks the
  build; CI proves it. *Class:* if goh has no check for moving image tags, add one there
  (everyone owns goh), not here.
- **P0.3 The README keymap table disagrees with the keymap.** Compared with upstream
  `97f5d73`:
  - The **Tab** key is `&mt HYPER GRAVE`, but the README says Tab is CAPSLOCK. The README's
    "Grave" row actually describes the Tab key's behaviour.
  - The **Grave** key is `&kp CAPS`.
  - The two **Ctrl** thumb keys became `LGUI`/`RGUI`, and the README does not mention it.
  - The rows for Caps-lock, Esc, Alt/Win, the macro keys, Kp and Fn match the keymap.

  *Accept:* every changed default-layer binding (diff of the `default_layer` block against
  `97f5d73`) has exactly one README row, and every README row names the right key. Best
  done as a small check that derives the remap list from that diff (feeds P1.2).
- **P0.4 The documented helper software is not what runs (needs the user).** No Hammerspoon
  is installed (no `~/.hammerspoon`). The machine runs ZoneWM (Swift), not ZoneTilerWM
  (Lua/Hammerspoon), and both appear in the README's "Recommended supporting software".
  The (2) macro's single tap sends `HYP(MINUS)`, documented as "Hammerspoon Vim-Expose".
  A grep of ZoneWM `Sources` for a Hyper-Minus or expose binding was inconclusive.
  *Accept:* on the real machine, Hyper-Minus does something documented, or the key is
  rebound. The README names the software that actually serves each binding (`HYP(F1)`,
  `HYP(F2)`, `HYP(MINUS)`), and a key that does nothing is not left in place.
- **P0.5 Gate hole: nothing local checks the keymap.** `pre-push` runs only structural
  checks, so a keymap that does not parse is pushed and only found by GitHub CI. The hook's
  comment "There is no CI behind this" is also false for this repo. Add
  `tools/repo_gates.sh` (layer 3 in `tools/gate.sh`). When `config/` changed, it builds both
  halves in the pinned image (P0.2). It must fail with a reason, never skip silently, when
  no container engine is running. Correct the hook comment in goh's template, not locally
  (still false in the 0.27.0 stock `pre-push:3`, re-read 2026-10-14).
  *Accept:* delete one `>` from `config/adv360.keymap`, and `tools/gate.sh --full` goes red
  naming the keymap. Restore it, and the gate goes green. *Risk:* a cold image build is
  slow (minutes), so cache the image and gate only on `config/` changes.

## Phase 2: fork hygiene and drift (size S, one session; after P0.2 and P0.3)

Goal: one source of truth for the keymap, upstream drift is reported by a tool rather than
remembered, and the build docs are true on Apple silicon.
Exit: P1 acceptance tests pass.

- **P1.1 `config/keymap.json` is stale.** It is byte-identical to upstream (no diff over
  `97f5d73..HEAD`), while `config/adv360.keymap` is customized, so the two disagree.
  Decide (user ruling): delete it (the README's recommended editor reads `.keymap`), or
  regenerate it. Deleting widens the surface for conflicts with upstream.
  *Accept:* one source of truth, plus a check that fails if both files exist and disagree.
- **P1.2 Upstream drift check (R1).** Add a script that fetches `upstream` and fails when
  `git rev-list --count HEAD..upstream/V3.0` is greater than 0. It is 0 today. Wire it as
  a warning in the gate, or run it on a schedule.
  *Accept:* run it against an older upstream ref, and it goes red with the count.
- **P1.3 Apple-silicon build advice is wrong.** The README says to use
  `colima start --arch x86_64`. The image is multi-arch: amd64 and arm64 are on Docker Hub
  for `stable`, `3.5` and `3.5-branch`. Forcing x86 emulation is unneeded and slower.
  *Accept:* `make` succeeds on native arm64 colima, and the README says so.

## Phase 3: parked, waiting on upstream

- **P2.1 ZMK base is Zephyr 3.5.** `config/west.yml` pins `refil/zmk` `adv360-z3.5-2`.
  ZMK images exist for Zephyr 4.1 and 4.4. Moving to base ZMK would lose the 360 Pro
  indicator LEDs (README "Note"), so this follows Kinesis. This is a stated exception to
  the cutting-edge rule, not a silent lag.
  *Trigger:* `upstream/V3.0` gets a newer adv360 branch. P1.2 detects that, then re-pin
  the image (P0.2) to match.
