-- 0011_enterprise_onboarding_packet.sql -- persisted enterprise onboarding packets.
--
-- Stores workflow 1a handoff/launch packets so the workbench can retrieve the
-- exact evidence, success-plan mechanics, proposals, and governance state that
-- were generated from a Closed Won trigger. Immutable migration.

CREATE TABLE enterprise_onboarding_packet (
  tenant_id      uuid NOT NULL REFERENCES tenant,
  packet_id      text NOT NULL,
  account_id     text NOT NULL,
  opportunity_id text NOT NULL,
  status         text NOT NULL CHECK (status IN ('ready', 'needs_data', 'ignored')),
  payload        jsonb NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT app.clock(),
  updated_at     timestamptz NOT NULL DEFAULT app.clock(),
  PRIMARY KEY (tenant_id, packet_id)
);

CREATE INDEX enterprise_onboarding_packet_account_idx
  ON enterprise_onboarding_packet (tenant_id, account_id, created_at DESC);

CREATE INDEX enterprise_onboarding_packet_opportunity_idx
  ON enterprise_onboarding_packet (tenant_id, opportunity_id, created_at DESC);

ALTER TABLE enterprise_onboarding_packet ENABLE ROW LEVEL SECURITY;
ALTER TABLE enterprise_onboarding_packet FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON enterprise_onboarding_packet
  USING (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

GRANT SELECT, INSERT, UPDATE ON enterprise_onboarding_packet TO app_runtime;

CREATE TRIGGER provenance
  AFTER INSERT OR UPDATE OR DELETE ON enterprise_onboarding_packet
  FOR EACH ROW EXECUTE FUNCTION audit.log_change(tenant_id, packet_id);
