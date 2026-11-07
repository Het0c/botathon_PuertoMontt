# Demo de cinco minutos · kit real y Blue Prism

## Preparación antes del reloj

1. Llevar a la VM los **dos crudos originales** del kit y el repositorio. En este repo solo está su salida plana de ejemplo; los crudos no fueron adjuntados a esta sesión. La prueba automatizada reconstruye un BUK mínimo para QA y usa las funciones del traductor existente; no se presenta como corrida sobre los originales completos.
2. Seguir `BLUE_PRISM.md`, crear `Planificacion`, montar `PA-01 Recepción` y ensayar una corrida. Registrar la versión de VBO utilizada y sus acciones efectivas.
3. Arrancar API en el directorio `cada-hora-cuenta` y frontend con `npm run dev`. Para online: API mediante HTTPS, Supabase configurado y migraciones 001 + 002 aplicadas. En demo local: token privado generado en `work/api-token`, proxy de desarrollo y revisiones en memoria claramente etiquetadas.
4. Procesar el reporte base desde el bot. En React: **Cargar resultados → Traer resultado de Blue Prism**, revisar y aprobar solo como escenario de prueba. Mostrar siempre el aviso de diferencias: el motor todavía no cierra la referencia oficial.
5. Generar dos variantes desde el BUK crudo que termina en julio, sin sobrescribirlo:

```powershell
python scripts/generar_reporte_agosto.py --input "C:/Botathon/base/Nac - Base contratos x mes.xlsx" --output-valid "C:/Botathon/demo/valido/Nac - Base contratos x mes.xlsx" --output-invalid "C:/Botathon/demo/invalido/Nac - Base contratos x mes.xlsx" --kit-referencia "C:/Botathon/base/Planificacion_Input_BluePrism.xlsx"
```

Se generan 2 altas (una con plazo hasta el 20 de agosto), 1 baja, 2 cambios de jornada y 1 cambio de cargo. La variante inválida añade 3 filas: sin horas, cargo inexistente y término anterior a ingreso. `*.manifest.json` identifica los IDs y sus valores antes/después. El cambio a 22 h se toma de una jornada >=40; si julio ya dice 42 por la ley, se informa 42→22 y la jornada nominal previa 44 no se finge como dato de julio.

La opción `--kit-referencia` evita elegir para los cambios de demo a personas cuyas horas serán reemplazadas por Excepciones_Horas. Los dos reportes se pasan por **el traductor original** con el mismo Excel de planificación. Reservar carpetas distintas por lote, para no mezclar estados o versiones.

## Guion cronometrado

| Tiempo | Qué se muestra | Evidencia |
|---|---|---|
| 0:00–0:40 | Panel base, filtro Puerto Montt o caso del kit elegido, enero y meta. Abrir Parámetros y mostrar META_GESTION=0,90. | ID, versión, cifra inicial y reglas del kit. |
| 0:40–1:30 | Llega la variante inválida. Blue Prism recibe, traduce, valida y produce Errores_Reporte.xlsx y notificación simulada. | Tres filas deliberadamente erróneas, con campo/fila; el plan aprobado no cambia. |
| 1:30–2:30 | Llega la variante válida. Mostrar Work Queue con ALTA, BAJA y cambios; el bot ejecuta el lector y consulta estado.json. | run_id, versión de revisión, ItemId completados y duración observada. |
| 2:30–3:40 | En web: traer resultado, Cambios del reporte, impacto en meta y un mes anterior conservado. Consultar revisión y justificar la decisión de demo. | Antes/después del manifest, delta de agosto y enero sin alteración. |
| 3:40–4:30 | Cambiar META_GESTION a 85 en Parámetros, guardar y recalcular. Abrir la nueva revisión. | Plan de atenciones igual; meta menor; plan aprobado anterior hasta decidir. |
| 4:30–5:00 | Diagrama de arquitectura y alcance real. | Qué hizo Blue Prism, qué calculó la aplicación, registro Supabase y límites de exactitud. |

No ocultar la diferencia con las 471 referencias ni afirmar que el cálculo es oficial. En la lámina, separar resultados comprobados de reglas pendientes de cerrar con el equipo. El caso 137732 reproduce enero y febrero, pero no implica validación anual de los 471.

## Comprobaciones del ensayo

- El teclado permite llegar a filtros, carga, parámetros y revisión; Enter/Space activan botones y el foco se ve. ID profesional abre su detalle y mes.
- Los avisos tienen texto, no solo color; errores usan `role=alert` y estado `role=status`.
- No hay copia/pega de filas entre Excel y el panel. El bot entrega el libro plano a la API.
- Un reintento del mismo libro/parámetros reutiliza la corrida; un error conserva el último resultado calculado y el plan aprobado.
- Con Supabase, un editor no aprueba: la cuenta de reviewer/admin hace la decisión. La cola Completed significa ingestión completada, no autorización clínica o institucional.
- Capturar duración de carga, número real de personas/sedes, ítems por etiqueta y diferencias. No prometer capacidad ni tiempos de la VM basándose solo en el benchmark Linux.
