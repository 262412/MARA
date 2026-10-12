# Reviewer follow-up: usefulness, verification, visual evidence, provenance

Date: 2026-09-23. Authorized scope: revise the paper and necessary evidence;
retain the existing video, authors, LMDoc name, and frozen historical records.

## Evidence and claim boundaries

- Compare the Harbor task with the actual raw-answer view. Do not infer improved
  user performance from additional exported fields or a static source comparison.
- Reproduce the recorded supported-policy rejection on the installed source
  commit e6afa5dc, then test a narrow fix in codex/lmdoc-verifier-repair.
  The original installer and historical benchmark are not changed.
- Retain all five predeclared before/after live pairs on the patched source,
  including failures, and compare verification on identical captured strings.
- Attempt a real public-chart case, retaining the image sent to the model,
  model response, route trace, and a generation-only image-removed control.
  A selected-page demonstration is not a learned-retrieval evaluation.
- Historical SlideVQA outputs remain missing locally. A failed read-only SSH
  access attempt does not establish that remote backups do not exist. Ask the
  author for alternate copies; never substitute new outputs for old ones.

## Verification and deliverables

Keep raw evidence separate from editorial summaries. Preserve the original
case and benchmark archive byte-for-byte. Supply a patch, runnable replay,
credential-free records, short comparison table, revised PDF, Overleaf source,
and supplementary ZIP. Compile and inspect the real final package; report
remaining scientific limits, without labeling them fully resolved.
