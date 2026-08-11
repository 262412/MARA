from __future__ import annotations

import os
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from decouple import config
from ktem.auth.policy import resolve_auth_mode, resolve_legacy_bootstrap_credentials
from ktem.utils.lang import SUPPORTED_LANGUAGE_MAP


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


ConfigReader = Callable[..., Any]


def _build_auth_settings(read_config: ConfigReader) -> dict[str, Any]:
    configured_mode = read_config("MARA_AUTH_MODE", default=None)
    legacy_sso_enabled = read_config("KH_SSO_ENABLED", default=False, cast=bool)
    if configured_mode is None and not legacy_sso_enabled:
        legacy_credentials = resolve_legacy_bootstrap_credentials(
            SimpleNamespace(
                KH_FEATURE_USER_MANAGEMENT_ADMIN=read_config(
                    "KH_FEATURE_USER_MANAGEMENT_ADMIN", default=""
                ),
                KH_FEATURE_USER_MANAGEMENT_PASSWORD=read_config(
                    "KH_FEATURE_USER_MANAGEMENT_PASSWORD", default=""
                ),
            )
        )
        if legacy_credentials is not None:
            configured_mode = "password"

    auth_mode = resolve_auth_mode(
        configured_mode=configured_mode,
        legacy_sso_enabled=legacy_sso_enabled,
    )
    return {
        "MARA_AUTH_MODE": auth_mode,
        "KH_SSO_ENABLED": auth_mode == "sso",
        "KH_FEATURE_USER_MANAGEMENT": auth_mode in {"password", "sso"},
    }


def _add_azure_models(
    settings: dict[str, Any],
    read_config: ConfigReader,
) -> None:
    if not (
        read_config("AZURE_OPENAI_API_KEY", default="")
        and read_config("AZURE_OPENAI_ENDPOINT", default="")
    ):
        return
    if read_config("AZURE_OPENAI_CHAT_DEPLOYMENT", default=""):
        settings["KH_LLMS"]["azure"] = {
            "spec": {
                "__type__": "kotaemon.llms.AzureChatOpenAI",
                "temperature": 0,
                "azure_endpoint": read_config("AZURE_OPENAI_ENDPOINT", default=""),
                "api_key": read_config("AZURE_OPENAI_API_KEY", default=""),
                "api_version": read_config("OPENAI_API_VERSION", default="")
                or "2024-02-15-preview",
                "azure_deployment": read_config(
                    "AZURE_OPENAI_CHAT_DEPLOYMENT", default=""
                ),
                "timeout": 20,
            },
            "default": False,
        }
    if read_config("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", default=""):
        settings["KH_EMBEDDINGS"]["azure"] = {
            "spec": {
                "__type__": "kotaemon.embeddings.AzureOpenAIEmbeddings",
                "azure_endpoint": read_config("AZURE_OPENAI_ENDPOINT", default=""),
                "api_key": read_config("AZURE_OPENAI_API_KEY", default=""),
                "api_version": read_config("OPENAI_API_VERSION", default="")
                or "2024-02-15-preview",
                "azure_deployment": read_config(
                    "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", default=""
                ),
                "timeout": 10,
            },
            "default": False,
        }


