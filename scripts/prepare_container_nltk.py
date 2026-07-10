from __future__ import annotations

import argparse
from pathlib import Path


def prepare_nltk_cache(cache: Path) -> Path:
    required = (cache / "corpora/stopwords/english",)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "The locked llama-index-core wheel lacks required bundled NLTK data: "
            + ", ".join(missing)
        )
    # llama-index-core 0.10.68.post1 checks the legacy path before using the
    # normal tokenizer paths. The empty compatibility directory prevents its
    # eager import hook from attempting a network download. MARA uses the
    # locked tiktoken path rather than NLTK's generic Punkt tokenizer.
    (cache / "tokenizers/punkt").mkdir(parents=True, exist_ok=True)
    return cache


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare the locked llama-index NLTK cache for offline use."
    )
    parser.add_argument("cache", type=Path)
    args = parser.parse_args()
    prepare_nltk_cache(args.cache.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
