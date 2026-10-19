#!/usr/bin/env python3
"""The README must name the software that actually serves each chord the board sends.

    check_host_software.py [root]     # check the tree (default: the repo root)
    check_host_software.py --probe    # prove this check goes red on each defect it claims to catch

The keymap sends three chords to the host: `HYP(MINUS)`, `HYP(F1)` and `HYP(F2)`. Something on the
host has to answer them. The README used to say "Hammerspoon Vim-Expose" and recommended
Hammerspoon and ZoneTilerWM; on this machine neither is installed -- the app that answers is
ZoneWM v2 (the native rewrite of the public ZoneTilerWM), and it is spelled `HYPER` + key in its
own config. A README that names software nobody runs is worse than no README: the reader presses
a key, sees nothing, and blames the keyboard.

`HOST_SOFTWARE` below is the fork's RECORD of what answers each chord, measured on the owner's
machine on 2026-10-19 (ZoneWM v2.81.0, `~/.config/zonewm/config.toml`: `window_hints = ["HYPER",
"-"]`, `hyperAppCuts` F1 = Gemini and F2 = Claude, `HYPER` = shift+ctrl+alt+cmd). It is a
recorded fact, not a constant of nature: when the host software changes, this table and the
README change together, in one commit.

What holds after this check passes:
  1. The keymap defines `HYP(key)` and `HYPER` with the SAME modifier stack, so the software's
     `HYPER` prefix really is the prefix the chords are built on.
  2. The chords the bindings reach are derived from the keymap, and README.md's "Host chords"
     table lists exactly those chords, once each.
  3. Every row names the software this fork records for that chord, and that software is in
     README.md's "Recommended supporting software" list.
  4. Every recommended software that is not the platform is named by some row -- a recommendation
     nobody can act on is dead text.
  5. The Layout rows spell each chord the way the keymap spells it (`HYP(MINUS)`, not
     `HYPER-Minus`) and name the software that serves it.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.environ.get("GOH_DIR", os.path.expanduser("~/Projects/gates_of_heck")))
from tui.lib import err, ok  # noqa: E402

KEYMAP = "config/adv360.keymap"
README = "README.md"
# The recorded host software per chord (measured 2026-10-19); see the docstring.
HOST_SOFTWARE = {
    "HYP(MINUS)": "ZoneWM",
    "HYP(F1)": "ZoneWM",
    "HYP(F2)": "ZoneWM",
}
# The platform is not "supporting software"; it is where the software runs.
PLATFORM = {"macOS"}
MODIFIER = "HYPER"  # the keymap's own name for the modifier stack the chords sit on


def strip_comments(text):
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))


def defines(text):
    """{macro: value} for the keymap's #defines (the HYP(key) form is read separately)."""
    return {
        name: value.strip()
        for name, value in re.findall(r"#define\s+([A-Za-z_]\w*)\s+([^\n]+)", text)
    }


def modifier_stack(value, drop=()):
    """The modifier tokens of a nested ZMK modifier expression: LS(LC(LA(LG(key)))) -> LS LC LA LG."""
    stack = [token for token in re.findall(r"[A-Za-z_]\w*", value) if token not in drop]
    return [("LG" if token == "LGUI" else token) for token in stack]


def binding_tokens(text):
    """Every token of every `bindings = <...>` list, in file order.

    One statement can hold several lists (`bindings = <&kp HYP(F1)>, <&kp HYP(F2)>;`), so the
    statement is read to its `;` and every `<...>` in it is taken.
    """
    tokens = []
    for match in re.finditer(r"bindings\s*=\s*", text):
        rest = text[match.end():]
        end = rest.find(";")
        statement = rest if end < 0 else rest[:end]
        for block in re.findall(r"<([^>]*)>", statement, flags=re.S):
            tokens.extend(token.strip(",") for token in block.split() if token.strip(","))
    return tokens


