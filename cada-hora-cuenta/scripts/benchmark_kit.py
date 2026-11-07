"""Carga sintética derivada del plano; mide motor local, no Blue Prism/Supabase."""
import argparse,copy,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.kit_teleton import load_kit
from server.domain import calculate

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--kit',required=True);ap.add_argument('--professionals',type=int,default=600);a=ap.parse_args()
    if not 1<=a.professionals<=1200:ap.error('Tamaño entre 1 y 1.200')
    kit=load_kit(a.kit);ids=sorted({str(r['PersonaId']) for r in kit['tables']['Dotacion_Mes']})
    if a.professionals<len(ids):ap.error('Usar un tamaño no inferior al kit de origen')
    originals=copy.deepcopy(kit['tables']);extra=a.professionals-len(ids)
    for n in range(extra):
        source=ids[n%len(ids)];target=900000000+n
        for name in ['Dotacion_Mes','Asignaciones_Especiales','Ausencias_Mes','Dias_Adicionales','Excepciones_Horas']:
            for r in originals[name]:
                if str(r['PersonaId'])==source:
                    new=copy.deepcopy(r);new['PersonaId']=target
                    if name=='Dotacion_Mes':new['Clave']=f'{target}-{new["IT"]}-{new["Mes"]:02}'
                    kit['tables'][name].append(new)
    kit['professionals']=a.professionals
    start=time.perf_counter();result=calculate(kit)
    print(json.dumps({'synthetic':True,'scope':'motor local; no VM/Blue Prism/red','professionals':a.professionals,'rows':len(result['document']['rows']),'institutes':len({r['institute'] for r in result['document']['rows']}),'elapsed_seconds':round(time.perf_counter()-start,3)}))
if __name__=='__main__':main()
