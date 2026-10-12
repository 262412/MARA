# Refactor boundaries and remaining limits

Current setup and dependency versions are defined by the [README](../../README.md),
package metadata, and `uv.lock`. The primary runtime uses Python 3.11 and the
updated dependency stack. Historical candidate reviews describe their frozen
inputs; they are not the current installation status.

## Responsibilities and verification

The [architecture contracts](architecture-contracts.md) identify the owners of
CLI inspection, DocQA policies, Chat event/rendering services, Desktop launch,
MCP operations/sessions, and deck export. Preserve their public aliases,
patch points, persisted identities, and lazy dependency boundaries.

Run the affected checks in [Contributing](contributing.md) and the
[hygiene contract](codebase-hygiene-contract.md). Source tests, installed-wheel
checks, native Desktop packages, model-backed workflows, security scans, and
release acceptance establish different things. Record results against the
actual input and platform in the pull request or CI run.

## Dependency compatibility

- MARA messages are separate from native LangChain message classes. Exchange
  them through `to_langchain_message` / `from_langchain_message` in
  `kotaemon.base.message_adapters`; do not rely on native `isinstance` or
  `issubclass` identity. Internal `doc_id` and provider message `id` are separate.
- `kotaemon.agents.openai.OpenAIAgent` supports the chat/streaming adapter.
  The removed third-party import `llama_index.agent.openai.OpenAIAgent` and
  advanced AgentRunner task/step APIs require caller migration.
- Inside a running event loop, use `achat` / `astream_chat`. Synchronous chat
  methods reject that context before starting work.
- PDF navigation uses proven one-based physical positions, separately from
  display labels. Old references without a trustworthy position stay unresolved;
  parser policy changes invalidate incompatible cache entries instead of guessing.
- Existing vector data requires the explicit Qdrant migration and verification
  workflow described in the README. Changing a directory or embedding setting
  alone does not migrate an index.

## Remaining acceptance limits

- Web event ordering, rAF timing, natural login, and the earlier U1 browser
  matrix need their own acceptance. A sequential document QA smoke does not
  close every event-order or concurrency case.
- Cache, source-lock, Notebook, artifact, and download services retain their
  tested process boundaries. Atomic replacement alone does not establish
  cross-process serialization or rollback across independent stores.
- Native Windows lacks some POSIX `dir_fd`, `fcntl`, and FIFO operations;
  symlink tests also depend on the user's privileges. Refusal contracts and
  permission-limited tests remain distinct from successful file publication.
  Preview-cache keys use Windows DPAPI; that does not implement every
  artifact/export backend.
- Desktop feature scope and native installer requirements are maintained in the
  [feature matrix](../desktop/feature-parity-matrix.md) and
  [release plan](../desktop/release-and-acceptance-plan.md). Shared profiles do
  not imply automatic migration or validated concurrent writes to one session.
- Historical protection incidents retain their original OPEN, UNKNOWN, or
  UNVERIFIED dispositions. Later isolated runs cannot establish a blanket
  historical protection pass. Model quality and research claims follow the
  [evaluation protocol](project-status/evaluation-protocol.md).
- Security and release decisions require current scans and platform evidence;
  old package/test passes do not retire later findings or authorize a release.

## Historical review reference

The S1-4E candidate review remains available in its
[review Page](https://chatgpt.com/space/page_716504448bcc8191a8d960d87fa307e8).
Its frozen manifest is
`9db01fe6f58ac04594547dc2c4d0969f7cad5e63bc9f65fe91ce477b17fd7f53`;
its patch is `859d12cbd4d6fa555321faa7ae3adfcae4f62e69c17ccbd3c01c092aa2639d04`.
The original failures, identity assertions, and platform limits belong to that
candidate. The earlier per-stage narratives are recoverable from Git history;
raw fixtures, manifests, licenses, and paper evidence retain their own roles.
