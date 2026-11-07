"""Genera datos sintéticos y libros normalizados, nunca el kit oficial."""
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from server.domain import BUK_COLUMNS, SIC_COLUMNS, default_params

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'examples'
OUT.mkdir(exist_ok=True)
institutes = ['Santiago', 'Concepción', 'Puerto Montt', 'Aysén']
roles = list(default_params()['roles'])
areas = ['Rehabilitación', 'Rehabilitación', 'Apoyo clínico', 'Inclusión']
buk, sic = [], []
for idx in range(16):
    buk.append(dict(zip(BUK_COLUMNS, [f'C-{idx+1:03}', f'PRO-{idx+1:03}', institutes[idx//4],
        areas[idx%4], roles[idx%4], [44, 40, 30, 22][idx%4], '2026-01-01', None,
        '2026-01-01', 'Líder de equipo' if idx%4 == 0 else '', '', None, None])))
    for m in range(1, 10):
        sic.append({'professional_id': f'PRO-{idx+1:03}', 'institute': institutes[idx//4],
                    'month': f'2026-{m:02}', 'actual': 130 + ((idx*37+m*11) % 90)})
base = {'schema_version': 1, 'buk': buk, 'sic': sic}
change = copy.deepcopy(buk)
change[8]['hours_weekly'] = 30
change[8]['effective_from'] = '2026-07-01'
invalid = copy.deepcopy(change)
invalid[0]['hours_weekly'] = -5
invalid.append(copy.deepcopy(invalid[1]))


def sheet(wb, name, columns, rows):
    ws = wb.create_sheet(name)
    ws.append(columns)
    for row in rows:
        ws.append([row.get(k) for k in columns])
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.fill = PatternFill('solid', fgColor='12333A')
        cell.font = Font(color='FFFFFF', bold=True)
        cell.alignment = Alignment(wrap_text=True)
    ws.row_dimensions[1].height = 30
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(32, max(18, len(str(col[0].value))+2))
    return ws


def workbook(name, books):
    wb = Workbook(); wb.remove(wb.active)
    for title, columns, rows in books:
        sheet(wb, title, columns, rows)
    wb.save(OUT / name)


workbook('BUK_base_demo.xlsx', [('BUK', BUK_COLUMNS, buk)])
workbook('BUK_cambio_julio.xlsx', [('BUK', BUK_COLUMNS, change)])
workbook('BUK_invalido.xlsx', [('BUK', BUK_COLUMNS, invalid)])
workbook('SIC_demo.xlsx', [('SIC', SIC_COLUMNS, sic)])
workbook('Plantilla_Botathon_2026.xlsx', [
    ('LEEME', ['campo', 'instrucción'], [
        {'campo': 'Estado', 'instrucción': 'PLANTILLA NORMALIZADA PROVISIONAL. Datos ficticios, no kit oficial.'},
        {'campo': 'BUK', 'instrucción': 'Completar fila por contrato/vigencia; no usar nombres ni RUT reales.'},
        {'campo': 'SIC', 'instrucción': 'Mes AAAA-MM. Cero es atención observada; fila ausente significa sin SIC.'},
        {'campo': 'Publicación', 'instrucción': 'Seleccionar este libro en ambos campos BUK y SIC del panel.'},
        {'campo': 'Fechas', 'instrucción': 'Formato AAAA-MM-DD; effective_from rige cambios y conserva historia.'},
        {'campo': 'Asignaciones', 'instrucción': 'Separar por punto y coma; aprobación no acredita identidad.'},
        {'campo': 'Parámetros y calendario', 'instrucción': 'Hojas de referencia; configurar en la pestaña Parámetros. No se importan con BUK.'},
        {'campo': 'Bajas', 'instrucción': 'Informar end_date explícito. Ausencia de una fila no causa baja.'}]),
    ('BUK', BUK_COLUMNS, []), ('SIC', SIC_COLUMNS, []),
    ('Calendario_referencia', ['institute', 'month', 'holidays', 'vacation_days'],
     [{'institute': i, 'month': f'2026-{m:02}', 'holidays': 0, 'vacation_days': 0} for i in institutes for m in range(1,13)]),
    ('Reglas_referencia', ['role', 'band', 'direct', 'indirect', 'nas', 'minutes_direct', 'minutes_indirect'],
     [{'role': n, 'band': b, 'direct': v[0], 'indirect': v[1], 'nas': v[2],
       'minutes_direct': r['minutes_direct'], 'minutes_indirect': r['minutes_indirect']}
       for n,r in default_params()['roles'].items() for b,v in r['bands'].items()])])
(OUT / 'lote_base.json').write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'lote_cambio.json').write_text(json.dumps({'schema_version': 1, 'buk': change}, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'parametros_iniciales.json').write_text(json.dumps(default_params(), ensure_ascii=False, indent=2), encoding='utf-8')
print('Generadas 5 planillas y 3 contratos JSON en examples/')
