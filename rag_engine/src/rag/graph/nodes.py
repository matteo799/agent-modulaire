"""Nœuds du graphe CRAG (LangGraph).

Chaque nœud est une **factory** qui retourne une fonction prenant un
`CRAGState` et renvoyant un `dict[str, Any]` des champs à mettre à jour.
LangGraph fusionne ce dict dans l'état partagé.

Pourquoi factory + closure : les dépendances (Retriever, LLMClient, …) sont
capturées à la construction du graphe, pas chaque tour. Le nœud lui-même
reste une fonction pure de l'état → un dict de delta. Ça nous donne :
- des tests faciles (on passe un fake LLM à la factory, on appelle la
  closure avec un state),
- un graphe construit une seule fois au démarrage et réutilisé,
- pas d'état global, pas de Singleton.

Format du retour : `dict[str, Any]` avec les seuls champs modifiés. C'est le
format que LangGraph attend pour les states pydantic + il rend les tests
plus précis (« ce nœud touche-t-il bien ce champ et seulement celui-là ? »).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from rag.interfaces import (
    Answer,
    Citation,
    CRAGState,
    Decision,
    GradedHit,
    LLMClient,
    RelevanceLabel,
    Retriever,
    SearchHit,
)
from rag.prompts import render
from rag.utils.logging import get_logger

_log = get_logger(__name__)

NodeFn = Callable[[CRAGState], dict[str, Any]]


# --- M4.2 : retrieve -------------------------------------------------------


def make_retrieve_node(retriever: Retriever, *, k: int = 5) -> NodeFn:
    """Factory du nœud `retrieve` : interroge le Retriever et stocke `hits`.

    Pas de filtres exposés ici : ils sont une fonctionnalité produit (M5)
    qui n'a pas besoin de passer par le graphe pour le POC.
    """

    def retrieve_node(state: CRAGState) -> dict[str, Any]:
        _log.info(
            "crag.retrieve",
            iteration=state.iteration,
            query=state.query,
            k=k,
        )
        hits = retriever.retrieve(query=state.query, k=k)
        # Reset graded_hits + refine state on every retrieval so a rewrite
        # loop never carries stale data from a previous iteration into decide
        # or generate.
        return {
            "hits": hits,
            "graded_hits": [],
            "refined_chunks": [],
            "used_chunk_ids": [],
        }

    return retrieve_node


# --- M4.3 + M4.6 : grade_and_refine (combined) ----------------------------

# Regex tolerante : extrait le premier objet JSON plat (sans braces imbriquées)
# dans la sortie du LLM, même si le modèle ajoute du texte autour.
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}", flags=re.DOTALL)


def _parse_grade_and_refine(raw: str) -> tuple[RelevanceLabel, str | None, str]:
    """Parse le JSON combiné grade+refine : retourne (label, reason, extracted).

    Robuste au bruit autour du JSON. En cas d'échec de parsing :
    - label → AMBIGUOUS (on ne rejette pas silencieusement un doc potentiellement utile)
    - extracted → "" (rien à injecter dans le prompt de génération)
    """
    match = _JSON_OBJECT_RE.search(raw)
    if not match:
        return RelevanceLabel.AMBIGUOUS, f"unparseable: {raw[:80]!r}", ""
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return RelevanceLabel.AMBIGUOUS, f"invalid json: {match.group(0)[:80]!r}", ""

    label_str = str(obj.get("label", "")).lower().strip()
    reason = obj.get("reason")
    reason_str = str(reason) if reason is not None else None
    extracted = str(obj.get("extracted", "")).strip()

    try:
        return RelevanceLabel(label_str), reason_str, extracted
    except ValueError:
        return RelevanceLabel.AMBIGUOUS, f"unknown label: {label_str!r}", extracted


def make_grade_and_refine_node(llm: LLMClient) -> NodeFn:
    """Factory du nœud `grade_and_refine` : grading + extraction en un seul appel LLM.

    Remplace les anciens nœuds `grade_documents` (M4.3) et `refine_knowledge`
    (M4.6) qui faisaient 2 x k appels séquentiels. Ici : k appels au total.

    Pour chaque hit :
    - le LLM classe le passage (relevant / ambiguous / irrelevant),
    - ET extrait les phrases utiles en même temps.
    Les hits IRRELEVANT n'alimentent pas `refined_chunks` (économie de tokens
    en génération).
    """

    def grade_and_refine_node(state: CRAGState) -> dict[str, Any]:
        graded: list[GradedHit] = []
        refined: list[str] = []
        used_ids: list[str] = []

        for hit in state.hits:
            prompt = render("grade_and_refine", query=state.query, doc=hit.text)
            raw = llm.generate(prompt, max_tokens=512)
            label, reason, extracted = _parse_grade_and_refine(raw)
            graded.append(GradedHit(hit=hit, label=label, reason=reason))
            if label is not RelevanceLabel.IRRELEVANT:
                # Fall back to the full hit text when the model fails to extract
                # (common with small models that label correctly but leave "extracted" empty).
                refined.append(extracted if extracted else hit.text)
                used_ids.append(hit.id)

        _log.info(
            "crag.grade_and_refine",
            iteration=state.iteration,
            n_hits=len(state.hits),
            n_relevant=sum(1 for g in graded if g.label is RelevanceLabel.RELEVANT),
            n_ambiguous=sum(1 for g in graded if g.label is RelevanceLabel.AMBIGUOUS),
            n_irrelevant=sum(1 for g in graded if g.label is RelevanceLabel.IRRELEVANT),
            n_refined=len(refined),
        )
        return {"graded_hits": graded, "refined_chunks": refined, "used_chunk_ids": used_ids}

    return grade_and_refine_node


# Helper exported for tests: construct a GradedHit without going through the LLM.
def _graded(hit: SearchHit, label: RelevanceLabel, reason: str | None = None) -> GradedHit:
    return GradedHit(hit=hit, label=label, reason=reason)


# --- M4.4 : decide ---------------------------------------------------------


def make_decide_node(*, min_relevant_fraction: float = 0.0) -> NodeFn:
    """Factory du nœud `decide` : pure logique, déterministe, sans LLM.

    Table de décision (les labels passent AVANT le quota d'itérations,
    parce que si on a du contenu pertinent, on génère, quel que soit
    le nombre de passes déjà faites) :

    1. Pas un seul `graded_hit` → FALLBACK (rien à juger, retrieval vide).
    2. Au moins un RELEVANT (et fraction ≥ `min_relevant_fraction`) → PROCEED.
       Indépendant de l'iteration : trouvé du pertinent → on l'exploite.
    3. 100 % IRRELEVANT → FALLBACK (aucune piste, rewrite ne sauvera rien).
    4. Sinon (mix ambiguous / irrelevant) : on AURAIT besoin d'un REWRITE.
       - si on a encore des itérations devant (`iteration < max_iterations`)
         → REWRITE.
       - sinon → FALLBACK (on a déjà tenté assez).

    `min_relevant_fraction` permet d'être plus strict (« il faut au moins
    20 % des hits classés relevant pour proceder »). Par défaut 0.0 :
    n'importe quel relevant déclenche PROCEED.
    """
    if not 0.0 <= min_relevant_fraction <= 1.0:
        raise ValueError("min_relevant_fraction doit être dans [0, 1]")

    def decide_node(state: CRAGState) -> dict[str, Any]:
        graded = state.graded_hits
        if not graded:
            _log.info("crag.decide", decision="fallback", reason="no_graded_hits")
            return {"decision": Decision.FALLBACK}

        n_total = len(graded)
        n_relevant = sum(1 for g in graded if g.label is RelevanceLabel.RELEVANT)
        n_irrelevant = sum(1 for g in graded if g.label is RelevanceLabel.IRRELEVANT)

        if n_relevant > 0 and (n_relevant / n_total) >= min_relevant_fraction:
            _log.info(
                "crag.decide",
                decision="proceed",
                n_relevant=n_relevant,
                n_total=n_total,
                iteration=state.iteration,
            )
            return {"decision": Decision.PROCEED}

        if n_irrelevant == n_total:
            _log.info("crag.decide", decision="fallback", reason="all_irrelevant")
            return {"decision": Decision.FALLBACK}

        # On voudrait réécrire — vérifie qu'il reste des passes autorisées.
        if state.iteration >= state.max_iterations:
            _log.info(
                "crag.decide",
                decision="fallback",
                reason="max_iterations",
                n_relevant=n_relevant,
                n_total=n_total,
            )
            return {"decision": Decision.FALLBACK}

        _log.info(
            "crag.decide",
            decision="rewrite",
            n_relevant=n_relevant,
            n_irrelevant=n_irrelevant,
            n_total=n_total,
            iteration=state.iteration,
        )
        return {"decision": Decision.REWRITE}

    return decide_node


# --- M4.5 : rewrite_query --------------------------------------------------


def _clean_rewrite_output(raw: str) -> str:
    """Nettoie la sortie du LLM pour le rewrite (1 seule ligne)."""
    # On prend la première ligne non vide, on enlève les guillemets éventuels.
    for line in raw.splitlines():
        line = line.strip().strip('"').strip("'")
        if line:
            return line
    return raw.strip()


def make_rewrite_query_node(llm: LLMClient) -> NodeFn:
    """Factory du nœud `rewrite_query` : reformule la question, incrémente l'iter."""

    def rewrite_query_node(state: CRAGState) -> dict[str, Any]:
        prompt = render("rewrite_query", query=state.query)
        raw = llm.generate(prompt, max_tokens=200)
        rewritten = _clean_rewrite_output(raw)
        # Garde-fou : si la sortie LLM est vide, on ne casse pas la query.
        if not rewritten:
            rewritten = state.query
        new_iter = state.iteration + 1
        _log.info(
            "crag.rewrite_query",
            iteration=new_iter,
            before=state.query,
            after=rewritten,
        )
        return {"query": rewritten, "iteration": new_iter}

    return rewrite_query_node


