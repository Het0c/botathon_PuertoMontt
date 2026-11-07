import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { validateDocument, readPlanFile, toCsv, ContractError } from '../src/validation';
import { DemoRepository } from '../src/repositories';
import { resolveConfig } from '../src/config';
const document = () => JSON.parse(readFileSync(new URL('../public/examples/plan_demo_2026.json',import.meta.url),'utf8'));

describe('Contrato de resultados procesados',()=>{
  it('recibe el ejemplo y conserva sus cifras, sin recalcular reglas',()=>{
    const plan=validateDocument(document());
    expect(plan.rows).toHaveLength(192);
    expect(plan.rows.reduce((s,r)=>s+r.planned,0)).toBe(43688);
    expect(plan.rows.find(r=>r.professional_id==='PRO-009'&&r.month==='2026-01')?.contracted).toBe(193.6);
  });
  it.each(['missing','negative','duplicate','sic','hours','meta','extra','foja'])('rechaza un contrato inválido: %s',kind=>{
    const p=document();const r=p.rows[0];
    if(kind==='missing')delete r.month;
    if(kind==='negative')r.direct=-1;
    if(kind==='duplicate')p.rows.push(structuredClone(r));
    if(kind==='sic')r.actual=undefined;
    if(kind==='hours')r.contracted+=10;
    if(kind==='meta')r.target=r.planned+1;
    if(kind==='extra')r.nombre_real='campo no permitido';
    if(kind==='foja')r.foja=null;
    expect(()=>validateDocument(p)).toThrow(ContractError);
  });
  it('distingue SIC cero de ausencia y neutraliza fórmulas al exportar',()=>{
    const p=document();p.rows[0].actual=0;p.rows[1].actual=null;p.rows[0].professional_id='=CMD()';
    const plan=validateDocument(p);const csv=toCsv(plan);
    expect(plan.rows[0].actual).toBe(0);expect(plan.rows[1].actual).toBeNull();
    expect(csv).toContain('"\'=CMD()"');
  });
  it('lee el archivo JSON que entrega el equipo',async()=>{
    const file=new File([JSON.stringify(document())],'resultados.json',{type:'application/json'});
    expect((await readPlanFile(file)).rows).toHaveLength(192);
  });
  it('rechaza un Excel o un JSON corrupto antes de enviarlo',async()=>{
    await expect(readPlanFile(new File(['x'],'entrada.xlsx'))).rejects.toThrow('JSON');
    await expect(readPlanFile(new File(['{'],'salida.json'))).rejects.toThrow('ilegible');
  });
});

describe('Demostración aislada',()=>{
  it('no publica pendientes, conserva la aprobada al rechazar y no duplica un reproceso',async()=>{
    const repo=new DemoRepository();const base=await repo.submit(document(),'demo.json');
    expect((await repo.load()).current).toBeNull();
    expect((await repo.submit(document(),'mismo.json')).id).toBe(base.id);
    await repo.review(base.id,'approved','Caso cotejado ficticio');
    const p=document();p.parameters_version='cambio-v2';const next=await repo.submit(p,'cambio.json');
    await repo.review(next.id,'rejected','No concilia con referencia');
    await repo.recordFailure(['Fila inválida']);
    expect((await repo.load()).current?.revision_id).toBe(base.id);
    expect((await repo.load()).logs[0].operation).toBe('validation_failed');
    expect((await new DemoRepository().load()).current).toBeNull();
  });
  it('respeta roles, decisiones inmutables y orden de publicación',async()=>{
    await expect(new DemoRepository('viewer').submit(document(),'demo')).rejects.toThrow('rol');
    const editor=new DemoRepository('editor');const r=await editor.submit(document(),'demo');
    await expect(editor.review(r.id,'approved','ok')).rejects.toThrow('rol');
    const repo=new DemoRepository();const first=await repo.submit(document(),'primera');
    const p=document();p.parameters_version='segunda';const second=await repo.submit(p,'segunda');
    await repo.review(second.id,'approved','ok');
    await expect(repo.review(first.id,'approved','ok')).rejects.toThrow('anterior');
    await expect(repo.review(second.id,'rejected','otra decisión')).rejects.toThrow('resuelta');
  });
});

describe('Configuración web',()=>{
  it('identifica demo y no oculta una conexión incompleta con datos ficticios',()=>{
    expect(resolveConfig({}).mode).toBe('demo');
    expect(resolveConfig({VITE_DATA_MODE:'supabase'}).mode).toBe('error');
    expect(resolveConfig({VITE_SUPABASE_URL:'https://example.supabase.co'}).mode).toBe('error');
  });
  it('admite claves públicas y rechaza claves privilegiadas',()=>{
    const env={VITE_DATA_MODE:'supabase',VITE_SUPABASE_URL:'https://example.supabase.co',VITE_SUPABASE_PUBLISHABLE_KEY:'sb_publishable_example'};
    expect(resolveConfig(env).mode).toBe('supabase');
    expect(resolveConfig({...env,VITE_SUPABASE_PUBLISHABLE_KEY:'sb_secret_example'}).mode).toBe('error');
    const role=btoa(JSON.stringify({role:'service_role'}));
    expect(resolveConfig({...env,VITE_SUPABASE_PUBLISHABLE_KEY:`head.${role}.signature`}).mode).toBe('error');
  });
  it('rechaza claves privadas incluso si se seleccionó demo',()=>{
    expect(resolveConfig({VITE_DATA_MODE:'demo',VITE_SUPABASE_PUBLISHABLE_KEY:'sb_secret_example'}).mode).toBe('error');
  });
});
