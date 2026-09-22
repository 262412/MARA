# MARA EACL 2027 Demo manuscript

This directory contains the EACL revision and preserves the original EMNLP source archive.

- source/main.tex: the EACL single-blind review entry point, with author names, line numbers, and page numbers.
- source/diagnostic_tables.tex: complete existing benchmark quality, operational, and paired-comparison tables.
- REVISION_STATUS_ZH.md: author decisions, issue-by-issue treatment, verified corrections, and remaining limitations.
- SUBMISSION_AUDIT_ZH.md: the initial preparation audit, retained as a dated baseline.
- submission/OPENREVIEW_FIELDS.md: copy-ready submission metadata and links; no form has been submitted.
- submission/ARTIFACT_GUIDE.md and REPRODUCTION.md: release/deployment instructions and analysis definitions.
- submission/mara-eacl2027-demo.pdf: generated submission PDF.
- submission/mara-eacl2027-source.zip: generated Overleaf/source package.
- submission/mara-eacl2027-supplement.zip: guides, reanalysis evidence, and the unchanged public benchmark bundle.
- submission/artifact-manifest.json: exported file sizes, SHA-256 checksums, and verified ZIP member lists.
- archive/emnlp-submitted-source.zip and archive/source-manifest.json: unchanged original source and hashes.
- audit/verification.json: original preparation checks; audit/revision-verification.json records the revised-paper checks.
- audit/revision-evidence.json: numerical reanalysis, including 360 aggregate cells and 14 paired/bootstrap comparisons.
- audit/release-bundle-check.json: local benchmark ZIP hash matches the official GitHub release asset digest.

The branch is codex/eacl-2027-demo, based on locally available origin/Dev commit adab3f4d8f221e3620494fab0a24ef8e5557d12a. It lives in a separate worktree and does not change the refactor checkout. No fetch was performed to characterize this base as the latest remote state.

The revision presents MARA as a workbench for observability and reproducible diagnosis, retains negative results, and makes no quality-superiority claim. Main content ends on page 5; the complete PDF is 11 pages. The author-confirmed 150-second original video is retained with explicit deployment/version distinctions. No new model runs, runtime code changes, dependency installs, video edits, or end-to-end installation tests were performed.

Generated PDFs and ZIPs are kept locally and ignored by Git. The source, guides, and verification records are versioned. LaTeX build logs and rendered page images are under ignored audit/build and audit/rendered directories.

The initial review inventory is based on the area-chair metareview and three reviews supplied by the author. Browser access was attempted but did not succeed; neither this revision nor the audit claims a successful direct OpenReview retrieval.
