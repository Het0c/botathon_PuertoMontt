import { useEffect, useMemo, useState } from 'react';
import { Activity, ArrowDownToLine, ArrowRight, CalendarDays, Check, CheckCircle2, ChevronRight,
  Clock3, Database, FileCheck2, FileSpreadsheet, FolderClock, GitBranch, LayoutDashboard,
  LoaderCircle, RefreshCw, Search, Settings2, ShieldCheck, Upload, Users, X } from 'lucide-react';
import { request, download, type Snapshot, type PlanRow } from './api';

const months = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
const n = (v: number, digits = 0) => new Intl.NumberFormat('es-CL', { maximumFractionDigits: digits }).format(v);
const pct = (v: number | null) => v === null ? 'Sin jornada' : `${n(v * 100, 1)}%`;
const sum = (rows: PlanRow[], field: keyof PlanRow) => rows.reduce((s,r) => s + Number(r[field] || 0), 0);
const stamp = (v: string) => new Date(v).toLocaleString('es-CL', { timeZone: 'America/Santiago', dateStyle: 'short', timeStyle: 'short' });
const navigation = [
  { id: 'dashboard', label: 'Resumen nacional', icon: LayoutDashboard },
  { id: 'people', label: 'Dotación y metas', icon: Users },
  { id: 'import', label: 'Carga de reportes', icon: Upload },
  { id: 'parameters', label: 'Parámetros', icon: Settings2 },
  { id: 'versions', label: 'Versiones y trazabilidad', icon: FolderClock },
];
const EMPTY: Snapshot = { version: null, rows: [], comparisons: [], changes: [] };

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [snapshot, setSnapshot] = useState<Snapshot>(EMPTY);
  const [runs, setRuns] = useState<any[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [parameters, setParameters] = useState('');
  const [paramHash, setParamHash] = useState('');
  const [role, setRole] = useState('viewer');
  const [online, setOnline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null);
  const [institute, setInstitute] = useState('');
  const [area, setArea] = useState('');
  const [month, setMonth] = useState('');
  const [query, setQuery] = useState('');
  const [buk, setBuk] = useState<File>();
  const [sic, setSic] = useState<File>();
  const [reuse, setReuse] = useState(false);
  const [result, setResult] = useState<any>();
  const [historical, setHistorical] = useState<Snapshot>();

  async function refresh() {
    const [health, plan, history, p] = await Promise.all([
      request('/api/health'), request<Snapshot>('/api/plan'), request('/api/runs'), request('/api/parameters'),
    ]);
    setRole(health.role); setSnapshot(plan); setRuns(history.runs); setAudit(history.audit);
    setParameters(JSON.stringify(p.params, null, 2)); setParamHash(p.hash); setOnline(true);
  }
  useEffect(() => {
    refresh().catch(e => setNotice({ text: `No se pudo conectar al servicio local. ${e.message}`, error: true })).finally(() => setLoading(false));
  }, []);
  async function action(fn: () => Promise<void>) {
    setBusy(true); setNotice(null);
    try { await fn(); } catch (e) {
      setNotice({ text: e instanceof Error ? e.message : String(e), error: true });
      if (online) {
        try { const history = await request('/api/runs'); setRuns(history.runs); setAudit(history.audit); }
        catch { /* Preserve the original operation error if history is unavailable. */ }
      }
    }
    finally { setBusy(false); }
  }
  const filtered = useMemo(() => snapshot.rows.filter(r => (!institute || r.institute === institute)
    && (!area || r.area === area) && (!month || r.month === month)
    && (!query || `${r.professional_id} ${r.role}`.toLowerCase().includes(query.toLowerCase()))), [snapshot, institute, area, month, query]);
  const institutions = [...new Set(snapshot.rows.map(r => r.institute))].sort();
  const areas = [...new Set(snapshot.rows.map(r => r.area))].sort();
  const planned = sum(filtered, 'planned');
  const contracted = sum(filtered, 'contracted');
  const direct = sum(filtered, 'direct');
  const actualRows = filtered.filter(r => r.actual !== null);
  const actual = sum(actualRows, 'actual');
  const professionals = new Set(filtered.map(r => r.professional_id)).size;
  const chart = months.map((label, i) => {
    const rows = filtered.filter(r => r.month === `2026-${String(i+1).padStart(2,'0')}`);
    return { label, planned: sum(rows, 'planned_direct'), actual: sum(rows, 'actual'), hasSic: rows.some(r => r.actual !== null) };
  });
  const maxChart = Math.max(1, ...chart.flatMap(m => [m.planned, m.actual]));
  const currentRun = runs.find(r => r.version === snapshot.version);
  const isEditor = role === 'editor';

  const filters = <div className="filters">
    <label>Instituto<select value={institute} onChange={e => setInstitute(e.target.value)}><option value="">Todos los institutos</option>{institutions.map(v => <option key={v}>{v}</option>)}</select></label>
    <label>Área<select value={area} onChange={e => setArea(e.target.value)}><option value="">Todas las áreas</option>{areas.map(v => <option key={v}>{v}</option>)}</select></label>
    <label>Período<select value={month} onChange={e => setMonth(e.target.value)}><option value="">Enero – diciembre 2026</option>{months.map((v,i) => <option key={v} value={`2026-${String(i+1).padStart(2,'0')}`}>{v} 2026</option>)}</select></label>
    <button className="text-button filter-reset" onClick={() => { setInstitute(''); setArea(''); setMonth(''); setQuery(''); }}><RefreshCw size={14}/> Limpiar filtros</button>
  </div>;

  return <div className="app-shell">
    <a className="skip" href="#main">Saltar al contenido</a>
    <aside className="sidebar">
      <div className="brand"><div className="brand-symbol"><Clock3 size={27}/></div><div>Cada hora<span>CUENTA</span></div></div>
      <div className="workspace"><span className="workspace-dot"/><div>Planificación asistencial<small>Equipo central · Teletón</small></div><ChevronRight size={14}/></div>
      <div className="nav-label">ESPACIO DE TRABAJO</div>
      <nav aria-label="Navegación principal">{navigation.map(item => <button key={item.id} className={tab === item.id ? 'nav-item active' : 'nav-item'} aria-current={tab === item.id ? 'page' : undefined} onClick={() => setTab(item.id)}><item.icon size={18}/>{item.label}{item.id === 'import' && <span className="nav-tag">BUK</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="local-card"><Database size={18}/><div>Base de datos local<small><span className={online ? 'dot online' : 'dot'}/>{online ? 'SQLite conectado' : 'Conectando servicio'}</small></div></div><div className="profile"><div className="avatar">PC</div><div>Planificación central<small>{isEditor ? 'Edición local' : 'Solo lectura'}</small></div><ShieldCheck size={16}/></div></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb">Planificación <ChevronRight size={14}/><strong>{navigation.find(v => v.id === tab)?.label}</strong></div><div className="topbar-right"><span className="year"><CalendarDays size={14}/> Año 2026</span><span className="top-divider"/><span className="app-label">BOTATHON <b>2026</b></span></div></header>
      <main id="main">
        <div className="page-heading"><div><div className="eyebrow">CADA HORA QUE PLANIFICAMOS, CUENTA.</div><h1>{tab === 'dashboard' ? 'Una mirada a toda la red' : navigation.find(v => v.id === tab)?.label}</h1><p>{tab === 'dashboard' ? 'Capacidad asistencial, metas y ejecución en un solo lugar.' : tab === 'people' ? 'Del consolidado al detalle por profesional, instituto y mes.' : tab === 'import' ? 'Valida la dotación y publica una nueva versión del plan.' : tab === 'parameters' ? 'Reglas visibles y editables, con una versión para cada cálculo.' : 'Cada publicación tiene un origen y un historial.'}</p></div><div className="heading-actions"><button className="button secondary" disabled={busy || !snapshot.version} onClick={() => action(() => download('/api/export', `plan_v${snapshot.version}.csv`))}><ArrowDownToLine size={16}/> Exportar plan</button>{tab !== 'import' && isEditor && <button className="button primary" onClick={() => setTab('import')}><Upload size={16}/> Cargar reportes</button>}</div></div>
        <div className="demo-banner"><span className="demo-mark">BASE MVP</span><span>Datos {currentRun?.source === 'demo-ficticia' ? 'ficticios' : 'locales'} · Reglas iniciales pendientes de validar con el kit oficial.</span><span className="demo-tech">React + Tauri + SQLite</span></div>
        {notice && <div role={notice.error ? 'alert' : 'status'} className={`notice ${notice.error ? 'error' : 'success'}`}><span>{notice.text}</span><button aria-label="Cerrar aviso" onClick={() => setNotice(null)}><X size={17}/></button></div>}
        {loading ? <div className="loading"><LoaderCircle className="spin"/> Conectando con la planificación local…</div> : <>
          {!online && <div className="empty"><Database/><h2>El servicio local no está disponible</h2><p>Inicia la aplicación con <code>npm run dev</code> para conectar React y SQLite.</p><button className="button primary" onClick={() => action(async () => { await refresh(); setNotice({ text: 'Servicio conectado.' }); })}>Reintentar conexión</button></div>}
          {online && (tab === 'dashboard' || tab === 'people') && <>
            <div className="publication-line"><span><span className="dot online"/>{snapshot.version ? `Versión v${String(snapshot.version).padStart(3,'0')} · Publicada localmente` : 'Aún no hay un plan publicado'}</span><small>{snapshot.created_at ? `Actualizada ${stamp(snapshot.created_at)}` : 'Comienza con una carga válida'}</small></div>
            {filters}
            {!snapshot.version ? <div className="empty"><FileSpreadsheet size={40}/><h2>Tu primera planificación comienza aquí</h2><p>Carga BUK y SIC o explora el flujo con archivos ficticios.</p><button className="button primary" disabled={busy || !isEditor} onClick={() => action(async () => { await request('/api/demo', {method:'POST'}); await refresh(); setNotice({ text:'Demo ficticia publicada. Puedes probar el cambio de julio.' }); })}>Cargar demo ficticia</button></div> : <>
              <section className="kpi-grid" aria-label="Indicadores del período"><Kpi label="ATENCIONES PLANIFICADAS" value={n(planned)} detail="Directas + indirectas" icon={<Activity size={19}/>} extra="Proyección del período"/><Kpi label="META DE GESTIÓN" value={n(sum(filtered,'target'),1)} detail="Según parámetros publicados" icon={<CheckCircle2 size={19}/>} extra="Suma sin redondeo intermedio"/><Kpi label="FOJA" value={pct(contracted ? direct/contracted : null)} detail="Horas directas / contratadas" icon={<Clock3 size={19}/>} extra={`${n(direct)} h de atención directa`} accent/><Kpi label="PROFESIONALES" value={n(professionals)} detail={`${new Set(filtered.map(r => r.institute)).size} institutos en la selección`} icon={<Users size={19}/>} extra={`${n(contracted)} h contratadas`}/></section>
              {tab === 'dashboard' ? <>
                <div className="dashboard-grid"><section className="card chart-card"><div className="card-heading"><div><h2>Planificación y ejecución</h2><p>Atención directa · comparación mensual con SIC</p></div><span className="light-tag">2026</span></div><div className="chart-legend"><span><i className="legend-plan"/>Plan directo</span><span><i className="legend-actual"/>Realizado SIC</span></div><div className="chart"><div className="chart-axis">{[1,.75,.5,.25,0].map(v => <span key={v}>{n(maxChart*v)}</span>)}</div><div className="chart-plot"><div className="grid-lines">{[1,2,3,4,5].map(i => <i key={i}/>)}</div>{chart.map(m => <div key={m.label} className="chart-month"><div className="bar-pair" role="img" aria-label={`${m.label}: ${n(m.planned)} planificadas; ${m.hasSic ? n(m.actual) + ' realizadas' : 'sin SIC'}`} title={`${m.label}: plan ${n(m.planned)}, SIC ${m.hasSic ? n(m.actual) : 'sin datos'}`}><div className="bar plan" style={{height: `${m.planned / maxChart * 100}%`}}/><div className={`bar actual ${!m.hasSic ? 'no-data' : ''}`} style={{height: m.hasSic ? `${m.actual / maxChart * 100}%` : '3px'}}/></div><span>{m.label}</span></div>)}</div></div><div className="chart-footer"><span className="dot"/>Sin barra SIC = sin datos. Cero es un dato observado.<span>{n(actual)} atenciones realizadas</span></div></section>
                <section className="card distribution-card"><div className="card-heading"><div><h2>¿Dónde están las horas?</h2><p>Distribución de la jornada contratada</p></div></div><div className="hours-total">{n(contracted)} <span>horas</span></div><div className="stacked-bar">{(['direct','indirect','nas','absence'] as const).map(k => <span className={`segment ${k}`} key={k} style={{width:`${contracted ? sum(filtered,k)/contracted*100 : 0}%`}}/>)}</div><div className="hour-breakdown">{[['direct','Atención directa'],['indirect','Atención indirecta'],['nas','No asistencial'],['absence','Ausencias y calendario']].map(([key,label]) => <div key={key}><span><i className={`segment ${key}`}/>{label}</span><strong>{n(sum(filtered,key as keyof PlanRow))} <small>h</small></strong></div>)}</div><div className="insight"><ShieldCheck size={17}/><span>FOJA se calcula sobre la suma de horas, también en los consolidados.</span></div></section></div>
                <section className="card institute-card"><div className="card-heading"><div><h2>La red, instituto por instituto</h2><p>Selecciona una sede para profundizar en su dotación.</p></div><button className="text-button" onClick={() => setTab('people')}>Ver detalle <ArrowRight size={15}/></button></div><div className="table-scroll"><table><thead><tr><th>Instituto</th><th>Profesionales</th><th>Horas directas</th><th>Atenciones totales</th><th>Meta de gestión</th><th>FOJA</th><th><span className="sr-only">Detalle</span></th></tr></thead><tbody>{[...new Set(filtered.map(r => r.institute))].sort().map(i => { const rows = filtered.filter(r => r.institute === i); return <tr key={i}><td><span className="institute-icon">{i.slice(0,2).toUpperCase()}</span><strong>{i}</strong></td><td>{new Set(rows.map(r => r.professional_id)).size}</td><td>{n(sum(rows,'direct'),1)} h</td><td>{n(sum(rows,'planned'))}</td><td>{n(sum(rows,'target'),1)}</td><td><span className="foja-pill">{pct(sum(rows,'contracted') ? sum(rows,'direct')/sum(rows,'contracted') : null)}</span></td><td><button className="icon-button" aria-label={`Ver detalle de ${i}`} onClick={() => { setInstitute(i); setTab('people'); }}><ArrowRight size={16}/></button></td></tr>; })}</tbody></table></div>{filtered.length === 0 && <p className="no-results">No hay resultados para estos filtros.</p>}</section>
                <div className="bottom-strip"><div><GitBranch size={19}/><span>Un plan trazable, desde su origen.<small>BUK → validación → cálculo → versión publicada</small></span></div><button className="text-button" onClick={() => setTab('versions')}>Consultar trazabilidad <ArrowRight size={15}/></button></div>
              </> : <section className="card people-card"><div className="card-heading"><div><h2>Plan por profesional y mes</h2><p>{n(filtered.length)} registros · SIC se compara con atención directa.</p></div><label className="search"><Search size={16}/><input aria-label="Buscar profesional o cargo" placeholder="Buscar ID o cargo" value={query} onChange={e => setQuery(e.target.value)}/></label></div><div className="table-scroll"><table><thead><tr>{['Profesional','Instituto / cargo','Mes','Contratadas','Directas','Indirectas','NAS','Ausencias','Plan total','Meta','SIC directo','FOJA'].map(h => <th key={h}>{h}</th>)}</tr></thead><tbody>{filtered.slice(0,240).map((r,i) => <tr key={i}><td><strong>{r.professional_id}</strong></td><td>{r.institute}<small className="cell-small">{r.role}</small></td><td>{months[Number(r.month.slice(-2))-1]}</td><td>{n(r.contracted,1)}</td><td>{n(r.direct,1)}</td><td>{n(r.indirect,1)}</td><td>{n(r.nas,1)}</td><td>{n(r.absence,1)}</td><td>{n(r.planned)}</td><td>{n(r.target,1)}</td><td>{r.actual === null ? <span className="muted">Sin SIC¹</span> : n(r.actual)}</td><td>{pct(r.foja)}</td></tr>)}</tbody></table></div><p className="table-note">Horas en h. ¹ SIC ausente o cruce con varios cargos: no se atribuye el mismo realizado a dos filas. Se muestran hasta 240 filas; exportar para obtener el detalle completo.</p></section>}
            </>}
          </>}
          {online && tab === 'import' && <div className="import-grid"><section className="card import-form"><div className="card-heading"><div><h2>Una nueva versión, con datos validados</h2><p>El plan vigente permanece visible hasta que termine la carga.</p></div><FileCheck2 size={24}/></div><form onSubmit={e => { e.preventDefault(); action(async () => { if (!buk) throw new Error('Selecciona un BUK .xlsx'); const form = new FormData(); form.append('buk',buk); if (sic) form.append('sic',sic); form.append('reuse_sic',String(reuse)); const r = await request('/api/import',{method:'POST',body:form}); setResult(r); await refresh(); setNotice({text: r.status === 'reused' ? `Lote ya procesado. Sigue visible v${r.active_version}.` : `Plan v${r.version} publicado localmente.`}); }); }}>
            <FileInput label="1. Reporte BUK" hint="Dotación y vigencias · hoja BUK" file={buk} setFile={setBuk}/><FileInput label="2. Reporte SIC" hint="Atenciones realizadas · hoja SIC" file={sic} setFile={setSic}/><label className="checkbox"><input type="checkbox" checked={reuse} disabled={!snapshot.version} onChange={e => setReuse(e.target.checked)}/> Reutilizar el SIC de la última versión válida</label><div className="import-foot"><p>Se validan columnas, tipos, fechas, duplicados y reglas. Publicación local en SQLite.</p><button className="button primary" disabled={busy || !isEditor || !buk} type="submit">{busy ? <LoaderCircle className="spin" size={16}/> : <ShieldCheck size={16}/>}Validar y publicar</button></div></form>{result && <div className="import-result" role="status"><CheckCircle2 size={21}/><div><strong>{result.status === 'reused' ? 'Entrada ya procesada' : `Versión v${result.version} publicada`}</strong><p>{result.summary.added} altas · {result.summary.changed} cambios · {result.summary.ended} términos explícitos</p><code>Lote {result.run_id.slice(0,8)}</code></div></div>}</section><div><section className="card helper-card"><div className="helper-icon"><FileSpreadsheet size={25}/></div><h2>Parte con la planilla base</h2><p>Usa el formato normalizado mientras llega el kit. Sus columnas se deben mapear al Excel oficial antes de la competencia.</p><button className="button secondary full" onClick={() => action(() => download('/api/templates/Plantilla_Botathon_2026.xlsx','Plantilla_Botathon_2026.xlsx'))}><ArrowDownToLine size={16}/> Descargar plantilla vacía</button><hr/><h3>Recorrido de prueba</h3><ol className="demo-steps"><li>Publica BUK base + SIC demo.</li><li>Carga el cambio de julio y reutiliza SIC.</li><li>Prueba el archivo inválido: el plan se conserva.</li></ol><div className="sample-links">{['BUK_base_demo.xlsx','SIC_demo.xlsx','BUK_cambio_julio.xlsx','BUK_invalido.xlsx'].map(f => <button className="text-button" key={f} onClick={() => action(() => download(`/api/templates/${f}`,f))}><ArrowDownToLine size={13}/>{f}</button>)}</div><button className="button secondary full" disabled={busy || !isEditor} onClick={() => action(async () => { await request('/api/demo',{method:'POST'}); await refresh(); setNotice({text:'Datos ficticios procesados. Consulta la versión visible en el resumen.'}); })}>Cargar demo ficticia</button></section><div className="integration-note"><GitBranch size={18}/><div><strong>Preparado para Blue Prism</strong><p>El contrato JSON y el cliente de carpeta están incluidos. La ejecución real del bot debe conectarse y verificarse en la VM.</p></div></div></div></div>}
          {online && tab === 'parameters' && <section className="card params-card"><div className="card-heading"><div><h2>Parámetros de trabajo</h2><p>Guardar valida el borrador. Recalcular publica otra versión sin alterar las anteriores.</p></div><span className="light-tag">SHA {paramHash.slice(0,8)}</span></div><div className="params-info"><Settings2 size={18}/><p>Porcentajes entre 0 y 1. Cada distribución suma 1. Calendario por instituto/mes; incluye descuentos de feriados y vacaciones. Meta inicial: 90%.</p></div><label className="json-label" htmlFor="params">Configuración JSON editable</label><textarea id="params" className="json-editor" spellCheck={false} value={parameters} onChange={e => setParameters(e.target.value)} readOnly={!isEditor}/><div className="params-actions"><button className="button secondary" disabled={busy || !isEditor} onClick={() => action(async () => { let p; try { p=JSON.parse(parameters); } catch { throw new Error('JSON inválido. Revisa comas y llaves.'); } const r=await request('/api/parameters',{method:'PUT',body:JSON.stringify({params:p})}); setParamHash(r.hash); setNotice({text:'Parámetros validados y guardados. El plan visible conserva su versión hasta recalcular.'}); })}><Check size={16}/>Validar y guardar</button><button className="button primary" disabled={busy || !isEditor || !snapshot.version} onClick={() => action(async () => { const r=await request('/api/recalculate',{method:'POST'}); await refresh(); setNotice({text:`Recálculo listo. Versión visible: v${r.active_version}.`}); })}><RefreshCw size={16}/>Recalcular con parámetros guardados</button></div></section>}
          {online && tab === 'versions' && <>
            <div className="version-summary"><ShieldCheck size={22}/><div><strong>{snapshot.version ? `La última versión válida es v${String(snapshot.version).padStart(3,'0')}` : 'Sin versión publicada'}</strong><p>Un archivo rechazado no sustituye el plan publicado. Reprocesar la misma entrada y reglas no duplica una versión.</p></div></div><section className="card"><div className="card-heading"><div><h2>Historial de corridas</h2><p>Origen, resultado y cambios detectados en cada lote.</p></div><span className="light-tag">{runs.length} corridas</span></div><div className="table-scroll"><table><thead><tr><th>Versión / lote</th><th>Fecha · Santiago</th><th>Origen</th><th>Resultado</th><th>Altas / cambios / términos</th><th>Detalle</th></tr></thead><tbody>{runs.map(r => <tr key={r.id}><td><strong>{r.version ? `v${String(r.version).padStart(3,'0')}` : 'Sin publicar'}</strong><small className="cell-small">{r.id.slice(0,8)}</small></td><td>{stamp(r.created_at)}</td><td>{r.source}</td><td><span className={`status-pill ${r.status}`}>{r.status === 'published' ? 'Publicada' : 'Rechazada'}</span></td><td>{r.status === 'published' ? `${r.summary.added} / ${r.summary.changed} / ${r.summary.ended}` : 'Se conserva el plan vigente'}</td><td>{r.version ? <button className="text-button" onClick={() => action(async () => setHistorical(await request(`/api/plan?version=${r.version}`)))}>Consultar <ChevronRight size={14}/></button> : <details><summary>Ver errores</summary><ul>{r.errors.map((e:string,i:number) => <li key={i}>{e}</li>)}</ul></details>}</td></tr>)}</tbody></table></div>{!runs.length && <p className="no-results">La primera carga aparecerá aquí.</p>}</section>
            {historical && <section className="card historical"><div className="card-heading"><div><h2>Consulta de v{historical.version}</h2><p>Esta consulta conserva la versión vigente.</p></div><button className="icon-button" aria-label="Cerrar versión consultada" onClick={() => setHistorical(undefined)}><X size={18}/></button></div><p>{historical.rows.length} registros · {n(sum(historical.rows,'planned'))} atenciones · parámetros {historical.params_hash?.slice(0,8)}</p><div className="change-list">{historical.changes.map((c:any,i:number) => <div key={i}><GitBranch size={15}/><strong>{c.contract_id}</strong><span>{c.kind === 'added' ? 'Alta' : c.kind === 'ended' ? 'Término explícito' : 'Cambio'} · desde {c.effective_from}</span><span>{c.before ? `${c.before.hours_weekly} h → ` : ''}{c.after.hours_weekly} h</span></div>)}</div></section>}
            <section className="card audit-card"><div className="card-heading"><div><h2>Registro de operaciones</h2><p>Identidad local de sesión. No reemplaza autenticación institucional.</p></div></div>{audit.slice(0,12).map(e => <div className="audit-row" key={e.id}><span className="dot"/><strong>{e.operation}</strong><span>{e.actor}</span><time>{stamp(e.created_at)}</time></div>)}</section>
          </>}
        </>}
        <footer className="page-footer"><span>Cada hora cuenta <span className="footer-dot">·</span> Base de trabajo Botathon 2026</span><span><Database size={12}/> Datos en tu equipo <span className="footer-dot">·</span> v0.1.0</span></footer>
      </main>
    </div>
    {busy && <div className="busy-indicator" role="status"><LoaderCircle size={16} className="spin"/> Procesando…</div>}
  </div>;
}

function Kpi({label,value,detail,icon,extra,accent=false}:{label:string;value:string;detail:string;icon:React.ReactNode;extra:string;accent?:boolean}) {
  return <article className={`kpi ${accent ? 'accent' : ''}`}><div className="kpi-label">{label}<span>{icon}</span></div><div className="kpi-value">{value}</div><p>{detail}</p><div className="kpi-extra"><span className="dot"/>{extra}</div></article>;
}
function FileInput({label,hint,file,setFile}:{label:string;hint:string;file:File|undefined;setFile:(f:File|undefined)=>void}) {
  return <label className={`file-input ${file ? 'selected' : ''}`}><span className="file-label">{label}</span><span className="file-zone"><FileSpreadsheet size={27}/><span><strong>{file?.name || 'Selecciona un archivo Excel'}</strong><small>{file ? `${n(file.size/1024,1)} KB · listo para validar` : hint}</small></span><span className="light-tag">.xlsx</span></span><input type="file" accept=".xlsx" onChange={e => setFile(e.target.files?.[0])}/></label>;
}
