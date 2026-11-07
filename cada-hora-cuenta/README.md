# Cada hora cuenta · Base web v0.2.0

React + TypeScript + Vite para publicación online. Supabase guarda logs, revisiones y snapshots aprobados. El equipo se encarga de la limpieza en Python y del cálculo/integración con Blue Prism; este frontend recibe resultados listos para revisar.

## Arranque rápido

Requisito: Node 24 y npm.

```bash
npm ci
npm run dev
```

Abrir la dirección local que indica Vite (por defecto `http://127.0.0.1:5173`). Sin configuración, la aplicación muestra el modo demo explícito. Seleccionar **Cargar demo ficticia** para explorar el resumen nacional. No hay datos compartidos en ese modo: recargar reinicia la sesión.

Para conectar el proyecto real, aplicar la migración e invitar miembros según [SUPABASE.md](docs/SUPABASE.md). Copiar `.env.example` a `.env.local`, seleccionar `VITE_DATA_MODE=supabase` y configurar su URL y clave pública. Reconstruir el sitio después de cambiar variables.

## Flujo de trabajo

1. Python limpia los datos; el proceso del equipo con Blue Prism entrega el JSON de resultados según [CONTRATO.md](docs/CONTRATO.md).
2. El editor entra en **Cargar resultados** y selecciona ese JSON. La aplicación valida estructura, duplicados e identidades de horas/metas, sin aplicar fórmulas institucionales.
3. Supabase registra una revisión pendiente con la identidad del usuario autenticado. Reprocesar el mismo documento reutiliza la revisión existente.
4. El revisor abre **Revisiones → Ver revisión**, consulta/exporta el detalle y justifica su decisión.
5. **Aprobar y publicar** cambia la versión visible; **Rechazar** conserva el último plan aprobado. Los logs registran autor, operación, fecha y decisión.
6. **Actualizar** recupera cambios de otros usuarios. El frontend no utiliza suscripciones en tiempo real en esta base.

Los roles editor y reviewer están separados; admin puede hacer ambas operaciones. Viewer solo consulta. Los permisos también se comprueban en PostgreSQL, no solo en los botones del panel.

## Ejemplos para probar

Los archivos de `public/examples/` se pueden descargar desde **Cargar resultados**:

- `plan_demo_2026.json`: 192 resultados mensuales, 16 IDs y 4 institutos ficticios.
- `plan_cambio_julio.json`: otro snapshot ya calculado, con un cambio de jornada desde julio y meses anteriores conservados.
- `plan_invalido.json`: horas negativas para comprobar rechazo y preservación del plan aprobado.

No representan el kit oficial. Las reglas/cifras del caso real se cotejan dentro del trabajo del equipo; la web solo consume su salida. `actual: null` se distingue de cero y FOJA agregado divide las sumas de horas.

## Build, pruebas y hosting

```bash
npm test
npm run build
```

El build genera `dist/`, listo para hosting estático por HTTPS. No necesita un backend Python para servir la web. [DESPLIEGUE.md](docs/DESPLIEGUE.md) explica la configuración de hosting y GitHub Pages.

La suite ejecuta el contrato de entrada, el repositorio de demo, la configuración pública y la migración en PostgreSQL embebido, incluidos permisos RLS y revisión transaccional. Ver límites de verificación en [VALIDACION.md](docs/VALIDACION.md).

## Estructura

- `src/`: panel, validación del contrato, acceso Supabase y demo en memoria.
- `supabase/migrations/`: tablas, políticas RLS y funciones de revisión/publicación.
- `public/examples/`: resultados ficticios ya calculados.
- `tests/`: pruebas de contrato y PostgreSQL.
- `docs/`: contrato, Supabase y despliegue.

No se ha provisionado un proyecto Supabase real ni publicado el sitio online durante la preparación de esta versión. El código de limpieza del equipo vive fuera del frontend. Esta base fue preparada con asistencia de Codex.
