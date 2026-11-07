"""Reglas trazables sobre el kit. Las hojas Referencia_* NO alimentan el cálculo."""
import calendar,collections,copy,datetime as dt,math
from decimal import Decimal,ROUND_FLOOR,ROUND_HALF_UP
from .kit_teleton import canonical,digest,validate_parameters,KitError,issue,finite
from .contract import validate_document
MONTHS=['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']

def num(value,default=0):
    if value is None:return default
    if not finite(value):raise KitError('Valor numérico inválido en entradas humanas')
    return float(value)

def rounded(value,policy):
    return int(Decimal(str(round(max(0,value),9))).to_integral_value(rounding=ROUND_FLOOR if policy=='FLOOR' else ROUND_HALF_UP))

def key(r):return (str(r['PersonaId']),int(r['IT']),int(r['Mes']))

def active_fraction(row,month):
    days=calendar.monthrange(2026,month)[1];start=dt.date(2026,month,1);end=dt.date(2026,month,days)
    ingress=dt.date.fromisoformat(row['Fecha_Ingreso']) if row.get('Fecha_Ingreso') else start
    term=dt.date.fromisoformat(row['Fecha_Termino']) if row.get('Fecha_Termino') else end
    first,last=max(start,ingress),min(end,term)
    if first>last:return 0
    schedule=str(row.get('Dias_Jornada') or 'lmwjv').lower();codes='lmwjvsd'
    weekdays={i for i,c in enumerate(codes) if c in schedule} or set(range(5))
    all_days=[dt.date(2026,month,d) for d in range(1,days+1)]
    total=sum(d.weekday() in weekdays for d in all_days)
    return sum(d.weekday() in weekdays and first<=d<=last for d in all_days)/total if total else 0

def expand_months(kit):
    tables=kit['tables'];pol=kit['parameters']['politicas'];observed={key(r):copy.deepcopy(r) for r in tables['Dotacion_Mes']}
    latest=max(r['Mes'] for r in observed.values());expanded=copy.deepcopy(observed)
    by_link=collections.defaultdict(list)
    for r in observed.values():by_link[(str(r['PersonaId']),int(r['IT']))].append(r)
    if pol['PROYECTAR_ULTIMO_MES']:
        for history in by_link.values():
            last=max(history,key=lambda r:r['Mes'])
            if last['Mes']!=latest:continue
            for month in range(latest+1,13):
                r={**last,'Mes':month,'Periodo':f'2026-{month:02}-01','_projected':True}
                expanded[key(r)]=r
    # Explicit monthly allocation replaces rather than adds to the original link.
    for ex in tables['Excepciones_Horas']:
        pid=str(ex['PersonaId']);it=int(ex['IT']);donors=[r for r in observed.values() if str(r['PersonaId'])==pid]
        if not donors:continue
        for month,suffix in enumerate(MONTHS,1):
            h=ex.get('HS_'+suffix)
            old=expanded.pop((pid,it,month),None)
            if not finite(h) or h<=0:continue
            eligible=[r for r in donors if r['Mes']<=month]
            donor=old or max(eligible or donors,key=lambda r:r['Mes'])
            expanded[(pid,it,month)]={**donor,'PersonaId':ex['PersonaId'],'IT':it,'Mes':month,'Instituto':ex.get('Sigla') or ex.get('Instituto'),
                'Horas_Semanales':h,'N_Dias_Semana':ex.get('Dias_Semana') or donor['N_Dias_Semana'],'_exception_hours':True,'_projected':month>latest}
    return expanded,observed,latest

def extra_days(record,month,g,policy):
    if not record:return 0
    total=0
    if month==1:total+=num(record.get('Feriado_Zona_Extrema_Ene'))
    if month==2:total+=num(record.get('Feriado_Zona_Extrema_Feb'))
    if month==int(record.get('Mes_Cumpleanos') or 0):total+=num(record.get('Dias_Cumpleanos'))
    if month==9:total+=num(record.get('Dias_Vispera_FFPP'))
    if month==12:total+=num(record.get('Dias_Visperas_Navidad'))
    spread=12 if policy=='todo_anio' else int(g['MESES_2DO_SEMESTRE'])
    if month>=13-spread:
        annual=sum(num(record.get(k)) for k in ['Feriado_Legal_Adicional','Dias_Administrativos','Dias_Capacitacion','Dias_HEXA_CTR','Dias_Jornada_Nacional','Dias_Directiva_Sindical','Dias_Lactancia'])
        for field,factor in [('Dias_Progresivos','FACTOR_DIAS_PROGRESIVOS'),('Dias_Complementarios','FACTOR_DIAS_COMPLEMENTARIOS'),('Dias_Ley_21530','FACTOR_LEY_21530'),('Dias_Vac_Pendientes','FACTOR_VAC_PENDIENTES')]:annual+=num(record.get(field))*num(g.get(factor),1)
        total+=annual/spread
    return total