def build_kotaemon_settings(
    *,
    base_dir: Path,
    app_data_dir: Path,
    docs_dir: Path | None = None,
    mode: str = "dev",
    package_name: str = "mara-app",
    config_reader: ConfigReader = config,
) -> dict[str, Any]:
    read_config = config_reader
    base_dir = Path(base_dir).resolve()
    app_data_dir = Path(app_data_dir).resolve()
    docs_dir = Path(docs_dir).resolve() if docs_dir else (base_dir / "docs").resolve()
    app_data_exists = app_data_dir.exists()
    app_data_dir = _ensure_dir(app_data_dir)
    user_data_dir = _ensure_dir(app_data_dir / "user_data")
    markdown_output_dir = _ensure_dir(app_data_dir / "markdown_cache_dir")
    chunks_output_dir = _ensure_dir(app_data_dir / "chunks_cache_dir")
    parse_cache_dir = _ensure_dir(app_data_dir / "parse_cache_dir")
    embedding_cache_dir = _ensure_dir(app_data_dir / "embedding_cache_dir")
    vision_cache_dir = _ensure_dir(app_data_dir / "vision_cache_dir")
    ocr_cache_dir = _ensure_dir(app_data_dir / "ocr_cache_dir")
    formula_ocr_cache_dir = _ensure_dir(app_data_dir / "formula_ocr_cache_dir")
    office_pdf_cache_dir = _ensure_dir(app_data_dir / "office_pdf_cache_dir")
    zip_output_dir = _ensure_dir(app_data_dir / "zip_cache_dir")
    zip_input_dir = _ensure_dir(app_data_dir / "zip_cache_dir_in")
    file_storage_path = _ensure_dir(user_data_dir / "files")

    os.environ.setdefault("HF_HOME", str(app_data_dir / "huggingface"))
    os.environ.setdefault("HF_HUB_CACHE", str(app_data_dir / "huggingface"))

    app_version = read_config("KH_APP_VERSION", None)
    if not app_version:
        try:
            app_version = version(package_name)
        except Exception:
            app_version = "local" if mode == "dev" else "installed"

    settings: dict[str, Any] = {
        "KH_PACKAGE_NAME": package_name,
        "KH_APP_NAME": "MARA",
        "KH_APP_VERSION": app_version,
        "KH_GRADIO_SHARE": read_config("KH_GRADIO_SHARE", default=False, cast=bool),
        "KH_ENABLE_FIRST_SETUP": read_config(
            "KH_ENABLE_FIRST_SETUP", default=True, cast=bool
        ),
        "KH_DEMO_MODE": read_config("KH_DEMO_MODE", default=False, cast=bool),
        "KH_OLLAMA_URL": read_config(
            "KH_OLLAMA_URL", default="http://localhost:11434/v1/"
        ),
        "KH_APP_DATA_DIR": app_data_dir,
        "KH_APP_DATA_EXISTS": app_data_exists,
        "KH_USER_DATA_DIR": user_data_dir,
        "KH_MARKDOWN_OUTPUT_DIR": markdown_output_dir,
        "KH_CHUNKS_OUTPUT_DIR": chunks_output_dir,
        "KH_PARSE_CACHE_DIR": parse_cache_dir,
        "KH_EMBEDDING_CACHE_DIR": embedding_cache_dir,
        "KH_VISION_CACHE_DIR": vision_cache_dir,
        "KH_OCR_CACHE_DIR": ocr_cache_dir,
        "KH_FORMULA_OCR_CACHE_DIR": formula_ocr_cache_dir,
        "KH_OFFICE_PDF_CACHE_DIR": office_pdf_cache_dir,
        "KH_OFFICE_TO_PDF_INDEXING": read_config(
            "KH_OFFICE_TO_PDF_INDEXING", default=True, cast=bool
        ),
        "KH_OFFICE_TO_PDF_INDEXING_STRICT": read_config(
            "KH_OFFICE_TO_PDF_INDEXING_STRICT", default=True, cast=bool
        ),
        "KH_ZIP_OUTPUT_DIR": zip_output_dir,
        "KH_ZIP_INPUT_DIR": zip_input_dir,
        "KH_DOC_DIR": docs_dir,
        "KH_MODE": mode,
        **_build_auth_settings(read_config),
        "KH_FEATURE_CHAT_SUGGESTION": read_config(
            "KH_FEATURE_CHAT_SUGGESTION", default=False, cast=bool
        ),
        "KH_USER_CAN_SEE_PUBLIC": None,
        "KH_FEATURE_USER_MANAGEMENT_ADMIN": str(
            read_config("KH_FEATURE_USER_MANAGEMENT_ADMIN", default="")
        ),
        "KH_FEATURE_USER_MANAGEMENT_PASSWORD": str(
            read_config("KH_FEATURE_USER_MANAGEMENT_PASSWORD", default="")
        ),
        "KH_ENABLE_ALEMBIC": False,
        "KH_DATABASE": f"sqlite:///{user_data_dir / 'sql.db'}",
        "KH_FILESTORAGE_PATH": str(file_storage_path),
        "KH_WEB_SEARCH_BACKEND": (
            "kotaemon.indices.retrievers.tavily_web_search.WebSearch"
        ),
        "KH_DOCSTORE": {
            "__type__": "kotaemon.storages.LanceDBDocumentStore",
            "path": str(user_data_dir / "docstore"),
        },
        "KH_VECTORSTORE": {
            "__type__": "kotaemon.storages.ChromaVectorStore",
            "path": str(user_data_dir / "vectorstore"),
        },
        "KH_LLMS": {},
        "KH_EMBEDDINGS": {},
        "KH_RERANKINGS": {},
    }

    _add_azure_models(settings, read_config)

    openai_default = "<YOUR_OPENAI_KEY>"
    openai_api_key = read_config("OPENAI_API_KEY", default=openai_default)
    google_api_key = read_config("GOOGLE_API_KEY", default="your-key")
    is_openai_default = len(openai_api_key) > 0 and openai_api_key != openai_default

    if openai_api_key:
        settings["KH_LLMS"]["openai"] = {
            "spec": {
                "__type__": "kotaemon.llms.ChatOpenAI",
                "temperature": 0,
                "base_url": read_config("OPENAI_API_BASE", default="")
                or "https://api.openai.com/v1",
                "api_key": openai_api_key,
                "model": read_config("OPENAI_CHAT_MODEL", default="gpt-4o-mini"),
                "timeout": 20,
            },
            "default": is_openai_default,
        }
        settings["KH_EMBEDDINGS"]["openai"] = {
            "spec": {
                "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
                "base_url": read_config(
                    "OPENAI_API_BASE", default="https://api.openai.com/v1"
                ),
                "api_key": openai_api_key,
                "model": read_config(
                    "OPENAI_EMBEDDINGS_MODEL", default="text-embedding-3-large"
                ),
                "timeout": 10,
                "context_length": 8191,
            },
            "default": is_openai_default,
        }

    voyage_api_key = read_config("VOYAGE_API_KEY", default="")
    if voyage_api_key:
        settings["KH_EMBEDDINGS"]["voyageai"] = {
            "spec": {
                "__type__": "kotaemon.embeddings.VoyageAIEmbeddings",
                "api_key": voyage_api_key,
                "model": read_config(
                    "VOYAGE_EMBEDDINGS_MODEL", default="voyage-3-large"
                ),
            },
            "default": False,
        }
        settings["KH_RERANKINGS"]["voyageai"] = {
            "spec": {
                "__type__": "kotaemon.rerankings.VoyageAIReranking",
                "model_name": "rerank-2",
                "api_key": voyage_api_key,
            },
            "default": False,
        }

    if read_config("LOCAL_MODEL", default=""):
        settings["KH_LLMS"]["ollama"] = {
            "spec": {
                "__type__": "kotaemon.llms.ChatOpenAI",
                "base_url": settings["KH_OLLAMA_URL"],
                "model": read_config("LOCAL_MODEL", default="qwen2.5:7b"),
                "api_key": "ollama",
            },
            "default": False,
        }
        settings["KH_LLMS"]["ollama-long-context"] = {
            "spec": {
                "__type__": "kotaemon.llms.LCOllamaChat",
                "base_url": settings["KH_OLLAMA_URL"].replace("v1/", ""),
                "model": read_config("LOCAL_MODEL", default="qwen2.5:7b"),
                "num_ctx": 8192,
            },
            "default": False,
        }
        settings["KH_EMBEDDINGS"]["ollama"] = {
            "spec": {
                "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
                "base_url": settings["KH_OLLAMA_URL"],
                "model": read_config(
                    "LOCAL_MODEL_EMBEDDINGS", default="nomic-embed-text"
                ),
                "api_key": "ollama",
            },
            "default": False,
        }
        settings["KH_EMBEDDINGS"]["fast_embed"] = {
            "spec": {
                "__type__": "kotaemon.embeddings.FastEmbedEmbeddings",
                "model_name": "BAAI/bge-base-en-v1.5",
            },
            "default": False,
        }

    settings["KH_LLMS"]["claude"] = {
        "spec": {
            "__type__": "kotaemon.llms.chats.LCAnthropicChat",
            "model_name": "claude-3-5-sonnet-20240620",
            "api_key": "your-key",
        },
        "default": False,
    }
    settings["KH_LLMS"]["google"] = {
        "spec": {
            "__type__": "kotaemon.llms.chats.LCGeminiChat",
            "model_name": "gemini-1.5-flash",
            "api_key": google_api_key,
        },
        "default": not is_openai_default,
    }
    settings["KH_LLMS"]["groq"] = {
        "spec": {
            "__type__": "kotaemon.llms.ChatOpenAI",
            "base_url": "https://api.groq.com/openai/v1",
            "model": "llama-3.1-8b-instant",
            "api_key": "your-key",
        },
        "default": False,
    }
    settings["KH_LLMS"]["cohere"] = {
        "spec": {
            "__type__": "kotaemon.llms.chats.LCCohereChat",
            "model_name": "command-r-plus-08-2024",
            "api_key": read_config("COHERE_API_KEY", default="your-key"),
        },
        "default": False,
    }
    settings["KH_LLMS"]["mistral"] = {
        "spec": {
            "__type__": "kotaemon.llms.ChatOpenAI",
            "base_url": "https://api.mistral.ai/v1",
            "model": "ministral-8b-latest",
            "api_key": read_config("MISTRAL_API_KEY", default="your-key"),
        },
        "default": False,
    }

    settings["KH_EMBEDDINGS"]["cohere"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.LCCohereEmbeddings",
            "model": "embed-multilingual-v3.0",
            "cohere_api_key": read_config("COHERE_API_KEY", default="your-key"),
            "user_agent": "default",
        },
        "default": False,
    }
    settings["KH_EMBEDDINGS"]["google"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.LCGoogleEmbeddings",
            "model": "models/text-embedding-004",
            "google_api_key": google_api_key,
        },
        "default": not is_openai_default,
    }
    settings["KH_EMBEDDINGS"]["mistral"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.LCMistralEmbeddings",
            "model": "mistral-embed",
            "api_key": read_config("MISTRAL_API_KEY", default="your-key"),
        },
        "default": False,
    }
    settings["KH_RERANKINGS"]["local"] = {
        "spec": {
            "__type__": "kotaemon.rerankings.LocalMultilingualReranking",
        },
        "default": True,
    }
    settings["KH_RERANKINGS"]["cohere"] = {
        "spec": {
            "__type__": "kotaemon.rerankings.CohereReranking",
            "model_name": "rerank-v4.0-fast",
            "cohere_api_key": read_config("COHERE_API_KEY", default=""),
        },
        "default": False,
    }

    settings["KH_REASONINGS"] = [
        "ktem.reasoning.simple.FullQAPipeline",
        "ktem.reasoning.mara.MaraAgentPipeline",
        "ktem.reasoning.simple.FullDecomposeQAPipeline",
        "ktem.reasoning.react.ReactAgentPipeline",
        "ktem.reasoning.rewoo.RewooAgentPipeline",
    ]
    settings["KH_REASONINGS_USE_MULTIMODAL"] = read_config(
        "USE_MULTIMODAL", default=False, cast=bool
    )
    settings[
        "KH_VLM_ENDPOINT"
    ] = "{0}/openai/deployments/{1}/chat/completions?api-version={2}".format(
        read_config("AZURE_OPENAI_ENDPOINT", default=""),
        read_config("OPENAI_VISION_DEPLOYMENT_NAME", default="gpt-4o"),
        read_config("OPENAI_API_VERSION", default=""),
    )

    settings["SETTINGS_APP"] = {}
    settings["SETTINGS_REASONING"] = {
        "use": {
            "name": "Reasoning options",
            "value": None,
            "choices": [],
            "component": "radio",
        },
        "lang": {
            "name": "Language",
            "value": "en",
            "choices": [(lang, code) for code, lang in SUPPORTED_LANGUAGE_MAP.items()],
            "component": "dropdown",
        },
        "max_context_length": {
            "name": "Max context length (LLM)",
            "value": read_config("MAX_CONTEXT_LENGTH", default=32000, cast=int),
            "component": "number",
        },
    }

    settings["USE_GLOBAL_GRAPHRAG"] = read_config(
        "USE_GLOBAL_GRAPHRAG", default=False, cast=bool
    )
    settings["USE_NANO_GRAPHRAG"] = read_config(
        "USE_NANO_GRAPHRAG", default=False, cast=bool
    )
    settings["USE_LIGHTRAG"] = read_config("USE_LIGHTRAG", default=False, cast=bool)
    settings["USE_MS_GRAPHRAG"] = read_config(
        "USE_MS_GRAPHRAG", default=False, cast=bool
    )
    settings["GRAPHRAG_INDEX_TYPES"] = []
    settings["KH_INDEX_TYPES"] = ["ktem.index.file.FileIndex"]
    settings["GRAPHRAG_INDICES"] = []
    settings["KH_INDICES"] = [
        {
            "name": "File Collection",
            "config": {
                "supported_file_types": (
                    ".png, .jpeg, .jpg, .tiff, .tif, .pdf, .xls, .xlsx, .doc, .docx, "
                    ".ppt, .pptx, .csv, .html, .mhtml, .txt, .md, .zip"
                ),
                "private": True,
            },
            "index_type": "ktem.index.file.FileIndex",
        },
    ]

    return settings
