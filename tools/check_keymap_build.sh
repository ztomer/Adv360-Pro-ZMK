#!/usr/bin/env bash
# check_keymap_build.sh -- the keymap must BUILD before it is pushed (ROADMAP P0.5).
#
#   tools/check_keymap_build.sh            # build both halves in the pinned image, unless this
#                                          # exact config/ already built green
#   tools/check_keymap_build.sh --probe    # prove the gate goes red, with a stub engine
#
# Before this, the only thing that compiled config/ was GitHub CI: a keymap that did not parse
# was pushed and found there. This builds what `make` builds -- the left half with ZMK Studio
# (bin/build.sh) and the right half -- in the image the Dockerfile pins (tools/check_image_pin.py
# keeps that the same image CI uses).
#
# CACHED BY CONTENT, never by "did config/ change in this push": the key is a hash of every file
# the firmware is built from (config/, Dockerfile, bin/build.sh). A key that built green once is
# not rebuilt; any byte changed there rebuilds. Stamps live in the git common dir, so the pre-push
# gate's clean worktree sees the stamps an interactive run left.
#
# NEVER SKIPS: no container engine, or one that does not answer, is a red with the remedy named.
# A gate that passes because the build could not run is the failure this gate exists to remove.
#
# Seams (for --probe and for a machine with podman): DOCKER names the engine; KEYMAP_BUILD_STAMPS
# names the stamp directory.
set -euo pipefail
GOH="${GOH_DIR:-${GOH:-$HOME/Projects/gates_of_heck}}"
# shellcheck source=/dev/null
. "$GOH/tui/lib.sh"

ROOT="$(git rev-parse --show-toplevel)"
IMAGE_TAG="adv360-zmk-gate"

engine() {
    if [ -n "${DOCKER:-}" ]; then printf '%s\n' "$DOCKER"; return; fi
    command -v podman || command -v docker || true
}

# Every tracked or untracked-unignored file the firmware build reads, hashed with its path.
build_key() {
    (
        cd "$ROOT"
        git ls-files -z --cached --others --exclude-standard -- config Dockerfile bin/build.sh \
            | sort -z | xargs -0 shasum -a 256
    ) | shasum -a 256 | cut -c1-16
}

build() {
    local docker="$1" log="$2" stage="$3"
    "$docker" build --quiet --tag "$IMAGE_TAG" --file "$ROOT/Dockerfile" "$ROOT" >"$log" 2>&1 || return 1
    # config/version.dtsi is committed EMPTY and generated per build (macros.dtsi needs the
    # macro_ver it defines). Generate it the way `make` does, with the repo's own script, into a
    # staged copy of config/ -- the gate never writes the working tree.
    (
        cd "$ROOT"
        git ls-files -z --cached --others --exclude-standard -- config | tar --null -T - -cf - | tar -xf - -C "$stage"
    ) >>"$log" 2>&1 || return 1
    (cd "$stage" && GIT_DIR="$(git -C "$ROOT" rev-parse --absolute-git-dir)" GIT_WORK_TREE="$ROOT" \
        "$ROOT/bin/get_version_local.sh" clique) >>"$log" 2>&1 || return 1
    # bin/build.sh writes its .uf2 files to ./firmware, which the image does not have; the gate
    # keeps nothing, so the directory lives and dies with the container.
    "$docker" run --rm \
        -v "$stage/config:/app/config:ro" \
        -e TIMESTAMP=gate -e COMMIT=gate -e BUILD_RIGHT=true \
        "$IMAGE_TAG" bash -c 'mkdir -p firmware && ./build.sh' >>"$log" 2>&1
}

