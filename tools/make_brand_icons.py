#!/usr/bin/env python3
"""Genera le brand image per il custom component nei formati richiesti da HA.

Uso:
    pip install pillow
    python make_brand_icons.py sorgente.png [--out ../custom_components/tryber/brand]

Produce in output:
    icon.png      256x256   (quadrata, avatar-like)
    icon@2x.png   512x512
    logo.png      lato corto 256px  (mantiene le proporzioni)
    logo@2x.png   lato corto 512px

Note sulle specifiche HA:
- solo PNG, trasparenza consigliata
- l'immagine va "trimmata": niente bordi o spazio vuoto attorno al soggetto
- le varianti per tema scuro si chiamano dark_icon.png / dark_logo.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Manca Pillow: installalo con  pip install pillow")


def trim(img: Image.Image) -> Image.Image:
    """Rimuove lo spazio trasparente/uniforme attorno al soggetto."""
    img = img.convert("RGBA")
    bbox = img.getbbox()  # basato sul canale alpha
    return img.crop(bbox) if bbox else img


def make_square(img: Image.Image, size: int) -> Image.Image:
    """Adatta l'immagine in un quadrato size x size, centrata, senza deformarla."""
    img = img.copy()
    img.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    return canvas


def make_logo(img: Image.Image, short_side: int) -> Image.Image:
    """Scala il logo mantenendo le proporzioni, portando il lato corto a short_side."""
    ratio = short_side / min(img.width, img.height)
    new_size = (round(img.width * ratio), round(img.height * ratio))
    return img.resize(new_size, Image.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="immagine sorgente (PNG/SVG rasterizzato)")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("../custom_components/tryber/brand"),
        help="cartella di destinazione (default: brand/ dell'integrazione)",
    )
    parser.add_argument(
        "--dark",
        action="store_true",
        help="genera i file con prefisso dark_ (variante per tema scuro)",
    )
    args = parser.parse_args()

    if not args.source.is_file():
        sys.exit(f"File non trovato: {args.source}")

    args.out.mkdir(parents=True, exist_ok=True)
    prefix = "dark_" if args.dark else ""

    source = trim(Image.open(args.source))

    outputs = {
        f"{prefix}icon.png": make_square(source, 256),
        f"{prefix}icon@2x.png": make_square(source, 512),
        f"{prefix}logo.png": make_logo(source, 256),
        f"{prefix}logo@2x.png": make_logo(source, 512),
    }

    for name, image in outputs.items():
        path = args.out / name
        # optimize=True -> PNG compresso lossless, come richiesto dalle specifiche
        image.save(path, "PNG", optimize=True)
        print(f"{path}  ({image.width}x{image.height})")

    print("\nFatto. Riavvia Home Assistant e svuota la cache del browser (Ctrl+F5).")


if __name__ == "__main__":
    main()
