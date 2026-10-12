# Contributing to MARA

Start with the [development setup and verification guide](docs/development/contributing.md).
All non-trivial changes follow the [codebase hygiene contract](docs/development/codebase-hygiene-contract.md)
and [storage layout contract](docs/development/storage-layout-contract.md).
The [architecture contracts](docs/development/architecture-contracts.md) describe
current responsibility boundaries and their tests.

Preserve public `MARA` / `MARA-cli` commands, persisted data, user configuration
and unrelated working changes. Characterize old behavior before extraction;
demonstrate a defect before changing production behavior. Use focused tests,
then the applicable package, collection and delivery gates. Never refresh a
baseline to make a failing gate pass.

Submit a focused pull request to [MARA](https://github.com/262412/MARA/compare)
with the problem, resulting behavior, actual verification and remaining limits.
Use conventional commit subjects such as `test: guard inspection imports`.
Check [existing issues](https://github.com/262412/MARA/issues) before reporting
a reproducible problem, and omit secrets and real user data from evidence.

The [code of conduct](CODE_OF_CONDUCT.md) applies. Contributions use the
[Apache 2.0 license](LICENSE.txt); preserve upstream attribution in [NOTICE](NOTICE).
Green structural tests do not replace functional review or release gates.
