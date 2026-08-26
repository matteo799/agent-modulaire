"""Ablation architecturale : quel composant agentique paie réellement ?

Usage :
    python tests/agent_eval/run_ablation.py [--arms A,B,C,D,E] [--set fichier.yaml] [--limit N]

Fait passer LES MÊMES questions par cinq architectures, de la récupération nue à
l'agent complet, et mesure ce que chaque composant ajoute :

    A  rag_only        un seul rag_search, puis synthèse ancrée. Pas de planner,
                       pas de boucle. C'est la référence basse.
    B  rag_tools       un unique tour de sélection d'outil sur la question, puis
                       synthèse. L'agent peut choisir un outil, mais ne planifie pas.
    C  planner         planification + boucle d'exécution, SANS correction
                       (max_retries=0). Isole l'apport de la planification.
    D  full            C + réflexion déterministe et une reprise par étape.
                       C'est la configuration de production.
    E  full_llm_judge  D, mais la réflexion déterministe est remplacée par un juge
                       LLM. Mesure le choix écarté en conception (design-decisions §5).

A→B isole l'outillage, B→C la planification, C→D la boucle de correction, D→E le
coût d'un juge sémantique. La sécurité, la synthèse ancrée et le garde-fou
hors-corpus sont IDENTIQUES sur tous les bras : on compare des architectures, pas
des garde-fous.

Métriques, toutes DÉTERMINISTES (aucun juge LLM dans la notation, donc aucun coût
et aucune circularité) :

  - couverture d'outils   : expected_tools ⊆ outils réellement appelés ;
  - refus correct         : sur les questions hors-corpus, la réponse refuse-t-elle ?
  - ancrage numérique     : proxy d'hallucination — chaque nombre de la réponse
                            finale apparaît-il dans un résultat d'outil ou dans la
                            question ? Un nombre non retrouvé est « non étayé » ;
  - latence, tokens, taux d'échec.

L'ancrage numérique est un PROXY et non une mesure de justesse : il détecte un
chiffre sorti de nulle part, pas un chiffre correct utilisé au mauvais endroit.
La limite est assumée et rappelée dans le rapport.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from agent import executor, llm, security  # noqa: E402
from agent.llm import LLMUnavailable  # noqa: E402
from agent.planner import make_plan  # noqa: E402
from agent.rag_adapter import rag_search  # noqa: E402

DEFAULT_SET = HERE / "question_test.yaml"
REPORTS_DIR = HERE / "reports"

# Marqueurs de refus produits par la synthèse ancrée et les outils. Sert à vérifier
# qu'une question hors-corpus se solde bien par un refus plutôt que par une réponse
# tirée des connaissances générales du modèle.
REFUSAL_MARKERS = (
    "ne permettent pas de répondre",
    "aucun passage pertinent",
    "ne permet pas de répondre",
    "je ne sais pas répondre",
    "n'est pas couvert",
    "ne figure pas",
    "aucune information",
    "aucune donnée",
    "hors du périmètre",
    "hors périmètre",
)


def _is_refusal(answer: str) -> bool:
    low = (answer or "").lower()
    return any(m in low for m in REFUSAL_MARKERS)


def _numbers(text: str) -> list[str]:
    """Nombres normalisés d'un texte, pour comparer réponse et sources.

    Les entiers < 10 sont ignorés : ce sont massivement des numéros d'étape, de
    liste ou d'échelle (SRI sur 7…), et leur présence fortuite dans les sources
    rendrait la mesure ininterprétable.
    """
    out = []
    for raw in re.findall(r"\d[\d\s ]*(?:[.,]\d+)?", text or ""):
        cleaned = raw.replace(" ", "").replace(" ", "").replace(",", ".")
        cleaned = cleaned.rstrip(".")
        if not cleaned:
            continue
        try:
            val = float(cleaned)
        except ValueError:
            continue
        if abs(val) < 10 and val == int(val):
            continue
        out.append(f"{val:.6f}".rstrip("0").rstrip("."))
    return out


def _ungrounded_numbers(answer: str, sources: str, question: str) -> list[str]:
    """Nombres de la réponse absents des sources ET de la question."""
    haystack = set(_numbers(sources)) | set(_numbers(question))
    return [n for n in _numbers(answer) if n not in haystack]


# ── Les cinq bras ────────────────────────────────────────────────────────────
# Chacun renvoie (réponse, mémoire). La mémoire est la liste d'étapes exécutées,
# au format de l'executor, ce qui permet de réutiliser la synthèse et les mesures.


def _synthesize(user_query: str, memory: list[dict]) -> str:
    from main import synthesize  # import tardif : main importe l'agent complet

    return synthesize(user_query, memory)


def arm_rag_only(question: str) -> tuple[str, list[dict]]:
    result = rag_search(question)
    memory = [{"step": question, "tool": "rag_search", "result": result, "args": {}, "raison": ""}]
    return _synthesize(question, memory), memory


def arm_rag_tools(question: str) -> tuple[str, list[dict]]:
    choice = executor.choose_tool(question, question, [])
    result = executor.execute_step(choice)
    entry = {
        "step": question,
        "tool": choice.get("tool", "?"),
        "result": result,
        "args": choice.get("args") or {},
        "raison": choice.get("raison", ""),
    }
    if entry["tool"] == "write_file" and not result.startswith("Erreur"):
        entry["content"] = (choice.get("args") or {}).get("content", "")
    return _synthesize(question, [entry]), [entry]


def _planned(question: str, max_retries: int, reflect_fn) -> tuple[str, list[dict]]:
    plan = make_plan(question)
    memory = executor.run(question, plan, max_retries=max_retries, reflect_fn=reflect_fn)
    return _synthesize(question, memory), memory


def arm_planner(question: str) -> tuple[str, list[dict]]:
    return _planned(question, max_retries=0, reflect_fn=executor.reflect)


def arm_full(question: str) -> tuple[str, list[dict]]:
    return _planned(question, max_retries=1, reflect_fn=executor.reflect)


def arm_full_llm_judge(question: str) -> tuple[str, list[dict]]:
    return _planned(question, max_retries=1, reflect_fn=executor.llm_reflect)


ARMS = {
    "A": ("rag_only", arm_rag_only),
    "B": ("rag_tools", arm_rag_tools),
    "C": ("planner", arm_planner),
    "D": ("full", arm_full),
    "E": ("full_llm_judge", arm_full_llm_judge),
}


def run_one(arm_key: str, item: dict) -> dict:
    """Exécute une question sur un bras et renvoie ses mesures."""
    question = item["question"]
    _, fn = ARMS[arm_key]

    llm.start_run()
    llm.reset_usage()
    t0 = time.time()
    error = ""
    try:
        verdict = security.screen_query(question)
        if not verdict.allowed:
            answer, memory = verdict.message, []
        else:
            answer, memory = fn(question)
    except (LLMUnavailable, RuntimeError, ValueError) as exc:
        answer, memory, error = f"[erreur] {exc}", [], str(exc)[:200]
    latency = time.time() - t0
    usage = llm.get_usage()

    used = list(dict.fromkeys(m.get("tool", "?") for m in memory))
    expected = item.get("expected_tools") or []
    sources = "\n".join(str(m.get("result", "")) for m in memory)
    category = item.get("category", "")
    out_of_corpus = category.startswith("hors")

    return {
        "id": item["id"],
        "category": category,
        "arm": arm_key,
        "used": used,
        "covered": all(t in used for t in expected) if expected else None,
        "refused": _is_refusal(answer),
        "refusal_ok": _is_refusal(answer) if out_of_corpus else None,
        "ungrounded": _ungrounded_numbers(answer, sources, question),
        "latency": latency,
        "tokens": usage["in_tokens"] + usage["out_tokens"],
        "llm_calls": usage["calls"],
        "error": error,
        "answer": answer,
    }


def aggregate(rows: list[dict]) -> dict:
    """Agrège les mesures d'un bras."""
    n = len(rows)
    cov = [r for r in rows if r["covered"] is not None]
    ref = [r for r in rows if r["refusal_ok"] is not None]
    return {
        "n": n,
        "coverage": f"{sum(r['covered'] for r in cov)}/{len(cov)}" if cov else "—",
        "refusal": f"{sum(r['refusal_ok'] for r in ref)}/{len(ref)}" if ref else "—",
        "ungrounded_q": sum(1 for r in rows if r["ungrounded"]),
        "ungrounded_n": sum(len(r["ungrounded"]) for r in rows),
        "latency": sum(r["latency"] for r in rows) / n if n else 0.0,
        "tokens": sum(r["tokens"] for r in rows),
        "llm_calls": sum(r["llm_calls"] for r in rows) / n if n else 0.0,
        "errors": sum(1 for r in rows if r["error"]),
    }


