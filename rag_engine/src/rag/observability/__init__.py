"""Observabilité — wrappers utilitaires (Langfuse pour le moment).

Pourquoi un package séparé : la stack d'observabilité grossira (Prometheus
counters M6+, OpenTelemetry plus tard) et on ne veut pas la diluer dans
`rag.utils`. Ce module reste OFF par défaut côté config ; il faut
explicitement activer `observability.langfuse_enabled` pour que les
callbacks soient construits.
"""

from __future__ import annotations

from rag.observability.langfuse_handler import build_langfuse_handler

__all__ = ["build_langfuse_handler"]
