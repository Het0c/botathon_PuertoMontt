-- Ejecutar una vez en el proyecto Supabase del equipo. Auth y usuarios los provee Supabase.
begin;

create table public.plan_members (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null check (role in ('viewer','editor','reviewer','admin'))
);
create table public.plan_revisions (
  id uuid primary key default gen_random_uuid(),
  version bigint generated always as identity unique,
  content_hash text not null unique,
  snapshot jsonb not null,
  source_label text not null,
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  submitted_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  reviewed_by uuid references auth.users(id),
  reviewed_at timestamptz,
  review_comment text
);
create table public.plan_publication (
  singleton boolean primary key default true check (singleton),
  revision_id uuid not null references public.plan_revisions(id),
  updated_at timestamptz not null default now()
);
create table public.plan_audit_logs (
  id bigint generated always as identity primary key,
  actor_id uuid not null references auth.users(id),
  operation text not null,
  revision_id uuid references public.plan_revisions(id),
  detail jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.plan_members enable row level security;
alter table public.plan_revisions enable row level security;
alter table public.plan_publication enable row level security;
alter table public.plan_audit_logs enable row level security;

create function public.is_plan_member() returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
  select exists(select 1 from public.plan_members where user_id = auth.uid());
$$;
revoke all on function public.is_plan_member() from public, anon;
grant execute on function public.is_plan_member() to authenticated;

create policy member_self on public.plan_members for select to authenticated using (user_id = auth.uid());
create policy revision_read on public.plan_revisions for select to authenticated using (public.is_plan_member());
create policy publication_read on public.plan_publication for select to authenticated using (public.is_plan_member());
create policy audit_read on public.plan_audit_logs for select to authenticated using (public.is_plan_member());
revoke all on public.plan_members, public.plan_revisions, public.plan_publication, public.plan_audit_logs from anon, authenticated;
grant select on public.plan_members, public.plan_revisions, public.plan_publication, public.plan_audit_logs to authenticated;

-- Validación del contrato también en servidor. No implementa limpieza ni cálculo de reglas.
create function public.validate_plan_payload(p jsonb) returns void language plpgsql
set search_path = public, pg_temp as $$
declare r jsonb; k text; v numeric; i integer := 0;
  strings text[] := array['professional_id','institute','area','role','month'];
  numbers text[] := array['contracted','direct','indirect','nas','absence','planned_direct','planned_indirect','planned','target'];
  fields text[] := array['professional_id','institute','area','role','month','contracted','direct','indirect','nas','absence','planned_direct','planned_indirect','planned','target','actual','foja'];
begin
  if jsonb_typeof(p) is distinct from 'object' then raise exception 'Se requiere un documento JSON'; end if;
  if exists(select 1 from jsonb_object_keys(p) x where x not in ('schema_version','year','parameters_version','rows')) then raise exception 'Campos de documento no soportados'; end if;
  if (p->'schema_version') is distinct from '1'::jsonb or (p->'year') is distinct from '2026'::jsonb then raise exception 'Esquema o año no soportado'; end if;
  if jsonb_typeof(p->'parameters_version') is distinct from 'string' or coalesce(length(btrim(p->>'parameters_version')),0) not between 1 and 120 then raise exception 'parameters_version requerido'; end if;
  if jsonb_typeof(p->'rows') is distinct from 'array' then raise exception 'rows debe ser una lista'; end if;
  if jsonb_array_length(p->'rows') not between 1 and 20000 or octet_length(p::text)>10485760 then raise exception 'Tamaño de revisión fuera de límite'; end if;
  for r in select value from jsonb_array_elements(p->'rows') loop
    i := i+1;
    if jsonb_typeof(r) is distinct from 'object' then raise exception 'Fila %: se requiere un objeto', i; end if;
    if not (r ?& fields) or exists(select 1 from jsonb_object_keys(r) x where not(x=any(fields))) then raise exception 'Fila %: columnas incompletas o no soportadas',i; end if;
    foreach k in array strings loop
      if jsonb_typeof(r->k) is distinct from 'string' or coalesce(length(btrim(r->>k)),0) not between 1 and 120 then raise exception 'Fila %: % requerido',i,k; end if;
    end loop;
    if (r->>'month') !~ '^2026-(0[1-9]|1[0-2])$' then raise exception 'Fila %: mes inválido',i; end if;
    foreach k in array numbers loop
      if jsonb_typeof(r->k) is distinct from 'number' then raise exception 'Fila %: % debe ser número',i,k; end if;
      v := (r->>k)::numeric;
      if v<0 or v>10000000 then raise exception 'Fila %: % fuera de rango',i,k; end if;
    end loop;
    foreach k in array array['planned_direct','planned_indirect','planned'] loop
      v := (r->>k)::numeric;
      if v <> trunc(v) then raise exception 'Fila %: % debe ser entero',i,k; end if;
    end loop;
    if (r->'actual') <> 'null'::jsonb then
      if jsonb_typeof(r->'actual') is distinct from 'number' then raise exception 'Fila %: actual debe ser entero o null',i; end if;
      v := (r->>'actual')::numeric;
      if v<0 or v>10000000 or v<>trunc(v) then raise exception 'Fila %: actual fuera de rango',i; end if;
    end if;
    if abs((r->>'contracted')::numeric-(r->>'direct')::numeric-(r->>'indirect')::numeric-(r->>'nas')::numeric-(r->>'absence')::numeric)>.01 then raise exception 'Fila %: horas no concilian',i; end if;
    if (r->>'planned')::numeric <> (r->>'planned_direct')::numeric+(r->>'planned_indirect')::numeric or (r->>'target')::numeric>(r->>'planned')::numeric then raise exception 'Fila %: atenciones o meta no concilian',i; end if;
    if (r->>'contracted')::numeric=0 then
      if (r->'foja') <> 'null'::jsonb then raise exception 'Fila %: FOJA debe ser null sin jornada',i; end if;
    else
      if jsonb_typeof(r->'foja') is distinct from 'number' then raise exception 'Fila %: FOJA requerido',i; end if;
      if abs((r->>'foja')::numeric-(r->>'direct')::numeric/(r->>'contracted')::numeric)>.0001 then raise exception 'Fila %: FOJA no concilia',i; end if;
    end if;
  end loop;
  if exists(select 1 from jsonb_array_elements(p->'rows') entry(value) group by entry.value->>'professional_id',entry.value->>'institute',entry.value->>'area',entry.value->>'role',entry.value->>'month' having count(*)>1) then raise exception 'Resultados mensuales duplicados'; end if;
end;
$$;
revoke all on function public.validate_plan_payload(jsonb) from public, anon, authenticated;

create function public.submit_plan_revision(p_payload jsonb, p_source_label text) returns jsonb
language plpgsql security definer set search_path=public,pg_temp as $$
declare membership text; h text; revision public.plan_revisions; created boolean := false;
begin
  select role into membership from public.plan_members where user_id=auth.uid();
  if coalesce(membership,'') not in ('editor','admin') then raise exception 'Tu rol no permite cargar revisiones' using errcode='42501'; end if;
  perform public.validate_plan_payload(p_payload);
  if coalesce(length(btrim(p_source_label)),0) not between 1 and 120 then raise exception 'Etiqueta de archivo requerida (máximo 120 caracteres)'; end if;
  h := encode(sha256(convert_to(p_payload::text,'UTF8')),'hex');
  insert into public.plan_revisions(content_hash,snapshot,source_label,submitted_by)
    values(h,p_payload,btrim(p_source_label),auth.uid()) on conflict(content_hash) do nothing returning * into revision;
  created := found;
  if not created then select * into revision from public.plan_revisions where content_hash=h; end if;
  if created then
    insert into public.plan_audit_logs(actor_id,operation,revision_id) values(auth.uid(),'revision_submitted',revision.id);
  end if;
  return to_jsonb(revision)-'snapshot'-'content_hash';
end;
$$;

create function public.review_plan_revision(p_revision_id uuid,p_decision text,p_comment text) returns void
language plpgsql security definer set search_path=public,pg_temp as $$
declare membership text; revision public.plan_revisions; active_version bigint;
begin
  select role into membership from public.plan_members where user_id=auth.uid();
  if coalesce(membership,'') not in ('reviewer','admin') then raise exception 'Tu rol no permite revisar planes' using errcode='42501'; end if;
  if p_decision is null or p_decision not in ('approved','rejected') then raise exception 'Decisión inválida'; end if;
  if coalesce(length(btrim(p_comment)),0) not between 1 and 2000 then raise exception 'Escribe una justificación de 1 a 2.000 caracteres'; end if;
  -- Serializa aprobaciones incluso antes de que exista el primer puntero publicado.
  perform pg_advisory_xact_lock(730026);
  select * into revision from public.plan_revisions where id=p_revision_id for update;
  if not found or revision.status <> 'pending' then raise exception 'La revisión ya fue resuelta o no existe'; end if;
  if p_decision='approved' then
    select r.version into active_version from public.plan_publication p join public.plan_revisions r on r.id=p.revision_id where p.singleton;
    if active_version is not null and active_version>=revision.version then raise exception 'No se puede publicar una versión anterior al plan vigente'; end if;
    insert into public.plan_publication(singleton,revision_id) values(true,revision.id)
      on conflict(singleton) do update set revision_id=excluded.revision_id,updated_at=now();
  end if;
  update public.plan_revisions set status=p_decision,reviewed_by=auth.uid(),reviewed_at=now(),review_comment=btrim(p_comment) where id=revision.id;
  insert into public.plan_audit_logs(actor_id,operation,revision_id,detail)
    values(auth.uid(),'revision_'||p_decision,revision.id,jsonb_build_object('comment',btrim(p_comment)));
end;
$$;

create function public.record_plan_validation_failure(p_errors jsonb) returns void
language plpgsql security definer set search_path=public,pg_temp as $$
declare membership text;
begin
  select role into membership from public.plan_members where user_id=auth.uid();
  if coalesce(membership,'') not in ('editor','admin') then raise exception 'Tu rol no permite registrar cargas' using errcode='42501'; end if;
  if jsonb_typeof(p_errors) is distinct from 'array' then raise exception 'Se requiere una lista de errores'; end if;
  if jsonb_array_length(p_errors) not between 1 and 100 or octet_length(p_errors::text)>32768 then raise exception 'Lista de errores fuera de límite'; end if;
  if exists(select 1 from jsonb_array_elements(p_errors) x where jsonb_typeof(x)<>'string') then raise exception 'Los errores deben ser textos'; end if;
  insert into public.plan_audit_logs(actor_id,operation,detail) values(auth.uid(),'validation_failed',jsonb_build_object('errors',p_errors));
end;
$$;

revoke all on function public.submit_plan_revision(jsonb,text), public.review_plan_revision(uuid,text,text), public.record_plan_validation_failure(jsonb) from public, anon;
grant execute on function public.submit_plan_revision(jsonb,text), public.review_plan_revision(uuid,text,text), public.record_plan_validation_failure(jsonb) to authenticated;
commit;
