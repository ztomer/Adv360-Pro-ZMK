#!/usr/bin/env bash
# check_upstream_drift.sh -- is there upstream (Kinesis) work this fork has not replayed? (P1.2)
#
#   tools/check_upstream_drift.sh           # fetch upstream, red when HEAD lacks its commits
#   tools/check_upstream_drift.sh --probe   # prove it goes red, in a scratch repo
#
# Ruling R1: the fork is ONE patch on top of upstream/V3.0, and syncing means fetching upstream
# and replaying the patch. Drift used to be found by remembering to look. This counts it:
# `git rev-list --count HEAD..upstream/V3.0`, after a fetch.
#
# Exit: 0 in sync, 1 behind (the count is printed), 2 unknown (no upstream remote, or the fetch
# failed). tools/repo_gates.sh reports a non-zero as a WARNING, not a push blocker: upstream moving
# is not a defect of the commit being pushed, but it is a thing to act on, so it is said every
# push until it is done.
#
# Seams: FORK_REF (default HEAD), UPSTREAM_REMOTE (default upstream), UPSTREAM_BRANCH (default
# V3.0), UPSTREAM_FETCH=0 skips the fetch (the probe; an offline check of the last fetch).
set -euo pipefail
GOH="${GOH_DIR:-${GOH:-$HOME/Projects/gates_of_heck}}"
# shellcheck source=/dev/null
. "$GOH/tui/lib.sh"

drift() {
    local fork="${FORK_REF:-HEAD}" remote="${UPSTREAM_REMOTE:-upstream}" branch="${UPSTREAM_BRANCH:-V3.0}"
    local ref="$remote/$branch" count
    if ! git remote get-url "$remote" >/dev/null 2>&1; then
        err "upstream drift: no '$remote' remote; add it:"
        err "  git remote add upstream https://github.com/KinesisCorporation/Adv360-Pro-ZMK.git"
        return 2
    fi
    if [ "${UPSTREAM_FETCH:-1}" != 0 ] && ! git fetch --quiet "$remote" "$branch" 2>/dev/null; then
        err "upstream drift: could not fetch $remote $branch, so drift is unknown"
        return 2
    fi
    if ! git rev-parse --verify --quiet "$ref^{commit}" >/dev/null; then
        err "upstream drift: no ref $ref; fetch it (git fetch $remote)"
        return 2
    fi
    count="$(git rev-list --count "$fork..$ref")"
    if [ "$count" -gt 0 ]; then
        err "upstream drift: $ref has $count commit(s) $fork does not; replay the fork patch on it (R1)"
        return 1
    fi
    ok "upstream drift: $fork contains $ref ($(git rev-parse --short "$ref"))"
}

probe() {
    local scratch failed=0 out rc
    scratch="$(mktemp -d "${TMPDIR:-/tmp}/drift-probe.XXXXXX")"
    (
        cd "$scratch"
        git init -q
        git -c user.name=p -c user.email=p@p commit -q --allow-empty -m base
        git remote add upstream "$scratch"
        git update-ref refs/remotes/upstream/V3.0 HEAD
        export UPSTREAM_FETCH=0
        check() { # name, want-rc
            rc=0
            out="$(drift 2>&1)" || rc=$?
            if [ "$rc" != "$2" ]; then
                err "upstream drift probe: $1: expected exit $2, got $rc: $out"
                failed=1
            fi
        }
        check "in sync" 0
        git -c user.name=p -c user.email=p@p commit -q --allow-empty -m up1
        git -c user.name=p -c user.email=p@p commit -q --allow-empty -m up2
        git update-ref refs/remotes/upstream/V3.0 HEAD
        git reset -q --hard HEAD~2
        check "two behind" 1
        case "$out" in *"has 2 commit(s)"*) ;; *) err "upstream drift probe: count not named: $out"; failed=1 ;; esac
        git update-ref -d refs/remotes/upstream/V3.0
        check "no upstream ref" 2
        git remote remove upstream
        check "no upstream remote" 2
        exit "$failed"
    ) || failed=1
    find "$scratch" -delete
    [ "$failed" = 0 ] && ok "upstream drift probe: in sync green, behind red with its count, unknown is exit 2"
    return "$failed"
}

if [ "${1:-}" = "--probe" ]; then
    probe
else
    drift
fi
