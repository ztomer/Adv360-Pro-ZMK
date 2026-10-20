#!/usr/bin/env bash
# Per-repo gate entry point. Declares which toolchains this repo contains and
# delegates; it holds no gate logic of its own.
#   --staged : pre-commit scope (fast) — layer 1 only
#   --full   : pre-push scope — every layer
set -euo pipefail
GOH="${GOH_DIR:-${GOH:-$HOME/Projects/gates_of_heck}}"

# Informational flags never reach the gates below.
case "${1:-}" in
  -h|--help)
    echo "usage: gate.sh [--staged | --full | --doctor [repo] | --help]"
    exit 0 ;;
  --doctor)  exec bash "$GOH/gates/doctor.sh" "${2:-$PWD}" ;;
esac

"$GOH/gates/structural.sh" "$@"

case "${1:-}" in
  --full)
    # Layer 2: the steps .gatesrc declares (GOH_CI_STEPS), run by the house's local_ci.sh --
    # the same runner the pre-push hook's gate uses, and the one CI's proof job mirrors. The
    # list lives in ONE place (.gatesrc), so a step added here runs in CI too, and a step added
    # ONLY in CI is what the house's CI/local parity check refuses.
    exec "$GOH/gates/local_ci.sh" "$(git rev-parse --show-toplevel)"
    ;;
esac
