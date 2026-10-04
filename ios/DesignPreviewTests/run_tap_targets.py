#!/usr/bin/env python3
"""Fails when a plain-style Button or NavigationLink has no content shape and no review.

A plain-style control hit-tests only what its label draws, so the empty part of a row,
frame or outline takes no taps. Each `buttonStyle(.plain)` is traced back through its
modifier chain to the statement it styles. That statement must either carry `contentShape`
or be listed in tap_targets_reviewed.txt with the reason its label is already fully hittable.
A style on a container of controls fails outright: the style goes on each control, so each
one is read. A reviewed entry is keyed by a digest of the statement, so editing it asks for
a new review. A reason of the form "<helper> carries the shape" is checked against the
helper's body. Invitations and Household belong to other lanes and are not read.
"""
import hashlib, pathlib, re, sys

here = pathlib.Path(__file__).resolve().parent
root = pathlib.Path(sys.argv[sys.argv.index("--root") + 1]) if "--root" in sys.argv else here.parent / "ArgusFoundation"
reviewed_path = here / "tap_targets_reviewed.txt"
control = re.compile(r"\b(Button|NavigationLink)\b")
styled = re.compile(r"(Button|NavigationLink|Menu)\b")  # a Menu hit-tests its label; its items are system rows
style = "buttonStyle(.plain)"
skip = ("/Invitations/", "/Household/")
pairs = {")": "(", "}": "{", "]": "["}


def mask(text):
    """Blanks string literals and line comments, keeping every offset."""
    blank = lambda match: " " * len(match.group())
    return re.sub(r"//[^\n]*", blank, re.sub(r'"(?:\\.|[^"\\\n])*"', blank, text))


def opener(text, close):
    depth = 0
    for at in range(close, -1, -1):
        if text[at] in pairs:
            depth += 1
        elif text[at] in pairs.values():
            depth -= 1
            if depth == 0:
                return at
    raise ValueError("unbalanced")


def head(text, dot):
    """Start of the statement whose modifier chain reaches the `.` at `dot`."""
    at = dot
    while True:
        at -= 1
        while text[at].isspace():
            at -= 1
        if text[at] in pairs:
            at = opener(text, at)
            before = text[:at].rstrip()
            if before.endswith(":"):  # a labelled trailing closure such as `label: {`
                at = re.search(r"\w+\s*:$", before).start()
                continue
            if before and before[-1] in "})":  # the closure or argument list before this one
                at = len(before)
                continue
            at = len(before)
        start = at
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] in "_$"):
            start -= 1
        before = text[:start].rstrip()
        if not before.endswith("."):
            return start
        at = len(before) - 1


def body(text, name):
    """Bodies of every `struct name`, `func name(` or `var name:` in `text`."""
    for match in re.finditer(rf"\b(?:struct|func|var)\s+{re.escape(name)}\b", text):
        brace = text.index("{", match.end())
        depth = 0
        for at in range(brace, len(text)):
            depth += {"{": 1, "}": -1}.get(text[at], 0)
            if depth == 0:
                yield text[brace:at]
                break


def sources():
    for path in sorted(root.rglob("*.swift")):
        if not any(part in str(path) for part in skip):
            yield path, path.read_text()


def hits():
    for path, raw in sources():
        text = mask(raw)
        lines = raw.splitlines()
        for match in re.finditer(re.escape("." + style), text):
            start = head(text, match.start())
            first, last = text.count("\n", 0, start), text.count("\n", 0, match.start())
            where = f"{path.relative_to(root.parent)}:{first + 1}-{last + 1}"
            statement = text[start:match.start()]
            window = [line.strip() for line in lines[first:last + 1]]
            digest = hashlib.sha256("\n".join(window).encode()).hexdigest()[:12]
            if styled.match(statement):
                kind = "shaped" if "contentShape" in statement else "bare"
            elif control.search(statement):
                kind = "container"
            else:
                kind = "bare"  # a helper that builds the control; its call carries no shape to read
            yield kind, digest, where, window, path


reviewed = {}
for line in reviewed_path.read_text().splitlines():
    if line.strip() and not line.startswith("#"):
        digest, _, reason = line.partition("  ")
        reviewed[digest] = reason
found = list(hits())
bare = [hit for hit in found if hit[0] == "bare"]
containers = [hit for hit in found if hit[0] == "container"]
if "--list" in sys.argv:
    for kind, digest, where, window, _ in found:
        if kind != "shaped":
            print(f"== {digest}  {where}  {'CONTAINER' if kind == 'container' else reviewed.get(digest, 'UNREVIEWED')}")
            for text in window:
                print("   " + text[:170])
unreviewed = [(d, w) for _, d, w, _, _ in bare if d not in reviewed]
stale = sorted(set(reviewed) - {d for _, d, _, _, _ in bare})
everything = None
helpers = []
for _, digest, where, _, path in bare:
    reason = reviewed.get(digest, "")
    if not reason.endswith("carries the shape"):
        continue
    named = re.search(r"(\w+)(?:\([^)]*\))? carries the shape$", reason)
    if not named:
        helpers.append((digest, where, "the reason", "names no helper"))
        continue
    bodies = list(body(mask(path.read_text()), named.group(1)))
    if not bodies:
        everything = everything or [mask(text) for _, text in sources()]
        bodies = [found_body for text in everything for found_body in body(text, named.group(1))]
    if not bodies or not all("contentShape" in text for text in bodies):
        helpers.append((digest, where, named.group(1), "has no content shape" if bodies else "was not found"))
for _, digest, where, _, _ in containers:
    print(f"CONTAINER {digest}  {where}  the plain style sits on a container; set it on each control")
for digest, where in unreviewed:
    print(f"UNREVIEWED {digest}  {where}")
for digest in stale:
    print(f"STALE {digest}  {reviewed[digest]}")
for digest, where, name, why in helpers:
    print(f"HELPER {digest}  {where}  {name} {why}")
print(f"plain-style statements: {len(found)}, without a content shape: {len(bare)}, reviewed: {len(bare) - len(unreviewed)}, "
      f"unreviewed: {len(unreviewed)}, stale entries: {len(stale)}, container styles: {len(containers)}, "
      f"helpers without a shape: {len(helpers)}")
sys.exit(1 if unreviewed or stale or containers or helpers else 0)
