import { spawn } from 'node:child_process';
import { python } from './python.mjs';
const api = spawn(python, ['-m', 'server.app', '--demo-dev', '--seed-demo'], { stdio: ['inherit', 'pipe', 'inherit'] });
let ui;
api.stdout.on('data', chunk => {
  process.stdout.write(chunk);
  if (chunk.toString().includes('"ready": true') && !ui) {
    ui = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1'], { stdio: 'inherit' });
    ui.on('exit', code => { api.kill(); process.exit(code ?? 0); });
  }
});
api.on('error', e => { console.error('Preparar .venv: ', e.message); process.exit(1); });
api.on('exit', code => { ui?.kill(); process.exit(code ?? 0); });
for (const s of ['SIGINT', 'SIGTERM']) process.on(s, () => { ui?.kill(); api.kill(); });
