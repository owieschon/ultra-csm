-- 0011_workflow_packet.sql -- generic workflow packet persistence.
--
-- One table stores execution-envelope-backed workflow packets. Individual
-- workflows must not add one table/migration per packet type.

CREATE TABLE workflow_packet (
  tenant_id     uuid NOT NULL REFERENCES tenant,
  workflow_id   text NOT NULL,
  packet_id     text NOT NULL,
  account_id    text NOT NULL,
  subject_ref   text NOT NULL,
  status        text NOT NULL,
  payload       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT app.clock(),
  updated_at    timestamptz NOT NULL DEFAULT app.clock(),
  PRIMARY KEY (tenant_id, workflow_id, packet_id)
);

ALTER TABLE workflow_packet ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_packet FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON workflow_packet
  USING (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

GRANT SELECT, INSERT, UPDATE ON workflow_packet TO app_runtime;

CREATE TRIGGER provenance AFTER INSERT OR UPDATE OR DELETE ON workflow_packet
  FOR EACH ROW EXECUTE FUNCTION audit.log_change(tenant_id, workflow_id, packet_id);
