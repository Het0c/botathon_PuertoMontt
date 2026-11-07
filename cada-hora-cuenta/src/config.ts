export type DataConfig = { mode: 'demo' } | { mode: 'supabase'; url: string; key: string } | { mode: 'error'; message: string };
export function resolveConfig(env: Record<string, string | undefined>): DataConfig {
  const calc = env.VITE_CALC_API_URL?.trim();
  if(calc){try{const u=new URL(calc);if(u.protocol!=='https:'&&!(u.protocol==='http:'&&['localhost','127.0.0.1'].includes(u.hostname)))throw new Error();}catch{return {mode:'error',message:'La API de cálculo debe usar HTTPS; HTTP solo en localhost.'};}}
  const mode = env.VITE_DATA_MODE;
  const url = env.VITE_SUPABASE_URL?.trim();
  const key = env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim();
  let privileged = !!key?.startsWith('sb_secret_');
  try { privileged ||= JSON.parse(atob(key!.split('.')[1].replaceAll('-','+').replaceAll('_','/'))).role === 'service_role'; } catch { /* New publishable keys are not JWTs. */ }
  if (privileged) return {mode:'error',message:'El navegador solo admite una clave publishable/anon. Retira la clave privada y rótala si fue publicada.'};
  if (mode === 'demo' || (!mode && !url && !key)) return {mode:'demo'};
  if (mode && mode !== 'supabase') return {mode:'error',message:'VITE_DATA_MODE debe ser demo o supabase.'};
  if (!url || !key) return {mode:'error',message:'Configura VITE_SUPABASE_URL y VITE_SUPABASE_PUBLISHABLE_KEY para conectar el proyecto.'};
  try {
    const target = new URL(url);
    if (target.protocol !== 'https:' && !(target.protocol === 'http:' && ['localhost','127.0.0.1'].includes(target.hostname))) throw new Error();
  } catch { return {mode:'error',message:'La URL de Supabase debe usar HTTPS (HTTP solo para desarrollo en localhost).'}; }
  return {mode:'supabase',url,key};
}
