-- Close two action-boundary integrity gaps:
-- 1. An authorizing verdict must bind the authoritative proposal row's
--    current payload hash, never a caller-supplied snapshot.
-- 2. Idempotency reservations expose pending/completed/failed state so
--    simulated targets can reconcile and retry a crash-stranded attempt.

ALTER TABLE idempotency_keys
  ADD COLUMN state text,
  ADD COLUMN updated_at timestamptz,
  ADD COLUMN attempt_token text,
  ADD COLUMN lease_expires_at timestamptz;

-- Under the old schema, existence meant the operation had already been
-- handled. Preserve that meaning during an in-place upgrade; only new rows
-- default to pending.
UPDATE idempotency_keys
   SET state = 'completed', updated_at = created_at
 WHERE state IS NULL;

ALTER TABLE idempotency_keys
  ALTER COLUMN state SET DEFAULT 'pending',
  ALTER COLUMN state SET NOT NULL,
  ALTER COLUMN updated_at SET DEFAULT app.clock(),
  ALTER COLUMN updated_at SET NOT NULL,
  ADD CONSTRAINT idempotency_keys_state_check
    CHECK (state IN ('pending', 'completed', 'failed'));

CREATE OR REPLACE FUNCTION app.enforce_verdict_payload_binding()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  proposal_hash text;
  proposal_status text;
BEGIN
  IF NEW.approved_payload_sha256 IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT payload_sha256, status
    INTO proposal_hash, proposal_status
    FROM action_proposal
   WHERE proposal_id = NEW.proposal_id
     AND tenant_id = NEW.tenant_id;

  IF proposal_hash IS NULL
     OR proposal_status <> 'approved'
     OR NEW.approved_payload_sha256 IS DISTINCT FROM proposal_hash THEN
    RAISE EXCEPTION
      'approved verdict hash must match the current approved proposal payload'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER action_verdict_payload_binding
BEFORE INSERT OR UPDATE OF approved_payload_sha256, proposal_id, tenant_id
ON action_verdict
FOR EACH ROW EXECUTE FUNCTION app.enforce_verdict_payload_binding();
