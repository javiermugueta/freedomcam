from __future__ import annotations

import io

from PIL import Image

from custom_components.freedomcam import motion
from custom_components.freedomcam.const import INDOOR_LABELS

from .images import frame


def test_motion_light_and_still():
    d = motion.Detector()
    assert d.analyse(frame())[0] == motion.START
    assert d.analyse(frame())[0] == motion.STILL
    assert d.analyse(frame(box=(100, 100, 220, 300)))[0] == motion.MOTION
    assert d.analyse(frame(background=230))[0] == motion.LIGHT      # whole image changes: light, not motion


def test_thumbnail_is_small():
    thumb = motion.thumbnail(frame(size=(1920, 1080)))
    assert Image.open(io.BytesIO(thumb)).size == (320, 180)


def test_labels_vehicles_need_motion_people_do_not():
    d = motion.Detector()
    d.analyse(frame())
    d.analyse(frame(box=(0, 0, 100, 100)))          # change only in the top-left corner
    objects = [
        {"label": "car", "score": 0.95, "box": {"xmin": 400, "ymin": 200, "xmax": 600, "ymax": 350}},   # parked
        {"label": "truck", "score": 0.9, "box": {"xmin": 0, "ymin": 0, "xmax": 100, "ymax": 100}},     # moving
        {"label": "person", "score": 0.8, "box": {"xmin": 300, "ymin": 50, "xmax": 340, "ymax": 200}},
        {"label": "dog", "score": 0.5, "box": {"xmin": 1, "ymin": 1, "xmax": 2, "ymax": 2}},          # unsure
        {"label": "toaster", "score": 0.99, "box": {"xmin": 1, "ymin": 1, "xmax": 2, "ymax": 2}},
    ]
    assert motion.labels(objects, (640, 360), d.changed) == ["car", "person"]
    assert motion.labels(objects, (640, 360), allowed=INDOOR_LABELS) == ["person"]
