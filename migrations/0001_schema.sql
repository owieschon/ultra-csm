-- 0001_schema.sql — full E2 schema (tables, app/audit schemas, logical clock).
-- Money is integer cents (BIGINT *_cents). Every business row carries
-- tenant_id, and every mutable business row carries row_version + timestamps.
-- Immutable: migrations are applied once, in order, never edited in place.

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid for runtime rows

-- ---------------------------------------------------------------------------
-- app schema: the identity/clock seam that RLS and the provenance trigger read
-- ---------------------------------------------------------------------------
CREATE SCHEMA app;

-- Injectable logical clock. Seed/eval set app.now to a fixed instant so audit
-- timestamps are byte-deterministic; runtime leaves it unset and falls to now().
CREATE FUNCTION app.clock() RETURNS timestamptz
LANGUAGE sql STABLE AS $$
  SELECT coalesce(nullif(current_setting('app.now', true), '')::timestamptz, now())
$$;

-- ---------------------------------------------------------------------------
-- audit schema: the single append-only provenance substrate
-- ---------------------------------------------------------------------------
CREATE SCHEMA audit;

CREATE TABLE audit.change_log (
  change_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id          uuid NOT NULL,
  table_name         text NOT NULL,
  row_pk             jsonb NOT NULL,
  op                 char(1) NOT NULL CHECK (op IN ('I', 'U', 'D')),
  before             jsonb,
  after              jsonb,
  actor_principal_id uuid NOT NULL,
  actor_kind         text NOT NULL,
  cause_ref          text,
  request_id         text,
  turn_id            text,
  model_id           text,        -- AI lineage (SOC2-for-AI evidence)
  prompt_version     text,
  ts                 timestamptz NOT NULL DEFAULT app.clock()
);

-- ---------------------------------------------------------------------------
-- Governance overlays
-- ---------------------------------------------------------------------------
CREATE TABLE tenant (
  tenant_id  uuid PRIMARY KEY,
  name       text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT app.clock()
);

-- Agents are first-class principals (amendment 17): same RBAC shape as humans.
CREATE TABLE principal (
  principal_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL REFERENCES tenant,
  kind         text NOT NULL CHECK (kind IN ('human', 'agent')),
  display_name text NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT app.clock()
);

CREATE TABLE role (
  role_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name    text NOT NULL UNIQUE
);

-- grant_ (GRANT is reserved): principal↔role assignment, tenant-scoped.
CREATE TABLE grant_ (
  principal_id uuid NOT NULL REFERENCES principal,
  role_id      uuid NOT NULL REFERENCES role,
  tenant_id    uuid NOT NULL,
  PRIMARY KEY (principal_id, role_id)
);

-- ---------------------------------------------------------------------------
-- ERP
-- ---------------------------------------------------------------------------
CREATE TABLE part (
  tenant_id   uuid NOT NULL REFERENCES tenant,
  sku         text NOT NULL,
  description text,
  family      text,
  status      text NOT NULL DEFAULT 'active'
              CHECK (status IN ('active', 'discontinued', 'superseded')),
  uom         text,
  created_at  timestamptz NOT NULL DEFAULT app.clock(),
  updated_at  timestamptz NOT NULL DEFAULT app.clock(),
  row_version int NOT NULL DEFAULT 1,
  PRIMARY KEY (tenant_id, sku)
);

CREATE TABLE inventory (
  tenant_id      uuid NOT NULL,
  sku            text NOT NULL,
  qty_on_hand    int NOT NULL DEFAULT 0,
  committed_qty  int NOT NULL DEFAULT 0,   -- ATP: available = on_hand - committed
  location       text,
  lead_time_days int,                      -- NULL iff in stock
  updated_at     timestamptz NOT NULL DEFAULT app.clock(),
  row_version    int NOT NULL DEFAULT 1,
  PRIMARY KEY (tenant_id, sku),
  FOREIGN KEY (tenant_id, sku) REFERENCES part (tenant_id, sku)
);

