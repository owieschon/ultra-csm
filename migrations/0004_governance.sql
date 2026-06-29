-- 0004_governance.sql — the agent-first governance plane (ARCHITECTURE §8, §10b;
-- design/governance_and_learning.md Part 1). Adds the RBAC permission layer
-- (permission / role_permission), externalized versioned config (policy /
-- policy_binding), the principal↔skill link (agent_skill), and the universal
-- approve/deny/revise gate (action_proposal / action_verdict).
--
-- Every new business table follows the §3 conventions verbatim: tenant_id NOT
-- NULL, ENABLE + FORCE RLS via the identical tenant_isolation policy (0002),
-- app_runtime GRANT (0002), and the single generic provenance trigger attached
-- with its PK columns (0003). No bespoke audit columns — every config/gate
-- mutation lands in audit.change_log through the existing mechanism.
--
-- Immutable: applied once, in order, never edited in place.

-- ---------------------------------------------------------------------------
-- 1.1 — RBAC permission layer (role + grant_ already exist in 0001)
-- ---------------------------------------------------------------------------

-- permission: a verb-on-resource capability the autonomy gate checks by lookup.
CREATE TABLE permission (
  permission_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenant,
  name          text NOT NULL,        -- e.g. 'order.confirm', 'email.send'
  description   text,
  created_at    timestamptz NOT NULL DEFAULT app.clock(),
  UNIQUE (tenant_id, name)
);

-- role_permission: roles aggregate permissions (tenant-scoped membership).
CREATE TABLE role_permission (
  role_id       uuid NOT NULL REFERENCES role,
  permission_id uuid NOT NULL REFERENCES permission,
  tenant_id     uuid NOT NULL REFERENCES tenant,
  PRIMARY KEY (role_id, permission_id)
);

-- policy: externalized, versioned config the deterministic gate reads. The
-- rule_to_follow / pattern_to_avoid kinds are the dreaming loop's adoption
-- target (Part 2). Authored by humans (or an approved dream), never by an LLM
-- at runtime.
CREATE TABLE policy (
  policy_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   uuid NOT NULL REFERENCES tenant,
  name        text NOT NULL,
  policy_kind text NOT NULL
              CHECK (policy_kind IN ('autonomy_tier','rule_to_follow','pattern_to_avoid')),
  body        jsonb NOT NULL,
  version     int  NOT NULL DEFAULT 1,
  source      text NOT NULL DEFAULT 'human'
              CHECK (source IN ('human','dream')),
  source_ref  text,                   -- learning_candidate id when source='dream'
  active      boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT app.clock(),
  updated_at  timestamptz NOT NULL DEFAULT app.clock(),
  row_version int NOT NULL DEFAULT 1,
  UNIQUE (tenant_id, name, version)
);

-- policy_binding: which principals a policy version governs.
CREATE TABLE policy_binding (
  policy_id    uuid NOT NULL REFERENCES policy,
  principal_id uuid NOT NULL REFERENCES principal,
  tenant_id    uuid NOT NULL REFERENCES tenant,
  PRIMARY KEY (policy_id, principal_id)
);

-- agent_skill: principal ↔ skill bundle, id-linked to the live beta.skills
-- mirror. The Postgres row is the system-of-record; live_skill_id is NULL
-- offline and set only when the live lane provisions.
CREATE TABLE agent_skill (
  principal_id       uuid NOT NULL REFERENCES principal,
  skill_name         text NOT NULL,
  tenant_id          uuid NOT NULL REFERENCES tenant,
  live_skill_id      text,            -- beta.skills id (NULL offline)
  live_skill_version int,
  created_at         timestamptz NOT NULL DEFAULT app.clock(),
  PRIMARY KEY (principal_id, skill_name)
);

-- Live-lane mirror ids on the agent principal (NULL offline; set on provision).
ALTER TABLE principal
  ADD COLUMN live_agent_id      text,
  ADD COLUMN live_agent_version int;

-- ---------------------------------------------------------------------------
-- 1.2 — the universal approve/deny/revise gate
-- ---------------------------------------------------------------------------

-- action_proposal: every real-world-affecting action emits one. payload_sha256
-- binds the action body (anti-TOCTOU). state machine: pending → {approved|denied};
-- a revise verdict moves it to approved while atomically updating payload+hash.
CREATE TABLE action_proposal (
  proposal_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL REFERENCES tenant,
  actor_principal_id  uuid NOT NULL REFERENCES principal,  -- the proposing agent
  case_id             uuid,                 -- flywheel parent on the Case object
  intent              text NOT NULL,        -- e.g. 'confirm_order','send_email'
  action              text NOT NULL,        -- the typed-service method / outbound verb
  payload             jsonb NOT NULL,       -- the proposed action body
  payload_sha256      text NOT NULL,        -- anti-TOCTOU binding
  grounding_ref       text,                 -- value-ledger / surfaced_values provenance
  autonomy_tier       int  NOT NULL CHECK (autonomy_tier IN (1,2,3)),
  required_permission text NOT NULL,        -- permission.name the actor must hold
  status              text NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','approved','denied')),
  request_id          text,
  turn_id             text,
  created_ts          timestamptz NOT NULL DEFAULT app.clock(),
  updated_at          timestamptz NOT NULL DEFAULT app.clock(),
  row_version         int NOT NULL DEFAULT 1
);

