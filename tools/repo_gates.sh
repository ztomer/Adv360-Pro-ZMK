#!/usr/bin/env bash
# repo_gates.sh -- layer 3 of tools/gate.sh: the checks that only this repo can make.
#
#   tools/repo_gates.sh     # run every repo-local gate against the working tree
#
# Each check is its own tools/check_* script with a --probe self-proof, which goh's structural
# step "gate self-proofs still pass" runs on every push; this file only sequences them. Every
# check runs even after one goes red, so one run names every red (a broken keymap fails both the
# README check and the build, and each says why).
set -euo pipefail
GOH="${GOH_DIR:-${GOH:-$HOME/Projects/gates_of_heck}}"
# shellcheck source=/dev/null
. "$GOH/tui/lib.sh"
cd "$(git rev-parse --show-toplevel)"

info "repo gates"
failed=()
bash "$GOH/gates/python.sh" tools/check_image_pin.py || failed+=("image pin")
bash "$GOH/gates/python.sh" tools/check_readme_keymap.py || failed+=("readme keymap")
bash "$GOH/gates/python.sh" tools/check_keymap_source.py || failed+=("keymap source")
bash "$GOH/gates/python.sh" tools/check_host_software.py || failed+=("host software")
bash "$GOH/gates/python.sh" tools/check_zmk_base.py || failed+=("zmk base")
tools/check_keymap_build.sh || failed+=("keymap build")
# Upstream drift is reported, not blocking: upstream moving is not this commit's defect (P1.2).
tools/check_upstream_drift.sh || warn "repo gates: upstream drift is a sync to do (R1), not a push blocker"
if [ "${#failed[@]}" -gt 0 ]; then
    err "repo gates: ${#failed[@]} failed: ${failed[*]}"
    exit 1
fi
ok "repo gates: all passed"
