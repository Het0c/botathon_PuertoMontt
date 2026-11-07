"""Adaptador del libro plano producido por bot_traductor.py, sin modificar el traductor."""
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import unicodedata
import zipfile
from openpyxl import load_workbook

MAX_BYTES = 20 * 1024 * 1024
REQUIRED = {
    'Dotacion_Mes': ['Clave','PersonaId','IT','Mes','Cargo','Horas_Semanales','Fecha_Ingreso','Fecha_Termino','N_Dias_Semana','Vigente_Mes','Alerta'],
    'Cambios_Mes': ['PersonaId','IT','Mes','Tipo_Cambio'],
    'Param_Generales': ['Parametro','Valor'],
    'Param_Distribucion_Cargo': ['Cargo','Tramo_Horas','Pct_Directo','Pct_Indirecto','Pct_NAS','Min_Estandar_Directa','Min_Estandar_Indirecta'],
    'Param_Semanas_Habiles': ['Mes','Semanas_Habiles'],
    'Param_Institutos': ['IT','Nombre','Sigla'],
    'Asignaciones_Especiales': ['PersonaId','IT','Asignacion','Horas_Semana','Estado'],
    'Ausencias_Mes': ['PersonaId','IT','Mes','Total_Semanas_Ausente'],
    'Dias_Adicionales': ['PersonaId','IT'],
    'Excepciones_Horas': ['PersonaId','IT'],
    'Referencia_Por_Persona': ['PersonaId','IT','Plan_Anual_Directa','MG_Anual_Directa'],
}
# Explicit minimum-data projection: no dates of birth, names, free observations or raw logs.
DROP = {'Fecha_Nacimiento','Observaciones','Unidad','Quien_Define','Mensaje','Centro_Costo','Descripcion_CCosto'}
DOT_FIELDS = {'Clave','IT','Instituto','PersonaId','Periodo','Mes','Cargo','Cod_Esp','Sub_Area','Tipo_Contrato','Tipo_Trabajador','Fecha_Ingreso','Fecha_Termino','Mes_Cumpleanos','Horas_Semanales','Tramo_Horas','Dias_Jornada','N_Dias_Semana','Vigente_Mes','Alerta'}

class KitError(ValueError):
    def __init__(self, errors):
        self.errors = errors if isinstance(errors,list) else [{'sheet':'Libro','row':None,'field':'','code':'INVALID','severity':'error','message':str(errors)}]
        super().__init__('; '.join(e['message'] for e in self.errors[:10]))

def canonical(value):
    return unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode().strip().upper()

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def date_value(value):
    if value in (None,''): return None
    if isinstance(value,dt.datetime):return value.date().isoformat()
    if isinstance(value,dt.date):return value.isoformat()
    try:return dt.date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:raise ValueError('Fecha inválida: usar AAAA-MM-DD')

def issue(sheet,row,field,code,message,severity='error',**keys):
    return {'sheet':sheet,'row':row,'field':field,'code':code,'message':message,'severity':severity,**keys}

