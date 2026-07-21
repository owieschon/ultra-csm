# Hosted Action Control deployment runbook

<!-- sourcebound:purpose -->
This runbook deploys the rollback-isolated synthetic sandbox as a **separate
Vercel project**. It does not change the root static project's `vercel.json`,
and the generated bundle contains no main API, MCP, connector, UI, test, or
evaluation modules. No deployment or database has been provisioned by the
repository build itself.
<!-- sourcebound:end purpose -->
<!-- sourcebound:allow doc-length reason="Deployment, verification, rollback, and teardown are one operator sequence" -->

The bundle follows Vercel's current [FastAPI entrypoint
contract](https://vercel.com/docs/frameworks/backend/fastapi) and [Python
runtime bundle controls](https://vercel.com/docs/functions/runtimes/python).
Python 3.12 and every runtime package are pinned. The source allowlist is under
512 KiB, far below the current 500 MB uncompressed Python function limit.

## 1. Build and inspect locally

From the repository root:

```bash
make setup
make hosted-action-control-deploy-check
make hosted-action-control-bundle
git status --porcelain
```

The last command must be empty. The generated project root is
`build/hosted-action-control/`; its `.bundle-manifest.json` must exactly match
`deploy/hosted-action-control/manifest.json`.

Use a separate Vercel project name supplied by the operator. Do not run Vercel
commands from the repository root, because that root is the static UI project.
Pin the CLI and link only from the generated bundle:

```bash
export VERCEL_CLI_VERSION=55.0.0
export VERCEL_SCOPE='<team-or-user-scope>'
export SANDBOX_PROJECT='<separate-sandbox-project-name>'
cd build/hosted-action-control
npx --yes "vercel@${VERCEL_CLI_VERSION}" whoami
npx --yes "vercel@${VERCEL_CLI_VERSION}" link --yes \
  --scope "$VERCEL_SCOPE" --project "$SANDBOX_PROJECT"
cd ../..
```

Linking is an explicit operator action. Do not commit `.vercel/`; it remains
inside the ignored `build/` directory.

## 2. Prepare Neon without retaining admin credentials

Provision or select a Neon Postgres database using the Vercel Marketplace or
an existing Neon account. Choose a plan and region explicitly; this repository
does not assume a paid plan or promise that current quotas fit future traffic.

Neon recommends a [direct connection for migrations and a pooled connection
for serverless runtime](https://neon.com/docs/connect/connection-pooling). Prepare:

- a direct administrator DSN;
- a pooled DSN whose username is exactly `app_runtime` and whose new password
  is at least 24 characters.

Keep shell tracing disabled and enter both values silently. The bootstrap
script reads them only from process environment, never prints them, applies the
immutable migrations and seed, sets `app_runtime` to `LOGIN NOSUPERUSER
NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION`, limits it to ten
connections, and reconnects through the runtime DSN to verify the role.

```bash
set +x
read -r -s -p 'Direct admin DSN: ' ULTRA_CSM_DATABASE_ADMIN_URL; printf '\n'
read -r -s -p 'Pooled app_runtime DSN: ' ULTRA_CSM_DATABASE_URL; printf '\n'
export ULTRA_CSM_DATABASE_ADMIN_URL ULTRA_CSM_DATABASE_URL
PYTHONPATH=src:. .venv/bin/python scripts/bootstrap_hosted_action_control_db.py
unset ULTRA_CSM_DATABASE_ADMIN_URL
test -z "${ULTRA_CSM_DATABASE_ADMIN_URL:-}"
```

Do not add `ULTRA_CSM_DATABASE_ADMIN_URL` to Vercel. PostgreSQL documents why
[`NOBYPASSRLS` and non-superuser runtime roles](https://www.postgresql.org/docs/16/ddl-rowsecurity.html)
are required for enforced row security.

## 3. Configure only runtime values

Set the existing static UI's exact HTTPS origin—scheme and host, without a
path or wildcard. Production accepts exactly one origin. Add the runtime DSN as
a [sensitive production environment
variable](https://vercel.com/docs/environment-variables/sensitive-environment-variables)
without writing it to disk:

```bash
set +x
read -r -p 'Exact static UI origin (https://...): ' UI_ORIGIN
cd build/hosted-action-control
printf '%s' "$ULTRA_CSM_DATABASE_URL" | \
  npx --yes "vercel@${VERCEL_CLI_VERSION}" env add \
  ULTRA_CSM_DATABASE_URL production --sensitive
printf '%s' "$UI_ORIGIN" | \
  npx --yes "vercel@${VERCEL_CLI_VERSION}" env add \
  ULTRA_CSM_SANDBOX_ALLOWED_ORIGINS production
unset ULTRA_CSM_DATABASE_URL
npx --yes "vercel@${VERCEL_CLI_VERSION}" env ls production
cd ../..
```

Stop if the listing contains `ULTRA_CSM_DATABASE_ADMIN_URL`. Remove it before
building. Preview deployments must use a separate preview database/branch and
branch-scoped DSN; never point an untrusted preview at production data.

## 4. Build, deploy without aliasing, verify, then promote

Record the current production deployment first so rollback is unambiguous.
Use `env run` so production values are injected into the build process without
creating a local `.env` file. The deployment remains unaliased until its health
route succeeds through `vercel curl`, which preserves deployment protection.

```bash
cd build/hosted-action-control
npx --yes "vercel@${VERCEL_CLI_VERSION}" list
npx --yes "vercel@${VERCEL_CLI_VERSION}" env run -e production -- \
  npx --yes "vercel@${VERCEL_CLI_VERSION}" build --prod
DEPLOYMENT_URL="$(npx --yes "vercel@${VERCEL_CLI_VERSION}" deploy \
  --prebuilt --prod --skip-domain)"
npx --yes "vercel@${VERCEL_CLI_VERSION}" inspect "$DEPLOYMENT_URL"
npx --yes "vercel@${VERCEL_CLI_VERSION}" curl /health \
  --deployment "$DEPLOYMENT_URL"
npx --yes "vercel@${VERCEL_CLI_VERSION}" promote "$DEPLOYMENT_URL"
cd ../..
```

After promotion, set `SANDBOX_ORIGIN` to the promoted backend origin and run
the bounded live verifier. It checks the exact route set, exact CORS origin,
`no-store` on success and error responses, approve/commit/retry/tamper flow,
rollback isolation, and validation-error sanitization without printing bodies:

```bash
read -r -p 'Promoted sandbox origin (https://...): ' SANDBOX_ORIGIN
PYTHONPATH=src:. .venv/bin/python scripts/verify_hosted_action_control.py \
  --base-url "$SANDBOX_ORIGIN" --ui-origin "$UI_ORIGIN"
```

Only after that receipt is green, set the static UI project's
`NEXT_PUBLIC_ACTION_CONTROL_SANDBOX_API` to `SANDBOX_ORIGIN` and rebuild that
separate static project. This value is public configuration, not a credential.
The backend still exposes only health, FastAPI metadata, and the evaluator.

## 5. Rollback and credential removal

Vercel rollback re-points the production alias without rebuilding. From the
linked generated bundle:

```bash
cd build/hosted-action-control
npx --yes "vercel@${VERCEL_CLI_VERSION}" rollback '<known-good-deployment-url-or-id>'
npx --yes "vercel@${VERCEL_CLI_VERSION}" inspect '<restored-deployment-url-or-id>'
cd ../..
```

Migrations are checksum-bound and additive; application rollback does not run
down migrations. If this is the first sandbox release and no known-good backend
exists, remove `NEXT_PUBLIC_ACTION_CONTROL_SANDBOX_API` from the static project
and redeploy the read-only UI before removing the sandbox deployment.

For credential rotation, create a new `app_runtime` password/pooled DSN, rerun
the bootstrap verification, update the sensitive production variable, deploy a
new unaliased build, verify it, promote it, and then revoke the old password.
Never place the admin DSN in Vercel, a shell argument, a committed file, or a
support ticket.
