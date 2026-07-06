-- 0009_safety_backstops.sql -- DB-level safety backstops for the action gate.
-- Adds two hard checks beneath the Python gate:
--
-- 1. action_proposal.payload_sha256 must equal the canonical SHA-256 of the
--    stored payload. This closes direct-SQL or future-caller gaps around the
--    anti-TOCTOU binding.
-- 2. An authorizing verdict for draft_customer_outreach must reference a
--    consented contact ref in the proposal payload. REST/MCP already check
--    this at the edge; this trigger makes the invariant fail-closed in the DB
--    without assuming every connected CRM id is a local UUID.
--
-- Immutable: applied once, in order, never edited in place.

CREATE FUNCTION app.canonical_jsonb(value jsonb) RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT CASE jsonb_typeof(value)
    WHEN 'object' THEN
      COALESCE(
        (
          SELECT '{' || string_agg(
            to_jsonb(key)::text || ':' || app.canonical_jsonb(val),
            ',' ORDER BY key
          ) || '}'
          FROM jsonb_each(value) AS e(key, val)
        ),
        '{}'
      )
    WHEN 'array' THEN
      COALESCE(
        (
          SELECT '[' || string_agg(
            app.canonical_jsonb(elem),
            ',' ORDER BY ord
          ) || ']'
          FROM jsonb_array_elements(value) WITH ORDINALITY AS a(elem, ord)
        ),
        '[]'
      )
    WHEN 'string' THEN value::text
    WHEN 'number' THEN value::text
    WHEN 'boolean' THEN value::text
    WHEN 'null' THEN 'null'
    ELSE value::text
  END
$$;

CREATE FUNCTION app.canonical_payload_sha256(payload jsonb) RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT encode(digest(app.canonical_jsonb(payload), 'sha256'), 'hex')
$$;

CREATE FUNCTION app.enforce_action_proposal_payload_hash() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_expected text := app.canonical_payload_sha256(NEW.payload);
BEGIN
  IF NEW.payload_sha256 IS DISTINCT FROM v_expected THEN
    RAISE EXCEPTION
      'payload hash mismatch for action_proposal %: expected %, got %',
      COALESCE(NEW.proposal_id::text, '<new>'), v_expected, NEW.payload_sha256
      USING errcode = 'check_violation';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER action_proposal_payload_hash
  BEFORE INSERT OR UPDATE OF payload, payload_sha256 ON action_proposal
  FOR EACH ROW EXECUTE FUNCTION app.enforce_action_proposal_payload_hash();

-- Text-keyed mirror of the contact/account consent fact used by customer
-- outreach proposals. The source ids are external-system refs by design
-- (Salesforce/Rocketlane/Gmail/sim fixtures do not all share the local UUID
-- business tables), while tenant_id keeps RLS/provenance identical to the rest
-- of the governance plane.
CREATE TABLE outreach_contact_consent_ref (
  tenant_id   uuid NOT NULL REFERENCES tenant,
  account_ref text NOT NULL,
  contact_ref text NOT NULL,
  email       text,
  name        text,
  consent     boolean NOT NULL DEFAULT false,
  observed_at timestamptz NOT NULL DEFAULT app.clock(),
  PRIMARY KEY (tenant_id, account_ref, contact_ref)
);

ALTER TABLE outreach_contact_consent_ref ENABLE ROW LEVEL SECURITY;
ALTER TABLE outreach_contact_consent_ref FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON outreach_contact_consent_ref
  USING (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON outreach_contact_consent_ref TO app_runtime;

CREATE TRIGGER provenance
  AFTER INSERT OR UPDATE OR DELETE ON outreach_contact_consent_ref
  FOR EACH ROW EXECUTE FUNCTION audit.log_change('tenant_id', 'account_ref', 'contact_ref');

CREATE FUNCTION app.enforce_outreach_verdict_contact_consent() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_action text;
  v_payload jsonb;
  v_contact_ref text;
  v_account_ref text;
  v_ok boolean;
BEGIN
  -- Deny and deny+supersede verdicts authorize nothing.
  IF NEW.approved_payload_sha256 IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT action, payload INTO v_action, v_payload
  FROM action_proposal
  WHERE proposal_id = NEW.proposal_id;

  IF v_action IS DISTINCT FROM 'draft_customer_outreach' THEN
    RETURN NEW;
  END IF;

  IF v_payload ? 'contact_id' IS FALSE THEN
    RAISE EXCEPTION
      'outreach consent: draft_customer_outreach proposal % lacks contact_id',
      NEW.proposal_id
      USING errcode = 'check_violation';
  END IF;

  IF v_payload ? 'account_id' IS FALSE THEN
    RAISE EXCEPTION
      'outreach consent: draft_customer_outreach proposal % lacks account_id',
      NEW.proposal_id
      USING errcode = 'check_violation';
  END IF;

  v_contact_ref := nullif(v_payload ->> 'contact_id', '');
  v_account_ref := nullif(v_payload ->> 'account_id', '');
  IF v_contact_ref IS NULL OR v_account_ref IS NULL THEN
    RAISE EXCEPTION
      'outreach consent: proposal % has blank contact/account ref',
      NEW.proposal_id
      USING errcode = 'check_violation';
  END IF;

  SELECT EXISTS (
    SELECT 1
    FROM outreach_contact_consent_ref r
    WHERE r.tenant_id = NEW.tenant_id
      AND r.account_ref = v_account_ref
      AND r.contact_ref = v_contact_ref
      AND r.consent IS TRUE
  ) INTO v_ok;

  IF NOT v_ok THEN
    RAISE EXCEPTION
      'outreach consent: contact ref % is not consented for proposal %',
      v_contact_ref, NEW.proposal_id
      USING errcode = 'insufficient_privilege';
  END IF;

  RETURN NEW;
END $$;

CREATE TRIGGER gate_outreach_verdict_contact_consent
  BEFORE INSERT ON action_verdict
  FOR EACH ROW EXECUTE FUNCTION app.enforce_outreach_verdict_contact_consent();

GRANT EXECUTE ON FUNCTION app.canonical_jsonb(jsonb) TO app_runtime;
GRANT EXECUTE ON FUNCTION app.canonical_payload_sha256(jsonb) TO app_runtime;
GRANT EXECUTE ON FUNCTION app.enforce_action_proposal_payload_hash() TO app_runtime;
GRANT EXECUTE ON FUNCTION app.enforce_outreach_verdict_contact_consent() TO app_runtime;
