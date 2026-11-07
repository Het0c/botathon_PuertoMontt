"""Puente invocable por Blue Prism; no modifica bot_traductor.py."""
import argparse,base64,json,sys,urllib.request,urllib.error,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.kit_teleton import load_kit,KitError

def main():
    ap=argparse.ArgumentParser()
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--kit');group.add_argument('--manifest')
    ap.add_argument('--status',required=True);ap.add_argument('--output')
    ap.add_argument('--api-url');ap.add_argument('--token-file');ap.add_argument('--normalize-only',action='store_true')
    args=ap.parse_args();run_id=str(uuid.uuid4());code=3
    try:
        if args.api_url:
            if not args.token_file:raise KitError('La conexión a la API requiere --token-file')
            token=Path(args.token_file).read_text().strip()
            payload={'kit_base64':base64.b64encode(Path(args.kit).read_bytes()).decode(),'filename':Path(args.kit).name} if args.kit else {'document':json.loads(Path(args.manifest).read_text(encoding='utf-8'))}
            req=urllib.request.Request(args.api_url.rstrip('/')+'/api/batches',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=60) as response:result=json.load(response)
        elif args.kit:
            kit=load_kit(args.kit)
            if args.normalize_only:
                result={'status':'normalized','stage':'adapter','run_id':run_id,'version':None,'counts':kit['counts'],'warnings':kit['warnings']}
                if args.output:Path(args.output).write_text(json.dumps(kit,ensure_ascii=False,indent=2),encoding='utf-8')
            else:
                from server.domain import calculate
                result=calculate(kit)
                if args.output:Path(args.output).write_text(json.dumps(result['document'],ensure_ascii=False,indent=2),encoding='utf-8')
                result={k:v for k,v in result.items() if k!='document'}
                result.update(run_id=run_id,status='calculated',version=None,published=False)
        else:raise KitError('--manifest requiere --api-url para registrar la revisión en la aplicación')
        code=0
    except KitError as e:result={'status':'rejected','run_id':run_id,'version':None,'errors':e.errors};code=2
    except urllib.error.HTTPError as e:
        try:result=json.load(e)
        except Exception:result={'status':'failed','error':'HTTP '+str(e.code)}
        code=2 if e.code==422 else 3
    except Exception as e:result={'status':'failed','run_id':run_id,'version':None,'error':str(e)}
    target=Path(args.status);target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(target)
    print(json.dumps({k:result[k] for k in ('status','run_id','version') if k in result}));return code
if __name__=='__main__':raise SystemExit(main())
