#!/usr/bin/env python3
"""Build Home Assistant brand assets from the official CountryMod logo.

Source: the full-resolution PNG from CountryMod's own CDN, which already has a
real alpha channel. Everything here is a downscale, so no colour keying or edge
reconstruction is needed and the output stays crisp.

    python3 tools/make_brand_assets.py <source.png> <output-dir>

The source is one wide lockup: a burst-and-C mark, a gap, then the COUNTRYMOD
wordmark. The mark is split off at the first wide gap in the alpha channel, so
this adapts to a re-exported logo without hand-tuned crop boxes.
"""

import sys

from PIL import Image, ImageDraw

MIN_GAP = 16  # px of empty columns separating the mark from the wordmark


def load(path):
    im = Image.open(path).convert("RGBA")
    box = im.getchannel("A").getbbox()
    if box is None:
        raise SystemExit(f"{path}: image is fully transparent")
    return im.crop(box)


def split_mark(im):
    """Return the burst-and-C mark, split at the first wide alpha gap."""
    alpha = im.getchannel("A").load()
    w, h = im.size
    step = max(1, h // 400)
    empty = [all(alpha[x, y] <= 24 for y in range(0, h, step)) for x in range(w)]

    run_start = None
    for x in range(w):
        if empty[x]:
            if run_start is None:
                run_start = x
        else:
            if run_start is not None and x - run_start >= MIN_GAP:
                mark = im.crop((0, 0, run_start, h))
                return mark.crop(mark.getchannel("A").getbbox())
            run_start = None
    raise SystemExit("could not find a gap separating the mark from the wordmark")


def square(img, size, pad_ratio):
    """Centre `img` on a transparent square canvas, with padding."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inner = size * (1 - 2 * pad_ratio)
    f = min(inner / img.width, inner / img.height)
    new = img.resize(
        (max(1, round(img.width * f)), max(1, round(img.height * f))),
        Image.LANCZOS,
    )
    canvas.paste(new, ((size - new.width) // 2, (size - new.height) // 2), new)
    return canvas


def on_white(img, radius_ratio=0.18):
    """Same artwork over a white rounded square, for dark backgrounds."""
    size = img.width
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=round(size * radius_ratio), fill=255
    )
    out.paste(Image.new("RGBA", (size, size), (255, 255, 255, 255)), (0, 0), mask)
    out.alpha_composite(img)
    return out


def wide(img, width):
    return img.resize((width, round(width * img.height / img.width)), Image.LANCZOS)


def main():
    src, out = sys.argv[1], sys.argv[2]
    lockup = load(src)
    mark = split_mark(lockup)
    print(f"source lockup: {lockup.size}   mark: {mark.size}")
    if mark.width < 512 or lockup.width < 1024:
        print("WARNING: source is small; output will be upscaled and soft")

    square(mark, 256, 0.12).save(f"{out}/brands/icon.png")
    square(mark, 512, 0.12).save(f"{out}/brands/icon@2x.png")
    wide(lockup, 512).save(f"{out}/brands/logo.png")
    wide(lockup, 1024).save(f"{out}/brands/logo@2x.png")
    on_white(square(mark, 256, 0.18)).save(f"{out}/icon-on-white.png")
    on_white(square(mark, 512, 0.18)).save(f"{out}/icon-on-white@2x.png")

    for name in (
        "brands/icon.png",
        "brands/icon@2x.png",
        "brands/logo.png",
        "brands/logo@2x.png",
        "icon-on-white.png",
        "icon-on-white@2x.png",
    ):
        im = Image.open(f"{out}/{name}")
        print(f"  {name:24} {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main()
