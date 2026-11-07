import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { PGlite } from '@electric-sql/pglite';
import { readFileSync } from 'node:fs';

const ids={editor:'11111111-1111-1111-1111-111111111111',reviewer:'22222222-2222-2222-2222-222222222222',viewer:'33333333-3333-3333-3333-333333333333',outsider:'44444444-4444-4444-4444-444444444444'};
const sample=()=>{
  const p=JSON.parse(readFileSync(new URL('../public/examples/plan_demo_2026.json',import.meta.url),'utf8'));
  p.rows=p.rows.slice(0,2);return p;
};
let db:PGlite;
async function asUser(user:keyof typeof ids,sql:string,params:any[]=[]){
  await db.exec('set role authenticated');
  try{await db.query("select set_config('request.jwt.claim.sub',$1,false)",[ids[user]]);return await db.query<any>(sql,params);}
  finally{await db.exec('reset role');}
}
const submit=async(p=sample())=>(await asUser('editor','select public.submit_plan_revision($1::jsonb,$2) as revision',[JSON.stringify(p),'salida_python.json'])).rows[0].revision;
const review=async(id:string,decision='approved',comment='Evidencia revisada')=>asUser('reviewer','select public.review_plan_revision($1::uuid,$2,$3)',[id,decision,comment]);

beforeAll(async()=>{
  db=new PGlite();
  // Solo fixture de prueba. Supabase proporciona auth.users, auth.uid y estos roles.
  await db.exec(`create role anon;create role authenticated;create schema auth;
    create table auth.users(id uuid primary key);
    create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;
    grant usage on schema auth to authenticated,anon;
    grant usage on schema public to authenticated,anon;`);
  for(const id of Object.values(ids))await db.query('insert into auth.users values($1::uuid)',[id]);
  await db.exec(readFileSync(new URL('../supabase/migrations/202611070001_plan_reviews.sql',import.meta.url),'utf8'));
  await db.exec(readFileSync(new URL('../supabase/migrations/202611070002_calculation_parameters.sql',import.meta.url),'utf8'));
  for(const role of ['editor','reviewer','viewer'] as const)await db.query('insert into public.plan_members values($1::uuid,$2)',[ids[role],role]);
},30000);
beforeEach(async()=>{await db.exec('delete from public.plan_audit_logs;delete from public.plan_publication;delete from public.plan_revisions;');});
afterAll(async()=>{await db?.close();});

