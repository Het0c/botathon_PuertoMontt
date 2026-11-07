# Motor y decisiones pendientes del kit

El cálculo utiliza exclusivamente Dotacion_Mes, Param_*, Asignaciones_Especiales, Ausencias_Mes, Dias_Adicionales y Excepciones_Horas. Referencia_* se consulta después, desde un módulo de comparación separado.

- El tramo se decide por el promedio anual ponderado por días de vigencia del vínculo persona/instituto. Las horas excepcionales reemplazan ese vínculo por mes. No se deduplica una persona eliminando sus otras sedes.
- Se aplica el tope legal editable 44/42 con cambio inicial en mayo. Los meses posteriores al último observado se proyectan solo para vínculos que aún aparecen en ese último mes. La ausencia se interpreta como baja en el siguiente snapshot mensual completo; esta semántica debe conservarse al cambiar la fuente.
- Pausa y colación son componentes descriptivos de NAS de matriz; no se restan otra vez además de HS × Pct_NAS. Las entradas no identifican todas las vigencias de beneficios individuales. El valor de colación desglosada no cambia por sí solo el total de NAS de la matriz.
- Asignaciones VIGENTE se aplican cuando HS supera el mínimo; POR_AUTORIZAR no. El máximo controla asignaciones especiales; N_Asignacion=4 (reunión sindical dentro del contrato) se trata aparte. Horas sin autorización numérica se informan, no se adivinan.
- Se reparte HS disponible entre directa e indirecta en la proporción de la matriz. Atenciones semanales se truncan antes del factor grupal. Las tres políticas de redondeo son visibles y editables; hay una contradicción entre REDONDEAR del texto y truncamientos que se observan en el Excel de referencia.
- Semanas efectivas = calendario × fracción de contrato − ausencias − días adicionales prorrateados / 5. Feriados ya contenidos en Semanas_Habiles no se descuentan otra vez. Param_Semanas_Instituto permite sustituir el calendario por IT/mes.
- Los días adicionales incluyen ponderadores de progresivos, complementarios, Ley 21.530 y vacaciones pendientes. Cumpleaños, vísperas y zona extrema van al mes indicado; el resto se reparte en los meses configurados de segundo semestre o todo el año. Esa decisión todavía debe cotejarse con las fórmulas originales.
- Meta de cada categoría = plan × META_GESTION, con política de redondeo declarada. FOJA es horas directas / contratadas; en agregados se dividen las sumas. Horas de ausencia se separan de NAS.
- Si cambian solo datos contractuales, se preservan los meses completos anteriores a la vigencia detectada. Si se editan parámetros, el recálculo anual crea otra revisión completa. Supabase mantiene el plan aprobado hasta la decisión humana.

**Estado: provisional, no validado oficialmente.** El informe da 1/471 coincidencias completas. No se deben ajustar casos copiando valores de Referencia_Por_Persona al motor. Las diferencias requieren cerrar prorrateos, vigencias de asignaciones y redondeos con los archivos/fórmulas originales o el responsable del kit.
