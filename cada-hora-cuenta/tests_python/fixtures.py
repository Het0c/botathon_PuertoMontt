"""QA: reconstrucción mínima del BUK desde el plano, NO sustituye los crudos originales."""
import sys,importlib.util
from pathlib import Path
from openpyxl import Workbook,load_workbook
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('original_translator',ROOT/'bot_traductor.py');translator=importlib.util.module_from_spec(spec);spec.loader.exec_module(translator)
HEADERS=['IT','Instituto','PersonaId','Área','Nombre Sub-área','Centro de Costo','Fecha de Nacimiento','Periodo','Tipo de Contrato','Tipo_Trab_161225','Fecha Ingreso Compañía','Fecha Término','Horas Semanales','Cargo','Tipo_Trabajador','Días de la Jornada','Reg_SIC','Cod_Esp','Ndias']
MAPPING={'IT':'IT','Instituto':'Instituto','PersonaId':'PersonaId','Nombre Sub-área':'Sub_Area','Centro de Costo':'Centro_Costo','Periodo':'Periodo','Tipo de Contrato':'Tipo_Contrato','Fecha Ingreso Compañía':'Fecha_Ingreso','Fecha Término':'Fecha_Termino','Horas Semanales':'Horas_Semanales','Cargo':'Cargo','Tipo_Trabajador':'Tipo_Trabajador','Días de la Jornada':'Dias_Jornada','Cod_Esp':'Cod_Esp','Ndias':'N_Dias_Semana'}

def raw_from_flat(flat_path,target):
    w=load_workbook(flat_path,read_only=True,data_only=True);it=w['Dotacion_Mes'].iter_rows(values_only=True);header=next(it)
    out=Workbook();ws=out.active;ws.title='Dotacion_2026';ws.append(['Reconstrucción mínima para QA; no es el archivo crudo original']);ws.append(HEADERS)
    for line in it:
        row=dict(zip(header,line));ws.append([row.get(MAPPING.get(k,'')) for k in HEADERS])
    w.close();out.save(target);out.close()

def translated_flat(raw,base,target):
    w=load_workbook(base);it=w['Param_Generales'].iter_rows(values_only=True);next(it);generals={r[0]:r[1] for r in it}
    contracts=translator.leer_contratos(raw)
    for name,pair in [('Dotacion_Mes',translator.tabla_dotacion(contracts,generals)),('Personas',translator.tabla_personas(contracts)),('Cambios_Mes',translator.tabla_cambios(contracts,generals))]:
        index=w.sheetnames.index(name);del w[name];ws=w.create_sheet(name,index);head,rows=pair;ws.append(head)
        for row in rows:ws.append(row)
    w.save(target);w.close()
