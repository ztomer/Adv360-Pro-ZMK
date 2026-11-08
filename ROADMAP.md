# Roadmap

The one forward-looking plan for this fork. Closed work lives in git history (`git log`,
`git show 229f346:ROADMAP.md` for the 2026-10-12 consolidation); this file keeps only open work
and the rulings still in force. `README.md`, `UPGRADE.md` and `CHANGELOG.md` are upstream
(Kinesis) reference docs, not plans.

## Context

- Personal fork of `KinesisCorporation/Adv360-Pro-ZMK`, branch `V3.0`: ONE fork patch
  (`7a19473`) on top of `upstream/V3.0` (`97f5d73`), 0 behind upstream (re-measured 2026-11-08).
  The commits after the patch are this plan, the house gates (`.gatesrc`, `tools/`,
  `.githooks/`), and the build-image / CI pins.
- Firmware builds on GitHub Actions (Legacy and Clique jobs, plus a `Gate proofs` job) and locally
  via `make`. `tools/gate.sh --full` runs the whole gate, including a build of both halves in the
  pinned image.
- The app that answers the keyboard's host chords is ZoneWM v2, reading
  `~/.config/zonewm/config.toml`, where `HYPER` is Shift+Ctrl+Option+Cmd.
- ZMK base: the Kinesis fork `refil/zmk`, branch `adv360-z3.5-2` (Zephyr 3.5), followed per R5.

## Rulings in force

- **R1 (2026-10-11, `7a19473`).** The fork is a single patch on top of upstream history. The
  2026-09-04 flatten broke the shared history. Do not flatten again; to sync, fetch upstream and
  replay the patch. (`tools/check_upstream_drift.sh` reports drift on every gate run.)
- **R2 (2026-10-08).** Every `actions/checkout` sets `persist-credentials: false`; the goh
  structural gate enforces it.
- **R3 (2026-10-11).** The goh install receipts (`.githooks/.goh-installed/*.sha256`) stay on the
  local machine and are never committed.
- **R4 (2026-10-19).** The software that answers a host chord is recorded in
  `tools/check_host_software.py` (`HOST_SOFTWARE`) and named in README.md's "Host chords" table.
  The two change together, in one commit. A chord with nothing behind it is a bug, not a
  configuration choice.
- **R5 (2026-10-23, owner: "follow kinesis"; Option B).** The ZMK base pin stays the BRANCH
  `adv360-z3.5-2` in `config/west.yml`, byte-identical to upstream's, so every Kinesis fix arrives
  on the next build. `tools/check_zmk_base.py` reports the pin kind, the head, its date and the
  base the local image baked on every run. The cost accepted: the local image freezes the branch
  at its last build, so a local build can lag CI until `config/` changes.

## Phase 1: owner confirmation of the host chords

Why: the one open defect-shaped item; software and gate are in place, only the owner at the real
keyboard can close it.

- **P0.4 Host chords: confirm on the real keyboard (queue: OW.2; BLOCKED on the owner).**
  README.md's "Host chords" table and `tools/check_host_software.py` say ZoneWM v2 answers
  `HYP(MINUS)` (window hints), `HYP(F1)` (Gemini) and `HYP(F2)` (Claude). No gate can press the
  key. The owner confirms on the 360 Pro that (2) Macro once opens ZoneWM's window hints, that
  (4) Macro once opens Gemini and twice opens Claude, and that Karabiner still maps CAPSLOCK to
  FN. If a chord does nothing, the fix is a rebind in `config/adv360.keymap`, and the README and
  `HOST_SOFTWARE` change with it (R4).
  *Done when:* the owner reports what the three chords do on the real keyboard; for any that do
  nothing, a rebind commit exists and `python3 tools/check_host_software.py` is green with the
  README table matching.

## Phase 2: parked, waiting on upstream

Why: trigger-gated; nothing to do until Kinesis moves, and the gate reports when it does.

- **P2.1 ZMK base is Zephyr 3.5 (trigger: `upstream/V3.0` gets a newer adv360 branch).**
  `config/west.yml` pins `refil/zmk` `adv360-z3.5-2`; ZMK images exist for Zephyr 4.1 and 4.4,
  but base ZMK would lose the 360 Pro indicator LEDs (README "Note"), so this follows Kinesis, a
  stated exception to the cutting-edge rule. Not fired as of 2026-11-08: `refil/zmk` has no
  newer `adv360-z*` branch, and the pinned image (`3.5-branch-20250930025731`) is the newest
  `3.5-branch` image ZMK publishes. On the trigger, re-pin the build image (`Dockerfile`, both CI
  jobs) to the new Zephyr line.
  *Done when:* `config/west.yml` and the build image name the same new Zephyr line,
  `python3 tools/check_zmk_base.py` is green, `tools/gate.sh --full` builds both halves, and CI
  on the commit is green.
