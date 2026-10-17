#!/usr/bin/env python3
"""The README's remap tables are DERIVED from the keymap's diff against upstream, and checked.

    check_readme_keymap.py           # check README.md against config/adv360.keymap
    check_readme_keymap.py --list    # print the remap list the diff implies, per layer
    check_readme_keymap.py --probe   # prove this check goes red on each defect it claims to catch

The fork changes Kinesis's default keymap, and README.md "Layout" documents what changed. On
2026-10-12 the two disagreed: the Tab row described CAPSLOCK (the Grave key's new binding), the
Grave row described the Tab key, and the two Ctrl thumb keys had become Cmd with no row at all.
Nothing could notice, because the table was prose.

The remap list is now a FACT derived from git: for every layer, the bindings of
`config/adv360.keymap` at HEAD versus at the upstream base (`git merge-base HEAD upstream/V3.0`,
ROADMAP R1: the fork is one patch on upstream). A remap is a binding the fork CHANGED in that
layer. Two refinements keep the list to what a reader needs:
  - Spelling is not a remap. On a layer other than the base layer, a binding equal to that
    version's base-layer binding at the same position is the same as `&trans`, so a key that
    merely falls through (upstream spelled `&kp T` out, the fork writes `&trans`) is not listed.
  - A binding the fork left alone is not a remap of its layer, even where a base-layer remap now
    shows through differently (Fn keeps upstream's `&none` on the macro keys): the base-layer row
    documents that key.

What holds after this check passes, per layer that has a remap:
  1. README.md has a `### <section>` for it, with a table `| Original | Binding | Mapped to |`.
  2. Every remapped position has exactly ONE row, named after the key it is on (`NAMES`, or the
     upstream base-layer keycode in `KEYCODE_NAMES`), and every row names a remapped position.
  3. Each row's Binding cell is the binding actually in the keymap at that position, so a row
     cannot describe one key while sitting on another.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.environ.get("GOH_DIR", os.path.expanduser("~/Projects/gates_of_heck")))
from tui.lib import err, info, ok  # noqa: E402

KEYMAP = "config/adv360.keymap"
UPSTREAM = "upstream/V3.0"
# Keymap layer node -> README section heading (the text after "### ", matched as a prefix).
SECTIONS = {
    "default_layer": "Default layer",
    "keypad": "Keypad layer",
    "fn": "Function layer",
    "mod": "Mod layer",
}
# Positions named by their legend rather than by an upstream keycode (assets/key-positions.md):
# the four keys beside the inner columns, bound to &none or a layer key upstream.
NAMES = {20: "(3) Macro", 21: "(1) Macro", 34: "(4) Macro", 39: "(2) Macro"}
KEYCODE_NAMES = {
    "TAB": "Tab", "ESC": "Esc", "GRAVE": "Grave (~)", "CAPS": "Caps-lock",
    "LCTRL": "Left Ctrl", "LALT": "Left Alt", "LGUI": "Win-key", "RCTRL": "Right Ctrl",
    "SEMI": ";", "SQT": "'",
}


def strip_comments(text):
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))


def layers(text):
    """{layer: [binding, ...]} for every layer under `keymap {`, in file order."""
    text = strip_comments(text)
    start = re.search(r"\bkeymap\s*\{", text)
    if not start:
        raise ValueError("no `keymap {` node")
    found = {}
    for match in re.finditer(r"(\w+)\s*\{[^{}]*?bindings\s*=\s*<([^>]*)>\s*;", text[start.end():]):
        found[match.group(1)] = [
            "&" + " ".join(part.split()) for part in match.group(2).split("&") if part.strip()
        ]
    if not found:
        raise ValueError("`keymap {` holds no layer with bindings")
    return found


def remaps(base_text, head_text):
    """{layer: {position: head_binding}} -- what the fork changed, after fall-through folding."""
    base, head = layers(base_text), layers(head_text)
    base_layer = next(iter(head))
    out = {}
    for name, bindings in head.items():
        if name not in base:
            out[name] = dict(enumerate(bindings))
            continue
        if len(bindings) != len(base[name]):
            raise ValueError(f"layer {name}: {len(bindings)} bindings, upstream has {len(base[name])}")

        def fold(version, layer, pos, binding):
            if layer != base_layer and binding == version[base_layer][pos]:
                return "&trans"
            return binding

        changed = {
            pos: binding
            for pos, binding in enumerate(bindings)
            if binding != base[name][pos]
            and fold(head, name, pos, binding) != fold(base, name, pos, base[name][pos])
        }
        if changed:
            out[name] = changed
    return out, base[base_layer]


def key_name(pos, base_default):
    if pos in NAMES:
        return NAMES[pos]
    match = re.fullmatch(r"&kp (\w+)", base_default[pos])
    if match:
        code = match.group(1)
        if code in KEYCODE_NAMES:
            return KEYCODE_NAMES[code]
        if re.fullmatch(r"[A-Z]", code):
            return code.lower()
    return None


def readme_tables(readme):
    """{section heading: [(original, binding), ...]} for every ### section holding a table."""
    tables, heading = {}, None
    for line in readme.splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip() if line.startswith("### ") else None
            continue
        if heading is None or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or set(cells[0]) <= set("-: ") or cells[0] == "Original":
            continue
        binding = cells[1].strip("`").strip() if len(cells) >= 3 else None
        tables.setdefault(heading, []).append((cells[0], binding))
    return tables


