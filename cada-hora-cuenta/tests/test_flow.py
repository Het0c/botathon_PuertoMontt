import copy
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from server.app import create_app
from server.domain import Invalid, default_params, calculate, normalize_buk, validate_params

ROOT = Path(__file__).resolve().parent.parent
HEADERS = {'Authorization': 'Bearer test-local-token'}


@pytest.fixture
def payload():
    return json.loads((ROOT/'examples/lote_base.json').read_text(encoding='utf-8'))


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path/'test.sqlite3', 'test-local-token', 'viewer-local-token')


def publish(app, data):
    return app.test_client().post('/api/batches', json=data, headers=HEADERS)


def test_buk_valid_and_restart(app, payload):
    r = publish(app, payload)
    assert r.status_code == 200
    assert r.json['version'] == 1
    assert len(app.store.snapshot()['rows']) == 16*12
    restarted = create_app(app.store.path, 'test-local-token')
    assert restarted.store.snapshot() == app.store.snapshot()


def test_invalid_keeps_last_valid(app, payload):
    publish(app,payload)
    before = app.store.snapshot()
    bad = copy.deepcopy(payload); bad['buk'][0]['hours_weekly'] = -1
    r = publish(app,bad)
    assert r.status_code == 422
    assert 'fila 2' in r.json['errors'][0]
    assert app.store.snapshot() == before
    assert app.store.history()['runs'][0]['status'] == 'rejected'


def test_replay_is_idempotent(app, payload):
    a,b = publish(app,payload).json, publish(app,payload).json
    assert a['version'] == b['version'] == 1
    assert b['status'] == 'reused'
    assert len(app.store.history()['runs']) == 1


def test_effective_change_preserves_january_to_june(app,payload):
    publish(app,payload)
    old = app.store.snapshot()
    change = json.loads((ROOT/'examples/lote_cambio.json').read_text(encoding='utf-8'))
    assert publish(app,change).status_code == 200
    new = app.store.snapshot()
    a = [r for r in old['rows'] if r['professional_id']=='PRO-009']
    b = [r for r in new['rows'] if r['professional_id']=='PRO-009']
    # This demo's annual average changes its band, so a rule is needed to freeze historical
    # months; publication must retain every pre-effective result, including band-derived values.
    for oldrow,newrow in zip(a,b):
        if oldrow['month'] < '2026-07':
            assert oldrow == newrow
        else:
            assert newrow['contracted'] < oldrow['contracted']


def test_legal_boundary_and_zero_hours():
    p=default_params(); c={
        'contract_id':'C1','professional_id':'P1','institute':'Santiago','area':'Clínica',
        'role':'Kinesiología','hours_weekly':44,'start_date':'2026-01-01'}
    rows,_=calculate(normalize_buk([c],p),[],p)
    apr=next(r for r in rows if r['month']=='2026-04')
    may=next(r for r in rows if r['month']=='2026-05')
    assert apr['contracted']==193.6  # 22 weekdays × 44/5
    assert may['contracted']==176.4  # 21 weekdays × 42/5
    c['hours_weekly']=0
    rows,_=calculate(normalize_buk([c],p),[],p)
    assert all(r['planned']==0 and r['foja'] is None for r in rows)


def test_parameters_validation_and_recalculation(app,payload):
    publish(app,payload)
    original=app.store.snapshot()
    p=app.store.params()['params']; p['roles']['Kinesiología']['bands']['40+']=[.9,.9,.1]
    assert app.test_client().put('/api/parameters',json={'params':p},headers=HEADERS).status_code==422
    assert app.store.snapshot()==original
    p=app.store.params()['params']; p['management_pct']=.8
    assert app.test_client().put('/api/parameters',json={'params':p},headers=HEADERS).status_code==200
    assert app.store.snapshot()==original
    r=app.test_client().post('/api/recalculate',headers=HEADERS)
    assert r.status_code==200
    assert app.store.snapshot()['version']==2
    assert sum(r['target'] for r in app.store.snapshot()['rows']) < sum(r['target'] for r in original['rows'])


def test_sic_absent_is_distinct_from_zero(app,payload):
    payload['sic']=[{'professional_id':'PRO-001','institute':'Santiago','month':'2026-01','actual':0}]
    publish(app,payload)
    rows=app.store.snapshot()['rows']
    assert next(r for r in rows if r['professional_id']=='PRO-001' and r['month']=='2026-01')['actual']==0
    assert next(r for r in rows if r['month']=='2026-02')['actual'] is None


def test_excel_errors_and_duplicate(app,payload):
    publish(app,payload)
    response=app.test_client().post('/api/import',data={
        'buk':(io.BytesIO((ROOT/'examples/BUK_invalido.xlsx').read_bytes()),'invalido.xlsx'),
        'reuse_sic':'true'},headers=HEADERS)
    assert response.status_code==422
    assert any('duplicados' in e for e in response.json['errors'])
    assert app.store.snapshot()['version']==1


def test_concurrent_identical_publications(app,payload):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:app.store.publish(payload['buk'],payload['sic']), range(2)))
    assert {r['status'] for r in results}=={'published','reused'}
    assert len(app.store.history()['runs'])==1


def test_access_and_cors(app,payload):
    client=app.test_client()
    assert client.get('/api/plan').status_code==401
    viewer={'Authorization':'Bearer viewer-local-token'}
    assert client.get('/api/plan',headers=viewer).status_code==200
    assert client.post('/api/batches',json=payload,headers=viewer).status_code==403
    assert client.get('/api/plan',headers={**HEADERS,'Origin':'https://evil.example'}).status_code==403
    native=client.get('/api/plan',headers={**HEADERS,'Origin':'http://tauri.localhost'})
    assert native.status_code==200 and native.headers['Access-Control-Allow-Origin']=='http://tauri.localhost'


def test_snapshot_rollback_on_calculation_failure(app,payload):
    publish(app,payload)
    before=app.store.snapshot()
    bad=copy.deepcopy(payload)
    bad['sic'].append({'professional_id':'UNKNOWN','institute':'Aysén','month':'2026-01','actual':1})
    assert publish(app,bad).status_code==422
    assert app.store.snapshot()==before


def test_omitted_row_is_not_termination(app,payload):
    publish(app,payload)
    payload['buk']=payload['buk'][:1]
    result=publish(app,payload)
    assert result.json['status']=='reused'
    assert len(app.store.snapshot()['rows'])==192


def test_explicit_termination(app,payload):
    payload['sic']=[]
    publish(app,payload)
    payload['buk']=[payload['buk'][0]]
    payload['buk'][0]['end_date']='2026-06-30'
    result=publish(app,payload)
    assert result.status_code==200
    assert result.json['summary']['ended']==1
    rows=[r for r in app.store.snapshot()['rows'] if r['professional_id']=='PRO-001']
    assert len(rows)==6 and all(r['month']<='2026-06' for r in rows)


def test_stale_parameter_fingerprint(app,payload):
    publish(app,payload)
    payload['params_hash']='stale'
    assert publish(app,payload).status_code==422
    assert app.store.snapshot()['version']==1


def test_current_parameter_fingerprint_is_accepted(app,payload):
    payload['params_hash']=app.test_client().get('/api/parameters',headers=HEADERS).json['hash']
    assert publish(app,payload).status_code==200
