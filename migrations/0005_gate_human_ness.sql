-- 0005_gate_human_ness.sql — DB-level defense-in-depth: for a tier>=2
-- action_verdict that AUTHORIZES a proposal (approved_payload_sha256 IS NOT
-- NULL -- gate.py's own 'approve'/'revise' paths, both of which set
-- status='approved'), the approving human_principal_id must reference a
-- principal with kind='human' and must differ from the proposal's own
-- actor_principal_id. Mirrors 0004_governance.sql's sod_confirm_authority
-- trigger style verbatim: a BEFORE trigger in the app schema, current_setting
-- read for context the caller cannot spoof via the row itself, RAISE with a
-- specific errcode, narrowly scoped to the one transition of concern so it
-- never fires on unrelated writes.
--
-- Deliberately does NOT fire on a 'deny' verdict, nor on the deny+supersede
-- path agent1/revise.py's reject_and_supersede uses (approved_payload_sha256
-- IS NULL there): neither authorizes anything, so there is no approving
-- principal to check -- see docs/PROGRAM_REPORT_40.md for the full scoping
-- rationale. Tier-1 auto_internal_only verdicts (autonomy_tier=1) are exempt
-- by construction: committers.py's auto_approve_internal legitimately
-- approves via a non-human system_principal_id, unchanged by this migration.
--
-- Immutable: applied once, in order, never edited in place.

CREATE FUNCTION app.enforce_verdict_human_approver() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_tier   int;
  v_actor  uuid;
  v_kind   text;
BEGIN
  -- Only guard verdicts that actually authorize something (deny, and the
  -- deny+supersede revise-loop path, never reach this check).
  IF NEW.approved_payload_sha256 IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT autonomy_tier, actor_principal_id INTO v_tier, v_actor
  FROM action_proposal WHERE proposal_id = NEW.proposal_id;

  -- Tier-1 auto_internal_only is the existing, correct non-human auto-approve
  -- path (committers.py::auto_approve_internal) -- out of scope by design.
  IF v_tier IS NULL OR v_tier < 2 THEN
    RETURN NEW;
  END IF;

  SELECT kind INTO v_kind FROM principal WHERE principal_id = NEW.human_principal_id;

  IF v_kind IS DISTINCT FROM 'human' THEN
    RAISE EXCEPTION
      'gate human-ness: approving principal % is not kind=human (tier %)',
      NEW.human_principal_id, v_tier
      USING errcode = 'insufficient_privilege';
  END IF;

  IF NEW.human_principal_id = v_actor THEN
    RAISE EXCEPTION
      'gate human-ness: approving principal % cannot be the proposal''s own actor (tier %)',
      NEW.human_principal_id, v_tier
      USING errcode = 'insufficient_privilege';
  END IF;

  RETURN NEW;
END $$;

-- BEFORE INSERT so the RAISE blocks the write before it commits (and before
-- the AFTER provenance trigger runs). action_verdict rows are only ever
-- inserted, never updated (UNIQUE(proposal_id) makes each verdict terminal).
CREATE TRIGGER gate_verdict_human_approver
  BEFORE INSERT ON action_verdict
  FOR EACH ROW EXECUTE FUNCTION app.enforce_verdict_human_approver();

GRANT EXECUTE ON FUNCTION app.enforce_verdict_human_approver() TO app_runtime;
