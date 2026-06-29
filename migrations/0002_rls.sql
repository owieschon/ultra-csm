-- 0002_rls.sql — FORCE row-level security + the NOSUPERUSER NOBYPASSRLS runtime
-- role. FORCE (not just ENABLE) is what protects app_runtime: ENABLE alone
-- exempts table owners, so the runtime would see every tenant. The seeded
-- superuser (bootstrap) intentionally bypasses RLS — that asymmetry is the proof.

-- Every business + governance table is tenant-keyed on tenant_id and gets the
-- identical isolation policy. change_log is keyed the same way (audit is per-tenant).
-- tenant.tenant_id IS the tenant key, so the generic policy below already scopes
-- it correctly (a principal only sees its own tenant row).
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'tenant', 'principal', 'grant_',
    'part', 'inventory', 'account', 'price_list', 'price_rule',
    'order_hdr', 'order_line', 'contact', 'interaction', 'idempotency_keys',
    'audit.change_log'
  ] LOOP
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %s '
      'USING (tenant_id = current_setting(''app.tenant_id'')::uuid) '
      'WITH CHECK (tenant_id = current_setting(''app.tenant_id'')::uuid)', t);
  END LOOP;
END $$;

-- role is a tenant-less global lookup (name UNIQUE); per-tenant membership lives
-- in grant_. FORCE RLS with an all-visible policy keeps it locked-down-by-default
-- yet readable, without a tenant_id it doesn't have.
ALTER TABLE role ENABLE ROW LEVEL SECURITY;
ALTER TABLE role FORCE ROW LEVEL SECURITY;
CREATE POLICY role_global ON role USING (true) WITH CHECK (true);

-- Runtime role: no password (trust auth on the unix socket), cannot bypass RLS.
CREATE ROLE app_runtime LOGIN NOSUPERUSER NOBYPASSRLS;

GRANT USAGE ON SCHEMA app, public, audit TO app_runtime;
GRANT EXECUTE ON FUNCTION app.clock() TO app_runtime;

GRANT SELECT, INSERT, UPDATE, DELETE ON
  tenant, principal, role, grant_,
  part, inventory, account, price_list, price_rule,
  order_hdr, order_line, contact, interaction, idempotency_keys
TO app_runtime;

-- Audit log is append-only for the runtime: it may write provenance and read it,
-- never rewrite history. (A trigger in 0003 enforces this even against owners.)
GRANT SELECT, INSERT ON audit.change_log TO app_runtime;
