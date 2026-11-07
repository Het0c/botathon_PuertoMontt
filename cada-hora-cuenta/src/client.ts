import { createClient } from '@supabase/supabase-js';
import { resolveConfig } from './config';
import { DemoRepository, SupabaseRepository } from './repositories';
export const config = resolveConfig({
  VITE_DATA_MODE:import.meta.env.VITE_DATA_MODE,
  VITE_SUPABASE_URL:import.meta.env.VITE_SUPABASE_URL,
  VITE_SUPABASE_PUBLISHABLE_KEY:import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY,
});
export const supabase = config.mode === 'supabase' ? createClient(config.url,config.key) : null;
export const repository = config.mode === 'demo' ? new DemoRepository() : supabase ? new SupabaseRepository(supabase) : null;
