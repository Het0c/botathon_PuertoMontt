"""Comparación independiente. La referencia solo se consulta después del cálculo."""
import collections,json
from pathlib import Path
from .domain import MONTHS

def compare_reference(kit,result):
    names={int(r['IT']):str(r['Nombre']) for r in kit['parameters']['Param_Institutos']}
    rows=collections.defaultdict(list);details=collections.defaultdict(list)
    for r in result['document']['rows']:rows[(r['professional_id'],r['institute'])].append(r)
    for r in result['details']:details[(r['professional_id'],int(r['institute_id']))].append(r)
    comparisons=[]
    for reference in kit['tables']['Referencia_Por_Persona']:
        pid=str(reference['PersonaId']);it=int(reference['IT']);actual=rows[(pid,names.get(it,str(it)))];det=details[(pid,it)]
        differences=[];checks=[]
        def check(field,obtained):
            expected=reference.get(field)
            if expected is None:return
            matched=abs(obtained-float(expected))<.000001
            checks.append({'field':field,'expected':expected,'actual':obtained,'match':matched})
            if not matched:differences.append({'field':field,'expected':expected,'actual':obtained,'delta':obtained-float(expected)})
        for m,suffix in enumerate(MONTHS,1):
            check('PlanDir_'+suffix,sum(r['planned_direct'] for r in actual if r['month']==f'2026-{m:02}'))
            check('MG_Dir_'+suffix,sum(r['target_direct'] for r in det if r['month']==m))
        check('Plan_Anual_Directa',sum(r['planned_direct'] for r in actual));check('Plan_Anual_Indirecta',sum(r['planned_indirect'] for r in actual))
        check('MG_Anual_Directa',sum(r['target_direct'] for r in det));check('MG_Anual_Indirecta',sum(r['target_indirect'] for r in det))
        comparisons.append({'professional_id':pid,'institute_id':it,'role':reference['Cargo'],'status':'missing' if not actual else 'match' if not differences else 'different','checks':checks,'differences':differences})
    return {'reference_cases':len(comparisons),'matched':sum(r['status']=='match' for r in comparisons),'different':sum(r['status']=='different' for r in comparisons),'missing':sum(r['status']=='missing' for r in comparisons),
        'checks':sum(len(r['checks']) for r in comparisons),'checks_matched':sum(c['match'] for r in comparisons for c in r['checks']), 'cases':comparisons}

def markdown(kit,result,report):
    references=kit['tables']['Referencia_Por_Persona'];selected=[('40 h con asignación','137732',11)]
    def choose(label,predicate):
        r=next((r for r in references if predicate(r)),None)
        if r:selected.append((label,str(r['PersonaId']),int(r['IT'])))
    vacation={(str(r['PersonaId']),int(r['IT'])) for r in kit['tables']['Ausencias_Mes'] if r['Mes']==2 and (r.get('Semanas_Vacaciones') or 0)>0 and str(r['PersonaId'])!='137732'}
    choose('Vacaciones en febrero',lambda r:(str(r['PersonaId']),int(r['IT'])) in vacation)
    choose('Tramo T2',lambda r:22<=float(r.get('Prom_Pond_HS') or 0)<40)
    choose('Área grupal ED/AS',lambda r:r.get('Cod_Esp') in ('ED','AS'))
    choose('Multiinstituto',lambda r:str(r['PersonaId'])=='125129')
    lines=['# Validación del kit y límites reales','',f"Fuente: `ejemplo_salida_Planificacion_Input_BluePrism.xlsx`, SHA256 `{kit['source_hash']}`.",'',
        f"Se leyeron {kit['counts']['Dotacion_Mes']} registros, {kit['professionals']} IDs distintos y {len(kit['parameters']['Param_Institutos'])} entradas de catálogo de institutos. El número real del archivo se reporta sin sustituirlo por la cifra estimada del enunciado.",'',
        f"**Comparación completa:** {report['matched']} de {report['reference_cases']} casos coinciden en todos los campos comprobados; {report['different']} presentan diferencias y {report['missing']} no tienen cobertura contractual calculable. Coinciden {report['checks_matched']} de {report['checks']} comprobaciones mensuales/anuales.",'',
        'La referencia no alimenta el motor. Una prueba altera Referencia_Por_Persona y comprueba que el plan no cambia. Las diferencias no se rellenan con valores del Excel para aparentar coincidencia.','',
        '## Casos solicitados','', '| Caso | PersonaId / IT | Resultado | Campos distintos |','|---|---|---|---|']
    for label,pid,it in selected:
        c=next(c for c in report['cases'] if c['professional_id']==pid and c['institute_id']==it)
        lines.append(f"| {label} | {pid} / {it} | {c['status']} | {len(c['differences'])} |")
    lines+=['','## Hallazgos que deben cerrar reglas y datos','',
        '- El caso 137732 reproduce enero: 36 atenciones directas/semana, 11 indirectas, 151 directas del mes y 135 de meta directa. Febrero incorpora sus tres semanas de vacaciones. Esto no implica coincidencia anual completa.',
        '- El libro trae dos alertas NDIAS_NO_CUADRA y tres filas CARGO de encabezado dentro de la matriz. Se informan las alertas y se descartan únicamente esos encabezados repetidos.',
        '- La referencia observada trunca varios planes/metas mensuales; el texto del requerimiento habla de REDONDEAR. REDONDEO_MENSUAL y REDONDEO_META permiten FLOOR o HALF_UP. El modo inicial FLOOR se declara, no se presenta como regla institucional cerrada.',
        '- El reporte contractual llega hasta julio. Agosto–diciembre se proyectan desde el último mes para los vínculos aún presentes; la interfaz informa esos meses. No se inventan contratos para referencias sin vínculo.',
        '- Las asignaciones pendientes no se aplican. La reunión sindical de N_Asignacion=4 se trata como beneficio separado del máximo de dos asignaciones especiales. No aplicar asignaciones especiales cuando HS no supera el mínimo queda informado como excepción.',
        '- Se aplican Excepciones_Horas por mes e instituto reemplazando, no sumando, la jornada del vínculo original. Una celda vacía de esa tabla no prolonga horas del mes anterior.',
        '- Las vigencias exactas de beneficios/asignaciones no están en la tabla plana. Los días adicionales se distribuyen con la política editable declarada; no se copian SemHab ni porcentajes finales de la referencia para cuadrar los números.',
        '- Los feriados incluidos en Semanas_Habiles no se descuentan dos veces. Para calendario regional distinto, cargar Param_Semanas_Instituto. La fuente de feriados detallados no cubre todo el año.',
        '- El SIC de realizados no aparece en este libro plano: actual permanece null. No se fabrica un cero.',
        '', '## Evidencia y ejecución','',
        'El detalle completo está en `validacion_kit.json` y `validacion_diferencias.csv`, generados por `scripts/validar_kit.py`. Los campos analizados son PlanDir/MG_Dir de los doce meses y cuatro totales anuales. Se comparan las 471 filas de referencia, no solo los casos que coinciden.',
        '', '**No se declara cálculo oficial cerrado ni MVP apto para producción mientras existan diferencias sin resolver.** Blue Prism debe ejecutarse en la VM por el equipo; esta sesión no tiene ese entorno. Supabase remoto requiere configuración de proyecto y sesión. La prueba de UI en navegador sigue limitada por las herramientas disponibles de esta sesión.',
        '', 'Pruebas: `python -m unittest discover -s tests_python -v`, `npm test`, `npm run build`. Medir tiempos de la corrida real en la VM antes de afirmar el objetivo de 60 s o capacidad para 600 profesionales.'
    ]
    return '\n'.join(lines)+'\n'
