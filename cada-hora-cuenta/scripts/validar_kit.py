import argparse,csv,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.kit_teleton import load_kit
from server.domain import calculate
from server.validation_report import compare_reference,markdown

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--kit',required=True);ap.add_argument('--output-dir',required=True);a=ap.parse_args()
    start=time.perf_counter();kit=load_kit(a.kit);result=calculate(kit);report=compare_reference(kit,result);report['elapsed_seconds']=round(time.perf_counter()-start,3)
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
    (out/'validacion_kit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'VALIDACION.md').write_text(markdown(kit,result,report),encoding='utf-8')
    with (out/'validacion_diferencias.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['professional_id','institute_id','status','field','expected','actual','delta']);w.writeheader()
        for c in report['cases']:
            for d in c['differences']:w.writerow({**{k:c[k] for k in ['professional_id','institute_id','status']},**d})
    print(json.dumps({k:v for k,v in report.items() if k!='cases'}))
if __name__=='__main__':main()
