# Formato del bucket de freedomCam — versión 1

*[Read in English](bucket-format.md)*

freedomCam guarda las fotos de las cámaras en un bucket compatible con S3 (Cloudflare R2, AWS S3,
Backblaze B2, Wasabi, MinIO…). La integración de Home Assistant es la única que **escribe**; los visores
(la app de iOS o cualquier otro cliente) solo **leen**. Este documento es el contrato entre ambas partes.

## Estructura

```
freedomcam.json                                    manifiesto del bucket
<cámara>/<AAAA>/<MM>/<DD>/<HHMMSS>[_<etiquetas>].jpg foto
_thumbs/<cámara>/<AAAA>/<MM>/<DD>/<mismo nombre>.jpg miniatura (opcional)
_index/<AAAA>/<MM>/<DD>.json                       índice del día (opcional)
_index/<AAAA>/<MM>.json                            resumen del mes (opcional)
```

- `<cámara>` es el identificador de la cámara: minúsculas `a-z`, `0-9`, `_` y `-`, nunca empieza por `_`.
  Los nombres que empiezan por `_` están reservados para freedomCam.
- Fechas y horas en **hora local** de Home Assistant (ver `timezone` en el manifiesto).
- `<etiquetas>` es la lista ordenada de objetos detectados unida con `-`, p. ej. `181502_car-person.jpg`.
  Las fotos sin detecciones no llevan sufijo: `181502.jpg`.
- Nunca hay dos fotos de la misma cámara en el mismo segundo: quien escribe espera al menos un segundo.

### Etiquetas

| Etiqueta     | Significado                |
|--------------|----------------------------|
| `person`     | persona                    |
| `car`        | coche, camión o autobús    |
| `motorcycle` | moto                       |
| `bicycle`    | bicicleta                  |
| `dog`        | perro                      |
| `cat`        | gato                       |

Las etiquetas se escriben siempre en inglés y los clientes las traducen. Los clientes deben ignorar las
etiquetas que no conozcan.

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
    {"id": "garden", "name": "Jardín", "kind": "outdoor"}
  ],
  "updated": "2026-11-06T18:03:10+01:00"
}
```

- `retention_days`: `0` = las fotos se guardan siempre.
- `indexed_since`: primer día con el índice completo. Los días anteriores pueden tener fotos que no están
  en los índices (por ejemplo, escritas antes de que existieran). Si falta, aún no hay índices completos.
- `kind`: `indoor` (interior) u `outdoor` (exterior); solo orienta el icono.
- Los clientes deben ignorar los campos que no conozcan. Si `version` es mayor que la que conoce, el
  cliente debe avisar al usuario, aunque puede intentar leer la estructura de arriba.

## Índice del día — `_index/AAAA/MM/DD.json`

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

Las fotos van ordenadas por hora. Si no hay miniatura, falta `thumb`.

## Resumen del mes — `_index/AAAA/MM.json`

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

Sirve a los clientes para marcar en el calendario los días con fotos sin listar el bucket.

## Reglas para quien escribe

- Conservar `indexed_since` al reescribir el manifiesto. Un manifiesto nuevo lleva el día siguiente a su creación.
- Primero la foto, después la miniatura y al final los índices. Los índices pueden ir hasta un minuto
  por detrás de las fotos (se actualizan por lotes).
- Las miniaturas son JPEG de como mucho 320 px de ancho.
- La caducidad se aplica con una regla de ciclo de vida del bucket (también borra índices y miniaturas
  antiguos). El resumen del mes quita los días más antiguos que `retention_days`.

## Reglas para quien lee

- Desde `indexed_since`, leer el índice del día. Antes (o si el índice no existe), listar `<cámara>/AAAA/MM/DD/`
  de cada cámara y tomar las miniaturas del índice si lo hay. Igual con el resumen del mes: los meses que no
  están indexados del todo también se listan.
- Tolerar entradas del índice cuyo objeto ya se haya borrado (HTTP 404).
- Los visores deben usar credenciales de **solo lectura**.
