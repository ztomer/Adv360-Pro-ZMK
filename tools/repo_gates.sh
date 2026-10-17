#!/usr/bin/env bash
# repo_gates.sh -- layer 3 of tools/gate.sh: the checks that only this repo can make.
#
#   tools/repo_gates.sh     # run every repo-local gate against the working tree
#
# Each check is its own tools/check_* script with a --probe self-proof, which goh's structural
# step "gate self-proofs still pass" runs on every push; this file only sequences them.
set -euo pipefail
GOH="${GOH_DIR:-${GOH:-$HOME/Projects/gates_of_heck}}"
# shellcheck source=/dev/null
. "$GOH/tui/lib.sh"
cd "$(git rev-parse --show-toplevel)"

info "repo gates"
bash "$GOH/gates/python.sh" tools/check_image_pin.py
bash "$GOH/gates/python.sh" tools/check_readme_keymap.py