def build_report(by_arm: dict[str, list[dict]], set_name: str, model: str, dt: float) -> str:
    head = [
        f"# Ablation architecturale — {set_name}",
        "",
        f"Modèle : `{model}` — {len(next(iter(by_arm.values())))} question(s) par bras — "
        f"temps total : {dt:.0f}s",
        "",
        "Chaque bras traite LES MÊMES questions. La sécurité, la synthèse ancrée et le "
        "garde-fou hors-corpus sont identiques partout : la seule variable est "
        "l'architecture agentique.",
        "",
        "| Bras | Couverture outils | Refus corrects | Q. avec nombre non étayé | Nombres non étayés | Appels LLM / Q | Tokens | Latence moy. | Erreurs |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for key, rows in by_arm.items():
        a = aggregate(rows)
        label = f"**{key} · {ARMS[key][0]}**"
        head.append(
            f"| {label} | {a['coverage']} | {a['refusal']} | {a['ungrounded_q']}/{a['n']} | "
            f"{a['ungrounded_n']} | {a['llm_calls']:.1f} | {a['tokens']} | "
            f"{a['latency']:.1f}s | {a['errors']} |"
        )
    head += [
        "",
        "## Comment lire",
        "",
        "- **A→B** isole l'apport de l'outillage, **B→C** celui de la planification, "
        "**C→D** celui de la boucle de correction, **D→E** le coût d'un juge sémantique.",
        "- **Refus corrects** ne porte que sur les questions hors-corpus : c'est la mesure "
        "d'hallucination la plus dure du jeu.",
        "- **Nombre non étayé** est un PROXY d'hallucination : un chiffre de la réponse "
        "finale qu'on ne retrouve ni dans un résultat d'outil ni dans la question. Il "
        "détecte un chiffre sorti de nulle part, pas un chiffre correct mal employé. Les "
        "entiers < 10 sont ignorés (numéros d'étape, échelles).",
        "- La **justesse** de la réponse n'est pas notée automatiquement : aucun juge LLM "
        "n'intervient dans la notation, pour éviter d'évaluer un LLM par un LLM.",
        "",
        "---",
        "",
    ]
    for key, rows in by_arm.items():
        head.append(f"## Bras {key} — {ARMS[key][0]}\n")
        for r in rows:
            marks = []
            if r["covered"] is not None:
                marks.append("couverture " + ("✓" if r["covered"] else "✗"))
            if r["refusal_ok"] is not None:
                marks.append("refus " + ("✓" if r["refusal_ok"] else "✗"))
            if r["ungrounded"]:
                marks.append("non étayés : " + ", ".join(r["ungrounded"][:5]))
            head.append(
                f"- `{r['id']}` [{r['category']}] — outils {r['used'] or '—'} · "
                f"{r['latency']:.1f}s · ~{r['tokens']} tok"
                + (" · " + " · ".join(marks) if marks else "")
                + (f" · ERREUR {r['error']}" if r["error"] else "")
            )
        head.append("")
    return "\n".join(head)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arms", default="A,B,C,D,E", help="bras à exécuter (défaut : tous)")
    ap.add_argument("--set", dest="qset", default=str(DEFAULT_SET), help="jeu de questions")
    ap.add_argument("--limit", type=int, default=0, help="ne traiter que les N premières")
    args = ap.parse_args()

    keys = [k.strip().upper() for k in args.arms.split(",") if k.strip()]
    unknown = [k for k in keys if k not in ARMS]
    if unknown:
        ap.error(f"bras inconnu(s) : {', '.join(unknown)} — attendus : {', '.join(ARMS)}")

    path = Path(args.qset)
    if not path.exists():
        path = HERE / args.qset
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    items = data["items"][: args.limit] if args.limit else data["items"]

    try:
        model = str(llm._client().model_id).replace("/", "-")
    except Exception:
        model = "model"

    by_arm: dict[str, list[dict]] = {}
    t0 = time.time()
    for key in keys:
        print(f"\n===== Bras {key} — {ARMS[key][0]} =====")
        rows = []
        for i, item in enumerate(items, 1):
            print(f"  {i}/{len(items)} {item['id']}", flush=True)
            row = run_one(key, item)
            rows.append(row)
            print(
                f"    outils={row['used']} · {row['latency']:.1f}s · ~{row['tokens']} tok"
                + (f" · non étayés {len(row['ungrounded'])}" if row["ungrounded"] else "")
            )
        by_arm[key] = rows

    dt = time.time() - t0
    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"ablation_{path.stem}_{model}.md"
    out.write_text(build_report(by_arm, path.name, model, dt), encoding="utf-8")
    print(f"\nRapport écrit dans {out.relative_to(ROOT)} ({dt:.0f}s).")
    for key, rows in by_arm.items():
        a = aggregate(rows)
        print(
            f"  {key} {ARMS[key][0]:<15} couverture {a['coverage']:<6} refus {a['refusal']:<5} "
            f"non étayés {a['ungrounded_n']:<4} tokens {a['tokens']:<8} {a['latency']:.0f}s/Q"
        )


if __name__ == "__main__":
    main()
