"""Contrato del frontend y Supabase: solo resultados calculados y mínimos."""
import copy,math
from .kit_teleton import KitError
TEXT=['professional_id','institute','area','role','month']
NUM=['contracted','direct','indirect','nas','absence','planned_direct','planned_indirect','planned','target']
def validate_document(p):
    def invalid(message):raise KitError(message)
    if not isinstance(p,dict) or set(p)!={'schema_version','year','parameters_version','rows'}:invalid('Contrato JSON incompleto o con campos no permitidos')
    if p['schema_version']!=1 or p['year']!=2026 or not isinstance(p['parameters_version'],str) or not 1<=len(p['parameters_version'])<=120:invalid('Esquema, año o versión de parámetros inválidos')
    if not isinstance(p['rows'],list) or not 1<=len(p['rows'])<=20000:invalid('Se requieren entre 1 y 20.000 resultados')
    seen=set()
    for i,r in enumerate(p['rows'],1):
        if not isinstance(r,dict) or set(r)!=set(TEXT+NUM+['actual','foja']):invalid(f'Resultado {i}: columnas incorrectas')
        if any(not isinstance(r[k],str) or not 1<=len(r[k].strip())<=120 for k in TEXT):invalid(f'Resultado {i}: texto requerido')
        if r['month'] not in [f'2026-{m:02}' for m in range(1,13)]:invalid(f'Resultado {i}: mes inválido')
        if any(not isinstance(r[k],(int,float)) or isinstance(r[k],bool) or not math.isfinite(r[k]) or not 0<=r[k]<=10000000 for k in NUM):invalid(f'Resultado {i}: número inválido')
        if any(r[k]!=int(r[k]) for k in ['planned_direct','planned_indirect','planned']):invalid(f'Resultado {i}: atenciones deben ser enteras')
        if abs(r['contracted']-sum(r[k] for k in ['direct','indirect','nas','absence']))>.01:invalid(f'Resultado {i}: horas no concilian')
        if r['planned']!=r['planned_direct']+r['planned_indirect'] or r['target']>r['planned']:invalid(f'Resultado {i}: plan/meta no concilian')
        if r['actual'] is not None and (not isinstance(r['actual'],(int,float)) or not math.isfinite(r['actual']) or not 0<=r['actual']<=10000000 or r['actual']!=int(r['actual'])):invalid(f'Resultado {i}: SIC inválido')
        if r['contracted']==0:
            if r['foja'] is not None:invalid(f'Resultado {i}: FOJA debe ser null')
        elif not isinstance(r['foja'],(int,float)) or not math.isfinite(r['foja']) or abs(r['foja']-r['direct']/r['contracted'])>.0001:invalid(f'Resultado {i}: FOJA no concilia')
        key=tuple(r[k] for k in TEXT)
        if key in seen:invalid(f'Resultado {i}: clave duplicada')
        seen.add(key)
    return copy.deepcopy(p)
