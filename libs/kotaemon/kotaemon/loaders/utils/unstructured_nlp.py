"""Require a local NLP model before Unstructured can invoke its auto-installer."""


def require_local_spacy_model() -> None:
    import spacy

    try:
        spacy.load("en_core_web_sm", exclude=["ner", "lemmatizer", "attribute_ruler"])
    except OSError as exc:
        raise RuntimeError(
            "Install the spaCy en_core_web_sm model locally before using "
            "Unstructured parsing. MARA does not download it automatically."
        ) from exc
