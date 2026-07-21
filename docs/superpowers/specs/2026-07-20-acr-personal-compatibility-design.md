# ACR Personal Edition Compatibility Design

## Goal

Allow the existing single-server image deployment workflow to use an Alibaba
Cloud ACR Personal Edition instance in Beijing while preserving the existing
SHA-based deployment, health checks, backups, and rollback behavior.

Personal Edition remains a deliberate availability trade-off: Alibaba Cloud
documents it as development/test only, with no SLA. The runbook must state this
clearly and must not describe Personal Edition as equivalent to Enterprise
Edition.

## Selected Approach

Use a strict ACR endpoint allowlist instead of accepting an arbitrary registry.
The production preflight will accept:

- Enterprise Edition public endpoints:
  `<instance>-registry.cn-beijing.cr.aliyuncs.com`
- New Personal Edition public endpoints:
  `crpi-<instance>.cn-beijing.personal.cr.aliyuncs.com`
- Legacy Personal Edition public endpoints:
  `registry.cn-beijing.aliyuncs.com`

Endpoints from other regions, VPC-only endpoints, placeholders, URLs with a
scheme or path, and unrelated registries remain invalid.

Alternatives considered:

1. Accept any syntactically valid registry. This is smaller but weakens the
   deployment contract and can silently route production credentials elsewhere.
2. Deploy images exclusively by OCI digest. This gives stronger immutability on
   Personal Edition but requires separate backend/frontend digest state and a
   larger change to Compose, publication metadata, rollback, and recovery.

The strict allowlist is selected because it addresses the current constraint
without broadening the registry trust boundary or redesigning deployment state.

## Publication Safety

The GitHub workflow continues to:

- build only the missing SHA-tagged backend or frontend image;
- never overwrite an already present SHA tag;
- verify `org.opencontainers.image.revision` against the tested commit;
- promote `latest` only when the tested commit is still current;
- keep production deployment independent of `latest`.

Enterprise repositories should still enable immutable image versions. Personal
Edition cannot rely on that repository-side control, so its compensating
controls are:

- use a dedicated push credential in GitHub Actions;
- use a separate pull-only credential on ECS where the edition permits;
- do not manually push, retag, or delete 40-character SHA tags;
- keep the current and previous images locally on ECS;
- retain the existing pre-pull-before-downtime and rollback behavior.

The workflow step names and diagnostics will refer to SHA tags rather than
claiming they are repository-enforced immutable tags.

## Configuration And Documentation

`deploy/.env.deploy.example` will use a Personal Edition Beijing endpoint
placeholder because that is the selected deployment target. The production
runbook will document both supported editions, the Personal Edition limitations,
the new and legacy endpoint formats, explicit `docker login`, and the absence
of an SLA or immutable-tag guarantee.

Historical design and implementation-plan documents remain unchanged because
they describe the decisions at the time they were written. The active runbook,
examples, tests, and runtime preflight form the current operational contract.

## Testing

Behavior tests will prove that:

- valid Enterprise, new Personal, and legacy Personal Beijing endpoints pass;
- Personal endpoints from another region and VPC endpoints fail;
- placeholders and arbitrary registries fail;
- deploy and restore continue to share the same read-only preflight;
- workflow checks and revision verification remain ordered before `latest`;
- the runbook states Personal Edition limitations and compensating controls.

The focused deployment and workflow tests, Bash syntax checks, Compose config,
and the full backend/frontend suites will run before integration.