def problems(base_text, head_text, readme):
    found = []
    changed, base_default = remaps(base_text, head_text)
    tables = readme_tables(readme)
    for layer, positions in changed.items():
        section = SECTIONS.get(layer)
        if section is None:
            found.append(f"layer {layer} has remaps but no README section is mapped to it in SECTIONS")
            continue
        heading = next((h for h in tables if h.startswith(section)), None)
        if heading is None:
            found.append(f"layer {layer}: {len(positions)} remap(s) but README has no '### {section}' table")
            continue
        rows = tables[heading]
        by_name = {}
        for original, binding in rows:
            by_name.setdefault(original, []).append(binding)
        named = set()
        for pos, binding in sorted(positions.items()):
            name = key_name(pos, base_default)
            if name is None:
                found.append(
                    f"{layer} position {pos} (upstream `{base_default[pos]}`) is remapped but has no "
                    "name; add it to NAMES or KEYCODE_NAMES"
                )
                continue
            named.add(name)
            cells = by_name.get(name, [])
            if not cells:
                found.append(f"{heading}: no row for '{name}' (position {pos}, now `{binding}`)")
            elif len(cells) > 1:
                found.append(f"{heading}: {len(cells)} rows for '{name}'; there must be one")
            elif cells[0] is None:
                found.append(f"{heading}: row '{name}' has no Binding column")
            elif " ".join(cells[0].split()) != binding:
                found.append(f"{heading}: row '{name}' says `{cells[0]}`, the keymap has `{binding}`")
        for original, _ in rows:
            if original not in named:
                found.append(f"{heading}: row '{original}' names no remapped key on layer {layer}")
    for layer, section in SECTIONS.items():
        heading = next((h for h in tables if h.startswith(section)), None)
        if heading and layer not in changed:
            found.append(f"{heading}: README documents remaps, but layer {layer} has none")
    return found


def git(*args):
    return subprocess.run(
        ["git", *args], stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False
    )


def sources():
    top = git("rev-parse", "--show-toplevel")
    if top.returncode:
        raise SystemExit(f"not a git checkout: {top.stderr.strip()}")
    root = top.stdout.strip()
    base = git("merge-base", "HEAD", UPSTREAM)
    if base.returncode or not base.stdout.strip():
        err(f"readme keymap: no merge-base with {UPSTREAM}; add the remote and fetch it:")
        err("  git remote add upstream https://github.com/KinesisCorporation/Adv360-Pro-ZMK.git")
        err("  git fetch upstream")
        raise SystemExit(1)
    sha = base.stdout.strip()
    shown = git("show", f"{sha}:{KEYMAP}")
    if shown.returncode:
        raise SystemExit(f"cannot read {KEYMAP} at {sha}: {shown.stderr.strip()}")
    with open(os.path.join(root, KEYMAP), encoding="utf-8") as handle:
        head = handle.read()
    with open(os.path.join(root, "README.md"), encoding="utf-8") as handle:
        readme = handle.read()
    return sha, shown.stdout, head, readme


