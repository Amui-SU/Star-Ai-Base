# ACR Attestation Compatibility Design

**Approval:** User confirmed the in-chat design on 2026-09-10.

## Problem and evidence

PR 7 merged as `9228693785d5ac0ee668535bc98a0d545b77d7a3` and its main CI passed.
[Publish Images run 34475921680](https://github.com/Amui-SU/Star-Ai-Base/actions/runs/34475921680)
used BuildKit v0.32.2 and provenance mode=max. Backend compilation succeeded,
but ACR rejected the attestation config media type
`application/vnd.oci.empty.v1+json`. Frontend publication and revision checks
were skipped; this SHA is not an accepted release.

BuildKit 0.32 defaults to OCI artifact attestations. Its
[versioned storage documentation](https://github.com/moby/buildkit/blob/v0.32.2/docs/attestations/attestation-storage.md)
documents `oci-artifact=false` as the legacy attestation image-manifest format.
This changes storage, not the provenance statement contents.

## Approved change

Both build-push steps explicitly set
`outputs: type=image,oci-mediatypes=true,oci-artifact=false` while retaining
`push: true`, SHA tags, and index revision annotations. Preserve the existing
provenance generation; do not set provenance=false or disable default attestations.
The explicit OCI media types preserve the existing index annotation contract.
No BuildKit downgrade, registry migration, or new credentials are needed.

## Boundaries and verification

- Modify only the publish workflow, its focused regression tests, and documentation.
- Test parsed build-action exporter inputs independently for backend and frontend.
  Removing the compatibility attribute from either step must fail its case.
- Existing tests continue to guard SHA-only builds, no-overwrite behavior,
  revision verification, freshness, and manual-only deployment.
- Run complete repository verification and normal commit hooks.
- Publish through the reviewed GitHub workflow after CI, never by local pushes
  to ACR. Only a successful two-image publication and revision check accepts a release.
- Never overwrite or delete the failed SHA's tags to make a retry pass.
- No ECS access, production deployment, secret changes, or permission changes.

## Alternatives

Disabling provenance removes useful build evidence and is outside the approved
solution. Downgrading BuildKit merely postpones the compatibility issue.
Updating the registry is a separate infrastructure decision. Use the explicit
exporter compatibility setting first; if ACR still rejects it, inspect the new
error and stop before expanding scope.
