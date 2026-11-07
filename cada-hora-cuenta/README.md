# Cada hora cuenta · Base Botathon 2026

Plantilla inicial **v0.1.0** para empezar sin repositorio: React + TypeScript + Vite, escritorio Tauri 2 y SQLite mediante un servicio Python local. Idioma: español. Uso previsto: equipo central en una VM, con datos ficticios.

**Flujo implementado:** BUK/SIC Excel normalizados → validación → cálculo provisional → publicación local transaccional → panel con última versión válida. Un lote inválido deja un error registrado y conserva la versión visible. Una repetición idéntica no duplica una versión.

Esta base parte de los dos DOCX adjuntos. La conversación enlazada no se pudo recuperar: no había una herramienta `read_thread` disponible. Los documentos se usaron como especificación; sus asignaciones de equipo y horarios no se ejecutaron como instrucciones del usuario.

## Arranque rápido en Windows (PowerShell)

Requisitos: Node 24 LTS, npm y Python 3.12. Ejecutar dentro de esta carpeta:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server/requirements-dev.txt
npm ci
npm run dev
```

Abrir **http://localhost:1420**. El modo de desarrollo carga una demo explícitamente ficticia con 16 profesionales y 4 institutos. Se guarda en `work/data/botathon.sqlite3`; reiniciar conserva el plan. El proceso arranca API y frontend juntos; Ctrl+C los detiene.

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements-dev.txt
npm ci
npm run dev
```

La clave de desarrollo es `demo-local-cambiar`; úsala solo en el entorno local ficticio. Si se cambia `BOTATHON_TOKEN`, definir el mismo valor en `VITE_DEV_API_TOKEN` para el servidor de desarrollo. En escritorio, Tauri genera una clave aleatoria por ejecución.

## Probar la publicación y el último plan válido

1. En **Carga de reportes**, descargar los archivos de ejemplo, o usar los de `examples/`.
2. Cargar `BUK_base_demo.xlsx` + `SIC_demo.xlsx`. Si la demo ya está cargada, se reutiliza su versión.
3. En Dotación, filtrar **Puerto Montt → PRO-009 → Ene 2026** y observar las cifras.
4. Cargar `BUK_cambio_julio.xlsx` marcando **Reutilizar SIC**. Cambia la jornada de PRO-009 desde julio: 44 nominales a 30 h. La aplicación ya aplica el tope 42 desde mayo.
5. Enero–junio conservan sus resultados; julio cambia. En la demo: enero 193,6 h contratadas; julio después del cambio, 138 h.
6. Cargar `BUK_invalido.xlsx`: reporta horas negativas y duplicados, sin reemplazar el plan.
7. Consultar **Versiones y trazabilidad** y exportar el plan CSV. Cerrar y abrir: la versión válida persiste.

La planilla vacía `examples/Plantilla_Botathon_2026.xlsx` incluye BUK, SIC, instrucciones y hojas de referencia de parámetros/calendario. Para usar un solo libro, seleccionarlo tanto como BUK como SIC. Las hojas de referencia no se importan automáticamente: editar reglas en Parámetros.

## Compilar Tauri

Tauri usa el mismo panel y empaqueta el servicio como sidecar con PyInstaller: el usuario final no necesita instalar Python ni iniciar un servidor aparte. La primera apertura del escritorio comienza sin datos; permite cargar la demo.

Requisitos adicionales Windows: Rust estable mediante rustup, **Visual Studio Build Tools con Desktop development with C++** y WebView2 Runtime. Compilar en la misma plataforma y arquitectura que usará el instalador.

```powershell
npm run desktop:dev
npm run desktop:build
```

`desktop:build` crea el sidecar, compila React y ejecuta Tauri. Salida: `src-tauri/target/release/bundle/`. Las descargas abren un diálogo nativo; solo se permite escribir en el archivo seleccionado.

Linux Debian/Ubuntu requiere previamente GLib/GTK/WebKit y las herramientas de compilación:

```bash
sudo apt-get update
sudo apt-get install -y libwebkit2gtk-4.1-dev build-essential libssl-dev librsvg2-dev patchelf libayatana-appindicator3-dev
npm run desktop:build
```

