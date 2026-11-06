# freedomCam bucket format — version 1

*[Leer en español](bucket-format.es.md)*

freedomCam stores camera snapshots in an S3-compatible bucket (Cloudflare R2, AWS S3, Backblaze B2,
Wasabi, MinIO…). The Home Assistant integration is the only **writer**; viewers (the iOS app or any
other client) only **read**. This document is the contract between both sides.

## Layout

```
freedomcam.json                                   bucket manifest
<camera>/<YYYY>/<MM>/<DD>/<HHMMSS>[_<labels>].jpg photo
_thumbs/<camera>/<YYYY>/<MM>/<DD>/<same name>.jpg thumbnail (optional)
_index/<YYYY>/<MM>/<DD>.json                      day index (optional)
_index/<YYYY>/<MM>.json                           month summary (optional)
```

- `<camera>` is the camera id: lowercase `a-z`, `0-9`, `_` and `-`, never starting with `_`.
  Names starting with `_` are reserved for freedomCam.
- Dates and times are **local time** of the Home Assistant instance (see `timezone` in the manifest).
- `<labels>` is the sorted list of detected objects joined by `-`, e.g. `181502_car-person.jpg`.
  Photos without detections have no suffix: `181502.jpg`.
- Two photos of the same camera in the same second never happen: writers wait at least one second.

### Labels

| Label        | Meaning                    | Legacy alias (read only) |
|--------------|----------------------------|--------------------------|
| `person`     | person                     | `persona`                |
| `car`        | car, truck or bus          | `coche`                  |
| `motorcycle` | motorcycle                 | `moto`                   |
| `bicycle`    | bicycle                    | `bici`                   |
| `dog`        | dog                        | `perro`                  |
| `cat`        | cat                        | `gato`                   |

Labels are always written in English; clients translate them. Clients must ignore unknown labels and
should accept the legacy aliases, used by buckets created before version 1.

## `freedomcam.json`

```json
{
  "format": "freedomcam",
  "version": 1,
  "timezone": "Europe/Madrid",
  "retention_days": 30,
  "indexed_since": "2026-11-07",
  "cameras": [
    {"id": "hall", "name": "Hall", "kind": "indoor"},
    {"id": "garden", "name": "Garden", "kind": "outdoor"}
  ],
  "updated": "2026-11-06T18:03:10+01:00"
}
```

- `retention_days`: `0` = photos are kept forever.
- `indexed_since`: first day whose day index is complete. Earlier days may have photos that are not in
  the indexes (for example, written before the indexes existed). Missing = no complete index yet.
- `kind`: `indoor` or `outdoor` (only a hint for icons).
- Clients must ignore unknown fields. A higher `version` means a client that does not know it should
  warn the user, but may still try to read the layout above.

## Day index — `_index/YYYY/MM/DD.json`

```json
{
  "version": 1,
  "date": "2026-11-06",
  "photos": [
    {"camera": "hall", "time": "18:03:10", "key": "hall/2026/11/06/180310_person.jpg",
     "thumb": "_thumbs/hall/2026/11/06/180310_person.jpg", "labels": ["person"], "size": 184233}
  ]
}
```

Photos are sorted by time. `thumb` is missing when there is no thumbnail.

## Month summary — `_index/YYYY/MM.json`

```json
{
  "version": 1,
  "month": "2026-11",
  "days": {
    "05": {"photos": 208, "labels": {"person": 9, "car": 41}},
    "06": {"photos": 77, "labels": {"person": 2}}
  }
}
```

Used by clients to mark days with photos in a calendar without listing the bucket.

## Writer rules

- Keep `indexed_since` when rewriting the manifest. A new manifest gets the day after it is created.
- Upload the photo first, then the thumbnail, then the indexes. Indexes may lag behind photos by up to
  one minute (writers batch index updates).
- Thumbnails are JPEG, at most 320 px wide.
- Retention is enforced with a lifecycle rule on the bucket (it also expires old indexes and
  thumbnails). The month summary drops days older than `retention_days`.

## Reader rules

- From `indexed_since` on, read the day index. Before it (or if the index does not exist), list
  `<camera>/YYYY/MM/DD/` for each camera and take the thumbnails from the index when there is one.
  The same for the month summary: months not fully indexed are also listed.
- Tolerate index entries whose objects were already deleted (HTTP 404).
- Viewers should use **read-only** credentials.
