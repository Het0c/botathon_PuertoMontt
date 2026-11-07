# Contrato de resultados del equipo Python · v1

React recibe un **JSON ya limpio y calculado**. No lee los Excel BUK/SIC, no transforma las hojas del traductor y no aplica fórmulas de planificación. La limpieza y la exportación de este formato las implementará el equipo en Python. Blue Prism orquesta el proceso del desafío; el equipo define y valida su etapa de cálculo.

El traductor existente en la raíz genera un Excel intermedio con tablas planas. Ese archivo todavía no es el JSON consumido por esta web: el enlace entre ambos queda a cargo del equipo.

```json
{
  "schema_version": 1,
  "year": 2026,
  "parameters_version": "reglas-2026-v1",
  "rows": [{
    "professional_id": "PRO-001",
    "institute": "Puerto Montt",
    "area": "Rehabilitación",
    "role": "Kinesiología",
    "month": "2026-07",
    "contracted": 138,
    "direct": 89.7,
    "indirect": 34.5,
    "nas": 13.8,
    "absence": 0,
    "planned_direct": 179,
    "planned_indirect": 69,
    "planned": 248,
    "target": 223.2,
    "actual": null,
    "foja": 0.65
  }]
}
```

Cada campo del ejemplo es obligatorio. El documento no admite otros campos. Los textos tienen 1–120 caracteres; las categorías numéricas son finitas y no negativas, con máximo 10.000.000. `actual` puede ser null y debe ser entero cuando existe. `foja` debe ser null con jornada cero y concordar con directa/contratada en el resto. `planned_direct`, `planned_indirect` y `planned` son enteros.

Se admite entre 1 y 20.000 filas, con máximo 10 MB por archivo. La clave única es profesional + instituto + área + cargo + mes. El período de esta base es 2026. Las horas contratadas deben conciliar con directa + indirecta + NAS + ausencias (tolerancia 0,01 h); la meta no puede superar el plan y `planned` debe sumar directa e indirecta. Estas verificaciones comprueban el contrato y sus identidades, no certifican las reglas institucionales.

Python entrega los resultados de todo el plan vigente, incluidos los meses históricos que corresponda conservar. Cada revisión es un snapshot completo; React y Supabase no fusionan contratos ni recalculan meses. La política de vigencias, tramos, redondeo, calendario y asignaciones se valida contra el kit en el proceso de cálculo del equipo.

`actual: 0` significa cero observado; `actual: null`, ausencia de un SIC atribuible a esa fila. Si SIC no distingue cargos o áreas, Python debe evitar duplicarlo entre filas, asignándolo solo cuando el cruce sea inequívoco o entregando null. El resumen suma los realizados atribuidos a las filas.

## Flujo de revisión

1. El editor carga el JSON y se valida en navegador y servidor.
2. Supabase crea una revisión `pending` con número y fecha del servidor.
3. El revisor consulta el detalle, puede exportarlo y escribe una justificación.
4. Aprobar cambia el plan visible en la misma transacción que guarda la decisión y su log. Rechazar mantiene el aprobado anterior.
5. Repetir el mismo documento reutiliza la revisión existente. El hash lo calcula PostgreSQL sobre el JSON, sin confiar en una huella enviada desde el navegador. Una revisión rechazada idéntica sigue rechazada: corregir su salida o versión de reglas antes de enviarla otra vez.

Los logs no guardan archivos BUK/SIC crudos: registran la operación, el usuario autenticado, la revisión y la justificación o errores del contrato. Los snapshots sí contienen los resultados mensuales necesarios para la revisión. No enviar nombres, RUT ni antecedentes clínicos en esta base de demostración.
