-- 0003_provenance.sql — the single generic per-change provenance mechanism.
-- ONE AFTER I/U/D trigger on every business table writes ONE change_log row,
-- reading who/cause from the app.* GUCs. Mutation without provenance is
-- impossible: a missing app.actor_id RAISEs. NOT security definer — the trigger
-- runs as the mutating role, so RLS still applies to its change_log INSERT.

CREATE FUNCTION audit.log_change() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_actor uuid := nullif(current_setting('app.actor_id', true), '')::uuid;
  v_pk    jsonb := '{}'::jsonb;
  v_src   jsonb := to_jsonb(coalesce(NEW, OLD));  -- the surviving row image
  col     text;
BEGIN
  IF v_actor IS NULL THEN
    -- Fail-closed: the connection factory should set this, but the DB is the
    -- backstop. No actor → no mutation.
    RAISE EXCEPTION 'provenance: app.actor_id must be set before mutating %', TG_TABLE_NAME
      USING errcode = 'check_violation';
  END IF;

  -- Build the PK image from the column names passed as trigger args.
  FOREACH col IN ARRAY TG_ARGV LOOP
    v_pk := v_pk || jsonb_build_object(col, v_src -> col);
  END LOOP;

  INSERT INTO audit.change_log (
    tenant_id, table_name, row_pk, op, before, after,
    actor_principal_id, actor_kind, cause_ref,
    request_id, turn_id, model_id, prompt_version, ts
  ) VALUES (
    current_setting('app.tenant_id')::uuid,
    TG_TABLE_NAME,
    v_pk,
    left(TG_OP, 1),
    CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN to_jsonb(OLD) END,
    CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN to_jsonb(NEW) END,
    v_actor,
    coalesce(nullif(current_setting('app.actor_kind', true), ''), 'agent'),
    nullif(current_setting('app.cause_ref', true), ''),
    nullif(current_setting('app.request_id', true), ''),
    nullif(current_setting('app.turn_id', true), ''),
    nullif(current_setting('app.model_id', true), ''),
    nullif(current_setting('app.prompt_version', true), ''),
    app.clock()
  );
  RETURN NULL;  -- AFTER trigger: return value ignored
END $$;

-- Attach to every business table, passing that table's PK column names as args.
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM (VALUES
    ('tenant',           'tenant_id'),
    ('principal',        'principal_id'),
    ('role',             'role_id'),
    ('grant_',           'principal_id, role_id'),
    ('part',             'tenant_id, sku'),
    ('inventory',        'tenant_id, sku'),
    ('account',          'account_id'),
    ('price_list',       'price_list_id'),
    ('price_rule',       'price_rule_id'),
    ('order_hdr',        'order_id'),
    ('order_line',       'order_id, line_no'),
    ('contact',          'contact_id'),
    ('interaction',      'interaction_id'),
    ('idempotency_keys', 'tenant_id, idem_key')
  ) AS x(tbl, pk_cols) LOOP
    EXECUTE format(
      'CREATE TRIGGER provenance AFTER INSERT OR UPDATE OR DELETE ON %I '
      'FOR EACH ROW EXECUTE FUNCTION audit.log_change(%s)',
      r.tbl, r.pk_cols);
  END LOOP;
END $$;

-- change_log immutability: append-only even for owners. REVOKE alone is not
-- enough (owners/superuser keep rights), so a BEFORE U/D trigger is the floor.
CREATE FUNCTION audit.deny_change_log_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit.change_log is append-only (% rejected)', TG_OP
    USING errcode = 'check_violation';
END $$;

CREATE TRIGGER append_only
  BEFORE UPDATE OR DELETE ON audit.change_log
  FOR EACH ROW EXECUTE FUNCTION audit.deny_change_log_mutation();
