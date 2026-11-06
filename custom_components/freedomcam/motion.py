"""Motion detection by image difference, thumbnails and object labels (pure functions, CPU bound).

Each frame is converted to grey and reduced to 96×54, then compared with a background that adapts
slowly (it follows gradual light changes). There is motion when more than `threshold_fraction` of the
pixels change; above `max_fraction` it is a light change (clouds, infrared switching at dusk) and
only the background is rebuilt. Corrupt frames (lower half in vertical stripes, typical of a frame
grabbed by FFmpeg before it is fully decoded) are discarded.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from PIL import Image, ImageFilter

from .const import THUMB_WIDTH, VEHICLE_LABELS

SIZE = (96, 54)

# COCO labels (used by most object detectors) -> freedomCam labels
COCO_LABELS = {"person": "person", "car": "car", "truck": "car", "bus": "car", "motorcycle": "motorcycle",
               "bicycle": "bicycle", "dog": "dog", "cat": "cat"}

MOTION, LIGHT, STILL, START, CORRUPT = "motion", "light", "still", "start", "corrupt"


@dataclass
class Settings:
    pixel_threshold: int = 25          # grey difference (0-255) for a pixel to count as changed
    threshold_fraction: float = 0.01   # fraction of changed pixels that means motion
    max_fraction: float = 0.6          # above this: a light change, not motion
    adaptation: float = 0.2            # weight of the new frame in the background


@dataclass
class Detector:
    settings: Settings = field(default_factory=Settings)
    background: list[float] | None = None
    changed: list[bool] | None = None  # changed pixels in the last analysed frame

    def analyse(self, jpeg: bytes) -> tuple[str, float]:
        """Return (MOTION | LIGHT | STILL | START | CORRUPT, fraction of changed pixels)."""
        img = Image.open(io.BytesIO(jpeg)).convert("L").resize(SIZE)
        if _striped(list(img.getdata())):
            return CORRUPT, 0.0
        current = list(img.filter(ImageFilter.BoxBlur(1)).getdata())
        if self.background is None or len(self.background) != len(current):
            self.background = [float(p) for p in current]
            return START, 0.0
        s = self.settings
        self.changed = [abs(p - b) > s.pixel_threshold for p, b in zip(current, self.background, strict=True)]
        fraction = sum(self.changed) / len(current)
        if fraction > s.max_fraction:
            self.background = [float(p) for p in current]
            return LIGHT, fraction
        self.background = [b + s.adaptation * (p - b) for p, b in zip(current, self.background, strict=True)]
        return (MOTION if fraction > s.threshold_fraction else STILL), fraction


def _striped(px: list[int]) -> bool:
    """The lower half repeats each row almost exactly (frame not fully decoded)."""
    width, height = SIZE
    rows = [px[y * width:(y + 1) * width] for y in range(height)]
    lower = range(height // 2 + 1, height)
    equal = sum(1 for y in lower if sum(abs(a - b) for a, b in zip(rows[y], rows[y - 1], strict=True)) / width < 1.0)
    return equal > len(lower) / 2


def image_size(jpeg: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(jpeg)).size


def thumbnail(jpeg: bytes, width: int = THUMB_WIDTH) -> bytes:
    """JPEG at most `width` pixels wide."""
    img = Image.open(io.BytesIO(jpeg))
    if img.width > width:
        img = img.resize((width, max(1, round(img.height * width / img.width))), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=70, optimize=True)
    return out.getvalue()


def labels(objects: list[dict], size: tuple[int, int], changed: list[bool] | None = None,
           allowed: tuple[str, ...] | None = None, min_score: float = 0.7,
           min_change: float = 0.1) -> list[str]:
    """Sorted unique freedomCam labels of the confident objects.

    `objects` are [{"label", "score", "box": {xmin, ymin, xmax, ymax}}] in pixels of an image of `size`.
    With `changed` (the motion mask), vehicles only count if part of their box changed: parked cars
    are not labelled every time. People and animals always count (dark clothes barely change the grey).
    """
    width, height = size
    cw, ch = SIZE
    seen = set()
    for o in objects:
        name = COCO_LABELS.get(o.get("label", ""))
        if not name or o.get("score", 0) < min_score or (allowed and name not in allowed):
            continue
        if changed is not None and name in VEHICLE_LABELS:
            b = o["box"]
            x0 = int(b["xmin"] * cw / width)
            y0 = int(b["ymin"] * ch / height)
            x1, y1 = max(int(b["xmax"] * cw / width), x0 + 1), max(int(b["ymax"] * ch / height), y0 + 1)
            cells = [changed[y * cw + x]
                     for y in range(max(0, y0), min(ch, y1)) for x in range(max(0, x0), min(cw, x1))]
            if not cells or sum(cells) / len(cells) < min_change:
                continue
        seen.add(name)
    return sorted(seen)
