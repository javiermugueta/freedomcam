# freedomCam privacy policy

*[Leer en español](privacy.es.md)* · Effective date: 6 November 2026

freedomCam is made of an iOS app and an integration for Home Assistant. It is designed so that **your photos
and your data never pass through us**. In short: **we do not collect, receive, store, sell or share any data.**

## The iOS app

- **No data collection.** The app has no accounts, no analytics, no advertising, no tracking and no crash
  reporting services. We receive nothing from it.
- **Your storage settings and keys** (provider, bucket, access keys) are kept only on your iPhone, in the
  system Keychain. They are not sent anywhere except to sign the requests to your own storage.
- **Your photos** are downloaded directly from the storage you configured (for example your Cloudflare R2,
  Amazon S3 or Backblaze B2 bucket) to your iPhone, over an encrypted connection (HTTPS) whenever your provider
  supports it. A copy is kept in the app's cache on your iPhone; you can delete it in *Settings → Empty cache*
  or by deleting the app.
- **Camera.** The app asks for camera access only to scan the QR code that connects it to your storage. The
  image is processed on the device to read the code; it is not recorded, saved or sent.
- **Sharing.** When you share a photo, it goes only where you choose, through the standard iOS share sheet.

## The Home Assistant integration

The integration runs in your own Home Assistant. It takes snapshots of the cameras you choose and uploads them
to **your** storage, with the keys you provide. Optionally, if you turn on object detection, each photo is sent
to **Cloudflare Workers AI** using **your** Cloudflare account and token, to label what it shows; Cloudflare
processes it under its own terms. We have no access to your Home Assistant, your storage or your photos.

## Third parties

freedomCam only talks to the services you configure. Their own privacy policies apply to the data you keep
with them: your storage provider (for example [Cloudflare](https://www.cloudflare.com/privacypolicy/),
[Amazon Web Services](https://aws.amazon.com/privacy/), [Backblaze](https://www.backblaze.com/company/policy/privacy),
[Wasabi](https://wasabi.com/legal/privacy-policy)) and, if you use it, Cloudflare Workers AI.

## Your responsibility as camera owner

The photos may show other people. Depending on where you live, recording people (for example neighbours or
the street) may be regulated by privacy laws such as the GDPR. You decide what your cameras record, how long
photos are kept (retention setting) and who has the keys.

## Children

freedomCam is not directed to children and does not knowingly collect any information from anyone.

## Changes

If this policy changes, the new version will be published here with a new effective date. The history is
available in the [project repository](https://github.com/javiermugueta/freedomcam/commits/main/docs/privacy.md).

## Contact

Questions about this policy: [open an issue](https://github.com/javiermugueta/freedomcam/issues) in the project repository.
