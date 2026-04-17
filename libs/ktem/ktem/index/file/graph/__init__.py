from importlib import import_module

__all__ = ["GraphRAGIndex", "NanoGraphRAGIndex", "LightRAGIndex"]


def __getattr__(name: str):
	if name == "GraphRAGIndex":
		return getattr(import_module(".graph_index", __name__), name)
	if name == "LightRAGIndex":
		return getattr(import_module(".light_graph_index", __name__), name)
	if name == "NanoGraphRAGIndex":
		return getattr(import_module(".nano_graph_index", __name__), name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
