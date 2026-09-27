# Portable observation packets

Original candidates, snapshot locks and full local exports remain unchanged.
Independent qualification uses the complete original locked tree. Publication is
a separate representation of that evidence, not a repair or a changed outcome.

Some subjects installed about 130 MB of ordinary Python dependencies under `.deps`.
The frozen snapshot captured those files. `publication.py` inventories this cache
without deleting it: only files matching installed-distribution RECORD SHA-256
digests (and the RECORD inventory itself) may be represented by hashes and exact
distribution metadata in Git. Unknown files and modified dependencies remain in
the published source overlay. All model-created code, data, documents, public
events and failed attempts remain reviewable. This classification never changes
a score, a model resource limit, or an input supplied to an active subject.

Each immutable `publication-manifest.v1.json` binds the original snapshot and full
export map, partitions every file into published content or retained dependency
cache, and records names, versions and platform wheel tags. The full local cache
remains in the declared evaluation boundary. Another reviewer can install the
pinned distributions in a compatible disposable environment and apply published
overlays. Byte equivalence requires checking the original inventory; this document
does not claim that reconstruction has already been verified or that platform
wheels are interchangeable. Missing blobs are explicit, not silently discarded.

Run `publication.py prepare --storage <declared storage>` to describe newly locked
exports, then `publication.py verify` to verify the portable representation. Stage
the receipt files plus the manifest's `published_files`; do not bulk-stage an
unclassified dependency cache or an active JSONL stream. Existing frozen manifests,
source artifacts, historical results and export maps must not be rewritten.
