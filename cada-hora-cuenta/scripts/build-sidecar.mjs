import { spawnSync } from 'node:child_process';
import { mkdirSync, copyFileSync, renameSync } from 'node:fs';
import { resolve } from 'node:path';
import { python } from './python.mjs';
const rust = spawnSync('rustc', ['-vV'], { encoding: 'utf8' });
if (rust.status !== 0) throw new Error('Instala Rust estable (rustup) y vuelve a abrir la terminal.');
const target = rust.stdout.match(/host: (.+)/)?.[1]?.trim();
if (!target) throw new Error('No se pudo detectar el target de Rust.');
const built = spawnSync(python, ['-m','PyInstaller','--noconfirm','--clean','--onefile',
  '--name','botathon-api','--paths',resolve('.'), '--add-data',`${resolve('examples')}${process.platform === 'win32' ? ';' : ':'}examples`,
  '--distpath','work/sidecar','--workpath','work/pyinstaller','--specpath','work', 'server/entrypoint.py'],
  { stdio:'inherit', env:{...process.env, PYINSTALLER_CONFIG_DIR:resolve('work/pyinstaller-cache')} });
if (built.status !== 0) process.exit(built.status ?? 1);
mkdirSync('src-tauri/binaries',{recursive:true});
const ext = process.platform === 'win32' ? '.exe' : '';
const destination = `src-tauri/binaries/botathon-api-${target}${ext}`;
copyFileSync(`work/sidecar/botathon-api${ext}`, destination + '.new');
try { renameSync(destination + '.new', destination); }
catch (e) { throw new Error('Cierra la aplicación de escritorio antes de reemplazar su servicio: ' + e.message); }
console.log(`Sidecar preparado para ${target}.`);