def report_changes(observed,previous):
    old={tuple(r['key']):r['value'] for r in (previous or {}).get('input_months',[])}
    # JSON roundtrip normalizes the numeric IT/month key types.
    old={(str(k[0]),int(k[1]),int(k[2])):v for k,v in old.items()}
    old_links=collections.defaultdict(list)
    for k,v in old.items():old_links[k[:2]].append((k[2],v))
    changes=[]
    if not old:return changes
    newest=max(k[2] for k in observed);old_max=max(k[2] for k in old)
    for k,r in observed.items():
        before=old.get(k)
        if before is None:
            earlier=[(m,v) for m,v in old_links[k[:2]] if m<k[2]]
            before=max(earlier,key=lambda x:x[0])[1] if earlier else None
        types=[]
        if before is None:types=['ALTA']
        else:
            if num(before.get('hours'))!=num(r['Horas_Semanales']):types.append('CAMBIO_HORAS')
            if before.get('role')!=r['Cargo']:types.append('CAMBIO_CARGO')
            if before.get('end_date')!=r.get('Fecha_Termino'):types.append('FECHA_TERMINO')
        for kind in types:
            effective=f'2026-{k[2]:02}-01'
            if kind=='FECHA_TERMINO' and r.get('Fecha_Termino'):effective=(dt.date.fromisoformat(r['Fecha_Termino'])+dt.timedelta(days=1)).isoformat()
            changes.append({'professional_id':k[0],'institute_id':k[1],'month':k[2],'kind':kind,'effective_from':effective,
                'before':before,'after':{'hours':r['Horas_Semanales'],'role':r['Cargo'],'end_date':r.get('Fecha_Termino')}})
    if newest>old_max:
        previous_links={k[:2] for k in old if k[2]==old_max}
        current_links={k[:2] for k in observed if k[2]==newest}
        for pid,it in sorted(previous_links-current_links):changes.append({'professional_id':pid,'institute_id':it,'month':newest,'kind':'BAJA','effective_from':f'2026-{newest:02}-01','before':dict(max(old_links[(pid,it)],key=lambda x:x[0])[1]),'after':None})
    return changes

