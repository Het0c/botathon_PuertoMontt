import { invoke, isTauri } from '@tauri-apps/api/core';

type Connection = { port: number; token: string };
let connection: Connection | undefined;
async function settings() {
  if (!isTauri()) return { base: '', token: import.meta.env.VITE_DEV_API_TOKEN || (import.meta.env.DEV ? 'demo-local-cambiar' : sessionStorage.getItem('botathon_token') || '') };
  if (!connection) {
    for (let i = 0; i < 80; i++) {
      try { connection = await invoke<Connection>('get_connection'); break; }
      catch (e) { if (i === 79) throw e; await new Promise(r => setTimeout(r, 250)); }
    }
  }
  return { base: `http://127.0.0.1:${connection!.port}`, token: connection!.token };
}
export async function request<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const { base, token } = await settings();
  const headers = new Headers(options.headers);
  headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(base + path, { ...options, headers, signal: AbortSignal.timeout(60000) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.errors?.join('\n') || data.error || 'No se pudo completar la operación');
  return data;
}
export async function download(path: string, name: string) {
  const { base, token } = await settings();
  const response = await fetch(base + path, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error('No se pudo descargar el archivo');
  const blob = await response.blob();
  if (isTauri()) {
    const { save } = await import('@tauri-apps/plugin-dialog');
    const { writeFile } = await import('@tauri-apps/plugin-fs');
    const target = await save({ defaultPath: name });
    if (target) await writeFile(target, new Uint8Array(await blob.arrayBuffer()));
    return;
  }
  const href = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = href; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(href), 5000);
}
export type PlanRow = { professional_id: string; institute: string; area: string; role: string; month: string;
  contracted: number; direct: number; indirect: number; nas: number; absence: number;
  planned: number; planned_direct: number; planned_indirect: number; target: number; actual: number | null; foja: number | null };
export type Snapshot = { version: number | null; created_at?: string; run_id?: string; params_hash?: string;
  rows: PlanRow[]; comparisons: any[]; changes: any[] };
