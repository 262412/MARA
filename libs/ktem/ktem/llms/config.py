"""Narrow migration at the first-party model configuration boundary."""

import logging

_OLD_OPENAI_AGENT = "llama_index.agent.openai.OpenAIAgent"
_NEW_OPENAI_AGENT = "kotaemon.agents.openai.OpenAIAgent"
_RETIRED_OPENAI_MULTIMODAL = "llama_index.multi_modal_llms.openai.OpenAIMultiModal"


def migrate_legacy_agent_classpath(classpath):
    if classpath == _RETIRED_OPENAI_MULTIMODAL:
        raise ValueError(
            "OpenAIMultiModal has been retired; remove the old entry from model configuration."
        )
    if classpath == _OLD_OPENAI_AGENT:
        logging.getLogger(__name__).warning(
            "Migrating saved model classpath %s to %s; external Python imports require migration",
            _OLD_OPENAI_AGENT,
            _NEW_OPENAI_AGENT,
        )
        return _NEW_OPENAI_AGENT
    return classpath


def migrate_legacy_agent_spec(spec):
    legacy_paths = (_OLD_OPENAI_AGENT, _RETIRED_OPENAI_MULTIMODAL)
    if isinstance(spec, dict) and spec.get("__type__") in legacy_paths:
        return {**spec, "__type__": migrate_legacy_agent_classpath(spec["__type__"])}
    if isinstance(spec, str) and spec.startswith("{{") and spec.endswith("}}"):
        path = spec[2:-2].strip()
        if path in legacy_paths:
            return "{{ " + migrate_legacy_agent_classpath(path) + " }}"
    return spec
