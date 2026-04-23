from importlib import import_module

_LAZY_EXPORTS = {
    # Document stores
    "BaseDocumentStore": ".docstores",
    "InMemoryDocumentStore": ".docstores",
    "ElasticsearchDocumentStore": ".docstores",
    "SimpleFileDocumentStore": ".docstores",
    "LanceDBDocumentStore": ".docstores",
    # Vector stores
    "BaseVectorStore": ".vectorstores",
    "ChromaVectorStore": ".vectorstores",
    "InMemoryVectorStore": ".vectorstores",
    "SimpleFileVectorStore": ".vectorstores",
    "LanceDBVectorStore": ".vectorstores",
    "MilvusVectorStore": ".vectorstores",
    "QdrantVectorStore": ".vectorstores",
}

__all__ = list(_LAZY_EXPORTS.keys())


def __getattr__(name: str):
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
