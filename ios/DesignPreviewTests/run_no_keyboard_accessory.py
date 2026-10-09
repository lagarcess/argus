#!/usr/bin/env python3
"""Fails when any app source puts a Done (or any) control above the keyboard.

On iOS 26 a keyboard toolbar item or an input accessory view floats as a blue pill over the sheet's own button.
Keyboards close by tapping away (KeyboardTapAway), scrolling or the Return key, never by a Done control."""
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parents[1] / "ArgusFoundation"
banned = [
    (re.compile(r"placement:\s*\.keyboard\b"), "ToolbarItem(placement: .keyboard)"),
    (re.compile(r"\binputAccessoryView\b"), "inputAccessoryView"),
    (re.compile(r"\bUIToolbar\b"), "UIToolbar"),
]
found = []
for path in sorted(root.rglob("*.swift")):
    for number, line in enumerate(path.read_text().splitlines(), 1):
        for pattern, name in banned:
            if pattern.search(line):
                found.append(f"{path.relative_to(root.parent)}:{number}: {name}")
if found:
    print("Controls above the keyboard are not allowed:\n" + "\n".join(found))
    sys.exit(1)
print("No controls above the keyboard.")
