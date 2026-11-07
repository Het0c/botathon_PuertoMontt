import base64,copy,http.client,json,subprocess,sys,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.app import Service,handler
APP=Path(__file__).resolve().parents[1];ROOT=APP.parent
class ApiTests(unittest.TestCase):
    def test_authenticated_http_and_blueprism_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=Service(tmp,'a'*32);server=ThreadingHTTPServer(('127.0.0.1',0),handler(service,{'http://localhost:5173'}))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def call(path,body=None,method=None,token='a'*32):
                client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=60)
                client.request(method or ('POST' if body is not None else 'GET'),path,body=None if body is None else json.dumps(body),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                response=client.getresponse();data=json.loads(response.read());status=response.status;client.close();return status,data
            try:
                self.assertEqual(call('/api/health',token='wrong')[0],403)
                payload={'kit_base64':base64.b64encode((ROOT/'ejemplo_salida_Planificacion_Input_BluePrism.xlsx').read_bytes()).decode()}
                status,first=call('/api/batches',payload);self.assertEqual(status,200);self.assertFalse(first['published'])
                _,params=call('/api/parameters');invalid=copy.deepcopy(params['params'])
                next(r for r in invalid['Param_Generales'] if r['Parametro']=='META_GESTION')['Valor']=2
                self.assertEqual(call('/api/parameters',{'params':invalid},'PUT')[0],422)
                self.assertEqual(call('/api/parameters')[1]['hash'],params['hash'])
                updated=copy.deepcopy(params['params']);next(r for r in updated['Param_Generales'] if r['Parametro']=='META_GESTION')['Valor']=.85
                self.assertEqual(call('/api/parameters',{'params':updated},'PUT')[0],200)
                status,recalc=call('/api/recalculate',{});self.assertEqual(status,200)
                self.assertLess(sum(r['target'] for r in recalc['document']['rows']),sum(r['target'] for r in first['document']['rows']))
                token_file=Path(tmp)/'token';token_file.write_text('a'*32)
                report=Path(tmp)/'estado.json'
                child=subprocess.run([sys.executable,str(APP/'scripts/blueprism_ingest.py'),'--kit',str(ROOT/'ejemplo_salida_Planificacion_Input_BluePrism.xlsx'),'--api-url',f'http://127.0.0.1:{server.server_port}','--token-file',str(token_file),'--status',str(report)],capture_output=True,text=True,timeout=60)
                self.assertEqual(child.returncode,0,child.stderr);state=json.loads(report.read_text(encoding='utf-8'));self.assertEqual(state['status'],'reused')
                self.assertNotIn('a'*32,child.stdout)
            finally:server.shutdown();server.server_close();thread.join(timeout=5)
if __name__=='__main__':unittest.main()
