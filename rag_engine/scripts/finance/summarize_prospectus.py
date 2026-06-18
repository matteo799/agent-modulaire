#!/usr/bin/env python3
"""Résumé structuré des prospectus financiers via le RAG hybride.

Use-case spécifique finance — isolé du cœur RAG.
Les templates Jinja2 vivent dans scripts/finance/prompts/, pas dans src/rag/prompts/.

Approche : un appel LLM par groupe de 2-4 champs (réponse courte) + extraction
regex pour les champs à format normalisé (SFDR, SRI, frais…).

Prérequis :
    python -m rag.ingestion.cli  (source par défaut : documents/finance)
    LLM : Ollama configuré dans configs/

Usage :
    python scripts/finance/summarize_prospectus.py
    python scripts/finance/summarize_prospectus.py --src ../documents/finance --output data/fund_summaries.csv
    python scripts/finance/summarize_prospectus.py --k 5 --model SetneufPT/ccode79_2b_q4_64k_8gb-gpu:latest
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import re
import sys

# Extracteur règle-based (sans LLM) — première passe sur tous les champs déterministes.
import sys as _sys
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import pymupdf  # lecture PDF directe — utilisé pour SFDR context-aware
from jinja2 import Environment, FileSystemLoader, StrictUndefined

_sys.path.insert(0, str(Path(__file__).resolve().parent))
from prospectus_extractor import ProspectusExtractor
from rag.adapters.vector_stores.qdrant_store import QdrantVectorStore
from rag.config.factory import build_doc_store, build_embedder, build_llm, build_vector_store
from rag.config.settings import load_settings
from rag.interfaces import Retriever
from rag.interfaces.types import ChildChunk, ChunkMetadata
from rag.retrieval.bm25 import BM25Retriever
from rag.retrieval.dense import DenseRetriever
from rag.retrieval.hybrid import HybridRetriever
from rag.retrieval.parent_child import ParentChildRetriever
from rag.utils.logging import configure_logging, get_logger

_log = get_logger(__name__)

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROMPTS_DIR = _SCRIPT_DIR / "prompts"
# Source unique des prospectus : documents/finance à la racine du dépôt (calculé
# depuis l'emplacement du script pour être indépendant du cwd).
_DEFAULT_SRC = _SCRIPT_DIR.parents[2] / "documents" / "finance"
_DEFAULT_OUTPUT = Path("data/fund_summaries.csv")
_DEFAULT_K = 5


# ── rendu Jinja2 local (ne touche pas à rag.prompts) ─────────────────────────


@lru_cache(maxsize=1)
def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR)),
        autoescape=False,
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _render(name: str, **kwargs: Any) -> str:
    return _jinja_env().get_template(f"{name}.j2").render(**kwargs)


# ── champs et groupes ─────────────────────────────────────────────────────────

_FIELDS = [
    "fonds",
    "code_fonds",
    "isin",
    "societe_gestion",
    "structure",
    "categorie",
    "univers",
    "benchmark",
    "gestion",
    "devise",
    "date_creation",
    "actif_net",
    "depositaire",
    "horizon_recommande",
    "sfdr_article",
    "priips_sri",
    "esg_estime",
    "classe_esg",
    "pea",
    "per",
    "perco",
    "pee",
    "exposition_usa",
    "style_dominant",
    "small_caps",
    "mega_caps_tech",
    "nombre_lignes",
    "risque_devise",
    "frais_entree_max",
    "frais_gestion_annuels",
    "frais_sortie",
    "commission_surperformance",
]

# Groupes LLM — uniquement les champs sémantiques que l'extracteur règle-based ne couvre pas.
# L'extracteur (prospectus_extractor.py) gère déjà : fonds, ISIN, société, structure,
# dépositaire, devise, catégorie, benchmark, SRI, horizon, frais, SFDR, ESG.
_FIELD_GROUPS: list[dict[str, Any]] = [
    {
        "fields": ["categorie", "univers", "gestion"],
        "query": "catégorie AMF classification univers investissement zones géographiques types actifs gestion active passive indicielle",
        "question": "Quelle est la catégorie AMF exacte (ex: 'Actions internationales', 'Obligations zone euro', 'Monétaire', 'FCPE Actions zone EURO') ? NE PAS mettre SFDR ni du texte juridique. Quel est l'univers d'investissement en une phrase simple (zones, types d'actifs) ? La gestion est-elle Active, Indiciel ou Discrétionnaire ? Réponds avec des chaînes de texte simples, pas des objets JSON imbriqués.",
        "schema": '{"categorie": "ex: Actions internationales", "univers": "ex: Actions européennes cotées de toutes capitalisations", "gestion": "Actif/Indiciel/Passif/Discrétionnaire"}',
    },
    {
        "fields": ["pea", "per", "perco", "pee"],
        "query": "PEA plan épargne actions PER retraite PERCO PEE épargne salariale entreprise éligible",
        "question": "Le fonds est-il éligible au PEA ? Au PER ? Au PERCO ? Au PEE (épargne salariale) ?",
        "schema": '{"pea": "Oui/Non", "per": "Oui/Non/N/A", "perco": "Oui/Non/N/A", "pee": "Oui/Non/N/A"}',
    },
    {
        "fields": [
            "exposition_usa",
            "style_dominant",
            "small_caps",
            "mega_caps_tech",
            "nombre_lignes",
        ],
        "query": "exposition États-Unis USA Amérique style valeur croissance blend small cap petites capitalisations méga technologie nombre lignes portefeuille titres",
        "question": "Quelle est l'exposition aux États-Unis ? Le style dominant (Croissance/Valeur/Blend) ? Y a-t-il des small caps ? Des méga caps tech ? Combien de lignes en portefeuille ?",
        "schema": '{"exposition_usa": "X% ou N/A", "style_dominant": "Croissance/Valeur/Blend/N/A", "small_caps": "Oui/Non/N/A", "mega_caps_tech": "Oui/Non/N/A", "nombre_lignes": "N ou N/A"}',
    },
    {
        "fields": ["actif_net", "risque_devise", "classe_esg"],
        "query": "actif net encours total milliards millions risque change devise couvert classe ESG notation",
        "question": "Quel est l'actif net ou encours du fonds ? Le risque de change est-il couvert ? Y a-t-il une classe ESG (A/B/C/D/E) ?",
        "schema": '{"actif_net": "X M EUR ou N/A", "risque_devise": "Couvert/Non couvert/Partiel/N/A", "classe_esg": "A/B/C/D/E ou N/A"}',
    },
]


# ── extraction première passe (règle-based, sans LLM) ────────────────────────


def _pdf_text(pdf_path: Path) -> str:
    doc = pymupdf.open(pdf_path)
    return " ".join(page.get_text() for page in doc)


def _extractor_to_row(pdf_path: Path) -> dict[str, str]:
    """Première passe : ProspectusExtractor règle-based sur le PDF complet.

    Couvre ~18 champs déterministes sans LLM (ISIN, frais, SRI, SFDR, dépositaire…).
    Retourne uniquement les champs trouvés (valeur non-vide) ; les champs manquants
    restent à la charge du LLM ou du SFDR contextuel ci-dessous.
    """
    try:
        ext = ProspectusExtractor(str(pdf_path))
        d = ext.extract_all()
    except Exception:
        return {}

    def _v(val: Any) -> str:
        s = str(val).strip() if val else ""
        return s if s else "N/A"

    # Frais gestion annuels : préférence PRIIPS frais_courants > frais_fonctionnement > frais_gestion
    frais_g = next(
        (f for f in [d.frais_courants, d.frais_fonctionnement, d.frais_gestion] if f), None
    )

    # SRI : "4 / 7" → "4" — valide que c'est bien un chiffre 1-7
    sri_raw = _v(d.sri or d.srri)
    sri_candidate = sri_raw.split("/")[0].strip() if "/" in sri_raw else sri_raw
    sri = sri_candidate if re.match(r"^[1-7]$", sri_candidate) else "N/A"

    # ESG : combine approche + investissements durables
    esg_parts = [p for p in [d.approche_esg, d.investissements_durables_min] if p]
    esg = " / ".join(esg_parts) if esg_parts else "N/A"

    # Détecte FCPE depuis le texte complet du PDF (forme_juridique seul pas toujours fiable)
    try:
        _full = _pdf_text(pdf_path)
    except Exception:
        _full = str(d.forme_juridique or "") + str(d.type_produit or "")
    is_fcpe = bool(
        re.search(
            r"\bFCPE\b|Fonds Commun de Placement d.Entreprise|épargne salariale",
            _full,
            re.IGNORECASE,
        )
    )

    row: dict[str, str] = {}
    mapping = {
        "fonds": _v(d.nom_produit),
        "code_fonds": _v(d.identifiant),
        "isin": _v(d.isin),
        "societe_gestion": _v(d.societe_gestion),
        "structure": _v(d.forme_juridique),
        "categorie": _v(d.classification),
        "devise": _v(d.devise),
        "date_creation": _v(d.date_document),
        "depositaire": _v(d.depositaire),
        "horizon_recommande": _v(d.periode_detention),
        "sfdr_article": _v(d.classification_sfdr),
        "priips_sri": sri,
        "esg_estime": esg,
        "frais_entree_max": _v(d.commission_souscription),
        "frais_gestion_annuels": _v(frais_g),
        "frais_sortie": _v(d.commission_rachat),
        "commission_surperformance": _v(d.commission_surperformance),
        "benchmark": _v(d.indice_reference),
        # FCPE : par définition éligible PEE/PERCO/PER, non éligible PEA
        "pee": "Oui" if is_fcpe else "N/A",
        "perco": "Oui" if is_fcpe else "N/A",
        "per": "Oui" if is_fcpe else "N/A",
        "pea": "Non" if is_fcpe else "N/A",
    }
    for field, value in mapping.items():
        if value and value != "N/A":
            row[field] = value

    # ── Nettoyages post-extraction ─────────────────────────────────────────────

    # 1. Société de gestion — rejette phrases parasites
    if "societe_gestion" in row:
        sg = re.sub(
            r"^(?:du PRIIP|Nom[^:]*|Initiateur[^:]*)\s*:\s*",
            "",
            row["societe_gestion"],
            flags=re.IGNORECASE,
        ).strip()
        if (
            re.search(
                r"\binforme\b|\brisques?\b|\bdont\b|investisseur|tient\s+a|portefeuille\b|dispose\b|et le pourcentage|par la Commiss|de portefeuille par",
                sg,
                re.IGNORECASE,
            )
            or len(sg) < 4
            or len(sg) > 70
        ):
            del row["societe_gestion"]
        else:
            row["societe_gestion"] = sg

    # 2. Nom du fonds — rejette adresses et textes parasites
    if "fonds" in row:
        f = re.sub(r'^[:\s«»"\']+|[«»"\']+$', "", row["fonds"]).strip()
        # Rejette si contient une adresse (rue, numéro postal, cedex, m²...)
        if (
            re.search(
                r"\d{4,5}|\brue\b|\bavenue\b|\bcedex\b|\bsociete anonyme\b|\bfinancier sont\b",
                f,
                re.IGNORECASE,
            )
            or len(f) < 3
        ):
            del row["fonds"]
        else:
            row["fonds"] = f

    # 3. ISIN — valide que l'ISIN extrait correspond au nom du fichier quand possible
    if "isin" in row:
        isin = row["isin"]
        # Le nom de fichier contient souvent l'ISIN correct
        if re.match(r"^[A-Z]{2}\d{10}$", pdf_path.stem.upper()):
            expected = pdf_path.stem.upper()
            if isin.upper() != expected:
                row["isin"] = expected  # priorité au nom de fichier
        # Rejette si l'ISIN est une liste JSON ou contient des crochets
        if isin.startswith("[") or isin.startswith("{"):
            del row["isin"]

    # 4. Structure — préfère la forme spécifique (FCP, SCPI…) à la forme générique (OPCVM, FIA)
    if "structure" in row:
        s = row["structure"]
        if len(s) < 3:
            del row["structure"]
        # "OPCVM" et "FIA" sont trop génériques — le LLM peut trouver mieux
        elif s.upper() in ("OPCVM", "FIA", "ETF") and row.get("fonds", "N/A") != "N/A":
            pass  # trop générique mais on garde — le LLM peut affiner

    # 5. Frais entrée — rejette montants EUR sans %
    if "frais_entree_max" in row and (
        re.search(r"\d+\s*(?:EUR|€)\s*$", row["frais_entree_max"], re.IGNORECASE)
        and "%" not in row["frais_entree_max"]
    ):
        del row["frais_entree_max"]

    # 6. Benchmark — rejette textes non-financiers
    if "benchmark" in row:
        b = row["benchmark"]
        if re.search(
            r"derni[èe]res ann[ée]es|sc[eé]nario|p[eé]riode d.analyse|indicateur synth[eé]tique|risque ne tient|est anticip[eé]|niveau de risque|port[ef]|ou dans celle de|capacit[eé] de",
            b,
            re.IGNORECASE,
        ) or not re.search(r"[A-Z]{2,}|%|\d|sans benchmark", b, re.IGNORECASE):
            del row["benchmark"]

    return row


def _sfdr_contextuel(pdf_path: Path) -> str:
    """SFDR via contexte pymupdf - extraction context-aware sur les prospectus longs."""
    text = _pdf_text(pdf_path)
    sfdr_ctx = ""
    for trigger in [r"2019/2088", r"\bSFDR\b", r"R[èe]glement\s+Disclosure"]:
        m = re.search(trigger, text, re.IGNORECASE)
        if m:
            s, e = max(0, m.start() - 200), min(len(text), m.end() + 200)
            sfdr_ctx += " " + text[s:e]
    if sfdr_ctx:
        for article, patterns in [
            ("Article 9", [r"article\s+9\b"]),
            ("Article 8", [r"article\s+8\b", r"promeut\s+des\s+crit[èe]res\s+esg"]),
            ("Article 6", [r"article\s+6\b"]),
        ]:
            if any(re.search(p, sfdr_ctx, re.IGNORECASE) for p in patterns):
                return article
    return "N/A"


def _regex_extract(texts: list[str], pdf_path: Path | None = None) -> dict[str, str]:
    """Conservé pour compatibilité — maintenant appelle _sfdr_contextuel uniquement."""
    sfdr = _sfdr_contextuel(pdf_path) if pdf_path else "N/A"
    return {"sfdr_article": sfdr} if sfdr != "N/A" else {}


# ── helpers JSON ──────────────────────────────────────────────────────────────


def _parse_json(raw: str, fields: list[str]) -> dict[str, str]:
    for attempt in [raw.strip(), _strip_code_block(raw), _first_balanced_json(raw)]:
        if not attempt:
            continue
        try:
            data: dict[str, Any] = json.loads(attempt)
            return {f: str(data.get(f, "N/A")).strip() for f in fields}
        except (json.JSONDecodeError, ValueError):
            pass
    return {f: "N/A" for f in fields}


def _strip_code_block(text: str) -> str:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    return m.group(1) if m else ""


def _first_balanced_json(text: str) -> str:
    start = text.find("{")
    if start == -1:
        return ""
    depth, in_string, escape = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return ""


def _hits_to_children(hits: Any) -> list[ChildChunk]:
    children: list[ChildChunk] = []
    for hit in hits:
        meta_dict = dict(hit.metadata)
        parent_id = str(meta_dict.pop("parent_id", ""))
        if not parent_id:
            continue
        for k, v in meta_dict.items():
            if isinstance(v, str) and v and v[0] in ("{", "["):
                with contextlib.suppress(json.JSONDecodeError):
                    meta_dict[k] = json.loads(v)
        try:
            metadata = ChunkMetadata.model_validate(meta_dict)
        except Exception:
            continue
        children.append(
            ChildChunk(id=hit.id, parent_id=parent_id, text=hit.text, metadata=metadata)
        )
    return children


# ── main ──────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    arg_parser = argparse.ArgumentParser(description=__doc__)
    arg_parser.add_argument("--src", type=Path, default=_DEFAULT_SRC)
    arg_parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    arg_parser.add_argument("--k", type=int, default=_DEFAULT_K)
    arg_parser.add_argument(
        "--model", type=str, default=None, help="Override modèle (Ollama) ou vide pour LM Studio"
    )
    arg_parser.add_argument(
        "--provider", type=str, default=None, help="Provider LLM : ollama | lmstudio"
    )
    arg_parser.add_argument("--verbose", action="store_true")
    args = arg_parser.parse_args(argv)

    repo_root = _SCRIPT_DIR.parent.parent  # scripts/finance/ → scripts/ → RAG/
    src = args.src if args.src.is_absolute() else repo_root / args.src
    output = args.output if args.output.is_absolute() else repo_root / args.output

    if not src.is_dir():
        print(f"ERREUR : répertoire introuvable : {src}", file=sys.stderr)
        return 2
    pdfs = sorted(p for p in src.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
    if not pdfs:
        print(f"ERREUR : aucun PDF trouvé dans {src}", file=sys.stderr)
        return 2

    configure_logging(level="INFO")
    settings = load_settings(repo_root / "configs")
    settings.retrieval.hybrid_enabled = True
    settings.reranker.enabled = False
    settings.retrieval.dense_k = args.k
    settings.retrieval.bm25_k = args.k
    settings.llm.ollama.timeout_s = 300.0
    settings.llm.lmstudio.timeout_s = 300.0
    if args.provider:
        settings.llm.provider = args.provider  # type: ignore[assignment]
    if args.model is not None:  # "" = vide = modèle chargé dans LM Studio
        if settings.llm.provider == "lmstudio":
            settings.llm.lmstudio.model = args.model
        else:
            settings.llm.ollama.model = args.model

    model_name = (
        settings.llm.lmstudio.model or "chargé dans LM Studio"
        if settings.llm.provider == "lmstudio"
        else settings.llm.ollama.model
    )
    print(f"== Résumé de {len(pdfs)} prospectus — k={args.k}")
    print(f"   LLM : {settings.llm.provider} / {model_name}")

    embedder = build_embedder(settings)
    vector_store = build_vector_store(settings)
    doc_store = build_doc_store(settings)
    llm = build_llm(settings)

    if not isinstance(vector_store, QdrantVectorStore):
        print("ERREUR : vector store non Qdrant", file=sys.stderr)
        return 3

    # Charge tous les chunks une seule fois et les groupe par document.
    # Pour chaque PDF, le BM25 ne voit que ses ~150 chunks — pas les 12k de la collection.
    print("Indexation par document...", flush=True)
    all_children = _hits_to_children(vector_store.scroll_all())
    children_by_doc: dict[str, list[ChildChunk]] = {}
    for c in all_children:
        children_by_doc.setdefault(c.metadata.source_file, []).append(c)
    print(f"  {len(all_children)} chunks — {len(children_by_doc)} documents")

    dense_global: Retriever = cast(
        Retriever, DenseRetriever(embedder=embedder, vector_store=vector_store)
    )

    # Reprise : charge les lignes déjà traitées dans le CSV de sortie.
    already_done: dict[str, dict[str, str]] = {}
    columns = ["source_file", *_FIELDS]
    if output.exists():
        with output.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                already_done[row["source_file"]] = row
        print(f"  {len(already_done)} PDFs déjà dans le CSV — reprise depuis le dernier arrêt")

    results: list[dict[str, str]] = list(already_done.values())
    pending = [p for p in pdfs if p.name not in already_done]
    print(f"  {len(pending)} PDFs restants à traiter\n")

    # Ouvre le CSV en mode append pour écrire immédiatement après chaque PDF.
    output.parent.mkdir(parents=True, exist_ok=True)
    csv_file = output.open("a", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(csv_file, fieldnames=columns)
    if not already_done:  # nouveau fichier : écrit l'en-tête
        csv_writer.writeheader()

    for pdf in pending:
        print(f"\n--- {pdf.name} ---", flush=True)
        source_filter: dict[str, Any] = {"source_file": pdf.name}

        # BM25 sur les seuls chunks de CE document (~150 chunks, pas 12k).
        doc_children = children_by_doc.get(pdf.name, [])
        bm25_doc: Retriever = cast(
            Retriever, BM25Retriever(doc_children if doc_children else all_children)
        )
        hybrid_doc: Retriever = cast(
            Retriever,
            HybridRetriever(
                sources=[(dense_global, args.k), (bm25_doc, args.k)],
                rrf_constant=settings.retrieval.hybrid_rrf_constant,
            ),
        )
        retriever: Retriever = cast(
            Retriever, ParentChildRetriever(inner=hybrid_doc, doc_store=doc_store)
        )

        broad_hits = retriever.retrieve(
            query="caractéristiques fonds ISIN frais gestion structure dépositaire horizon",
            k=args.k,
            filters=source_filter,
        )
        if not broad_hits:
            print("  AVERTISSEMENT : aucun chunk")
            results.append({"source_file": pdf.name, **{f: "N/A" for f in _FIELDS}})
            continue

        # ── Passe 1 : extracteur règle-based (sans LLM) ──────────────────────────
        row: dict[str, str] = _extractor_to_row(pdf)
        # Override SFDR avec notre version context-aware (plus robuste sur les prospectus longs)
        sfdr_ctx = _sfdr_contextuel(pdf)
        if sfdr_ctx != "N/A":
            row["sfdr_article"] = sfdr_ctx

        if args.verbose:
            print(
                f"  [extracteur] fonds={row.get('fonds', '?')} | ISIN={row.get('isin', '?')} | SFDR={row.get('sfdr_article', '?')} | SRI={row.get('priips_sri', '?')}"
            )

        # ── Passe 2 : LLM uniquement pour les champs sémantiques restants ───────
        for g_idx, group in enumerate(_FIELD_GROUPS, 1):
            k_group = group.get("k_override", args.k)
            targeted = retriever.retrieve(query=group["query"], k=k_group, filters=source_filter)
            chunks = [h.text for h in targeted] if targeted else [h.text for h in broad_hits]
            try:
                prompt = _render(
                    "extract_fund_field",
                    chunks=chunks,
                    question=group["question"],
                    schema=group["schema"],
                    filename=pdf.name,
                )
                raw = llm.generate(prompt, max_tokens=256, think=False)
                extracted = _parse_json(raw, group["fields"])
            except Exception as exc:
                _log.warning("group_failed", group=g_idx, error=str(exc))
                extracted = {f: "ERREUR" for f in group["fields"]}
            row.update(extracted)
            if args.verbose:
                for f in group["fields"]:
                    print(f"  [{g_idx}] {f:30s}: {row[f]}")

        # Post-traitement champs LLM — nettoie les dicts Python sérialisés et les valeurs aberrantes
        for field in list(row.keys()):
            v = row[field]
            if not v or v == "N/A":
                continue
            # Rejette si le LLM a retourné un dict/liste Python sérialisé
            if v.startswith("{") or v.startswith("[") or v.startswith("'"):
                row[field] = "N/A"
                continue
            # Nettoie les valeurs trop longues (>120 chars = phrase parasite)
            if len(v) > 120 and field not in ("univers", "objectif_gestion"):
                row[field] = v[:120].rsplit(" ", 1)[0]

        # Override extracteur sur les champs regex — fiabilité 100%
        for field, value in _regex_extract([], pdf_path=pdf).items():
            if value != "N/A":
                row[field] = value

        print(f"  fonds    : {row.get('fonds', 'N/A')}")
        print(f"  ISIN     : {row.get('isin', 'N/A')}")
        print(f"  structure: {row.get('structure', 'N/A')}")
        print(f"  soc.gest.: {row.get('societe_gestion', 'N/A')}")
        print(f"  frais    : {row.get('frais_gestion_annuels', 'N/A')}")
        print(f"  SFDR     : {row.get('sfdr_article', 'N/A')}")
        print(f"  SRI      : {row.get('priips_sri', 'N/A')}")

        new_row = {"source_file": pdf.name, **{f: row.get(f, "N/A") for f in _FIELDS}}
        results.append(new_row)
        csv_writer.writerow(new_row)
        csv_file.flush()  # écrit immédiatement sur disque

    csv_file.close()
    print(f"\n== CSV : {output}  ({len(results)} lignes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
