-- 0013_adoption_regression_packet.sql -- persisted adoption regression packets.
--
-- Stores ongoing account-usage regression packets generated from product
-- observability triggers. Payload carries metric-window comparisons, value-model
-- context, interpretation alternatives, suppression reasons, and ActionGate refs.

CREATE TABLE adoption_regression_packet (
  tenant_id   uuid NOT NULL REFERENCES tenant,
  packet_id   text NOT NULL,
  account_id  text NOT NULL,
  metric_name text NOT NULL,
  status      text NOT NULL CHECK (status IN ('ready', 'needs_data', 'internal_only', 'ignored')),
  payload     jsonb NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT app.clock(),
  updated_at  timestamptz NOT NULL DEFAULT app.clock(),
  PRIMARY KEY (tenant_id, packet_id)
);

CREATE INDEX adoption_regression_packet_account_idx
  ON adoption_regression_packet (tenant_id, account_id, created_at DESC);

CREATE INDEX adoption_regression_packet_metric_idx
  ON adoption_regression_packet (tenant_id, metric_name, created_at DESC);

ALTER TABLE adoption_regression_packet ENABLE ROW LEVEL SECURITY;
ALTER TABLE adoption_regression_packet FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON adoption_regression_packet
  USING (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

GRANT SELECT, INSERT, UPDATE ON adoption_regression_packet TO app_runtime;

CREATE TRIGGER provenance
  AFTER INSERT OR UPDATE OR DELETE ON adoption_regression_packet
  FOR EACH ROW EXECUTE FUNCTION audit.log_change(tenant_id, packet_id);
