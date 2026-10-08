# Diagnostic case revision

## Authorized scope
Address the four review weaknesses: a complete verified diagnosis, a task-level
comparison with Kotaemon, inspectable raw outputs and effective execution
provenance, and diagnostic demonstration material. Keep the original video and
URL. Keep four authors and affiliation; remove the email as in the submitted PDF.

## Public surface
Paper, figures, supplementary evidence, and reviewer reproduction instructions.
The application and public CLI surface are not changed by this revision.
Work on `codex/eacl-diagnostic-case`, forked from `171ae066`, outside the primary
refactor checkout. Runtime data and model credentials stay outside Git.

## Evidence constraints
Keep the historical synthesis archive unchanged. Do not reconstruct missing
historical answer strings from metrics. Label any new case as a new deployment
case, not an addition to or reproduction of the historical benchmark. Distinguish
observed execution from static upstream inspection and proposed future work.

## Acceptance
- Traceable trigger, evidence, cause, intervention and observed outcome.
- Same diagnostic task mapped to upstream and MARA operations, with provenance.
- Self-contained case inputs, outputs, sanitized configuration, source identity
  and replay checks; explicit residual historical limitations.
- Compiled PDF within six content pages, visually inspected; fresh Overleaf ZIP
  and supplement, preserving the submitted original.
- No OpenReview submission or release mutation as part of this task.
