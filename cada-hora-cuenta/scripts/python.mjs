import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
export const python = process.env.BOTATHON_PYTHON || (existsSync('.venv/Scripts/python.exe') ? '.venv/Scripts/python.exe' : existsSync('.venv/bin/python') ? '.venv/bin/python' : process.platform === 'win32' ? 'python' : 'python3');
if (process.argv[1]?.endsWith('python.mjs')) {
  const p = spawn(python, process.argv.slice(2), { stdio: 'inherit' });
  p.on('error', e => { console.error(e.message); process.exit(1); });
  p.on('exit', code => process.exit(code ?? 1));
}
