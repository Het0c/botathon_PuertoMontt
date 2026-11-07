# Build y despliegue web

El frontend es una SPA React + TypeScript + Vite. No necesita un proceso Python para servir sus páginas. Las pestañas son estado de React; no requiere reglas de reescritura para rutas internas. El build usa rutas relativas para poder publicarse en un subdirectorio.

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
