# Evidencia de la base v0.1.0

Entorno de preparación Linux x86_64; fecha local de revisión 6 de noviembre de 2026, America/Santiago. Datos exclusivamente ficticios de `examples/`.

| Comprobación | Resultado |
|---|---|
| `npm run build` | TypeScript y Vite compilan |
| `npm test` | 25 pruebas aprobadas |
| Entrada BUK/SIC normalizada | Publica 192 filas mensuales para 16 IDs / 4 institutos |
| Reproceso idéntico | Reutiliza versión, sin duplicar corrida publicada |
| Cambio efectivo en julio | Conserva enero–junio; julio refleja 30 h semanales |
| BUK con horas negativas / duplicado | HTTP 422, error localizado y versión visible conservada |
| Fallo de cálculo / SIC sin contrato | Transacción revertida; publicación previa conservada |
| Reinicio del servicio | Lee la misma última versión desde SQLite |
| Dos publicaciones concurrentes iguales | Una publicación y una reutilización |
| Tramos | Probados 21,99; 22; 39,99; 40 h |
| Abril/mayo | Probado 44 → 42 h |
| Mes parcial, cero horas, licencia, calendario | Pruebas con resultados independientes e identidad de horas |
| Atención grupal | Redondeo mensual de individual, sesiones grupales e indirecta |
| Multiinstituto / SIC con varios cargos | Jornada conjunta para tramo; SIC no duplicado entre cargos |
| Acceso | Token requerido, lector no puede publicar y origen ajeno rechazado |
| Parámetros | Configuración inválida rechazada; guardar válido no publica hasta recalcular |
| Chromium 1440 px | Carga, filtros, cambio, rechazo, historial y CSV comprobados |
| Chromium 390 px | Sin desborde horizontal de página; tabla con scroll propio |
| Consola de página | Sin errores JavaScript en el recorrido |
| Sidecar PyInstaller Linux | Arranque independiente y `--ingest`: carga inicial, cambio de julio y rechazo; v002 conservada |
| Tauri nativo | Intentado `cargo check`; bloqueado por GLib de desarrollo ausente, además no está WebKit de desarrollo |
| Instalador Windows | Pendiente de ejecutar en Windows/VM o CI |
| Blue Prism real | Pendiente de montar y ejecutar en VM de la organización |
| Comparación con Excel oficial | Pendiente: no se adjuntó el kit |

Caso de demo PRO-009, Puerto Montt: enero 193,6 h contratadas; julio tras el cambio 138 h. El resumen inicial ficticio tiene 43.688 atenciones planificadas y meta 39.319,2. No son cifras oficiales ni resultados del kit.

Para repetir el recorrido: README y `scripts/check-ui.mjs`. Para el ejecutable independiente: `python scripts/check-sidecar.py <ruta-al-sidecar>`. Las capturas y estados temporales se generan en `work/`, fuera del control de versiones.
