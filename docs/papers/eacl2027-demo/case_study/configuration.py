"""Write a fresh case configuration; credentials remain in environment variables."""

import os
from pathlib import Path

OVERRIDES = """import os
KH_LLMS = {"case_deepseek": {"default": True, "spec": {
    "__type__": "kotaemon.llms.chats.openai.ChatOpenAI",
    "api_key": os.environ["MARA_CASE_CHAT_API_KEY"],
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-v4-flash", "timeout": 45}}}
KH_EMBEDDINGS = {"case_openai_embedding": {"default": True, "spec": {
    "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
    "api_key": os.environ["MARA_CASE_EMBEDDING_API_KEY"],
    "base_url": "https://api.openai.com/v1", "context_length": 8191,
    "model": "text-embedding-3-large", "timeout": 30}}}
KH_RERANKINGS = {"case_unused_reranker": {"default": True, "spec": {
    "__type__": "kotaemon.rerankings.CohereReranking",
    "cohere_api_key": "unused", "model_name": "rerank-multilingual-v3.0"}}}
KH_FEATURE_USER_MANAGEMENT = False
KH_ENABLE_FIRST_SETUP = False
KH_WEB_SEARCH_BACKEND = ""
KH_FILE_INDEX_ARTIFACTS_ENABLED = False
"""


def configure(output):
    for name in ("MARA_CASE_CHAT_API_KEY", "MARA_CASE_EMBEDDING_API_KEY"):
        if not os.environ.get(name):
            raise ValueError(f"Set {name} before a new live run")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty output directory to preserve previous runs")
    app = output / "runtime"
    (app / "config").mkdir(parents=True)
    (app / "config/flowsettings.py").write_text(OVERRIDES, encoding="utf-8")
    os.environ["MARA_APP_HOME"] = str(app)
    os.environ["KH_APP_DATA_DIR"] = str(app / "data")
    os.environ["KH_SETTINGS_MODULE"] = "ktem.default_flowsettings"
    os.environ.pop("MARA_DESKTOP_DATA_DIR", None)
    return Path(app)
