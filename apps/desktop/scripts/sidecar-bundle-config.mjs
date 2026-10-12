export const excludedSidecarModules = [
  "IPython",
  "_pytest",
  "_tkinter",
  "black",
  "cohere",
  "cryptography",
  "docutils",
  "gradio",
  "gradio_client",
  "google.generativeai",
  "googleapiclient",
  "haystack",
  "huggingface_hub",
  "jedi",
  "keyring",
  "llvmlite",
  "magic",
  "matplotlib",
  "mistralai",
  "networkx",
  "numba",
  "pytest",
  "safetensors",
  "scipy",
  "sentence_transformers",
  "sklearn",
  "sphinx",
  "tensorflow",
  "tkinter",
  "torch",
  "transformers",
];

export const requiredSidecarModules = [
  "docx",
  "en_core_web_sm",
  "ktem.default_flowsettings",
  "ktem.desktop_model_routes",
  "ktem.docqa",
  "ktem.index.file.pipelines",
  "ktem.reasoning.prompt_optimization.decompose_question",
  "ktem.reasoning.prompt_optimization.rewrite_question",
  "ktem.reasoning.simple",
  "ktem.runtime_defaults",
  "kotaemon.embeddings.openai",
  "kotaemon.llms",
  "kotaemon.llms.chats.openai",
  "kotaemon.storages.docstores.lancedb",
  "kotaemon.storages.vectorstores.qdrant",
  "lancedb",
  "llama_index.vector_stores.qdrant",
  "openai",
  "openpyxl",
  "onnxruntime",
  "pandas",
  "pptx",
  "qdrant_client",
  "slide_cli.docqa_runtime",
  "theflow.backends",
  "theflow.cache",
  "theflow.callbacks",
  "theflow.context",
  "theflow.middleware",
  "theflow.settings.default",
  "theflow.storage",
  "tiktoken_ext.openai_public",
  "tokenizers",
  "tqdm",
  "unstructured.partition.auto",
  "unstructured.partition.pptx",
];

export const supportedDesktopEmbeddingProviders = [
  {
    module: "openai",
    types: [
      "kotaemon.embeddings.OpenAIEmbeddings",
      "kotaemon.embeddings.AzureOpenAIEmbeddings",
    ],
  },
];

export const supportedDesktopChatProviders = [
  {
    module: "openai",
    providers: ["openai_compatible", "azure_openai", "ollama"],
    types: ["kotaemon.llms.ChatOpenAI", "kotaemon.llms.AzureChatOpenAI"],
  },
];

export const requiredSidecarDataPackages = [
  "en_core_web_sm", "llama_index.core",
];

export const requiredTiktokenEncodings = ["cl100k_base"];
export const tiktokenCacheDestination = "tiktoken_cache";

export const requiredSidecarDataDirectories = [
  {
    source: "sidecar/nltk_data/tokenizers/punkt",
    destination: "llama_index/core/_static/nltk_cache/tokenizers/punkt",
  },
];
