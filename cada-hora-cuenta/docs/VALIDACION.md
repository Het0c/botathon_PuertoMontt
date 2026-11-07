# Validación de la base web v0.2.0

Se verifican el contrato de resultados, la simulación y el SQL de revisiones. Las cifras de ejemplo son ficticias; no se certifica el cálculo contra el kit institucional.

- `npm test`: 30 pruebas aprobadas; cubren del frontend y de la migración sobre PostgreSQL embebido (PGlite).
- `npm run build`: TypeScript y Vite generan el sitio estático en `dist/`.
- El SQL se ejecuta con roles anon/authenticated y un fixture mínimo de `auth.users`/`auth.uid()`. Ese fixture vive solo en los tests; en producción, Auth lo proporciona Supabase.
- Casos de aceptación: pendiente no publica, aprobación publica, rechazo conserva la anterior, reproceso no duplica, error de contrato no crea revisión, identidades de horas y metas, permisos de editor/revisor/lector, acceso de cuenta ajena, protección de logs/membresías y bloqueo de retrocesos o decisiones dobles.
- La demo no persiste al recargar y no escribe datos compartidos. Nunca se usa como fallback silencioso ante un fallo de Supabase.

Límites: no se probó un proyecto Supabase real ni el transporte Auth/PostgREST contra su servicio remoto porque no se han configurado sus datos. La herramienta de navegador compartido requerida por este entorno no está disponible; no se afirma una prueba de interfaz en navegador para esta versión. La suite de SQL no sustituye la prueba de conexión del proyecto real.

La limpieza de datos la implementa el equipo Python; el cálculo oficial y su integración con Blue Prism los valida el equipo; no forman parte de esta entrega de frontend.