def calculate(kit,previous=None):
    p=validate_parameters(kit['parameters']);kit={**kit,'parameters':p};g={r['Parametro']:r['Valor'] for r in p['Param_Generales']};pol=p['politicas']
    matrix={(canonical(r['Cargo']),r['Tramo_Horas']):r for r in p['Param_Distribucion_Cargo']}
    calendar_map={int(r['Mes']):r for r in p['Param_Semanas_Habiles']}
    regional={(int(r['IT']),int(r['Mes'])):r for r in p.get('Param_Semanas_Instituto',[])}
    names={int(r['IT']):str(r['Nombre']) for r in p['Param_Institutos']}
    specialties={str(r['Cod_Esp']):str(r['Especialidad']) for r in p.get('Param_Especialidades',[])}
    group={str(r['Cod_Esp']):r for r in p.get('Param_Factor_Grupal',[])}
    catalog={canonical(r['Asignacion']):r for r in p.get('Param_Asignaciones',[])}
    absences={(str(r['PersonaId']),int(r['IT']),int(r['Mes'])):r for r in kit['tables']['Ausencias_Mes']}
    days={(str(r['PersonaId']),int(r['IT'])):r for r in kit['tables']['Dias_Adicionales']}
    assignments=collections.defaultdict(list)
    for r in kit['tables']['Asignaciones_Especiales']:assignments[(str(r['PersonaId']),int(r['IT']))].append(r)
    expanded,observed,last=expand_months(kit)
    weights=collections.defaultdict(lambda:[0,0])
    for (pid,it,m),r in expanded.items():
        cap=pol['TOPE_ANTES_MAYO'] if m<pol['MES_CAMBIO_LEGAL'] else pol['TOPE_DESDE_MAYO']
        h=min(num(r['Horas_Semanales']),cap);weight=calendar.monthrange(2026,m)[1]*active_fraction(r,m)
        weights[(pid,it)][0]+=h*weight;weights[(pid,it)][1]+=weight
    warnings=list(kit['warnings']);warning_keys=set();detail=[];rows=[]
    def warn(pid,it,m,code,message):
        k=(pid,it,code)
        if k not in warning_keys:warnings.append(issue('Calculo',None,'',code,message,'warning',professional_id=pid,institute_id=it,month=m));warning_keys.add(k)
    for (pid,it,m),r in sorted(expanded.items()):
        frac=active_fraction(r,m)
        if frac==0:continue
        avg=weights[(pid,it)][0]/weights[(pid,it)][1] if weights[(pid,it)][1] else 0
        band='T1_>=40' if avg>=g['UMBRAL_TRAMO_1'] else 'T2_22-39' if avg>=g['UMBRAL_TRAMO_2'] else 'T3_<22'
        rule=matrix.get((canonical(r['Cargo']),band))
        if not rule:raise KitError(f'Cargo sin matriz: PersonaId {pid}, IT {it}, mes {m}, tramo {band}')
        a,b,nas_pct=[num(rule.get(k)) for k in ['Pct_Directo','Pct_Indirecto','Pct_NAS']]
        if a+b<=0:raise KitError(f'Matriz no configurada para atención: PersonaId {pid}, IT {it}, mes {m}')
        cap=pol['TOPE_ANTES_MAYO'] if m<pol['MES_CAMBIO_LEGAL'] else pol['TOPE_DESDE_MAYO'];h=min(num(r['Horas_Semanales']),cap)
        applied=[];special=0
        for entry in assignments[(pid,it)]:
            if entry['Estado']!='VIGENTE':warn(pid,it,m,'ASIGNACION_PENDIENTE','Asignación por autorizar no aplicada');continue
            union=entry.get('N_Asignacion')==4
            if not union and h<=g['MIN_HS_PARA_ASIGNACION']:
                warn(pid,it,m,'ASIGNACION_JORNADA','Asignación especial no aplicada por jornada <= mínimo');continue
            if not union:
                special+=1
                if special>g['MAX_ASIGNACIONES_ESPECIALES']:raise KitError(f'Máximo de asignaciones excedido para PersonaId {pid}, IT {it}')
            known=catalog.get(canonical(entry.get('Asignacion')), {})
            hours=entry.get('Horas_Semana') if entry.get('Horas_Semana') is not None else known.get('Horas_Semana')
            if hours is None:warn(pid,it,m,'ASIGNACION_SIN_HORAS','Asignación sin horas autorizadas: pendiente de revisión');continue
            applied.append(num(hours))
        assigned=sum(applied);nas_week=h*nas_pct+assigned
        if nas_week>h+1e-9:raise KitError(f'NAS y asignaciones superan la jornada: PersonaId {pid}, IT {it}, mes {m}')
        direct_week=max(0,h-nas_week)*a/(a+b);indirect_week=max(0,h-nas_week)-direct_week
        min_direct=num(rule.get('Min_Estandar_Directa'));min_indirect=num(rule.get('Min_Estandar_Indirecta'),g['MIN_ESTANDAR_INDIRECTA'])
        if min_direct<=0 or min_indirect<=0:raise KitError('Minutos no configurados en matriz activa')
        weekly_direct=rounded(direct_week*60/min_direct,'FLOOR');weekly_indirect=rounded(indirect_week*60/min_indirect,'FLOOR')
        gr=group.get(str(r.get('Cod_Esp')),{});gp=num(gr.get('Pct_Atencion_Grupal'));patients=num(gr.get('N_Pacientes_Grupo_San_Con' if it in pol['INSTITUTOS_GRUPO_MAYOR'] else 'N_Pacientes_Grupo_Otros_IT'),1)
        weekly_group=rounded(weekly_direct*((1-gp)+gp*patients),pol['REDONDEO_GRUPAL'])
        baseweeks=num(regional.get((it,m),calendar_map[m]).get('Semanas_Habiles'));grossweeks=baseweeks*frac
        absence=num(absences.get((pid,it,m),{}).get('Total_Semanas_Ausente'))
        benefit_days=extra_days(days.get((pid,it)),m,g,pol['REPARTO_DIAS_EXTRA'])
        effective=max(0,grossweeks-absence-benefit_days/5*frac)
        license=days.get((pid,it),{}).get('Licencia_Extensa')
        if license not in (None,'',0,'NO','No',False):effective=0;warn(pid,it,m,'LICENCIA_EXTENSA','Licencia extensa: mes sin atención')
        direct=direct_week*effective;indirect=indirect_week*effective;nas=nas_week*effective;contracted=h*grossweeks
        plan_direct=rounded(weekly_group*effective,pol['REDONDEO_MENSUAL']);plan_indirect=rounded(weekly_indirect*effective,pol['REDONDEO_MENSUAL'])
        target_direct=rounded(plan_direct*g['META_GESTION'],pol['REDONDEO_META']);target_indirect=rounded(plan_indirect*g['META_GESTION'],pol['REDONDEO_META'])
        row={'professional_id':pid,'institute':names.get(it,str(r['Instituto'])),'area':specialties.get(str(r.get('Cod_Esp')),str(r.get('Sub_Area') or 'Sin área')),'role':str(r['Cargo']),'month':f'2026-{m:02}',
            'contracted':round(contracted,6),'direct':round(direct,6),'indirect':round(indirect,6),'nas':round(nas,6),'absence':round(max(0,contracted-direct-indirect-nas),6),
            'planned_direct':plan_direct,'planned_indirect':plan_indirect,'planned':plan_direct+plan_indirect,'target':target_direct+target_indirect,'actual':None,'foja':direct/contracted if contracted else None}
        rows.append(row)
        detail.append({'professional_id':pid,'institute_id':it,'month':m,'band':band,'weekly_hours':h,'average_weekly_hours':round(avg,6),
            'weekly_pause':h*num(g['PCT_PAUSA_SALUDABLE_40H'] if h>=g['UMBRAL_TRAMO_1'] else g['PCT_PAUSA_SALUDABLE_MENOS_40H']),
            'weekly_lunch':0 if pol['COLACION_EN_CONTRATO'] else num(g['HORAS_COLACION_15MIN_POR_DIA'])*num(r['N_Dias_Semana']),
            'weekly_nas':nas_week,'weekly_assignments':assigned,'weekly_direct':weekly_direct,'weekly_indirect':weekly_indirect,'weekly_group':weekly_group,
            'effective_weeks':round(effective,6),'target_direct':target_direct,'target_indirect':target_indirect,'projected':bool(r.get('_projected')),'exception_hours':bool(r.get('_exception_hours'))})
    changes=report_changes(observed,previous)
    # Preserve complete months before changed input when the parameter set is unchanged.
    if previous and previous.get('document',{}).get('parameters_version')==digest(p):
        cutoffs={}
        for c in changes:
            cutoff=c['effective_from'][:7];pid=c['professional_id'];cutoffs[pid]=min(cutoffs.get(pid,cutoff),cutoff)
        old_rows=previous.get('document',{}).get('rows',[])
        old_lookup={(r['professional_id'],r['institute'],r['area'],r['role'],r['month']):r for r in old_rows}
        old_details={(d['professional_id'],d['institute_id'],d['month']):d for d in previous.get('details',[])}
        for i,row in enumerate(rows):
            if row['professional_id'] in cutoffs and row['month']<cutoffs[row['professional_id']]:
                identity=tuple(row[k] for k in ['professional_id','institute','area','role','month'])
                if identity in old_lookup:
                    rows[i]=copy.deepcopy(old_lookup[identity])
                    prior=old_details.get((row['professional_id'],detail[i]['institute_id'],int(row['month'][-2:])))
                    if prior:detail[i]=copy.deepcopy(prior)
    old_targets=collections.defaultdict(float);new_targets=collections.defaultdict(float)
    for r in (previous or {}).get('document',{}).get('rows',[]):old_targets[(r['professional_id'],r['institute'],int(r['month'][-2:]))]+=r['target']
    for r in rows:new_targets[(r['professional_id'],r['institute'],int(r['month'][-2:]))]+=r['target']
    for c in changes:
        identity=(c['professional_id'],names.get(c['institute_id'],str(c['institute_id'])),c['month']);c['meta_before']=old_targets[identity];c['meta_after']=new_targets[identity];c['meta_delta']=c['meta_after']-c['meta_before']
    document=validate_document({'schema_version':1,'year':2026,'parameters_version':digest(p),'rows':rows})
    input_months=[{'key':list(k),'value':{'hours':r['Horas_Semanales'],'role':r['Cargo'],'end_date':r.get('Fecha_Termino')}} for k,r in observed.items()]
    return {'status':'calculated','document':document,'details':detail,'changes':changes,'report_changes':kit['tables']['Cambios_Mes'],'warnings':warnings,
        'counts':kit['counts'],'professionals':kit['professionals'],'input_months':input_months,'last_observed_month':last,'projected_months':list(range(last+1,13)),'parameters_hash':digest(p)}
