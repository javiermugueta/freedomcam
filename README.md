# freedomCam 📸

*[Leer en español](README.es.md)*

Camera snapshots on motion, stored in **your own** S3-compatible bucket, and an iOS app to browse them
by day. No cloud subscription, no third-party servers: Home Assistant writes to your bucket and your
phone reads from it.

- **Home Assistant integration** (this repository, installable with HACS): watches your cameras, saves a
  photo when something moves and, optionally, names it after what it sees (`181502_car-person.jpg`).
- **iOS app** (`FreedomCam/`): browse photos by day and camera, filter by people, vehicles or animals.
  📱 **Coming soon to the App Store.** Meanwhile you can build it yourself (see below).
- **Open format** ([docs/bucket-format.md](docs/bucket-format.md)): any other client can read the bucket.

## Documentation

- 📖 **[User guide](docs/guide.md)**: storage, installation, cameras, options, app, costs and troubleshooting.
- 🔒 **[Privacy policy](docs/privacy.md)**: freedomCam collects no data.
- 🪣 [Bucket format](docs/bucket-format.md), for developers of other clients.

## Storage

Any S3-compatible service: Cloudflare R2, Amazon S3, Backblaze B2, Wasabi, MinIO, a NAS with S3…
The setup wizard explains, for each provider, how to create the bucket and the keys, checks that they
work and can create the bucket and the retention rule for you.

Use two pairs of keys: one with **read and write** access for Home Assistant and one **read-only**
for the app.

## Install the integration

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/javiermugueta/freedomcam` as an *Integration*.
2. Install **freedomCam** and restart Home Assistant.
3. *Settings → Devices & services → Add integration → freedomCam* and follow the wizard.
4. In the freedomCam card, **Add camera** for each camera:
   - **Image**: compares each snapshot with the previous ones. Works with any camera.
   - **Motion sensor**: takes photos while a `binary_sensor` reports motion (e.g. Tapo, Reolink).
   - *Only when nobody is home*: uses the presence entity set in the options (e.g. `zone.home`).
5. Options: pause between photos, photos per hour, sensitivity, thumbnails and object detection
   (Cloudflare Workers AI, optional).

To connect the iOS app without typing: in the options, enter **read-only** app keys. The integration checks
that they cannot write and shows a **QR code** (image entity *App connection QR*). Scan it from the app, or
with the iPhone Camera app.

Each camera gets a *Photos today* sensor with the last photo, its labels and the last error as attributes.

Requires Home Assistant 2025.6 or newer.

## iOS app

The app will be available on the App Store soon. Until then, build it with Xcode:

```sh
xcodegen generate
open FreedomCam.xcodeproj
```

In Xcode choose your team in *Signing & Capabilities*, connect the iPhone and Run.
Tests: `xcodebuild test -scheme FreedomCam -destination 'platform=iOS Simulator,name=iPhone 17 Pro'`.

## Development

```sh
uv venv --python 3.13 .venv && uv pip install pytest-homeassistant-custom-component botocore "moto[server]" segno PyTurboJPEG
.venv/bin/pytest                                            # Home Assistant tests
.venv/bin/pytest tests_live -p no:homeassistant -p no:socket   # real HTTP against a local S3 emulator
```
