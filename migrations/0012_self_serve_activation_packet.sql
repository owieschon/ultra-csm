-- 0012_self_serve_activation_packet.sql -- persisted product-led activation packets.
--
-- Stores workflow 1b packets generated from self-serve signup/product events.
-- The payload carries the selected value path, milestone progress, evidence
-- receipts, suppression reasons, and ActionGate proposal refs.

CREATE TABLE self_serve_activation_packet (
  tenant_id    uuid NOT NULL REFERENCES tenant,
  packet_id    text NOT NULL,
  account_id   text NOT NULL,
  workspace_id text NOT NULL,
  signup_email text NOT NULL,
  status       text NOT NULL CHECK (status IN ('ready', 'needs_data', 'internal_only', 'ignored')),
  payload      jsonb NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT app.clock(),
  updated_at   timestamptz NOT NULL DEFAULT app.clock(),
  PRIMARY KEY (tenant_id, packet_id)
);

CREATE INDEX self_serve_activation_packet_account_idx
  ON self_serve_activation_packet (tenant_id, account_id, created_at DESC);

CREATE INDEX self_serve_activation_packet_workspace_idx
  ON self_serve_activation_packet (tenant_id, workspace_id, created_at DESC);

ALTER TABLE self_serve_activation_packet ENABLE ROW LEVEL SECURITY;
ALTER TABLE self_serve_activation_packet FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON self_serve_activation_packet
  USING (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

GRANT SELECT, INSERT, UPDATE ON self_serve_activation_packet TO app_runtime;

CREATE TRIGGER provenance
  AFTER INSERT OR UPDATE OR DELETE ON self_serve_activation_packet
  FOR EACH ROW EXECUTE FUNCTION audit.log_change(tenant_id, packet_id);
