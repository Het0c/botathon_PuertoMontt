"""Smoke test del ejecutable empaquetado, incluyendo su modo --ingest."""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

root=Path(__file__).resolve().parent.parent
binary=Path(sys.argv[1]).resolve()
(root/'work').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=root/'work',prefix='sidecar-check-') as temp:
    process=subprocess.Popen([str(binary),'--port','0','--data-dir',temp],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
        env={**os.environ,'BOTATHON_TOKEN':'test-packaged-local-token'})
    try:
        ready=json.loads(process.stdout.readline())
        assert ready['ready']
        connection=str(Path(temp)/'connection.json')
        for name,args,code in [
            ('base',['--manifest',str(root/'examples/lote_base.json')],0),
            ('change',['--buk',str(root/'examples/BUK_cambio_julio.xlsx'),'--reuse-sic'],0),
            ('invalid',['--buk',str(root/'examples/BUK_invalido.xlsx'),'--reuse-sic'],2),
        ]:
            status=str(Path(temp)/(name+'.json'))
            result=subprocess.run([str(binary),'--ingest','--connection',connection,'--status',status,*args],
                                  capture_output=True,text=True,timeout=60)
            assert result.returncode==code, (name,result.returncode,result.stdout,result.stderr)
            data=json.loads(Path(status).read_text(encoding='utf-8'))
            assert data['status']==('rejected' if code else 'published'),data
        req=urllib.request.Request(f'http://127.0.0.1:{ready["port"]}/api/plan',
                                   headers={'Authorization':'Bearer test-packaged-local-token'})
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req,timeout=5) as response:
            assert json.load(response)['version']==2
        print(json.dumps({'sidecar':'ok','packaged_ingest':'ok','last_valid_version':2,'rejected_preserves_plan':True}))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill();process.wait()