def run(argv):
    sha, base_text, head_text, readme = sources()
    try:
        if "--list" in argv:
            changed, base_default = remaps(base_text, head_text)
            for layer, positions in changed.items():
                info(f"{layer} (vs {sha[:7]})")
                for pos, binding in sorted(positions.items()):
                    print(f"  {pos:>2}  {key_name(pos, base_default) or '?':<10}  {binding}")
            return 0
        found = problems(base_text, head_text, readme)
    except ValueError as exc:
        err(f"readme keymap: {KEYMAP}: {exc}")
        return 1
    for line in found:
        err(f"readme keymap: {line}")
    if found:
        err("readme keymap: list the remaps with: tools/check_readme_keymap.py --list")
        return 1
    count = sum(len(p) for p in remaps(base_text, head_text)[0].values())
    ok(f"readme keymap: {count} remaps vs upstream {sha[:7]}, each with one true README row")
    return 0


# --- self-proof -------------------------------------------------------------------------------
# A two-layer, four-key board. Upstream: base `A B C D`, fn spells A and B out and leaves C, D
# transparent. The fork remaps base position 0 and fn position 2, and writes &trans on fn
# position 1 (a fall-through, which is not a remap).
_BASE = "keymap { default_layer { bindings = <&kp A &kp B &kp C &kp D>; }; fn { bindings = <&kp A &kp B &trans &trans>; }; };"
_HEAD = "keymap { default_layer { bindings = <&kp TAB &kp B &kp C &kp D>; }; fn { bindings = <&kp A &trans &kp X &trans>; }; };"


def _readme(default_rows, fn_rows):
    head = "| Original | Binding | Mapped to |\n| --- | --- | --- |\n"
    return (
        "## Layout\n### Default layer\n" + head + "".join(f"| {r} |\n" for r in default_rows)
        + "### Function layer (fp)\n" + head + "".join(f"| {r} |\n" for r in fn_rows)
    )


def probe():
    good_default, good_fn = ["a | `&kp TAB` | Tab"], ["c | `&kp X` | X"]
    cases = {
        "clean": (_HEAD, _readme(good_default, good_fn), False),
        "missing row": (_HEAD, _readme([], good_fn), True),
        "wrong binding": (_HEAD, _readme(["a | `&kp ESC` | Tab"], good_fn), True),
        "row on the wrong key": (_HEAD, _readme(["b | `&kp TAB` | Tab"], good_fn), True),
        "duplicate row": (_HEAD, _readme(good_default * 2, good_fn), True),
        "row with no remap": (_HEAD, _readme(good_default + ["d | `&kp D` | D"], good_fn), True),
        "no binding column": (_HEAD, _readme(["a | Tab"], good_fn), True),
        "stale section": (_BASE, _readme(good_default, good_fn), True),
        "broken keymap": (_HEAD.replace(">;", ";", 1), _readme(good_default, good_fn), True),
    }
    failed = []
    for name, (head, readme, want_red) in cases.items():
        try:
            red = bool(problems(_BASE, head, readme))
        except ValueError:
            red = True
        if red != want_red:
            failed.append(f"{name}: expected {'red' if want_red else 'green'}, got {'red' if red else 'green'}")
    for line in failed:
        err(f"readme keymap probe: {line}")
    if not failed:
        ok(f"readme keymap probe: {len(cases)} fixtures, each defect red and the clean tree green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(probe() if "--probe" in sys.argv else run(sys.argv))