describe('Migración PostgreSQL y políticas de Supabase',()=>{
  it('habilita RLS en las cuatro tablas',async()=>{
    const {rows}=await db.query<any>("select relrowsecurity from pg_class where relname in ('plan_members','plan_revisions','plan_publication','plan_audit_logs')");
    expect(rows).toHaveLength(4);expect(rows.every(r=>r.relrowsecurity)).toBe(true);
  });
  it('publica solo al aprobar; rechazos y errores conservan la última aprobada',async()=>{
    const base=await submit();expect((await db.query('select * from plan_publication')).rows).toHaveLength(0);
    await review(base.id);
    const changed=sample();changed.parameters_version='nuevo';const next=await submit(changed);
    await review(next.id,'rejected');
    await asUser('editor','select record_plan_validation_failure($1::jsonb)',[JSON.stringify(['Fila 1: inválida'])]);
    const {rows}=await db.query<any>('select revision_id from plan_publication');expect(rows[0].revision_id).toBe(base.id);
    const logs=(await db.query<any>('select operation,actor_id from plan_audit_logs order by id')).rows;
    expect(logs.map(r=>r.operation)).toEqual(['revision_submitted','revision_approved','revision_submitted','revision_rejected','validation_failed']);
    expect(logs[1].actor_id).toBe(ids.reviewer);
  });
  it('hace idempotente un reproceso sin generar otra revisión o log',async()=>{
    const a=await submit(),b=await submit();expect(a.id).toBe(b.id);
    expect((await db.query('select * from plan_revisions')).rows).toHaveLength(1);
    expect((await db.query('select * from plan_audit_logs')).rows).toHaveLength(1);
  });
  it.each(['negative','duplicate','unknown','meta','sic','foja'])('valida en servidor aunque se omita el frontend: %s',async kind=>{
    const p=sample();
    if(kind==='negative')p.rows[0].direct=-1;
    if(kind==='duplicate')p.rows.push(p.rows[0]);
    if(kind==='unknown')p.rows[0].nombre='dato no permitido';
    if(kind==='meta')p.rows[0].target=p.rows[0].planned+1;
    if(kind==='sic')delete p.rows[0].actual;
    if(kind==='foja')p.rows[0].foja=null;
    await expect(submit(p)).rejects.toThrow();
    expect((await db.query('select * from plan_revisions')).rows).toHaveLength(0);
  });
  it('separa editor, revisor, lector y cuenta sin membresía',async()=>{
    const r=await submit();
    await expect(asUser('editor','select review_plan_revision($1::uuid,$2,$3)',[r.id,'approved','ok'])).rejects.toThrow('rol');
    await expect(asUser('viewer','select submit_plan_revision($1::jsonb,$2)',[JSON.stringify(sample()),'x'])).rejects.toThrow('rol');
    await expect(asUser('outsider','select submit_plan_revision($1::jsonb,$2)',[JSON.stringify(sample()),'x'])).rejects.toThrow('rol');
    expect((await asUser('outsider','select * from plan_revisions')).rows).toHaveLength(0);
    expect((await asUser('viewer','select * from plan_revisions')).rows).toHaveLength(1);
  });
  it('impide modificar directamente revisiones, membresías y logs',async()=>{
    const r=await submit();
    await expect(asUser('editor',"update plan_revisions set status='approved' where id=$1::uuid",[r.id])).rejects.toThrow('permission');
    await expect(asUser('editor',"update plan_members set role='admin'")).rejects.toThrow('permission');
    await expect(asUser('editor',"insert into plan_audit_logs(actor_id,operation) values($1::uuid,'falso')",[ids.editor])).rejects.toThrow('permission');
    await expect(asUser('viewer','select record_plan_validation_failure($1::jsonb)',['["falso"]'])).rejects.toThrow('rol');
  });
  it('no admite decisiones vacías, dobles ni retrocesos de versión',async()=>{
    const first=await submit();
    await expect(review(first.id,'approved','  ')).rejects.toThrow('justificación');
    expect((await db.query<any>('select status from plan_revisions')).rows[0].status).toBe('pending');
    const p=sample();p.parameters_version='v2';const newer=await submit(p);await review(newer.id);
    await expect(review(first.id)).rejects.toThrow('anterior');
    await expect(review(newer.id,'rejected')).rejects.toThrow('resuelta');
    expect((await db.query<any>('select revision_id from plan_publication')).rows[0].revision_id).toBe(newer.id);
  });
  it('registra versiones de parámetros inmutables con rol de editor',async()=>{
    const version='a'.repeat(64),params={Param_Generales:[],Param_Distribucion_Cargo:[],Param_Semanas_Habiles:[],politicas:{}};
    await asUser('editor','select save_calculation_parameters($1,$2::jsonb)',[version,JSON.stringify(params)]);
    expect((await asUser('viewer','select * from plan_parameter_sets')).rows).toHaveLength(1);
    await expect(asUser('viewer','select save_calculation_parameters($1,$2::jsonb)',[version,JSON.stringify(params)])).rejects.toThrow('rol');
    await expect(asUser('editor','update plan_parameter_sets set parameters=parameters')).rejects.toThrow('permission');
    await expect(asUser('editor','select save_calculation_parameters($1,$2::jsonb)',[version,JSON.stringify({...params,politicas:{changed:true}})])).rejects.toThrow('inmutable');
  });
  it('anon no puede leer resultados ni invocar la escritura',async()=>{
    await db.exec('set role anon');
    try{
      await expect(db.query('select * from plan_revisions')).rejects.toThrow('permission');
      await expect(db.query('select submit_plan_revision($1::jsonb,$2)',[JSON.stringify(sample()),'x'])).rejects.toThrow('permission');
    }finally{await db.exec('reset role');}
  });
});
