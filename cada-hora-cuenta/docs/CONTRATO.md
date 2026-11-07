# Contrato de resultados del equipo Python · v1

El camino principal v0.3 es **Blue Prism → libro plano del traductor → API de la aplicación**. El adaptador lee Dotacion_Mes, Param_*, entradas humanas y excepciones; el motor calcula este JSON de resultados. React muestra y revisa el resultado. Se conserva la carga directa del JSON como alternativa. La limpieza de los dos crudos sigue en bot_traductor.py, sin reescribirlo.

El traductor existente en la raíz genera un Excel intermedio con tablas planas. La API ya adapta ese archivo a los resultados; el equipo debe ejecutar y validar su orquestación Blue Prism en la VM.

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

La API entrega el plan completo y conserva meses previos a cambios contractuales cuando las reglas no cambian. Un cambio de parámetros recalcula el año y crea otra revisión. Supabase conserva snapshots completos y el último aprobado; las fórmulas del motor aún tienen diferencias que cerrar con el kit. Ver REGLAS.md y VALIDACION.md.

`actual: 0` significa cero observado; `actual: null`, ausencia de un SIC atribuible a esa fila. Si SIC no distingue cargos o áreas, Python debe evitar duplicarlo entre filas, asignándolo solo cuando el cruce sea inequívoco o entregando null. El resumen suma los realizados atribuidos a las filas.

## Flujo de revisión

1. El editor carga el JSON y se valida en navegador y servidor.
2. Supabase crea una revisión `pending` con número y fecha del servidor.
3. El revisor consulta el detalle, puede exportarlo y escribe una justificación.
4. Aprobar cambia el plan visible en la misma transacción que guarda la decisión y su log. Rechazar mantiene el aprobado anterior.
5. Repetir el mismo documento reutiliza la revisión existente. El hash lo calcula PostgreSQL sobre el JSON, sin confiar en una huella enviada desde el navegador. Una revisión rechazada idéntica sigue rechazada: corregir su salida o versión de reglas antes de enviarla otra vez.

Los logs no guardan archivos BUK/SIC crudos: registran la operación, el usuario autenticado, la revisión y la justificación o errores del contrato. Los snapshots sí contienen los resultados mensuales necesarios para la revisión. No enviar nombres, RUT ni antecedentes clínicos en esta base de demostración.