CREATE TABLE account (
  account_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid NOT NULL REFERENCES tenant,
  name              text NOT NULL,
  payment_terms     text,
  pricing_tier      text,
  credit_status     text,
  credit_limit_cents BIGINT NOT NULL DEFAULT 0,
  created_at        timestamptz NOT NULL DEFAULT app.clock(),
  updated_at        timestamptz NOT NULL DEFAULT app.clock(),
  row_version       int NOT NULL DEFAULT 1
);

CREATE TABLE price_list (
  price_list_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenant,
  tier          text NOT NULL
);

-- Effective-dated pricing: the honest basis for "price valid on the order date".
CREATE TABLE price_rule (
  price_rule_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  price_list_id    uuid NOT NULL REFERENCES price_list,
  sku              text NOT NULL,
  min_qty          int NOT NULL DEFAULT 1,
  unit_price_cents BIGINT NOT NULL,
  valid_from       timestamptz NOT NULL,
  valid_to         timestamptz          -- NULL = open-ended
);

CREATE TABLE order_hdr (
  order_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id          uuid NOT NULL REFERENCES tenant,
  account_id         uuid NOT NULL REFERENCES account,
  status             text NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft', 'confirmed', 'cancelled', 'escalated')),
  currency           text NOT NULL DEFAULT 'USD',
  subtotal_cents     BIGINT NOT NULL DEFAULT 0,
  total_cents        BIGINT NOT NULL DEFAULT 0,
  confirm_token_hash text,             -- system-issued; never an LLM "yes"
  created_at         timestamptz NOT NULL DEFAULT app.clock(),
  updated_at         timestamptz NOT NULL DEFAULT app.clock(),
  confirmed_at       timestamptz,
  row_version        int NOT NULL DEFAULT 1
);

CREATE TABLE order_line (
  order_id         uuid NOT NULL REFERENCES order_hdr,
  line_no          int NOT NULL,
  tenant_id        uuid NOT NULL,
  sku              text NOT NULL,
  qty              int NOT NULL,
  unit_price_cents BIGINT NOT NULL,
  extended_cents   BIGINT NOT NULL,
  price_as_of      timestamptz NOT NULL,  -- price snapshot frozen onto the line
  ship_status      text NOT NULL DEFAULT 'pending',
  PRIMARY KEY (order_id, line_no)
);

-- ---------------------------------------------------------------------------
-- CRM
-- ---------------------------------------------------------------------------
CREATE TABLE contact (
  contact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  uuid NOT NULL REFERENCES tenant,
  account_id uuid NOT NULL REFERENCES account,
  email      text NOT NULL,
  name       text,
  role       text,
  consent    boolean NOT NULL DEFAULT false,  -- TCPA
  created_at timestamptz NOT NULL DEFAULT app.clock(),
  updated_at timestamptz NOT NULL DEFAULT app.clock(),
  row_version int NOT NULL DEFAULT 1,
  UNIQUE (tenant_id, email)
);

CREATE TABLE interaction (
  interaction_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL REFERENCES tenant,
  account_id     uuid NOT NULL,
  contact_id     uuid,
  channel        text,
  direction      text,
  summary        text,
  ts             timestamptz NOT NULL DEFAULT app.clock()
);

-- PII field tags (crypto-shred-compatible erasure later; data-governance seam).
COMMENT ON COLUMN contact.email IS 'pii';
COMMENT ON COLUMN contact.name IS 'pii';
COMMENT ON COLUMN interaction.summary IS 'pii';

-- Write contract: idempotency key on the single mutation path.
CREATE TABLE idempotency_keys (
  tenant_id  uuid NOT NULL,
  idem_key   text NOT NULL,
  request_id text,
  result_ref text,
  created_at timestamptz NOT NULL DEFAULT app.clock(),
  PRIMARY KEY (tenant_id, idem_key)
);