def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def load_kit(source):
    data = Path(source).read_bytes() if isinstance(source,(str,Path)) else source
    if len(data)>MAX_BYTES:raise KitError('El libro supera 20 MB')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if sum(i.file_size for i in z.infolist())>150*1024*1024:raise KitError('Libro expandido demasiado grande')
        wb=load_workbook(io.BytesIO(data),read_only=True,data_only=False)
    except KitError:raise
    except Exception:raise KitError('Excel plano ilegible. Ejecutar primero bot_traductor.py.')
    tables={};errors=[]
    try:
        for name,cols in REQUIRED.items():
            if name not in wb.sheetnames:errors.append(issue(name,None,'','MISSING_SHEET','Falta hoja '+name))
        if errors:raise KitError(errors)
        for ws in wb:
            if ws.title=='Log':continue
            if ws.title not in REQUIRED and not ws.title.startswith('Param_') and ws.title not in ('Personas','Referencia_Por_Instituto'):continue
            iterator=ws.iter_rows(values_only=True)
            headers=[str(v).strip() if v is not None else '' for v in next(iterator,[])]
            if len(set(headers))!=len(headers) or not set(REQUIRED.get(ws.title,[])).issubset(headers):
                errors.append(issue(ws.title,1,'','HEADER','Encabezados incompletos o duplicados'));continue
            rows=[]
            for line,values in enumerate(iterator,2):
                if line>20001:raise KitError('Máximo 20.000 filas por hoja')
                if not any(v is not None for v in values):continue
                if any(isinstance(v,str) and v.startswith('=') for v in values):
                    errors.append(issue(ws.title,line,'','FORMULA','El libro plano debe tener valores, no fórmulas'));continue
                r={}
                for k,v in zip(headers,values):
                    if k in DROP or (ws.title=='Dotacion_Mes' and k not in DOT_FIELDS):continue
                    if isinstance(v,(dt.date,dt.datetime)):v=date_value(v)
                    if isinstance(v,str):v=v.strip() or None
                    r[k]=v
                if ws.title=='Param_Distribucion_Cargo' and canonical(r.get('Cargo'))=='CARGO':continue
                r['_row']=line;rows.append(r)
            tables[ws.title]=rows
    finally:wb.close()
    if errors:raise KitError(errors[:100])
    params={name:rows for name,rows in tables.items() if name.startswith('Param_')}
    params['politicas']={'TOPE_ANTES_MAYO':44,'TOPE_DESDE_MAYO':42,'MES_CAMBIO_LEGAL':5,
        'REDONDEO_MENSUAL':'FLOOR','REDONDEO_META':'FLOOR','REDONDEO_GRUPAL':'FLOOR',
        'PROYECTAR_ULTIMO_MES':True,'REPARTO_DIAS_EXTRA':'segundo_semestre',
        'ALERTAS_BLOQUEANTES':['SIN_HORAS','SIN_CARGO','SIN_COD_ESP'],
        'COLACION_EN_CONTRATO':True,'INSTITUTOS_GRUPO_MAYOR':[81,131]}
    params=validate_parameters(params)
    matrices={(canonical(r['Cargo']),r['Tramo_Horas']) for r in params['Param_Distribucion_Cargo']}
    seen=set();warnings=[]
    for r in tables['Dotacion_Mes']:
        line=r['_row'];keys={'professional_id':str(r.get('PersonaId')),'institute_id':r.get('IT'),'month':r.get('Mes')}
        def add(field,code,message,severity='error'):errors.append(issue('Dotacion_Mes',line,field,code,message,severity,**keys))
        if not r.get('Clave') or r['Clave'] in seen:add('Clave','DUPLICATE','Clave ausente o duplicada')
        seen.add(r.get('Clave'))
        h=r.get('Horas_Semanales')
        if not finite(h) or not 0<=h<=44:add('Horas_Semanales','HOURS','Horas semanales deben estar entre 0 y 44')
        if not finite(r.get('Mes')) or r['Mes']!=int(r['Mes']) or not 1<=r['Mes']<=12:add('Mes','MONTH','Mes inválido')
        if not r.get('PersonaId') or not r.get('IT'):add('PersonaId','IDENTITY','Falta ID ficticio o instituto')
        if not finite(r.get('N_Dias_Semana')) or not 0<r['N_Dias_Semana']<=7:add('N_Dias_Semana','DAYS','Días de jornada deben estar entre 1 y 7')
        for k in ['Fecha_Ingreso','Fecha_Termino']:
            try:r[k]=date_value(r.get(k))
            except ValueError:add(k,'DATE','Fecha inválida')
        if r.get('Fecha_Ingreso') and r.get('Fecha_Termino') and r['Fecha_Termino']<r['Fecha_Ingreso']:add('Fecha_Termino','DATE_ORDER','Fecha término anterior a ingreso')
        if (canonical(r.get('Cargo')),r.get('Tramo_Horas')) not in matrices:add('Cargo','UNKNOWN_ROLE','Cargo/tramo sin matriz')
        if r.get('Vigente_Mes')=='NO' and finite(h) and h>0:add('Vigente_Mes','INACTIVE_HOURS','Contrato no vigente con horas positivas')
        for alert in str(r.get('Alerta') or '').split(';'):
            if alert:add('Alerta',alert,'Alerta declarada por el traductor: '+alert,'error' if alert in params['politicas']['ALERTAS_BLOQUEANTES'] else 'warning')
    warnings=[e for e in errors if e['severity']=='warning'];errors=[e for e in errors if e['severity']=='error']
    if errors:raise KitError(errors[:100])
    return {'schema_version':1,'source_hash':hashlib.sha256(data).hexdigest(),'tables':tables,'parameters':params,
        'warnings':warnings,'counts':{name:len(rows) for name,rows in tables.items()},
        'professionals':len({r['PersonaId'] for r in tables['Dotacion_Mes']}),
        'parameters_version':digest(params)}

