#!/usr/bin/env python3
"""Check brand assets against the home-assistant/brands image specification.

    python3 tools/check_brand_assets.py <dir>

Rules encoded here come from https://github.com/home-assistant/brands README:
PNG, transparency preferred, trimmed to minimum empty space, icons exactly
256/512 square, and logo short side within 128-256 (normal) or 256-512 (hDPI).
"""

import sys

from PIL import Image

ICON_SIZE = {"icon.png": 256, "icon@2x.png": 512}
LOGO_SHORT = {"logo.png": (128, 256), "logo@2x.png": (256, 512)}

failures = []
notes = []


def check(path, name):
    im = Image.open(path)
    if im.format != "PNG":
        failures.append(f"{name}: not a PNG ({im.format})")
    rgba = im.convert("RGBA")
    w, h = rgba.size

    if "A" not in rgba.getbands():
        notes.append(f"{name}: no alpha channel")

    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        failures.append(f"{name}: fully transparent")
        return

    # Trimming: the subject must touch the canvas on at least one axis.
    left, top, right, bottom = bbox
    slack_x = left + (w - right)
    slack_y = top + (h - bottom)
    if slack_x > 1 and slack_y > 1:
        failures.append(
            f"{name}: untrimmed — {slack_x}px empty horizontally and "
            f"{slack_y}px vertically; spec requires minimum empty space"
        )

    if name in ICON_SIZE:
        want = ICON_SIZE[name]
        if (w, h) != (want, want):
            failures.append(f"{name}: must be {want}x{want}, got {w}x{h}")
        if w != h:
            failures.append(f"{name}: aspect ratio must be 1:1")

    if name in LOGO_SHORT:
        lo, hi = LOGO_SHORT[name]
        short = min(w, h)
        if not lo <= short <= hi:
            failures.append(
                f"{name}: short side {short}px outside required {lo}-{hi}px"
            )
        if w < h:
            notes.append(f"{name}: portrait; a landscape logo is preferred")

    print(f"  {name:16} {w}x{h}  alpha-bbox={bbox}")


def main():
    d = sys.argv[1]
    for name in ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png"):
        check(f"{d}/{name}", name)

    # The icon is a fallback for a missing logo, so aspect sanity matters.
    icon = Image.open(f"{d}/icon.png").convert("RGBA")
    logo = Image.open(f"{d}/logo.png").convert("RGBA")
    if logo.width <= logo.height:
        notes.append("logo.png is not landscape")
    print(f"\n  icon aspect 1:1 = {icon.width == icon.height}")
    print(f"  logo aspect     = {logo.width / logo.height:.2f}:1")

    for n in notes:
        print(f"\nNOTE: {n}")
    if failures:
        print("\nFAILED:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("\nAll home-assistant/brands requirements satisfied.")


if __name__ == "__main__":
    main()
