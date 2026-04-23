from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any, Optional, Type, overload

from sqlalchemy import select
from sqlalchemy.orm import Session
from theflow.utils.modules import deserialize, import_dotted_string

if TYPE_CHECKING:
    from kotaemon.llms import ChatLLM

from .db import LLMTable, engine


class LLMManager:
    """Represent a pool of models"""

    def __init__(self):
        from theflow.settings import settings as flowsettings

        self._models: dict[str, ChatLLM] = {}
        self._info: dict[str, dict] = {}
        self._default: str = ""
        self._vendors: list[Type] = []
        self._load_errors: list[str] = []

        if hasattr(flowsettings, "KH_LLMS"):
            for name, model in flowsettings.KH_LLMS.items():
                with Session(engine) as session:
                    stmt = select(LLMTable).where(LLMTable.name == name)
                    result = session.execute(stmt)
                    if not result.first():
                        item = LLMTable(
                            name=name,
                            spec=model["spec"],
                            default=model.get("default", False),
                        )
                        session.add(item)
                        session.commit()

        self.load()

    def load(self):
        """Load the model pool from database"""
        self._models, self._info, self._default, self._load_errors = {}, {}, "", []
        with Session(engine) as session:
            stmt = select(LLMTable)
            items = session.execute(stmt)

            for (item,) in items:
                info = {
                    "name": item.name,
                    "spec": item.spec,
                    "default": item.default,
                }
                self._info[item.name] = info
                if item.default:
                    self._default = item.name

    def _load_model(self, key: str) -> "ChatLLM":
        if key not in self._info:
            raise KeyError(key)

        if key in self._models:
            return self._models[key]

        spec = self._info[key]["spec"]
        try:
            model = deserialize(spec, safe=False)
        except Exception as exc:
            message = str(exc)
            self._info[key]["load_error"] = message
            formatted = f"{key}: {message}"
            if formatted not in self._load_errors:
                self._load_errors.append(formatted)
            raise

        self._models[key] = model
        self._info[key].pop("load_error", None)
        return model

    def load_vendors(self):
        from theflow.settings import settings as flowsettings

        from kotaemon.llms import (
            AzureChatOpenAI,
            ChatOpenAI,
            LCAnthropicChat,
            LCCohereChat,
            LCGeminiChat,
            LCOllamaChat,
            LlamaCppChat,
        )

        self._vendors = [
            ChatOpenAI,
            AzureChatOpenAI,
            LCAnthropicChat,
            LCGeminiChat,
            LCCohereChat,
            LCOllamaChat,
            LlamaCppChat,
        ]

        for extra_vendor in getattr(flowsettings, "KH_LLM_EXTRA_VENDORS", []):
            self._vendors.append(import_dotted_string(extra_vendor, safe=False))

    def __getitem__(self, key: str) -> ChatLLM:
        """Get model by name"""
        return self._load_model(key)

    def __contains__(self, key: str) -> bool:
        """Check if model exists"""
        return key in self._info

    @overload
    def get(self, key: str, default: None) -> Optional[ChatLLM]:
        ...

    @overload
    def get(self, key: str, default: ChatLLM) -> ChatLLM:
        ...

    def get(self, key: str, default: Optional[ChatLLM] = None) -> Optional[ChatLLM]:
        """Get model by name with default value"""
        if key not in self:
            return default
        return self._load_model(key)

    def settings(self) -> dict:
        """Present model pools option for gradio"""
        return {
            "label": "LLM",
            "choices": list(self._info.keys()),
            "value": self.get_default_name(),
        }

    def options(self) -> Mapping[str, Any]:
        """Present a dict of models"""
        return _LazyOptionsView(self)

    def get_random_name(self) -> str:
        """Get the name of random model

        Returns:
            str: random model name in the pool
        """
        import random

        if not self._info:
            raise ValueError("No models in pool")

        return random.choice(list(self._info.keys()))

    def get_default_name(self) -> str:
        """Get the name of default model

        In case there is no default model, choose random model from pool. In
        case there are multiple default models, choose random from them.

        Returns:
            str: model name
        """
        if not self._info:
            raise ValueError("No models in pool")

        if not self._default:
            return self.get_random_name()

        return self._default

    def get_random(self) -> ChatLLM:
        """Get random model"""
        return self[self.get_random_name()]

    def get_default(self) -> ChatLLM:
        """Get default model

        In case there is no default model, choose random model from pool. In
        case there are multiple default models, choose random from them.

        Returns:
            ChatLLM: model
        """
        return self[self.get_default_name()]

    def info(self) -> dict:
        """List all models"""
        return self._info

    def load_errors(self) -> list[str]:
        """List model specs that failed to deserialize."""
        return list(self._load_errors)

    def add(self, name: str, spec: dict, default: bool):
        """Add a new model to the pool"""
        if not name:
            raise ValueError("Name must not be empty")

        try:
            with Session(engine) as session:

                if default:
                    # turn all models to non-default
                    session.query(LLMTable).update({"default": False})
                    session.commit()

                item = LLMTable(name=name, spec=spec, default=default)
                session.add(item)
                session.commit()
        except Exception as e:
            raise ValueError(f"Failed to add model {name}: {e}")

        self.load()

    def delete(self, name: str):
        """Delete a model from the pool"""
        try:
            with Session(engine) as session:
                item = session.query(LLMTable).filter_by(name=name).first()
                session.delete(item)
                session.commit()
        except Exception as e:
            raise ValueError(f"Failed to delete model {name}: {e}")

        self.load()

    def update(self, name: str, spec: dict, default: bool, new_name: str = ""):
        """Update a model in the pool, optionally renaming it."""
        if not name:
            raise ValueError("Name must not be empty")

        if new_name and new_name != name:
            # Check uniqueness before destructive delete
            if new_name in self._info:
                raise ValueError(
                    f"Model '{new_name}' already exists. Use a unique name."
                )
            self.delete(name)
            self.add(new_name, spec=spec, default=default)
            return

        try:
            with Session(engine) as session:

                if default:
                    # turn all models to non-default
                    session.query(LLMTable).update({"default": False})
                    session.commit()

                item = session.query(LLMTable).filter_by(name=name).first()
                if not item:
                    raise ValueError(f"Model {name} not found")
                item.spec = spec
                item.default = default
                session.commit()
        except Exception as e:
            raise ValueError(f"Failed to update model {name}: {e}")

        self.load()

    def vendors(self) -> dict:
        """Return list of vendors"""
        if not self._vendors:
            self.load_vendors()
        return {vendor.__qualname__: vendor for vendor in self._vendors}


