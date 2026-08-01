# Brand assets

## Trademark

The CountryMod name and logo are the property of CountryMod. This project is
not affiliated with, endorsed by, or sponsored by CountryMod or Kingcontech.
The mark is reproduced here only to identify the device this integration
controls, which is the same convention Home Assistant's own
[brands repository](https://github.com/home-assistant/brands) uses for every
manufacturer it supports.

If CountryMod would prefer these assets not be distributed, remove this
directory and drop the brands submission; nothing in the integration depends on
them.

## Files

| File | Size | Use |
| --- | --- | --- |
| `brands/icon.png` | 256×256 | Square mark, transparent — for a `home-assistant/brands` submission |
| `brands/icon@2x.png` | 512×512 | Same, 2x |
| `brands/logo.png` | 512×119 | Full lockup, transparent |
| `brands/logo@2x.png` | 1024×238 | Same, 2x |
| `icon-on-white.png` | 256×256 | Mark on a white rounded square, for dark backgrounds |
| `icon-on-white@2x.png` | 512×512 | Same, 2x |
| `countrymod-logo-source.png` | 5000×1199 | Unmodified source, kept so the assets can be rebuilt |

The square icon uses the burst-and-C mark rather than the full lockup, which is
4.3:1 and unreadable at icon size.

Brand colour: **`#1D73BB`**.

## These do not change the Home Assistant UI

Home Assistant serves integration icons from `brands.home-assistant.io`, not
from the integration directory. A custom integration cannot ship its own icon,
so Home Assistant will keep showing a default placeholder until the assets are
accepted into [home-assistant/brands](https://github.com/home-assistant/brands).
Until then these are for the repository README and HACS.

## Provenance

`countrymod-logo-source.png` is the official logo, taken unmodified from
CountryMod's own CDN at full resolution:

```
https://countrymodpro.com/cdn/shop/files/New_logo_png_166a4f73-159f-43b5-b5f1-efda477d29f6.png
```

That URL accepts a `width=` parameter; omitting it returns the 5000×1199
original, which already carries a real alpha channel. Everything in
`tools/make_brand_assets.py` is therefore a downscale — no colour keying, no
edge reconstruction, no upscaling.

To rebuild:

```bash
python3 tools/make_brand_assets.py assets/countrymod-logo-source.png assets
```

The script locates the mark by finding the first wide gap in the alpha channel
rather than using hard-coded crop boxes, so it should survive a re-exported
logo. It warns if handed a source small enough that the output would be
upscaled.

### Earlier revision

The first version of these assets was reconstructed from a 447×447 search-result
thumbnail whose artwork occupied only 303×95 px. It required keying white to
transparency and reconstructing edges, and it reported the brand colour as
`#105B9C` — the palette quantisation in that thumbnail had shifted the blue.
The official source gives `#1D73BB`.
