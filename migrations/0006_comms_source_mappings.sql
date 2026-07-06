-- 0006_comms_source_mappings.sql — comms_source_mapping: confirmed
-- account attribution for identity-ambiguous external comms evidence
-- (Notion meeting transcripts, Slack channels). Follows the §3
-- conventions verbatim, same as 0004/0005: tenant_id NOT NULL, ENABLE +
-- FORCE RLS via the identical tenant_isolation policy (0002), app_runtime
-- GRANT (0002), and the single generic provenance trigger attached with
-- its PK column (0003). No bespoke audit columns.
--
-- One row per confirmed external-identifier -> account attribution.
-- Never auto-populated: a human (confirmed_by) must confirm it (see
-- notion_call_transcripts.py/slack_reader.py's propose-then-confirm
-- discipline -- this table IS the persisted "confirm" half of that split).
-- contact_id is nullable: meaningful for a notion_meeting attendee, not
-- applicable to a slack_channel mapping (a channel maps to an account,
-- not a specific customer contact).
--
-- Immutable: applied once, in order, never edited in place.

CREATE TABLE comms_source_mapping (
  mapping_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenant,
  source_type   text NOT NULL CHECK (source_type IN ('notion_meeting', 'slack_channel')),
  external_id   text NOT NULL,
  account_id    uuid NOT NULL REFERENCES account,
  contact_id    uuid REFERENCES contact,
  confirmed_by  uuid NOT NULL REFERENCES principal,
  confirmed_at  timestamptz NOT NULL DEFAULT app.clock(),
  row_version   int NOT NULL DEFAULT 1,
  UNIQUE (tenant_id, source_type, external_id)
);

-- (a) tenant_isolation: ENABLE + FORCE + the identical generic RLS policy (0002).
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['comms_source_mapping'] LOOP
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %s '
      'USING (tenant_id = current_setting(''app.tenant_id'')::uuid) '
      'WITH CHECK (tenant_id = current_setting(''app.tenant_id'')::uuid)', t);
  END LOOP;
END $$;

-- (b) app_runtime GRANT (same DML grants as every other business table).
GRANT SELECT, INSERT, UPDATE, DELETE ON comms_source_mapping TO app_runtime;

-- (c) provenance trigger attach with the table's PK column (0003 loop shape).
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM (VALUES
    ('comms_source_mapping', 'mapping_id')
  ) AS x(tbl, pk_cols) LOOP
    EXECUTE format(
      'CREATE TRIGGER provenance AFTER INSERT OR UPDATE OR DELETE ON %I '
      'FOR EACH ROW EXECUTE FUNCTION audit.log_change(%s)',
      r.tbl, r.pk_cols);
  END LOOP;
END $$;
