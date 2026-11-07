# Configuración de Supabase

La integración está implementada en el código. No se ha creado ni modificado un proyecto real desde esta sesión; todavía se necesitan su URL, clave pública y usuarios.

## Preparación por el administrador

1. Crear o seleccionar el proyecto Supabase del equipo.
2. Aplicar en orden las migraciones de `supabase/migrations/` con el SQL Editor o el CLI de Supabase.
3. Crear/invitar usuarios desde Authentication. La web usa correo y contraseña, sin registro público. Completar la invitación y establecer la contraseña antes de entrar.
4. Dar de alta solo a las cuentas del equipo en `public.plan_members` mediante SQL administrativo. Ejemplo, sustituyendo el UUID por uno que ya exista en `auth.users`:

```sql
insert into public.plan_members(user_id, role)
values ('UUID-DEL-USUARIO', 'admin');
```

5. Copiar `.env.example` a `.env.local` y configurar:

```dotenv
VITE_DATA_MODE=supabase
VITE_SUPABASE_URL=https://TU-PROYECTO.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=TU-CLAVE-PUBLICA
```

Estas variables se incorporan al build y son visibles al navegador. Usar únicamente la clave **publishable** o **anon**, nunca una clave privada. La configuración rechaza claves privilegiadas tanto al construir como al iniciar. No compartir contraseñas ni claves privadas en el chat o repositorio. Después de cambiar variables en el hosting, reconstruir y desplegar.

La política de acceso depende de la sesión de Supabase Auth y RLS; conocer la clave pública no concede acceso a los datos. Cada usuario debe existir también en `plan_members`. Sin esa membresía, sus consultas no obtienen revisiones y las funciones de escritura rechazan la operación.

## Roles

| Rol | Consultar planes/logs | Cargar resultados | Aprobar/rechazar |
|---|---|---|---|
| viewer | Sí | No | No |
| editor | Sí | Sí | No |
| reviewer | Sí | No | Sí |
| admin | Sí | Sí | Sí |

La administración de membresías se hace desde Supabase con permisos de administrador del proyecto; no está expuesta en la web. Un admin de la aplicación puede cargar y aprobar su propia revisión en esta base; no se impone separación entre autor y aprobador para ese rol.

## Tablas y funciones

- `plan_members`: membresías y roles de acceso.
- `plan_revisions`: snapshots completos, huella, versión, autor y decisión. Los clientes autenticados no pueden insertar, modificar ni borrar filas directamente.
- `plan_publication`: referencia al último plan aprobado.
- `plan_audit_logs`: actividad registrada por las funciones; sin permiso de edición directa para clientes.
- `submit_plan_revision`: valida el JSON y registra una revisión pendiente, de forma idempotente.
- `review_plan_revision`: decide y, al aprobar, publica de forma atómica. Serializa aprobaciones y rechaza un retroceso de versión o una segunda decisión sobre una revisión resuelta.
- `record_plan_validation_failure`: registra rechazos detectados por el frontend. Un error al escribir el log se muestra explícitamente; no se simula éxito.

Las cuatro tablas tienen RLS; anon no puede leerlas. Todos los miembros autorizados pueden consultar la información nacional, incluidas revisiones pendientes/rechazadas y actividad del equipo. Las operaciones toman la identidad de `auth.uid()`, no del archivo. Los administradores de la base conservan sus privilegios fuera de la aplicación.

No se usa una clave de servicio en el frontend. Si más adelante Python envía revisiones automáticamente, el equipo debe definir su identidad y un canal autenticado de servidor: esta entrega no incorpora un secreto administrativo al bot.

## Demostración sin proyecto

Con `VITE_DATA_MODE=demo`, el repositorio simulado guarda revisiones en memoria y lo indica en pantalla. Recargar reinicia los datos; no es persistencia compartida y no escribe en Supabase. Si se selecciona `supabase` y falta configuración o falla la conexión, no se cambia silenciosamente a demo.

## Integración del cálculo del kit (v0.3)

Aplicar también `202611070002_calculation_parameters.sql`. Añade `plan_parameter_sets`, versiones de parámetros inmutables y su RPC de auditoría. Python valida las reglas; PostgreSQL controla acceso, inmutabilidad del identificador y registra la huella propia del contenido. Los clientes no modifican la tabla directamente.

La API necesita `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` en **el servidor**, además de las variables públicas del frontend. Para llamadas de la web, el JWT de su sesión se verifica contra Supabase y se reenvía a los RPC con esa identidad. Para Blue Prism bajo token local, configurar en el proceso servidor `BOTATHON_SUPABASE_ACCESS_TOKEN` con una sesión temporal de una cuenta editor/admin. Si no se configura, el resultado es solo `local_draft` y no se afirma que se publicó una revisión remota. Renovar la sesión al expirar; no poner ese JWT en el repo, argumentos de procesos ni logs.

El rol de editor guarda parámetros y crea revisiones; reviewer/admin aprueba en la web. La actualización local de un borrador de parámetros y su registro remoto no es una transacción distribuida: si un fallo de disco sucede después de registrarlo en Supabase, el administrador debe reconciliar el borrador de la VM. La aprobación del plan sí conserva su transacción PostgreSQL.
