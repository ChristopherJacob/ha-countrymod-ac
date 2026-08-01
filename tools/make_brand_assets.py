#!/usr/bin/env python3
"""Build icon/logo assets from the CountryMod wordmark.

The source is a small PNG of the wordmark on solid white. White is keyed out to
transparency and the ink is normalised to the brand blue, so antialiased edges
stay clean instead of turning into grey fringes.

The artwork is only 64x95 px, so reaching a 256/512 icon means upscaling ~3x.
Plain interpolation turns the thin burst rays to mush, so the alpha channel is
put through a contrast curve after resampling. For flat two-colour art that
restores a crisp edge while keeping the antialiasing.
"""

import sys

from PIL import Image, ImageDraw

SRC, OUT = sys.argv[1], sys.argv[2]

BRAND = (16, 91, 156)  # #105B9C, the dominant ink colour in the source
BRAND_LUM = 0.299 * BRAND[0] + 0.587 * BRAND[1] + 0.114 * BRAND[2]

MARK_BOX = (72, 176, 136, 271)  # burst + C
WORD_BOX = (72, 176, 375, 271)  # full COUNTRYMOD wordmark


def keyed(box):
    """Crop `box` and return brand-coloured ink on transparency."""
    im = Image.open(SRC).convert("RGB").crop(box)
    px = im.load()
    w, h = im.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    op = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            # White -> 0. Anything at or darker than the brand ink -> fully
            # opaque, so solid areas do not come out semi-transparent.
            a = 255.0 * (255.0 - lum) / (255.0 - BRAND_LUM)
            op[x, y] = (*BRAND, max(0, min(255, round(a))))
    return out


def sharpen_alpha(img, k=3.0):
    """Push the alpha channel through a contrast curve around 50%."""
    alpha = img.getchannel("A")
    lut = []
    for v in range(256):
        t = (v / 255.0 - 0.5) * k + 0.5
        lut.append(max(0, min(255, round(t * 255))))
    out = img.copy()
    out.putalpha(alpha.point(lut))
    return out


def scale(img, w, h):
    return sharpen_alpha(img.resize((w, h), Image.LANCZOS))


def fit(img, size, pad_ratio):
    """Centre `img` on a transparent square canvas, with padding."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inner = int(size * (1 - 2 * pad_ratio))
    f = min(inner / img.width, inner / img.height)
    new = scale(img, max(1, round(img.width * f)), max(1, round(img.height * f)))
    canvas.paste(new, ((size - new.width) // 2, (size - new.height) // 2), new)
    return canvas


def on_white(img, radius_ratio=0.18):
    """Same artwork over a white rounded square, for dark backgrounds."""
    size = img.width
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * radius_ratio), fill=255
    )
    bg.paste(Image.new("RGBA", (size, size), (255, 255, 255, 255)), (0, 0), mask)
    bg.alpha_composite(img)
    return bg


mark, word = keyed(MARK_BOX), keyed(WORD_BOX)
print("mark ink:", mark.size, " wordmark ink:", word.size)

fit(mark, 256, 0.12).save(f"{OUT}/icon.png")
fit(mark, 512, 0.12).save(f"{OUT}/icon@2x.png")
on_white(fit(mark, 256, 0.18)).save(f"{OUT}/icon-on-white.png")
on_white(fit(mark, 512, 0.18)).save(f"{OUT}/icon-on-white@2x.png")

scale(word, 512, round(512 * word.height / word.width)).save(f"{OUT}/logo.png")
scale(word, 1024, round(1024 * word.height / word.width)).save(f"{OUT}/logo@2x.png")

for name in (
    "icon.png",
    "icon@2x.png",
    "icon-on-white.png",
    "icon-on-white@2x.png",
    "logo.png",
    "logo@2x.png",
):
    im = Image.open(f"{OUT}/{name}").convert("RGBA")
    px = im.load()
    solid = sum(
        1 for y in range(im.height) for x in range(im.width) if px[x, y][3] == 255
    )
    print(f"  {name:22} {im.size[0]}x{im.size[1]}  fully-opaque px: {solid}")
