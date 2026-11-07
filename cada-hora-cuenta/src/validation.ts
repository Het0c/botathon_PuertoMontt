import type { PlanDocument } from './types';

export const MAX_FILE_BYTES = 10 * 1024 * 1024;
const textFields = ['professional_id', 'institute', 'area', 'role', 'month'] as const;
const numericFields = ['contracted', 'direct', 'indirect', 'nas', 'absence', 'planned_direct', 'planned_indirect', 'planned', 'target'] as const;
const allowed = new Set<string>([...textFields, ...numericFields, 'actual', 'foja']);
export class ContractError extends Error {
  constructor(public readonly errors: string[]) { super(errors.join('\n')); }
}
const object = (v: unknown): v is Record<string, any> => !!v && typeof v === 'object' && !Array.isArray(v);
const finite = (v: unknown, max = 1e7): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= max;

/** Validación del contrato de salida. No limpia Excel ni calcula reglas asistenciales. */
export function validateDocument(input: unknown): PlanDocument {
  if (!object(input)) throw new ContractError(['Se esperaba un objeto JSON con resultados procesados.']);
  const errors: string[] = [];
  if (Object.keys(input).some(k => !['schema_version','year','parameters_version','rows'].includes(k))) errors.push('El documento contiene campos no soportados.');
  if (input.schema_version !== 1 || input.year !== 2026) errors.push('Se requiere schema_version=1 y year=2026.');
  if (typeof input.parameters_version !== 'string' || !input.parameters_version.trim() || input.parameters_version.length > 120) errors.push('parameters_version debe identificar las reglas usadas por Python (1–120 caracteres).');
  if (!Array.isArray(input.rows) || input.rows.length === 0 || input.rows.length > 20000) throw new ContractError([...errors, 'rows debe contener entre 1 y 20.000 resultados mensuales.']);
  const seen = new Set<string>();
  input.rows.forEach((r: unknown, i: number) => {
    const at = `Fila ${i+1}`;
    if (!object(r)) { errors.push(`${at}: se esperaba un objeto.`); return; }
    if (Object.keys(r).some(k => !allowed.has(k))) errors.push(`${at}: columnas no soportadas; exportar solo el contrato normalizado.`);
    for (const k of textFields) if (typeof r[k] !== 'string' || !r[k].trim() || r[k].length > 120) errors.push(`${at}: ${k} requerido (1–120 caracteres).`);
    if (typeof r.month !== 'string' || !/^2026-(0[1-9]|1[0-2])$/.test(r.month)) errors.push(`${at}: month debe ser AAAA-MM dentro de 2026.`);
    for (const k of numericFields) if (!finite(r[k])) errors.push(`${at}: ${k} debe ser un número entre 0 y 10.000.000.`);
    for (const k of ['planned_direct','planned_indirect','planned']) if (!Number.isInteger(r[k])) errors.push(`${at}: ${k} debe ser entero.`);
    if (r.actual !== null && (!finite(r.actual) || !Number.isInteger(r.actual))) errors.push(`${at}: actual debe ser entero no negativo o null si no hay SIC.`);
    if (numericFields.every(k => finite(r[k]))) {
      if (Math.abs(r.contracted - r.direct - r.indirect - r.nas - r.absence) > .01) errors.push(`${at}: las categorías de horas no concilian con las contratadas.`);
      if (r.planned !== r.planned_direct + r.planned_indirect) errors.push(`${at}: planned no concilia con directa + indirecta.`);
      if (r.target > r.planned) errors.push(`${at}: target supera las atenciones planificadas.`);
      if (r.contracted === 0 ? r.foja !== null : !finite(r.foja,1) || Math.abs(r.foja - r.direct/r.contracted) > .0001) errors.push(`${at}: FOJA no concilia con las horas; con jornada cero debe ser null.`);
    }
    const key = JSON.stringify(textFields.map(k => r[k]));
    if (seen.has(key)) errors.push(`${at}: profesional, instituto, área, cargo y mes duplicados.`);
    seen.add(key);
  });
  if (errors.length) throw new ContractError(errors.slice(0,100));
  return structuredClone(input) as PlanDocument;
}

export async function readPlanFile(file: File): Promise<PlanDocument> {
  if (!file.name.toLowerCase().endsWith('.json')) throw new ContractError(['Selecciona el JSON de resultados generado por Python.']);
  if (file.size > MAX_FILE_BYTES) throw new ContractError(['El archivo supera 10 MB.']);
  let data: unknown;
  try { data = JSON.parse(await file.text()); } catch { throw new ContractError(['JSON ilegible. Revisa la salida del proceso Python.']); }
  return validateDocument(data);
}

export function toCsv(document: PlanDocument): string {
  const fields = [...textFields, ...numericFields, 'actual', 'foja'];
  const quote = (v: unknown) => {
    let s = v === null || v === undefined ? '' : String(v);
    if (typeof v === 'string' && /^[=+\-@\t\r]/.test(s)) s = "'" + s;
    return '"' + s.replaceAll('"','""') + '"';
  };
  return '\uFEFF' + [fields.map(quote).join(','), ...document.rows.map(r => fields.map(k => quote(r[k as keyof typeof r])).join(','))].join('\r\n');
}

export function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
