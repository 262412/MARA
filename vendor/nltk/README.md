# NLTK model I/O security backport

This is MARA's **3.10.3.post1+mara.1** distribution, not an official NLTK
release. It addresses [GHSA-8mgp-746c-j5xp](https://github.com/advisories/GHSA-8mgp-746c-j5xp)
using source from NLTK commit
[`b417a98a9497b4a27067043e35e64c388e060686`](https://github.com/nltk/nltk/tree/b417a98a9497b4a27067043e35e64c388e060686).

`security.patch` contains 14 runtime files: the affected model APIs, adjacent
Punkt/CRF/NE model I/O, and their path, serialization, regex and terminal/CSV
security dependencies. The modules are copied exactly from that commit to avoid
inventing a different security implementation. The patch also includes the
upstream regression tests and fixtures, unchanged, and a distinct local version.
Other NLTK package files remain byte-for-byte identical to the official base.

The build backend reads the official `nltk==3.10.3` build dependency **without
importing its Python code**, checks every input against `base-files.json`, applies
the patch with Git, and verifies every resulting file against `backport.json`.
The original wheel SHA-256 is
`ff9598a8e20518ee0d557745890cc4435b9578489e2dcbc69c4f81fa060caf7c`.
Original copyright and Apache-2.0 license files are retained. Git and Python 3.11+
are required to build. No prebuilt binary or vulnerable base dependency is
included in the application runtime.

The root and container locks must resolve this source package. Do not substitute
a PyPI release with the same base version, add an audit ignore, or consider a
version-only scanner result proof of the fix. CI verifies the installed source
hashes and executes the exploit and legitimate-use regressions separately.

This local distribution is for repository/container builds. Publishing MARA
packages for independent PyPI installation requires a separately published
backport wheel or an accepted fixed upstream release. Replace the backport once
an upstream release includes these fixes, retaining the regression tests and
rerunning dependency audits and supported-platform gates.
