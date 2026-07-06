-- 0010_audit_event_log.sql -- append-only operational audit events.
--
-- Complements audit.change_log (row provenance) with product-level events the
-- ops surface needs to display without re-computing them from business state.
-- Immutable: applied once, in order, never edited in place.

CREATE TABLE audit.event_log (
  event_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id    uuid NOT NULL REFERENCES tenant,
  event_type   text NOT NULL,
  proposal_id  uuid REFERENCES action_proposal,
  account_ref  text,
  source_ref   text NOT NULL,
  detail       text NOT NULL,
  payload      jsonb NOT NULL DEFAULT '{}'::jsonb,
  ts           timestamptz NOT NULL DEFAULT app.clock(),
  UNIQUE (tenant_id, event_type, source_ref)
);

ALTER TABLE audit.event_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit.event_log FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON audit.event_log
  USING (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

GRANT SELECT, INSERT ON audit.event_log TO app_runtime;

CREATE FUNCTION audit.deny_event_log_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit.event_log is append-only (% rejected)', TG_OP
    USING errcode = 'check_violation';
END $$;

CREATE TRIGGER append_only
  BEFORE UPDATE OR DELETE ON audit.event_log
  FOR EACH ROW EXECUTE FUNCTION audit.deny_event_log_mutation();

CREATE TRIGGER append_only_truncate
  BEFORE TRUNCATE ON audit.event_log
  FOR EACH STATEMENT EXECUTE FUNCTION audit.deny_event_log_mutation();
