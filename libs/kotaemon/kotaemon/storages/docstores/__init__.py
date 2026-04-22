from importlib import import_module

_LAZY_EXPORTS = {
    "BaseDocumentStore": ".base",
    "InMemoryDocumentStore": ".in_memory",
    "SimpleFileDocumentStore": ".simple_file",
    "ElasticsearchDocumentStore": ".elasticsearch",
    "LanceDBDocumentStore": ".lancedb",
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
