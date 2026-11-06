"""Synthetic JPEG frames for the tests (textured, like a real scene)."""
from __future__ import annotations

import io
import random

from PIL import Image, ImageDraw


def frame(box: tuple[int, int, int, int] | None = None, background: int = 90, size=(640, 360)) -> bytes:
    rnd = random.Random(1)                     # same texture in every frame: only `box` changes
    img = Image.new("RGB", size, (background,) * 3)
    draw = ImageDraw.Draw(img)
    for _ in range(400):
        x, y = rnd.randrange(size[0]), rnd.randrange(size[1])
        g = max(0, min(255, background + rnd.randrange(-40, 40)))
        draw.rectangle((x, y, x + rnd.randrange(5, 40), y + rnd.randrange(5, 40)), fill=(g, g, g))
    if box:
        draw.rectangle(box, fill=(250, 250, 250))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=90)
    return out.getvalue()
