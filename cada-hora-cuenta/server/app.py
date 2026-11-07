"""API de cálculo opcional, Windows/Linux. Estado local atómico; publicación en Supabase."""
import argparse,base64,copy,datetime as dt,importlib.util,json,os,secrets,threading,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from .kit_teleton import KitError,load_kit,validate_parameters,digest
from .contract import validate_document

class Service:
    def __init__(self,directory,token,supabase_url='',supabase_key='',supabase_access_token=''):
        self.directory=Path(directory);self.directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.path=self.directory/'state.json';self.token=token;self.lock=threading.RLock()
        self.supabase_url=supabase_url.rstrip('/');self.supabase_key=supabase_key;self.supabase_access_token=supabase_access_token
        self.state=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'sequence':0,'runs':[],'parameters_history':[]}
    def save(self):
        temp=self.path.with_suffix('.tmp')
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(self.state,f,ensure_ascii=False,allow_nan=False)
        os.replace(temp,self.path)
    def remote(self,path,token,body=None):
        if not self.supabase_url or not self.supabase_key:raise RuntimeError('Supabase no está configurado en la API')
        req=Request(self.supabase_url+path,data=None if body is None else json.dumps(body).encode(),headers={'apikey':self.supabase_key,'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urlopen(req,timeout=30) as response:return json.load(response)
    def authorize(self,token,write):
        if secrets.compare_digest(token.encode(),self.token.encode()):return {'actor':'equipo-vm','remote_token':self.supabase_access_token}
        if not self.supabase_url:raise PermissionError('Token de sesión inválido')
        user=self.remote('/auth/v1/user',token)
        member=self.remote('/rest/v1/plan_members?select=role&user_id=eq.'+user['id'],token)
        if not member or (write and member[0]['role'] not in ('editor','admin')):raise PermissionError('La cuenta no tiene permisos para esta operación')
        return {'actor':user['id'],'remote_token':token}
    def batch(self,payload,session):
        with self.lock:
            original=copy.deepcopy(self.state);run_id=str(uuid.uuid4())
            try:
                if 'kit_base64' in payload:
                    try:data=base64.b64decode(payload['kit_base64'],validate=True)
                    except Exception:raise KitError('kit_base64 inválido')
                    kit=load_kit(data)
                    # Reapply an explicitly edited draft to later reports, not old fictitious defaults.
                    if self.state.get('parameters_edited'):kit['parameters']=self.state['parameters'];kit['parameters_version']=digest(kit['parameters'])
                    signature=digest({'source':kit['source_hash'],'params':kit['parameters_version']})
                    if self.state.get('latest',{}).get('input_signature')==signature:return {**copy.deepcopy(self.state['latest']),'status':'reused'}
                    result=self.compute(kit)
                elif 'document' in payload:
                    document=validate_document(payload['document']);signature=digest(document)
                    if self.state.get('latest',{}).get('input_signature')==signature:return {**copy.deepcopy(self.state['latest']),'status':'reused'}
                    result={'document':document,'status':'calculated','warnings':[],'changes':[]}
                    kit=None
                else:raise KitError('Se requiere kit_base64 o document')
                revision=None
                if result.get('document') and session.get('remote_token'):
                    if kit:self.remote('/rest/v1/rpc/save_calculation_parameters',session['remote_token'],{'p_version':kit['parameters_version'],'p_parameters':kit['parameters']})
                    revision=self.remote('/rest/v1/rpc/submit_plan_revision',session['remote_token'],{'p_payload':result['document'],'p_source_label':str(payload.get('filename') or 'Blue Prism')[:120]})
                self.state['sequence']+=1
                result.update(input_signature=signature,run_id=run_id,version=revision['version'] if revision else self.state['sequence'],
                    revision_id=revision['id'] if revision else None,published=False,revision_status=revision['status'] if revision else 'local_draft',
                    source='supabase' if revision else 'vm',created_at=dt.datetime.now(dt.timezone.utc).isoformat())
                if kit:self.state.update(kit=kit,parameters=kit['parameters'])
                self.state['latest']=result
                self.state['runs'].append({'run_id':run_id,'status':result['status'],'version':result['version'],'actor':session['actor'],'created_at':result['created_at']})
                self.state['runs']=self.state['runs'][-100:];self.save()
                return result
            except Exception as exc:
                self.state=original
                errors=exc.errors if isinstance(exc,KitError) else [{'message':type(exc).__name__+': fallo de cálculo o publicación'}]
                self.state['runs'].append({'run_id':run_id,'status':'rejected','errors':errors,'actor':session['actor'],'created_at':dt.datetime.now(dt.timezone.utc).isoformat()});self.state['runs']=self.state['runs'][-100:];self.save()
                raise
    def compute(self,kit):
        if importlib.util.find_spec('server.domain'):
            from .domain import calculate
            result=calculate(kit,previous=self.state.get('latest'))
            from .validation_report import compare_reference
            validation=compare_reference(kit,result)
            result['validation']={k:v for k,v in validation.items() if k!='cases'}
            return result
        return {'status':'normalized','stage':'adapter','counts':kit['counts'],'warnings':kit['warnings'],'professionals':kit['professionals']}
    def parameters(self):
        if 'parameters' not in self.state:raise KitError('Primero se debe procesar el Excel plano del kit')
        return {'params':self.state['parameters'],'hash':digest(self.state['parameters']),'history':self.state['parameters_history'][-20:]}
    def edit_parameters(self,params,session):
        with self.lock:
            p=validate_parameters(params);h=digest(p)
            if session.get('remote_token'):self.remote('/rest/v1/rpc/save_calculation_parameters',session['remote_token'],{'p_version':h,'p_parameters':p})
            self.state['parameters_history'].append({'hash':h,'actor':session['actor'],'date':dt.datetime.now(dt.timezone.utc).isoformat()})
            self.state.setdefault('parameter_sets',{})[h]=p
            self.state.update(parameters=p,parameters_edited=True);self.save();return self.parameters()
    def recalculate(self,session):
        with self.lock:
            if 'kit' not in self.state:raise KitError('Primero se debe procesar el kit')
            kit=copy.deepcopy(self.state['kit']);kit['parameters']=self.state['parameters'];kit['parameters_version']=digest(kit['parameters'])
            # Keep the same durable batch path and remote review semantics.
            previous=copy.deepcopy(self.state);signature=digest({'source':kit['source_hash'],'params':kit['parameters_version']})
            if self.state.get('latest',{}).get('input_signature')==signature:return {**copy.deepcopy(self.state['latest']),'status':'reused'}
            result=self.compute(kit);self.state['kit']=kit
            try:
                result.update(status='calculated')
                revision=self.remote('/rest/v1/rpc/submit_plan_revision',session['remote_token'],{'p_payload':result['document'],'p_source_label':'Recálculo de parámetros'}) if session.get('remote_token') else None
                self.state['sequence']+=1;result.update(input_signature=signature,run_id=str(uuid.uuid4()),version=revision['version'] if revision else self.state['sequence'],revision_id=revision['id'] if revision else None,published=False,revision_status=revision['status'] if revision else 'local_draft',source='supabase' if revision else 'vm',created_at=dt.datetime.now(dt.timezone.utc).isoformat())
                self.state['latest']=result;self.state['runs'].append({'run_id':result['run_id'],'status':'calculated','version':result['version'],'actor':session['actor'],'created_at':result['created_at']});self.state['runs']=self.state['runs'][-100:];self.save();return result
            except Exception:self.state=previous;raise

def handler(service,origins):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,code,data):
            raw=b'' if code==204 else json.dumps(data,ensure_ascii=False,allow_nan=False).encode();self.send_response(code)
            self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store')
            origin=self.headers.get('Origin')
            if origin in origins:self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin')
            self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type');self.send_header('Access-Control-Allow-Methods','GET,POST,PUT,OPTIONS')
            self.end_headers();self.wfile.write(raw)
        def do_OPTIONS(self):
            if self.headers.get('Origin') not in origins:return self.send(403,{'error':'Origen no permitido'})
            self.send(204,{})
        def perform(self):
            try:
                origin=self.headers.get('Origin')
                if origin and origin not in origins:raise PermissionError('Origen no permitido')
                value=self.headers.get('Authorization','');token=value[7:] if value.startswith('Bearer ') else ''
                session=service.authorize(token,self.command!='GET')
                body={}
                if self.command!='GET':
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=30*1024*1024:return self.send(413,{'error':'Tamaño de petición inválido'})
                    try:body=json.loads(self.rfile.read(length))
                    except (ValueError,UnicodeDecodeError):raise KitError('JSON ilegible')
                    if not isinstance(body,dict):raise KitError('Se requiere un objeto JSON')
                path=self.path.split('?')[0]
                if path=='/api/health' and self.command=='GET':result={'status':'ok','storage':'supabase' if service.supabase_url else 'local-draft','actor':session['actor']}
                elif path=='/api/parameters' and self.command=='GET':result=service.parameters()
                elif path=='/api/parameters' and self.command=='PUT':result=service.edit_parameters(body.get('params'),session)
                elif path=='/api/batches' and self.command=='POST':result=service.batch(body,session)
                elif path=='/api/recalculate' and self.command=='POST':result=service.recalculate(session)
                elif path=='/api/latest' and self.command=='GET':result=service.state.get('latest')
                elif path=='/api/runs' and self.command=='GET':result={'runs':service.state['runs']}
                else:return self.send(404,{'error':'Ruta desconocida'})
                return self.send(200,result)
            except PermissionError as exc:self.send(403,{'error':str(exc)})
            except KitError as exc:self.send(422,{'status':'rejected','errors':exc.errors,'error':str(exc)})
            except HTTPError:self.send(502,{'status':'failed','error':'Supabase rechazó la operación; la versión aprobada se conserva'})
            except Exception:self.send(500,{'status':'failed','error':'Fallo de la API. Consultar el estado de la corrida; no se reemplaza el plan aprobado.'})
        do_GET=perform;do_POST=perform;do_PUT=perform
    return Handler

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--data-dir',default='work/calculation');parser.add_argument('--token-file',default='work/api-token')
    a=parser.parse_args();path=Path(a.token_file);path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        fd=os.open(path,os.O_CREAT|os.O_WRONLY|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(32))
    token=path.read_text().strip()
    if len(token)<24:parser.error('El token debe tener al menos 24 caracteres')
    url=os.environ.get('SUPABASE_URL','');key=os.environ.get('SUPABASE_PUBLISHABLE_KEY','')
    if a.host not in ('127.0.0.1','localhost') and not(url and key):parser.error('Exponer la API requiere Supabase Auth y un proxy HTTPS configurados')
    service=Service(a.data_dir,token,url,key,os.environ.get('BOTATHON_SUPABASE_ACCESS_TOKEN',''))
    origins=set(filter(None,os.environ.get('BOTATHON_ALLOWED_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',')))
    server=ThreadingHTTPServer((a.host,a.port),handler(service,origins));print(json.dumps({'ready':True,'port':server.server_port}),flush=True);server.serve_forever()
if __name__=='__main__':main()