# --- M4.7 : generate -------------------------------------------------------


# Regex pour récupérer les marqueurs de citation [1], [12], … dans la réponse.
_CITATION_RE = re.compile(r"\[(\d+)\]")


def _extract_citation_indices(text: str) -> list[int]:
    """Retourne les indices 1-based uniques cités dans l'ordre d'apparition."""
    seen: dict[int, None] = {}  # dict pour préserver l'ordre d'insertion
    for m in _CITATION_RE.finditer(text):
        idx = int(m.group(1))
        if idx not in seen:
            seen[idx] = None
    return list(seen.keys())


def _citation_from_hit(hit: SearchHit) -> Citation:
    """Construit une `Citation` à partir des metadata d'un hit (parent hydraté)."""
    meta = hit.metadata
    source = str(meta.get("source_file", "unknown"))
    raw_page = meta.get("page")
    page = int(raw_page) if isinstance(raw_page, int) else None
    return Citation(source_file=source, page=page, chunk_id=hit.id)


def make_generate_node(llm: LLMClient) -> NodeFn:
    """Factory du nœud `generate` : prompt avec citations forcées → `Answer`.

    On suppose que `grade_and_refine` a déjà filtré les chunks et rempli
    `used_chunk_ids` dans le même ordre que `refined_chunks`. Le mapping
    [n] (1-based) → chunk_id est donc trivial.
    """

    def generate_node(state: CRAGState) -> dict[str, Any]:
        if not state.refined_chunks:
            # Pas de matière → on bascule en fallback via le graphe ; ici on
            # ne fabrique pas d'answer pour ne pas masquer le no-answer.
            return {"answer": None}

        prompt = render("generate", query=state.query, chunks=state.refined_chunks)
        text = llm.generate(prompt).strip()

        # Construit l'index chunk_id → SearchHit pour récupérer source_file/page.
        id_to_hit: dict[str, SearchHit] = {g.hit.id: g.hit for g in state.graded_hits}

        citations: list[Citation] = []
        for idx in _extract_citation_indices(text):
            # idx est 1-based ; on convertit en 0-based pour indexer used_chunk_ids.
            if 1 <= idx <= len(state.used_chunk_ids):
                chunk_id = state.used_chunk_ids[idx - 1]
                hit = id_to_hit.get(chunk_id)
                if hit is not None:
                    citations.append(_citation_from_hit(hit))

        answer = Answer(
            text=text,
            citations=citations,
            grounded=False,  # le nœud ground_check (M4.9) confirmera
            used_chunks=list(state.used_chunk_ids),
        )
        _log.info(
            "crag.generate",
            chars=len(text),
            n_citations=len(citations),
        )
        return {"answer": answer}

    return generate_node


