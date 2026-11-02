# Security operations — Phase 1

## 1. Rotate the database credential immediately

A database connection string was committed to the repository's deployment configuration.
Treat that credential as compromised even after removing it from the current branch.

1. Rotate/reset the PostgreSQL user password in the database provider dashboard.
2. Update the Render web service's `DATABASE_URL` environment variable with the newly issued connection string.
3. Redeploy and verify database connectivity and critical application flows.
4. Revoke the old credential. Do not reuse it.
5. Review Git history and deployment logs for any other exposed credentials. Removing a secret from the latest commit does not remove it from earlier Git history.

Do not paste credentials into issues, pull requests, chat, or source files.

## 2. Configure application secrets

- Keep `SECRET_KEY` in the Render environment. The application now refuses to start in production when it is missing or set to a development/test placeholder.
- Keep `DATABASE_URL`, payment secrets, OAuth secrets, and email credentials in the hosting provider's secret environment configuration.
- The committed Render blueprint intentionally declares `DATABASE_URL` as `sync: false`; configure it in the Render dashboard.

## 3. Initial administrator bootstrap

Admin creation is disabled by default. For a genuinely new database only:

1. Set `ADMIN_EMAIL` and a strong `ADMIN_PASSWORD` in the Render environment.
2. Set `ADMIN_BOOTSTRAP_ENABLED=true` and deploy once.
3. Confirm the administrator can sign in.
4. Immediately set `ADMIN_BOOTSTRAP_ENABLED=false` and redeploy.

The startup bootstrap no longer resets existing admin passwords or promotes an existing non-admin account. Use the normal controlled admin-management process for later account changes.

## 4. Password reset delivery

Password reset tokens and full reset URLs are no longer written to application logs. A transactional email provider is not currently configured in this repository, so password-reset email delivery remains a deployment prerequisite and must be implemented before advertising self-service password reset as available.
