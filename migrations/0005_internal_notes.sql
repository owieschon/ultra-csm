-- 0005_internal_notes.sql — internal_note: CSM-authored + Slack-sourced
-- internal account commentary (never customer-facing). Follows the §3
-- conventions verbatim, same as 0004: tenant_id NOT NULL, ENABLE + FORCE
-- RLS via the identical tenant_isolation policy (0002), app_runtime GRANT
-- (0002), and the single generic provenance trigger attached with its PK
-- column (0003). No bespoke audit columns — every mutation lands in
-- audit.change_log through the existing mechanism.
--
-- ``author`` is plain text, not a principal_id FK: a Slack-sourced note's
-- author is an external Slack identity with no corresponding ``principal``
-- row, so this column must uniformly hold a display string for both
-- sources rather than a foreign key only one of them can satisfy.
--
-- Immutable: applied once, in order, never edited in place.

CREATE TABLE internal_note (
  note_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid NOT NULL REFERENCES tenant,
  account_id  uuid NOT NULL REFERENCES account,
  author      text NOT NULL,
  content     text NOT NULL,
  source      text NOT NULL DEFAULT 'csm_note'
              CHECK (source IN ('csm_note', 'slack')),
  created_at  timestamptz NOT NULL DEFAULT app.clock(),
  updated_at  timestamptz NOT NULL DEFAULT app.clock(),
  row_version int NOT NULL DEFAULT 1
);

-- (a) tenant_isolation: ENABLE + FORCE + the identical generic RLS policy (0002).
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['internal_note'] LOOP
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %s '
      'USING (tenant_id = current_setting(''app.tenant_id'')::uuid) '
      'WITH CHECK (tenant_id = current_setting(''app.tenant_id'')::uuid)', t);
  END LOOP;
END $$;

-- (b) app_runtime GRANT (same DML grants as every other business table).
GRANT SELECT, INSERT, UPDATE, DELETE ON internal_note TO app_runtime;

-- (c) provenance trigger attach with the table's PK column (0003 loop shape).
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM (VALUES
    ('internal_note', 'note_id')
  ) AS x(tbl, pk_cols) LOOP
    EXECUTE format(
      'CREATE TRIGGER provenance AFTER INSERT OR UPDATE OR DELETE ON %I '
      'FOR EACH ROW EXECUTE FUNCTION audit.log_change(%s)',
      r.tbl, r.pk_cols);
  END LOOP;
END $$;
