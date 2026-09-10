# Dependency Audit Exceptions

This register documents temporary dependency-security exceptions. CI blocks
high-severity findings in both the production dependency audit and the full
dependency audit.

## Active exceptions

None.

## Closed exceptions

### GHSA-mh99-v99m-4gvg

- Status: closed
- Closed: 2026-08-22
- Former affected path: `eslint -> minimatch@3.1.5 -> brace-expansion@1.1.16`
- Resolution: the lockfile now resolves patched `brace-expansion` releases
  `1.1.18` and `5.0.9`. `npm audit --audit-level=high` exits successfully, so
  the full dependency audit is blocking in CI.