-- action_verdict: the human (or fixture) approve/deny/revise decision. One
-- terminal verdict per proposal (UNIQUE → idempotent under retry / double-post).
-- approved_payload_sha256 records exactly what the verdict authorized to commit.
CREATE TABLE action_verdict (
  verdict_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id               uuid NOT NULL REFERENCES tenant,
  proposal_id             uuid NOT NULL REFERENCES action_proposal,
  verdict                 text NOT NULL CHECK (verdict IN ('approve','deny','revise')),
  revised_payload         jsonb,           -- present iff verdict='revise'
  approved_payload_sha256 text,            -- what this verdict authorized to commit
  rationale               text,
  human_principal_id      uuid NOT NULL REFERENCES principal,  -- the human (or fixture)
  decided_ts              timestamptz NOT NULL DEFAULT app.clock(),
  UNIQUE (proposal_id)
);

-- ---------------------------------------------------------------------------
-- Registration into the three existing platform loops (no new mechanism).
-- ---------------------------------------------------------------------------

-- (a) tenant_isolation: ENABLE + FORCE + the identical generic RLS policy (0002).
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'permission', 'role_permission', 'policy', 'policy_binding',
    'agent_skill', 'action_proposal', 'action_verdict'
  ] LOOP
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', t);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %s '
      'USING (tenant_id = current_setting(''app.tenant_id'')::uuid) '
      'WITH CHECK (tenant_id = current_setting(''app.tenant_id'')::uuid)', t);
  END LOOP;
END $$;

-- (b) app_runtime GRANT (same DML grants as the 0002 business tables).
GRANT SELECT, INSERT, UPDATE, DELETE ON
  permission, role_permission, policy, policy_binding,
  agent_skill, action_proposal, action_verdict
TO app_runtime;

-- (c) provenance trigger attach with each table's PK columns (0003 loop shape).
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM (VALUES
    ('permission',      'permission_id'),
    ('role_permission', 'role_id, permission_id'),
    ('policy',          'policy_id'),
    ('policy_binding',  'policy_id, principal_id'),
    ('agent_skill',     'principal_id, skill_name'),
    ('action_proposal', 'proposal_id'),
    ('action_verdict',  'verdict_id')
  ) AS x(tbl, pk_cols) LOOP
    EXECUTE format(
      'CREATE TRIGGER provenance AFTER INSERT OR UPDATE OR DELETE ON %I '
      'FOR EACH ROW EXECUTE FUNCTION audit.log_change(%s)',
      r.tbl, r.pk_cols);
  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- DB-level SoD policy (defense-in-depth for drafter ≠ confirmer).
-- order_hdr's transition INTO status='confirmed' is permitted ONLY to a
-- principal whose roles (via grant_ → role_permission → permission) hold
-- 'order.confirm'. This is independent of the typed service: even a direct SQL
-- UPDATE that flips status to 'confirmed' RAISEs unless the acting principal
-- (app.actor_id) carries the permission. The cs-orchestrator principal does NOT
-- hold it; only the order-confirm-authority role does (seeded by the governance
-- authorizer). Fail-closed: unset actor already RAISEs in the provenance trigger.
-- ---------------------------------------------------------------------------
CREATE FUNCTION app.enforce_confirm_authority() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_actor uuid := nullif(current_setting('app.actor_id', true), '')::uuid;
  v_ok    boolean;
BEGIN
  -- Only guard the draft→confirmed transition; other edits are unaffected.
  IF NEW.status = 'confirmed' AND OLD.status IS DISTINCT FROM 'confirmed' THEN
    IF v_actor IS NULL THEN
      RAISE EXCEPTION 'confirm authority: app.actor_id must be set'
        USING errcode = 'check_violation';
    END IF;
    SELECT EXISTS (
      SELECT 1
      FROM grant_ g
      JOIN role_permission rp ON rp.role_id = g.role_id
      JOIN permission p       ON p.permission_id = rp.permission_id
      WHERE g.principal_id = v_actor
        AND p.name = 'order.confirm'
    ) INTO v_ok;
    IF NOT v_ok THEN
      RAISE EXCEPTION
        'separation of duties: principal % lacks order.confirm', v_actor
        USING errcode = 'insufficient_privilege';
    END IF;
  END IF;
  RETURN NEW;
END $$;

-- BEFORE UPDATE so the RAISE blocks the write before it commits (and before the
-- AFTER provenance trigger runs). Fires on every order_hdr UPDATE; the body
-- short-circuits unless the row is moving into 'confirmed'.
CREATE TRIGGER sod_confirm_authority
  BEFORE UPDATE ON order_hdr
  FOR EACH ROW EXECUTE FUNCTION app.enforce_confirm_authority();

GRANT EXECUTE ON FUNCTION app.enforce_confirm_authority() TO app_runtime;