# --- M4.9 : ground_check ---------------------------------------------------


# Split sur fin de phrase. On garde les ponctuations terminales attachées au
# bout précédent. Pas un parseur, c'est une heuristique POC.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Mots vides FR + EN, minuscules. Volontairement court : on ne veut pas
# overfit le grounding sur des mots fonctionnels.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "de",
        "du",
        "et",
        "ou",
        "à",
        "au",
        "aux",
        "en",
        "dans",
        "sur",
        "par",
        "pour",
        "avec",
        "sans",
        "ce",
        "cette",
        "ces",
        "est",
        "sont",
        "qui",
        "que",
        "quoi",
        "se",
        "son",
        "sa",
        "ses",
        "ne",
        "pas",
        "the",
        "a",
        "an",
        "of",
        "and",
        "or",
        "in",
        "on",
        "for",
        "with",
        "without",
        "is",
        "are",
        "was",
        "were",
        "this",
        "that",
        "these",
        "those",
        "to",
        "from",
    }
)


def _tokens(text: str) -> set[str]:
    """Tokens content-words : alphanum minuscule, hors stopwords."""
    return {
        t
        for t in re.findall(r"\w+", text.lower(), flags=re.UNICODE)
        if t not in _STOPWORDS and len(t) > 1
    }


def _split_sentences(text: str) -> list[str]:
    """Découpe en phrases via une regex simple (POC)."""
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]