Se incluye `.github/workflows/desktop.yml` para compilar Windows/Linux manualmente o con una etiqueta `v*` cuando el equipo cree su repositorio remoto. El flujo sube artefactos de compilación a Actions; no publica una web ni crea un release público. El instalador debe firmarse según las políticas del equipo antes de una distribución institucional.

**Estado comprobado en este entorno:** build React, pruebas del núcleo, flujo real en Chromium y sidecar Linux. La compilación Tauri se detuvo por ausencia de bibliotecas de desarrollo GLib/GTK/WebKit. El instalador de Windows y el ciclo completo de escritorio no están verificados aquí.

## Integración Blue Prism

La organización no proporciona APIs BUK/SIC para el evento: se trabaja con Excel simulados. Esta base **recibe** BUK; no envía información a un servicio externo BUK.

Blue Prism debe vigilar la carpeta, ejecutar el lector y decidir según `estado.json`. El conector real y el proceso Blue Prism se montan en la VM del evento. Ver `docs/BLUE_PRISM.md`.

```powershell
.\.venv\Scripts\python.exe scripts/blueprism_ingest.py --connection work/data/connection.json --buk examples/BUK_base_demo.xlsx --sic examples/SIC_demo.xlsx --status work/estado.json
```

También acepta `--manifest examples/lote_cambio.json`. En instalación empaquetada, el sidecar ofrece `botathon-api.exe --ingest ...` con los mismos argumentos, sin Python instalado.

## Qué incluye y qué falta

Incluye filtros por instituto, área, mes e ID/cargo; horas por categoría, FOJA agregado por sumas, metas, SIC ausente frente a cero; catálogo de reglas editable; historial de corridas, errores, cambios y publicaciones; Excel, CSV, contrato JSON, conservación por vigencias y control de sesión local editor/lector.

**Antes de competir:** mapear las columnas reales del kit, cargar catálogos y calendario oficial completo por sede, conciliar fórmulas/redondeos con casos oficiales, conectar Blue Prism y validar el instalador en la VM. No se afirma coincidencia con el Excel oficial ni cobertura de todos los institutos: esos datos aún no fueron adjuntados. Reemplazos, vacantes y beneficios necesitan el modelo real del kit. El control de acceso actual es local por cuenta del sistema y token; no hay autenticación institucional ni flujo de autorización DMN.

Las decisiones provisionales y el tratamiento de historia están en `docs/REGLAS.md`; los campos y endpoints, en `docs/CONTRATO.md`. Las pruebas no sustituyen el cotejo con el Excel de referencia.

## Verificación

```bash
npm test
npm run build
```

Para repetir la prueba de interfaz, con `npm run dev` en otra terminal y Chromium instalado:

```bash
node scripts/check-ui.mjs
```

Definir `CHROMIUM_PATH` si Chromium está en otra ruta. La prueba modifica únicamente los datos ficticios de la demo, carga el cambio de julio, intenta una entrada inválida, descarga CSV y verifica vista móvil. Capturas en `work/screenshots/`.

## Carpetas y datos

- `src/`: panel React y adaptador para navegador/Tauri.
- `server/`: validación, cálculo, API local y SQLite.
- `src-tauri/`: shell Rust, permisos, iconos y configuración del sidecar.
- `examples/`: planillas y lotes JSON ficticios.
- `scripts/`: desarrollo, empaquetado e integración por carpeta.
- `tests/`: pruebas del flujo, persistencia y errores.
- `docs/`: contrato, reglas, Blue Prism y evidencia de validación.

En escritorio, SQLite queda en el directorio de datos de la aplicación: Windows `%APPDATA%/cl.botathon.cadahoracuenta`, Linux `$XDG_DATA_HOME/cl.botathon.cadahoracuenta` o `~/.local/share/cl.botathon.cadahoracuenta`. En macOS, `~/Library/Application Support/cl.botathon.cadahoracuenta`. `connection.json` vive junto a la base; contiene la clave efímera y no debe compartirse ni versionarse. La base tampoco se versiona. Para respaldar una base en uso, emplear SQLite backup; para copiar el archivo directamente, detener la aplicación primero.

Apoyo de IA: esta plantilla fue generada con asistencia de Codex; reglas y resultados institucionales requieren validación humana con el kit.
