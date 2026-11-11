# freedomCam 📸

*[Read in English](README.md)*

Fotos de tus cámaras cuando hay movimiento, guardadas en **tu propio** bucket compatible con S3, y una app
de iOS para verlas por día. Sin suscripciones ni servidores de terceros: Home Assistant escribe en tu
bucket y tu móvil lee de él.

- **Integración de Home Assistant** (este repositorio, se instala con HACS): vigila las cámaras, guarda una
  foto cuando algo se mueve y, si quieres, le pone en el nombre lo que ve (`181502_car-person.jpg`).
- **App de iOS** (`FreedomCam/`): fotos por día y cámara, con filtros de personas, vehículos o animales.
  📱 **[Descárgala en el App Store](https://apps.apple.com/app/freedomcam/id6831813216)** (0,99 €, pago único). También puedes compilarla tú mismo (ver más abajo).
- **Formato abierto** ([docs/bucket-format.es.md](docs/bucket-format.es.md)): cualquier otro cliente puede leer el bucket.

## Documentación

- 📖 **[Guía de uso](docs/guide.es.md)**: almacenamiento, instalación, cámaras, opciones, app, costes y problemas frecuentes.
- 🔒 **[Política de privacidad](docs/privacy.es.md)**: freedomCam no recoge ningún dato.
- 🪣 [Formato del bucket](docs/bucket-format.es.md), para quien quiera hacer otros clientes.

## Almacenamiento

Cualquier servicio compatible con S3: Cloudflare R2, Amazon S3, Backblaze B2, Wasabi, MinIO, un NAS con S3…
El asistente de configuración explica, para cada proveedor, cómo crear el bucket y las claves, comprueba
que funcionan y puede crear él mismo el bucket y la regla de caducidad.

Usa dos pares de claves: uno de **lectura y escritura** para Home Assistant y otro de **solo lectura** para la app.

## Instalar la integración

1. HACS → ⋮ → *Repositorios personalizados* → añade `https://github.com/javiermugueta/freedomcam` como *Integración*.
2. Instala **freedomCam** y reinicia Home Assistant.
3. *Ajustes → Dispositivos y servicios → Añadir integración → freedomCam* y sigue el asistente.
4. En la tarjeta de freedomCam, **Añadir cámara** por cada cámara:
   - **Imagen**: compara cada foto con las anteriores. Vale para cualquier cámara.
   - **Sensor de movimiento**: hace fotos mientras un `binary_sensor` detecta movimiento (p. ej. Tapo, Reolink).
   - *Solo cuando no hay nadie en casa*: usa la entidad de presencia de las opciones (p. ej. `zone.home`).
5. Opciones: pausa entre fotos, fotos por hora, sensibilidad, miniaturas y detección de objetos
   (Cloudflare Workers AI, opcional).

Para conectar la app de iOS sin teclear: en las opciones, escribe unas claves de **solo lectura** para la app.
La integración comprueba que no pueden escribir y muestra un **código QR** (entidad de imagen *QR para conectar
la app*). Escanéalo desde la app o con la Cámara del iPhone.

Cada cámara tiene un sensor *Fotos de hoy* con la última foto, sus etiquetas y el último error como atributos.

Requiere Home Assistant 2025.6 o posterior.

## App de iOS

Descárgala en el [App Store](https://apps.apple.com/app/freedomcam/id6831813216) o compílala tú mismo con Xcode:

```sh
xcodegen generate
open FreedomCam.xcodeproj
```

En Xcode elige tu equipo en *Signing & Capabilities*, conecta el iPhone y pulsa Run.
Pruebas: `xcodebuild test -scheme FreedomCam -destination 'platform=iOS Simulator,name=iPhone 17 Pro'`.

## Desarrollo

```sh
uv venv --python 3.13 .venv && uv pip install pytest-homeassistant-custom-component botocore "moto[server]" segno PyTurboJPEG
.venv/bin/pytest                                            # pruebas con Home Assistant
.venv/bin/pytest tests_live -p no:homeassistant -p no:socket   # HTTP real contra un emulador S3 local
```
