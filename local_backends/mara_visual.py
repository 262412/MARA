from __future__ import annotations

from typing import Any

from ktem.docqa import visual_backends


def build_visual_retriever_backend(backend_name: str):
    return visual_backends.build_visual_retriever_backend(backend_name)


def build_visual_generator_backend(backend_name: str):
    return visual_backends.build_visual_generator_backend(backend_name)


def local_visual_backend_health(
    *,
    visual_retriever_backend: str = "colqwen",
    visual_generator_backend: str = "local_qwen3_vl",
    requires_backend_config: bool = True,
) -> dict[str, Any]:
    return visual_backends.visual_backend_health(
        {
            "route_policy": "visual",
            "visual_retriever_backend": visual_retriever_backend,
            "visual_generator_backend": visual_generator_backend,
            "requires_backend_config": requires_backend_config,
        }
    )