run() {
    local docker stamps key log stage
    docker="$(engine)"
    if [ -z "$docker" ] || ! command -v "$docker" >/dev/null 2>&1; then
        err "keymap build: no container engine (podman or docker) on PATH${DOCKER:+ (DOCKER=$DOCKER)}"
        err "  install one (brew install docker colima), or set DOCKER; this gate never skips"
        return 1
    fi
    if ! "$docker" info >/dev/null 2>&1; then
        err "keymap build: $docker is installed but its engine is not running"
        err "  start it (colima start), then re-run; this gate never skips"
        return 1
    fi
    stamps="${KEYMAP_BUILD_STAMPS:-$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)/keymap-build-stamps}"
    mkdir -p "$stamps"
    key="$(build_key)"
    if [ -f "$stamps/$key" ]; then
        ok "keymap build: config/ $key already built green ($(cat "$stamps/$key"))"
        return 0
    fi
    log="$stamps/$key.log"
    stage="$(mktemp -d "$stamps/stage.XXXXXX")"
    info "keymap build: building both halves for config/ $key (log: $log)"
    local built=0
    build "$docker" "$log" "$stage" || built=1
    find "$stage" -delete
    if [ "$built" != 0 ]; then
        err "keymap build: FAILED for config/ $key; the errors:"
        # The compiler's own lines name the file and line (devicetree errors read
        # "/app/config/adv360.keymap:LINE..."); show those, else the tail.
        local errors
        errors="$(grep -E '(error|Error|ERROR)' "$log" | grep -v 'Werror' || true)"
        if [ -n "$errors" ]; then
            head -n 20 <<<"$errors" >&2
        else
            tail -n 20 "$log" >&2
        fi
        return 1
    fi
    date -u +"%Y-%m-%dT%H:%MZ" >"$stamps/$key"
    ok "keymap build: both halves built for config/ $key"
}

# --- self-proof: a stub engine, a scratch repo, no network --------------------------------------
probe() {
    local scratch stub calls failed=0 out
    scratch="$(mktemp -d "${TMPDIR:-/tmp}/keymap-build-probe.XXXXXX")"
    git -C "$scratch" init -q
    mkdir -p "$scratch/config" "$scratch/bin"
    printf 'keymap\n' >"$scratch/config/adv360.keymap"
    printf 'FROM x\n' >"$scratch/Dockerfile"
    printf 'true\n' >"$scratch/bin/build.sh"
    printf '#!/usr/bin/env bash\necho "macro_ver: macro_ver {};" >config/version.dtsi\n' >"$scratch/bin/get_version_local.sh"
    chmod +x "$scratch/bin/get_version_local.sh"
    stub="$scratch/engine"
    calls="$scratch/calls"
    # The stub answers `info` and `build`; `run` fails when the keymap holds BROKEN, naming it
    # the way dtc does.
    cat >"$stub" <<EOF
#!/usr/bin/env bash
echo "\$1" >>"$calls"
case "\$1" in
    info|build) exit 0 ;;
    run) if grep -q BROKEN "$scratch/config/adv360.keymap"; then
             echo "Error: /app/config/adv360.keymap:3.1-2 syntax error"; exit 1
         fi; exit 0 ;;
esac
EOF
    chmod +x "$stub"

    expect() { # name, want (0 green / 1 red), command...
        local name="$1" want="$2" got=0
        shift 2
        out="$("$@" 2>&1)" || got=1
        if [ "$got" != "$want" ]; then
            err "keymap build probe: $name: expected $([ "$want" = 0 ] && echo green || echo red)"
            printf '%s\n' "$out" >&2
            failed=1
        fi
    }
    (
        cd "$scratch"
        export KEYMAP_BUILD_STAMPS="$scratch/stamps"
        ROOT="$scratch"
        DOCKER="$scratch/missing" expect "no engine" 1 run
        DOCKER="$stub"
        export DOCKER
        expect "good keymap" 0 run
        expect "cached keymap" 0 run
        [ "$(grep -c '^run$' "$calls")" = 1 ] || { err "keymap build probe: cached key rebuilt"; failed=1; }
        printf 'BROKEN\n' >>"$scratch/config/adv360.keymap"
        expect "broken keymap" 1 run
        case "$out" in
            *adv360.keymap*) ;;
            *) err "keymap build probe: the red did not name the keymap: $out"; failed=1 ;;
        esac
        expect "broken keymap stays red" 1 run
        exit "$failed"
    ) || failed=1
    find "$scratch" -delete
    if [ "$failed" = 0 ]; then
        ok "keymap build probe: no engine red, good green, cache reused, broken keymap red and named"
    fi
    return "$failed"
}

if [ "${1:-}" = "--probe" ]; then
    probe
else
    run
fi
