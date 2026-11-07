import copy
import pytest
from server.domain import default_params, normalize_buk, calculate, validate_params, Invalid


def contract(**overrides):
    return {'contract_id':'C1','professional_id':'P1','institute':'Santiago',
            'area':'Área','role':'Kinesiología','hours_weekly':20,
            'start_date':'2026-01-01','end_date':'2026-01-31',**overrides}


@pytest.mark.parametrize('hours,ratio',[(21.99,.75),(22,.70),(39.99,.70),(40,.65)])
def test_band_boundaries(hours,ratio):
    p=default_params()
    rows,_=calculate(normalize_buk([contract(hours_weekly=hours)],p),[],p)
    assert len(rows)==1
    assert rows[0]['direct']/rows[0]['contracted']==pytest.approx(ratio,abs=1e-7)


def test_partial_month_and_full_license():
    p=default_params()
    rows,_=calculate(normalize_buk([contract(start_date='2026-01-15')],p),[],p)
    assert rows[0]['contracted']==48
    rows,_=calculate(normalize_buk([contract(leave_start='2026-01-01',leave_end='2026-01-31')],p),[],p)
    assert rows[0]['contracted']==88 and rows[0]['absence']==88
    assert rows[0]['planned']==rows[0]['direct']==rows[0]['nas']==0


def test_calendar_accounting_identity():
    p=default_params()
    p['calendar']=[{'institute':'Santiago','month':'2026-01','holidays':2,'vacation_days':1}]
    rows,_=calculate(normalize_buk([contract()],p),[],validate_params(p))
    r=rows[0]
    assert r['absence']==12
    assert r['contracted']==pytest.approx(r['direct']+r['indirect']+r['nas']+r['absence'],abs=1e-6)


def test_group_floor_and_target():
    p=default_params()
    rows,_=calculate(normalize_buk([contract(role='Educación')],p),[],p)
    r=rows[0]
    assert r['direct']==66 and r['indirect']==22
    assert r['planned_direct']==104  # floor(52.8) + floor(13.2) × 4
    assert r['planned_indirect']==44
    assert r['target']==133.2


def test_multi_institute_band_uses_professional_total():
    p=default_params()
    rows,_=calculate(normalize_buk([contract(),contract(contract_id='C2',institute='Concepción',hours_weekly=22)],p),[],p)
    assert len(rows)==2
    assert next(r for r in rows if r['institute']=='Santiago')['direct']==57.2


def test_sic_ambiguous_cargo_not_duplicated():
    p=default_params()
    rows,comparisons=calculate(normalize_buk([contract(hours_weekly=10),contract(contract_id='C2',role='Educación',hours_weekly=10)],p),
        [{'professional_id':'P1','institute':'Santiago','month':'2026-01','actual':23}],p)
    assert len(rows)==2 and all(r['actual'] is None for r in rows)
    assert len(comparisons)==1 and comparisons[0]['actual']==23 and comparisons[0]['ambiguous']


def test_approval_and_invalid_assignment():
    p=default_params()
    with pytest.raises(Invalid,match='autorización'):
        normalize_buk([contract(assignments='Comité nacional')],p)
    with pytest.raises(Invalid,match='entero'):
        q=copy.deepcopy(p);q['roles']['Educación']['patients_group']=3.2;validate_params(q)
