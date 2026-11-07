import { defineConfig, loadEnv } from 'vite';
import { cwd } from 'node:process';
import react from '@vitejs/plugin-react';
import { resolveConfig } from './src/config.ts';
export default defineConfig(({mode}) => {
  const config = resolveConfig(loadEnv(mode,cwd(),'VITE_'));
  if (config.mode === 'error') throw new Error(config.message);
  return {plugins:[react()],base:'./',server:{host:'127.0.0.1',port:5173},preview:{host:'127.0.0.1',port:4173}};
});
