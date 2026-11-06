"""Builds the photos of the app's demo mode (FreedomCam/Demo): a week of made-up scenes.

Run from the repository root:  python tools/make_demo.py
Days are relative ("offset" 0 = today): the app places them on the last 7 days when it opens.
"""
import io
import json
import random
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from demo_scenes import escena  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "FreedomCam" / "Demo"
CAMERAS = [("driveway", "outdoor"), ("garden", "outdoor"), ("hall", "indoor")]


def thumb(jpeg: bytes) -> bytes:
    img = Image.open(io.BytesIO(jpeg))
    img = img.resize((320, 180), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=70, optimize=True)
    return out.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.jpg"):
        f.unlink()
    rnd = random.Random(11)
    entries = []
    for offset in range(7):
        n = 12 if offset == 0 else rnd.randint(4, 9)
        usados = set()
        for _ in range(n):
            cam, kind = rnd.choice(CAMERAS)
            hora = rnd.choice([7, 8, 9, 10, 12, 13, 14, 16, 17, 18, 19, 20, 21])
            hhmmss = f"{hora:02d}{rnd.randint(0, 59):02d}{rnd.randint(0, 59):02d}"
            if (cam, hhmmss) in usados:
                continue
            usados.add((cam, hhmmss))
            objs = (rnd.choice([["person"], ["person"], [], ["dog"], ["cat"]]) if kind == "indoor"
                    else rnd.choice([["car"], ["person"], ["car", "person"], [], ["dog"], ["dog", "person"]]))
            objs = [o for o in objs if o != "cat"] if kind == "outdoor" else [o if o != "cat" else "dog" for o in objs]
            jpeg = escena(cam, hora, rnd, objs)
            jpeg_img = Image.open(io.BytesIO(jpeg))
            full = io.BytesIO()
            jpeg_img.save(full, "JPEG", quality=72, optimize=True)
            name = f"d{offset}_{cam}_{hhmmss}"
            (OUT / f"{name}.jpg").write_bytes(full.getvalue())
            (OUT / f"{name}_t.jpg").write_bytes(thumb(full.getvalue()))
            entries.append({"offset": offset, "camera": cam, "time": hhmmss, "labels": sorted(set(objs)),
                            "file": f"{name}.jpg", "thumb": f"{name}_t.jpg"})
    (OUT / "demo.json").write_text(json.dumps({"cameras": [{"id": c, "kind": k} for c, k in CAMERAS],
                                               "photos": entries}, indent=1))
    total = sum(f.stat().st_size for f in OUT.iterdir())
    print(f"{len(entries)} photos, {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