def validate_parameters(raw):
    try:p=json.loads(json.dumps(raw,allow_nan=False))
    except (ValueError,TypeError):raise KitError('Parámetros JSON no finitos')
    if not isinstance(p,dict):raise KitError('Se requiere objeto de parámetros')
    for name in ['Param_Generales','Param_Distribucion_Cargo','Param_Semanas_Habiles','Param_Institutos','politicas']:
        if name not in p:raise KitError('Falta '+name)
    g={r.get('Parametro'):r.get('Valor') for r in p['Param_Generales']}
    for key in ['META_GESTION','UMBRAL_TRAMO_1','UMBRAL_TRAMO_2','MIN_ESTANDAR_INDIRECTA','MAX_ASIGNACIONES_ESPECIALES','MIN_HS_PARA_ASIGNACION','MESES_2DO_SEMESTRE']:
        if not finite(g.get(key)):raise KitError('Parámetro numérico requerido: '+key)
    if not 0<=g['META_GESTION']<=1 or not 0<g['UMBRAL_TRAMO_2']<g['UMBRAL_TRAMO_1'] or g['MIN_ESTANDAR_INDIRECTA']<=0 or g['MESES_2DO_SEMESTRE']!=6:raise KitError('Meta, umbrales, minutos o prorrateo inválidos')
    seen=set()
    for r in p['Param_Distribucion_Cargo']:
        key=(canonical(r.get('Cargo')),r.get('Tramo_Horas'))
        if key in seen:raise KitError('Cargo/tramo duplicado')
        seen.add(key)
        vals=[r.get(k) for k in ['Pct_Directo','Pct_Indirecto','Pct_NAS']]
        if any(not finite(v) or not 0<=v<=1 for v in vals) or (sum(vals)!=0 and abs(sum(vals)-1)>.00001):raise KitError('La distribución debe sumar 100% (o 0% para matriz no configurada)')
        for k in ['Min_Estandar_Directa','Min_Estandar_Indirecta']:
            if r.get(k) is not None and (not finite(r[k]) or r[k]<0 or (sum(vals)>0 and r[k]==0)):raise KitError('Minutos inválidos en matriz')
    months=set()
    for r in p['Param_Semanas_Habiles']:
        if r.get('Mes') in months or r.get('Mes') not in range(1,13) or not finite(r.get('Semanas_Habiles')) or not 0<=r['Semanas_Habiles']<=5:raise KitError('Calendario mensual inválido')
        months.add(r['Mes'])
    if len(months)!=12:raise KitError('Se requieren los doce meses de calendario')
    for r in p.get('Param_Asignaciones',[]):
        if r.get('Horas_Semana') is not None and (not finite(r['Horas_Semana']) or not 0<=r['Horas_Semana']<=44):raise KitError('Horas de asignación inválidas')
    for r in p.get('Param_Factor_Grupal',[]):
        if not finite(r.get('Pct_Atencion_Grupal')) or not 0<=r['Pct_Atencion_Grupal']<=1:raise KitError('Porcentaje grupal inválido')
        for key in ['N_Pacientes_Grupo_San_Con','N_Pacientes_Grupo_Otros_IT']:
            if not finite(r.get(key)) or r[key]<0 or (r['Pct_Atencion_Grupal']>0 and r[key]<1):raise KitError('Pacientes grupales inválidos')
    pol=p['politicas']
    for k in ['REDONDEO_MENSUAL','REDONDEO_META','REDONDEO_GRUPAL']:
        if pol.get(k) not in ('FLOOR','HALF_UP'):raise KitError('Política de redondeo inválida')
    for k in ['TOPE_ANTES_MAYO','TOPE_DESDE_MAYO']:
        if not finite(pol.get(k)) or not 0<pol[k]<=44:raise KitError('Tope de jornada inválido')
    if pol.get('MES_CAMBIO_LEGAL') not in range(1,13):raise KitError('Mes de cambio legal inválido')
    return p
