# Validación del kit y límites reales

Fuente: `ejemplo_salida_Planificacion_Input_BluePrism.xlsx`, SHA256 `fbfc67ed0c755af823ddb3ff97cf8fe3a809594cabcbde80930bcd6e924d662d`.

Se leyeron 3123 registros, 462 IDs distintos y 18 entradas de catálogo de institutos. El número real del archivo se reporta sin sustituirlo por la cifra estimada del enunciado.

**Comparación completa:** 1 de 471 casos coinciden en todos los campos comprobados; 470 presentan diferencias y 0 no tienen cobertura contractual calculable. Coinciden 4487 de 13188 comprobaciones mensuales/anuales.

La referencia no alimenta el motor. Una prueba altera Referencia_Por_Persona y comprueba que el plan no cambia. Las diferencias no se rellenan con valores del Excel para aparentar coincidencia.

## Casos solicitados

| Caso | PersonaId / IT | Resultado | Campos distintos |
|---|---|---|---|
| 40 h con asignación | 137732 / 11 | different | 6 |
| Vacaciones en febrero | 71269 / 11 | different | 6 |
| Tramo T2 | 76852 / 11 | different | 6 |
| Área grupal ED/AS | 140763 / 11 | different | 20 |
| Multiinstituto | 125129 / 21 | different | 28 |

## Hallazgos que deben cerrar reglas y datos

- El caso 137732 reproduce enero: 36 atenciones directas/semana, 11 indirectas, 151 directas del mes y 135 de meta directa. Febrero incorpora sus tres semanas de vacaciones. Esto no implica coincidencia anual completa.
- El libro trae dos alertas NDIAS_NO_CUADRA y tres filas CARGO de encabezado dentro de la matriz. Se informan las alertas y se descartan únicamente esos encabezados repetidos.
- La referencia observada trunca varios planes/metas mensuales; el texto del requerimiento habla de REDONDEAR. REDONDEO_MENSUAL y REDONDEO_META permiten FLOOR o HALF_UP. El modo inicial FLOOR se declara, no se presenta como regla institucional cerrada.
- El reporte contractual llega hasta julio. Agosto–diciembre se proyectan desde el último mes para los vínculos aún presentes; la interfaz informa esos meses. No se inventan contratos para referencias sin vínculo.
- Las asignaciones pendientes no se aplican. La reunión sindical de N_Asignacion=4 se trata como beneficio separado del máximo de dos asignaciones especiales. No aplicar asignaciones especiales cuando HS no supera el mínimo queda informado como excepción.
- Se aplican Excepciones_Horas por mes e instituto reemplazando, no sumando, la jornada del vínculo original. Una celda vacía de esa tabla no prolonga horas del mes anterior.
- Las vigencias exactas de beneficios/asignaciones no están en la tabla plana. Los días adicionales se distribuyen con la política editable declarada; no se copian SemHab ni porcentajes finales de la referencia para cuadrar los números.
- Los feriados incluidos en Semanas_Habiles no se descuentan dos veces. Para calendario regional distinto, cargar Param_Semanas_Instituto. La fuente de feriados detallados no cubre todo el año.
- El SIC de realizados no aparece en este libro plano: actual permanece null. No se fabrica un cero.

## Evidencia y ejecución

El detalle completo está en `validacion_kit.json` y `validacion_diferencias.csv`, generados por `scripts/validar_kit.py`. Los campos analizados son PlanDir/MG_Dir de los doce meses y cuatro totales anuales. Se comparan las 471 filas de referencia, no solo los casos que coinciden.

**No se declara cálculo oficial cerrado ni MVP apto para producción mientras existan diferencias sin resolver.** Blue Prism debe ejecutarse en la VM por el equipo; esta sesión no tiene ese entorno. Supabase remoto requiere configuración de proyecto y sesión. La prueba de UI en navegador sigue limitada por las herramientas disponibles de esta sesión.

Pruebas: `python -m unittest discover -s tests_python -v`, `npm test`, `npm run build`. Medir tiempos de la corrida real en la VM antes de afirmar el objetivo de 60 s o capacidad para 600 profesionales.
