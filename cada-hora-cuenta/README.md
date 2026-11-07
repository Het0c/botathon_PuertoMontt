# Cada hora cuenta · Kit real v0.3.0 (provisional)

React web + API Python opcional de cálculo + Supabase para logs/revisiones y plan aprobado. Blue Prism recibe, traduce, valida, encola, entrega y audita. `bot_traductor.py` de la raíz se integra sin reescribirlo.

**Alcance acordado: base para probar el flujo; sin despliegue. La validación del cálculo queda por hacer.**

**Exactitud pendiente:** en el plano real del repo se compararon los 471 casos: 1 coincide completamente y 470 presentan diferencias. Coinciden 4.487/13.188 comprobaciones. No se declara cálculo oficial correcto ni MVP listo para competir sin cerrar esas diferencias con el kit. Ver [VALIDACION.md](docs/VALIDACION.md) y sus datos.

## Arranque local para la VM

Node 24, Python 3.12 y openpyxl (sin dependencias nativas nuevas). Ejecutar desde `cada-hora-cuenta/`:

```powershell
python -m pip install -r server/requirements.txt
npm ci
```

Terminal 1:

```powershell
npm run api
```

Terminal 2:

```powershell
npm run dev
```

Vite indica `http://127.0.0.1:5173`. La API escucha solo loopback en 8765 y crea un token privado en `work/api-token`. El proxy de desarrollo añade ese token en el servidor de Vite; no se incorpora al bundle ni se muestra en la web. Guardar `work/` fuera del repositorio y limitar sus permisos en la VM.

## Primer recorrido con el plano del repo

En otra terminal, desde `cada-hora-cuenta`:

```powershell
python scripts/blueprism_ingest.py --kit "../ejemplo_salida_Planificacion_Input_BluePrism.xlsx" --api-url "http://127.0.0.1:8765" --token-file "work/api-token" --status "work/lote-base/estado.json"
```

En React: **Cargar resultados → Traer resultado de Blue Prism**. Consulta la revisión y sus advertencias; el plan aprobado anterior se conserva hasta decidir. Para una prueba ficticia local puedes aprobar como admin de demo; se identifica en pantalla que esa revisión vive en memoria. En producción, Supabase controla la persistencia y los roles.

El libro contiene 3.123 filas contractuales, 462 IDs distintos, 471 referencias y un catálogo de 18 institutos. El cálculo produce resultados para 15 sedes de esa muestra. Son los números observados del archivo, aunque difieran de la cifra estimada en el requerimiento. Agosto–diciembre se proyectan y se indican en pantalla cuando el reporte termina en julio.

## Camino real de la demo

1. Blue Prism recibe los dos crudos y ejecuta el **traductor existente**.
2. Valida el plano con sus VBO, produce el informe de errores y llena Work Queue `Planificacion` con etiquetas.
3. Invoca `blueprism_ingest.py --kit ... --api-url ...`. El lector entrega el Excel a `/api/batches`.
4. La API normaliza las tablas, carga parámetros reales y calcula un snapshot con incidencias y comparación independiente.
5. Con sesión Supabase configurada, crea una revisión pendiente y registra su versión; en modo local entrega un borrador persistido en la VM, claramente diferenciado.
6. La web permite revisar, aprobar y filtrar el plan. **Cambios del reporte** muestra cambios frente a la corrida anterior y su delta de meta mensual.
7. **Parámetros** permite editar meta, cargo/tramo, porcentajes y minutos; catálogo, calendario regional y asignaciones también están en el JSON completo. Guardar no publica; recalcular prepara otra revisión.

[BLUE_PRISM.md](docs/BLUE_PRISM.md) contiene la receta de VBO, Data Items y Work Queue. [DEMO.md](docs/DEMO.md) contiene el guion de cinco minutos y el generador de agosto. [REGLAS.md](docs/REGLAS.md) documenta las decisiones y límites del motor.

## API

Todas las rutas requieren token local o Supabase Auth con membresía. GET permite lectura a miembros; escrituras requieren editor/admin. La aprobación sigue en Supabase con reviewer/admin.

| Ruta | Método | Uso |
|---|---|---|
| `/api/health` | GET | Estado y modalidad de persistencia |
| `/api/batches` | POST | `{kit_base64, filename}` o `{document}` como alternativa de resultados JSON |
| `/api/parameters` | GET / PUT | `{params}`: lectura y edición validada del borrador |
| `/api/recalculate` | POST | Recalcular el último kit con parámetros guardados |
| `/api/latest` | GET | Último cálculo válido, cambios, advertencias y resumen de cotejo |
| `/api/runs` | GET | Historial de ingestión de la VM |

Una entrada inválida conserva el último cálculo y el plan aprobado. Reprocesar la misma entrada/parámetros reutiliza la corrida. El JSON de resultados de v0.2 continúa como alternativa; el formato ficticio BUK de la antigua versión de escritorio no es el camino de la arquitectura web actual.

`status=calculated/reused` con `published=false` no significa autorización del plan. `revision_status=pending` identifica revisión Supabase; `local_draft` identifica solo la VM. No presentar un borrador local como última versión aprobada compartida.

## Supabase y web online

Aplicar las migraciones **001 y 002**, configurar usuarios/roles y variables según [SUPABASE.md](docs/SUPABASE.md). Para online, publicar `dist/` y alojar la API Python mediante HTTPS con origen autorizado. No poner el token local ni credenciales de servicio en variables VITE. [DESPLIEGUE.md](docs/DESPLIEGUE.md) detalla la separación.

```bash
npm test
npm run test:python
npm run build
```

El build del frontend sigue siendo Vite, sin compilación de aplicación nativa. La prueba automatizada del SQL no sustituye una conexión con el proyecto real. No se ejecutó Blue Prism ni una prueba de interfaz en navegador: falta la VM y la herramienta compartida requerida en este entorno.

## Cotejo y escala

```powershell
python scripts/validar_kit.py --kit "../ejemplo_salida_Planificacion_Input_BluePrism.xlsx" --output-dir "work/validacion"
python scripts/benchmark_kit.py --kit "../ejemplo_salida_Planificacion_Input_BluePrism.xlsx" --professionals 600
```

La prueba sintética de 600 IDs generó 7.030 filas en 15 sedes en 0,544 s de motor en este Linux. No mide Blue Prism, red, navegador ni la VM Windows. Para 14 institutos/600 profesionales se usan los mismos catálogos por sede, claves persona/IT/mes, lotes reproducibles y snapshots: hay que medir la corrida completa en la VM y cerrar la exactitud antes de afirmar capacidad operativa.

Se usó IA (Codex) para programar y preparar pruebas/documentación. Los datos se identifican por PersonaId; no enviar nombres, RUT ni antecedentes clínicos. El adaptador omite nacimiento completo y observaciones libres.
