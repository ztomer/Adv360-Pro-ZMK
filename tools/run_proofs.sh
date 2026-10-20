#!/usr/bin/env bash
# run_proofs.sh -- run every gate's self-proof, in this tree, on every push.
#
#   tools/run_proofs.sh            # run every tools/check_* self-proof
#
# WHY. A gate's self-proof is the only thing that says the gate can still fail. The house layer
# runs them locally (gates_of_heck's "gate self-proofs still pass"), and CI runs them here, so a
# proof that stopped biting is red on a push that a maintainer did not make -- and no push can be
# made with a broken proof, because the proof is what the push runs.
#
# Every gate under tools/ is run, in the order the files sort, and EVERY one runs even after one
# goes red: a run that names every red is worth more than a run that stops at the first.
#
# Seams: GOH_DIR names the shared gate harness (the checks import its tui/lib);
# GATE_PROOF_TIMEOUT is the per-proof ceiling in seconds.
set -euo pipefail
GOH="${GOH_DIR:-${GOH:-$HOME/Projects/gates_of_heck}}"
TIMEOUT="${GATE_PROOF_TIMEOUT:-180}"
cd "$(git rev-parse --show-toplevel)"

if [ ! -f "$GOH/gates/python.sh" ]; then
    echo "run_proofs: no gate harness at $GOH -- set GOH_DIR to a gates_of_heck checkout" >&2
    exit 1
fi

# `timeout` is GNU; macOS ships gtimeout (coreutils) or nothing. A proof that hangs is worse than
# a proof that failed, so a ceiling is set when the platform has one and named when it does not.
CEILING=()
if command -v gtimeout >/dev/null 2>&1; then
    CEILING=(gtimeout "$TIMEOUT")
elif command -v timeout >/dev/null 2>&1; then
    CEILING=(timeout "$TIMEOUT")
else
    echo "run_proofs: no timeout(1) on this machine -- a proof that hangs will hang the run" >&2
fi

failed=()
count=0
for gate in tools/check_*.py tools/check_*.sh; do
    [ -f "$gate" ] || continue
    count=$((count + 1))
    case "$gate" in
        *.py) runner=(bash "$GOH/gates/python.sh" "$gate" --probe) ;;
        *) runner=(bash "$gate" --probe) ;;
    esac
    if [ "${#CEILING[@]}" -gt 0 ]; then
        "${CEILING[@]}" "${runner[@]}" || failed+=("$gate")
    else
        "${runner[@]}" || failed+=("$gate")
    fi
done

if [ "$count" -eq 0 ]; then
    echo "run_proofs: no gates under tools/ -- there is nothing to prove" >&2
    exit 1
fi
if [ "${#failed[@]}" -gt 0 ]; then
    echo "run_proofs: ${#failed[@]} of $count proof(s) failed: ${failed[*]}" >&2
    exit 1
fi
echo "run_proofs: $count proof(s) passed"
