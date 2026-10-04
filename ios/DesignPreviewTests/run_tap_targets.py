#!/usr/bin/env python3
"""Fails when a plain-style Button or NavigationLink has no content shape and no review.

A plain-style control hit-tests only what its label draws, so the empty part of a row,
frame or outline takes no taps. Each statement must either carry `contentShape` or be
listed in tap_targets_reviewed.txt with the reason its label is already fully hittable.
A reviewed entry is keyed by a digest of the statement, so editing it asks for a new review.
Invitations and Household belong to other lanes and are not read.
"""
import hashlib, pathlib, re, sys

here = pathlib.Path(__file__).resolve().parent
root = here.parent / "ArgusFoundation"
reviewed_path = here / "tap_targets_reviewed.txt"
start = re.compile(r"\b(Button|NavigationLink)\b")
skip = ("/Invitations/", "/Household/")


def hits():
    for path in sorted(root.rglob("*.swift")):
        if any(part in str(path) for part in skip):
            continue
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            if "buttonStyle(.plain)" not in line:
                continue
            j = i
            while j > 0 and i - j < 25 and not start.search(lines[j]):
                j -= 1
            window = [text.strip() for text in lines[j:i + 1]]
            if any("contentShape" in text for text in window):
                continue
            digest = hashlib.sha256("\n".join(window).encode()).hexdigest()[:12]
            yield digest, f"{path.relative_to(here.parent)}:{j + 1}-{i + 1}", window


reviewed = {}
for line in reviewed_path.read_text().splitlines():
    if line.strip() and not line.startswith("#"):
        digest, _, reason = line.partition("  ")
        reviewed[digest] = reason
found = list(hits())
if "--list" in sys.argv:
    for digest, where, window in found:
        print(f"== {digest}  {where}  {reviewed.get(digest, 'UNREVIEWED')}")
        for text in window:
            print("   " + text[:170])
unreviewed = [(d, w) for d, w, _ in found if d not in reviewed]
stale = sorted(set(reviewed) - {d for d, _, _ in found})
for digest, where in unreviewed:
    print(f"UNREVIEWED {digest}  {where}")
for digest in stale:
    print(f"STALE {digest}  {reviewed[digest]}")
print(f"plain-style statements without a content shape: {len(found)}, reviewed: {len(found) - len(unreviewed)}, "
      f"unreviewed: {len(unreviewed)}, stale entries: {len(stale)}")
sys.exit(1 if unreviewed or stale else 0)
