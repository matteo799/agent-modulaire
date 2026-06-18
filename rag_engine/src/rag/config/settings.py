"""Typed configuration loaded from YAML + env vars.

Hierarchy (lowest priority first):
1. `configs/default.yaml`
2. `configs/{ENV}.yaml`  (ENV defaults to "dev")
3. Environment variables, prefixed `RAG__` (double underscore = nesting)
4. `.env` file (same prefix rules)

Examples:
    RAG__VECTOR_STORE__PROVIDER=qdrant
    RAG__LLM__PROVIDER=ollama
    RAG__LLM__OLLAMA__BASE_URL=http://localhost:11434

Nothing else in the codebase is allowed to call os.getenv directly.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---- sub-models -----------------------------------------------------------


class QdrantSettings(BaseModel):
    url: str = "http://localhost:6333"
    api_key: str | None = None


class VectorStoreSettings(BaseModel):
    provider: Literal["qdrant"] = "qdrant"
    collection: str = "rag_default"
    qdrant: QdrantSettings = QdrantSettings()


class EmbedderSettings(BaseModel):
    provider: Literal["sentence_transformers"] = "sentence_transformers"
    model: str = "BAAI/bge-m3"
    device: Literal["cpu", "cuda", "mps", "auto"] = "auto"
    batch_size: int = 32


class OllamaSettings(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "mistral:7b-instruct"
    # Timeout par requête. 120 s pour tenir sur du Mac CPU avec un 7B
    # (chaque génération de ~200 tokens peut prendre 60-90 s). Augmente
    # encore via `RAG__LLM__OLLAMA__TIMEOUT_S=180` si tu vois des ReadTimeout.
    timeout_s: float = 120.0


class VLLMSettings(BaseModel):
    base_url: str = "http://localhost:8000/v1"
    model: str = "mistralai/Mistral-7B-Instruct-v0.3"
    api_key: str = "EMPTY"


class LMStudioSettings(BaseModel):
    base_url: str = "http://localhost:1234"
    model: str = ""  # vide = modèle actuellement chargé dans LM Studio
    timeout_s: float = 120.0


class OpenAISettings(BaseModel):
    """API OpenAI ou toute passerelle compatible (ex. meai.cloud servant Claude)."""

    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    # JAMAIS en clair dans la config versionnée. Renseignée par la variable
    # d'env `RAG__LLM__OPENAI__API_KEY` (ou un `.env` gitignoré).
    api_key: str = ""
    timeout_s: float = 120.0


class LLMSettings(BaseModel):
    provider: Literal["ollama", "vllm", "openai", "lmstudio"] = "ollama"
    temperature: float = 0.0  # we want determinism on a RAG, not creativity
    max_tokens: int = 1024
    ollama: OllamaSettings = OllamaSettings()
    vllm: VLLMSettings = VLLMSettings()
    lmstudio: LMStudioSettings = LMStudioSettings()
    openai: OpenAISettings = OpenAISettings()


class RerankerSettings(BaseModel):
    enabled: bool = True
    model: str = "BAAI/bge-reranker-v2-m3"
    top_k: int = 5
    # `cpu` par défaut : le reranker tourne en CPU pour laisser MPS libre à
    # l'embedder (BGE-M3) et à Ollama. Sur une machine avec GPU dédié, passer
    # RAG__RERANKER__DEVICE=cuda.
    device: Literal["cpu", "cuda", "mps", "auto"] = "cpu"
    # Réduire si OOM sur GPU/MPS avec de longs passages (juridique, médical…).
    # 8 est sûr sur un M1 Air 8 GB avec BGE-M3 + reranker chargés ensemble.
    batch_size: int = 8


class RetrievalSettings(BaseModel):
    dense_k: int = 20
    bm25_k: int = 20
    hybrid_enabled: bool = False  # activer le retrieval hybride (dense + BM25)
    hybrid_rrf_constant: int = 60  # standard RRF constant
    parent_neighbors: int = 0  # 0 = only the parent; 1 = parent ± 1, etc.


class CRAGSettings(BaseModel):
    enabled: bool = True  # False = RAG simple (retrieve → generate), sans boucle corrective
    max_iterations: int = 2  # how many rewrite→retrieve loops before giving up
    relevance_threshold: float = 0.5  # below = irrelevant
    ambiguous_threshold: float = 0.75  # between thresholds = ambiguous, above = relevant
    enable_grounding_check: bool = True


class APISettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=list)


class ObservabilitySettings(BaseModel):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_queries: bool = False  # off by default for sensitive content
    langfuse_enabled: bool = False
    langfuse_host: str = "http://localhost:3000"


# ---- root -----------------------------------------------------------------


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RAG__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["dev", "test", "prod"] = "dev"
    data_dir: Path = Path("./data")

    vector_store: VectorStoreSettings = VectorStoreSettings()
    embedder: EmbedderSettings = EmbedderSettings()
    llm: LLMSettings = LLMSettings()
    reranker: RerankerSettings = RerankerSettings()
    retrieval: RetrievalSettings = RetrievalSettings()
    crag: CRAGSettings = CRAGSettings()
    api: APISettings = APISettings()
    observability: ObservabilitySettings = ObservabilitySettings()


# ---- loader ---------------------------------------------------------------


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _apply_env_overrides(
    target: dict[str, Any],
    *,
    prefix: str = "RAG__",
    delimiter: str = "__",
) -> None:
    """Sur-couche env vars → dict YAML, IN-PLACE.

    pydantic-settings v2 donne la priorité aux kwargs `Settings(**...)` sur
    les env vars. Comme on charge le YAML en kwargs, les env vars étaient
    ignorées dès qu'une clé existait dans la YAML. On rétablit l'ordre de
    priorité attendu (env > YAML > defaults) en injectant manuellement les
    vars RAG__... dans le dict YAML avant de l'envoyer à pydantic.

    Conversion : les valeurs restent en `str`, c'est pydantic qui coerce
    en bool / int / float au moment de la validation.
    """
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        path = [p.lower() for p in key[len(prefix) :].split(delimiter) if p]
        if not path:
            continue
        cur = target
        for sub in path[:-1]:
            existing = cur.get(sub)
            if not isinstance(existing, dict):
                existing = {}
                cur[sub] = existing
            cur = existing
        cur[path[-1]] = value


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Injecte les paires `KEY=VALUE` d'un `.env` dans os.environ (sans écraser
    une variable déjà définie). Sert à garder les secrets (clés API) hors de la
    config versionnée : `_apply_env_overrides` les reprend ensuite normalement.

    Volontairement minimal (pas de python-dotenv) : lignes `KEY=VALUE`, `#`
    commentaires et lignes vides ignorées, guillemets optionnels retirés.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_settings(configs_dir: Path | str = "configs") -> Settings:
    """Charge `.env` + `default.yaml` + `{env}.yaml` + env vars, dans cet ordre.

    Priorité finale (du plus fort au plus faible) :
    1. env vars `RAG__SECTION__KEY` (un `.env` du cwd les pré-remplit)
    2. `configs/{env}.yaml`
    3. `configs/default.yaml`
    4. defaults pydantic
    """
    _load_dotenv()
    configs_dir = Path(configs_dir)
    env = os.getenv("RAG__ENV", "dev")

    merged: dict[str, Any] = {}
    for name in ("default.yaml", f"{env}.yaml"):
        path = configs_dir / name
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                merged = _deep_merge(merged, yaml.safe_load(f) or {})

    _apply_env_overrides(merged)
    return Settings(**merged)
