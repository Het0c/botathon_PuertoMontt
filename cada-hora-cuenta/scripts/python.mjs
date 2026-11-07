import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
const python=process.env.BOTATHON_PYTHON||(existsSync('.venv/Scripts/python.exe')?'.venv/Scripts/python.exe':existsSync('.venv/bin/python')?'.venv/bin/python':process.platform==='win32'?'python':'python3');
const child=spawn(python,process.argv.slice(2),{stdio:'inherit'});
child.on('error',e=>{console.error('No se pudo iniciar Python:',e.message);process.exit(1);});
child.on('exit',code=>process.exit(code??1));
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>child.kill());
