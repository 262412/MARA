# Data & Data Structure Components

The data & data structure components include:

- The `Document` class.
- The document store.
- The vector store.

## Data Loader

- PdfLoader
- Layout-aware with table parsing PdfLoader

  - MathPixLoader: To use this loader, you need MathPix API key, refer to [mathpix docs](https://docs.mathpix.com/#introduction) for more information
  - OCRLoader: This loader uses lib-table and Flax pipeline to perform OCR and read table structure from PDF file (TODO: add more info about deployment of this module).
  - Output:

    - Document: text + metadata to identify whether it is table or not

      ```
      - "source": source file name
      - "type": "table" or "text"
      - "table_origin": original table in markdown format (to be feed to LLM or visualize using external tools)
      - "page_label": page number in the original PDF document
      ```

## Document Store

- InMemoryDocumentStore

## Vector Store

- QdrantVectorStore (default, shared Qdrant service)
- InMemoryVectorStore
- ChromaVectorStore (legacy migration environment only)

The default store connects to `http://127.0.0.1:6333`. Web and CLI processes use
the same service and namespace, so they can access an index concurrently.
It preserves MARA string document IDs, document payloads, source scopes, deletion,
and the former Chroma L2 score `exp(-squared_distance)`. Configure
`MARA_QDRANT_URL`, `MARA_QDRANT_API_KEY`, and optionally `MARA_QDRANT_NAMESPACE`.
The default namespace is derived from the resolved `user_data` path. Preserve the
namespace explicitly when moving that directory. Separate app data directories
must have separate namespaces. `user_data/vectorstore_qdrant` holds the migration
receipt; server data belongs in Qdrant's own persistent storage directory.

Run Qdrant 1.19.2 or newer separately before starting MARA. Earlier servers are
rejected because 1.19.2 fixes
[GHSA-3gph-6c29-p29v](https://github.com/qdrant/qdrant/security/advisories/GHSA-3gph-6c29-p29v).
The
[official installation guide](https://qdrant.tech/documentation/operations/installation/)
describes server deployments. For a native server, save a `qdrant.yaml` file:

```yaml
telemetry_disabled: true
service:
  host: 127.0.0.1
  http_port: 6333
  grpc_port: 6334
storage:
  storage_path: /absolute/persistent/qdrant/storage
  snapshots_path: /absolute/persistent/qdrant/snapshots
```

Set `QDRANT__SERVICE__API_KEY` in the server environment and the matching
`MARA_QDRANT_API_KEY` in MARA, then run `qdrant --config-path qdrant.yaml`.
Use a short absolute storage path for the native Windows server. Production
storage should follow Qdrant's Linux/POSIX filesystem requirements. For a remote
service, use HTTPS and restrict network access to the MARA hosts. A MARA container
must receive a `MARA_QDRANT_URL` reachable from its container network. Back up
Qdrant storage together with the app's SQL, document store and files.

The explicit `QdrantVectorStore(path=...)` API remains available for a single
process. It cannot be shared across processes. Caller-supplied Qdrant clients keep
their ownership; use `mara_compatibility=True` for MARA's ID and L2 semantics.
External clients without that flag retain their existing native Qdrant behavior.
CI starts an isolated, authenticated, loopback-only service using the SHA-256
verified native release in `scripts/prepare_qdrant_test_service.py`.

### Migrating existing Chroma data

Existing `user_data/vectorstore/chroma.sqlite3` blocks default Qdrant startup until
migration succeeds. No automatic migration or dependency installation occurs.
Stop every MARA process and back up the **entire app data directory**, including
SQL and document stores, before migration. Keep the source stopped throughout.
The exporter opens only a copied database in a separate legacy environment with
`chromadb==0.5.17` and `llama-index-vector-stores-chroma==0.6.0` (the prior lock).
Do not install these packages into the new application environment.

Run from the new checkout, replacing the placeholders with absolute paths:
Set the same `MARA_QDRANT_API_KEY` used by the target service. Choose a new, unused
namespace and use it as `MARA_QDRANT_NAMESPACE` when starting MARA after migration.

```text
<legacy-python> scripts/migrate_chroma_to_qdrant.py export --source <app-data>/user_data/vectorstore --snapshot <new-snapshot-dir> --output <new-export-dir> --source-stopped
<new-python> scripts/migrate_chroma_to_qdrant.py import --export <new-export-dir> --target <app-data>/user_data/vectorstore_qdrant --url http://127.0.0.1:6333 --namespace <new-namespace>
<new-python> scripts/migrate_chroma_to_qdrant.py verify --export <new-export-dir> --target <app-data>/user_data/vectorstore_qdrant --url http://127.0.0.1:6333 --namespace <new-namespace>
```

Snapshot, export, and target directories must be new, disjoint paths. The source
must remain at its final runtime path. Import accepts MARA L2 collections, checks
source/export hashes, IDs, dimensions, all document fields and vectors, then
reopens the target and checks recorded nearest-neighbor probes. A failed import
remains marked incomplete and cannot enable the default store; use a new target
and namespace for another attempt. Hashes of the retained legacy source, the
service address, namespace and server-side migration identity are checked at
startup. An existing server namespace is never overwritten by import.

If a copied legacy HNSW index cannot answer queries but all records and vectors
can still be read, retry export into new directories with `--probe-mode exact-l2`.
This explicitly computes the probes from every exported vector using squared L2
distance; it does not re-embed documents or repair the original Chroma directory.
The export and migration receipt record the probe source. Payload/vector checks
and target nearest-neighbor verification still apply, but this recovery mode
does not establish parity with the broken legacy approximate index.

After verification, start the new MARA version. The legacy source is preserved.
Before any new writes, rollback can use the old application and untouched source.
After new writes, roll back the old application **and the complete pre-cutover
app-data backup together**; the old vector store alone is no longer consistent
with changed SQL/document stores. No reverse migration of new Qdrant writes is
provided. Custom non-L2 collections require a separately reviewed migration.
