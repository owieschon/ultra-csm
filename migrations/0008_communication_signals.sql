-- 0008_communication_signals.sql — communication_signal: durable store for
-- CommunicationSignal (Gmail email + Notion call transcripts, distinguished
-- by channel). Closes the same gap 0005 closed for InternalCommsNote:
-- FixtureCommsConnector's Gmail/call-transcript reads were in-memory-only
-- fixture data with no ingest destination. Follows the §3 conventions
-- verbatim, same as 0005/0006/0007: tenant_id NOT NULL, ENABLE + FORCE RLS
-- via the identical tenant_isolation policy (0002), app_runtime GRANT
-- (0002), and the single generic provenance trigger attached with its PK
-- column (0003).
--
-- contact_id is NOT NULL (matches CommunicationSignal.contact_id: str,
-- a required field in the dataclass -- every comms signal names a
-- specific customer contact, unlike comms_source_mapping's channel-level
-- attribution which has no single contact).
--
-- Immutable: applied once, in order, never edited in place.

CREATE TABLE communication_signal (
  signal_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL REFERENCES tenant,
  account_id           uuid NOT NULL REFERENCES account,
  contact_id           uuid NOT NULL REFERENCES contact,
  channel              text NOT NULL CHECK (channel IN ('email', 'call', 'meeting', 'chat')),
  direction            text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  message_ts           timestamptz NOT NULL,
  response_time_hours  double precision,
  attendees            text[] NOT NULL DEFAULT '{}',
  created_at           timestamptz NOT NULL DEFAULT app.clock(),
  row_version          int NOT NULL DEFAULT 1
);

-- (a) tenant_isolation: ENABLE + FORCE + the identical generic RLS policy (0002).
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['communication_signal'] LOOP
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %s '
      'USING (tenant_id = current_setting(''app.tenant_id'')::uuid) '
      'WITH CHECK (tenant_id = current_setting(''app.tenant_id'')::uuid)', t);
  END LOOP;
END $$;

-- (b) app_runtime GRANT (same DML grants as every other business table).
GRANT SELECT, INSERT, UPDATE, DELETE ON communication_signal TO app_runtime;

-- (c) provenance trigger attach with the table's PK column (0003 loop shape).
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM (VALUES
    ('communication_signal', 'signal_id')
  ) AS x(tbl, pk_cols) LOOP
    EXECUTE format(
      'CREATE TRIGGER provenance AFTER INSERT OR UPDATE OR DELETE ON %I '
      'FOR EACH ROW EXECUTE FUNCTION audit.log_change(%s)',
      r.tbl, r.pk_cols);
  END LOOP;
END $$;
