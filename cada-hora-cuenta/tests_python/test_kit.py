import io,sys,unittest
from pathlib import Path
from openpyxl import load_workbook
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.kit_teleton import load_kit,KitError
ROOT=Path(__file__).resolve().parents[2]
FIXTURE=ROOT/'ejemplo_salida_Planificacion_Input_BluePrism.xlsx'
class KitTests(unittest.TestCase):
    def test_real_output(self):
        k=load_kit(FIXTURE)
        self.assertEqual(k['counts']['Dotacion_Mes'],3123);self.assertEqual(k['professionals'],462)
        self.assertEqual(len(k['tables']['Referencia_Por_Persona']),471)
        self.assertEqual(len(k['parameters']['Param_Semanas_Habiles']),12)
        self.assertEqual(len(k['warnings']),2)
        self.assertNotIn('Fecha_Nacimiento',k['tables']['Dotacion_Mes'][0])
        self.assertTrue(all('Observaciones' not in r for r in k['tables']['Dias_Adicionales']))
    def altered(self,change):
        w=load_workbook(FIXTURE);change(w);b=io.BytesIO();w.save(b);w.close();return b.getvalue()
    def test_duplicate(self):
        def change(w):w['Dotacion_Mes'].append([c.value for c in w['Dotacion_Mes'][2]])
        with self.assertRaises(KitError) as error:load_kit(self.altered(change))
        self.assertIn('DUPLICATE',{r['code'] for r in error.exception.errors})
    def test_hours(self):
        with self.assertRaises(KitError) as error:load_kit(self.altered(lambda w:setattr(w['Dotacion_Mes']['R2'],'value',-1)))
        self.assertEqual(error.exception.errors[0]['sheet'],'Dotacion_Mes')
        self.assertEqual(error.exception.errors[0]['row'],2)
if __name__=='__main__':unittest.main()
