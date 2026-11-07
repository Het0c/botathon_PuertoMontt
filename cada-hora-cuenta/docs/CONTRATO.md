# Contrato inicial de intercambio · v1

Este formato normalizado es del proyecto, no el formato oficial de BUK ni SIC. La capa de lectura debe mapearlo a las columnas que llegue a entregar el kit.

## Excel BUK

Hoja `BUK`; primeras ocho columnas obligatorias por nombre. Máximo 20.000 filas y 8 MB por archivo. Se rechazan fórmulas y archivos corruptos.

| Columna | Tipo | Condición |
|---|---|---|
| contract_id | texto | Clave de vínculo; no reutilizar para otra persona |
| professional_id | texto | ID ficticio; no usar RUT/nombres reales en la demo |
| institute | texto | Sede normalizada |
| area | texto | Área normalizada |
| role | texto | Cargo debe existir en catálogo de parámetros |
| hours_weekly | número | 0 a 80, sujeto a los topes parametrizados del cálculo |
| start_date | fecha ISO | Inicio contractual |
| end_date | fecha ISO o vacío | Término explícito; nunca inferido por ausencia |
| effective_from | fecha ISO o vacío | Desde cuándo rigen los valores; por defecto start_date |
| assignments | texto o lista JSON | Nombres del catálogo separados por `;` en Excel |
| approved_assignments | texto o lista JSON | Declaración de autorización del dato; no prueba identidad DMN |
| leave_start / leave_end | fecha ISO o vacío | Ambas presentes y ordenadas si hay licencia |

Orden: inicio ≤ fecha efectiva ≤ término cuando existe. Clave única del segmento: `contract_id + effective_from`. Varios segmentos de un vínculo representan cambios en el año. Varios vínculos permiten repartir una persona entre sedes. Por ahora se admite un intervalo de licencia por segmento; el kit definirá incidencias múltiples, reemplazos, vacantes y beneficios.

No se deduce una baja a partir de un contrato omitido: se preserva su historia hasta recibir término explícito. Un segmento con la misma clave sustituye sus valores; otro con fecha efectiva nueva se añade a la historia.

## Excel SIC

Hoja `SIC`: `professional_id`, `institute`, `month` (AAAA-MM), `actual` (entero ≥0). Clave única: persona + sede + mes. La demo supone que SIC mide atenciones directas; confirmar el tipo con el kit. Una fila con cero es distinta de una fila ausente. Un cruce sin contrato vigente se rechaza y requiere revisión del archivo.

Si una persona tiene varios cargos/áreas en una sede y mes, SIC se conserva en el nivel persona/sede/mes (`comparisons`) y no se copia a cada cargo. El panel de detalle muestra sin atribución SIC en esas filas; el CSV conserva los nulos. El resumen actual de SIC usa solo los cruces inequívocos del detalle: ampliar a comparación agrupada cuando el kit presente este caso.

## API local

Solo loopback; todas las rutas requieren `Authorization: Bearer <clave local>`. La clave de edición permite cambios; `BOTATHON_READ_TOKEN` habilita un token opcional de lectura. `connection.json` solo registra la clave de edición para el bot local. El actor de auditoría deriva de la sesión local; el JSON no puede elegirlo.

| Ruta | Método | Uso |
|---|---|---|
| /api/health | GET | Conexión, rol y versión de aplicación |
| /api/plan | GET | Último plan válido, filas, cambios y comparación |
| /api/plan?version=1 | GET | Consulta histórica sin mover la publicación |
| /api/runs | GET | Últimas 100 corridas y operaciones |
| /api/parameters | GET / PUT | Leer o validar/guardar `{ "params": {...} }` |
| /api/import | POST multipart | `buk`, `sic`, o `reuse_sic=true` explícito |
| /api/batches | POST JSON | Lote normalizado orquestado por Blue Prism |
| /api/recalculate | POST | Recalcular la última dotación con parámetros guardados |
| /api/export | GET | CSV completo del plan vigente |
| /api/templates/{nombre} | GET | Plantillas del conjunto permitido |
| /api/demo | POST | Datos ficticios del paquete |

Ejemplo JSON para la automatización:

```json
{
  "schema_version": 1,
  "params_hash": "SHA256 opcional de GET /api/parameters",
  "buk": [{
    "contract_id": "C-001",
    "professional_id": "PRO-001",
    "institute": "Santiago",
    "area": "Rehabilitación",
    "role": "Kinesiología",
    "hours_weekly": 44,
    "start_date": "2026-01-01",
    "end_date": null,
    "effective_from": "2026-01-01"
  }],
  "sic": []
}
```

`params_hash` impide publicar si las reglas cambian entre la preparación del lote y su recepción. Si se omite `sic`, se reutiliza la última versión válida; está prohibido en la primera carga. `sic: []` declara explícitamente que no hay realizados observados.

Éxito: HTTP 200 con `status=published`, `version`, `active_version`, `run_id` y conteos `summary`. Repetición: `status=reused`; no crea versión ni retrocede la visible. Validación: HTTP 422, `errors` localizados y `run_id` cuando el rechazo ocurre dentro del servicio. El lector externo también puede rechazar antes de enviar: en ese caso su `estado.json` contiene el error y no hay corrida nueva en la base.

Se calcula SHA256 de los contratos normalizados resultantes, SIC y parámetros. El merge, el cálculo, la inserción de la versión y el cambio del puntero visible se ejecutan bajo la misma transacción `BEGIN IMMEDIATE`. Si falla, se revierte y se registra el rechazo por separado. Las versiones publicadas son inmutables. SQLite utiliza WAL y claves foráneas.
