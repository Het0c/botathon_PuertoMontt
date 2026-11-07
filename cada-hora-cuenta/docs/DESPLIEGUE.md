# Build y despliegue web

El frontend es una SPA React + TypeScript + Vite. No necesita Python para servir sus páginas estáticas; la función de cálculo del kit usa la API Python separada. Las pestañas son estado de React; no requiere reglas de reescritura para rutas internas. El build usa rutas relativas para poder publicarse en un subdirectorio.

```bash
cd cada-hora-cuenta
npm ci
npm test
npm run build
```

Publicar el contenido de `dist/` mediante HTTPS en el hosting estático elegido. En Vercel/Netlify: root `cada-hora-cuenta`, comando `npm run build`, salida `dist`, Node 24 y las tres variables públicas de Supabase descritas en `SUPABASE.md`. Si no se configura Supabase, el build es una demostración explícita en memoria.

## GitHub Actions / Pages

El workflow `.github/workflows/web.yml` en la raíz ejecuta tests y build en cambios del frontend y deja el artefacto `react-web-dist`. No requiere el compilador de una aplicación nativa.

Para publicar desde GitHub Pages:

1. En el repositorio: Settings → Pages → Source → GitHub Actions.
2. Configurar Repository Variables `VITE_DATA_MODE=supabase`, `VITE_SUPABASE_URL` y `VITE_SUPABASE_PUBLISHABLE_KEY` si se quiere conexión real. Solo son valores públicos. Para una demo, mantener modo `demo`.
3. Desde Actions → React web → Run workflow, seleccionar `main` y marcar `deploy`.
4. Revisar la URL devuelta por el job de Pages. El workflow no publica automáticamente en cada push; se despliega el build comprobado de esa ejecución manual.

Esta actualización prepara la publicación online. No habilita un proyecto Supabase ni cambia ajustes de Pages del propietario automáticamente. La sesión de preparación no ejecutó una publicación online ni prueba contra un Supabase real.

## API del kit real (v0.3)

El frontend estático conserva el build Vite. Para procesar el Excel plano y recalcular necesita además `server/app.py`, desplegado en el servicio Python del equipo o en la VM tras un proxy HTTPS. Solo requiere la librería ya usada por el traductor: openpyxl; no añade dependencias nativas.

Variables del servidor: `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `BOTATHON_ALLOWED_ORIGINS` (lista de orígenes exactos, separados por coma). El proceso debe usar un directorio `--data-dir` persistente, privado y respaldado. Sus JSON guardan borradores, parámetros y corridas de la VM; Supabase sigue guardando las revisiones y el plan aprobado. El token local va en archivo privado generado automáticamente.

Variable pública del build web: `VITE_CALC_API_URL=https://api-del-equipo.example`. Configurar también esa Repository Variable para el build de GitHub Actions. No usar una URL loopback como dirección de API para usuarios online: apuntaría al computador del visitante. En desarrollo, la URL se omite y Vite usa `/calc-api` con un proxy a la API local; el token se inyecta exclusivamente desde el servidor de desarrollo.

La API rechaza exposición directa fuera de loopback si no se configuró Supabase. Para exponer el servicio usar autenticación Supabase, origen permitido y proxy TLS. La infraestructura Windows/hosting y la configuración del proyecto Supabase deben verificarse en el entorno del equipo; esta entrega no publica automáticamente una API con acceso externo.
