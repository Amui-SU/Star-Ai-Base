# Dependency Audit Exceptions

This register documents temporary dependency-security exceptions. Production
dependencies remain subject to the blocking CI command
`npm audit --omit=dev --audit-level=high`.

## GHSA-mh99-v99m-4gvg

- Status: active, development-only
- Affected path: `eslint -> minimatch@3.1.5 -> brace-expansion@1.1.16`
- Exposure: denial of service in local or CI lint processing; the dependency is
  omitted from the production dependency audit and production application image.
- Reason for exception: the first patched `brace-expansion` release is 5.0.8,
  while the current ESLint 9 plugin chain requires the incompatible 1.x API.
  `npm audit fix --force` would start an incomplete ESLint 10 migration.
- Mitigations: CI uses read-only repository permissions, a 30-minute job timeout,
  a blocking production audit, and a visible non-blocking full audit. User-provided
  values must not be used to construct lint glob patterns.
- Review no later than: 2026-08-11
- Removal criteria: remove this exception when a compatible patched 1.x release
  exists, or when ESLint and all Next.js lint plugins support a safe minimatch and
  brace-expansion chain. The full `npm audit --audit-level=high` command must then
  exit successfully before the exception is closed.
