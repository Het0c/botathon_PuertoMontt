"""Genera dos variantes de demo desde el BUK crudo; nunca sobrescribe el original."""
import argparse,copy,datetime as dt,json
from pathlib import Path
from openpyxl import load_workbook

MUST=['PersonaId','Periodo','Horas Semanales','Cargo','IT','Fecha Ingreso Compañía','Fecha Término']

def generate(source,valid_path,invalid_path,excluded=None):
    source=Path(source);valid_path=Path(valid_path);invalid_path=Path(invalid_path)
    if len({source.resolve(),valid_path.resolve(),invalid_path.resolve()})!=3:raise ValueError('Usar rutas distintas para original, válido e inválido')
    if valid_path.exists() or invalid_path.exists():raise FileExistsError('La salida ya existe; elegir una carpeta de lote nueva')
    w=load_workbook(source);ws=w['Dotacion_2026'] if 'Dotacion_2026' in w.sheetnames else w.worksheets[0]
    header=None
    for i,row in enumerate(ws.iter_rows(values_only=True),1):
        if i>15:break
        if set(MUST)<=set(str(v).strip() for v in row if v is not None):header=i;columns=[str(v).strip() if v is not None else '' for v in row];break
    if header is None:raise ValueError('No se encuentra el encabezado del BUK crudo')
    cols={v:i for i,v in enumerate(columns) if v}
    def read(row,k):return row[cols[k]] if k in cols else None
    def put(row,k,v):
        if k in cols:row[cols[k]]=v
    def month(row):
        value=read(row,'Periodo')
        if isinstance(value,(dt.datetime,dt.date)):return value.month
        try:return dt.date.fromisoformat(str(value)[:10]).month
        except ValueError:raise ValueError('Periodo inválido en el archivo de origen')
    original=[list(r) for r in ws.iter_rows(min_row=header+1,values_only=True) if read(r,'PersonaId') is not None]
    latest=max(month(r) for r in original)
    if latest!=7:raise ValueError('La demo agrega agosto a una base que debe terminar en julio')
    july=[r for r in original if month(r)==7]
    eligible=[r for r in july if str(read(r,'PersonaId')) not in set(map(str,excluded or [])) and isinstance(read(r,'Horas Semanales'),(int,float)) and read(r,'Horas Semanales')>0]
    if len(eligible)<6:raise ValueError('Se requieren al menos seis vínculos vigentes elegibles en julio')
    high=next((r for r in eligible if read(r,'Horas Semanales')>=40),None)
    if high is None:raise ValueError('Se requiere una jornada >=40 para demostrar el cambio de tramo')
    selected=[high]+[r for r in eligible if read(r,'PersonaId')!=read(high,'PersonaId')][:4]
    reduce,other,role_change,depart,donor=selected
    departure=(read(depart,'PersonaId'),read(depart,'IT'))
    august=[]
    for source_row in july:
        r=copy.deepcopy(source_row)
        if (read(r,'PersonaId'),read(r,'IT'))==departure:continue
        put(r,'Periodo',dt.datetime(2026,8,1))
        if read(r,'PersonaId')==read(reduce,'PersonaId'):put(r,'Horas Semanales',22)
        if read(r,'PersonaId')==read(other,'PersonaId'):put(r,'Horas Semanales',40 if read(other,'Horas Semanales')<40 else 30)
        if read(r,'PersonaId')==read(role_change,'PersonaId'):
            alternative=next((a for a in eligible if read(a,'Cargo')!=read(r,'Cargo')),None)
            if alternative is None:raise ValueError('Se necesitan dos cargos distintos')
            for name in ['Cargo','Cod_Esp','Nombre Sub-área','Centro de Costo']:put(r,name,read(alternative,name))
        august.append(r)
    for r in original:
        if month(r)==7 and (read(r,'PersonaId'),read(r,'IT'))==departure:put(r,'Fecha Término',dt.datetime(2026,7,31))
    max_id=max(int(read(r,'PersonaId')) for r in original if str(read(r,'PersonaId')).isdigit())
    new_ids=[max_id+10001,max_id+10002]
    for n,pid in enumerate(new_ids):
        r=copy.deepcopy(donor);put(r,'PersonaId',pid);put(r,'Periodo',dt.datetime(2026,8,1));put(r,'Fecha Ingreso Compañía',dt.datetime(2026,8,1));put(r,'Fecha Término',dt.datetime(2026,8,20) if n else None);put(r,'Tipo de Contrato','Plazo fijo' if n else 'Indefinido');put(r,'Fecha de Nacimiento',None)
        august.append(r)
    ws.delete_rows(header+1,max(0,ws.max_row-header))
    for r in original+august:ws.append(r)
    valid_path.parent.mkdir(parents=True,exist_ok=True);invalid_path.parent.mkdir(parents=True,exist_ok=True);w.save(valid_path)
    bad_ids=[]
    for n in range(3):
        r=copy.deepcopy(august[0]);pid=max_id+10003+n;bad_ids.append(pid);put(r,'PersonaId',pid)
        if n==0:put(r,'Horas Semanales',None)
        if n==1:put(r,'Cargo','CARGO_INEXISTENTE_DEMO')
        if n==2:put(r,'Fecha Ingreso Compañía',dt.datetime(2026,8,10));put(r,'Fecha Término',dt.datetime(2026,8,1))
        ws.append(r)
    w.save(invalid_path);w.close()
    return {'source':source.name,'month_added':8,'base_rows':len(original),'august_rows':len(august),
        'new_ids':new_ids,'departure':list(departure),'hours_changes':[{'professional_id':read(reduce,'PersonaId'),'before':read(reduce,'Horas Semanales'),'after':22},{'professional_id':read(other,'PersonaId'),'before':read(other,'Horas Semanales'),'after':40 if read(other,'Horas Semanales')<40 else 30}],
        'role_change':read(role_change,'PersonaId'),'fixed_term_new_id':new_ids[1],'invalid_ids':bad_ids,
        'note':'Si la jornada nominal fue 44, julio puede figurar con 42 por la reducción legal. Se reporta el antes real, no se altera julio para fingir 44.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output-valid',required=True);ap.add_argument('--output-invalid',required=True);ap.add_argument('--kit-referencia');a=ap.parse_args()
    excluded=[]
    if a.kit_referencia:
        w=load_workbook(a.kit_referencia,read_only=True,data_only=True);rows=w['Excepciones_Horas'].iter_rows(values_only=True);h=list(next(rows));idx=h.index('PersonaId');excluded=[r[idx] for r in rows if r[idx] is not None];w.close()
    result=generate(a.input,a.output_valid,a.output_invalid,excluded)
    target=Path(a.output_valid).with_suffix('.manifest.json');target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