def reachable_chords(tokens, macros, seen=None):
    """The `HYP(...)` chords the bindings reach, following the keymap's own macros."""
    seen = set() if seen is None else seen
    found = set()
    for token in tokens:
        match = re.fullmatch(r"HYP\(([A-Za-z0-9_]+)\)", token)
        if match:
            found.add(f"HYP({match.group(1)})")
            continue
        name = token[1:] if token.startswith("&") else token
        if name in macros and name not in seen:
            seen.add(name)
            found |= reachable_chords(macros[name].split(), macros, seen)
    return found


def keymap_facts(text):
    """(chords, problems) read from the keymap source."""
    found = []
    text = strip_comments(text)
    macros = defines(text)
    hyp = re.search(r"#define\s+HYP\(\s*(\w+)\s*\)\s*([^\n]+)", text)
    hyper = re.search(rf"#define\s+{MODIFIER}\s+([^\n]+)", text)
    if hyp is None:
        found.append("the keymap does not define HYP(key); the host chords cannot be read")
    if hyper is None:
        found.append(f"the keymap does not define {MODIFIER}; the host chords cannot be read")
    if hyp is not None and hyper is not None:
        hyp_stack = modifier_stack(hyp.group(2), drop=(hyp.group(1),))
        hyper_stack = modifier_stack(hyper.group(1))
        if hyp_stack != hyper_stack:
            found.append(
                f"HYP(key) is {hyp_stack} but {MODIFIER} is {hyper_stack}; "
                "the software's prefix is not the prefix the chords are built on"
            )
    chords = reachable_chords(binding_tokens(text), macros)
    return chords, found


def blocks(readme):
    """[(level, heading, lines)] for every heading in the README."""
    out = []
    for line in readme.splitlines():
        match = re.match(r"^(#+)\s+(.*)$", line)
        if match:
            out.append((len(match.group(1)), match.group(2).strip(), []))
        elif out:
            out[-1][2].append(line)
    return out


def table_rows(lines):
    """[(cells)] for every table row, without the header and the separator."""
    rows = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or set(cells[0]) <= set("-: "):
            continue
        rows.append(cells)
    return rows


def entry_name(entry):
    """The name of a "Recommended supporting software" bullet."""
    if entry.startswith("["):
        match = re.match(r"\[([^\]]+)\]", entry)
        if match:
            return match.group(1).strip()
    for separator in (" -- ", " - ", ": ", " ("):
        if separator in entry:
            return entry.split(separator)[0].strip()
    return entry


def recommended(readme):
    """[(name, entry)] for every recommended supporting software bullet."""
    out = []
    for level, heading, lines in blocks(readme):
        if heading != "Recommended supporting software":
            continue
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith(("* ", "- ")):
                continue
            entry = stripped[2:].strip()
            out.append((entry_name(entry), entry))
    return out


def layout_rows(readme):
    """[(heading, cells)] for every row of the README's Layout tables."""
    out = []
    for level, heading, lines in blocks(readme):
        if level != 3:
            continue
        for cells in table_rows(lines):
            out.append((heading, cells))
    return out


def host_rows(readme):
    """[(cells)] for every row of the README's "Host chords" table."""
    for level, heading, lines in blocks(readme):
        if heading == "Host chords":
            return table_rows(lines)[1:]  # the header row
    return None