class _LazyManagerProxy:
    def __init__(self, factory):
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_manager", None)

    def _get_manager(self):
        manager = object.__getattribute__(self, "_manager")
        if manager is None:
            manager = object.__getattribute__(self, "_factory")()
            object.__setattr__(self, "_manager", manager)
        return manager

    def __getattribute__(self, name):
        if name in {
            "_factory",
            "_manager",
            "_get_manager",
            "__class__",
            "__dict__",
            "__weakref__",
            "__repr__",
            "__getitem__",
            "__contains__",
            "__setattr__",
            "__delattr__",
        }:
            return object.__getattribute__(self, name)

        local_dict = object.__getattribute__(self, "__dict__")
        if not name.startswith("_") and name in local_dict:
            return local_dict[name]
        return getattr(self._get_manager(), name)

    def __setattr__(self, name, value):
        if name in {"_factory", "_manager"}:
            object.__setattr__(self, name, value)
            return
        if name.startswith("_"):
            setattr(self._get_manager(), name, value)
            return

        local_dict = object.__getattribute__(self, "__dict__")
        if object.__getattribute__(self, "_manager") is None:
            local_dict[name] = value
            return
        setattr(self._get_manager(), name, value)

    def __delattr__(self, name):
        if name in {"_factory", "_manager"}:
            raise AttributeError(name)
        if name.startswith("_"):
            delattr(self._get_manager(), name)
            return

        local_dict = object.__getattribute__(self, "__dict__")
        if name in local_dict:
            del local_dict[name]
            return
        delattr(self._get_manager(), name)

    def __getitem__(self, key):
        return self._get_manager()[key]

    def __contains__(self, key):
        return key in self._get_manager()

    def __repr__(self):
        manager = object.__getattribute__(self, "_manager")
        if manager is None:
            return "<LazyManagerProxy uninitialized>"
        return repr(manager)


class _LazyOptionsView(Mapping[str, Any]):
    def __init__(self, manager: LLMManager):
        self._manager = manager

    def __getitem__(self, key: str) -> Any:
        return self._manager[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._manager._info.keys())

    def __len__(self) -> int:
        return len(self._manager._info)


llms = _LazyManagerProxy(LLMManager)
