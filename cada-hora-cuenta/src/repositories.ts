import type { SupabaseClient } from '@supabase/supabase-js';
import { canReview, canSubmit, type AuditLog, type PlanDocument, type PlanRepository, type Revision, type Role, type Snapshot, type Workspace } from './types';
import { validateDocument } from './validation';

type Saved = { revision: Revision; document: PlanDocument; hash: string };
const snapshot = (r: Revision, document: PlanDocument): Snapshot => ({...structuredClone(document), version:r.version, revision_id:r.id, created_at:r.created_at});

/** Simulación aislada, sin persistencia. No escribe en Supabase ni en almacenamiento local. */
export class DemoRepository implements PlanRepository {
  private saved: Saved[] = [];
  private logs: AuditLog[] = [];
  private published: string | null = null;
  constructor(private role: Role = 'admin') {}
  private log(operation: string, revision_id: string | null, detail: unknown = {}) {
    this.logs.unshift({id:crypto.randomUUID(),created_at:new Date().toISOString(),actor_id:'demo',operation,revision_id,detail});
  }
  async load(): Promise<Workspace> {
    const saved = this.saved.find(r => r.revision.id === this.published);
    return structuredClone({current:saved ? snapshot(saved.revision,saved.document) : null,
      revisions:this.saved.map(r => r.revision).slice().reverse(),logs:this.logs,role:this.role,user:'Sesión de demostración'});
  }
  async submit(input: PlanDocument, label: string): Promise<Revision> {
    if (!canSubmit(this.role)) throw new Error('Tu rol no permite cargar revisiones.');
    const document = validateDocument(input);
    // Stable object key order for idempotence within this demonstration session.
    const canonical = (v: any): any => Array.isArray(v) ? v.map(canonical) : v && typeof v === 'object' ? Object.fromEntries(Object.keys(v).sort().map(k => [k,canonical(v[k])])) : v;
    const hash = JSON.stringify(canonical(document));
    const existing = this.saved.find(r => r.hash === hash);
    if (existing) return structuredClone(existing.revision);
    const revision: Revision = {id:crypto.randomUUID(),version:this.saved.length+1,status:'pending',source_label:label.slice(0,120),
      created_at:new Date().toISOString(),submitted_by:'demo',reviewed_by:null,reviewed_at:null,review_comment:null};
    this.saved.push({revision,document,hash}); this.log('revision_submitted',revision.id);
    return structuredClone(revision);
  }
  async review(id: string, decision: 'approved' | 'rejected', comment: string) {
    if (!canReview(this.role)) throw new Error('Tu rol no permite revisar planes.');
    if (!comment.trim() || comment.length > 2000) throw new Error('Escribe una justificación de 1 a 2.000 caracteres.');
    const saved = this.saved.find(r => r.revision.id === id);
    if (!saved || saved.revision.status !== 'pending') throw new Error('La revisión ya fue resuelta o no existe.');
    const current = this.saved.find(r => r.revision.id === this.published);
    if (decision === 'approved' && current && current.revision.version >= saved.revision.version) throw new Error('No se puede publicar una versión anterior al plan vigente.');
    Object.assign(saved.revision,{status:decision,reviewed_by:'demo',reviewed_at:new Date().toISOString(),review_comment:comment.trim()});
    if (decision === 'approved') this.published = id;
    this.log(`revision_${decision}`,id,{comment:comment.trim()});
  }
  async recordFailure(errors: string[]) {
    if (!canSubmit(this.role)) throw new Error('Tu rol no permite registrar cargas.');
    this.log('validation_failed',null,{errors:errors.slice(0,100)});
  }
  async snapshot(id: string) {
    const r = this.saved.find(r => r.revision.id === id);
    if (!r) throw new Error('Revisión no encontrada.');
    return snapshot(r.revision,r.document);
  }
}

const metadata = 'id,version,status,source_label,created_at,submitted_by,reviewed_by,reviewed_at,review_comment';
function check(error: { message: string } | null) { if (error) throw new Error(error.message); }
export class SupabaseRepository implements PlanRepository {
  constructor(private client: SupabaseClient) {}
  async load(): Promise<Workspace> {
    const {data:{user},error} = await this.client.auth.getUser(); check(error);
    if (!user) throw new Error('Inicia sesión con una cuenta del equipo.');
    const member = await this.client.from('plan_members').select('role').eq('user_id',user.id).maybeSingle(); check(member.error);
    if (!member.data) throw new Error('Esta cuenta todavía no pertenece al equipo de planificación.');
    const [pub,revisions,logs] = await Promise.all([
      this.client.from('plan_publication').select('revision_id').eq('singleton',true).maybeSingle(),
      this.client.from('plan_revisions').select(metadata).order('version',{ascending:false}).limit(100),
      this.client.from('plan_audit_logs').select('*').order('id',{ascending:false}).limit(100),
    ]);
    for (const r of [pub,revisions,logs]) check(r.error);
    return {current:pub.data ? await this.snapshot(pub.data.revision_id) : null,revisions:revisions.data as Revision[],
      logs:logs.data as AuditLog[],role:member.data.role as Role,user:user.email || user.id};
  }
  async submit(document: PlanDocument, label: string): Promise<Revision> {
    const {data,error} = await this.client.rpc('submit_plan_revision',{p_payload:validateDocument(document),p_source_label:label.slice(0,120)}); check(error);
    return data as Revision;
  }
  async review(id: string, decision: 'approved' | 'rejected', comment: string) {
    const {error} = await this.client.rpc('review_plan_revision',{p_revision_id:id,p_decision:decision,p_comment:comment}); check(error);
  }
  async recordFailure(errors: string[]) {
    const {error} = await this.client.rpc('record_plan_validation_failure',{p_errors:errors.slice(0,100)}); check(error);
  }
  async snapshot(id: string) {
    const {data,error} = await this.client.from('plan_revisions').select(`${metadata},snapshot`).eq('id',id).single(); check(error);
    if (!data) throw new Error('Revisión no encontrada.');
    return snapshot(data as Revision,validateDocument(data.snapshot));
  }
}
