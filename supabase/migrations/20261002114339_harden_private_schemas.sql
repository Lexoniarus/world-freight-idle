-- The browser never accesses these application schemas directly. Keep them
-- private at the privilege boundary and enable RLS as defense in depth. The
-- backend login role owns these tables and has BYPASSRLS.
revoke all privileges on schema game from public, anon, authenticated;
revoke all privileges on schema world_catalogue from public, anon, authenticated;
revoke all privileges on schema vehicle_catalogue from public, anon, authenticated;

revoke all privileges on all tables in schema game from public, anon, authenticated;
revoke all privileges on all tables in schema world_catalogue from public, anon, authenticated;
revoke all privileges on all tables in schema vehicle_catalogue from public, anon, authenticated;

revoke all privileges on all sequences in schema game from public, anon, authenticated;
revoke all privileges on all sequences in schema world_catalogue from public, anon, authenticated;
revoke all privileges on all sequences in schema vehicle_catalogue from public, anon, authenticated;

revoke all privileges on all functions in schema game from public, anon, authenticated;
revoke all privileges on all functions in schema world_catalogue from public, anon, authenticated;
revoke all privileges on all functions in schema vehicle_catalogue from public, anon, authenticated;

alter default privileges in schema game
    revoke all privileges on tables from public, anon, authenticated;
alter default privileges in schema world_catalogue
    revoke all privileges on tables from public, anon, authenticated;
alter default privileges in schema vehicle_catalogue
    revoke all privileges on tables from public, anon, authenticated;

alter default privileges in schema game
    revoke all privileges on sequences from public, anon, authenticated;
alter default privileges in schema world_catalogue
    revoke all privileges on sequences from public, anon, authenticated;
alter default privileges in schema vehicle_catalogue
    revoke all privileges on sequences from public, anon, authenticated;

alter default privileges in schema game
    revoke all privileges on functions from public, anon, authenticated;
alter default privileges in schema world_catalogue
    revoke all privileges on functions from public, anon, authenticated;
alter default privileges in schema vehicle_catalogue
    revoke all privileges on functions from public, anon, authenticated;

do $$
declare
    application_table record;
begin
    for application_table in
        select schemaname, tablename
        from pg_tables
        where schemaname in (
            'game',
            'world_catalogue',
            'vehicle_catalogue'
        )
    loop
        execute format(
            'alter table %I.%I enable row level security',
            application_table.schemaname,
            application_table.tablename
        );
    end loop;
end
$$;

-- These are the mutable runtime foreign-key columns that are not already the
-- leading columns of another index. Catalogue tables are immutable and small;
-- adding every advisory index there would increase storage and write work
-- without supporting a measured runtime query.
create index if not exists market_offer_templates_template_id_idx
    on game.market_offer_templates (template_id);
create index if not exists market_template_uses_template_id_idx
    on game.market_template_uses (template_id);
create index if not exists sessions_user_id_idx
    on game.sessions (user_id);
