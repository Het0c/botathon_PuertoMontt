import copy,io,json,tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
from fixtures import raw_from_flat,translated_flat,ROOT
from server.kit_teleton import load_kit,KitError,digest
from server.domain import calculate
from server.validation_report import compare_reference
from server.app import Service
from scripts.generar_reporte_agosto import generate
FIXTURE=ROOT/'ejemplo_salida_Planificacion_Input_BluePrism.xlsx'
SESSION={'actor':'qa-vm','remote_token':''}
class CalculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kit=load_kit(FIXTURE);cls.result=calculate(cls.kit)
    def test_verified_fisiatra_january_and_february(self):
        d=next(r for r in self.result['details'] if r['professional_id']=='137732' and r['institute_id']==11 and r['month']==1)
        self.assertEqual((d['weekly_direct'],d['weekly_indirect'],d['weekly_assignments']),(36,11,2))
        jan=next(r for r in self.result['document']['rows'] if r['professional_id']=='137732' and r['month']=='2026-01')
        feb=next(r for r in self.result['document']['rows'] if r['professional_id']=='137732' and r['month']=='2026-02')
        self.assertEqual(jan['planned_direct'],151);self.assertEqual(d['target_direct'],135)
        self.assertEqual(feb['planned_direct'],36)
    def test_reference_is_not_an_input(self):
        kit=copy.deepcopy(self.kit)
        for r in kit['tables']['Referencia_Por_Persona']:
            for k in list(r):
                if k.startswith(('Plan','MG_','SemHab','Pct_')):r[k]=-999
        self.assertEqual(calculate(kit)['document'],self.result['document'])
    def test_full_reference_audit_and_five_categories(self):
        report=compare_reference(self.kit,self.result)
        self.assertEqual(report['reference_cases'],471)
        self.assertEqual(report['matched']+report['different']+report['missing'],471)
        self.assertTrue(report['different']>0) # Do not disguise known missing business rules.
        refs=self.kit['tables']['Referencia_Por_Persona']
        selected=[r for r in refs if r['PersonaId']==137732 or 22<=float(r.get('Prom_Pond_HS') or 0)<40 or r.get('Cod_Esp') in ('ED','AS') or r['PersonaId']==125129]
        self.assertGreaterEqual(len(selected),5)
        self.assertEqual(next(r for r in report['cases'] if r['professional_id']=='137732' and r['institute_id']==11)['checks'][0]['actual'],151)
    def test_multi_institute_no_duplicate_original_hours(self):
        data=[d for d in self.result['details'] if d['professional_id']=='125129' and d['month']==1]
        self.assertEqual(sorted(d['weekly_hours'] for d in data),[8,27])
    def test_edit_meta_without_changing_plan(self):
        kit=copy.deepcopy(self.kit)
        next(r for r in kit['parameters']['Param_Generales'] if r['Parametro']=='META_GESTION')['Valor']=.85
        result=calculate(kit)
        self.assertEqual(sum(r['planned'] for r in result['document']['rows']),sum(r['planned'] for r in self.result['document']['rows']))
        self.assertLess(sum(r['target'] for r in result['document']['rows']),sum(r['target'] for r in self.result['document']['rows']))
    def test_pending_assignments_never_applied(self):
        k=copy.deepcopy(self.kit)
        k['tables']['Asignaciones_Especiales'].append({'PersonaId':137732,'IT':11,'Estado':'POR_AUTORIZAR','N_Asignacion':3,'Asignacion':'Pendiente','Horas_Semana':40})
        self.assertEqual(calculate(k)['document'],self.result['document'])
    def test_api_restart_failure_and_reprocess(self):
        import base64
        with tempfile.TemporaryDirectory() as tmp:
            service=Service(tmp,'a'*32)
            payload={'kit_base64':base64.b64encode(FIXTURE.read_bytes()).decode()}
            result=service.batch(payload,SESSION)
            self.assertEqual(service.batch(payload,SESSION)['status'],'reused')
            self.assertEqual(service.state['sequence'],1)
            before=copy.deepcopy(service.state['latest'])
            with self.assertRaises(KitError):service.batch({'document':{'bad':True}},SESSION)
            self.assertEqual(service.state['latest'],before)
            self.assertEqual(Service(tmp,'a'*32).state['latest'],before)
            with self.assertRaises(PermissionError):service.authorize('bad',True)
    def test_august_raw_generator_translator_adapter_calculation(self):
        import base64
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);raw=folder/'raw.xlsx';valid=folder/'agosto.xlsx';bad=folder/'agosto_errores.xlsx'
            raw_from_flat(FIXTURE,raw)
            excluded={r['PersonaId'] for r in self.kit['tables']['Excepciones_Horas']}
            manifest=generate(raw,valid,bad,excluded)
            self.assertEqual(len(manifest['new_ids']),2);self.assertEqual(len(manifest['invalid_ids']),3)
            flat=folder/'plano.xlsx';translated_flat(valid,FIXTURE,flat)
            newkit=load_kit(flat);result=calculate(newkit,previous=self.result)
            kinds=[c['kind'] for c in result['changes']]
            self.assertEqual(kinds.count('ALTA'),2);self.assertEqual(kinds.count('BAJA'),1)
            self.assertEqual(kinds.count('CAMBIO_HORAS'),2);self.assertEqual(kinds.count('CAMBIO_CARGO'),1)
            # Every old observed month is preserved even when the annual band changes.
            old={(r['professional_id'],r['institute'],r['role'],r['month']):r for r in self.result['document']['rows'] if r['month']<'2026-08'}
            for row in result['document']['rows']:
                identity=(row['professional_id'],row['institute'],row['role'],row['month'])
                if identity in old:self.assertEqual(row,old[identity])
            self.assertTrue(any(c['meta_delta']!=0 for c in result['changes']))
            badflat=folder/'plano_errores.xlsx';translated_flat(bad,FIXTURE,badflat)
            with self.assertRaises(KitError) as error:load_kit(badflat)
            self.assertTrue({'HOURS','UNKNOWN_ROLE','DATE_ORDER'}<={e['code'] for e in error.exception.errors})
if __name__=='__main__':unittest.main()
