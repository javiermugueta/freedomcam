# Política de privacidad de freedomCam

*[Read in English](privacy.md)* · En vigor desde: 6 de noviembre de 2026

freedomCam está formado por una app de iOS y una integración para Home Assistant. Está diseñado para que **tus
fotos y tus datos nunca pasen por nosotros**. En resumen: **no recogemos, recibimos, guardamos, vendemos ni
compartimos ningún dato.**

## La app de iOS

- **Sin recogida de datos.** La app no tiene cuentas, ni analítica, ni publicidad, ni seguimiento, ni servicios
  de informes de errores. No recibimos nada de ella.
- **La configuración de tu almacenamiento y tus claves** (proveedor, bucket, claves de acceso) se guardan solo
  en tu iPhone, en el llavero del sistema. No se envían a ningún sitio salvo para firmar las peticiones a tu
  propio almacenamiento.
- **Tus fotos** se descargan directamente del almacenamiento que configuraste (por ejemplo tu bucket de
  Cloudflare R2, Amazon S3 o Backblaze B2) a tu iPhone, por una conexión cifrada (HTTPS) siempre que tu
  proveedor lo permita. Se guarda una copia en la caché de la app en tu iPhone; puedes borrarla en
  *Ajustes → Vaciar caché* o eliminando la app.
- **Cámara.** La app pide acceso a la cámara solo para escanear el código QR que la conecta con tu
  almacenamiento. La imagen se procesa en el dispositivo para leer el código; no se graba, guarda ni envía.
- **Compartir.** Cuando compartes una foto, va solo adonde tú eliges, con el menú de compartir de iOS.

## La integración de Home Assistant

La integración funciona en tu propio Home Assistant. Toma fotos de las cámaras que elijas y las sube a **tu**
almacenamiento, con las claves que tú le das. Opcionalmente, si activas la detección de objetos, cada foto se
envía a **Cloudflare Workers AI** con **tu** cuenta y **tu** token de Cloudflare, para etiquetar lo que aparece;
Cloudflare la trata según sus propias condiciones. No tenemos acceso a tu Home Assistant, a tu almacenamiento
ni a tus fotos.

## Terceros

freedomCam solo habla con los servicios que tú configuras. A los datos que guardas en ellos se les aplican sus
propias políticas de privacidad: tu proveedor de almacenamiento (por ejemplo
[Cloudflare](https://www.cloudflare.com/privacypolicy/), [Amazon Web Services](https://aws.amazon.com/privacy/),
[Backblaze](https://www.backblaze.com/company/policy/privacy), [Wasabi](https://wasabi.com/legal/privacy-policy)) y,
si lo usas, Cloudflare Workers AI.

## Tu responsabilidad como dueño de las cámaras

Las fotos pueden mostrar a otras personas. Según dónde vivas, grabar a personas (por ejemplo vecinos o la vía
pública) puede estar regulado por leyes de protección de datos como el RGPD. Tú decides qué graban tus cámaras,
cuánto tiempo se guardan las fotos (ajuste de caducidad) y quién tiene las claves.

## Menores

freedomCam no está dirigido a menores y no recoge a sabiendas información de nadie.

## Cambios

Si esta política cambia, la nueva versión se publicará aquí con una nueva fecha. El historial está en el
[repositorio del proyecto](https://github.com/javiermugueta/freedomcam/commits/main/docs/privacy.es.md).

## Contacto

Dudas sobre esta política: [abre una incidencia](https://github.com/javiermugueta/freedomcam/issues) en el repositorio del proyecto.
