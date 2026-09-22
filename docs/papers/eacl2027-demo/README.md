# MARA EACL 2027 Demo preparation

This directory preserves the author-supplied EMNLP source archive and records an
initial EACL submission audit. No manuscript revision has been applied.

- `SUBMISSION_AUDIT_ZH.md`: Chinese requirements audit, reviewer issue inventory,
  priorities, and proposed acceptance checks for later revision.
- `source/`: all 10 files extracted unchanged from the supplied ZIP.
- `archive/emnlp-submitted-source.zip`: unchanged copy of the original archive.
- `archive/source-manifest.json`: archive provenance and per-file SHA-256 hashes.
- `audit/verification.json`: results and limits of the checks performed here.
- `audit/build/`: ignored local LaTeX build outputs and logs.
- `audit/rendered/`: ignored local page images used for visual inspection.

The preparation branch is `codex/eacl-2027-demo`, based on the locally available
`origin/Dev` commit `adab3f4d8f221e3620494fab0a24ef8e5557d12a`. The separate
worktree preserves the primary checkout's refactor work and uncommitted changes.
No fetch was performed to assert that this base was the latest remote commit.

`source/main.tex` builds to 9 pages: 6 pages of main content, 1 page of references,
and 2 pages of appendices. It currently emits an incomplete conditional warning.
The other two entry points fail on the undefined `\Xiao` command. These existing
issues are recorded in the audit and deliberately left unchanged.

The review inventory is based on the area-chair metareview and three reviews
copied by the author into the conversation. Browser access was attempted but did
not succeed; this directory does not claim a direct OpenReview retrieval.

Keep the archive and its manifest as the original baseline when revising
`source/` later. The source attributes preserve its original line endings during
Git checkout; build products are kept outside that directory.