def problems(keymap_text, readme_text):
    found = []
    chords, keymap_problems = keymap_facts(keymap_text)
    found += keymap_problems

    host_table = host_rows(readme_text)
    if host_table is None:
        found.append("README.md has no '## Host chords' table; the chords the board sends are not documented")
        host_table = []
    listed = [cells[0].strip("`") for cells in host_table]
    for chord in sorted(set(listed) - chords):
        found.append(f"README.md documents chord {chord}, but the keymap does not send it")
    for chord in sorted(chords - set(listed)):
        found.append(f"the keymap sends {chord}, but README.md's 'Host chords' table does not list it")
    for chord in sorted({chord for chord in listed if listed.count(chord) > 1}):
        found.append(f"README.md's 'Host chords' table lists {chord} more than once")

    names = {name for name, _ in recommended(readme_text)}
    for cells in host_table:
        if len(cells) < 4:
            found.append(f"README.md's host-chord row {cells[0]} has fewer than four columns")
            continue
        chord, software, host_chord, serves = (cell.strip() for cell in cells[:4])
        chord = chord.strip("`")
        recorded = HOST_SOFTWARE.get(chord)
        if recorded is None:
            found.append(f"the keymap sends {chord}, which HOST_SOFTWARE does not record; record it here and in the README")
            continue
        if software != recorded:
            found.append(f"README.md says {chord} is served by {software}, but this fork records {recorded}")
        if software not in names:
            found.append(f"{software} serves {chord} but is not in 'Recommended supporting software'")
        if MODIFIER not in host_chord:
            found.append(f"README.md's {chord} row spells the host chord as {host_chord!r}, without {MODIFIER}")
        if not serves:
            found.append(f"README.md's {chord} row says what it serves not at all")

    layout = layout_rows(readme_text)
    layout_text = "\n".join(" | ".join(cells) for _, cells in layout)
    host_text = "\n".join(" | ".join(cells) for cells in host_table)
    for name, entry in recommended(readme_text):
        if name in PLATFORM:
            continue
        if name not in layout_text and name not in host_text:
            found.append(f"{name} is recommended but no row names it; it serves nothing here")

    for chord in sorted(chords):
        recorded = HOST_SOFTWARE.get(chord)
        naming = [
            (heading, cells)
            for heading, cells in layout
            if len(cells) >= 3 and chord in cells[2]
        ]
        if not naming:
            found.append(f"no Layout row spells {chord} the way the keymap spells it")
        for heading, cells in naming:
            if recorded and recorded not in " ".join(cells):
                found.append(f"the {heading} row names {chord} but not the software that serves it ({recorded})")
    return found


def run(root):
    keymap_path = os.path.join(root, KEYMAP)
    readme_path = os.path.join(root, README)
    for path, rel in ((keymap_path, KEYMAP), (readme_path, README)):
        if not os.path.isfile(path):
            err(f"host software: {rel} is missing -- the scan lost its subject")
            return 1
    with open(keymap_path, encoding="utf-8") as handle:
        keymap_text = handle.read()
    with open(readme_path, encoding="utf-8") as handle:
        readme_text = handle.read()
    found = problems(keymap_text, readme_text)
    for line in found:
        err(f"host software: {line}")
    if found:
        return 1
    chords, _ = keymap_facts(keymap_text)
    ok(f"host software: {len(chords)} host chords, each named with the software that serves it")
    return 0


_KEYMAP = """
#define HYP(key)        LS(LC(LA(LG(key))))
#define HYPER           LS(LC(LA(LGUI)))
#define VIMPOSE         HYP(MINUS)
/ {
  behaviors {
    EXPOSES:
      tap_dance_2 {
        bindings = <&kp VIMPOSE, &kp EXPOSE>;
      };
    G_C:
      tap_dance_5 {
        bindings = <&kp HYP(F1)>, <&kp HYP(F2)>;
      };
  };
  keymap {
    default_layer {
      bindings = <
        &mt HYPER GRAVE   &G_C   &EXPOSES
      >;
    };
  };
};
"""

_README = """# Fixture

## Recommended supporting software

* macOS (Tested on v15.x-v26.x)
* ZoneWM -- my own zone and tile window manager
* [Karabiner Elements](https://github.com/pqrs-org/Karabiner-Elements) Maps CAPSLOCK to FN.

## Layout

### Default layer

| Original   | Binding           | Mapped to |
| ---------- | ----------------- | --------- |
| (4) Macro  | `&G_C`            | Gemini (`HYP(F1)`), Claude (`HYP(F2)`) -- ZoneWM |
| (2) Macro  | `&EXPOSES`        | window hints (`HYP(MINUS)`) -- ZoneWM |
| Caps-lock  | `&kp CAPS`        | CAPSLOCK (mapped to FN with Karabiner Elements) |

## Host chords

| Chord | Software | Host chord | Serves |
| --- | --- | --- | --- |
| `HYP(MINUS)` | ZoneWM | `HYPER` + `-` | window hints |
| `HYP(F1)` | ZoneWM | `HYPER` + `F1` | Gemini |
| `HYP(F2)` | ZoneWM | `HYPER` + `F2` | Claude |
"""


