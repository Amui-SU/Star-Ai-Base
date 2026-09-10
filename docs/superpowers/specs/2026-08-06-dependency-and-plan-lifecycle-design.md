# Dependency And Plan Lifecycle Design

## Goal

Make a fresh frontend install report a healthy dependency tree without manual
cleanup, and make every implementation plan expose one unambiguous lifecycle
status.

## Frontend Dependency Contract

The repository keeps Node 22.13.1 and npm 10.9.2 as its canonical development
baseline. `.nvmrc`, the frontend `packageManager` field, and CI must agree on
that baseline, but local commands do not hard-fail on another already-supported
Node release. This avoids adding startup friction while giving developers and
automation one reproducible reference environment.

Sharp and the WASM-capable native toolchain leave three lockfile-resolved
optional packages at the installation root on Windows. Both npm 10 and npm 11
install them, and regenerating the lockfile does not remove them. The frontend
therefore declares the exact packages as optional dependencies:

- `@emnapi/runtime@1.11.1`
- `@img/sharp-wasm32@0.35.3`
- `@tybys/wasm-util@0.10.2`

This records what npm already installs instead of deleting dependency contents
after installation or teaching health checks to ignore extraneous packages.
The lockfile remains authoritative, and a fresh `npm ci` followed by
`npm ls --depth=0` is the acceptance test.

## Plan Lifecycle Contract

Every Markdown file in `docs/superpowers/plans/`, except the directory index,
must contain exactly one status near its title:

```markdown
**Status:** completed
```

Allowed values are `completed`, `partial`, `superseded`, and `planned`.

- `completed`: the planned behavior is present and integrated; historical
  checklist steps are marked complete.
- `partial`: some planned behavior is integrated, but an explicit remainder is
  still active.
- `superseded`: another named plan or current policy replaces this plan.
- `planned`: implementation has not started.

`docs/superpowers/plans/README.md` is the source-of-truth index. It records each
plan and its status, explains that the status field outranks illustrative plan
snippets, and identifies the newer plan when an entry is superseded.

The current audit found implementation evidence for every historical plan.
Twenty-seven plans are `completed`; the original micro-task fast-lane plan is
`superseded` by V2. Previously unchecked historical steps are marked complete
where commits and current tests prove integration.

## Automated Guards

Focused pytest contracts enforce both boundaries:

- the Node/npm baseline is represented consistently in `.nvmrc`, CI, and
  `frontend/package.json`;
- the three optional compatibility dependencies have exact versions in both
  the manifest and lockfile;
- every implementation plan has exactly one allowed status;
- every plan appears exactly once in the lifecycle index;
- completed plans have no unchecked checklist steps;
- superseded plans name their replacement.

The dependency change is verified with a disposable fresh install, frontend
tests, lint, build, workflow tests, and the repository's complete commit
verification. Documentation changes are additionally checked for formatting,
status/index consistency, and stale limitation text.

## Out Of Scope

- Changing application runtime behavior or production dependencies.
- Automatically deleting files from `node_modules` after install.
- Rewriting historical plan prose or code snippets that no longer match the
  latest implementation.
- Forcing developers off a currently supported Node release before running
  ordinary frontend commands.
