export type Role = 'viewer' | 'editor' | 'reviewer' | 'admin';
export type PlanRow = {
  professional_id: string; institute: string; area: string; role: string; month: string;
  contracted: number; direct: number; indirect: number; nas: number; absence: number;
  planned_direct: number; planned_indirect: number; planned: number; target: number;
  actual: number | null; foja: number | null;
};
export type PlanDocument = { schema_version: 1; year: 2026; parameters_version: string; rows: PlanRow[] };
export type RevisionStatus = 'pending' | 'approved' | 'rejected';
export type Revision = {
  id: string; version: number; status: RevisionStatus; source_label: string;
  created_at: string; submitted_by: string; reviewed_by: string | null;
  reviewed_at: string | null; review_comment: string | null;
};
export type Snapshot = PlanDocument & { version: number; revision_id: string; created_at: string };
export type AuditLog = { id: string | number; created_at: string; actor_id: string; operation: string; revision_id: string | null; detail: unknown };
export type Workspace = { current: Snapshot | null; revisions: Revision[]; logs: AuditLog[]; role: Role; user: string };
export interface PlanRepository {
  load(): Promise<Workspace>;
  submit(document: PlanDocument, label: string): Promise<Revision>;
  review(id: string, decision: 'approved' | 'rejected', comment: string): Promise<void>;
  recordFailure(errors: string[]): Promise<void>;
  snapshot(id: string): Promise<Snapshot>;
}
export const canSubmit = (role: Role) => role === 'editor' || role === 'admin';
export const canReview = (role: Role) => role === 'reviewer' || role === 'admin';
