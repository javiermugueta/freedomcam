# App Store metadata — freedomCam 1.0

## Steps

1. **Create the app** in [App Store Connect](https://appstoreconnect.apple.com/) → *Apps* → **+** → *New App*
   (it needs the Account Holder or Admin of your developer account): platform iOS, name, primary language,
   bundle ID `com.jmugueta.freedomcam` (Xcode already registered it), SKU. If the name is taken, use the
   alternative below.
2. Fill in **App information**, **Pricing**, **App Privacy** and the **1.0** version with this document, and
   upload the screenshots.
3. **Upload the build** from Xcode (*Product → Archive → Distribute App → App Store Connect*) or with
   `xcodebuild archive` + `-exportArchive` (destination *upload*).
4. Select the build in version 1.0, fill in **App Review information** and **Add for Review**.

Everything needed to fill in App Store Connect for the first version. Character limits are Apple's.
Screenshots are in [`screenshots/`](screenshots/).

## App information (once per app)

| Field | Value |
|-------|-------|
| Name (30) | **freedomCam** — if it is taken: `freedomCam: S3 Camera Photos` |
| Bundle ID | `com.jmugueta.freedomcam` |
| SKU | `freedomcam-ios` |
| Primary language | English (U.S.) — add the **Spanish (Spain)** localization below |
| Primary category | Utilities |
| Secondary category | Photo & Video |
| Content rights | Does not contain, show or access third-party content |
| Age rating | 4+ (answer *None* to every question; no unrestricted web access) |
| Price | 0.99 USD (paid app, no in-app purchases) |
| Availability | All countries and regions |

### URLs

| Field | Value |
|-------|-------|
| Privacy Policy URL | https://github.com/javiermugueta/freedomcam/blob/main/docs/privacy.md |
| Privacy Policy URL (Spanish) | https://github.com/javiermugueta/freedomcam/blob/main/docs/privacy.es.md |
| Support URL | https://github.com/javiermugueta/freedomcam/blob/main/docs/guide.md |
| Support URL (Spanish) | https://github.com/javiermugueta/freedomcam/blob/main/docs/guide.es.md |
| Marketing URL | https://github.com/javiermugueta/freedomcam |

### App Privacy (nutrition label)

**Data Not Collected.** The app has no accounts, analytics, ads or tracking; it only talks to the storage the
user configures, and the keys stay in the Keychain. Tracking: **No**.

### Export compliance

`ITSAppUsesNonExemptEncryption = NO` is already in the Info.plist: the app only uses HTTPS and the system
CryptoKit to sign requests (exempt). No documentation needed.

## Version 1.0

| Field | Value |
|-------|-------|
| Version | 1.0 (build 1) |
| Copyright | 2026 javiermugueta |
| Release | Manually release this version (recommended for the first one) |

### English (U.S.)

**Subtitle (30)**
```
Camera photos in your own S3
```

**Promotional text (170)**
```
See what your cameras saw, day by day. Your photos stay in your own storage: no subscription, no third-party cloud, no tracking. Works with Home Assistant.
```

**Description (4000)**
```
freedomCam shows the photos your security cameras take when something moves, organised by day and camera, and it keeps them where they belong: in your own storage.

No subscription. No third-party cloud. No account with us. The app reads the photos directly from your S3-compatible bucket (Cloudflare R2, Amazon S3, Backblaze B2, Wasabi, MinIO, a NAS…) and nothing passes through our servers — we do not have any.

THE DAY AT A GLANCE
• The week strip marks the days with photos; jump to any date with the calendar.
• See all cameras together or one by one, with how many photos each one took.
• Filter by people, vehicles or animals, or by photos where nothing was detected.

EVERY PHOTO, FULL SCREEN
• Swipe from one photo to the next, pinch or double-tap to zoom, share it.
• Photos already seen are kept on the phone and use no data again; thumbnails make the gallery fast and light on mobile data.

SET UP IN SECONDS
• Scan the QR code shown by the freedomCam integration in Home Assistant, or enter your provider, bucket and keys by hand.
• Use read-only keys: if the phone is lost, nobody can delete or change your photos.

HOW THE PHOTOS GET THERE
The free and open-source freedomCam integration for Home Assistant watches your cameras, saves a photo when something moves and, if you want, names it after what it sees (person, car, dog…). Guide and source code: github.com/javiermugueta/freedomcam

Not using Home Assistant yet? Tap “Try the demo” to see how it works with made-up photos.

Private by design: no analytics, no ads, no tracking. Available in English and Spanish.
```

**Keywords (100)** — no third-party brands: Apple rejects them in keywords
```
security camera,cctv,surveillance,motion,privacy,nvr,photos,storage,s3,self-hosted,ip camera,home
```

**What's New** (not shown for the first version; for later updates)

**Screenshots**: `screenshots/iphone63-en-*.jpg` (6.3", 1206×2622), `screenshots/iphone-en-*.jpg` (6.9", 1320×2868) and `screenshots/ipad-en-*.jpg` (13", 2064×2752), in order 1 to 5.

### Spanish (Spain) — add this localization

**Nombre (30)**
```
freedomCam
```

**Subtítulo (30)**
```
Fotos de cámaras en tu S3
```

**Texto promocional (170)**
```
Mira lo que vieron tus cámaras, día a día. Tus fotos se quedan en tu propio almacenamiento: sin suscripción, sin nube de terceros y sin seguimiento. Con Home Assistant.
```

**Descripción (4000)**
```
freedomCam te enseña las fotos que hacen tus cámaras de seguridad cuando algo se mueve, ordenadas por día y por cámara, y las deja donde deben estar: en tu propio almacenamiento.

Sin suscripción. Sin nube de terceros. Sin cuenta con nosotros. La app lee las fotos directamente de tu bucket compatible con S3 (Cloudflare R2, Amazon S3, Backblaze B2, Wasabi, MinIO, un NAS…) y nada pasa por nuestros servidores: no tenemos.

EL DÍA DE UN VISTAZO
• La tira de la semana marca los días con fotos; salta a cualquier fecha con el calendario.
• Mira todas las cámaras juntas o una a una, con cuántas fotos hizo cada una.
• Filtra por personas, vehículos o animales, o por fotos en las que no se detectó nada.

CADA FOTO, A PANTALLA COMPLETA
• Desliza de una foto a la siguiente, pellizca o toca dos veces para ampliar, compártela.
• Las fotos ya vistas se guardan en el móvil y no vuelven a gastar datos; las miniaturas hacen la galería rápida y ligera con datos móviles.

EN MARCHA EN SEGUNDOS
• Escanea el código QR que muestra la integración freedomCam en Home Assistant, o escribe a mano tu proveedor, bucket y claves.
• Usa claves de solo lectura: si pierdes el móvil, nadie podrá borrar ni cambiar tus fotos.

CÓMO LLEGAN LAS FOTOS
La integración freedomCam para Home Assistant, gratuita y de código abierto, vigila tus cámaras, guarda una foto cuando algo se mueve y, si quieres, le pone en el nombre lo que ve (persona, coche, perro…). Guía y código: github.com/javiermugueta/freedomcam

¿Aún no usas Home Assistant? Toca «Probar la demo» para ver cómo funciona con fotos inventadas.

Privada por diseño: sin analítica, sin publicidad, sin seguimiento. En español e inglés.
```

**Palabras clave (100)**
```
cámara,seguridad,videovigilancia,movimiento,privacidad,fotos,s3,nvr,alarma,casa,cámara ip,vigilancia
```

**Capturas**: `screenshots/iphone63-es-*.jpg` (6,3"), `screenshots/iphone-es-*.jpg` (6,9") y `screenshots/ipad-es-*.jpg` (13"), en orden del 1 al 5.

## App Review information

| Field | Value |
|-------|-------|
| Sign-in required | **No** |
| Contact | your name, phone and email (only visible to Apple) |

**Notes (English)**
```
freedomCam shows photos that the user's own Home Assistant saves in the user's own S3-compatible storage (Cloudflare R2, Amazon S3, Backblaze B2…). There is no account and no server of ours.

To review the app without any setup, tap "Try the demo" on the first screen: it shows a week of made-up photos bundled with the app, with all features (days, calendar, camera and label filters, full-screen viewer, share). "Exit" in the demo banner returns to the first screen.

The camera permission is only used to scan the QR code that connects the app to the user's storage ("Scan the code from Home Assistant").

The companion Home Assistant integration is open source: https://github.com/javiermugueta/freedomcam
```

## Screenshot list

| # | Screen | Shows |
|---|--------|-------|
| 1 | Gallery of today (demo) | week strip, cameras, filters, photos |
| 2 | Filter *People* | label filters |
| 3 | Full-screen photo | viewer with camera, time and labels |
| 4 | Calendar | jump to any day |
| 5 | Welcome | QR setup, manual setup and demo |

Taken with the iOS simulator in demo mode (made-up photos), status bar at 9:41.