def probe():
    """Each defect in the docstring goes red alone; the clean fixture is green."""

    def mutate(text, old, new):
        if old not in text:
            raise AssertionError(f"fixture does not hold {old!r}")
        return text.replace(old, new)

    cases = {
        "clean": (_KEYMAP, _README, False),
        "empty keymap": ("", _README, True),
        "no host chords section": (_KEYMAP, mutate(_README, "## Host chords", "## Chords"), True),
        "chord missing from the table": (
            _KEYMAP,
            mutate(_README, "| `HYP(F2)` | ZoneWM | `HYPER` + `F2` | Claude |\n", ""),
            True,
        ),
        "chord the keymap does not send": (
            _KEYMAP,
            _README + "| `HYP(F9)` | ZoneWM | `HYPER` + `F9` | nothing |\n",
            True,
        ),
        "chord listed twice": (
            _KEYMAP,
            _README + "| `HYP(F1)` | ZoneWM | `HYPER` + `F1` | Gemini |\n",
            True,
        ),
        "wrong software in the table": (
            _KEYMAP,
            mutate(_README, "| `HYP(F1)` | ZoneWM |", "| `HYP(F1)` | Hammerspoon |"),
            True,
        ),
        "software not recommended": (
            _KEYMAP,
            mutate(_README, "* ZoneWM -- my own zone and tile window manager\n", ""),
            True,
        ),
        "recommended software no row names": (
            _KEYMAP,
            mutate(_README, "* ZoneWM -- my own zone and tile window manager\n",
                   "* ZoneWM -- my own zone and tile window manager\n* Hammerspoon -- automation\n"),
            True,
        ),
        "host chord without the modifier": (
            _KEYMAP,
            mutate(_README, "`HYPER` + `-`", "`-`"),
            True,
        ),
        "row serves nothing": (
            _KEYMAP,
            mutate(_README, "| `HYP(F2)` | ZoneWM | `HYPER` + `F2` | Claude |",
                   "| `HYP(F2)` | ZoneWM | `HYPER` + `F2` |  |"),
            True,
        ),
        "layout row spells the chord differently": (
            _KEYMAP,
            mutate(_README, "(`HYP(MINUS)`)", "(HYPER-Minus)"),
            True,
        ),
        "layout row names the wrong software": (
            _KEYMAP,
            mutate(_README, "window hints (`HYP(MINUS)`) -- ZoneWM", "window hints (`HYP(MINUS)`) -- Hammerspoon"),
            True,
        ),
        "modifier stacks differ": (
            mutate(_KEYMAP, "#define HYPER           LS(LC(LA(LGUI)))", "#define HYPER           LS(LC(Q))"),
            _README,
            True,
        ),
        "no HYP define": (mutate(_KEYMAP, "#define HYP(key)        LS(LC(LA(LG(key))))\n", ""), _README, True),
    }
    failed = []
    for name, (keymap_text, readme_text, want_red) in cases.items():
        try:
            red = bool(problems(keymap_text, readme_text))
        except Exception as exc:  # a crash is a red gate, not a green one
            err(f"host software probe: {name}: {exc}")
            red = True
        if red != want_red:
            failed.append(f"{name}: expected {'red' if want_red else 'green'}, got {'red' if red else 'green'}")
    for line in failed:
        err(f"host software probe: {line}")
    if not failed:
        ok(f"host software probe: {len(cases)} fixtures, each defect red and the clean fixture green")
    return 1 if failed else 0


def main(argv):
    if "--probe" in argv:
        return probe()
    root = argv[1] if len(argv) > 1 else subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], stdin=subprocess.DEVNULL,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return run(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
