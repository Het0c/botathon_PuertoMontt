import { defineConfig, loadEnv } from 'vite';
import { cwd } from 'node:process';
import { existsSync, readFileSync } from 'node:fs';
import react from '@vitejs/plugin-react';
import { resolveConfig } from './src/config.ts';
export default defineConfig(({mode}) => {
  const config = resolveConfig(loadEnv(mode,cwd(),'VITE_'));
  if (config.mode === 'error') throw new Error(config.message);
  return {plugins:[react()],base:'./',server:{host:'127.0.0.1',port:5173,strictPort:true,proxy:{'/calc-api':{
    target:'http://127.0.0.1:8765',changeOrigin:true,rewrite:(path:string)=>path.replace(/^\/calc-api/,''),
    configure:(proxy)=>{proxy.on('proxyReq',(request,incoming)=>{
      // Token privado en el servidor de desarrollo; nunca en VITE_* ni en el navegador.
      if(!incoming.headers.authorization&&existsSync('work/api-token'))request.setHeader('Authorization','Bearer '+readFileSync('work/api-token','utf8').trim());
    });},
  }}},preview:{host:'127.0.0.1',port:4173}};
});
