# LMDoc EACL 2027 Demo manuscript

This directory contains the EACL revision and preserves the original EMNLP source archive.

The 23 September installation update replaces the public `slide-app.zip` with a tested Windows reviewer installer and updates the manuscript's quick-start instructions. The v0.0.40 source tag and benchmark bundle remain unchanged. See RELEASE_INSTALL_UPDATE_ZH.md for the new state; earlier dated audits below retain their historical findings.

- source/main.tex: the EACL single-blind review entry point, with author names, line numbers, and page numbers.
- source/diagnostic_tables.tex: complete existing benchmark quality, operational, and paired-comparison tables.
- REVISION_STATUS_ZH.md: author decisions, issue-by-issue treatment, verified corrections, and remaining limitations.
- REVIEWER_INSTALL_TEST_ZH.md: 23 September public-download and isolated Windows installation test; both README install paths failed and launch/index/query remain blocked.
- RELEASE_INSTALL_UPDATE_ZH.md: replacement installer publication, anonymous download verification, repeated historical-source failure, and rebuilt paper/Overleaf materials.
- SUBMISSION_AUDIT_ZH.md: the initial preparation audit, retained as a dated baseline.
- submission/OPENREVIEW_FIELDS.md: copy-ready submission metadata and links; no form has been submitted.
- submission/ARTIFACT_GUIDE.md and REPRODUCTION.md: release/deployment instructions and analysis definitions.
- submission/LMDoc-EACL2027.pdf: current paper.
- submission/LMDoc-EACL2027-Overleaf.zip: current upload project.
- submission/LMDoc-EACL2027-supplement.zip: current guides and diagnostic evidence.
- submission/diagnostic-artifact-manifest.json: current sizes and SHA-256 hashes.
- archive/emnlp-submitted-source.zip and archive/source-manifest.json: unchanged original source and hashes.
- audit/verification.json: original preparation checks; audit/revision-verification.json records the revised-paper checks.
- audit/revision-evidence.json: numerical reanalysis, including 360 aggregate cells and 14 paired/bootstrap comparisons.
- audit/release-bundle-check.json: local benchmark ZIP hash matches the official GitHub release asset digest.

The branch is codex/eacl-2027-demo, based on locally available origin/Dev commit adab3f4d8f221e3620494fab0a24ef8e5557d12a. It lives in a separate worktree and does not change the refactor checkout. No fetch was performed to characterize this base as the latest remote state.

The current revision keeps the negative historical results and narrows user-benefit claims. Table 1 compares observations from the same captured execution. Section 4 adds a verifier false-rejection repair and a real chart intervention with an image-removed control. The original video, case records and benchmark archive remain unchanged; a separate source patch and full follow-up records are included. See `DIAGNOSTIC_REVISION_ZH.md` and `reviewer_analysis.md` for evidence and remaining limits. The PDF preserves four authors and affiliation without email addresses.

Generated PDFs and ZIPs are kept locally and ignored by Git. The source, guides, and verification records are versioned. LaTeX build logs and rendered page images are under ignored audit/build and audit/rendered directories.

The initial review inventory is based on the area-chair metareview and three reviews supplied by the author. Browser access was attempted but did not succeed; neither this revision nor the audit claims a successful direct OpenReview retrieval.

The current paper name is LMDoc. Released software, video/screenshot labels, public command names, and historical evidence remain MARA. The paper and supplementary guide explicitly explain this identity; raw records are not relabelled. Earlier dated audit files preserve their historical terminology.