def _is_grounded(claim: str, chunks: list[str], *, min_overlap: float) -> bool:
    """Une claim est groundée si au moins un chunk partage `min_overlap`
    de ses tokens content-words.
    """
    claim_tokens = _tokens(claim)
    if not claim_tokens:
        # Phrase vide après stopword-stripping (ex. « C'est ça. ») : on la
        # considère trivialement groundée — sinon on punirait les transitions.
        return True
    needed = max(1, round(min_overlap * len(claim_tokens)))
    return any(len(claim_tokens & _tokens(chunk)) >= needed for chunk in chunks)


def make_ground_check_node(*, min_overlap: float = 0.3) -> NodeFn:
    """Factory du nœud `ground_check` : valide chaque phrase de l'answer.

    Si toutes les phrases de réponse partagent au moins `min_overlap` de
    tokens content-words avec au moins un chunk utilisé, on marque
    `answer.grounded = True`. Sinon False. La réponse n'est PAS modifiée :
    c'est au caller (ou à un nœud futur) de décider quoi en faire.

    Pourquoi pas un embedder : on évite une dep et une latence supplémentaire
    pour un check qui n'a besoin d'être qu'indicatif au POC. L'éval M6
    confirmera si on a besoin d'un grounding sémantique plus fin.
    """
    if not 0.0 <= min_overlap <= 1.0:
        raise ValueError("min_overlap doit être dans [0, 1]")

    def ground_check_node(state: CRAGState) -> dict[str, Any]:
        if state.answer is None:
            return {}
        sentences = _split_sentences(state.answer.text)
        if not sentences:
            return {}
        all_grounded = all(
            _is_grounded(s, state.refined_chunks, min_overlap=min_overlap) for s in sentences
        )
        updated = state.answer.model_copy(update={"grounded": all_grounded})
        _log.info(
            "crag.ground_check",
            grounded=all_grounded,
            n_sentences=len(sentences),
        )
        return {"answer": updated}

    return ground_check_node


# --- M4.10 : fallback_no_answer -------------------------------------------


# Message standard, en français car notre domaine est francophone par défaut.
# Pas dans un .j2 : c'est une chaîne fixe, pas un prompt — pas d'interpolation.
FALLBACK_MESSAGE = (
    "Je ne sais pas répondre à cette question à partir des documents disponibles. "
    "Si tu peux préciser ta question ou fournir un contexte supplémentaire, je peux retenter."
)


def make_fallback_no_answer_node() -> NodeFn:
    """Factory du nœud `fallback_no_answer`.

    On rend un `Answer` explicite plutôt qu'un `None` pour deux raisons :
    1. le caller (API, CLI, eval) reçoit un objet typé homogène,
    2. on peut tracer dans Langfuse / logs que le pipeline a échoué proprement,
       distinct d'un crash.
    """

    def fallback_node(state: CRAGState) -> dict[str, Any]:
        _log.info(
            "crag.fallback_no_answer",
            iteration=state.iteration,
            n_graded=len(state.graded_hits),
        )
        answer = Answer(
            text=FALLBACK_MESSAGE,
            citations=[],
            grounded=True,  # « je ne sais pas » est par définition non-halluciné
            used_chunks=[],
        )
        return {"answer": answer, "fallback_triggered": True}

    return fallback_node
