begin;
create table public.plan_parameter_sets (
  version text primary key,
  parameters jsonb not null,
  content_hash text not null,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);
alter table public.plan_parameter_sets enable row level security;
create policy parameters_read on public.plan_parameter_sets for select to authenticated using (public.is_plan_member());
revoke all on public.plan_parameter_sets from anon,authenticated;
grant select on public.plan_parameter_sets to authenticated;
create function public.save_calculation_parameters(p_version text,p_parameters jsonb) returns void
language plpgsql security definer set search_path=public,pg_temp as $$
declare membership text; existing jsonb; h text;
begin
  select role into membership from public.plan_members where user_id=auth.uid();
  if coalesce(membership,'') not in ('editor','admin') then raise exception 'Tu rol no permite editar parámetros' using errcode='42501'; end if;
  if p_version is null or p_version !~ '^[a-f0-9]{64}$' then raise exception 'Versión de parámetros inválida'; end if;
  if jsonb_typeof(p_parameters) is distinct from 'object' then raise exception 'Se requiere objeto de parámetros'; end if;
  if not (p_parameters ?& array['Param_Generales','Param_Distribucion_Cargo','Param_Semanas_Habiles','politicas']) or octet_length(p_parameters::text)>4194304 then raise exception 'Parámetros incompletos o demasiado grandes'; end if;
  h:=encode(sha256(convert_to(p_parameters::text,'UTF8')),'hex');
  insert into public.plan_parameter_sets(version,parameters,content_hash,created_by) values(p_version,p_parameters,h,auth.uid()) on conflict(version) do nothing;
  select parameters into existing from public.plan_parameter_sets where version=p_version;
  if existing is distinct from p_parameters then raise exception 'Una versión de parámetros es inmutable'; end if;
  insert into public.plan_audit_logs(actor_id,operation,detail) values(auth.uid(),'parameters_selected',jsonb_build_object('version',p_version,'content_hash',h));
end;
$$;
revoke all on function public.save_calculation_parameters(text,jsonb) from public,anon;
grant execute on function public.save_calculation_parameters(text,jsonb) to authenticated;
commit;
